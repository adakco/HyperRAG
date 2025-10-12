"""
Policy Service
OPA-based policy enforcement and access control for HyperRAG system
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

import asyncpg
import structlog
from cloudevents.http import CloudEvent
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from nats.aio.client import Client as NATS
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import httpx
from jose import JWTError, jwt
import jsonschema

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_logger_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configure OpenTelemetry
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics
policy_evaluation_counter = Counter(
    'hyperrag_policy_evaluations_total',
    'Total number of policy evaluations',
    ['tenant', 'operation', 'result']
)

policy_evaluation_duration = Histogram(
    'hyperrag_policy_evaluation_duration_seconds',
    'Time spent on policy evaluations',
    ['tenant', 'operation']
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://hyperrag:password123@localhost:5432/hyperrag"
    redis_url: str = "redis://localhost:6379"
    nats_url: str = "nats://localhost:4222"
    service_name: str = "policy"
    log_level: str = "INFO"
    
    # JWT settings
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # OPA settings
    opa_url: str = "http://localhost:8181"
    
    class Config:
        env_file = ".env"


class PolicyRequest(BaseModel):
    """Request model for policy evaluation"""
    operation: str
    tenant: str
    user_id: Optional[str] = None
    resource: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    jwt_token: Optional[str] = None


class PolicyResponse(BaseModel):
    """Response model for policy evaluation"""
    allowed: bool
    reason: str
    tenant: str
    user_id: Optional[str] = None
    operation: str
    resource: Optional[str] = None
    evaluation_time_ms: int


class JWTClaims(BaseModel):
    """JWT claims model"""
    tenant: str
    user_id: str
    role: str
    permissions: List[str] = Field(default_factory=list)
    exp: int
    iat: int
    sub: str


class OPAClient:
    """OPA client for policy evaluation"""
    
    def __init__(self, opa_url: str):
        self.opa_url = opa_url
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def evaluate_policy(self, policy_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate policy with OPA"""
        try:
            response = await self.client.post(
                f"{self.opa_url}/v1/data/{policy_name}",
                json={"input": input_data}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("OPA policy evaluation failed", error=str(e), policy=policy_name)
            raise
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class PolicyService:
    """Main policy service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.opa_client = OPAClient(settings.opa_url)
        
    async def initialize(self):
        """Initialize database connections and clients"""
        # Database connection pool
        self.db_pool = await asyncpg.create_pool(
            self.settings.database_url,
            min_size=5,
            max_size=20
        )
        
        # Redis client
        self.redis_client = redis.from_url(self.settings.redis_url)
        
        # NATS client
        self.nats_client = NATS()
        await self.nats_client.connect(self.settings.nats_url)
        
        logger.info("Policy service initialized successfully")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
        await self.opa_client.close()
    
    def decode_jwt_token(self, token: str) -> Optional[JWTClaims]:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token, 
                self.settings.jwt_secret_key, 
                algorithms=[self.settings.jwt_algorithm]
            )
            return JWTClaims(**payload)
        except JWTError as e:
            logger.warning("JWT token validation failed", error=str(e))
            return None
    
    async def evaluate_policy(
        self,
        request: PolicyRequest
    ) -> PolicyResponse:
        """Evaluate policy for the given request"""
        
        with tracer.start_as_current_span("evaluate_policy") as span:
            span.set_attribute("operation", request.operation)
            span.set_attribute("tenant", request.tenant)
            
            start_time = datetime.utcnow()
            
            # Decode JWT token if provided
            jwt_claims = None
            if request.jwt_token:
                jwt_claims = self.decode_jwt_token(request.jwt_token)
            
            # Prepare input for OPA
            opa_input = {
                "operation": request.operation,
                "tenant": request.tenant,
                "user_id": request.user_id,
                "resource": request.resource,
                "context": request.context,
                "jwt": {
                    "tenant": jwt_claims.tenant if jwt_claims else None,
                    "user_id": jwt_claims.user_id if jwt_claims else None,
                    "role": jwt_claims.role if jwt_claims else None,
                    "permissions": jwt_claims.permissions if jwt_claims else []
                } if jwt_claims else {}
            }
            
            # Determine policy name based on operation
            policy_name = self._get_policy_name(request.operation)
            
            try:
                # Evaluate policy with OPA
                opa_result = await self.opa_client.evaluate_policy(policy_name, opa_input)
                
                # Extract decision
                allowed = opa_result.get("result", {}).get("allow", False)
                reason = opa_result.get("result", {}).get("reason", "Policy evaluation completed")
                
            except Exception as e:
                logger.error("Policy evaluation failed", error=str(e), operation=request.operation)
                # Default to deny on error
                allowed = False
                reason = f"Policy evaluation error: {str(e)}"
            
            evaluation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update metrics
            policy_evaluation_counter.labels(
                tenant=request.tenant,
                operation=request.operation,
                result="allow" if allowed else "deny"
            ).inc()
            
            policy_evaluation_duration.labels(
                tenant=request.tenant,
                operation=request.operation
            ).observe(evaluation_time / 1000)
            
            # Log policy decision
            logger.info("Policy evaluation completed",
                       operation=request.operation,
                       tenant=request.tenant,
                       allowed=allowed,
                       reason=reason)
            
            return PolicyResponse(
                allowed=allowed,
                reason=reason,
                tenant=request.tenant,
                user_id=request.user_id,
                operation=request.operation,
                resource=request.resource,
                evaluation_time_ms=int(evaluation_time)
            )
    
    def _get_policy_name(self, operation: str) -> str:
        """Get OPA policy name based on operation"""
        policy_mapping = {
            "execute_agent": "hyperrag/agent_policies",
            "invoke_tool": "hyperrag/agent_policies",
            "read_document": "hyperrag/tenant_isolation",
            "write_document": "hyperrag/tenant_isolation",
            "access_tenant": "hyperrag/tenant_isolation"
        }
        return policy_mapping.get(operation, "hyperrag/default")
    
    async def create_audit_log(
        self,
        operation: str,
        tenant: str,
        user_id: Optional[str],
        resource: Optional[str],
        allowed: bool,
        reason: str
    ):
        """Create audit log entry"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO audit_logs 
                    (operation, tenant, user_id, resource, allowed, reason, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """, operation, tenant, user_id, resource, allowed, reason)
        except Exception as e:
            logger.error("Failed to create audit log", error=str(e))


# Global service instance
settings = Settings()
policy_service = PolicyService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Policy Service",
    description="OPA-based policy enforcement and access control",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await policy_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await policy_service.close()


@app.post("/evaluate", response_model=PolicyResponse)
async def evaluate_policy(request: PolicyRequest):
    """Evaluate policy for the given request"""
    try:
        response = await policy_service.evaluate_policy(request)
        
        # Create audit log
        await policy_service.create_audit_log(
            operation=request.operation,
            tenant=request.tenant,
            user_id=request.user_id,
            resource=request.resource,
            allowed=response.allowed,
            reason=response.reason
        )
        
        return response
    except Exception as e:
        logger.error("Policy evaluation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "policy"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/audit-logs")
async def get_audit_logs(
    tenant: str,
    limit: int = 100,
    offset: int = 0
):
    """Get audit logs for a tenant"""
    async with policy_service.db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT operation, tenant, user_id, resource, allowed, reason, created_at
            FROM audit_logs
            WHERE tenant = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, tenant, limit, offset)
        
        return [
            {
                "operation": r["operation"],
                "tenant": r["tenant"],
                "user_id": r["user_id"],
                "resource": r["resource"],
                "allowed": r["allowed"],
                "reason": r["reason"],
                "created_at": r["created_at"].isoformat()
            }
            for r in results
        ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8007,
        reload=True,
        log_level=settings.log_level.lower()
    )
