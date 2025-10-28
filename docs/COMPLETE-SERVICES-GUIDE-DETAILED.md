# راهنمای کامل، دقیق و جامع تمام سرویس‌های HyperRAG

**Last Updated:** 2025-10-27  
**Version:** 4.0 - Complete, Detailed & Comprehensive  
**Purpose:** توضیح شفاف، دقیق و کامل هر 13 سرویس با تمام جزئیات معماری و عملکرد

---

## 📚 فهرست مطالب

1. [معرفی سیستم](#معرفی-سیستم-hyperrag)
2. [معماری کلی](#معماری-کلی-سیستم)
3. [Core Pipeline Services](#سرویس‌های-core-pipeline)
4. [Supporting Services](#سرویس‌های-پشتیبانی)
5. [Orchestration Services](#سرویس‌های-ارکستراسیون)
6. [Security Services](#سرویس‌های-امنیتیލ)
7. [Billing Services](#سرویس‌های-بیلینگ)
8. [Enhancement Services](#سرویس‌های-تقویت-کننده)
9. [Pipeline Flow](#جریان-کامل-pipeline)
10. [Testing Guide](#راهنمای-تست)

---

# معرفی سیستم HyperRAG

HyperRAG یک سیستم پیشرفته RAG (Retrieval-Augmented Generation) است که از معماری میکروسرویس استفاده می‌کند. این سیستم قابلیت پردازش اسناد چندزبانه (فارسی و انگلیسی) را دارد و شامل **13 سرویس مستقل** است.

## ویژگی‌های کلیدی

- ✅ **Multi-tenant**: پشتیبانی از چند سازمان
- ✅ **Multi-language**: فارسی و انگلیسی
- ✅ **Hybrid Search**: جستجوی ترکیبی (Vector + Graph)
- ✅ **Event-Driven**: پردازش مبتنی بر رویداد
- ✅ **Observability**: OpenTelemetry + Prometheus + Grafana
- ✅ **Scalable**: معماری قابل گسترش

## اجزای سیستم

| Component | Technology | کاربرد |
|-----------|-----------|--------|
| **Storage** | MinIO | ذخیره‌سازی اسناد خام و پردازش شده |
| **Database** | PostgreSQL | Metadata و اطلاعات chunk‌ها |
| **Vector DB** | Qdrant | ذخیره embeddings |
| **Graph DB** | Neo4j | Knowledge Graph |
| **Message Queue** | NATS | ارتباط event-driven |
| **Cache** | Redis | کش‌گذاری |
| **Monitoring** | Prometheus + OTEL | Metrics و Tracing |
| **Visualization** | Grafana | Dashboard و Service Graph |

---

# معماری کلی سیستم

## نمودار جریان داده

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────────────────────┐
│      Ingestor (8000)            │ ← Upload document
│  - Receive file                 │
│  - Generate version             │
│  - Store in MinIO (raw)         │
│  - Publish NATS event           │
└──────┬──────────────────────────┘
       │ Event: doc.ingested.v1
       ▼
┌─────────────────────────────────┐
│    Normalizer (8001)            │ ← Auto trigger (event-driven)
│  - Read from MinIO              │
│  - Detect PII                   │
│  - Normalize text               │
│  - Store in MinIO (clean)       │
│  - Publish NATS event           │
└──────┬──────────────────────────┘
       │ Event: doc.normalized.v1
       ▼
┌─────────────────────────────────┐
│     Chunker (8003)              │ ← Manual trigger
│  - Split into chunks            │
│  - Calculate tokens             │
│  - Store in PostgreSQL          │
│  - Store in MinIO               │
└──────┬──────────────────────────┘
       ▼
┌─────────────────────────────────┐
│    Embedder (8004)              │ ← Manual trigger
│  - Generate embeddings          │
│  - Store in Qdrant              │
│  - Update PostgreSQL            │
└──────┬──────────────────────────┘
       ▼
┌─────────────────────────────────┐
│    Retriever (8002)             │ ← User query
│  - Vector search (Qdrant)       │
│  - Graph search (Neo4j)         │
│  - Hybrid fusion                │
│  - Return results               │
└─────────────────────────────────┘
```

## انواع سرویس‌ها

| دسته | سرویس‌ها | تعداد | هدف |
|------|---------|-------|-----|
| **Core Pipeline** | Ingestor, Normalizer, Chunker, Embedder, Retriever | 5 | پردازش اصلی اسناد |
| **Supporting** | Reranker, Evaluator | 2 | بهبود و ارزیابی |
| **Orchestration** | Agent-Orch | 1 | هماهنگی workflow |
| **Security** | Policy | 1 | کنترل دسترسی |
| **Billing** | Costing | 1 | محاسبه هزینه |
| **Enhancement** | Pack, Memory, Graph KG | 3 | قابلیت‌های پیشرفته |

---

# سرویس‌های Core Pipeline

## 1. Ingestor Service (Port 8000)

### معرفی سرویس

**Ingestor** اولین مرحله در pipeline پردازش اسناد است. این سرویس فایل‌های آپلود شده توسط کاربر را دریافت می‌کند، پردازش می‌کند و در MinIO ذخیره می‌کند.

### معماری و عملکرد

```
┌──────────┐      ┌──────────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  Client  │─────▶│   Ingestor   │─────▶│  MinIO   │─────▶│PostgreSQL│─────▶│   NATS   │
│  Upload  │      │   Port 8000  │      │  Raw     │      │ Metadata │      │  Event   │
│   File   │      │              │      │ Storage  │      │          │      │ Publish  │
└──────────┘      └──────────────┘      └──────────┘      └──────────┘      └──────────┘
```

### وظایف اصلی

1. **دریافت فایل** از client از طریق HTTP POST (multipart/form-data)
2. **تولید Version** number منحصر به فرد (Unix timestamp)
3. **محاسبه Hash** SHA-256 برای اطمینان از یکپارچگی فایل
4. **ذخیره‌سازی** در MinIO در bucket `raw` با ساختار: `{tenant}/{project}/{doc_id}/{version}`
5. **ثبت Metadata** در PostgreSQL در جدول `documents` و `document_versions`
6. **انتشار Event** به NATS با topic `doc.ingested.v1` برای ادامه pipeline

### کلاس‌ها و متدهای اصلی

#### کلاس `IngestorService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS, MinIO
- `ingest_document()`: پردازش و ذخیره سند
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /ingest

**Method**: POST  
**Content-Type**: multipart/form-data

**Input Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doc_id` | string | ✅ | شناسه منحصر به فرد سند |
| `tenant` | string | ✅ | شناسه tenant (شرکت/سازمان) |
| `project` | string | ✅ | شناسه پروژه |
| `lang` | string | ✅ | زبان سند: "en" یا "fa" |
| `file` | file | ✅ | فایل سند (txt, pdf, docx, ...) |
| `title` | string | ❌ | عنوان سند |
| `author` | string | ❌ | نام نویسنده |
| `tags` | JSON string | ❌ | آرایه JSON از برچسب‌ها |
| `acl` | JSON string | ❌ | آرایه JSON از لیست کنترل دسترسی |

**Output Schema:**

```json
{
  "doc_id": "python-guide-001",
  "version": 1730123456789,
  "status": "ingested",
  "uri_raw": "s3://raw/mycompany/docs/python-guide-001/1730123456789",
  "sha256": "a8f5f167f44f4964e6c998dee827110c",
  "file_size": 245760,
  "file_name": "document.pdf",
  "content_type": "application/pdf",
  "upload_time": "2025-10-27T10:30:00Z",
  "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=python-guide-001" \
  -F "tenant=mycompany" \
  -F "project=documentation" \
  -F "lang=en" \
  -F "title=Python Programming Guide" \
  -F "author=John Doe" \
  -F "tags=[\"python\", \"programming\", \"guide\"]" \
  -F "file=@document.pdf"
```

**Example Response:**

```json
{
  "doc_id": "python-guide-001",
  "version": 1730123456789,
  "status": "ingested",
  "uri_raw": "s3://raw/mycompany/docs/python-guide-001/1730123456789",
  "sha256": "a8f5f167f44f4964e6c998dee827110c",
  "file_size": 245760,
  "file_name": "document.pdf",
  "content_type": "application/pdf",
  "upload_time": "2025-10-27T10:30:00Z",
  "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
}
```

### Event Publishing

بعد از موفقیت، این event به NATS ارسال می‌شود:

```json
{
  "type": "doc.ingested.v1",
  "source": "ingestor",
  "specversion": "1.0",
  "data": {
    "doc_id": "python-guide-001",
    "version": "1730123456789",
    "uri_raw": "s3://raw/mycompany/docs/python-guide-001/1730123456789",
    "lang": "en",
    "tenant": "mycompany",
    "project": "documentation"
  }
}
```

### نحوه استفاده در کد Python

```python
import requests

# آماده‌سازی فایل
files = {
    'file': ('document.pdf', open('document.pdf', 'rb'), 'application/pdf')
}

data = {
    'doc_id': 'python-guide-001',
    'tenant': 'mycompany',
    'project': 'documentation',
    'lang': 'en',
    'title': 'Python Programming Guide'
}

# ارسال درخواست
response = requests.post('http://localhost:8000/ingest', files=files, data=data)

if response.status_code == 200:
    result = response.json()
    print(f"Document uploaded: {result['doc_id']}")
    print(f"Version: {result['version']}")
    print(f"URI: {result['uri_raw']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### Health Check

#### Endpoint: GET /health

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "ingestor",
  "version": "1.0",
  "database_connected": true,
  "minio_connected": true,
  "nats_connected": true
}
```

---

## 2. Normalizer Service (Port 8001)

### معرفی سرویس

**Normalizer** سرویس پاکسازی و نرمال‌سازی متن است که به صورت event-driven کار می‌کند. این سرویس بعد از دریافت event از Ingestor، متن را پاکسازی، PII (Personally Identifiable Information) را حذف، و نرمال‌سازی می‌کند.

### معماری و عملکرد

```
┌──────────┐      ┌──────────────┐      ┌──────────┐      ┌──────────┐
│   NATS   │─────▶│  Normalizer  │─────▶│  MinIO   │─────▶│   NATS   │
│  Event   │      │  Port 8001   │      │  Clean   │      │  Event   │
│ doc.     │      │              │      │ Storage  │      │ doc.     │
│ingested  │      │              │      │          │      │normalized│
└──────────┘      └──────────────┘      └──────────┘      └──────────┘
```

### وظایف اصلی

1. **خواندن سند** از MinIO براساس `uri_raw` از event
2. **تشخیص زبان** به صورت خودکار (persian یا english)
3. **حذف PII** با استفاده از library `presidio`
4. **نرمال‌سازی فارسی** با استفاده از `hazm`
5. **نرمال‌سازی انگلیسی** برای پاکسازی whitespace و علائم
6. **ذخیره نسخه clean** در MinIO در bucket `raw`
7. **انتشار Event** به NATS با topic `doc.normalized.v1`

### ویژگی‌های خاص

#### PII Detection با Presidio

موارد شناسایی شده:
- Email addresses
- Phone numbers
- Credit card numbers
- IP addresses
- Names (Person names)
- Dates

#### Persian Normalization با Hazm

```python
from hazm import Normalizer as PersianNormalizer

normalizer = PersianNormalizer()
text = "این متن   فارسی است!"
cleaned = normalizer.normalize(text)
# نتیجه: "این متن فارسی است"
```

### کلاس‌-b متدهای اصلی

#### کلاس `NormalizerService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS, MinIO
- `start_nats_listener()`: subscribe به event `doc.ingested.v1`
- `handle_document_ingested()`: پردازش event و normalize
- `normalize_text()`: پاکسازی و نرمال‌سازی متن
- `close()`: بستن تمام اتصالات

### Event Subscriber

#### Listening to: `doc.ingested.v1`

```json
{
  "type": "doc.ingested.v1",
  "data": {
    "doc_id": "python-guide-001",
    "version": "1730123456789",
    "uri_raw": "s3://raw/mycompany/docs/python-guide-001/1730123456789",
    "lang": "en",
    "tenant": "mycompany"
  }
}
```

### Event Publisher

#### Publishing: `doc.normalized.v1`

```json
{
  "type": "doc.normalized.v1",
  "source": "normalizer",
  "specversion": "1.0",
  "data": {
    "doc_id": "python-guide-001",
    "version": "1730123456789",
    "uri_clean": "s3://raw/mycompany/docs/python-guide-001/1730123456789/clean",
    "lang": "en",
    "tenant": "mycompany",
    "project": "documentation",
    "pii_detected": 3,
    "pii_removed": true
  }
}
```

### API Endpoints

این سرویس فقط health check endpoint دارد و به صورت event-driven کار می‌کند.

#### GET /health

```bash
curl http://localhost:8001/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "normalizer",
  "events_processed": 1250,
  "pii_detected": 342
}
```

### نحوه استفاده

این سرویس نیازی به فراخوانی مستقیم ندارد. به محض آپلود سند توسط Ingestor، به صورت خودکار event دریافت می‌کند و پردازش را شروع می‌کند.

### مثال عملی

```python
# 1. User آپلود می‌کند
response = requests.post('http://localhost:8000/ingest', ...)
# result: {"doc_id": "test", "version": "123", "uri_raw": "s3://..."}

# 2. بعد از 5-10 ثانیه، Normalizer خودکار کار می‌کند
# 3. شما می‌توانید فایل clean شده را بررسی کنید:

import boto3

s3 = boto3.client('s3', 
    endpoint_url='http://192.168.2.23:9190',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin123'
)

clean_content = s3.get_object(
    Bucket='raw',
    Key='mycompany/docs/test/123/clean'
)['Body'].read()
```

---

## 3. Chunker Service (Port 8003)

### معرفی سرویس

**Chunker** سرویس تقسیم اسناد به chunks برای embedding است. این سرویس متن clean شده را به قطعات قابل مدیریت تقسیم می‌کند.

### معماری و عملکرد

```
API Call → Chunker → PostgreSQL (metadata) → MinIO (chunks)
```

### وظایف اصلی

1. **خواندن سند clean شده** از MinIO
2. **تشخیص زبان** (persian یا english)
3. **تقسیم به chunks** با استفاده از `langchain_text_splitters`
4. **محاسبه token count** با استفاده از `tiktoken`
5. **ذخیره در PostgreSQL** در جدول `document_chunks`
6. **ذخیره chunks در MinIO** برای پردازش بعدی

### پارامترهای Chunking

- `chunk_size`: 1000 tokens
- `chunk_overlap`: 200 tokens
- `max_chunk_size`: 2000 tokens
- `min_chunk_size`: 100 tokens

### کلاس‌ها و متدهای اصلی

#### کلاس `LanguageSpecificChunker`

- `chunk_text()`: تقسیم متن براساس زبان

#### کلاس `ChunkerService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS, MinIO
- `chunk_document()`: پردازش و chunking سند
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /chunk

**Input (Query Parameters):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doc_id` | string | ✅ | شناسه سند |
| `version` | string | ✅ | نسخه سند |
| `uri_clean` | string | ✅ | URI فایل clean شده در MinIO |
| `lang` | string | ✅ | "en" یا "fa" |
| `tenant` | string | ✅ | tenant ID |

**Output Schema:**

```json
{
  "doc_id": "python-001",
  "version": "1730123456789",
  "total_chunks": 15,
  "total_tokens": 4523,
  "uri_processed": "s3://raw/.../chunked/...",
  "chunks": [
    {
      "chunk_id": "python-001-1730123456789-0",
      "chunk_index": 0,
      "content": "First chunk...",
      "token_count": 250
    }
  ]
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:8003/chunk?doc_id=python-001&version=1730123456789&uri_clean=s3://raw/tenant/project/python-001/1730123456789/clean&lang=en&tenant=mycompany"
```

---

## 4. Embedder Service (Port 8004)

### معرفی سرویس

**Embedder** سرویس تولید embeddings برای chunks و ذخیره در Qdrant است.

### معماری و عملکرد

```
API Call → Embedder → Qdrant (vectors) → PostgreSQL (metadata)
```

### وظایف اصلی

1. **خواندن chunks از MinIO**
2. **تولید embeddings** با استفاده از SentenceTransformer
3. **ذخیره در Qdrant** به صورت points
4. **ثبت metadata در PostgreSQL**

### مدل‌های Embedding

- **Persian**: `paraphrase-multilingual-MiniLM-L12-v2`
- **English**: `all-MiniLM-L6-v2`
- **Dimension**: 384
- **Batch Size**: 32

### کلاس‌ها و متدهای اصلی

#### کلاس `EmbeddingService`

- `initialize()`: بارگذاری مدل‌ها و اتصال به Qdrant
- `get_embedding()`: تولید embedding برای متن واحد
- `get_embeddings_batch()`: تولید embedding برای batch

#### کلاس `EmbedderService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS, MinIO
- `embed_document()`: پردازش و embedding سند
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /embed

**Input (Query Parameters):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doc_id` | string | ✅ | شناسه سند |
| `version` | string | ✅ | نسخه سند |
| `uri_processed` | string | ✅ | URI chunks در MinIO |
| `lang` | string | ✅ | "en" یا "fa" |
| `tenant` | string | ✅ | tenant ID |
| `project` | string | ❌ | project ID |

**Output Schema:**

```json
{
  "doc_id": "python-001",
  "version": "1730123456789",
  "embeddings_count": 15,
  "vector_dimension": 384,
  "processing_time_ms": 1234,
  "points_created": 15
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:8004/embed?doc_id=python-001&version=1730123456789&uri_processed=s3://...&lang=en&tenant=mycompany&project=docs"
```

---

## 5. Retriever Service (Port 8002)

### معرفی سرویس

**Retriever** سرویس جستجوی hybrid است که ترکیبی از vector search (Qdrant) و graph search (Neo4j) را انجام می‌دهد.

### معماری و عملکرد

```
Query → Retriever → Qdrant (vector) → Neo4j (graph) → Fusion → Results
```

### وظایف اصلی

1. **دریافت query از user**
2. **تولید embedding برای query**
3. **جستجوی vector در Qdrant**
4. **جستجوی graph در Neo4j** (اختیاری)
5. **ترکیب نتایج** (fusion)
6. **بازگرداندن نتایج**

### Hybrid Retrieval

- **Vector Weight**: 0.7 (پیش‌فرض)
- **Graph Weight**: 0.3 (پیش‌فرض)
- **Fusion Method**: Weighted score

### کلاس‌ها و متدهای اصلی

#### کلاس `EmbeddingService`

- `initialize()`: بارگذاری مدل‌ها
- `get_embedding()`: تولید embedding
- `rerank()`: reranking documents

#### کلاس `RetrieverService`

- `initialize()`: اتصال به PostgreSQL, Redis, Qdrant, Neo4j
- `retrieve()`: جستجو و retrieval
- `query_graph_knowledge()`: جستجوی graph
- `_fuse_results()`: ترکیب نتایج
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /retrieve

**Input (JSON):**

```json
{
  "query": "Python programming",
  "tenant": "mycompany",
  "lang": "en",
  "project": "docs",
  "limit": 5,
  "use_graph": true,
  "vector_weight": 0.7,
  "graph_weight": 0.3
}
```

**Output Schema:**

```json
{
  "results": [
    {
      "chunk_id": "...",
      "doc_id": "...",
      "content": "...",
      "score": 0.85,
      "matadata": {
        "fused": true,
        "vector_score": 0.75,
        "graph_score": 0.80
      }
    }
  ],
  "metadata": {
    "total_results": 5,
    "search_time_ms": 234,
    "graph_enabled": true
  }
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python",
    "tenant": "mycompany",
    "lang": "en",
    "limit": 5
  }'
```

---

# سرویس‌های پشتیبانی

## 6. Reranker Service (Port 8011)

### معرفی سرویس

**Reranker** سرویس مرتب‌سازی مجدد نتایج با cross-encoder است.

### وظایف اصلی

1. **دریافت documents و query**
2. **امتیازدهی با cross-encoder**
3. **مرتب‌سازی براساس score**
4. **بازگرداندن نتایج**

### کلاس‌ها و متدهای اصلی

#### کلاس `RerankerService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS
- `rerank_documents()`: پردازش reranking
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /rerank

**Input (JSON):**

```json
{
  "query": "Python programming",
  "documents": [
    {"content": "Python is...", "metadata": {}},
    {"content": "Python features...", "metadata": {}}
  ],
  "lang": "en",
  "tenant": "mycompany"
}
```

**Output Schema:**

```json
{
  "reranked_documents": [
    {"content": "Python is...", "score": 0.95},
    {"content": "Python features...", "score": 0.82}
  ],
  "processing_time_ms": 123
}
```

---

## 7. Evaluator Service (Port 8005)

### معرفی سرویس

**Evaluator** سرویس ارزیابی کیفیت RAG responses است.

### وظایف اصلی

1. **دریافت query, answer, contexts**
2. **محاسبه faithfulness**
3. **محاسبه answer relevancy**
4. **محاسبه context precision**
5. **محاسبه context recall**
6. **بازگرداندن scores**

### کلاس‌ها و متدهای اصلی

#### کلاس `LanguageSpecificEvaluator`

- `evaluate_faithfulness()`: ارزیابی faithfulness
- `evaluate_answer_relevancy()`: ارزیابی relevancy
- `evaluate_context_precision()`: ارزیابی precision
- `evaluate_context_recall()`: ارزیابی recall

#### کلاس `EvaluatorService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS
- `evaluate()`: پردازش evaluation
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /evaluate

**Input (JSON):**

```json
{
  "query": "What is Python?",
  "answer": "Python is a programming language",
  "contexts": ["context1", "context2"],
  "lang": "en",
  "tenant": "mycompany"
}
```

**Output Schema:**

```json
{
  "faithfulness": 0.95,
  "answer_relevancy": 0.88,
  "context_precision": 0.92,
  "context_recall": 0.90
}
```

---

# سرویس‌های ارکستراسیون

## 8. Agent-Orch Service (Port 8006)

### معرفی سرویس

**Agent-Orch** سرویس ارکستراسیون agent workflows به صورت MCP-Native است.

### معماری و عملکرد

```
Query → Start Session → Background Processing → MCP Tools → Store Results
```

### وظایف اصلی

1. **ایجاد agent session**
2. **اجرای agent loop در background**
3. **فراخوانی MCP tools**
4. **جمع‌آوری و ذخیره نتایج**
5. **تولید پاسخ نهایی**

### پارامترهای پیکربندی

- **Max Steps**: 10
- **Max Cost**: 0.01
- **Timeout**: 300 seconds
- **LLM Model**: deepseek/deepseek-chat (OpenRouter)
- **Tools**: retriever.mcp, evaluator.ragas.mcp

### کلاس‌ها و متدهای اصلی

#### کلاس `MCPTool`

- `invoke()`: فراخوانی tool
- `close()`: بستن HTTP client

#### کلاس `AgentOrchestrator`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS و initialize tools
- `start_session()`: شروع agent session
- `execute_agent_loop()`: اجرای agent loop
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /sessions

**Input (Form Data):**

```
query: string          # سوال اولیه (الزامی)
lang: string           # "en" یا "fa" (الزامی)
tenant: string         # tenant ID (الزامی)
user_id: string        # user ID (اختیاری)
token_budget: integer  # بودجه توکن (پیش‌فرض: 4000)
max_steps: integer     # حداکثر گام‌ها (پیش‌فرض: 10)
```

**Output Schema:**

```json
{
  "session_id": "uuid-...",
  "status": "active",
  "trace_id": "00-...",
  "created_at": "2025-10-27T10:30:00Z"
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:8006/sessions" \
  -F "query=What is Python programming?" \
  -F "lang=en" \
  -F "tenant=mycompany" \
  -F "user_id=user123"
```

#### GET /sessions/{session_id}

**Output Schema:**

```json
{
  "session_id": "uuid-...",
  "status": "completed",
  "final_response": "Python is a high-level programming language...",
  "citations": [...],
  "total_cost": 0.0012,
  "created_at": "2025-10-27T10:30:00Z",
  "completed_at": "2025-10-27T10:31:45Z"
}
```

---

# سرویس‌های امنیتی

## 9. Policy Service (Port 8007)

### معرفی سرویس

**Policy** سرویس کنترل دسترسی و policy enforcement است.

### کلاس‌ها و متدهای اصلی

#### کلاس `OPAClient`

- `evaluate_policy()`: ارزیابی policy

#### کلاس `PolicyService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS
- `evaluate()`: پردازش policy evaluation
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /policy/evaluate

**Input (JSON):**

```json
{
  "principal": "user123",
  "action": "read",
  "resource": "document:abc123",
  "context": {"tenant": "mycompany"}
}
```

**Output Schema:**

```json
{
  "decision": "allow",
  "reason": "User has read access"
}
```

---

# سرویس‌های بیلینگ

## 10. Costing Service (Port 8008)

### معرفی سرویس

**Costing** سرویس محاسبه هزینه و budget management است.

### کلاس‌ها و متدهای اصلی

#### کلاس `CostCalculator`

- `calculate_cost()`: محاسبه هزینه

#### کلاس `CostingService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS
- `track_cost()`: ثبت هزینه
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /costing/track

**Input (JSON):**

```json
{
  "tenant": "mycompany",
  "operation": "retrieval",
  "cost": 0.001,
  "metadata": {}
}
```

**Output Schema:**

```json
{
  "total_cost": 0.001,
  "monthly_cost": 12.50,
  "budget_status": "within_budget"
}
```

---

# سرویس‌های تقویت‌کننده

## 11. Pack Service (Port 8009)

### معرفی سرویس

**Pack** سرویس بسته‌بندی context برای مدیریت long contexts است.

### کلاس‌ها و متدهای اصلی

#### کلاس `ContextPacker`

- `pack_contexts()`: بسته‌بندی contexts

#### کلاس `PackLongRAGService`

- `initialize()`: اتصال به PostgreSQL, Redis, miss
- `pack()`: پردازش packing
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /pack

**Input (JSON):**

```json
{
  "query": "What are the features?",
  "contexts": ["context1", "context2"],
  "lang": "en",
  "tenant": "mycompany",
  "max_tokens": 500
}
```

**Output Schema:**

```json
{
  "packs": [
    {
      "chunk_index": 0,
      "content": "packed context...",
      "original_length": 42,
      "packed_length": 40,
      "relevance_score": 0.9
    }
  ],
  "total_tokens": 40,
  "efficiency_ratio": 1.0
}
```

---

## 12. Memory Service (Port 8010)

### معرفی سرویس

**Memory** سرویس مدیریت episodic و semantic memories است.

### کلاس‌ها و متدهای اصلی

#### کلاس `EmbeddingService`

- `get_embedding()`: تولید embedding

#### کلاس `MemoryService`

- `initialize()`: اتصال به PostgreSQL, Redis, NATS و create tables
- `store_memory()`: ذخیره memory
- `search_memories()`: جستجوی memories
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /store

**Input (Query Parameters):**

```
tenant: string       # tenant ID
content: string      # محتوای memory
memory_type: string  # "episodic" یا "semantic"
lang: string         # "en" یا "fa"
user_id: string      # user ID (اختیاری)
session_id: string   # session ID (اختیاری)
```

#### POST /retrieve

**Input (JSON):**

```json
{
  "tenant": "mycompany",
  "query": "What did user ask?",
  "memory_type": "episodic",
  "lang": "en",
  "limit": 5
}
```

**Output Schema:**

```json
{
  "total_found": 3,
  "results": [
    {
      "memory_id": "...",
      "content": "User asked中是 Python",
      "score": 0.92
    }
  ]
}
```

---

## 13. Graph KG Service (Port 8012)

### معرفی سرویس

**Graph KG** سرویس استخراج entities و relationships و query در Neo4j است.

### کلاس‌ها و متدهای اصلی

#### کلاس `EntityExtractor`

- `initialize()`: بارگذاری spaCy model
- `extract_entities()`: استخراج entities
- `extract_relationships()`: استخراج relationships

#### کلاس `KnowledgeGraphService`

- `initialize()`: اتصال به Neo4j
- `extract_and_store()`: پرداز closing and storage
- `query_graph()`: جستجوی graph
- `close()`: بستن تمام اتصالات

### API Endpoints

#### POST /extract

**Input (JSON):**

```json
{
  "doc_id": "knowledge-001",
  "content": "Python was created by Guido van Rossum",
  "tenant": "mycompany",
  "lang": "en"
}
```

**Output Schema:**

```json
{
  "doc_id": "knowledge-001",
  "entities_count": 2,
  "relationships_count": 1,
  "entities": [
    {"entity_id": "...", "label": "Python", "type": "ORG"},
    {"entity_id": "...", "label": "Guido van Rossum", "type": "PERSON"}
  ],
  "relationships": [
    {"from": "Python", "to": "Guido van Rossum", "type": "CREATED_BY"}
  ]
}
```

#### POST /query

**Input (JSON):**

```json
{
  "query": "Python",
  "tenant": "mycompany",
  "limit": 5
}
```

**Output Schema:**

```json
{
  "entities": [
    {"entity_id": "...", "label": "Python", "type": "ORG"}
  ],
  "relationships": [...]
}
```

---

# جریان کامل Pipeline

## ترتیب اجرا

1. **Ingest** → `/ingest` (upload document)
2. **Normalize** → Auto (event-driven)
3. **Chunk** → `/chunk` (manual trigger)
4. **Embed** → `/embed` (manual trigger)
5. **Retrieve** → `/retrieve` (user query)

## مثال کامل

```bash
# 1. Upload
curl -X POST "http://localhost:8000/ingest" -F "doc_id=test" ...

# 2. Wait (5-10 seconds for normalization)

# 3. Chunk
curl -X POST "http://localhost:8003/chunk?..." 

# 4. Embed
curl -X POST "http://localhost:8004/embed?..."

# 5. Wait (3-5 seconds for indexing)

# 6. Retrieve
curl -X POST "http://localhost:8002/retrieve" -d '{...}'
```

---

# راهنمای تست

## Health Checks

```bash
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011 8012; do
  curl http://localhost:$port/health
done
```

## تست کامل

```bash
./test-all-services-complete.sh
```

---

**این مستند کامل تمام 13 سرویس را با جزئیات معماری و عملکرد پوشش می‌دهد!**

