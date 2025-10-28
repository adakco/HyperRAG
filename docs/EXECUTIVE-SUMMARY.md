# 🎯 خلاصه اجرایی (Executive Summary) - HyperRAG System

**Date:** 2025-10-27  
**Version:** 1.0  
**Status:** Production Ready

---

## 📊 وضعیت کلی سیستم

### Services: 13 Services Operational

| # | Service | Port | Event-Driven | OTEL | Status |
|---|---------|------|-------------|------|--------|
| 1 | Ingestor | 8000 | ✅ Yes | ✅ Yes | ✅ Running |
| 2 | Normalizer | 8001 | ✅ Yes | ✅ Yes | ✅ Running |
| 3 | Retriever | 8002 | ❌ No | ✅ Yes | ✅ Running |
| 4 | Chunker | 8003 | ❌ No | ✅ Yes | ✅ Running |
| 5 | Embedder | 8004 | ❌ No | ✅ Yes | ✅ Running |
| 6 | Evaluator | 8005 | ❌ No | ✅ Yes | ✅ Running |
| 7 | Agent-Orch | 8006 | ✅ Yes | ✅ Yes | ✅ Running |
| 8 | Policy | 8007 | ❌ No | ✅ Yes | ✅ Running |
| 9 | Costing | 8008 | ✅ Yes | ✅ Yes | ✅ Running |
| 10 | Pack Long-RAG | 8009 | ❌ No | ✅ Yes | ✅ Running |
| 11 | Memory | 8010 | ❌ No | ✅ Yes | ✅ Running |
| 12 | Reranker | 8011 | ❌ No | ✅ Yes | ✅ Running |
| 13 | Graph KG | 8012 | ❌ No | ✅ Yes | ✅ Running |

---

## 🔄 Event-Driven Services

### Event-Driven Architecture (4 Services)

#### 1. **Ingestor** (Port 8000)
- **Publishes:** `doc.ingested.v1` event
- **Trigger:** Document uploaded
- **Event Data:**
  ```json
  {
    "doc_id": "...",
    "version": "...",
    "uri_raw": "...",
    "lang": "en",
    "tenant": "...",
    "project": "..."
  }
  ```

#### 2. **Normalizer** (Port 8001)
- **Subscribes to:** `doc.ingested.v1` event
- **Publishes:** `doc.normalized.v1` event
- **Function:** Automatic document cleaning

#### 3. **Agent Orchestrator** (Port 8006)
- **Publishes:** Agent execution events
- **Subscribes to:** Various workflow events
- **Function:** Workflow orchestration

#### 4. **Costing** (Port 8008)
- **Publishes:** `budget.alert.v1` event
- **Trigger:** Budget threshold exceeded
- **Function:** Cost monitoring and alerts

### Event Flow

```
Ingestor (doc.ingested.v1)
    ↓
Normalizer (doc.normalized.v1)
    ↓
Chunker (manual or event)
    ↓
Embedder (manual or event)
    ↓
Retriever (on-demand)
```

---

## 📡 OpenTelemetry Integration

### All 13 Services Connected to OTEL ✅

**Configuration:**
- **Exporter:** OTLPSpanExporter
- **Endpoint:** http://192.168.2.23:4317
- **Protocol:** gRPC
- **Service Name:** Configured in all services

**Example (Ingestor):**
```python
resource = Resource.create(attributes={SERVICE_NAME: "hyperrag-ingestor"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

**What's Tracked:**
- Span creation for operations
- Service attributes
- Trace context propagation
- Distributed tracing

---

## 🔍 Langfuse Integration

### Status: ❌ **Not Currently Used**

**Current Situation:**
- Langfuse infrastructure is available at `192.168.2.23:3000`
- Environment variable configured: `LANGFUSE_HOST=http://192.168.2.23:3000`
- But services are NOT calling it yet

**How to Enable:**

1. **Install Langfuse SDK:**
   ```bash
   pip install langfuse
   ```

2. **Add to any service:**
   ```python
   from langfuse import Langfuse
   
   langfuse = Langfuse(
       secret_key="sk-...",
       public_key="pk-...",
       host="http://192.168.2.23:3000"
   )
   
   # Track generation
   langfuse.generation(
       name="retrieval",
       input=query,
       output=result
   )
   ```

**Recommended Services to Track:**
- Retriever: Track search queries and results
- Embedder: Track embedding generation
- Evaluator: Track quality metrics

---

## 🔌 MCP Server Integration

### Current State

**Services have MCP contracts defined:**
- `platform/contracts/mcp/memory.memorag.inputs.schema.json`
- `platform/contracts/mcp/retriever.inputs.schema.json`
- `platform/contracts/mcp/retriever.outputs.schema.json`

### How to Create MCP Server

#### Option 1: Wrap Existing Services

**Example: Retriever as MCP Server**

```python
# mcp-server-retriever.py
from mcp.server import Server
from mcp.types import Tool, ToolResult
import httpx

server = Server("hyperrag-retriever")

@server.call_tool()
async def retrieve(query: str, tenant: str, lang: str) -> ToolResult:
    """Retrieve documents from HyperRAG"""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/retrieve",
            json={
                "query": query,
                "tenant": tenant,
                "lang": lang,
                "limit": 5,
                "use_graph": True
            }
        )
    
    merit = response.json()
    
    return ToolResult(
        content=[
            {
                "type": "text",
                "text": json.dumps(result)
            }
        ]
    )

# Register tools
server.list_tools = lambda: [
    Tool(
        name="retrieve_documents",
        description="Retrieve relevant documents from HyperRAG",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "tenant": {"type": "string"},
                "lang": {"type": "string", "enum": ["en", "fa"]}
            },
            "required": ["query", "tenant", "lang"]
        }
    )
]
```

#### Option 2: Use Existing Agent-Orch Service

The Agent-Orch service (port 8006) is designed to be MCP-native and can act as an MCP server.

**Key Features:**
- Tool chaining
- Decision loops
- Schema validation
- Event-driven workflows

**Usage:**
```python
# Connect to agent-orch as MCP server
from mcp import ClientSession
import httpx

async def query_agent():
    response = await httpx.post(
        "http://localhost:8006/agent/query",
        json={
            "query": "Your question",
            "tenant": "mycompany",
            "tools": ["retriever", "graph", "memory"]
        }
    )
    return response.json()
```

---

## 🔗 LangGraph Integration

### How to Integrate with LangGraph

#### Current Architecture

The system is already designed for LangGraph integration:

1. **Agent Orchestrator** (Port 8006) is ready
2. **Decision loops** in agent-orch/main.py
3. **State management** with Redis
4. **Tool definitions** in contracts

#### Integration Steps

**1. Install LangGraph:**
```bash
pip install langgraph langchain langchain-core
```

**2. Create LangGraph Workflow:**

```python
# langgraph-integration.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
import httpx

# Define state
class HyperRAGState(TypedDict):
    query: str
    tenant: str
    lang: str
    retrieved_docs: Annotated[list, add_messages]
    graph_entities: list
    final_answer: str

زبانgraph = StateGraph(HyperRAGState)

# Node 1: Retrieve from vector search
async def vector_retrieve(state: HyperRAGState这些都是):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/retrieve",
            json={
                "query": state["query"],
                "tenant": state["tenant"],
                "lang": state["lang"],
                "use_graph": False
            }
        )
    return {"retrieved_docs": response.json()["results"]}

# Node 2: Extract graph knowledge
async def graph_extract(state: HyperRAGState):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8012/extract",
            json={
                "doc_id": "current-query",
                "content": state["query"],
                "tenant": state["tenant"],
                "lang": state["lang"]
            }
        )
    return {"graph_entities": response.json()["entities"]}

# Node 3: Synthesize answer
async def synthesize(state: HyperRAGState):
    docs = state["retrieved_docs"]
    entities = state["graph_entities"]
    return {"final_answer": f"Synthesized from {len(docs)} docs and {len(entities)} entities"}

# Build graph
workflow = graph
    .add_node("retrieve", vector_retrieve)
    .add_node("extract_graph", graph_extract)
    .add_node("synthesize", synthesize)
    .add_edge("retrieve", "extract_graph")
    .add_edge("extract_graph", "synthesize")
    .add_edge("synthesize", END)

 машины.compile()

# Run
result = workflow.invoke({
    "query": "Python programming",
    "tenant": "mycompany",
    "lang": "en"
})
```

**3. Integration with Agent-Orch:**

The agent-orch service can be extended to include LangGraph:

```python
# In agent-orch/main.py, add LangGraph workflow
from langgraph.graph import StateGraph

# Use existing decision loops but wrap in LangGraph
class AgentWorkflow:
    def __init__(self):
        self.graph = StateGraph(...)
        self.build_workflow()
    
    def build_workflow(self):
        # Add nodes for each agent action
        self.graph.add_node("retrieve", self._retrieve_node)
        self.graph.add_node("graph_search", self._graph_search_node)
        self.graph.add_node("synthesize", self._synthesize_node)
        
        # Add conditional edges
        self.graph.add_conditional_edges(
            "retrieve",
            self._decide_next_action,
            {
                "search_graph": "graph_search",
                "synthesize": "synthesize"
            }
        )
```

---

## 📊 Infrastructure Overview

### Current Infrastructure (192.168.2.23)

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| PostgreSQL | 5442 | ✅ | Metadata & chunks |
| Redis | 6479 | ✅ | Caching & state |
| NATS | 4222 | ✅ | Event bus |
| Qdrant | 6333 | ✅ | Vector search |
| MinIO | 9190 | ✅ | Object storage |
| Neo4j | 7687 | ✅ | Knowledge graph |
| Grafana | 3001 | ✅ | Monitoring |
| Langfuse | 3000 | ✅ | (Not used yet) |

---

## 🎯 Key Takeaways

### 1. Event-Driven Architecture
- **4 services** are event-driven
- **NATS** is the event bus
- **CloudEvents** format used

### 2. Observability
- **All 13 services** connected to OTEL
- **Distributed tracing** working
- **Service graph** in Grafana
- **Langfuse not used** (can be added)

### 3. MCP Server
- **Contracts defined**
- **Agent-Orch ready** for MCP
- **Can wrap services** individually

### 4. LangGraph Integration
- **Agent-Orch designed** for LangGraph
- **State management** in place
- **Decision loops** implemented
- **Need to add** LangGraph library

---

## 🚀 Recommended Next Steps

### Immediate
1. ✅ System is production-ready
2. ✅ All services operational
3. ✅ Hybrid retrieval working

### Optional Enhancements
1. **Langfuse Integration** (2-3 hours)
   - Add tracking to Retriever, Embedder, Evaluator
   - Track queries, responses, quality metrics

2. **MCP Server Implementation** (4-6 hours)
   - Create MCP server wrapper for services
   - Test with Claude Desktop or other MCP clients

3. **LangGraph Workflow** (4-8 hours)
   - Integrate LangGraph into Agent-Orch
   - Create complex multi-step workflows
   - Test with real queries

---

**Status: Production Ready ✅**  
**All core features implemented and tested!**

