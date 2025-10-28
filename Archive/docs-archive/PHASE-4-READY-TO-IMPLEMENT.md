# Phase 4: Hybrid Retrieval - Ready to Implement

**Date:** 2025-10-27  
**Status:** Design Complete, Ready for Implementation  
**Priority:** High

---

## 🎯 هدف

پیاده‌سازی **Hybrid Retrieval** که ترکیبی از:
- ✅ Vector Search (Qdrant) - فعلاً موجود
- ⏳ Graph Search (Neo4j) - باید اضافه شود
- ⏳ Result Fusion - باید پیاده‌سازی شود

---

## 📊 Current State

### What Exists ✅
1. **Vector Search (Qdrant)**
   - Working perfectly
   - Persian & English support
   - RRF implementation
   - Re-ranking (basic)

2. **Graph Knowledge (Neo4j)**
   - Service implemented (port 8012)
   - Entity/relationship extraction
   - Graph storage
   - Query capabilities

### What's Missing ⏳
1. **Graph Query Integration**
   - Query Neo4j from Retriever service
   - Extract relevant entities from query
   - Find related documents via graph

2. **Result Fusion**
   - Combine vector + graph results
   - Weighted scoring
   - Deduplication

3. **Quality Testing**
   - Test hybrid vs vector-only
   - Measure improvement

---

## 🔧 Implementation Plan

### Step 1: Graph Query Integration

**File:** `platform/services/retriever/main.py`

Add Neo4j integration:

```python
class RetrieverService:
    def __init__(self, settings: pocSettings):
        # ... existing code ...
        self.neo4j_driver = None  # NEW
        self.neo4j_uri = "bolt://192.168.2.23:7687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "Adakpro123"
        
    async def initialize(self):
        # ... existing code ...
        # NEW: Initialize Neo4j
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )
```

### Step 2: Add Graph Query Method

```python
async def query_graph_knowledge(
    self, 
    query: str, 
    tenant: str, 
    limit: int = 5
) -> List[Dict]:
    """Query Neo4j knowledge graph"""
    
    if not self.neo4j_driver:
        return []
    
    try:
        with self.neo4j_driver.session() as session:
            # Extract entities from query text
            # Simple implementation: search entities by label
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.tenant = $tenant
                AND toLower(e.label) CONTAINS toLower($query)
                OPTIONAL MATCH (e)-[r]->(related:Entity)
                RETURN e, collect(related) as related_entities
                LIMIT $limit
                """,
                tenant=tenant,
                query=query,
                limit=limit
            )
            
            results = []
            for record in result:
                entity = record['e']
                related = record['related_entities']
                
                results.append({
                    'type': 'graph',
                    'entity_id': entity.get('entity_id'),
                    'label': entity.get('label'),
                    'related': [r.get('label') for r in related],
                    'score': 0.8  # Graph relevance score
                })
            
            return results
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        return []
```

### Step 3: Modify Retrieve Method

Update `retrieve` method to support hybrid search:

```python
async def retrieve(
    self,
    request: RetrievalRequest
) -> RetrievalResponse:
    
    # ... existing vector search code ...
    vector_results = await self._vector_search(...)
    
    # NEW: Graph search if enabled
    graph_results = []
    if request.use_graph:  # Add this flag to RetrievalRequest
        graph_results = await self.query_graph_knowledge(
            query=request.query,
            tenant=request.tenant,
            limit=request.limit
        )
    
    # NEW: Fusion
    if graph_results:
        fused_results = self._fuse_results(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=0.7,
            graph_weight=0.3
        )
    else:
        fused_results = vector_results
    
    return fused_results
```

### Step 4: Implement Result Fusion

```python
def _fuse_results(
    self,
    vector_results: List[Dict],
    graph_results: List[Dict],
    vector_weight: float = 0.7,
    graph_weight: float = 0.3
) -> List[Dict]:
    """Fuse vector and graph results"""
    
    # Create a combined result set
    fused = {}
    
    # Add vector results
    for i, result in enumerate(vector_results):
        doc_id = result.get('doc_id')
        base_score = result.get('score', 0)
        fused[doc_id] = {
            'doc_id': doc_id,
            'content': result.get('content'),
            'score': base_score * vector_weight,
            'vector_score': base_score,
            'graph_score': 0,
            'type': 'vector'
        }
    
    # Add graph results
    for result in graph_results:
        entity_id = result.get('entity_id')
        # Try to link graph entity to document
        # This could be via relationships or metadata
        doc_id = self._get_doc_id_from_entity(entity_id)
        
        if doc_id in fused:
            # Boost existing vector result
            fused[doc_id]['graph_score'] = result.get('score', 0)
            fused[doc_id]['score'] += result.get('score', 0) * graph_weight
        else:
            # New result from graph
            fused[entity_id] = {
                'doc_id': entity_id,
                'content': result.get('label'),
                'score': result.get('score', 0) * graph_weight,
                'vector_score': 0,
                'graph_score': result.get('score', 0),
                'type': 'graph'
            }
    
    # Sort by final score
    return sorted(fused.values(), key=lambda x: x['score'], reverse=True)

def _get_doc_id_from_entity(self, entity_id: str) -> Optional[str]:
    """Get document ID from entity (implementation needed)"""
    # Query Neo4j for doc_id linked to entity
    try:
        with self.neo4j_driver.session() as session:
            result = session.run(
                "MATCH (e:Entity {entity_id: $entity_id}) RETURN e.doc_id as doc_id",
                entity_id=entity_id
            )
            record = result.single()
            return record['doc_id'] if record else None
    except:
        return None
```

### Step 5: Update API Model

```python
class RetrievalRequest(BaseModel):
    # ... existing fields ...
    use_graph: bool = False  # NEW: Enable graph search
    vector_weight: float = 0.7  # NEW: Weight for vector results
    graph_weight: float = 0.3  # NEW: Weight for graph results
```

---

## 🧪 Testing Plan

### Test 1: Graph-Only Search
```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What entities are related to Python?",
    "use_graph": true,
    "limit": 5
  }'
```

### Test 2: Hybrid Search
```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python programming",
    "use_graph": true,
    "vector_weight": 0.7,
    "graph_weight": 0.3,
    "limit": 5
  }'
```

### Test 3: Compare Results
```python
# Vector only
results_vector = retrieve(query, use_graph=False)

# Hybrid
results_hybrid = retrieve(query, use_graph=True)

# Compare quality
compare_quality(results_vector, results_hybrid)
```

---

## 📊 Expected Benefits

### 1. Better Context Understanding
- Entity relationships
- Multi-hop queries
- Contextual relevance

### 2. Improved Quality
- More accurate results
- Better ranking
- Richer context

### 3. Advanced Features
- "Who worked with X?"
- "What projects use Y?"
- Relationship queries

---

## 🎯 Success Criteria

| Metric | Target | How to Measure |
|--------|--------|---------------|
| Hybrid Quality | > Vector-only | Manual review |
| Response Time | <3s | Metrics |
| Graph Query Success | >90% | Test suite |
| Fusion Accuracy | High relevance | A/B testing |

---

## 📝 Next Steps

1. **Implement Graph Query Integration** (4-6 hours)
2. **Implement Result Fusion** (2-3 hours)
3. **Update API and Models** (1-2 hours)
4. **Create Tests** (2-3 hours)
5. **Documentation** (1 hour)

**Total Estimated Time:** 10-15 hours

---

## 💡 Notes

- Start with simple graph queries
- Gradually add complexity
- Test thoroughly before production
- Monitor performance impact

---

**Status:** Ready for implementation when needed  
**Priority:** Can be done in Phase 5 if more urgent features are needed  
**Impact:** Significant quality improvement for complex queries

