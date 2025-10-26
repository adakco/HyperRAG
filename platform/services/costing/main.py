"""
Costing Service
Cost tracking and billing for HyperRAG system operations
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_HALF_UP

import asyncpg
import structlog
from cloudevents.http import CloudEvent
from fastapi import FastAPI, HTTPException, Depends
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
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from fastapi.responses import Response

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
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

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics with custom registry to avoid conflicts
registry = CollectorRegistry()
cost_tracking_counter = Counter(
    'hyperrag_cost_tracking_total',
    'Total number of cost tracking operations',
    ['tenant', 'operation', 'status'],
    registry=registry
)

cost_amount = Histogram(
    'hyperrag_cost_amount',
    'Cost amounts by operation',
    ['tenant', 'operation'],
    registry=registry
)

budget_usage = Histogram(
    'hyperrag_budget_usage_ratio',
    'Budget usage ratio by tenant',
    ['tenant'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    service_name: str = "costing"
    log_level: str = "INFO"
    
    # Cost rates (per unit)
    embedding_cost_per_token: float = 0.0001
    retrieval_cost_per_query: float = 0.0005
    rerank_cost_per_query: float = 0.0002
    evaluation_cost_per_metric: float = 0.0001
    agent_cost_per_step: float = 0.001
    
    # Budget limits
    default_monthly_budget: float = 100.0
    budget_alert_threshold: float = 0.8  # 80% of budget
    
    class Config:
        env_file = ".env"


class CostEntry(BaseModel):
    """Cost entry model"""
    operation: str
    tenant: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    cost_amount: Decimal
    currency: str = "USD"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BudgetInfo(BaseModel):
    """Budget information model"""
    tenant: str
    monthly_budget: Decimal
    current_usage: Decimal
    usage_percentage: float
    remaining_budget: Decimal
    days_remaining: int
    projected_usage: Decimal


class CostSummary(BaseModel):
    """Cost summary model"""
    tenant: str
    period_start: datetime
    period_end: datetime
    total_cost: Decimal
    operation_breakdown: Dict[str, Decimal]
    daily_average: Decimal
    projected_monthly: Decimal


class CostCalculator:
    """Cost calculation utilities"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def calculate_embedding_cost(self, token_count: int) -> Decimal:
        """Calculate embedding cost based on token count"""
        cost = Decimal(str(token_count)) * Decimal(str(self.settings.embedding_cost_per_token))
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def calculate_retrieval_cost(self, query_count: int = 1) -> Decimal:
        """Calculate retrieval cost"""
        cost = Decimal(str(query_count)) * Decimal(str(self.settings.retrieval_cost_per_query))
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def calculate_rerank_cost(self, query_count: int = 1) -> Decimal:
        """Calculate re-ranking cost"""
        cost = Decimal(str(query_count)) * Decimal(str(self.settings.rerank_cost_per_query))
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def calculate_evaluation_cost(self, metric_count: int) -> Decimal:
        """Calculate evaluation cost"""
        cost = Decimal(str(metric_count)) * Decimal(str(self.settings.evaluation_cost_per_metric))
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def calculate_agent_cost(self, step_count: int) -> Decimal:
        """Calculate agent execution cost"""
        cost = Decimal(str(step_count)) * Decimal(str(self.settings.agent_cost_per_step))
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)


class CostingService:
    """Main costing service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.calculator = CostCalculator(settings)
        
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
        
        # Create cost tracking table if not exists
        await self._create_cost_tables()
        
        logger.info("Costing service initialized successfully")
    
    async def _create_cost_tables(self):
        """Create cost tracking tables"""
        async with self.db_pool.acquire() as conn:
            # Cost entries table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_entries (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    operation TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    cost_amount DECIMAL(10,6) NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Budgets table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_budgets (
                    tenant TEXT PRIMARY KEY,
                    monthly_budget DECIMAL(10,2) NOT NULL DEFAULT 100.0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_entries_tenant_created 
                ON cost_entries(tenant, created_at)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cost_entries_operation 
                ON cost_entries(operation)
            """)
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
    
    async def track_cost(
        self,
        operation: str,
        tenant: str,
        cost_amount: Decimal,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CostEntry:
        """Track a cost entry"""
        
        with tracer.start_as_current_span("track_cost") as span:
            span.set_attribute("operation", operation)
            span.set_attribute("tenant", tenant)
            span.set_attribute("cost_amount", float(cost_amount))
            
            cost_entry = CostEntry(
                operation=operation,
                tenant=tenant,
                user_id=user_id,
                session_id=session_id,
                cost_amount=cost_amount,
                metadata=metadata or {}
            )
            
            # Store in database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO cost_entries 
                    (operation, tenant, user_id, session_id, cost_amount, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, operation, tenant, user_id, session_id, cost_amount, json.dumps(metadata or {}))
            
            # Update Redis cache for quick budget checks
            await self._update_budget_cache(tenant, cost_amount)
            
            # Check budget alerts
            await self._check_budget_alerts(tenant)
            
            # Update metrics
            cost_tracking_counter.labels(
                tenant=tenant,
                operation=operation,
                status="success"
            ).inc()
            
            cost_amount.labels(
                tenant=tenant,
                operation=operation
            ).observe(float(cost_amount))
            
            logger.info("Cost tracked successfully",
                       operation=operation,
                       tenant=tenant,
                       cost_amount=float(cost_amount))
            
            return cost_entry
    
    async def _update_budget_cache(self, tenant: str, cost_amount: Decimal):
        """Update budget cache in Redis"""
        try:
            current_month = datetime.utcnow().strftime("%Y-%m")
            cache_key = f"budget:{tenant}:{current_month}"
            
            # Get current usage
            current_usage = await self.redis_client.get(cache_key)
            if current_usage:
                current_usage = Decimal(current_usage)
            else:
                current_usage = Decimal('0')
            
            # Add new cost
            new_usage = current_usage + cost_amount
            await self.redis_client.set(cache_key, str(new_usage), ex=86400 * 32)  # 32 days TTL
            
        except Exception as e:
            logger.error("Failed to update budget cache", error=str(e))
    
    async def _check_budget_alerts(self, tenant: str):
        """Check if budget alerts should be sent"""
        try:
            budget_info = await self.get_budget_info(tenant)
            
            if budget_info.usage_percentage >= self.settings.budget_alert_threshold:
                # Send budget alert
                alert_event = CloudEvent(
                    specversion="1.0",
                    id=str(uuid.uuid4()),
                    source="service/costing",
                    type="budget.alert.v1",
                    time=datetime.utcnow(),
                    datacontenttype="application/json",
                    data={
                        "tenant": tenant,
                        "usage_percentage": budget_info.usage_percentage,
                        "current_usage": float(budget_info.current_usage),
                        "monthly_budget": float(budget_info.monthly_budget),
                        "alert_threshold": self.settings.budget_alert_threshold
                    }
                )
                
                # Publish alert to NATS
                event_data = json.dumps({
                    "specversion": alert_event["specversion"],
                    "id": alert_event["id"],
                    "source": alert_event["source"],
                    "type": alert_event["type"],
                    "time": alert_event["time"].isoformat(),
                    "datacontenttype": alert_event["datacontenttype"],
                    "data": alert_event["data"]
                })
                
                await self.nats_client.publish("budget.alert.v1", str(event_data).encode())
                
                logger.warning("Budget alert sent",
                              tenant=tenant,
                              usage_percentage=budget_info.usage_percentage)
        
        except Exception as e:
            logger.error("Failed to check budget alerts", error=str(e))
    
    async def get_budget_info(self, tenant: str) -> BudgetInfo:
        """Get budget information for a tenant"""
        current_month = datetime.utcnow().strftime("%Y-%m")
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        async with self.db_pool.acquire() as conn:
            # Get monthly budget
            budget_row = await conn.fetchrow(
                "SELECT monthly_budget FROM tenant_budgets WHERE tenant = $1",
                tenant
            )
            
            if not budget_row:
                # Create default budget
                await conn.execute("""
                    INSERT INTO tenant_budgets (tenant, monthly_budget)
                    VALUES ($1, $2)
                    ON CONFLICT (tenant) DO NOTHING
                """, tenant, self.settings.default_monthly_budget)
                monthly_budget = Decimal(str(self.settings.default_monthly_budget))
            else:
                monthly_budget = budget_row['monthly_budget']
            
            # Get current usage
            usage_row = await conn.fetchrow("""
                SELECT COALESCE(SUM(cost_amount), 0) as total_cost
                FROM cost_entries
                WHERE tenant = $1 AND created_at >= $2 AND created_at <= $3
            """, tenant, month_start, month_end)
            
            current_usage = usage_row['total_cost'] if usage_row else Decimal('0')
        
        # Calculate metrics
        usage_percentage = float(current_usage / monthly_budget * 100) if monthly_budget > 0 else 0
        remaining_budget = monthly_budget - current_usage
        
        # Calculate days remaining in month
        today = datetime.utcnow()
        days_remaining = (month_end - today).days + 1
        
        # Projected usage based on current rate
        if today.day > 1:
            daily_average = current_usage / (today.day - 1)
            projected_usage = daily_average * 30  # 30-day month
        else:
            projected_usage = current_usage
        
        return BudgetInfo(
            tenant=tenant,
            monthly_budget=monthly_budget,
            current_usage=current_usage,
            usage_percentage=usage_percentage,
            remaining_budget=remaining_budget,
            days_remaining=days_remaining,
            projected_usage=projected_usage
        )
    
    async def get_cost_summary(
        self,
        tenant: str,
        start_date: datetime,
        end_date: datetime
    ) -> CostSummary:
        """Get cost summary for a period"""
        
        async with self.db_pool.acquire() as conn:
            # Get total cost and breakdown
            summary_row = await conn.fetchrow("""
                SELECT 
                    COALESCE(SUM(cost_amount), 0) as total_cost,
                    json_object_agg(operation, operation_cost) as operation_breakdown
                FROM (
                    SELECT 
                        operation,
                        SUM(cost_amount) as operation_cost
                    FROM cost_entries
                    WHERE tenant = $1 AND created_at >= $2 AND created_at <= $3
                    GROUP BY operation
                ) breakdown
            """, tenant, start_date, end_date)
            
            total_cost = summary_row['total_cost'] if summary_row else Decimal('0')
            operation_breakdown = summary_row['operation_breakdown'] if summary_row else {}
            
            # Calculate daily average
            days = (end_date - start_date).days + 1
            daily_average = total_cost / days if days > 0 else Decimal('0')
            
            # Project monthly usage
            projected_monthly = daily_average * 30
        
        return CostSummary(
            tenant=tenant,
            period_start=start_date,
            period_end=end_date,
            total_cost=total_cost,
            operation_breakdown=operation_breakdown,
            daily_average=daily_average,
            projected_monthly=projected_monthly
        )


# Global service instance
settings = Settings()
costing_service = CostingService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Costing Service",
    description="Cost tracking and billing for HyperRAG operations",
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
    await costing_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await costing_service.close()


@app.post("/track-cost")
async def track_cost(
    operation: str,
    tenant: str,
    cost_amount: float,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Track a cost entry"""
    try:
        cost_entry = await costing_service.track_cost(
            operation=operation,
            tenant=tenant,
            cost_amount=Decimal(str(cost_amount)),
            user_id=user_id,
            session_id=session_id,
            metadata=metadata
        )
        
        return {
            "id": str(cost_entry.id) if hasattr(cost_entry, 'id') else None,
            "operation": cost_entry.operation,
            "tenant": cost_entry.tenant,
            "cost_amount": float(cost_entry.cost_amount),
            "created_at": cost_entry.created_at.isoformat()
        }
    except Exception as e:
        logger.error("Cost tracking failed", error=str(e))
        cost_tracking_counter.labels(
            tenant=tenant,
            operation=operation,
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/budget/{tenant}")
async def get_budget_info(tenant: str):
    """Get budget information for a tenant"""
    try:
        budget_info = await costing_service.get_budget_info(tenant)
        return {
            "tenant": budget_info.tenant,
            "monthly_budget": float(budget_info.monthly_budget),
            "current_usage": float(budget_info.current_usage),
            "usage_percentage": budget_info.usage_percentage,
            "remaining_budget": float(budget_info.remaining_budget),
            "days_remaining": budget_info.days_remaining,
            "projected_usage": float(budget_info.projected_usage)
        }
    except Exception as e:
        logger.error("Failed to get budget info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cost-summary/{tenant}")
async def get_cost_summary(
    tenant: str,
    start_date: datetime,
    end_date: datetime
):
    """Get cost summary for a period"""
    try:
        summary = await costing_service.get_cost_summary(tenant, start_date, end_date)
        return {
            "tenant": summary.tenant,
            "period_start": summary.period_start.isoformat(),
            "period_end": summary.period_end.isoformat(),
            "total_cost": float(summary.total_cost),
            "operation_breakdown": {k: float(v) for k, v in summary.operation_breakdown.items()},
            "daily_average": float(summary.daily_average),
            "projected_monthly": float(summary.projected_monthly)
        }
    except Exception as e:
        logger.error("Failed to get cost summary", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "costing"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8008,
        reload=False,
        log_level=settings.log_level.lower()
    )
