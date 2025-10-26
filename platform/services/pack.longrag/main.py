"""
Pack LongRAG Service
Long context management with intelligent packing and summarization
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
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from fastapi.responses import Response
import tiktoken
from transformers import pipeline

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
packing_counter = Counter(
    'hyperrag_packing_total',
    'Total number of packing operations',
    ['tenant', 'lang', 'status'],
    registry=registry
)

packing_duration = Histogram(
    'hyperrag_packing_duration_seconds',
    'Time spent on packing operations',
    ['tenant', 'lang'],
    registry=registry
)

pack_efficiency = Histogram(
    'hyperrag_pack_efficiency_ratio',
    'Pack efficiency ratio (used tokens / total tokens)',
    ['tenant', 'lang'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    service_name: str = "pack.longrag"
    log_level: str = "INFO"
    
    # Packing parameters
    max_pack_size: int = 4000  # tokens
    min_pack_size: int = 1000  # tokens
    overlap_size: int = 200    # tokens
    summary_ratio: float = 0.3  # 30% of original size
    
    # Summarization models
    english_summarizer: str = "facebook/bart-large-cnn"
    persian_summarizer: str = "m3hrdadfi/bert2bert-fa-wiki-summary"
    
    class Config:
        env_file = ".env"


class PackRequest(BaseModel):
    """Request model for packing"""
    query: str
    contexts: List[str]
    lang: str = Field(..., enum=["en", "fa"])
    tenant: str
    max_tokens: int = 4000
    include_summaries: bool = True
    priority_chunks: Optional[List[int]] = None


class PackResult(BaseModel):
    """Individual pack result"""
    chunk_index: int
    content: str
    is_summary: bool
    original_length: int
    packed_length: int
    relevance_score: float


class PackResponse(BaseModel):
    """Response model for packing"""
    query: str
    lang: str
    tenant: str
    packs: List[PackResult]
    total_tokens: int
    efficiency_ratio: float
    processing_time_ms: int


class TextSummarizer:
    """Text summarization utilities"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.english_summarizer = None
        self.persian_summarizer = None
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    async def initialize(self):
        """Initialize summarization models"""
        logger.info("Loading summarization models...")
        
        try:
            # Load English summarizer
            self.english_summarizer = pipeline(
                "summarization",
                model=self.settings.english_summarizer,
                device=-1  # CPU
            )
            logger.info("English summarizer loaded", model=self.settings.english_summarizer)
        except Exception as e:
            logger.error("Failed to load English summarizer", error=str(e))
            # Fallback to simple truncation
            self.english_summarizer = None
        
        try:
            # Load Persian summarizer
            self.persian_summarizer = pipeline(
                "summarization",
                model=self.settings.persian_summarizer,
                device=-1  # CPU
            )
            logger.info("Persian summarizer loaded", model=self.settings.persian_summarizer)
        except Exception as e:
            logger.error("Failed to load Persian summarizer", error=str(e))
            # Fallback to simple truncation
            self.persian_summarizer = None
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def summarize_text(self, text: str, lang: str, max_length: int = 100) -> str:
        """Summarize text based on language"""
        if lang == 'fa' and self.persian_summarizer:
            try:
                result = self.persian_summarizer(text, max_length=max_length, min_length=50, do_sample=False)
                return result[0]['summary_text']
            except Exception as e:
                logger.warning("Persian summarization failed, using truncation", error=str(e))
                return self._truncate_text(text, max_length)
        elif lang == 'en' and self.english_summarizer:
            try:
                result = self.english_summarizer(text, max_length=max_length, min_length=50, do_sample=False)
                return result[0]['summary_text']
            except Exception as e:
                logger.warning("English summarization failed, using truncation", error=str(e))
                return self._truncate_text(text, max_length)
        else:
            return self._truncate_text(text, max_length)
    
    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Simple text truncation as fallback"""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)


class ContextPacker:
    """Context packing utilities"""
    
    def __init__(self, settings: Settings, summarizer: TextSummarizer):
        self.settings = settings
        self.summarizer = summarizer
    
    def calculate_relevance_score(self, query: str, context: str, lang: str) -> float:
        """Calculate relevance score between query and context"""
        # Simple relevance calculation based on word overlap
        query_words = set(query.lower().split())
        context_words = set(context.lower().split())
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words.intersection(context_words))
        return overlap / len(query_words)
    
    def pack_contexts(
        self,
        query: str,
        contexts: List[str],
        lang: str,
        max_tokens: int,
        include_summaries: bool = True,
        priority_chunks: Optional[List[int]] = None
    ) -> List[PackResult]:
        """Pack contexts into optimal packs"""
        
        # Calculate relevance scores
        context_scores = []
        for i, context in enumerate(contexts):
            score = self.calculate_relevance_score(query, context, lang)
            context_scores.append((i, context, score))
        
        # Sort by relevance (and priority if specified)
        if priority_chunks:
            # Boost priority chunks
            for i, (idx, context, score) in enumerate(context_scores):
                if idx in priority_chunks:
                    context_scores[i] = (idx, context, score * 1.5)
        
        context_scores.sort(key=lambda x: x[2], reverse=True)
        
        # Pack contexts
        packs = []
        current_pack_tokens = 0
        current_pack_content = []
        current_pack_indices = []
        
        for idx, context, score in context_scores:
            context_tokens = self.summarizer.count_tokens(context)
            
            # Check if adding this context would exceed max tokens
            if current_pack_tokens + context_tokens > max_tokens:
                # Finalize current pack
                if current_pack_content:
                    pack_content = " ".join(current_pack_content)
                    packs.append(PackResult(
                        chunk_index=current_pack_indices[0],  # Use first chunk index
                        content=pack_content,
                        is_summary=False,
                        original_length=sum(self.summarizer.count_tokens(ctx) for ctx in current_pack_content),
                        packed_length=self.summarizer.count_tokens(pack_content),
                        relevance_score=score
                    ))
                
                # Start new pack
                current_pack_content = [context]
                current_pack_indices = [idx]
                current_pack_tokens = context_tokens
            else:
                # Add to current pack
                current_pack_content.append(context)
                current_pack_indices.append(idx)
                current_pack_tokens += context_tokens
        
        # Add final pack
        if current_pack_content:
            pack_content = " ".join(current_pack_content)
            packs.append(PackResult(
                chunk_index=current_pack_indices[0],
                content=pack_content,
                is_summary=False,
                original_length=sum(self.summarizer.count_tokens(ctx) for ctx in current_pack_content),
                packed_length=self.summarizer.count_tokens(pack_content),
                relevance_score=score
            ))
        
        # Create summaries if requested
        if include_summaries and len(packs) > 1:
            summary_packs = []
            for pack in packs:
                if pack.packed_length > self.settings.min_pack_size:
                    summary = self.summarizer.summarize_text(
                        pack.content,
                        lang,
                        max_length=int(pack.packed_length * self.settings.summary_ratio)
                    )
                    summary_packs.append(PackResult(
                        chunk_index=pack.chunk_index,
                        content=summary,
                        is_summary=True,
                        original_length=pack.original_length,
                        packed_length=self.summarizer.count_tokens(summary),
                        relevance_score=pack.relevance_score
                    ))
            
            # Combine original packs with summaries
            packs = packs + summary_packs
        
        return packs


class PackLongRAGService:
    """Main pack longrag service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.summarizer = TextSummarizer(settings)
        self.packer = None
        
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
        
        # Initialize summarizer
        await self.summarizer.initialize()
        
        # Initialize packer
        self.packer = ContextPacker(self.settings, self.summarizer)
        
        logger.info("Pack LongRAG service initialized successfully")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
    
    async def pack_contexts(
        self,
        request: PackRequest
    ) -> PackResponse:
        """Pack contexts for long RAG"""
        
        with tracer.start_as_current_span("pack_contexts") as span:
            span.set_attribute("query", request.query)
            span.set_attribute("lang", request.lang)
            span.set_attribute("tenant", request.tenant)
            span.set_attribute("context_count", len(request.contexts))
            
            start_time = datetime.utcnow()
            
            # Pack contexts
            packs = self.packer.pack_contexts(
                query=request.query,
                contexts=request.contexts,
                lang=request.lang,
                max_tokens=request.max_tokens,
                include_summaries=request.include_summaries,
                priority_chunks=request.priority_chunks
            )
            
            # Calculate efficiency
            total_original_tokens = sum(pack.original_length for pack in packs)
            total_packed_tokens = sum(pack.packed_length for pack in packs)
            efficiency_ratio = total_packed_tokens / total_original_tokens if total_original_tokens > 0 else 0
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update metrics
            packing_counter.labels(
                tenant=request.tenant,
                lang=request.lang,
                status="success"
            ).inc()
            
            packing_duration.labels(
                tenant=request.tenant,
                lang=request.lang
            ).observe(processing_time / 1000)
            
            pack_efficiency.labels(
                tenant=request.tenant,
                lang=request.lang
            ).observe(efficiency_ratio)
            
            logger.info("Context packing completed successfully",
                       query_length=len(request.query),
                       context_count=len(request.contexts),
                       pack_count=len(packs),
                       efficiency_ratio=efficiency_ratio)
            
            return PackResponse(
                query=request.query,
                lang=request.lang,
                tenant=request.tenant,
                packs=packs,
                total_tokens=total_packed_tokens,
                efficiency_ratio=efficiency_ratio,
                processing_time_ms=int(processing_time)
            )


# Global service instance
settings = Settings()
pack_service = PackLongRAGService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Pack LongRAG",
    description="Long context management with intelligent packing and summarization",
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
    await pack_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await pack_service.close()


@app.post("/pack", response_model=PackResponse)
async def pack_contexts(request: PackRequest):
    """Pack contexts for long RAG"""
    try:
        return await pack_service.pack_contexts(request)
    except Exception as e:
        logger.error("Context packing failed", error=str(e), query=request.query)
        packing_counter.labels(
            tenant=request.tenant,
            lang=request.lang,
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "pack.longrag"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8009,
        reload=False,
        log_level=settings.log_level.lower()
    )
