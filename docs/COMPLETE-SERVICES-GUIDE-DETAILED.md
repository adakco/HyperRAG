# راهنمای کامل و دقیق تمام سرویس‌های HyperRAG

**Last Updated:** 2025-10-27  
**Version:** 3.0 - Complete & Detailed  
**Purpose:** توضیح شفاف، دقیق و کامل هر 13 سرویس

---

## 📊 فهرست سرویس‌ها

| # | Service | Port | Type | توضیح مختصر |
|---|---------|------|------|-------------|
| 1 | Ingestor | 8000 | Core | آپلود و ذخیره سند |
| 2 | Normalizer | 8001 | Core | پاکسازی و نرمال‌سازی |
| 3 | Chunker | 8003 | Core | تقسیم به chunks |
| 4 | Embedder | 8004 | Core | تولید embedding |
| 5 | Retriever | 8002 | Core | جستجوی hybrid |
| 6 | Reranker | 8011 | Support | مرتب‌سازی مجدد |
| 7 | Evaluator | 8005 | Support | ارزیابی کیفیت |
| 8 | Agent-Orch | 8006 | Orchestration | هدایت agent |
| 9 | Policy | 8007 | Security | کنترل دسترسی |
| 10 | Costing | 8008 | Billing | محاسبه هزینه |
| 11 | Pack | 8009 | Enhancement | بسته‌بندی context |
| 12 | Memory | 8010 | Enhancement | مدیریت حافظه |
| 13 | Graph KG | 8012 | Enhancement | Knowledge graph |

---

# 1. Ingestor Service (Port 8000)

## معرفی

Ingestor اولین سرویس در pipeline است که فایل‌ها را از کاربر دریافت و در MinIO ذخیره می‌کند.

### معماری

```
Client → POST /ingest → Ingestor → MinIO (Raw) → NATS Event → Normalizer
```

### وظایف

1. دریافت فایل از client
2. تولید version number
3. محاسبه SHA-256 hash
4. ذخیره در MinIO
5. ثبت metadata در PostgreSQL
6. انتشار event

## API Endpoints

### POST /ingest

**Input (Form Data):**

```
doc_id: string      # شناسه سند (الزامی)
tenant: string      # tenant ID (الزامی)
project: string     # project ID (الزامی)
lang: string        # "en" یا "fa" (الزامی)
file: file          # فایل (الزامی)
title: string       # عنوان (اختیاری)
author: string      # نویسنده (اختیاری)
tags: JSON string   # برچسب‌ها (اختیاری)
acl: JSON string    # دسترسی (اختیاری)
```

**Output:**

```json
{
  "doc_id": "python-001",
  "version": 1730123456789,
  "status": "ingested",
  "uri_raw": "s3://raw/tenant/project/doc_id/version",
  "sha256": "a8f5f167...",
  "file_size": 245760,
  "content_type": "application/pdf"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=python-001" \
  -F "tenant=mycompany" \
  -F "project=docs" \
  -F "lang=en" \
  -F "file=@document.pdf"
```

---

# 2. Normalizer Service (Port 8001)

## معرفی

Normalizer سرویس پاکسازی و نرمال‌سازی متن است که به صورت event-driven کار می‌کند.

### معماری

```
NATS Event (doc.ingested.v1) → Normalizer → MinIO (Clean) → NATS Event
```

### وظایف

1. خواندن فایل از MinIO
2. تشخیص زبان
3. حذف PII (presidio)
4. نرمال‌سازی فارسی (hazm)
5. نرمال‌سازی انگلیسی
6. ذخیره نسخه clean

### PII Detection

- Email addresses
- Phone numbers  
- Credit card numbers
- IP addresses
- Names
- Dates

## API Endpoints

### GET /health

```bash
curl http://localhost:8001/health
```

---

# 3. Chunker Service (Port 8003)

## معرفی

Chunker سرویس تقسیم اسناد به chunks برای embedding است.

### معماری

```
API Call → Chunker → PostgreSQL (metadata) + MinIO (chunks)
```

### وظایف

1. خواندن سند clean شده
2. تشخیص زبان
3. تقسیم به chunks
4. محاسبه token count
5. ذخیره در PostgreSQL
6. ذخیره chunks در MinIO

### پارامترهای Chunking

- `chunk_size`: 1000 tokens
- `chunk_overlap`: 200 tokens
- `max_chunk_size`: 2000 tokens
- `min_chunk_size`: 100 tokens

## API Endpoints

### POST /chunk

**Input (Query Parameters):**

```
doc_id: string           # شناسه سند
version: string          # نسخه
uri_clean: string        # URI فایل clean شده
lang: string             # "en" یا "fa"
tenant: string           # tenant ID
```

**Output:**

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

**Example:**

```bash
curl -X POST "http://localhost:8003/chunk?doc_id=python-001&version=1730123456789&uri_clean=s3://raw/tenant/project/python-001/1730123456789/clean&lang=en&tenant=mycompany"
```

---

# 4. Embedder Service (Port 8004)

## معرفی

Embedder سرویس تولید embeddings و ذخیره در Qdrant است.

### معماری

```
API Call → Embedder → Qdrant (vectors) + PostgreSQL (metadata)
```

### وظایف

1. خواندن chunks از MinIO
2. تولید embedding
3. ذخیره در Qdrant
4. ثبت metadata در PostgreSQL

### مدل‌های Embedding

- **Persian**: `paraphrase-multilingual-MiniLM-L12-v2`
- **English**: `all-MiniLM-L6-v2`
- **Dimension**: 384
- **Batch Size**: 32

## API Endpoints

### POST /embed

**Input (Query Parameters):**

```
doc_id: string           # شناسه سند
version: string          # نسخه
uri_processed: string    # URI chunks
lang: string             # "en" یا "fa"
tenant: string           # tenant ID
project: string          # project ID (اختیاری)
```

**Output:**

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

**Example:**

```bash
curl -X POST "http://localhost:8004/embed?doc_id=python-001&version=1730123456789&uri_processed=s3://...&lang=en&tenant=mycompany&project=docs"
```

---

# 5. Retriever Service (Port 8002)

## معرفی

Retriever سرویس جستجوی hybrid (vector + graph) است.

### معماری

```
Query → Retriever → Qdrant (vector) → Neo4j (graph) → Fusion → Results
```

### وظایف

1. دریافت query از user
2. تولید embedding برای query
3. جستجوی vector در Qdrant
4. جستجوی graph در Neo4j (اختیاری)
5. ترکیب نتایج (fusion)
6. بازگرداندن نتایج

### Hybrid Retrieval

- **Vector Weight**: 0.7 (پیش‌فرض)
- **Graph Weight**: 0.3 (پیش‌فرض)
- **Fusion Method**: Weighted score

## API Endpoints

### POST /retrieve

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

**Output:**

```json
{
  "results": [
    {
      "chunk_id": "...",
      "doc_id": "...",
      "content": "...",
      "score": 0.85,
      "rerank_score": 0.88,
      "metadata": {
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

**Example:**

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

# 6. Reranker Service (Port 8011)

## معرفی

Reranker سرویس مرتب‌سازی مجدد نتایج با cross-encoder است.

### معماری

```
Documents + Query → Reranker → Cross-Encoder → Sorted Results
```

### وظایف

1. دریافت documents و query
2. امتیازدهی با cross-encoder
3. مرتب‌سازی براساس score
4. بازگرداندن نتایج

### مدل Reranking

- **Model**: `ms-marco-MiniLM-L-6-v2`
- **Type**: Cross-Encoder

## API Endpoints

### POST /rerank

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

**Output:**

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

# 7. Evaluator Service (Port 8005)

## معرفی

Evaluator سرویس ارزیابی کیفیت RAG responses است.

### معماری

```
Query + Answer + Contexts → Evaluator → Quality Metrics
```

### وظایف

1. دریافت query, answer, contexts
2. محاسبه faithfulness
3. محاسبه answer relevancy
4. محاسبه context precision
5. محاسبه context recall
6. بازگرداندن scores

### Metrics

- **Faithfulness**: آیا answer بر اساس context است؟
- **Answer Relevancy**: آیا answer به query مربوط است؟
- **Context Precision**: آیا contexts مرتبط هستند؟
- **Context Recall**: آیا تمام context های لازم موجود است؟

## API Endpoints

### POST /evaluate

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

**Output:**

```json
{
  "faithfulness": 0.95,
  "answer_relevancy": 0.88,
  "context_precision": 0.92,
  "context_recall": 0.90
}
```

---

# 8. Agent-Orch Service (Port 8006)

## معرفی

Agent-Orch سرویس ارکستراسیون agent workflows به صورت MCP-Native است که agent sessions را مدیریت می‌کند.

### معماری

```
Query → Start Session → Background Processing → MCP Tools → Store Results
```

### وظایف

1. ایجاد agent session
2. اجرای agent loop در background
3. فراخوانی MCP tools (retriever, evaluator)
4. جمع‌آوری و ذخیره نتایج
5. تولید پاسخ نهایی

### پارامترهای پیکربندی

- **Max Steps**: 10
- **Max Cost**: 0.01
- **Timeout**: 300 seconds
- **LLM Model**: deepseek/deepseek-chat (OpenRouter)
- **Tools**: retriever.mcp, evaluator.ragas.mcp

## API Endpoints

### POST /sessions

شروع یک agent session جدید

**Input (Form Data):**

```
query: string          # سوال اولیه (الزامی)
lang: string           # "en" یا "fa" (الزامی)
tenant: string         # tenant ID (الزامی)
user_id: string        # user ID (اختیاری)
token_budget: integer  # بودجه توکن (پیش‌فرض: 4000)
max_steps: integer     # حداکثر گام‌ها (پیش‌فرض: 10)
```

**Output:**

```json
{
  "session_id": "uuid-...",
  "status": "active",
  "trace_id": "00-...",
  "created_at": "2025-10-27T10:30:00Z"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8006/sessions" \
  -F "query=What is Python programming?" \
  -F "lang=en" \
  -F "tenant=mycompany" \
  -F "user_id=user123"
```

### POST /session/start

شروع session با فرمت JSON (برای testing)

**Input (JSON):**

```json
{
  "initial_query": "What is Python?",
  "tenant": "mycompany",
  "user_id": "user123"
}
```

**Output:**

```json
{
  "session_id": "uuid-...",
  "status": "started",
  "message": "Agent session started successfully"
}
```

### GET /sessions/{session_id}

دریافت وضعیت agent session

**Output:**

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

### GET /sessions/{session_id}/steps

دریافت لیست steps یک session

**Output:**

```json
[
  {
    "step_id": "uuid-...",
    "step_number": 1,
    "tool_name": "retriever.mcp",
    "input_data": {"query": "...", "lang": "en"},
    "output_data": {"results": [...]},
    "status": "completed",
    "cost": 0.0001,
    "duration_ms": 234,
    "created_at": "2025-10-27T10:30:01Z",
    "completed_at": "2025-10-27T10:30:01Z"
  }
]
```

---

# 9. Policy Service (Port 8007)

## معرفی

Policy سرویس کنترل دسترسی و policy enforcement است.

### معماری

```
Principal + Action + Resource → Policy → Decision (Allow/Deny)
```

### وظایف

1. دریافت principal, action, resource
2. ارزیابی policy
3. تصمیم‌گیری (allow/deny)
4. ثبت audit log

## API Endpoints

### POST /policy/evaluate

**Input (JSON):**

```json
{
  "principal": "user123",
  "action": "read",
  "resource": "document:abc123",
  "context": {"tenant": "mycompany"}
}
```

**Output:**

```json
{
  "decision": "allow",
  "reason": "User has read access"
}
```

---

# 10. Costing Service (Port 8008)

## معرفی

Costing سرویس محاسبه هزینه و budget management است.

### معماری

```
Operation + Cost → Costing → Tracking + Budget Check
```

### وظایف

1. دریافت cost information
2. ثبت در database
3. بررسی budget
4. ارسال alert در صورت تجاوز

## API Endpoints

### POST /costing/track

**Input (JSON):**

```json
{
  "tenant": "mycompany",
  "operation": "retrieval",
  "cost": 0.001,
  "metadata": {}
}
```

**Output:**

```json
{
  "total_cost": 0.001,
  "monthly_cost": 12.50,
  "budget_status": "within_budget"
}
```

---

# 11. Pack Service (Port 8009)

## معرفی

Pack سرویس بسته‌بندی context برای مدیریت long contexts است.

### معماری

```
Contexts + Query → Pack → Relevance Calculation → Packed Contexts
```

### وظایف

1. دریافت contexts و query
2. محاسبه relevance
3. بسته‌بندی contexts
4. بازگرداندن packed contexts

## API Endpoints

### POST /pack

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

**Output:**

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

# 12. Memory Service (Port 8010)

## معرفی

Memory سرویس مدیریت episodic و semantic memories است.

### معماری

```
Content → Memory → Embedding → PostgreSQL (memories)
Query → Memory → Similarity Search → Retrieved Memories
```

### وظایف

1. ذخیره memory (episodic/semantic)
2. تولید embedding
3. ذخیره در PostgreSQL
4. جستجوی similarity

### انواع Memory

- **Episodic**: خاطرات رویدادها
- **Semantic**: خاطرات دانشی

## API Endpoints

### POST /store

**Input (Query Parameters):**

```
tenant: string       # tenant ID
content: string      # محتوای memory
memory_type: string  # "episodic" یا "semantic"
lang: string         # "en" یا "fa"
user_id: string      # user ID (اختیاری)
session_id: string   # session ID (اختیاری)
```

**Output:**

```json
{
  "memory_id": "uuid...",
  "memory_type": "episodic",
  "tenant": "mycompany",
  "created_at": "2025-10-27T..."
}
```

### POST /retrieve

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

**Output:**

```json
{
  "total_found": 3,
  "results": [
    {
      "memory_id": "...",
      "content": "User asked about Python",
      "score": 0.92
    }
  ]
}
```

---

# 13. Graph KG Service (Port 8012)

## معرفی

Graph KG سرویس استخراج entities و relationships و query در Neo4j است.

### معماری

```
Text → Extract → Entities + Relationships → Neo4j
Query → Neo4j → Entities + Relationships → Results
```

### وظایف

1. استخراج entities (spaCy یا pattern)
2. استخراج relationships
3. ذخیره در Neo4j
4. Query در Neo4j

### Entity Extraction

- **Model**: spaCy (en_core_web_sm)
- **Fallback**: Pattern-based extraction

## API Endpoints

### POST /extract

**Input (JSON):**

```json
{
  "doc_id": "knowledge-001",
  "content": "Python was created by Guido van Rossum",
  "tenant": "mycompany",
  "lang": "en"
}
```

**Output:**

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

### POST /query

**Input (JSON):**

```json
{
  "query": "Python",
  "tenant": "mycompany",
  "limit": 5
}
```

**Output:**

```json
{
  "entities": [
    {"entity_id": "...", "label": "Python", "type": "ORG"}
  ],
  "relationships": [...]
}
```

---

## Pipeline کامل

### Flow Diagram

```
User Upload → Ingestor (8000)
              ↓
         Normalizer (8001) [Auto]
              ↓
         Chunker (8003) [Manual]
              ↓
         Embedder (8004) [Manual]
              ↓
         Retriever (8002) ← User Query
              ↓
         Results
```

### ترتیب اجرا

1. آپلود سند → `/ingest`
2. صبر برای normalization (5-10 ثانیه)
3. Chunking → `/chunk`
4. Embedding → `/embed`
5. صبر برای indexing (3-5 ثانیه)
6. Retrieve → `/retrieve`

---

## Health Checks

```bash
curl http://localhost:8000/health  # Ingestor
curl http://localhost:8001/health  # Normalizer
curl http://localhost:8002/health  # Retriever
curl http://localhost:8003/health  # Chunker
curl http://localhost:8004/health  # Embedder
curl http://localhost:8005/health  # Evaluator
curl http://localhost:8006/health  # Agent-Orch
curl http://localhost:8007/health  # Policy
curl http://localhost:8008/health  # Costing
curl http://localhost:8009/health  # Pack
curl http://localhost:8010/health  # Memory
curl http://localhost:8011/health  # Reranker
curl http://localhost:8012/health  # Graph KG
```

---

## تست کامل سیستم

### اسکریپت تست

```bash
./test-all-services-complete.sh
```

### تست دستی

```bash
# 1. Health checks
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011 8012; do
  curl http://localhost:$port/health
done

# 2. Upload document
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=test-001" \
  -F "tenant=test" \
  -F "project=test" \
  -F "lang=en" \
  -F Spectacle=@test.txt

# 3. Wait and chunk
# 4. Embed
# 5. Retrieve
```

---

**این مستند کامل تمام 13 سرویس را پوشش می‌دهد!**

