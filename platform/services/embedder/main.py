"""
Document Embedder Service
Generates embeddings for document chunks using Persian and English models
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import asyncpg
import boto3
import structlog
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
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
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
embedding_counter = Counter(
    'hyperrag_embedding_total',
    'Total number of embedding operations',
    ['tenant', 'lang', 'model', 'status'],
    registry=registry
)

embedding_duration = Histogram(
    'hyperrag_embedding_duration_seconds',
    'Time spent generating embeddings',
    ['tenant', 'lang', 'model'],
    registry=registry
)

embeddings_created = Histogram(
    'hyperrag_embeddings_created_total',
    'Number of embeddings created per document',
    ['tenant', 'lang', 'model'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    qdrant_url: str = "http://192.168.2.23:6333"
    minio_endpoint: str = "http://192.168.2.23:9190"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "clean"
    service_name: str = "embedder"
    log_level: str = "INFO"

    # Model configurations - Using local models
    persian_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    english_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = 32
    max_sequence_length: int = 512
    
    class Config:
        env_file = ".env"


class EmbeddingResult(BaseModel):
    """Result of document embedding"""
    doc_id: str
    version: str
    lang: str
    embeddings_count: int
    vector_dimension: int
    processing_time_ms: int


class EmbeddingService:
    """Service for generating embeddings"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.persian_model = None
        self.english_model = None
        self.qdrant_client = None
        
    async def initialize(self):
        """Initialize embedding models and Qdrant client"""
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
        
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(url=self.settings.qdrant_url, check_compatibility=False)
        
        # Create collection if it doesn't exist
        try:
            self.qdrant_client.get_collection("documents")
        except Exception as e:
            # Get vector dimension from English model (assuming both models have same dimension)
            vector_dim = self.english_model.get_sentence_embedding_dimension()
            
            self.qdrant_client.create_collection(
                collection_name="documents",
                vectors_config=VectorParams(
                    size=vector_dim,
                    distance=Distance.COSINE
                )
            )
            logger.info("Created Qdrant collection", collection="documents", dimension=vector_dim)
    
    def get_embedding(self, text: str, lang: str) -> np.ndarray:
        """Get embedding for text"""
        if lang == 'fa' and self.persian_model:
            return self.persian_model.encode(text)
        elif lang == 'en' and self.english_model:
            return self.english_model.encode(text)
        else:
            # Fallback to English model
            return self.english_model.encode(text)
    
    def get_embeddings_batch(self, texts: List[str], lang: str) -> np.ndarray:
        """Get embeddings for a batch of texts"""
        if lang == 'fa' and self.persian_model:
            return self.persian_model.encode(texts, batch_size=self.settings.batch_size)
        elif lang == 'en' and self.english_model:
            return self.english_model.encode(texts, batch_size=self.settings.batch_size)
        else:
            # Fallback to English model
            return self.english_model.encode(texts, batch_size=self.settings.batch_size)


class EmbedderService:
    """Main embedder service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.s3_client = None
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
        
        # S3/MinIO client
        endpoint_url = self.settings.minio_endpoint
        if not endpoint_url.startswith('http'):
            endpoint_url = f"http://{endpoint_url}"

        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name='us-east-1',
            use_ssl=False
        )
        
        # Ensure bucket exists
        try:
            self.s3_client.head_bucket(Bucket=self.settings.minio_bucket)
        except Exception as e:
            logger.warning(f"Could not access bucket {self.settings.minio_bucket}: {e}")
            try:
                self.s3_client.create_bucket(Bucket=self.settings.minio_bucket)
                logger.info(f"Created bucket {self.settings.minio_bucket}")
            except Exception as create_error:
                logger.warning(f"Could not create bucket {self.settings.minio_bucket}: {create_error}")
                # Continue without bucket creation
        
        # Initialize embedding service
        await self.embedding_service.initialize()
            
        logger.info("Embedder service initialized successfully")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
    
    async def embed_document(
        self,
        doc_id: str,
        version: str,
        uri_processed: str,
        lang: str,
        tenant: str,
        project: Optional[str] = None
    ) -> EmbeddingResult:
        """Generate embeddings for document chunks"""
        
        with tracer.start_as_current_span("embed_document") as span:
            span.set_attribute("doc_id", doc_id)
            span.set_attribute("version", version)
            span.set_attribute("lang", lang)
            span.set_attribute("tenant", tenant)
            
            start_time = datetime.utcnow()
            
            # Download chunked document from S3
            try:
                # Parse URI properly
                if not uri_processed.startswith('s3://'):
                    raise ValueError(f"Invalid URI format: {uri_processed}")
                
                uri_parts = uri_processed[5:].split('/', 1)  # Remove 's3://' and split
                if len(uri_parts) != 2:
                    raise ValueError(f"Invalid URI format: {uri_processed}")
                
                bucket_name = uri_parts[0]
                key = uri_parts[1]
                
                logger.info(f"Downloading chunked document from S3", bucket=bucket_name, key=key)
                
                # Download file from S3
                response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
                content = response['Body'].read().decode('utf-8')
                logger.info(f"Downloaded content length: {len(content)}")
                
                # Validate content
                if not content.strip():
                    raise ValueError("Downloaded content is empty")
                
                # Parse JSON content
                try:
                    chunked_data = json.loads(content)
                    logger.info(f"Parsed chunked data keys: {list(chunked_data.keys())}")
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON parsing failed", error=str(json_err), content_preview=content[:200])
                    raise ValueError(f"Invalid JSON content: {str(json_err)}")
                
                # Validate chunked data structure
                if 'chunks' not in chunked_data:
                    raise ValueError("Missing 'chunks' key in chunked data")
                
                chunks = chunked_data['chunks']
                if not isinstance(chunks, list) or len(chunks) == 0:
                    raise ValueError("Chunks must be a non-empty list")
                
                logger.info(f"Found {len(chunks)} chunks to embed")
                
            except Exception as e:
                logger.error(f"Failed to download or parse chunked document", 
                           error=str(e), bucket=bucket_name, key=key, uri=uri_processed)
                raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")
            
            # Extract chunk texts
            chunk_texts = [chunk['content'] for chunk in chunks]
            
            # Generate embeddings in batches
            embeddings = self.embedding_service.get_embeddings_batch(chunk_texts, lang)
            
            # Prepare points for Qdrant
            points = []
            point_ids = []  # Store point IDs for database update
            
            for i, chunk in enumerate(chunks):
                # Generate unique point ID
                point_id = str(uuid.uuid4())
                point_ids.append(point_id)
                
                # Validate chunk structure
                if 'content' not in chunk:
                    raise ValueError(f"Chunk {i} missing 'content' field")
                if 'chunk_index' not in chunk:
                    raise ValueError(f"Chunk {i} missing 'chunk_index' field")
                
                point = PointStruct(
                    id=point_id,
                    vector=embeddings[i].tolist(),
                    payload={
                        'chunk_id': f"{doc_id}_{version}_{chunk['chunk_index']}",
                        'doc_id': doc_id,
                        'version': int(version),
                        'chunk_index': chunk['chunk_index'],
                        'content': chunk['content'],
                        'lang': lang,
                        'tenant': tenant,
                        'project': project or 'default',  # Add project field
                        'token_count': chunk.get('token_count', 0),
                        'char_count': chunk.get('char_count', len(chunk['content'])),
                        'created_at': datetime.utcnow().isoformat()
                    }
                )
                points.append(point)
            
            logger.info(f"Prepared {len(points)} points for Qdrant")
            
            # Upload points to Qdrant
            try:
                self.embedding_service.qdrant_client.upsert(
                    collection_name="documents",
                    points=points
                )
                logger.info(f"Successfully uploaded {len(points)} points to Qdrant")
            except Exception as e:
                logger.error(f"Failed to upload points to Qdrant", error=str(e))
                raise HTTPException(status_code=500, detail=f"Failed to upload to Qdrant: {str(e)}")
            
            # Update database with embedding information
            try:
                async with self.db_pool.acquire() as conn:
                    # Update document chunks with embedding IDs
                    for i, (chunk, point_id) in enumerate(zip(chunks, point_ids)):
                        await conn.execute("""
                            UPDATE document_chunks 
                            SET embedding = $1
                            WHERE doc_id = $2 AND version = $3 AND chunk_index = $4
                        """, point_id, doc_id, int(version), chunk['chunk_index'])
                    
                    # Update document version with embedding count
                    await conn.execute("""
                        UPDATE document_versions 
                        SET processing_status = 'embedded'
                        WHERE doc_id = $1 AND version = $2
                    """, doc_id, int(version))
                    
                logger.info(f"Updated database with embedding information")
            except Exception as e:
                logger.error(f"Failed to update database", error=str(e))
                raise HTTPException(status_code=500, detail=f"Failed to update database: {str(e)}")
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Create CloudEvent
            event = {
                "specversion": "1.0",
                "id": str(uuid.uuid4()),
                "source": "service/embedder",
                "type": "doc.embedded.v1",
                "time": datetime.utcnow().isoformat(),
                "datacontenttype": "application/json",
                "data": {
                    "doc_id": doc_id,
                    "version": version,
                    "uri_processed": uri_processed,
                    "lang": lang,
                    "tenant": tenant,
                    "embedding_count": len(chunks),
                    "vector_dimension": len(embeddings[0]) if len(embeddings) > 0 else 0,
                    "processing_time_ms": int(processing_time)
                }
            }
            
            # Publish event to NATS
            try:
                event_data = json.dumps({
                    "specversion": event["specversion"],
                    "id": event["id"],
                    "source": event["source"],
                    "type": event["type"],
                    "time": event["time"],
                    "datacontenttype": event["datacontenttype"],
                    "data": event["data"]
                }, default=str)
                
                await self.nats_client.publish("doc.embedded.v1", event_data.encode('utf-8'))
                logger.info(f"Published embedding event to NATS")
            except Exception as e:
                logger.error(f"Failed to publish event to NATS", error=str(e))
                # Don't raise exception here as embedding was successful
            
            logger.info("Document embedded successfully", 
                       doc_id=doc_id, version=version, embeddings_count=len(chunks))
            
            return EmbeddingResult(
                doc_id=doc_id,
                version=version,
                lang=lang,
                embeddings_count=len(chunks),
                vector_dimension=len(embeddings[0]) if len(embeddings) > 0 else 0,
                processing_time_ms=int(processing_time)
            )


# Global service instance
settings = Settings()
embedder_service = EmbedderService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Document Embedder",
    description="Document embedding service with Persian and English models",
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
    await embedder_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await embedder_service.close()


@app.post("/embed")
async def embed_document(
    doc_id: str,
    version: str,
    uri_processed: str,
    lang: str,
    tenant: str,
    project: Optional[str] = None
):
    """Generate embeddings for document chunks"""
    
    model_name = settings.persian_embedding_model if lang == 'fa' else settings.english_embedding_model
    
    with embedding_duration.labels(
        tenant=tenant,
        lang=lang,
        model=model_name
    ).time():
        try:
            result = await embedder_service.embed_document(
                doc_id, version, uri_processed, lang, tenant, project
            )
            
            embedding_counter.labels(
                tenant=tenant,
                lang=lang,
                model=model_name,
                status="success"
            ).inc()
            
            embeddings_created.labels(
                tenant=tenant,
                lang=lang,
                model=model_name
            ).observe(result.embeddings_count)
            
            return result
        except Exception as e:
            logger.error("Document embedding failed", error=str(e), doc_id=doc_id)
            embedding_counter.labels(
                tenant=tenant,
                lang=lang,
                model=model_name,
                status="error"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "embedder"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level=settings.log_level.lower()
    )
