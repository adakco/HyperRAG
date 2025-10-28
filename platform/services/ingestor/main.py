"""
Document Ingestor Service
Handles document ingestion with CloudEvent support and multi-language processing
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
import boto3
import structlog
# from cloudevents.http import CloudEvent  # Not used anymore
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
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
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, CollectorRegistry
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
resource = Resource.create(attributes={SERVICE_NAME: "hyperrag-ingestor"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics with custom registry to avoid conflicts
registry = CollectorRegistry()
ingestion_counter = Counter(
    'hyperrag_ingestion_total',
    'Total number of document ingestions',
    ['tenant', 'lang', 'content_type', 'status'],
    registry=registry
)

ingestion_duration = Histogram(

    'hyperrag_ingestion_duration_seconds',
    'Time spent processing document ingestion',
    ['tenant', 'lang', 'content_type'],
    registry=registry
)

file_size_bytes = Histogram(

    'hyperrag_ingestion_file_size_bytes',
    'Size of ingested files in bytes',
    ['tenant', 'content_type'],
    registry=registry
)


class Settings(BaseSettings):
    """Application settings"""
    database_url: str = "postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
    redis_url: str = "redis://192.168.2.23:6479"
    nats_url: str = "nats://192.168.2.23:4222"
    minio_endpoint: str = "http://192.168.2.23:9190"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "raw"
    service_name: str = "ingestor"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


class DocumentIngestionRequest(BaseModel):
    """Request model for document ingestion"""
    doc_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    tenant: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    project: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    lang: str = Field(..., enum=["en", "fa"])
    title: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = []
    acl: Optional[List[str]] = []


class DocumentIngestionResponse(BaseModel):
    """Response model for document ingestion"""
    doc_id: str
    version: int
    status: str
    uri_raw: str
    sha256: str
    file_size: int
    trace_id: str


class IngestorService:
    """Main ingestor service class"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.s3_client = None

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

        # Ensure bucket exists (skip if access denied)
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

        logger.info("Ingestor service initialized successfully")

    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()

    async def ingest_document(
        self,
        request: DocumentIngestionRequest,
        file_content: bytes,
        content_type: str
    ) -> DocumentIngestionResponse:
        """Ingest a document and trigger processing pipeline"""

        with tracer.start_as_current_span("ingest_document") as span:
            span.set_attribute("doc_id", request.doc_id)
            span.set_attribute("tenant", request.tenant)
            span.set_attribute("lang", request.lang)
            span.set_attribute("content_type", content_type)

            trace_id = str(span.get_span_context().trace_id)

            # Generate version and file paths
            version = int(datetime.utcnow().timestamp())
            file_key = f"{request.tenant}/{request.project}/{request.doc_id}/{version}"
            uri_raw = f"s3://{self.settings.minio_bucket}/{file_key}"

            # Calculate file hash and size
            import hashlib
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            file_size = len(file_content)

            # Check for duplicate
            async with self.db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT version FROM document_versions WHERE doc_id = $1 AND sha256 = $2",
                    request.doc_id, sha256_hash
                )

                if existing:
                    logger.info("Duplicate document detected", doc_id=request.doc_id, sha256=sha256_hash)
                    return DocumentIngestionResponse(
                        doc_id=request.doc_id,
                        version=existing['version'],
                        status="duplicate",
                        uri_raw=uri_raw,
                        sha256=sha256_hash,
                        file_size=file_size,
                        trace_id=trace_id
                    )

            # Upload to S3/MinIO
            self.s3_client.put_object(
                Bucket=self.settings.minio_bucket,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    'doc_id': request.doc_id,
                    'tenant': request.tenant,
                    'project': request.project,
                    'lang': request.lang,
                    'version': str(version)
                }
            )

            # Store metadata in database
            async with self.db_pool.acquire() as conn:
                # Insert or update document
                await conn.execute("""
                    INSERT INTO documents (doc_id, tenant, project, lang, title, content_type, file_size, latest_version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        latest_version = $8,
                        updated_at = NOW()
                """, request.doc_id, request.tenant, request.project, request.lang,
                    request.title, content_type, file_size, version)

                # Insert document version
                await conn.execute("""
                    INSERT INTO document_versions
                    (doc_id, version, sha256, uri_raw, lang, processing_status)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, request.doc_id, version, sha256_hash, uri_raw, request.lang, "pending")

            # Create event dict (avoiding CloudEvent object issues)
            event = {
                "specversion": str("1.0"),
                "id": str(uuid.uuid4()),
                "source": str("api/ingestor"),
                "type": str("doc.ingested.v1"),
                "time": datetime.utcnow(),
                "datacontenttype": str("application/json"),
                "data": {
                    "doc_id": str(request.doc_id),
                    "version": str(version),
                    "uri_raw": str(uri_raw),
                    "content_type": str(content_type),
                    "lang": str(request.lang),
                    "tenant": str(request.tenant),
                    "project": str(request.project),
                    "acl": [str(x) for x in request.acl] if request.acl else [],
                    "sha256": str(sha256_hash),
                    "file_size": str(file_size),
                    "title": str(request.title),
                    "author": str(request.author) if request.author else "",
                    "tags": [str(x) for x in request.tags] if request.tags else [],
                    "processing_status": str("pending")
                }
            }

            # Publish event to NATS
            try:
                event_message = json.dumps(event, default=str)
                # Ensure event_message is bytes
                if isinstance(event_message, str):
                    event_message_bytes = event_message.encode('utf-8')
                else:
                    event_message_bytes = str(event_message).encode('utf-8')
                await self.nats_client.publish("doc.ingested.v1", event_message_bytes)
            except Exception as e:
                logger.warning("Failed to publish to NATS", error=str(e))

            # Store event in database for audit
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO processing_events
                    (specversion, source, type, time, datacontenttype, data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, event["specversion"], event["source"], event["type"],
                    datetime.utcnow(), event["datacontenttype"], json.dumps(event["data"], default=str))

            # Update metrics
            ingestion_counter.labels(
                tenant=request.tenant,
                lang=request.lang,
                content_type=content_type,
                status="success"
            ).inc()

            file_size_bytes.labels(
                tenant=request.tenant,
                content_type=content_type
            ).observe(file_size)

            logger.info("Document ingested successfully",
                       doc_id=request.doc_id, version=version, tenant=request.tenant)

            return DocumentIngestionResponse(
                doc_id=request.doc_id,
                version=version,
                status="ingested",
                uri_raw=uri_raw,
                sha256=sha256_hash,
                file_size=file_size,
                trace_id=trace_id
            )


# Global service instance
settings = Settings()
ingestor_service = IngestorService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Document Ingestor",
    description="Document ingestion service with CloudEvent support",
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
    await ingestor_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await ingestor_service.close()


@app.post("/ingest", response_model=DocumentIngestionResponse)
async def ingest_document(
    doc_id: str = Form(...),
    tenant: str = Form(...),
    project: str = Form(...),
    lang: str = Form(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string
    acl: Optional[str] = Form(None),   # JSON string
    file: UploadFile = File(...)
):
    """Ingest a document file"""

    # Parse JSON fields
    tags_list = []
    acl_list = []

    if tags:
        try:
            tags_list = json.loads(tags)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid tags JSON")

    if acl:
        try:
            acl_list = json.loads(acl)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid ACL JSON")

    # Create request object
    request = DocumentIngestionRequest(
        doc_id=doc_id,
        tenant=tenant,
        project=project,
        lang=lang,
        title=title,
        author=author,
        tags=tags_list,
        acl=acl_list
    )

    # Read file content
    file_content = await file.read()

    # Process ingestion
    with ingestion_duration.labels(
        tenant=tenant,
        lang=lang,
        content_type=file.content_type or "application/octet-stream"
    ).time():
        try:
            response = await ingestor_service.ingest_document(
                request, file_content, file.content_type or "application/octet-stream"
            )
            return response
        except Exception as e:
            logger.error("Document ingestion failed", error=str(e), doc_id=doc_id)
            ingestion_counter.labels(
                tenant=tenant,
                lang=lang,
                content_type=file.content_type or "application/octet-stream",
                status="error"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ingestor"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/documents/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get processing status of a document"""
    async with ingestor_service.db_pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT d.doc_id, d.latest_version, dv.processing_status, dv.error_message
            FROM documents d
            LEFT JOIN document_versions dv ON d.doc_id = dv.doc_id AND d.latest_version = dv.version
            WHERE d.doc_id = $1
        """, doc_id)

        if not result:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "doc_id": result["doc_id"],
            "version": result["latest_version"],
            "status": result["processing_status"],
            "error": result["error_message"]
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower()
    )
