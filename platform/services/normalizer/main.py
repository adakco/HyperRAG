"""
Document Normalizer Service
Handles document normalization with PII removal and Persian/English text processing
"""

import asyncio
import json
import logging
import os
import re
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
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from fastapi.responses import Response

# PII detection and anonymization
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# Persian text processing
try:
    from hazm import Normalizer as PersianNormalizer
    PERSIAN_AVAILABLE = True
except ImportError:
    PERSIAN_AVAILABLE = False
    print("Warning: Hazm not available. Persian text processing will be limited.")

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
resource = Resource.create(attributes={SERVICE_NAME: "hyperrag-normalizer"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics with custom registry to avoid conflicts
registry = CollectorRegistry()
normalization_counter = Counter(
    'hyperrag_normalization_total',
    'Total number of document normalizations',
    ['tenant', 'lang', 'content_type', 'status'],
    registry=registry
)

normalization_duration = Histogram(
    'hyperrag_normalization_duration_seconds',
    'Time spent normalizing documents',
    ['tenant', 'lang', 'content_type'],
    registry=registry
)

pii_detection_counter = Counter(
    'hyperrag_pii_detected_total',
    'Total number of PII entities detected',
    ['tenant', 'lang', 'entity_type'],
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
    minio_bucket: str = "clean"
    service_name: str = "normalizer"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


class NormalizationResult(BaseModel):
    """Result of document normalization"""
    doc_id: str
    version: str
    uri_clean: str
    lang: str
    normalized_text: str
    pii_entities: List[Dict]
    token_count: int
    processing_time_ms: int


class TextNormalizer:
    """Text normalization utilities"""

    def __init__(self):
        self.analyzer = None
        self.anonymizer = None
        self.persian_normalizer = PersianNormalizer() if PERSIAN_AVAILABLE else None

    def _initialize_engines(self):
        """Initialize PII engines lazily"""
        if self.analyzer is None:
            try:
                self.analyzer = AnalyzerEngine()
                self.anonymizer = AnonymizerEngine()
            except Exception as e:
                logger.warning(f"Failed to initialize PII engines: {e}")
                self.analyzer = None
                self.anonymizer = None

    def normalize_persian_text(self, text: str) -> str:
        """Normalize Persian text"""
        if not self.persian_normalizer:
            logger.warning("Persian normalizer not available, using basic normalization")
            return self._basic_persian_normalization(text)

        try:
            # Normalize Persian text using Hazm
            normalized = self.persian_normalizer.normalize(text)

            # Additional Persian-specific normalizations
            normalized = self._persian_specific_normalizations(normalized)

            return normalized
        except Exception as e:
            logger.error("Persian normalization failed", error=str(e))
            return self._basic_persian_normalization(text)

    def _basic_persian_normalization(self, text: str) -> str:
        """Basic Persian text normalization without Hazm"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Normalize Persian digits
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        english_digits = '0123456789'
        for p, e in zip(persian_digits, english_digits):
            text = text.replace(p, e)

        # Normalize Persian punctuation
        text = text.replace('،', ',')
        text = text.replace('؛', ';')
        text = text.replace('؟', '?')
        text = text.replace('«', '"')
        text = text.replace('»', '"')

        return text.strip()

    def _persian_specific_normalizations(self, text: str) -> str:
        """Persian-specific text normalizations"""
        # Remove kashida (ـ)
        text = text.replace('ـ', '')

        # Normalize different forms of alef
        text = text.replace('أ', 'ا')
        text = text.replace('إ', 'ا')
        text = text.replace('آ', 'ا')

        # Normalize different forms of yeh
        text = text.replace('ي', 'ی')
        text = text.replace('ئ', 'ی')

        # Normalize different forms of teh
        text = text.replace('ة', 'ه')

        return text

    def normalize_english_text(self, text: str) -> str:
        """Normalize English text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Normalize dashes
        text = text.replace('–', '-').replace('—', '-')

        # Remove control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        return text.strip()

    def detect_and_anonymize_pii(self, text: str, lang: str) -> Tuple[str, List[Dict]]:
        """Detect and anonymize PII in text"""
        # Initialize PII engines if needed
        self._initialize_engines()

        # Check if engines are available
        if self.analyzer is None or self.anonymizer is None:
            logger.warning("PII engines not available, returning text unchanged")
            return text, []

        # Configure supported entities based on language
        if lang == 'fa':
            # Persian PII entities
            entities = ['PERSON', 'PHONE_NUMBER', 'EMAIL_ADDRESS', 'CREDIT_CARD', 'IBAN_CODE']
        else:
            # English PII entities
            entities = ['PERSON', 'PHONE_NUMBER', 'EMAIL_ADDRESS', 'CREDIT_CARD', 'SSN', 'IBAN_CODE']

        # Analyze text for PII
        results = self.analyzer.analyze(
            text=text,
            entities=entities,
            language=lang
        )

        # Convert results to list of dicts
        pii_entities = []
        for result in results:
            pii_entities.append({
                'entity_type': result.entity_type,
                'start': result.start,
                'end': result.end,
                'score': result.score,
                'text': text[result.start:result.end]
            })

        # Anonymize the text
        anonymized_text = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results
        ).text

        return anonymized_text, pii_entities


class NormalizerService:
    """Main normalizer service class"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.nats_client: Optional[NATS] = None
        self.s3_client = None
        self.text_normalizer = TextNormalizer()

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

        logger.info("Normalizer service initialized successfully")

    async def start_nats_listener(self):
        """Start NATS event listener"""
        try:
            # Subscribe to document ingestion events
            await self.nats_client.subscribe("doc.ingested.v1", cb=self.handle_document_ingested)
            logger.info("NATS listener started for document ingestion events")
        except Exception as e:
            logger.error("Failed to start NATS listener", error=str(e))

    async def handle_document_ingested(self, msg):
        """Handle document ingestion events"""
        try:
            # Parse event data
            event_data = json.loads(msg.data.decode())
            doc_id = event_data["data"]["doc_id"]
            version = event_data["data"]["version"]
            uri_raw = event_data["data"]["uri_raw"]
            lang = event_data["data"].get("lang", "en")
            tenant = event_data["data"].get("tenant", "default")

            logger.info(f"Processing document ingestion event: {doc_id}")

            # Process the document
            result = await self.normalize_document(doc_id, version, uri_raw, lang, tenant)

            # Publish normalization complete event
            event = {
                "specversion": "1.0",
                "source": "normalizer",
                "type": "doc.normalized.v1",
                "time": datetime.utcnow(),
                "datacontenttype": "application/json",
                "data": {
                    "doc_id": str(doc_id),
                    "version": str(version),
                    "uri_clean": str(result["uri_clean"]),
                    "lang": str(result["lang"]),
                    "tenant": str(tenant)
                }
            }

            # Publish event
            event_message = json.dumps(event, default=str)
            if isinstance(event_message, str):
                event_message_bytes = event_message.encode('utf-8')
            else:
                event_message_bytes = str(event_message).encode('utf-8')
            await self.nats_client.publish("doc.normalized.v1", event_message_bytes)

            logger.info(f"Document normalized and event published: {doc_id}")

        except Exception as e:
            logger.error("Failed to handle document ingestion event", error=str(e))

    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.nats_client:
            await self.nats_client.close()

    async def normalize_document(
        self,
        doc_id: str,
        version: str,
        uri_raw: str,
        lang: str,
        tenant: str
    ) -> NormalizationResult:
        """Normalize a document"""

        with tracer.start_as_current_span("normalize_document") as span:
            span.set_attribute("doc_id", doc_id)
            span.set_attribute("version", version)
            span.set_attribute("lang", lang)
            span.set_attribute("tenant", tenant)

            start_time = datetime.utcnow()

            # Download document from S3
            bucket_name = uri_raw.split('/')[2]  # Extract bucket from s3://bucket/key
            key = '/'.join(uri_raw.split('/')[3:])  # Extract key

            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            raw_content = response['Body'].read().decode('utf-8')

            # Normalize text based on language
            if lang == 'fa':
                normalized_text = self.text_normalizer.normalize_persian_text(raw_content)
            else:
                normalized_text = self.text_normalizer.normalize_english_text(raw_content)

            # Detect and anonymize PII
            anonymized_text, pii_entities = self.text_normalizer.detect_and_anonymize_pii(
                normalized_text, lang
            )

            # Count tokens (simple approximation)
            token_count = len(anonymized_text.split())

            # Upload normalized document to S3
            clean_key = f"{tenant}/clean/{doc_id}/{version}"
            uri_clean = f"s3://{self.settings.minio_bucket}/{clean_key}"

            self.s3_client.put_object(
                Bucket=self.settings.minio_bucket,
                Key=clean_key,
                Body=anonymized_text.encode('utf-8'),
                ContentType='text/plain',
                Metadata={
                    'doc_id': doc_id,
                    'version': version,
                    'lang': lang,
                    'tenant': tenant,
                    'pii_entities_count': str(len(pii_entities))
                }
            )

            # Update database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE document_versions
                    SET uri_clean = $1, processing_status = 'normalized'
                    WHERE doc_id = $2 AND version = $3
                """, uri_clean, doc_id, int(version))

            # Update metrics
            for entity in pii_entities:
                pii_detection_counter.labels(
                    tenant=tenant,
                    lang=lang,
                    entity_type=entity['entity_type']
                ).inc()

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Create CloudEvent
            event = {
                "specversion": "1.0",
                "id": str(uuid.uuid4()),
                "source": "service/normalizer",
                "type": "doc.normalized.v1",
                "time": datetime.utcnow().isoformat(),
                "datacontenttype": "application/json",
                "data": {
                    "doc_id": doc_id,
                    "version": version,
                    "uri_raw": uri_raw,
                    "uri_clean": uri_clean,
                    "lang": lang,
                    "tenant": tenant,
                    "pii_entities_count": len(pii_entities),
                    "token_count": token_count,
                    "processing_time_ms": int(processing_time)
                }
            }

            # Publish event to NATS
            event_data = json.dumps({
                "specversion": event["specversion"],
                "id": event["id"],
                "source": event["source"],
                "type": event["type"],
                "time": event["time"],
                "datacontenttype": event["datacontenttype"],
                "data": event["data"]
            })

            await self.nats_client.publish("doc.normalized.v1", str(event_data).encode())

            logger.info("Document normalized successfully",
                       doc_id=doc_id, version=version, pii_count=len(pii_entities))

            return NormalizationResult(
                doc_id=doc_id,
                version=version,
                uri_clean=uri_clean,
                lang=lang,
                normalized_text=anonymized_text,
                pii_entities=pii_entities,
                token_count=token_count,
                processing_time_ms=int(processing_time)
            )


# Global service instance
settings = Settings()
normalizer_service = NormalizerService(settings)

# FastAPI app
app = FastAPI(
    title="HyperRAG Document Normalizer",
    description="Document normalization service with PII removal and multi-language support",
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
    await normalizer_service.initialize()

    # Start NATS listener
    await normalizer_service.start_nats_listener()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await normalizer_service.close()


@app.post("/normalize")
async def normalize_document(
    doc_id: str,
    version: str,
    uri_raw: str,
    lang: str,
    tenant: str
):
    """Normalize a document"""

    with normalization_duration.labels(
        tenant=tenant,
        lang=lang,
        content_type="text/plain"
    ).time():
        try:
            result = await normalizer_service.normalize_document(
                doc_id, version, uri_raw, lang, tenant
            )

            normalization_counter.labels(
                tenant=tenant,
                lang=lang,
                content_type="text/plain",
                status="success"
            ).inc()

            return result
        except Exception as e:
            logger.error("Document normalization failed", error=str(e), doc_id=doc_id)
            normalization_counter.labels(
                tenant=tenant,
                lang=lang,
                content_type="text/plain",
                status="error"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "normalizer"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level=settings.log_level.lower()
    )
