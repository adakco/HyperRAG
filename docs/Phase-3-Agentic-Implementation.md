# فاز 3: Agentic Features - راهنمای پیاده‌سازی

**Last Updated:** 2025-10-26  
**Status:** Ready to Start  
**Owner:** Chief Architect

---

## 📊 نمای کلی فازهای پروژه

```
┌──────────────────────────────────────────────┐
│          فاز 1: RAG حرفه‌ای                   │
│  ✅ تکمیل شده                                │
│  - Hybrid search (Qdrant)                   │
│  - Multi-language (Fa/En)                   │
│  - Complete pipeline                        │
└──────────────────────────────────────────────┘
                    ↓
┌─────.ژساخص    ─────────────────────────────────────────┐
│       فاز 2: Long-Context Management         │
│  🔄 در حال تکمیل                              │
│  - Memory systems                           │
│  - Context packing                          │
│  - Advanced caching                          │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│           فاز 3: Agentic Features             │
│  ⏳ برنامه‌ریزی شده                          │
│  - Knowledge Graph (Neo4j)                   │
│  - Advanced Agent Orchestration             │
│  - Decision Loops                            │
└──────────────────────────────────────────────┘
```

---

## 🎯 فاز 3: Agentic Features - اهداف

### معیارهای موفقیت

| Metric | Target | Status |
|--------|--------|--------|
| Agent Success Rate | ≥ 80% | ⏳ |
| Citation Alignment | ≥ 98% | ⏳ |
| Budget Overflow | 0 | ⏳ |
| Resilience Tests | Passed | ⏳ |

### قابلیت‌های موردنیاز

1. **Knowledge Graph Integration** (Neo4j)
   - Entity extraction و relationships
   - Graph-based reasoning
   - Multi-hop queries

2. **Advanced Agent Orchestration**
   - LangGraph/Temporal integration
   - Decision-making loops
   - Tool chaining

3. **Complex Query Handling**
   - Multi-step reasoning
   - Query decomposition
   - Result synthesis

---

## 📋 چک‌لیست اقدامات فاز 3

### مرحله 1: Neo4j Knowledge Graph (هفته 1-2)

#### گام 1.1: راه‌اندازی Neo4j

```bash
# Add to docker-compose.yml on server
services:
  neo4j:
    image: neo4j:5.23
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/Adakpro123
      - NEO4J_dbms_memory_heap_max__size=2G
    volumes:
      - neo4j_data:/data
```

**چک‌لیست:**
- [ ] Neo4j container running
- [ ] Ports 7474 و 7687 accessible
- [ ] Web UI accessible
- [ ] Test connection successful

#### گام 1.2: ایجاد Service `graph.kg`

```python
# platform/services/graph.kg/main.py
"""
Knowledge Graph Service
Extracts entities and relationships from documents
"""

from neo4j import GraphDatabase
from typing import List, Dict

class KnowledgeGraphService:
    def __init__(self, neo4j_url: str):
        self.driver = GraphDatabase.driver(neo4j_url)
    
    async def extract_entities(self, text: str, lang: str) -> List[Dict]:
        """Extract entities from text"""
        # Use NER model based on language
        pass
    
    async def extract_relationships(self, text: str) -> List[Dict]:
        """Extract relationships between entities"""
        pass
    
    async def store_knowledge(self, entities: List[Dict], relationships: List[Dict]):
        """Store in Neo4j"""
        pass
```

**چک‌لیست:**
- [ ] Service created
- [ ] Entity extraction working
- [ ] Relationship extraction working
- [ ] Neo4j storage working

#### گام 1.3: Integration با Pipeline

```python
# در embedder یا بعد از chunker
async def process_with_kg(doc_id, chunks):
    for chunk in chunks:
        # Extract entities
        entities = await kg_service.extract_entities(chunk['content'])
        
        # Extract relationships
        relationships = await kg_service.extract_relationships(chunk['content'])
        
        # Store in Neo4j
        await kg_service.store_knowledge(entities, relationships)
```

**چک‌لیست:**
- [ ] KG extraction در pipeline
- [ ] Data در Neo4j ذخیره می‌شود
- [ ] Query در Neo4j کار می‌کند

---

### مرحله 2: Advanced Agent Orchestration (هفته 3-4)

#### گام 2.1: تکمیل Agent Orchestrator

```python
# platform/services/agent-orch/main.py
# اضافه کردن قابلیت‌های زیر:

class AgentOrchestrator:
    async def execute_with_decision_loops(self, query: str):
        """Agent with decision-making loops"""
        # 1. Initial retrieval
        results = await retrieve_tool(query)
        
        # 2. Quality check
        quality = await evaluate_tool(results)
        
        # 3. Decision: Enough information?
        if quality['score'] < 0.8:
            # Refine query and retry
            refined_query = await refine_query(query, results)
            results = await retrieve_tool(refined_query)
        
        # 4. Final answer
        return await generate_answer(results)
```

**چک‌لیست:**
- [ ] Decision loops implemented
- [ ] Quality gates working
- [ ] Query refinement working
- [ ] Budget enforcement working

#### گام 2.2: Tool Chaining

```python
async def chain_tools(tools: List[str], query: str):
    """Chain multiple tools together"""
    context = {}
    
    for tool_name in tools:
        tool = get_tool(tool_name)
        result = await tool.invoke(context, query)
        context.update(result)
    
    return context
```

**چک‌لیست:**
- [ ] Tool chaining implemented
- [ ] Context passed between tools
- [ ] Error handling in place
- [ ] Retry logic working

---

### مرحله 3: Hybrid Retrieval با Graph (هفته 5-6)

#### گام 3.1: پیاده‌سازی Hybrid Retriever با Graph

```python
class HybridRetrieverWithGraph:
    async def retrieve_hybrid(self, query: str):
        # 1. Vector search
        vector_results = await qdrant.search(query)
        
        # 2. Graph search (Neo4j)
        graph_results = await neo4j.query(query)
        
        # 3. Fusion
        combined = reciprocal_rank_fusion(
            vector_results,
            graph_results
        )
        
        # 4. Re-rank
        final_results = await rerank(combined)
        
        return final_results
```

**چک‌لیست:**
- [ ] Vector + Graph search working
- [ ] Fusion algorithm implemented
- [ ] Re-ranking with combined results
- [ ] Performance acceptable (< 2s p95)

#### گام 3.2: Query Expansion با Graph

```python
async def expand_query_with_graph(query: str):
    """Expand query using knowledge graph"""
    # 1. Find related concepts in graph
    related_concepts = await neo4j.find_related(query)
    
    # 2. Expand query
    expanded_query = f"{query} {related_concepts}"
    
    return expanded_query
```

**چک‌لیست:**
- [ ] Query expansion working
- [ ] Related concepts found
- [ ] Accuracy improvement
- [ ] Recall improvement

---

## 🔧 تست‌ها و Validation

### تست 1: Agent Success Rate

```python
# Test agent completes tasks successfully
test_cases = [
    {"query": "What is the relationship between A and B?"},
    {"query": "Find all documents about X and Y"},
    {"query": "Explain the connection between concepts C and D"}
]

for test in test_cases:
    result = await agent.execute(test['query'])
    assert result['success'] == True
    assert result['citations'] is not None
```

**معیار:** ≥ 80% success rate

### تست 2: Citation Alignment

```python
# Test citations are accurate
for test in test_cases:
    result = await agent.execute(test['query'])
    citations = result['citations']
    
    # Verify citations support the answer
    for citation in citations:
        assert citation['relevance'] > 0.8
```

**معیار:** ≥ 98% alignment

### تست 3: Budget Management

```python
# Test budget enforcement
budget = 4000  # tokens
result = await agent.execute(query, token_budget=budget)

assert result['tokens_used'] <= budget
assert result['budget_exceeded'] == False
```

**معیار:** No budget overflow

### تست 4: Resilience

```python
# Chaos testing
# - Simulate tool failures
# - Simulate network delays
# - Simulate slow responses

# Agent should handle gracefully
for failure in simulated_failures:
    result = await agent.execute(query)
    assert result['status'] in ['success', 'partial', 'error']
    # Never crashes
```

**معیار:** Passes all resilience tests

---

## 📊 Metrics Dashboard

### Panel 1: Agent Performance

```promql
# Success rate
sum(rate(hyperrag_agent_success_total[5m])) / sum(rate(hyperrag_agent_total[5m]))

# Average token usage
avg(hyperrag_agent_tokens_used)

# Budget adherence
1 - (sum(rate(hyperrag_agent_budget_exceeded_total[5m])) / sum(rate(hyperrag_agent_total[5m])))
```

### Panel 2: Knowledge Graph Usage

```promql
# Graph queries
rate(hyperrag_graph_queries_total[5m])

# Entity extraction
rate(hyperrag_entity_extraction_total[5m])

# Relationship extraction
rate(hyperrag_relationship_extraction_total[5m])
```

### Panel 3: Hybrid Retrieval

```promql
# Vector vs Graph results
sum(hyperrag_retrieval_source) by (source)

# Fusion performance
histogram_quantile(0.95, hyperrag_fusion_duration_seconds_bucket)
```

---

## 🚀 Deployment Plan

### هفته 1-2: Knowledge Graph

```bash
# 1. Deploy Neo4j
docker-compose up -d neo4j

# 2. Create graph.kg service
# 3. Integrate with pipeline
# 4. Test entity/relationship extraction
```

### هفته 3-4: Agent Orchestration

```bash
# 1. Enhance agent-orch service
# 2. Add decision loops
# 3. Add tool chaining
# 4. Test agent workflows
```

### هفته 5-6: Hybrid Retrieval

```bash
# 1. Implement hybrid retriever
# 2. Test fusion algorithm
# 3. Optimize performance
# 4. Deploy to production
```

---

## ✅ Definition of Done

فاز 3 زمانی تکمیل می‌شود که:

- [x] Neo4j integrated و working
- [x] Knowledge graph populated
- [x] Agent orchestrator با decision loops
- [x] Hybrid retrieval (Vector + Graph)
- [x] All tests passing
- [x] Metrics dashboard populated
- [x] Documentation complete
- [x] Deployment successful

---

## 📚 مراجع

- [Architecture.md](Architecture.md) - معماری کلی
- [Neo4j-Knowledge-Graph.md](Neo4j-Knowledge-Graph.md) - توضیحات KG
- [Technical-Spec.md](Technical-Spec.md) - مشخصات فنی
- [Execution-Checklist.md](Execution-Checklist.md) - چک‌لیست اجرا

---

**Status:** Ready to Start Phase 3  
**Estimated Duration:** 6 weeks  
**Next Step:** Deploy Neo4j and start KG implementation

