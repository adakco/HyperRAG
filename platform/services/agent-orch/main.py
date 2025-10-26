"""
Agent Orchestrator Service
MCP-Native agent orchestration with LangGraph integration and abstraction layer
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

import asyncpg
import structlog
from cloudevents.http import CloudEvent
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Form
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
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import jsonschema
from jsonschema import validate

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
agent_session_counter = Counter(
    'hyperrag_agent_sessions_total',
    'Total number of agent sessions',
    ['tenant', 'lang', 'status'],
    registry=registry
)

agent_step_counter = Counter(
    'hyperrag_agent_steps_total',
    'Total number of agent steps',
    ['tenant', 'lang', 'tool_name', 'status'],
    registry=registry
)

agent_duration = Histogram(
    'hyperrag_agent_duration_seconds',
    'Time spent on agent sessions',
    ['tenant', 'lang'],
    registry=registry
)

agent_cost = Histogram(
    'hyperrag_agent_cost_total',
    'Cost per agent session',
    ['tenant', 'lang'],
    registry=registry
)


class SessionStatus(str, Enum):
    """Agent session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class StepStatus(str, Enum):
    """Agent step status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    service_name: str = "agent-orch"
    log_level: str = "INFO"

    # LLM configurations - Using OpenRouter
    openrouter_api_key: str = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_base_url: str = Field(default_factory=lambda: os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    llm_model: str = "deepseek/deepseek-chat"

    # Agent configurations
    max_steps: int = 10
    max_cost: float = 0.01
    timeout_seconds: int = 300

    # MCP tool endpoints - Updated to run on host
    retriever_url: str = "http://localhost:8002"
    evaluator_url: str = "http://localhost:8005"
    
    class Config:
        env_file = ".env"


class AgentSession(BaseModel):
    """Agent session model"""
    session_id: str
    tenant: str
    user_id: Optional[str] = None
    query: str
    lang: str = Field(..., enum=["en", "fa"])
    token_budget: int = 4000
    max_steps: int = 10
    status: SessionStatus = SessionStatus.ACTIVE
    final_response: Optional[str] = None
    total_cost: float = 0.0
    citations: List[Dict] = []
    trace_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class AgentStep(BaseModel):
    """Agent step model"""
    step_id: str
    session_id: str
    step_number: int
    tool_name: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    status: StepStatus = StepStatus.PENDING
    error_message: Optional[str] = None
    cost: float = 0.0
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class MCPTool:
    """MCP Tool abstraction"""
    
    def __init__(self, name: str, url: str, input_schema: Dict, output_schema: Dict):
        self.name = name
        self.url = url
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the MCP tool"""
        # Validate input
        try:
            validate(input_data, self.input_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Invalid input for {self.name}: {e.message}")
        
        # Make request
        response = await self.client.post(f"{self.url}/invoke", json=input_data)
        response.raise_for_status()
        
        result = response.json()
        
        # Validate output
        try:
            validate(result, self.output_schema)
        except jsonschema.ValidationError as e:
            logger.warning(f"Output validation failed for {self.name}: {e.message}")
        
        return result
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class AgentOrchestrator:
    """Main agent orchestrator class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.tools: Dict[str, MCPTool] = {}
        
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
        
        # Initialize MCP tools
        await self._initialize_tools()
        
        logger.info("Agent orchestrator initialized successfully")
    
    async def _initialize_tools(self):
        """Initialize MCP tools"""
        # Retriever tool
        retriever_input_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "lang": {"type": "string", "enum": ["en", "fa"]},
                "tenant": {"type": "string"},
                "k_final": {"type": "integer", "default": 10},
                "rerank": {"type": "boolean", "default": True}
            },
            "required": ["query", "lang", "tenant"]
        }
        
        retriever_output_schema = {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "metadata": {"type": "object"},
                "cost": {"type": "object"}
            },
            "required": ["results", "metadata", "cost"]
        }
        
        self.tools["retriever.mcp"] = MCPTool(
            "retriever.mcp",
            self.settings.retriever_url,
            retriever_input_schema,
            retriever_output_schema
        )
        
        # Evaluator tool
        evaluator_input_schema = {
            "type": "object",
            "properties": {
                "lang": {"type": "string", "enum": ["en", "fa"]},
                "tenant": {"type": "string"},
                "query": {"type": "string"},
                "answer": {"type": "string"},
                "contexts": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["lang", "tenant", "query", "answer", "contexts"]
        }
        
        evaluator_output_schema = {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "overall_score": {"type": "number"},
                "passed": {"type": "boolean"}
            },
            "required": ["results", "overall_score", "passed"]
        }
        
        self.tools["evaluator.ragas.mcp"] = MCPTool(
            "evaluator.ragas.mcp",
            self.settings.evaluator_url,
            evaluator_input_schema,
            evaluator_output_schema
        )
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
        
        # Close tool clients
        for tool in self.tools.values():
            await tool.close()
    
    async def start_session(
        self,
        query: str,
        lang: str,
        tenant: str,
        user_id: Optional[str] = None,
        token_budget: int = 4000,
        max_steps: int = 10
    ) -> AgentSession:
        """Start a new agent session"""
        
        session_id = str(uuid.uuid4())
        trace_id = uuid.uuid4().hex
        
        session = AgentSession(
            session_id=session_id,
            tenant=tenant,
            user_id=user_id,
            query=query,
            lang=lang,
            token_budget=token_budget,
            max_steps=max_steps,
            trace_id=trace_id
        )
        
        # Store session in database
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO agent_sessions 
                (session_id, tenant, user_id, query, lang, token_budget, max_steps, status, trace_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, session_id, tenant, user_id, query, lang, token_budget, max_steps, SessionStatus.ACTIVE, trace_id)
        
        logger.info("Agent session started", session_id=session_id, query=query, lang=lang)
        return session
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def invoke_tool(
        self,
        session_id: str,
        tool_name: str,
        input_data: Dict[str, Any],
        traceparent: str
    ) -> Dict[str, Any]:
        """Invoke an MCP tool"""
        
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool = self.tools[tool_name]
        step_id = str(uuid.uuid4())
        
        # Create step record
        step = AgentStep(
            step_id=step_id,
            session_id=session_id,
            step_number=0,  # Will be updated
            tool_name=tool_name,
            input_data=input_data,
            status=StepStatus.RUNNING
        )
        
        # Store step in database
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO agent_steps 
                (step_id, session_id, step_number, tool_name, input_data, status)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, step_id, session_id, 0, tool_name, json.dumps(input_data), StepStatus.RUNNING)
        
        start_time = datetime.utcnow()
        
        try:
            # Invoke tool
            output_data = await tool.invoke(input_data)
            
            # Calculate cost (simplified)
            cost = 0.001  # Base cost per tool invocation
            
            # Update step
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE agent_steps 
                    SET output_data = $1, status = $2, cost = $3, duration_ms = $4, completed_at = NOW()
                    WHERE step_id = $5
                """, json.dumps(output_data), StepStatus.COMPLETED, cost, duration_ms, step_id)
            
            logger.info("Tool invoked successfully", 
                       tool_name=tool_name, session_id=session_id, duration_ms=duration_ms)
            
            return output_data
            
        except Exception as e:
            # Update step with error
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE agent_steps 
                    SET status = $1, error_message = $2, completed_at = NOW()
                    WHERE step_id = $3
                """, StepStatus.FAILED, str(e), step_id)
            
            logger.error("Tool invocation failed", 
                        tool_name=tool_name, session_id=session_id, error=str(e))
            raise
    
    async def execute_agent_loop(self, session: AgentSession) -> AgentSession:
        """Execute the agent decision loop"""
        
        with tracer.start_as_current_span("execute_agent_loop") as span:
            span.set_attribute("session_id", session.session_id)
            span.set_attribute("query", session.query)
            span.set_attribute("lang", session.lang)
            
            current_query = session.query
            step_number = 0
            
            try:
                while step_number < session.max_steps:
                    step_number += 1
                    
                    # Step 1: Retrieve relevant documents
                    retrieval_input = {
                        "query": current_query,
                        "lang": session.lang,
                        "tenant": session.tenant,
                        "k_final": 5,
                        "rerank": True
                    }
                    
                    retrieval_result = await self.invoke_tool(
                        session.session_id,
                        "retriever.mcp",
                        retrieval_input,
                        session.trace_id or ""
                    )
                    
                    # Extract contexts and citations
                    contexts = [r["content"] for r in retrieval_result["results"]]
                    citations = [
                        {
                            "doc_id": r["doc_id"],
                            "chunk_id": r["chunk_id"],
                            "content": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"]
                        }
                        for r in retrieval_result["results"]
                    ]
                    
                    # Step 2: Generate answer (simplified - in real implementation, use LLM)
                    answer = self._generate_answer(current_query, contexts, session.lang)
                    
                    # Step 3: Evaluate the response
                    evaluation_input = {
                        "lang": session.lang,
                        "tenant": session.tenant,
                        "query": current_query,
                        "answer": answer,
                        "contexts": contexts,
                        "metrics": ["faithfulness", "answer_relevancy"]
                    }
                    
                    evaluation_result = await self.invoke_tool(
                        session.session_id,
                        "evaluator.ragas.mcp",
                        evaluation_input,
                        session.trace_id or ""
                    )
                    
                    # Check if we should continue or stop
                    if evaluation_result["passed"] and evaluation_result["overall_score"] > 0.8:
                        # Good enough, stop here
                        session.final_response = answer
                        session.citations = citations
                        session.status = SessionStatus.COMPLETED
                        break
                    else:
                        # Need to refine, continue loop
                        current_query = f"Refine the answer for: {session.query}"
                        continue
                
                # Update session
                session.completed_at = datetime.utcnow()
                
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE agent_sessions 
                        SET status = $1, final_response = $2, citations = $3, completed_at = $4
                        WHERE session_id = $5
                    """, session.status, session.final_response, json.dumps(session.citations), 
                        session.completed_at, session.session_id)
                
                logger.info("Agent session completed", 
                           session_id=session.session_id, status=session.status)
                
                return session
                
            except Exception as e:
                # Mark session as failed
                session.status = SessionStatus.FAILED
                session.completed_at = datetime.utcnow()
                
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE agent_sessions 
                        SET status = $1, completed_at = $2
                        WHERE session_id = $3
                    """, session.status, session.completed_at, session.session_id)
                
                logger.error("Agent session failed", 
                            session_id=session.session_id, error=str(e))
                raise
    
    def _generate_answer(self, query: str, contexts: List[str], lang: str) -> str:
        """Generate answer from query and contexts (simplified)"""
        # In a real implementation, this would use an LLM
        context_text = " ".join(contexts[:3])  # Use top 3 contexts
        
        if lang == "fa":
            return f"بر اساس اطلاعات موجود: {context_text[:500]}..."
        else:
            return f"Based on the available information: {context_text[:500]}..."


# Global service instance
settings = Settings()
orchestrator = AgentOrchestrator(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Agent Orchestrator",
    description="MCP-Native agent orchestration with LangGraph integration",
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
    await orchestrator.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await orchestrator.close()


@app.post("/session/start")
async def start_agent_session_new(
    request: dict,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Start a new agent session (new format for testing)"""

    try:
        session = await orchestrator.start_session(
            query=request.get("initial_query", ""),
            lang="en",
            tenant=request.get("tenant", "test"),
            user_id=request.get("user_id", "test_user"),
            token_budget=4000,
            max_steps=10
        )

        return {
            "session_id": str(session.session_id),
            "status": "started",
            "message": "Agent session started successfully"
        }

    except Exception as e:
        logger.error("Failed to start agent session", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions")
async def start_agent_session(
    query: str = Form(...),
    lang: str = Form(...),
    tenant: str = Form(...),
    user_id: Optional[str] = Form(None),
    token_budget: int = Form(4000),
    max_steps: int = Form(10),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Start a new agent session"""
    
    try:
        session = await orchestrator.start_session(
            query=query,
            lang=lang,
            tenant=tenant,
            user_id=user_id,
            token_budget=token_budget,
            max_steps=max_steps
        )
        
        # Start agent loop in background
        background_tasks.add_task(orchestrator.execute_agent_loop, session)
        
        agent_session_counter.labels(
            tenant=tenant,
            lang=lang,
            status="started"
        ).inc()
        
        return {
            "session_id": session.session_id,
            "status": session.status,
            "trace_id": session.trace_id,
            "created_at": session.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to start agent session", error=str(e))
        agent_session_counter.labels(
            tenant=tenant,
            lang=lang,
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    """Get agent session status"""
    async with orchestrator.db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT session_id, status, final_response, citations, total_cost, created_at, completed_at
            FROM agent_sessions
            WHERE session_id = $1
        """, session_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": result["session_id"],
            "status": result["status"],
            "final_response": result["final_response"],
            "citations": result["citations"],
            "total_cost": float(result["total_cost"]),
            "created_at": result["created_at"].isoformat(),
            "completed_at": result["completed_at"].isoformat() if result["completed_at"] else None
        }


@app.get("/sessions/{session_id}/steps")
async def get_session_steps(session_id: str):
    """Get agent session steps"""
    async with orchestrator.db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT step_id, step_number, tool_name, input_data, output_data, status, 
                   error_message, cost, duration_ms, created_at, completed_at
            FROM agent_steps
            WHERE session_id = $1
            ORDER BY step_number ASC
        """, session_id)
        
        return [
            {
                "step_id": r["step_id"],
                "step_number": r["step_number"],
                "tool_name": r["tool_name"],
                "input_data": r["input_data"],
                "output_data": r["output_data"],
                "status": r["status"],
                "error_message": r["error_message"],
                "cost": float(r["cost"]),
                "duration_ms": r["duration_ms"],
                "created_at": r["created_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None
            }
            for r in results
        ]


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "agent-orch"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=False,
        log_level=settings.log_level.lower()
    )
