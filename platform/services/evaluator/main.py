"""
Evaluator MCP Service
RAGAS-based quality assessment for Persian and English RAG systems
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_similarity,
    answer_correctness
)
from sentence_transformers import SentenceTransformer
import numpy as np

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
evaluation_counter = Counter(
    'hyperrag_evaluation_total',
    'Total number of evaluation operations',
    ['tenant', 'lang', 'metric', 'status'],
    registry=registry
)

evaluation_duration = Histogram(
    'hyperrag_evaluation_duration_seconds',
    'Time spent on evaluation operations',
    ['tenant', 'lang', 'metric'],
    registry=registry
)

evaluation_score = Histogram(
    'hyperrag_evaluation_score',
    'Evaluation scores by metric',
    ['tenant', 'lang', 'metric'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    service_name: str = "evaluator"
    log_level: str = "INFO"
    
    # LLM configurations
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: str = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_base_url: str = Field(default_factory=lambda: os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    
    # Model configurations
    persian_embedding_model: str = "HooshvareLab/bert-fa-base-uncased"
    english_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Evaluation thresholds
    faithfulness_threshold: float = 0.8
    answer_relevancy_threshold: float = 0.8
    context_precision_threshold: float = 0.8
    context_recall_threshold: float = 0.8
    
    class Config:
        env_file = ".env"


class EvaluationRequest(BaseModel):
    """Request model for evaluation"""
    session_id: Optional[str] = None
    doc_id: Optional[str] = None
    version: Optional[str] = None
    lang: str = Field(..., enum=["en", "fa"])
    tenant: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    query: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None
    metrics: List[str] = Field(default=["faithfulness", "answer_relevancy", "context_precision", "context_recall"])


class EvaluationResult(BaseModel):
    """Individual evaluation result"""
    metric_name: str
    score: float
    threshold: float
    passed: bool
    explanation: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Response model for evaluation"""
    session_id: Optional[str] = None
    doc_id: Optional[str] = None
    version: Optional[str] = None
    lang: str
    tenant: str
    results: List[EvaluationResult]
    overall_score: float
    passed: bool
    processing_time_ms: int


class LanguageSpecificEvaluator:
    """Language-specific evaluation utilities"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.persian_model = None
        self.english_model = None
        
    async def initialize(self):
        """Initialize embedding models for evaluation"""
        logger.info("Loading evaluation models...")
        
        # Load Persian embedding model
        try:
            self.persian_model = SentenceTransformer(self.settings.persian_embedding_model)
            logger.info("Persian evaluation model loaded", model=self.settings.persian_embedding_model)
        except Exception as e:
            logger.error("Failed to load Persian evaluation model", error=str(e))
            raise
        
        # Load English embedding model
        try:
            self.english_model = SentenceTransformer(self.settings.english_embedding_model)
            logger.info("English evaluation model loaded", model=self.settings.english_embedding_model)
        except Exception as e:
            logger.error("Failed to load English evaluation model", error=str(e))
            raise
    
    def get_embedding(self, text: str, lang: str) -> np.ndarray:
        """Get embedding for evaluation"""
        if lang == 'fa' and self.persian_model:
            return self.persian_model.encode(text)
        elif lang == 'en' and self.english_model:
            return self.english_model.encode(text)
        else:
            # Fallback to English model
            return self.english_model.encode(text)
    
    def calculate_similarity(self, text1: str, text2: str, lang: str) -> float:
        """Calculate semantic similarity between two texts"""
        emb1 = self.get_embedding(text1, lang)
        emb2 = self.get_embedding(text2, lang)
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)
    
    def evaluate_faithfulness(self, answer: str, contexts: List[str], lang: str) -> float:
        """Evaluate faithfulness of answer to contexts"""
        if not contexts:
            return 0.0
        
        # Simple faithfulness check: answer should be supported by contexts
        context_text = " ".join(contexts)
        similarity = self.calculate_similarity(answer, context_text, lang)
        
        # Additional check: key phrases in answer should appear in contexts
        answer_words = set(answer.lower().split())
        context_words = set(context_text.lower().split())
        
        overlap_ratio = len(answer_words.intersection(context_words)) / len(answer_words) if answer_words else 0
        
        # Combine similarity and overlap
        faithfulness_score = (similarity * 0.7) + (overlap_ratio * 0.3)
        return min(faithfulness_score, 1.0)
    
    def evaluate_answer_relevancy(self, query: str, answer: str, lang: str) -> float:
        """Evaluate relevancy of answer to query"""
        return self.calculate_similarity(query, answer, lang)
    
    def evaluate_context_precision(self, query: str, contexts: List[str], lang: str) -> float:
        """Evaluate precision of retrieved contexts"""
        if not contexts:
            return 0.0
        
        relevancy_scores = []
        for context in contexts:
            score = self.calculate_similarity(query, context, lang)
            relevancy_scores.append(score)
        
        # Precision: average relevancy of retrieved contexts
        return sum(relevancy_scores) / len(relevancy_scores)
    
    def evaluate_context_recall(self, query: str, contexts: List[str], ground_truth: Optional[str], lang: str) -> float:
        """Evaluate recall of retrieved contexts"""
        if not contexts or not ground_truth:
            return 0.0
        
        # Calculate how well contexts cover the ground truth
        ground_truth_embedding = self.get_embedding(ground_truth, lang)
        context_embeddings = [self.get_embedding(ctx, lang) for ctx in contexts]
        
        # Average similarity between ground truth and contexts
        similarities = []
        for ctx_emb in context_embeddings:
            similarity = np.dot(ground_truth_embedding, ctx_emb) / (np.linalg.norm(ground_truth_embedding) * np.linalg.norm(ctx_emb))
            similarities.append(similarity)
        
        return sum(similarities) / len(similarities)


class EvaluatorService:
    """Main evaluator service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.evaluator = LanguageSpecificEvaluator(settings)
        
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
        
        # Initialize evaluator
        await self.evaluator.initialize()
        
        logger.info("Evaluator service initialized successfully")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
    
    async def evaluate_rag_response(
        self,
        request: EvaluationRequest
    ) -> EvaluationResponse:
        """Evaluate RAG response quality"""
        
        with tracer.start_as_current_span("evaluate_rag_response") as span:
            span.set_attribute("lang", request.lang)
            span.set_attribute("tenant", request.tenant)
            span.set_attribute("metrics", ",".join(request.metrics))
            
            start_time = datetime.utcnow()
            
            results = []
            
            # Evaluate each requested metric
            for metric in request.metrics:
                try:
                    if metric == "faithfulness":
                        score = self.evaluator.evaluate_faithfulness(
                            request.answer, request.contexts, request.lang
                        )
                        threshold = self.settings.faithfulness_threshold
                        explanation = "Measures how well the answer is supported by the retrieved contexts"
                    
                    elif metric == "answer_relevancy":
                        score = self.evaluator.evaluate_answer_relevancy(
                            request.query, request.answer, request.lang
                        )
                        threshold = self.settings.answer_relevancy_threshold
                        explanation = "Measures how relevant the answer is to the query"
                    
                    elif metric == "context_precision":
                        score = self.evaluator.evaluate_context_precision(
                            request.query, request.contexts, request.lang
                        )
                        threshold = self.settings.context_precision_threshold
                        explanation = "Measures the precision of retrieved contexts"
                    
                    elif metric == "context_recall":
                        score = self.evaluator.evaluate_context_recall(
                            request.query, request.contexts, request.ground_truth, request.lang
                        )
                        threshold = self.settings.context_recall_threshold
                        explanation = "Measures how well the contexts cover the ground truth"
                    
                    else:
                        logger.warning("Unknown metric requested", metric=metric)
                        continue
                    
                    result = EvaluationResult(
                        metric_name=metric,
                        score=score,
                        threshold=threshold,
                        passed=score >= threshold,
                        explanation=explanation
                    )
                    results.append(result)
                    
                    # Update metrics
                    evaluation_score.labels(
                        tenant=request.tenant,
                        lang=request.lang,
                        metric=metric
                    ).observe(score)
                    
                except Exception as e:
                    logger.error("Error evaluating metric", metric=metric, error=str(e))
                    evaluation_counter.labels(
                        tenant=request.tenant,
                        lang=request.lang,
                        metric=metric,
                        status="error"
                    ).inc()
                    continue
            
            # Calculate overall score
            if results:
                overall_score = sum(r.score for r in results) / len(results)
                passed = all(r.passed for r in results)
            else:
                overall_score = 0.0
                passed = False
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store evaluation results in database
            async with self.db_pool.acquire() as conn:
                for result in results:
                    await conn.execute("""
                        INSERT INTO evaluation_results 
                        (session_id, doc_id, version, lang, metric_name, metric_value, threshold, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, request.session_id, request.doc_id, request.version, request.lang,
                        result.metric_name, result.score, result.threshold,
                        json.dumps({"explanation": result.explanation}))
            
            # Create CloudEvent dict (avoiding CloudEvent constructor issues)
            event = {
                "specversion": "1.0",
                "id": str(uuid.uuid4()),
                "source": "service/evaluator",
                "type": "evaluation.completed.v1",
                "time": datetime.utcnow().isoformat(),
                "datacontenttype": "application/json",
                "data": {
                    "session_id": request.session_id,
                    "doc_id": request.doc_id,
                    "version": request.version,
                    "lang": request.lang,
                    "tenant": request.tenant,
                    "overall_score": overall_score,
                    "passed": passed,
                    "metrics_evaluated": len(results),
                    "processing_time_ms": int(processing_time)
                }
            }
            
            # Publish event to NATS
            event_data = json.dumps(event)
            
            await self.nats_client.publish("evaluation.completed.v1", str(event_data).encode())
            
            # Update metrics
            for result in results:
                evaluation_counter.labels(
                    tenant=request.tenant,
                    lang=request.lang,
                    metric=result.metric_name,
                    status="success"
                ).inc()
            
            evaluation_duration.labels(
                tenant=request.tenant,
                lang=request.lang,
                metric="overall"
            ).observe(processing_time / 1000)
            
            logger.info("Evaluation completed successfully", 
                       lang=request.lang, overall_score=overall_score, passed=passed)
            
            return EvaluationResponse(
                session_id=request.session_id,
                doc_id=request.doc_id,
                version=request.version,
                lang=request.lang,
                tenant=request.tenant,
                results=results,
                overall_score=overall_score,
                passed=passed,
                processing_time_ms=int(processing_time)
            )


# Global service instance
settings = Settings()
evaluator_service = EvaluatorService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Evaluator MCP",
    description="RAGAS-based quality assessment for Persian and English RAG systems",
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
    await evaluator_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await evaluator_service.close()


@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_rag_response(request: EvaluationRequest):
    """Evaluate RAG response quality"""
    try:
        return await evaluator_service.evaluate_rag_response(request)
    except Exception as e:
        logger.error("Evaluation failed", error=str(e), query=request.query)
        evaluation_counter.labels(
            tenant=request.tenant,
            lang=request.lang,
            metric="overall",
            status="error"
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "evaluator"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/evaluation/{session_id}/results")
async def get_evaluation_results(session_id: str):
    """Get evaluation results for a session"""
    async with evaluator_service.db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT metric_name, metric_value, threshold, passed, metadata, created_at
            FROM evaluation_results
            WHERE session_id = $1
            ORDER BY created_at DESC
        """, session_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="No evaluation results found")
        
        return {
            "session_id": session_id,
            "results": [
                {
                    "metric_name": r["metric_name"],
                    "score": float(r["metric_value"]),
                    "threshold": float(r["threshold"]),
                    "passed": r["passed"],
                    "metadata": r["metadata"],
                    "created_at": r["created_at"].isoformat()
                }
                for r in results
            ]
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=False,
        log_level=settings.log_level.lower()
    )
