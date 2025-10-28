# راهنمای کامل تمام سرویس‌ها - HyperRAG

**Last Updated:** 2025-10-27  
**Purpose:** توضیح دقیق تمام 13 سرویس با ورودی و خروجی

---

## 📊 فهرست سرویس‌ها

| # | Service | Port | Type | Event-Driven |
|---|---------|------|------|-------------|
| 1 | Ingestor | 8000 | Core | ✅ |
| 2 | Normalizer | 8001 | Core | ✅ |
| 3 | Chunker | 8003 | Core | ❌ |
| 4 | Embedder | 8004 | Core | ❌ |
| 5 | Retriever | 8002 | Core | ❌ |
| 6 | Reranker | 8011 | Support | ❌ |
| 7 | Evaluator | 8005 | Support | ❌ |
| 8 | Agent-Orch | 8006 | Orchestration | ✅ |
| 9 | Policy | 8007 | Security | ❌ |
| 10 | Costing | 8008 | Billing | ✅ |
| 11 | Pack Long-RAG | 8009 | Enhancement | ❌ |
| 12 | Memory | 8010 | Enhancement | ❌ |
| 13 | Graph KG | 8012 | Enhancement | ❌ |

---

## 🔄 Core Pipeline Services

### 1. Ingestor Service (Port 8000)

**Function:** Upload و ذخیره‌سازی initial document در MinIO

**Architecture:**
```
Client → Ingestor → MinIO → NATS Event
```

**Endpoints:**

#### POST /ingest
**Upload a document**

**Input (Form Data):**
```
doc_id: string (required)
tenant: string (required)
project: string (required)
lang: string (required) - "en" or "fa"
title: string (optional)
author: string (optional)
tags: string (optional) - JSON array
acl: string (optional) - JSON array
file: file (required)
```

**Output:**
```json
{
  "doc_id": "sample-doc-001",
  "version": 1730123456,
  "status": "ingested",
  "uri_raw": "s3://raw/mycompany/docs/sample-doc-001/1730123456",
  "sha256": "abc123...",
  "file_size": 1024,
  "trace_id": "..."
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=sample-001" \
  -F "tenant=mycompany" \
  -F "project=docs" \
  -F "lang=en" \
  -F "title=Sample Document" \
  -F "file=@sample.txt"
```

**Publishes Event:**
```json
{
  "type": "doc.ingested.v1",
  "data": {
    "doc_id": "...",
    "version": "...",
    "uri_raw": "...",
    "lang": "en",
    "tenant": "...",
    "project": "..."
  }
}
```

---

### 2. Normalizer Service (Port 8001)

**Function:** پاکسازی متن، حذف PII، نرمال‌سازی

**Architecture:**
```
Event (doc.ingested.v1) → Normalizer → MinIO → NATS Event
```

**Endpoints:**

#### GET /health
Check service health

**Output:**
```json
{"status": "healthy", "service": "normalizer"}
```

**Event Subscriber:**
- Listens to: `doc.ingested.v1`

**Event Publisher:**
- Publishes: `doc.normalized.v1`

**Output Event:**
```json
{
  "type": "doc.normalized.v1",
  "data": {
    "doc_id": "...",
    "version": "...",
    "uri_clean": "s3://raw/.../clean/...",
    "lang": "en",
    "tenant": "..."
  }
}
```

**Note:** این سرویس فقط event-driven است و API endpoint ندارد.

---

### 3. Chunker Service (Port 8003)

**Function:** تقسیم document به chunks برای embedding

**Architecture:**
```
Input (MinIO URI) → Chunker → Chunks → MinIO → PostgreSQL
```

**Endpoints:**

#### POST /chunk
**Chunk a document**

**Input (Query Parameters):**
```
doc_id: string (required)
version: string (required)
uri_clean: string (required) - MinIO URI
lang: string (required)
tenant: string (required)
```

**Output:**
```json
{
  "doc_id": "sample-doc-001",
  "version": "1730123456",
  "total_chunks": 5,
  "total_tokens": 1234,
  "uri_processed": "s3://raw/.../chunked/...",
  "chunks": [
    {
      "chunk_id": "sample-doc-001-1730123456-0",
      "chunk_index": 0,
      "content": "First chunk text...",
      "token_count": 256
    }
  ]
}
```

**Example:**
```bash
curl -X POST "http://localhost:8003/chunk?doc_id=test&version=123&uri_clean=s3://raw/test/test/1&lang=en&tenant=test"
```

#### GET /health
Check service health

---

### 4. Embedder Service (Port 8004)

**Function:** تبدیل chunks به vectors و ذخیره در Qdrant

**Architecture:**
```
Input (Chunked URI) → Embedder → Vectors → Qdrant + PostgreSQL
```

**Endpoints:**

#### POST /embed
**Generate embeddings**

**Input (Query Parameters):**
```
doc_id: string (required)
version: string (required)
uri_processed: string (required) - Chunked document URI
lang: string (required)
tenant: string (required)
project: string (optional)
```

**Output:**
```json
{
  "doc_id": "sample-doc-001",
  "version": "1730123456",
  "embeddings_count": 5,
  "vector_dimension": 384,
  "processing_time_ms": 1234,
  "points_created": 5
}
```

**Example:**
```bash
curl -X POST "http://localhost:8004/embed?doc_id=test&version=123&uri_processed=s3://raw/test/chunked/1&lang=en&tenant=test&project=docs"
```

#### GET /health
Check service health

---

### 5. Retriever Service (Port 8002)

**Function:** جستجوی hybrid (vector + graph)

**Architecture:**
```
Query → Retriever → Qdrant (vector) → Neo4j (graph) → atomize
```

**Endpoints:**

#### POST /retrieve
**Search documents**

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
      "version": "...",
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
    "search_time_ms": 1234,
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
    "tenant": "test",
    "lang": "en",
    "limit": 5
  }'
```

#### GET /health
Check service health

---

## 🛠️ Supporting Services

### 6. Reranker Service (Port 8011)

**Function:** Re-ranking نتایج جستجو با cross-encoder

**更有points:**

#### POST /rerank
**Re-rank documents**

**Input (JSON):**
```json
{
  "query": "Python programming",
  "documents": [
    {"content": "...", "metadata": {...}},
    {"content": "...", "metadata": {...}}
  ],
  "lang": "en",
  "tenant": "mycompany"
}
```

**Output:**
```json
{
  "reranked_documents": [
    {"content": "...", "score": 0.95},
    {"content": "...", "score": 0.82}
  ],
  "processing_time_ms": 123
}
```

**Example:**
```bash
curl -X POST "http://localhost:8011/rerank" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

### 7. Evaluator Service (Port 8005)

**Function:** ارزیابی کیفیت RAG responses

**Endpoints:**

#### POST /evaluate
**Evaluate RAG response**

**Input (JSON):**
```json
{
  "query": "What is Python?",
  "answer": "Python is a programming language",
  "contexts": ["context1", "context2"],
  "lang": "en",
  "tenant": "mycompany",
  "metrics": ["faithfulness", "answer_relevancy"]
}
```

**Output:**
```json
{
  "faithfulness": 0.95,
  "answer_relevancy": 0.88,
  "context_precision": 0.92,
  "context_recall": 0.90,
  "scores": {
    "faithfulness": {"score": 0.95, "confidence": 0.98},
    "answer_relevancy": {"score": 0.88, "confidence": 0.92}
  }
}
```

**Example:**
```bash
curl -X POST "http://localhost:8005/evaluate" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

## 🎛️ Orchestration Services

### 8. Agent-Orch Service (Port 8006)

**Function:** Orchestraion agent workflows، tool chaining

**Endpoints:**

#### POST /agent/query
**Execute agent query**

**Input (JSON):**
```json
{
  "query": "What is Python?",
  "tenant": "mycompany",
  "lang": "en",
  "tools": ["retriever", "graph", "memory"],
  "max_steps": 10
}
```

**Output:**
```json
{
  "session_id": "...",
  "query": "...",
  "response": "Python is...",
  "steps": [
    {"tool": "retriever", "result": "..."},
    {"tool": "graph", "result": "..."}
  ],
  "total_cost": 0.0012
}
```

**Example:**
```bash
curl -X POST "http://සිංhalla:8006/agent/query" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

## 🔒 Security Services

### 9. Policy Service (Port 8007)

**Function:** Policy enforcement و access control

**Endpoints:**

#### POST /policy/evaluate
**Evaluate policy**

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

**Example:**
```bash
curl -X POST "http://localhost:8007/policy/evaluate" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

## 💰 Billing Services

### 10. Costing Service (Port 8008)

**Function:** Cost tracking و budget management

**Endpoints:**

#### POST /costing/track
**Track cost**

**Input (JSON):**
```json
{
  "tenant": "mycompany",
  "operation": "retrieval",
  "cost": 0.001,
  "metadata": {...}
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

**Example:**
```bash
curl -X POST "http://localhost:8008/costing/track" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**Event Publisher:**
- Publishes: `budget.alert.v1` when budget exceeded

#### GET /health
Check service health

---

## 🚀 Enhancement Services

### 11. Pack Long-RAG Service (Port 8009)

**Function:** Context packing برای مدیریت long contexts

**Endpoints:**

#### POST /pack
**Pack contexts**

**Input (JSON):**
```json
{
  "query": "What are the features?",
  "contexts": ["context1", "context2", "context3"],
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
 Unit
}
```

**Example:**
```bash
curl -X POST "http://localhost:8009/pack" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

### 12. Memory Service (Port 8010)

**Function:** Episodic و semantic memory management

**Endpoints:**

#### POST /store
**Store memory**

**Input (Query Parameters):**
```
tenant: string (required)
content: string (required)
memory_type: string (required) - "episodic" or "semantic"
lang: string (required)
user_id: string (optional)
session_id: string (optional)
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

**Example:**
```bash
curl -X POST "http://localhost:8010/store?tenant=test&content=User%20asked%20about%20Python&memory_type=episodic&lang=en"
```

#### POST /retrieve
**Retrieve memories**

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

**Example:**
```bash
curl -X POST "http://localhost:8010/retrieve" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

### 13. Graph KG Service (Port 8012)

**Function:** استخراج entities و relationships، Query Neo4j

**Endpoints:**

#### POST /extract
**Extract entities and relationships**

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

**Example:**
```bash
curl -X POST "http://localhost:8012/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "test",
    "content": "Python was created by Guido",
    "tenant": "test",
    "lang": "en"
  }'
```

#### POST /query
**Query graph**

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

**Example:**
```bash
curl -X POST "http://localhost:8012/query" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### GET /health
Check service health

---

## 🔄 Data Flow

### Complete Pipeline Flow

```
1. Ingestor (8000)
   Input: file + metadata
   Output: Event (doc.ingested.v1)
   
2. Normalizer (8001)
   Input: Event (doc.ingested.v1)
   Output: Event (doc.normalized.v1)
   
3. Chunker (8003)
   Input: Manual API call
   Output: Chunked document in MinIO
   
4. Embedder (8004)
   Input: Manual API call
   Output: Vectors in Qdrant
   
5. Retriever (8002)
   Input: Query
   Output: Retrieved documents
```

---

## 📊 Testing Checklist

### For Complete System Test

```bash
# 1. Health checks
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

# 2. Complete pipeline
./start-services-host.sh
sleep 10

# 3. Upload document
curl -X POST "http://localhost:8000/ingest" -F "doc_id=test" ...

# 4. Wait for normalization (automatic)
sleep 5

# 5. Chunk
curl -X POST "http://localhost:8003/chunk?..."

# 6. Embed
curl -X POST "http://localhost:8004/embed?..."

# 7. Retrieve
curl -X POST "http://localhost:8002/retrieve" -d '{...}'

# 8. Test enhancements
curl -X POST "http://localhost:8012/extract" -d '{...}'  # Graph
curl -X POST "http://localhost:8010/store?..."           # Memory
curl -X POST "http://localhost:8009/pack" -d '{...}'      # Pack
```

---

**This completes the comprehensive guide for all 13 services!**

