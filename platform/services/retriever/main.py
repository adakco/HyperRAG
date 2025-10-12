"""
Retriever MCP Service
Hybrid search with RRF and re-ranking capabilities for Persian and English
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import asyncpg
import structlog
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
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
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, SearchRequest
import numpy as np
from sentence_transformers import SentenceTransformer
from cross_encoder import CrossEncoder

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
retrieval_counter = Counter(
    'hyperrag_retrieval_total',
    'Total number of retrieval operations',
    ['tenant', 'lang', 'search_mode', 'status']
)

retrieval_duration = Histogram(
    'hyperrag_retrieval_duration_seconds',
    'Time spent on retrieval operations',
    ['tenant', 'lang', 'search_mode']
)

rerank_duration = Histogram(
    'hyperrag_rerank_duration_seconds',
    'Time spent on re-ranking',
    ['tenant', 'lang']
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://hyperrag:password123@localhost:5432/hyperrag"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    service_name: str = "retriever"
    log_level: str = "INFO"
    
    # Model configurations
    persian_embedding_model: str = "HooshvareLab/bert-fa-base-uncased"
    english_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    persian_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    english_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    class Config:
        env_file = ".env"


class RetrievalRequest(BaseModel):
    """Request model for retrieval"""
    query: str = Field(..., min_length=1, max_length=1000)
    lang: str = Field(..., enum=["en", "fa"])
    tenant: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    project: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]+$")
    k_dense: int = Field(20, ge=1, le=100)
    k_sparse: int = Field(20, ge=1, le=100)
    k_final: int = Field(10, ge=1, le=50)
    rerank: bool = Field(True)
    filters: Optional[Dict] = Field(None)
    search_mode: str = Field("balanced", enum=["fast", "balanced", "thorough"])
    include_metadata: bool = Field(True)
    include_content: bool = Field(True)


class RetrievalResult(BaseModel):
    """Individual retrieval result"""
    chunk_id: str
    doc_id: str
    version: str
    chunk_index: int
    content: str
    score: float
    rerank_score: Optional[float] = None
    lang: str
    metadata: Dict


class RetrievalResponse(BaseModel):
    """Response model for retrieval"""
    results: List[RetrievalResult]
    metadata: Dict
    cost: Dict


class EmbeddingService:
    """Service for generating embeddings"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.persian_model = None
        self.english_model = None
        self.persian_rerank_model = None
        self.english_rerank_model = None
        
    async def initialize(self):
        """Initialize embedding models"""
        logger.info("Loading embedding models...")
        
        # Load Persian embedding model
        try:
            self.persian_model = SentenceTransformer(self.settings.persian_embedding_model)
            logger.info("Persian embedding model loaded", model=self.settings.persian_embedding_model)
        except Exception as e:
            logger.error("Failed to load Persian embedding model", error=str(e))
            raise
        
        # Load English embedding model
        try:
            self.english_model = SentenceTransformer(self.settings.english_embedding_model)
            logger.info("English embedding model loaded", model=self.settings.english_embedding_model)
        except Exception as e:
            logger.error("Failed to load English embedding model", error=str(e))
            raise
        
        # Load re-ranking models
        try:
            self.persian_rerank_model = CrossEncoder(self.settings.persian_rerank_model)
            self.english_rerank_model = CrossEncoder(self.settings.english_rerank_model)
            logger.info("Re-ranking models loaded")
        except Exception as e:
            logger.error("Failed to load re-ranking models", error=str(e))
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
    
    def rerank(self, query: str, documents: List[str], lang: str) -> List[float]:
        """Re-rank documents based on query"""
        if not documents:
            return []
        
        # Prepare pairs for cross-encoder
        pairs = [[query, doc] for doc in documents]
        
        # Get re-ranking model
        if lang == 'fa' and self.persian_rerank_model:
            model = self.persian_rerank_model
        else:
            model = self.english_rerank_model
        
        # Get scores
        scores = model.predict(pairs)
        return scores.tolist()


class RetrieverService:
    """Main retriever service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.qdrant_client: Optional[QdrantClient] = None
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
        
        # Qdrant client
        self.qdrant_client = QdrantClient(url=self.settings.qdrant_url)
        
        # Initialize embedding service
        await self.embedding_service.initialize()
        
        logger.info("Retriever service initialized successfully")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
    
    def _build_qdrant_filter(self, tenant: str, project: Optional[str], lang: str, filters: Optional[Dict]) -> Filter:
        """Build Qdrant filter for multi-tenant search"""
        conditions = [
            FieldCondition(key="tenant", match=MatchValue(value=tenant)),
            FieldCondition(key="lang", match=MatchValue(value=lang))
        ]
        
        if project:
            conditions.append(FieldCondition(key="project", match=MatchValue(value=project)))
        
        if filters:
            if "content_type" in filters:
                conditions.append(FieldCondition(key="content_type", match=MatchValue(value=filters["content_type"])))
            if "tags" in filters:
                # Handle tag filtering (assuming tags is a list)
                for tag in filters["tags"]:
                    conditions.append(FieldCondition(key="tags", match=MatchValue(value=tag)))
        
        return Filter(must=conditions)
    
    def _reciprocal_rank_fusion(self, dense_results: List, sparse_results: List, k: int = 60) -> List:
        """Apply Reciprocal Rank Fusion to combine dense and sparse results"""
        # Create score dictionaries
        dense_scores = {}
        sparse_scores = {}
        
        for i, result in enumerate(dense_results):
            chunk_id = result.payload.get('chunk_id')
            if chunk_id:
                dense_scores[chunk_id] = 1.0 / (k + i + 1)
        
        for i, result in enumerate(sparse_results):
            chunk_id = result.payload.get('chunk_id')
            if chunk_id:
                sparse_scores[chunk_id] = 1.0 / (k + i + 1)
        
        # Combine scores
        combined_scores = {}
        all_chunk_ids = set(dense_scores.keys()) | set(sparse_scores.keys())
        
        for chunk_id in all_chunk_ids:
            combined_scores[chunk_id] = dense_scores.get(chunk_id, 0) + sparse_scores.get(chunk_id, 0)
        
        # Sort by combined score
        sorted_chunks = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Create result list with combined scores
        results = []
        for chunk_id, score in sorted_chunks:
            # Find the original result
            for result in dense_results + sparse_results:
                if result.payload.get('chunk_id') == chunk_id:
                    result.score = score
                    results.append(result)
                    break
        
        return results
    
    async def retrieve(
        self,
        request: RetrievalRequest
    ) -> RetrievalResponse:
        """Perform hybrid retrieval with RRF and re-ranking"""
        
        with tracer.start_as_current_span("retrieve_documents") as span:
            span.set_attribute("query", request.query)
            span.set_attribute("lang", request.lang)
            span.set_attribute("tenant", request.tenant)
            span.set_attribute("search_mode", request.search_mode)
            
            start_time = time.time()
            
            # Generate query embedding
            query_embedding = self.embedding_service.get_embedding(request.query, request.lang)
            
            # Build filter
            qdrant_filter = self._build_qdrant_filter(
                request.tenant, request.project, request.lang, request.filters
            )
            
            # Configure search parameters based on mode
            if request.search_mode == "fast":
                ef_search = 100
                limit = min(request.k_dense, 50)
            elif request.search_mode == "thorough":
                ef_search = 400
                limit = request.k_dense
            else:  # balanced
                ef_search = 200
                limit = request.k_dense
            
            # Dense vector search
            dense_results = self.qdrant_client.search(
                collection_name="documents",
                query_vector=query_embedding.tolist(),
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                search_params={"ef": ef_search}
            )
            
            # Sparse vector search (simplified - using BM25-like scoring)
            # In a real implementation, you'd use a proper sparse vector search
            sparse_results = []  # Placeholder for sparse search results
            
            # Apply RRF
            rrf_results = self._reciprocal_rank_fusion(dense_results, sparse_results)
            
            # Take top k results
            top_results = rrf_results[:request.k_final * 2]  # Get more for re-ranking
            
            # Re-ranking
            rerank_scores = []
            if request.rerank and top_results:
                rerank_start = time.time()
                
                # Extract document texts
                doc_texts = [result.payload.get('content', '') for result in top_results]
                
                # Get re-ranking scores
                rerank_scores = self.embedding_service.rerank(
                    request.query, doc_texts, request.lang
                )
                
                # Apply re-ranking scores
                for i, result in enumerate(top_results):
                    if i < len(rerank_scores):
                        result.rerank_score = float(rerank_scores[i])
                        result.score = float(rerank_scores[i])  # Use re-rank score as final score
                
                # Sort by re-ranking score
                top_results = sorted(top_results, key=lambda x: x.rerank_score or 0, reverse=True)
                
                rerank_duration.labels(
                    tenant=request.tenant,
                    lang=request.lang
                ).observe(time.time() - rerank_start)
            
            # Take final k results
            final_results = top_results[:request.k_final]
            
            # Build response
            retrieval_results = []
            for result in final_results:
                payload = result.payload
                retrieval_result = RetrievalResult(
                    chunk_id=payload.get('chunk_id', ''),
                    doc_id=payload.get('doc_id', ''),
                    version=payload.get('version', ''),
                    chunk_index=payload.get('chunk_index', 0),
                    content=payload.get('content', '') if request.include_content else '',
                    score=float(result.score),
                    rerank_score=float(result.rerank_score) if hasattr(result, 'rerank_score') and result.rerank_score else None,
                    lang=payload.get('lang', request.lang),
                    metadata={
                        'title': payload.get('title', ''),
                        'content_type': payload.get('content_type', ''),
                        'created_at': payload.get('created_at', ''),
                        'token_count': payload.get('token_count', 0),
                        'tags': payload.get('tags', [])
                    } if request.include_metadata else {}
                )
                retrieval_results.append(retrieval_result)
            
            # Calculate costs (simplified)
            embedding_cost = 0.0001  # Approximate cost for embedding
            search_cost = 0.00005 * len(final_results)  # Approximate cost for search
            rerank_cost = 0.0002 * len(final_results) if request.rerank else 0  # Approximate cost for re-ranking
            
            total_cost = embedding_cost + search_cost + rerank_cost
            
            # Build metadata
            metadata = {
                'total_results': len(final_results),
                'search_time_ms': (time.time() - start_time) * 1000,
                'rerank_time_ms': (time.time() - start_time) * 1000 if request.rerank else 0,
                'dense_results': len(dense_results),
                'sparse_results': len(sparse_results),
                'rerank_applied': request.rerank,
                'search_mode': request.search_mode,
                'query_embedding_model': self.settings.persian_embedding_model if request.lang == 'fa' else self.settings.english_embedding_model,
                'rerank_model': self.settings.persian_rerank_model if request.lang == 'fa' else self.settings.english_rerank_model
            }
            
            # Update metrics
            retrieval_duration.labels(
                tenant=request.tenant,
                lang=request.lang,
                search_mode=request.search_mode
            ).observe(time.time() - start_time)
            
            retrieval_counter.labels(
                tenant=request.tenant,
                lang=request.lang,
                search_mode=request.search_mode,
                status="success"
            ).inc()
            
            logger.info("Retrieval completed successfully", 
                       query_length=len(request.query),
                       results_count=len(final_results),
                       tenant=request.tenant)
            
            return RetrievalResponse(
                results=retrieval_results,
                metadata=metadata,
                cost={
                    'embedding_cost': embedding_cost,
                    'search_cost': search_cost,
                    'rerank_cost': rerank_cost,
                    'total_cost': total_cost
                }
            )


# Global service instance
settings = Settings()
retriever_service = RetrieverService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Retriever MCP",
    description="Hybrid search with RRF and re-ranking for Persian and English",
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
    await retriever_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await retriever_service.close()


@app.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_documents(request: RetrievalRequest):
    """Perform document retrieval"""
    try:
        return await retriever_service.retrieve(request)
    except Exception as e:
        logger.error("Retrieval failed", error=str(e), query=request.query)
        retrieval_counter.labels(
            tenant=request.tenant,
            lang=request.lang,
            search_mode=request.search_mode,
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "retriever"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level=settings.log_level.lower()
    )
