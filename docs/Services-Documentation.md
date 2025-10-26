# HyperRAG Services - Complete Technical Documentation

**Last Updated:** 2025-10-25  
**Version:** 1.0  
**Status:** Production-Ready

---

## فهرست مطالب

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Services](#core-services)
4. [Supporting Services](#supporting-services)
5. [Data Flow](#data-flow)
6. [API Specifications](#api-specifications)
7. [Error Handling](#error-handling)
8. [Performance Metrics](#performance-metrics)

---

## Overview

HyperRAG یک سیستم RAG (Retrieval-Augmented Generation) مبتنی بر معماری میکروسرویس است که از 12 سرویس مستقل تشکیل شده است. این سیستم قابلیت پردازش اسناد چندزبانه (فارسی و انگلیسی) را دارد و از الگوی Agentic برای مدیریت جستجو و بازیابی استفاده می‌کند.

### Infrastructure Components

- **Storage**: MinIO (S3-compatible)
- **Database**: PostgreSQL (metadata)
- **Vector DB**: Qdrant (embeddings)
- **Message Queue**: NATS JetStream
- **Cache**: Redis
- **Monitoring**: Prometheus, OpenTelemetry, Grafana

---

## Architecture

### Service Communication Pattern

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────────────────────────┐
│         API Gateway                 │
│  (Auth, Rate Limit, Routing)       │
└──────┬─────────────────────────────┘
       │
       ├─────────┬──────────┬─────────┐
       │         │          │         │
       ▼         ▼          ▼         ▼
┌────────┐ ┌─────────┐ ┌──────┐ ┌─────────┐
│Ingestor │ │Normalizer│ │Chunker│ │Embedder│
└────┬────┘ └────┬─────┘ └───┬──┘ └────┬────┘
     │           │           │         │
     └───────────┴───────────┴─────────┘
                 │
          ┌───────▼───────┐
          │     NATS      │
          │   JetStream   │
          └───────┬───────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
    ┌────────┐ ┌────┐ ┌────────┐
    │Retriever│ │Reranker│ │Evaluator│
    └────┬───┘ └────┘ └────┬───┘
         │                 │
         └─────────┬───────┘
                   ▼
              ┌────────┐
              │Qdrant  │
              └────────┘
```

---

## Core Services

### 1. Ingestor Service

**Port:** 8000  
**Endpoints:**
- `POST /ingest` - Ingest a new document
- `GET /health` - Health check

#### Input Parameters

```python
{
    "doc_id": str,           # Unique document identifier
    "tenant": str,          # Tenant identifier
    "project": str,          # Project identifier
    "lang": str,             # Language code ("en" or "fa")
    "title": str (optional),
    "author": str (optional),
    "tags": List[str] (optional),
    "acl": List[str] (optional),
    "file": UploadFile       # Document file
}
```

#### Output Response

```python
{
    "doc_id": str,
    "version": int,          # Timestamp-based version
    "status": str,           # "success" or "duplicate"
    "uri_raw": str,         # S3 URI: s3://bucket/tenant/project/doc_id/version
    "sha256": str,          # SHA256 hash of file
    "file_size": int,
    "trace_id": str
}
```

#### Main Functionality

1. **Document Upload**: Receives document file via multipart/form-data
2. **Deduplication**: Checks SHA256 hash for duplicate documents
3. **Storage**: Uploads to MinIO (S3-compatible) at `s3://raw/{tenant}/{project}/{doc_id}/{version}`
4. **Metadata Storage**: Saves document metadata to PostgreSQL
5. **Event Publishing**: Publishes `doc.ingested.v1` event to NATS

#### Database Schema

```sql
INSERT INTO documents (doc_id, tenant, project, lang, created_at)
VALUES ($1, $2, $3, $4, NOW())

INSERT INTO document_versions (doc_id, version, sha256, uri_raw, uri_clean, lang, created_at)
VALUES ($1, $2, $3, $4, $5, $6, NOW())
```

#### Events Published

```json
{
    "type": "doc.ingested.v1",
    "data": {
        "doc_id": "doc-123",
        "version": 1761400000,
        "uri_raw": "s3://raw/tenant/project/doc-123/1761400000",
        "tenant": "acme",
        "project": "alpha",
        "lang": "en",
        "sha256": "abc123..."
    }
}
```

#### Example Request

```bash
curl -X POST http://localhost:8000/ingest \
  -F "doc_id=test-doc-001" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=en" \
  -F "file=@document.pdf"
```

---

### 2. Normalizer Service

**Port:** 8001  
**Endpoints:**
- `POST /normalize` - Normalize a document
- `GET /health` - Health check

#### Input Parameters

```python
{
    "doc_id": str,
    "version": str,
    "uri_raw": str,         # S3 URI of raw document
    "lang": str,            # "en" or "fa"
    "tenant": str
}
```

#### Output Response

```python
{
    "doc_id": str,
    "version": str,
    "uri_clean": str,       # S3 URI: s3://clean/tenant/clean/doc_id/version
    "lang": str,
    "normalized_text": str,
    "pii_entities": List[Dict],
    "token_count": int,
    "processing_time_ms": int
}
```

#### Main Functionality

1. **Document Download**: Downloads document from MinIO using `uri_raw`
2. **PII Detection**: Uses Microsoft Presidio to detect PII entities (emails, phone numbers, etc.)
3. **PII Removal**: Removes or anonymizes detected PII
4. **Text Normalization**:
   - **Persian**: Uses Hazm library for normalization
   - **English**: Standard text cleaning
5. **Storage**: Uploads cleaned text to MinIO at `s3://clean/{tenant}/clean/{doc_id}/{version}`
6. **Metadata Update**: Updates PostgreSQL with `uri_clean`
7. **Event Publishing**: Publishes `doc.normalized.v1` event to NATS

#### Persian Text Processing

```python
# Uses Hazm library for Persian-specific tasks
from hazm import Normalizer

persian_normalizer = Normalizer()
normalized_text = persian_normalizer.normalize(text)
```

#### PII Detection Example

```python
# Detects: EMAIL, PHONE_NUMBER, PERSON, CREDIT_CARD
analyzer = AnalyzerEngine()
entities = analyzer.analyze(text=text, language='fa')

# Anonymizes PII
anonymizer = AnonymizerEngine()
anonymized_text = anonymizer.anonymize(text=text, entities=entities)
```

#### Example Request

```bash
curl -X POST "http://localhost:8001/normalize?doc_id=test-001&version=1761400000&uri_raw=s3://raw/acme/alpha/test-001/1761400000&lang=en&tenant=acme"
```

---

### 3. Chunker Service

**Port:** 8003  
**Endpoints:**
- `POST /chunk` - Chunk a document
- `GET /health` - Health check

#### Input Parameters

```python
{
    "doc_id": str,
    "version": str,
    "uri_clean": str,       # S3 URI of cleaned document
    "lang": str,
    "tenant": str
}
```

#### Output Response

```python
{
    "doc_id": str,
    "version": str,
    "lang": str,
    "chunks": List[Dict],   # [{"chunk_index": 0, "content": "...", "token_count": 150}]
    "total_chunks": int,
    "total_tokens": int,
    "processing_time_ms": int,
    "uri_processed": str    # s3://clean/tenant/chunked/doc_id/version
}
```

#### Main Functionality

1. **Document Download**: Downloads cleaned text from MinIO
2. **Language-Specific Chunking**:
   - **English**: Uses tiktoken + RecursiveCharacterTextSplitter
   - **Persian**: Uses Hazm sent_tokenize for sentence-aware chunking
3. **Token Counting**: Counts tokens per chunk
4. **Storage**: 
   - Saves chunks as JSON to MinIO at `s3://clean/{tenant}/chunked/{doc_id}/{version}`
   - Stores chunk metadata in PostgreSQL `document_chunks` table
5. **Database Update**: Updates `document_versions` with chunk count
6. **Event Publishing**: Publishes `doc.chunked.v1` event to NATS

#### Chunking Strategy

```python
# English
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=count_tokens_english
)

# Persian
chunks = persian_sent_tokenize(text, chunk_size=500, overlap=50)
```

#### Database Schema

```sql
INSERT INTO document_chunks (
    chunk_id, doc_id, version, chunk_index,
    content, lang, token_count
) VALUES ($1, $2, $3, $4, $5, $6, $7)

UPDATE document_versions
SET chunk_count = $1
WHERE doc_id = $2 AND version = $3
```

#### Example Request

```bash
curl -X POST "http://localhost:8003/chunk?doc_id=test-001&version=1761400000&uri_clean=s3://clean/acme/clean/test-001/1761400000&lang=en&tenant=acme"
```

---

### 4. Embedder Service

**Port:** 8004  
**Endpoints:**
- `POST /embed` - Generate embeddings
- `GET /health` - Health check

#### Input Parameters

```python
{
    "doc_id": str,
    "version": str,
    "uri_processed": str,   # S3 URI of chunked document
    "lang": str,
    "tenant": str,
    "project": str (optional)
}
```

#### Output Response

```python
{
    "doc_id": str,
    "version": str,
    "lang": str,
    "embeddings_count": int,
    "vector_dimension": int,  # 384 for Persian, 3072 for English
    "processing_time_ms": int
}
```

#### Main Functionality

1. **Chunk Download**: Downloads chunked document from MinIO
2. **Model Selection**:
   - **Persian**: `HooshvareLab/bert-fa-base-uncased` (384 dimensions)
   - **English**: `text-embedding-3-large` (3072 dimensions)
3. **Embedding Generation**: Uses SentenceTransformers to generate embeddings
4. **Vector Storage**: Uploads embeddings to Qdrant vector database
5. **Database Update**: Updates `document_chunks` with `embedding` field (point ID)
6. **Database Update**: Updates `document_versions` with embedding count
7. **Event Publishing**: Publishes `doc.embedded.v1` event to NATS

#### Qdrant Point Structure

```python
PointStruct(
    id=uuid.uuid4(),  # UUID
    vector=embedding.tolist(),  # Vector array
    payload={
        'chunk_id': f"{doc_id}_{version}_{chunk_index}",
        'doc_id': doc_id,
        'version': int(version),
        'chunk_index': chunk_index,
        'content': chunk_content,
        'lang': lang,
        'tenant': tenant,
        'project': project,  # Added for filtering
        'token_count': token_count,
        'char_count': char_count,
        'created_at': timestamp
    }
)
```

#### Embedding Models

```python
# Persian
model = SentenceTransformer('HooshvareLab/bert-fa-base-uncased')
vector = model.encode(text)  # 384 dimensions

# English
model = SentenceTransformer('text-embedding-3-large')
vector = model.encode(text)  # 3072 dimensions
```

#### Example Request

```bash
curl -X POST "http://localhost:8004/embed?doc_id=test-001&version=1761400000&uri_processed=s3://clean/acme/chunked/test-001/1761400000&lang=en&tenant=acme&project=alpha"
```

---

### 5. Retriever Service

**Port:** 8002  
**Endpoints:**
- `POST /retrieve` - Retrieve documents
- `GET /health` - Health check

#### Input Parameters (RetrievalRequest)

```python
{
    "query": str,           # Search query
    "lang": str,           # Query language
    "tenant": str,         # Tenant filter
    "project": str (optional),  # Project filter
    "k_dense": int = 10,   # Number of dense results
    "k_sparse": int = 10,  # Number of sparse results
    "k_final": int = 5,    # Final result count
    "search_mode": str = "balanced",  # "fast", "balanced", "thorough"
    "filters": Dict (optional)  # Custom filters
}
```

#### Output Response (RetrievalResponse)

```python
{
    "query": str,
    "results": List[Dict],  # [{"chunk_id": "...", "content": "...", "score": 0.95}]
    "total": int,          # Total results before filtering
    "processing_time_ms": int,
    "trace_id": str
}
```

#### Main Functionality

1. **Query Embedding**: Converts query to vector using appropriate model
2. **Hybrid Search**:
   - **Dense Vector Search**: Semantic search in Qdrant
   - **Sparse Search**: BM25-style lexical search (future)
3. **Filtering**: Applies tenant, project, language filters
4. **Reciprocal Rank Fusion (RRF)**: Combines dense and sparse results
5. **Reranking**: Uses reranker service to improve relevance (optional)
6. **Result Formatting**: Returns top-k results with scores and content

#### Filter Building

```python
conditions = [
    FieldCondition(key="tenant", match=MatchValue(value=tenant)),
    FieldCondition(key="lang", match=MatchValue(value=lang))
]

if project:
    conditions.append(FieldCondition(key="project", match=MatchValue(value=project)))

qdrant_filter = Filter(must=conditions)
```

#### RRF Algorithm

```python
def reciprocal_rank_fusion(scores: Dict, k: int = 60) -> Dict:
    """Reciprocal Rank Fusion for combining search results"""
    rrf_scores = {}
    for doc_id, ranks in scores.items():
        total_score = sum(1 / (k + rank) for rank in ranks)
        rrf_scores[doc_id] = total_score
    return rrf_scores
```

#### Example Request

```bash
curl -X POST http://localhost:8002/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "HyperRAG complete pipeline test",
    "lang": "en",
    "tenant": "test",
    "project": "complete-pipeline-test",
    "k_dense": 10,
    "k_final": 5
  }'
```

---

## Supporting Services

### 6. Reranker Service

**Port:** 8011  
**Function:** Reranks retrieved documents using cross-encoder models  
**Models:** Bilingual for Persian/English support

### 7. Evaluator Service

**Port:** 8005  
**Function:** Evaluates RAG responses using RAGAS metrics  
**Metrics:** Faithfulness, Answer Relevancy, Context Precision, Context Recall

### 8. Agent Orchestrator

**Port:** 8006  
**Function:** Manages agentic workflows with tool orchestration  
**Features:** Session management, tool invocation, evaluation

### 9. Policy Service

**Port:** 8007  
**Function:** Enforces access control policies using OPA  
**Policies:** Tenant isolation, ACL enforcement

### 10. Costing Service

**Port:** 8008  
**Function:** Tracks and calculates operation costs  
**Tracking:** Token usage, API costs, resource usage

### 11. Pack Long-RAG

**Port:** 8009  
**Function:** Creates long-context packages from retrieval results  
**Features:** Token budgeting, summarization

### 12. Memory Service

**Port:** 8010  
**Function:** Manages conversation memory and context  
**Storage:** Redis-based memory storage

---

## Data Flow

### End-to-End Pipeline

```
1. INGESTION
   ├─ Client uploads document
   ├─ Ingestor receives file
   ├─ Stores to MinIO: s3://raw/{tenant}/{project}/{doc_id}/{version}
   ├─ Saves metadata to PostgreSQL
   └─ Publishes event: doc.ingested.v1

2. NORMALIZATION
   ├─ Normalizer listens to doc.ingested.v1
   ├─ Downloads from MinIO
   ├─ Detects and removes PII
   ├─ Normalizes text (Persian/English specific)
   ├─ Stores to MinIO: s3://clean/{tenant}/clean/{doc_id}/{version}
   ├─ Updates metadata in PostgreSQL
   └─ Publishes event: doc.normalized.v1

3. CHUNKING
   ├─ Chunker listens to doc.normalized.v1
   ├─ Downloads cleaned text
   ├─ Chunks based on language (Persian/English)
   ├─ Saves chunks JSON to MinIO: s3://clean/{tenant}/chunked/{doc_id}/{version}
   ├─ Stores chunks in PostgreSQL: document_chunks
   ├─ Updates chunk count
   └─ Publishes event: doc.chunked.v1

4. EMBEDDING
   ├─ Embedder listens to doc.chunked.v1
   ├─ Downloads chunked data
   ├─ Generates embeddings (model based on language)
   ├─ Uploads vectors to Qdrant with metadata
   ├─ Updates embedding IDs in PostgreSQL
   ├─ Updates embedding count
   └─ Publishes event: doc.embedded.v1

5. RETRIEVAL
   ├─ Client sends query
   ├─ Retriever embeds query
   ├─ Searches Qdrant with filters (tenant, project, lang)
   ├─ Applies RRF to combine results
   ├─ Optionally reranks results
   └─ Returns top-k results
```

---

## API Specifications

### Common Request Format

All services accept JSON or form-encoded data and return JSON responses.

### Common Response Format

```python
{
    "status": "success" | "error",
    "data": {...},
    "error": {...} (if error)
}
```

### Health Check

All services implement `GET /health` endpoint:

```bash
curl http://localhost:{PORT}/health
```

Response:
```json
{
    "status": "healthy",
    "service": "ingestor",
    "version": "1.0"
}
```

---

## Error Handling

### Common Error Codes

- `400 Bad Request`: Invalid input parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Response Format

```python
{
    "detail": "Error message",
    "error_code": "ERROR_CODE",
    "trace_id": "uuid"
}
```

---

## Performance Metrics

### Service Latencies (p95)

| Service | Latency Target | Actual (p95) |
|---------|---------------|--------------|
| Ingestor | < 500ms | 253ms |
| Normalizer | < 500ms | 117ms |
| Chunker | < 300ms | 110ms |
| Embedder | < 6000ms | 4985ms |
| Retriever | < 1500ms | ~1200ms |

### Database Operations

- **PostgreSQL**: Connection pool (5-20 connections)
- **Qdrant**: HNSW index (m=32, ef_construct=256)
- **Redis**: Cache with TTL (default 1 hour)

### Observability

- **Metrics**: Prometheus (counter, histogram)
- **Traces**: OpenTelemetry → Tempo
- **Logs**: Structured logging with correlation IDs

---

## Security

### Multi-Tenancy

- All services filter by `tenant` parameter
- Data isolation at storage level (MinIO bucket prefixes)
- Qdrant filters by tenant in payload
- PostgreSQL RLS policies

### Data Protection

- PII detection and removal in normalizer
- SHA256 verification for duplicate detection
- Access control lists (ACL) for document access

---

## Conclusion

این مستند شامل جزئیات کامل تمام سرویس‌های HyperRAG است. برای اطلاعات بیشتر به فایل‌های زیر مراجعه کنید:

- [Architecture.md](Architecture.md) - معماری کلی
- [Technical-Spec.md](Technical-Spec.md) - مشخصات فنی
- [API.md](API.md) - API Reference

---

**تماس**: برای سوالات و پشتیبانی با تیم توسعه تماس بگیرید.

