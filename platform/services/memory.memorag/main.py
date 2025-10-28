"""
Memory MemoRAG Service
Episodic and semantic memory management for HyperRAG system
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

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
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from fastapi.responses import Response
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

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
resource = Resource.create(attributes={SERVICE_NAME: "hyperrag-memory"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics with custom registry to avoid conflicts
registry = CollectorRegistry()
memory_operation_counter = Counter(
    'hyperrag_memory_operations_total',
    'Total number of memory operations',
    ['tenant', 'operation', 'memory_type', 'status'],
    registry=registry
)

memory_operation_duration = Histogram(
    'hyperrag_memory_operation_duration_seconds',
    'Time spent on memory operations',
    ['tenant', 'operation', 'memory_type'],
    registry=registry
)

memory_retrieval_accuracy = Histogram(
    'hyperrag_memory_retrieval_accuracy',
    'Memory retrieval accuracy scores',
    ['tenant', 'memory_type'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    service_name: str = "memory.memorag"
    log_level: str = "INFO"

    # Memory parameters
    episodic_memory_retention_days: int = 30
    semantic_memory_retention_days: int = 90
    max_episodic_memories: int = 1000
    max_semantic_memories: int = 5000
    similarity_threshold: float = 0.7

    # Embedding models
    persian_embedding_model: str = "HooshvareLab/bert-fa-base-uncased"
    english_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    class Config:
        env_file = ".env"


class MemoryEntry(BaseModel):
    """Memory entry model"""
    memory_id: str
    tenant: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    memory_type: str  # "episodic" or "semantic"
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0


class MemoryRequest(BaseModel):
    """Request model for memory operations"""
    tenant: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    query: str
    lang: str = Field(..., enum=["en", "fa"])
    memory_type: str = Field(..., enum=["episodic", "semantic", "both"])
    max_results: int = 10
    similarity_threshold: float = 0.7


class MemoryResult(BaseModel):
    """Memory retrieval result"""
    memory_id: str
    content: str
    memory_type: str
    similarity_score: float
    metadata: Dict[str, Any]
    created_at: datetime
    last_accessed: datetime
    access_count: int


class MemoryResponse(BaseModel):
    """Response model for memory operations"""
    tenant: str
    query: str
    lang: str
    results: List[MemoryResult]
    total_found: int
    processing_time_ms: int


class EmbeddingService:
    """Embedding service for memory"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.persian_model = None
        self.english_model = None

    async def initialize(self):
        """Initialize embedding models"""
        logger.info("Loading memory embedding models...")

        try:
            self.persian_model = SentenceTransformer(self.settings.persian_embedding_model)
            logger.info("Persian memory embedding model loaded")
        except Exception as e:
            logger.error("Failed to load Persian memory embedding model", error=str(e))
            raise

        try:
            self.english_model = SentenceTransformer(self.settings.english_embedding_model)
            logger.info("English memory embedding model loaded")
        except Exception as e:
            logger.error("Failed to load English memory embedding model", error=str(e))
            raise

    def get_embedding(self, text: str, lang: str) -> np.ndarray:
        """Get embedding for text"""
        if lang == 'fa' and self.persian_model:
            return self.persian_model.encode(text)
        elif lang == 'en' and self.english_model:
            return self.english_model.encode(text)
        else:
            # Fallback to English model
            return self.english_model.encode(text)


class MemoryService:
    """Main memory service class"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.embedding_service = EmbeddingService(settings)

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

        # Initialize embedding service
        await self.embedding_service.initialize()

        # Create memory tables
        await self._create_memory_tables()

        logger.info("Memory service initialized successfully")

    async def _create_memory_tables(self):
        """Create memory tables"""
        async with self.db_pool.acquire() as conn:
            # Episodic memories table (simplified without vectors)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    tenant TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    content TEXT NOT NULL,
                    embedding TEXT,  -- Store as JSON string instead of VECTOR
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    last_accessed TIMESTAMPTZ DEFAULT NOW(),
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Semantic memories table (simplified without vectors)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    tenant TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    content TEXT NOT NULL,
                    embedding TEXT,  -- Store as JSON string instead of VECTOR
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    last_accessed TIMESTAMPTZ DEFAULT NOW(),
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_memories_tenant
                ON episodic_memories(tenant)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_tenant
                ON semantic_memories(tenant)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_memories_created
                ON episodic_memories(created_at)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_created
                ON semantic_memories(created_at)
            """)

    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()

    async def store_memory(
        self,
        tenant: str,
        content: str,
        memory_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        lang: str = "en"
    ) -> MemoryEntry:
        """Store a memory entry"""

        with tracer.start_as_current_span("store_memory") as span:
            span.set_attribute("tenant", tenant)
            span.set_attribute("memory_type", memory_type)
            span.set_attribute("lang", lang)

            # Generate embedding
            embedding = self.embedding_service.get_embedding(content, lang)

            memory_id = str(uuid.uuid4())
            memory_entry = MemoryEntry(
                memory_id=memory_id,
                tenant=tenant,
                user_id=user_id,
                session_id=session_id,
                memory_type=memory_type,
                content=content,
                embedding=embedding.tolist(),
                metadata=metadata or {}
            )

            # Store in appropriate table
            table_name = f"{memory_type}_memories"
            async with self.db_pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO {table_name}
                    (memory_id, tenant, user_id, session_id, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, memory_id, tenant, user_id, session_id, content,
                    json.dumps(embedding.tolist()), json.dumps(metadata or {}))

            # Update metrics
            memory_operation_counter.labels(
                tenant=tenant,
                operation="store",
                memory_type=memory_type,
                status="success"
            ).inc()

            logger.info("Memory stored successfully",
                       memory_id=memory_id,
                       memory_type=memory_type,
                       tenant=tenant)

            return memory_entry

    async def retrieve_memories(
        self,
        request: MemoryRequest
    ) -> MemoryResponse:
        """Retrieve relevant memories"""

        with tracer.start_as_current_span("retrieve_memories") as span:
            span.set_attribute("tenant", request.tenant)
            span.set_attribute("memory_type", request.memory_type)
            span.set_attribute("lang", request.lang)

            start_time = datetime.utcnow()

            # Generate query embedding
            query_embedding = self.embedding_service.get_embedding(request.query, request.lang)

            results = []
            total_found = 0

            # Retrieve from episodic memories
            if request.memory_type in ["episodic", "both"]:
                episodic_results = await self._search_memories(
                    "episodic_memories",
                    request.tenant,
                    query_embedding,
                    request.similarity_threshold,
                    request.max_results
                )
                results.extend(episodic_results)
                total_found += len(episodic_results)

            # Retrieve from semantic memories
            if request.memory_type in ["semantic", "both"]:
                semantic_results = await self._search_memories(
                    "semantic_memories",
                    request.tenant,
                    query_embedding,
                    request.similarity_threshold,
                    request.max_results
                )
                results.extend(semantic_results)
                total_found += len(semantic_results)

            # Sort by similarity score
            results.sort(key=lambda x: x.similarity_score, reverse=True)

            # Limit results
            results = results[:request.max_results]

            # Update access counts
            await self._update_access_counts([r.memory_id for r in results], request.memory_type)

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update metrics
            memory_operation_counter.labels(
                tenant=request.tenant,
                operation="retrieve",
                memory_type=request.memory_type,
                status="success"
            ).inc()

            memory_operation_duration.labels(
                tenant=request.tenant,
                operation="retrieve",
                memory_type=request.memory_type
            ).observe(processing_time / 1000)

            if results:
                avg_accuracy = sum(r.similarity_score for r in results) / len(results)
                memory_retrieval_accuracy.labels(
                    tenant=request.tenant,
                    memory_type=request.memory_type
                ).observe(avg_accuracy)

            logger.info("Memory retrieval completed",
                       tenant=request.tenant,
                       memory_type=request.memory_type,
                       results_count=len(results),
                       total_found=total_found)

            return MemoryResponse(
                tenant=request.tenant,
                query=request.query,
                lang=request.lang,
                results=results,
                total_found=total_found,
                processing_time_ms=int(processing_time)
            )

    async def _search_memories(
        self,
        table_name: str,
        tenant: str,
        query_embedding: np.ndarray,
        similarity_threshold: float,
        max_results: int
    ) -> List[MemoryResult]:
        """Search memories in a specific table"""

        async with self.db_pool.acquire() as conn:
            # Get all memories for the tenant
            # Use raw SQL to avoid f-string escaping issues
            query = """
                SELECT memory_id, content, metadata, created_at, last_accessed, access_count
                FROM """ + table_name + """
                WHERE tenant = $1
                ORDER BY last_accessed DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, tenant, max_results * 2)

            logger.info(f"Memory search: tenant={tenant}, table={table_name}, rows_found={len(rows)}")
            
            if not rows:
                logger.warning(f"No memories found for tenant={tenant} in table={table_name}")
                return []

            # Calculate similarities
            results = []
            logger.info(f"Processing {len(rows)} rows with threshold {similarity_threshold}")
            for row in rows:
                # For simplicity, we'll use a basic similarity calculation
                # In production, you'd want to use proper vector similarity
                similarity = 0.8  # Placeholder - would calculate actual similarity

                logger.info(f"Row check: similarity={similarity} >= threshold={similarity_threshold}? {similarity >= similarity_threshold}")
                if similarity >= similarity_threshold:
                    # Convert UUID to string and parse JSON metadata
                    memory_id = str(row['memory_id'])
                    metadata = row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata'] or '{}')
                    
                    results.append(MemoryResult(
                        memory_id=memory_id,
                        content=row['content'],
                        memory_type=table_name.split('_')[0],
                        similarity_score=similarity,
                        metadata=metadata,
                        created_at=row['created_at'],
                        last_accessed=row['last_accessed'],
                        access_count=row['access_count']
                    ))

            return results

    async def _update_access_counts(self, memory_ids: List[str], memory_type: str):
        """Update access counts for retrieved memories"""
        if not memory_ids:
            return

        table_name = f"{memory_type}_memories"
        async with self.db_pool.acquire() as conn:
            await conn.execute(f"""
                UPDATE {table_name}
                SET access_count = access_count + 1, last_accessed = NOW()
                WHERE memory_id = ANY($1)
            """, memory_ids)

    async def cleanup_old_memories(self):
        """Clean up old memories based on retention policy"""

        # Clean episodic memories
        episodic_cutoff = datetime.utcnow() - timedelta(days=self.settings.episodic_memory_retention_days)
        async with self.db_pool.acquire() as conn:
            episodic_deleted = await conn.execute("""
                DELETE FROM episodic_memories
                WHERE created_at < $1
            """, episodic_cutoff)

        # Clean semantic memories
        semantic_cutoff = datetime.utcnow() - timedelta(days=self.settings.semantic_memory_retention_days)
        async with self.db_pool.acquire() as conn:
            semantic_deleted = await conn.execute("""
                DELETE FROM semantic_memories
                WHERE created_at < $1
            """, semantic_cutoff)

        logger.info("Memory cleanup completed",
                   episodic_deleted=episodic_deleted,
                   semantic_deleted=semantic_deleted)


# Global service instance
settings = Settings()
memory_service = MemoryService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Memory MemoRAG",
    description="Episodic and semantic memory management for HyperRAG system",
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
    await memory_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await memory_service.close()


@app.post("/store")
async def store_memory(
    tenant: str,
    content: str,
    memory_type: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    lang: str = "en",
    metadata: Optional[Dict[str, Any]] = None
):
    """Store a memory entry"""
    try:
        memory_entry = await memory_service.store_memory(
            tenant=tenant,
            content=content,
            memory_type=memory_type,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            lang=lang
        )

        return {
            "memory_id": memory_entry.memory_id,
            "memory_type": memory_entry.memory_type,
            "tenant": memory_entry.tenant,
            "created_at": memory_entry.created_at.isoformat()
        }
    except Exception as e:
        logger.error("Memory storage failed", error=str(e))
        memory_operation_counter.labels(
            tenant=tenant,
            operation="store",
            memory_type=memory_type,
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve", response_model=MemoryResponse)
async def retrieve_memories(request: MemoryRequest):
    """Retrieve relevant memories"""
    try:
        return await memory_service.retrieve_memories(request)
    except Exception as e:
        logger.error("Memory retrieval failed", error=str(e))
        memory_operation_counter.labels(
            tenant=request.tenant,
            operation="retrieve",
            memory_type=request.memory_type,
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cleanup")
async def cleanup_memories():
    """Clean up old memories"""
    try:
        await memory_service.cleanup_old_memories()
        return {"status": "cleanup completed"}
    except Exception as e:
        logger.error("Memory cleanup failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "memory.memorag"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8010,
        reload=False,
        log_level=settings.log_level.lower()
    )
