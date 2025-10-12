"""
Reranker Service
Cross-encoder based re-ranking for Persian and English documents
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
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
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from cross_encoder import CrossEncoder
import numpy as np

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
reranking_counter = Counter(
    'hyperrag_reranking_total',
    'Total number of reranking operations',
    ['tenant', 'lang', 'model', 'status']
)

reranking_duration = Histogram(
    'hyperrag_reranking_duration_seconds',
    'Time spent on reranking operations',
    ['tenant', 'lang', 'model']
)

reranking_quality = Histogram(
    'hyperrag_reranking_quality_score',
    'Reranking quality scores',
    ['tenant', 'lang', 'model']
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://hyperrag:password123@localhost:5432/hyperrag"
    redis_url: str = "redis://localhost:6379"
    nats_url: str = "nats://localhost:4222"
    service_name: str = "reranker"
    log_level: str = "INFO"
    
    # Re-ranking models
    persian_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    english_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    batch_size: int = 32
    max_sequence_length: int = 512
    
    class Config:
        env_file = ".env"


class RerankRequest(BaseModel):
    """Request model for reranking"""
    query: str
    documents: List[str]
    lang: str = Field(..., enum=["en", "fa"])
    tenant: str
    top_k: Optional[int] = None
    return_scores: bool = True


class RerankResult(BaseModel):
    """Individual rerank result"""
    document: str
    score: float
    rank: int
    original_rank: int


class RerankResponse(BaseModel):
    """Response model for reranking"""
    query: str
    lang: str
    tenant: str
    results: List[RerankResult]
    total_processed: int
    processing_time_ms: int
    model_used: str


class RerankerService:
    """Main reranker service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.persian_model = None
        self.english_model = None
        
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
        
        # Initialize re-ranking models
        await self._initialize_models()
        
        logger.info("Reranker service initialized successfully")
    
    async def _initialize_models(self):
        """Initialize re-ranking models"""
        logger.info("Loading re-ranking models...")
        
        try:
            # Load Persian re-ranking model
            self.persian_model = CrossEncoder(self.settings.persian_rerank_model)
            logger.info("Persian re-ranking model loaded", model=self.settings.persian_rerank_model)
        except Exception as e:
            logger.error("Failed to load Persian re-ranking model", error=str(e))
            raise
        
        try:
            # Load English re-ranking model
            self.english_model = CrossEncoder(self.settings.english_rerank_model)
            logger.info("English re-ranking model loaded", model=self.settings.english_rerank_model)
        except Exception as e:
            logger.error("Failed to load English re-ranking model", error=str(e))
            raise
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
    
    async def rerank_documents(
        self,
        request: RerankRequest
    ) -> RerankResponse:
        """Rerank documents based on query relevance"""
        
        with tracer.start_as_current_span("rerank_documents") as span:
            span.set_attribute("query", request.query)
            span.set_attribute("lang", request.lang)
            span.set_attribute("tenant", request.tenant)
            span.set_attribute("document_count", len(request.documents))
            
            start_time = datetime.utcnow()
            
            # Select appropriate model
            if request.lang == 'fa' and self.persian_model:
                model = self.persian_model
                model_name = self.settings.persian_rerank_model
            else:
                model = self.english_model
                model_name = self.settings.english_rerank_model
            
            # Prepare pairs for cross-encoder
            pairs = [[request.query, doc] for doc in request.documents]
            
            # Get re-ranking scores
            scores = model.predict(pairs, batch_size=self.settings.batch_size)
            
            # Create results with scores
            results = []
            for i, (doc, score) in enumerate(zip(request.documents, scores)):
                results.append(RerankResult(
                    document=doc,
                    score=float(score),
                    rank=0,  # Will be set after sorting
                    original_rank=i
                ))
            
            # Sort by score (descending)
            results.sort(key=lambda x: x.score, reverse=True)
            
            # Set final ranks
            for i, result in enumerate(results):
                result.rank = i + 1
            
            # Apply top_k filter if specified
            if request.top_k:
                results = results[:request.top_k]
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update metrics
            reranking_counter.labels(
                tenant=request.tenant,
                lang=request.lang,
                model=model_name,
                status="success"
            ).inc()
            
            reranking_duration.labels(
                tenant=request.tenant,
                lang=request.lang,
                model=model_name
            ).observe(processing_time / 1000)
            
            if results:
                avg_quality = sum(r.score for r in results) / len(results)
                reranking_quality.labels(
                    tenant=request.tenant,
                    lang=request.lang,
                    model=model_name
                ).observe(avg_quality)
            
            logger.info("Document reranking completed successfully",
                       query_length=len(request.query),
                       document_count=len(request.documents),
                       results_count=len(results),
                       processing_time_ms=processing_time)
            
            return RerankResponse(
                query=request.query,
                lang=request.lang,
                tenant=request.tenant,
                results=results,
                total_processed=len(request.documents),
                processing_time_ms=int(processing_time),
                model_used=model_name
            )


# Global service instance
settings = Settings()
reranker_service = RerankerService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Reranker",
    description="Cross-encoder based re-ranking for Persian and English documents",
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
    await reranker_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await reranker_service.close()


@app.post("/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    """Rerank documents based on query relevance"""
    try:
        return await reranker_service.rerank_documents(request)
    except Exception as e:
        logger.error("Document reranking failed", error=str(e), query=request.query)
        reranking_counter.labels(
            tenant=request.tenant,
            lang=request.lang,
            model="unknown",
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "reranker"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8011,
        reload=True,
        log_level=settings.log_level.lower()
    )
