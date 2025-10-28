# فاز 2: Long-Context Management - راهنمای پیاده‌سازی

**Last Updated:** 2025-10-26  
**Status:** Under Review - Services Already Implemented

---

## 📊 بررسی وضعیت فعلی

### سرویس‌های موجود

#### 1. Pack Long-RAG Service ✅
- **Location:** `platform/services/pack.longrag/main.py`
- **Port:** 8009
- **Status:** Implemented

**قابلیت‌ها:**
- ✅ Context packing با token budgeting
- ✅ Intelligent summarization
- ✅ Relevance scoring
- ✅ Priority chunk boosting
- ✅ Efficiency calculation

#### 2. Memory Service ✅
- **Location:** `platform/services/memory.memorag/main.py`
- **Port:** 8010
- **Status:** Implemented

**قابلیت‌ها:**
- ✅ Episodic memory storage
- ✅ Semantic memory storage
- ✅ Vector similarity search
- ✅ Access count tracking
- ✅ Memory cleanup (retention policies)

---

## 🎯 معیارهای فاز 2

### از Architecture.md:

**فاز ۲ (Long-Context)**:  
- کاهش ≥ 30% هزینه بدون افت کیفیت
- hit rate بسته ≥ 40%
- بدون افت Faithfulness

---

## 🧪 تست و Validation

### Step 1: Test Pack Long-RAG

```bash
# Test pack service
curl -X POST http://localhost:8009/pack \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "contexts": [
      "Context 1 content...",
      "Context 2 content...",
      "Context 3 content..."
    ],
    "lang": "en",
    "tenant": "test",
    "max_tokens": 2000,
    "include_summaries": true
  }'
```

**Expected Output:**
```json
{
  "query": "test query",
  "packs": [
    {
      "chunk_index": 0,
      "content": "packed content...",
      "is_summary": false,
      "original_length": 1500,
      "packed_length": 1200,
      "relevance_score": 0.85
    }
  ],
  "efficiency_ratio": 0.8,
  "processing_time_ms": 150
}
```

### Step 2: Test Memory Service

```bash
# Store episodic memory
curl -X POST http://localhost:8010/memory \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test",
    "content": "User asked about X",
    "memory_type": "episodic",
    "user_id": "user123",
    "session_id": "sess456"
  }'

# Retrieve memories
curl -X POST http://localhost:8010/memory/search \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "test",
    "query": "What was discussed?",
    "memory_type": "episodic",
    "similarity_threshold": 0.7,
    "max_results": 5
  }'
```

**Expected Output:**
```json
{
  "memories": [
    {
      "memory_id": "uuid",
      "content": "User asked about X",
      "similarity_score": 0.92,
      "access_count": 1
    }
  ],
  "total": 1
}
```

---

## 📋 Integration Checklist

### Pack Long-RAG Integration

- [ ] **Test packing with different contexts**
  - Short contexts (< 500 tokens)
  - Medium contexts (500-2000 tokens)
  - Long contexts (> 2000 tokens)

- [ ] **Verify efficiency ratio**
  - Target: ≥ 70% efficiency (packed/original tokens)
  - Summarization working correctly

- [ ] **Test priority chunks**
  - Priority chunks included first
  - Relevance scoring correct

- [ ] **Performance testing**
  - Latency < 500ms for typical use case
  - Memory usage acceptable

### Memory Service Integration

- [ ] **Test episodic memory**
  - Store conversation context
  - Retrieve based on similarity
  - Access count updates

- [ ] **Test semantic memory**
  - Store general knowledge
  - Cross-session retrieval
  - Cleanup working (30 days retention)

- [ ] **Integration with agent**
  - Agent uses memories in context
  - Memory improves responses
  - No performance degradation

---

## 🔧 Enhancement Opportunities

### 1. Advanced Summarization

**Current:** Basic text summarization  
**Enhancement:** LLM-based summarization with quality preservation

```python
# Enhancement to TextSummarizer
async def summarize_with_llm(self, text: str, max_length: int) -> str:
    """Use LLM for high-quality summarization"""
    prompt = f"Summarize the following text in {max_length} tokens:\n{text}"
    summary = await self.llm_client.generate(prompt, max_tokens=max_length)
    return summary
```

### 2. Smart Caching

**Current:** Basic Redis caching  
**Enhancement:** Intelligent cache with invalidation strategies

```python
# Cache packing results
async def pack_with_cache(self, query: str, contexts: List[str]) -> List[PackResult]:
    cache_key = f"pack:{query}:{hash_contexts(contexts)}"
    
    # Check cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Pack and cache
    packs = self.packer.pack_contexts(query, contexts)
    await redis.setex(cache_key, 3600, json.dumps(packs))
    
    return packs
```

### 3. Memory Consolidation

**Enhancement:** Periodic consolidation of similar memories

```python
async def consolidate_memories(self, tenant: str):
    """Merge similar episodic memories into semantic memories"""
    episodic_memories = await self.get_episodic_memories(tenant)
    
    # Cluster similar memories
    clusters = self.cluster_similar_memories(episodic_memories)
    
    for cluster in clusters:
        # Create semantic memory from cluster
        semantic_content = self.extract_key_concepts(cluster)
        await self.store_semantic_memory(tenant, semantic_content)
```

---

## 📊 Metrics to Track

### Pack Long-RAG Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Efficiency Ratio | ≥ 70% | - |
| Pack Creation Time | < 500ms | - |
| Token Savings | ≥ 30% | - |
| Summary Quality | High | - |

### Memory Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Memory Retrieval Accuracy | ≥ 85% | - |
| Memory Hit Rate | ≥ 40% | - |
| Storage Size | < 1GB per tenant | - |
| Cleanup Success | 100% | - |

---

## 🧪 Test Scenarios

### Scenario 1: Long Document Query

```python
# Given: 10,000 token document
document = load_long_document()  # 10k tokens

# When: Query for specific information
query = "What are the key findings?"

# Then: Pack should reduce to ~2,000 tokens
packs = await pack_service.pack(query, [document], max_tokens=2000)

assert sum(pack.packed_length for pack in packs) <= 2000
assert packs[0].relevance_score > 0.8
```

### Scenario 2: Context Memory

```python
# Given: Previous conversation
await memory_service.store_episodic(
    tenant="user123",
    content="User prefers technical explanations",
    session_id="sess1"
)

# When: New query comes in
query = "Explain how it works"

# Then: Memory should inform response
memories = await memory_service.search(query, similarity_threshold=0.7)
assert len(memories) > 0
assert "technical" in memories[0]['content']
```

### Scenario 3: Cost Reduction

```python
# Measure cost before packing
original_cost = calculate_cost(original_tokens)

# Measure cost after packing
packed_cost = calculate_cost(packed_tokens)

# Verify cost reduction
cost_reduction = (original_cost - packed_cost) / original_cost
assert cost_reduction >= 0.3  # ≥ 30%
```

...+SNIP
