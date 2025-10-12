"""
Document Chunker Service
Intelligent document chunking with language-specific segmentation for Persian and English
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import asyncpg
import boto3
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
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Persian text processing
try:
    from hazm import sent_tokenize, word_tokenize
    PERSIAN_AVAILABLE = True
except ImportError:
    PERSIAN_AVAILABLE = False
    print("Warning: Hazm not available. Persian text processing will be limited.")

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
chunking_counter = Counter(
    'hyperrag_chunking_total',
    'Total number of document chunking operations',
    ['tenant', 'lang', 'content_type', 'status']
)

chunking_duration = Histogram(
    'hyperrag_chunking_duration_seconds',
    'Time spent chunking documents',
    ['tenant', 'lang', 'content_type']
)

chunks_created = Histogram(
    'hyperrag_chunks_created_total',
    'Number of chunks created per document',
    ['tenant', 'lang', 'content_type']
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://hyperrag:password123@localhost:5432/hyperrag"
    redis_url: str = "redis://localhost:6379"
    nats_url: str = "nats://localhost:4222"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password123"
    minio_bucket: str = "processed"
    service_name: str = "chunker"
    log_level: str = "INFO"
    
    # Chunking parameters
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunk_size: int = 2000
    min_chunk_size: int = 100
    
    class Config:
        env_file = ".env"


class ChunkingResult(BaseModel):
    """Result of document chunking"""
    doc_id: str
    version: str
    lang: str
    chunks: List[Dict]
    total_chunks: int
    total_tokens: int
    processing_time_ms: int


class LanguageSpecificChunker:
    """Language-specific chunking utilities"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.english_tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Initialize text splitters
        self.english_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=self._count_tokens_english,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
        )
        
        self.persian_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=self._count_tokens_persian,
            separators=["\n\n", "\n", ". ", "! ", "? ", "، ", "؛ ", " ", ""]
        )
    
    def _count_tokens_english(self, text: str) -> int:
        """Count tokens in English text using tiktoken"""
        return len(self.english_tokenizer.encode(text))
    
    def _count_tokens_persian(self, text: str) -> int:
        """Count tokens in Persian text (approximation)"""
        # Simple approximation: 1 token ≈ 4 characters for Persian
        return len(text) // 4
    
    def chunk_english_text(self, text: str) -> List[Dict]:
        """Chunk English text using RecursiveCharacterTextSplitter"""
        chunks = self.english_splitter.split_text(text)
        
        result = []
        for i, chunk in enumerate(chunks):
            token_count = self._count_tokens_english(chunk)
            result.append({
                'chunk_index': i,
                'content': chunk,
                'token_count': token_count,
                'char_count': len(chunk),
                'lang': 'en'
            })
        
        return result
    
    def chunk_persian_text(self, text: str) -> List[Dict]:
        """Chunk Persian text with language-specific considerations"""
        if PERSIAN_AVAILABLE:
            return self._chunk_persian_with_hazm(text)
        else:
            return self._chunk_persian_basic(text)
    
    def _chunk_persian_with_hazm(self, text: str) -> List[Dict]:
        """Chunk Persian text using Hazm for better sentence segmentation"""
        # Split into sentences first
        sentences = sent_tokenize(text)
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens_persian(sentence)
            
            # If adding this sentence would exceed chunk size, start a new chunk
            if current_tokens + sentence_tokens > self.settings.chunk_size and current_chunk:
                chunks.append({
                    'chunk_index': chunk_index,
                    'content': current_chunk.strip(),
                    'token_count': current_tokens,
                    'char_count': len(current_chunk),
                    'lang': 'fa'
                })
                chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, self.settings.chunk_overlap)
                current_chunk = overlap_text + sentence
                current_tokens = self._count_tokens_persian(current_chunk)
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append({
                'chunk_index': chunk_index,
                'content': current_chunk.strip(),
                'token_count': current_tokens,
                'char_count': len(current_chunk),
                'lang': 'fa'
            })
        
        return chunks
    
    def _chunk_persian_basic(self, text: str) -> List[Dict]:
        """Basic Persian chunking without Hazm"""
        chunks = self.persian_splitter.split_text(text)
        
        result = []
        for i, chunk in enumerate(chunks):
            token_count = self._count_tokens_persian(chunk)
            result.append({
                'chunk_index': i,
                'content': chunk,
                'token_count': token_count,
                'char_count': len(chunk),
                'lang': 'fa'
            })
        
        return result
    
    def _get_overlap_text(self, text: str, overlap_tokens: int) -> str:
        """Get overlap text from the end of a chunk"""
        words = text.split()
        if len(words) <= overlap_tokens:
            return text
        
        # Take the last overlap_tokens words
        overlap_words = words[-overlap_tokens:]
        return " ".join(overlap_words)
    
    def chunk_text(self, text: str, lang: str) -> List[Dict]:
        """Chunk text based on language"""
        if lang == 'fa':
            return self.chunk_persian_text(text)
        else:
            return self.chunk_english_text(text)


class ChunkerService:
    """Main chunker service class"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.s3_client = None
        self.chunker = LanguageSpecificChunker(settings)
        
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
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{self.settings.minio_endpoint}",
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name='us-east-1'
        )
        
        # Ensure bucket exists
        try:
            self.s3_client.head_bucket(Bucket=self.settings.minio_bucket)
        except:
            self.s3_client.create_bucket(Bucket=self.settings.minio_bucket)
            
        logger.info("Chunker service initialized successfully")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()
    
    async def chunk_document(
        self,
        doc_id: str,
        version: str,
        uri_clean: str,
        lang: str,
        tenant: str
    ) -> ChunkingResult:
        """Chunk a document"""
        
        with tracer.start_as_current_span("chunk_document") as span:
            span.set_attribute("doc_id", doc_id)
            span.set_attribute("version", version)
            span.set_attribute("lang", lang)
            span.set_attribute("tenant", tenant)
            
            start_time = datetime.utcnow()
            
            # Download cleaned document from S3
            bucket_name = uri_clean.split('/')[2]  # Extract bucket from s3://bucket/key
            key = '/'.join(uri_clean.split('/')[3:])  # Extract key
            
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            clean_content = response['Body'].read().decode('utf-8')
            
            # Chunk the text
            chunks = self.chunker.chunk_text(clean_content, lang)
            
            # Calculate total tokens
            total_tokens = sum(chunk['token_count'] for chunk in chunks)
            
            # Store chunks in database
            async with self.db_pool.acquire() as conn:
                # Insert chunks
                for chunk in chunks:
                    await conn.execute("""
                        INSERT INTO document_chunks 
                        (doc_id, version, chunk_index, content, lang, token_count, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, doc_id, version, chunk['chunk_index'], chunk['content'], 
                        lang, chunk['token_count'], json.dumps({'char_count': chunk['char_count']}))
                
                # Update document version with chunk count
                await conn.execute("""
                    UPDATE document_versions 
                    SET chunk_count = $1, processing_status = 'chunked'
                    WHERE doc_id = $2 AND version = $3
                """, len(chunks), doc_id, version)
            
            # Upload chunked data to S3
            chunked_data = {
                'doc_id': doc_id,
                'version': version,
                'lang': lang,
                'chunks': chunks,
                'total_chunks': len(chunks),
                'total_tokens': total_tokens,
                'chunking_metadata': {
                    'chunk_size': self.settings.chunk_size,
                    'chunk_overlap': self.settings.chunk_overlap,
                    'chunker_version': '1.0.0'
                }
            }
            
            chunked_key = f"{tenant}/chunked/{doc_id}/{version}"
            uri_processed = f"s3://{self.settings.minio_bucket}/{chunked_key}"
            
            self.s3_client.put_object(
                Bucket=self.settings.minio_bucket,
                Key=chunked_key,
                Body=json.dumps(chunked_data, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'doc_id': doc_id,
                    'version': version,
                    'lang': lang,
                    'tenant': tenant,
                    'chunk_count': str(len(chunks))
                }
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Create CloudEvent
            event = CloudEvent(
                specversion="1.0",
                id=str(uuid.uuid4()),
                source="service/chunker",
                type="doc.chunked.v1",
                time=datetime.utcnow(),
                datacontenttype="application/json",
                data={
                    "doc_id": doc_id,
                    "version": version,
                    "uri_clean": uri_clean,
                    "uri_processed": uri_processed,
                    "lang": lang,
                    "tenant": tenant,
                    "chunk_count": len(chunks),
                    "total_tokens": total_tokens,
                    "processing_time_ms": int(processing_time)
                }
            )
            
            # Publish event to NATS
            event_data = json.dumps({
                "specversion": event["specversion"],
                "id": event["id"],
                "source": event["source"],
                "type": event["type"],
                "time": event["time"].isoformat(),
                "datacontenttype": event["datacontenttype"],
                "data": event["data"]
            })
            
            await self.nats_client.publish("doc.chunked.v1", event_data.encode())
            
            logger.info("Document chunked successfully", 
                       doc_id=doc_id, version=version, chunks_count=len(chunks))
            
            return ChunkingResult(
                doc_id=doc_id,
                version=version,
                lang=lang,
                chunks=chunks,
                total_chunks=len(chunks),
                total_tokens=total_tokens,
                processing_time_ms=int(processing_time)
            )


# Global service instance
settings = Settings()
chunker_service = ChunkerService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Document Chunker",
    description="Intelligent document chunking with language-specific segmentation",
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
    await chunker_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await chunker_service.close()


@app.post("/chunk")
async def chunk_document(
    doc_id: str,
    version: str,
    uri_clean: str,
    lang: str,
    tenant: str
):
    """Chunk a document"""
    
    with chunking_duration.labels(
        tenant=tenant,
        lang=lang,
        content_type="text/plain"
    ).time():
        try:
            result = await chunker_service.chunk_document(
                doc_id, version, uri_clean, lang, tenant
            )
            
            chunking_counter.labels(
                tenant=tenant,
                lang=lang,
                content_type="text/plain",
                status="success"
            ).inc()
            
            chunks_created.labels(
                tenant=tenant,
                lang=lang,
                content_type="text/plain"
            ).observe(result.total_chunks)
            
            return result
        except Exception as e:
            logger.error("Document chunking failed", error=str(e), doc_id=doc_id)
            chunking_counter.labels(
                tenant=tenant,
                lang=lang,
                content_type="text/plain",
                status="error"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "chunker"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level=settings.log_level.lower()
    )
