# تصمیم‌های معماری - HyperRAG System

**Date:** 2025-10-27  
**Purpose:** توضیح تصمیم‌های معماری و طراحی

---

## 🤔 چرا همه سرویس‌ها Event-Driven نیستند؟

### پاسخ: طراحی Combined (Event + On-Demand)

#### سرویس‌های Event-Driven (4 سرویس)

**1. Ingestor → Normalizer**
- ✅ **Event-Driven:** Automatic pipeline trigger
- **Dلیل:** Document ingestion باید بلافاصله پردازش شود
- **Event:** `doc.ingested.v1` → `doc.normalized.v1`

**2. Agent-Orch**
- ✅ **Event-Driven:** Workflow orchestration
- **Dلیل:** Need to coordinate multiple tools
- **Events:** Tool completion events, workflow events

**3. Costing**
- ✅ **Event-Driven:** Budget monitoring
- **دلیل:** Real-time budget alerts critical
- **Events:** `budget.alert.v1`

### سرویس‌های On-Demand (9 سرویس)

**Chunker, Embedder, Retriever, Evaluator, etc.**
- ❌ **Not Event-Driven:** Explicit API calls
- **دلایل:**

#### 1. **Control & Flexibility**
```python
# On-demand: کنترل دقیق روی فرآیند
POST /chunk → کنترل وقتی chunking انجام شود
POST /embed → انتخاب دقیق documents برای embedding
POST /retrieve → جستجوی on-demand با query خاص

# Event-driven: کمتر کنترل
Event می‌آید → سرویس به صورت automatic اجرا می‌شود
```

#### 2. **Performance Optimization**
- **Event-driven:** همه documents پردازش می‌شوند
- **On-demand:** فقط documents مورد نیاز پردازش می‌شوند

#### 3. **Error Handling**
- **Event-driven:** اگر event fail شود، نیاز به retry logic پیچیده
- **On-demand:** می‌توانید مستقیماً error handling کنید

#### 4. **User Control**
```bash
# کاربر می‌خواهد فقط یک document خاص را chunk کند
POST /chunk?doc_id=abc123

# با event-driven: همه documents chunk می‌شوند
```

### Architecture Decision: Hybrid Approach

```
Event-Driven Layer:
  Ingestor → Normalizer (Automatic pipeline)
  
On-Demand Layer:
  Chunker, Embedder, Retriever (User-controlled)

Hybrid:
  Agent-Orch: Can trigger on-demand services
  Costing: Monitors events + provides on-demand API
```

**مزایا:**
- ✅ **Flexibility:** کنترل دقیق روی flow
- ✅ **Performance:** پردازش فقط وقتی لازم است
- ✅ **Simplicity:** کمتر complexity در error handling
- ✅ **Scalability:** می‌توان از caching بهینه استفاده کرد

---

## 🔍 چرا از Langfuse استفاده نشده؟

### پاسخ: پلتفرم موجود بود اما integrate نشده

### وضعیت فعلی

**Infrastructure:**
- ✅ Langfuse running on `192.168.2.23:3000`
- ✅ Environment variable configured: `LANGFUSE_HOST`
- ❌ Services NOT calling it yet

### دلایل عدم استفاده

#### 1. **Focus on Core Features**
در Phase 1-3 تمرکز روی core functionality بود:
- RAG pipeline
- Vector search
- Knowledge graph
- Long-context management

**Observability با OTEL + Prometheus + Grafana کافی بود.**

#### 2. **Langfuse برای LLM Tracking است**
Langfuse برای tracking LLM calls طراحی شده:
- Input/output tracking
- Token usage
- Quality metrics
- User feedback

**در حال حاضر:**
- Retriever از LLM استفاده نمی‌کند (فقط vector search)
- Embedder از local models استفاده می‌کند (sentence-transformers)
- No LLM calls currently happening

#### 3. **Alternative: OTEL + Prometheus**
ما از OpenTelemetry استفاده می‌کنیم که:
- ✅ Distributed tracing
- ✅ Metrics collection
- ✅ Service graph
- ✅ Complete observability

**این tools کافی هستند برای current use case.**

### چه زمانی Langfuse مفید است؟

**برای Production با LLM:**

```python
# Example: Retriever with LLM

from langfuse import Langfuse

langfuse = Langfuse(
    secret_key="sk-...",
    public_key="pk-...",
    host="http://192.168.2.23:3000"
)

async def retrieve_with_llm(query):
    # Track retrieval
    retrieval_span = langfuse.generation(
        name="retrieval",
        input=query,
        model="text-embedding-3-large"
    )
    
    # Do retrieval
    results = await retriever.retrieve(query)
    
    # Track results
    retrieval_span.end(output=results)
    
    return results
```

### چگونه اضافه کنیم؟

**Step 1: Install**
```bash
pip install langfuse
```

**Step 2: Add to Retriever Service**
```python
# platform/services/retriever/main.py

from langfuse import Langfuse

class RetrieverService:
    def __init__(self):
        self.langfuse = Langfuse(
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            host=os.getenv("LANGFUSE_HOST")
        )
    
    async def retrieve(self, request):
        # Track with Langfuse
        span = self.langfuse.generation(
            name="retrieval",
            input={"query": request.query, "lang": request.lang}
        )
        
        # Do retrieval
        result = await self._retrieve_internal(request)
        
        # Track output
        span.end(output=result)
        
        return result
```

**Step 3: Track Quality Metrics**
```python
# Track with evaluator
evaluator_span = langfuse.generation(
    name="quality_evaluation",
    input={"query": query, "results": results}
)

quality_score = await evaluator.evaluate(results)

evaluator_span.end(
    output=quality_score,
    metadata={"faithfulness": 0.9, "relevance": 0.85}
)
```

---

## 📊 مقایسه رویکردها

### Event-Driven vs On-Demand

| Aspect | Event-Driven | On-Demand | Hybrid (Current) |
|--------|-------------|-----------|------------------|
| **Control** | Low | High | High |
| **Performance** | Processes all | Processes needed | Optimal |
| **Error Handling** | Complex | Simple | Flexible |
| **Scalability** | Auto-scale | Manual | Balanced |
| **Use Case** | Automation | User control | Best of both |

### Observability Stack

| Tool | Purpose | Status |
|------|---------|--------|
| **OTEL** | Distributed tracing | ✅ Implemented |
| **Prometheus** | Metrics | ✅ Implemented |
| **Grafana** | Visualization | ✅ Implemented |
| **Langfuse** | LLM tracking | ⏳ Not needed yet |

---

## 🎯 توصیه‌ها

### 1. Event-Driven Expansion

**اگر می‌خواهید event-driven اضافه کنید:**

```python
# Example: Make Chunker event-driven

# In normalizer/main.py
await self.nats_client.publish("doc.normalized.v1", event_data)

# In chunker/main.py
async def start_nats_listener(self):
    await self.nats_client.subscribe(
        "doc.normalized.v1",
        cb=self.handle_document_normalized
    )

async def handle_document_normalized(self, msg):
    event_data = json.loads(msg.data.decode())
    doc_id = event_data["data"]["doc_id"]
    
    # Auto-chunk
    await self.chunk_document(doc_id, ...)
```

### 2. Langfuse Integration

**اگر LLM به سیستم اضافه کنید:**

```python
# Add Langfuse tracking to:
- Retriever: Track retrieval queries
- Embedder: Track embedding generation  
- Evaluator: Track quality metrics
- Agent-Orch: Track agent workflows
```

**Estimated Time:** 2-3 hours per service

---

## 💡 نتیجه‌گیری

### چرا این رویکرد؟

1. **Flexibility:** ترکیب event-driven و on-demand
2. **Performance:** پردازش فقط وقتی لازم است
3. **Simplicity:** کمتر complexity در طراحی
4. **Scalability:** آماده برای expansion

### چرا Langfuse اضافه نشده؟

1. **Not needed:** فعلاً LLM calls نداریم
2. **OTEL sufficient:** observability کامل است
3. **Can be added:** infrastructure آماده است

### وقتی نیاز است اضافه شود؟

- **Event-driven:** اگر نیاز به fully automatic pipeline دارید
- **Langfuse:** اگر LLM به سیستم اضافه کنید

---

**Status: Current architecture is production-ready and optimal for use case!** ✅

