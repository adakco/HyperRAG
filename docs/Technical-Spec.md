# MCP-Native Agentic HyperRAG — Technical Specification
**Last updated:** 2025-10-11  
**Owner:** Platform Engineering  

## 1) ساختار مخزن
```
/platform
├── /infra
│   ├── compose/          # Local dev (Docker Compose)
│   ├── helmfile/         # Prod (K8s)
│   ├── otel/             # Observability config
│   └── grafana/          # Dashboards
├── /contracts
│   ├── cloudevents/
│   ├── mcp/              # JSON Schema for tools
│   ├── rego/             # OPA policies
│   └── agent-interface.yaml  # Orchestrator abstraction
├── /services
│   ├── ingestor/
│   ├── normalizer/
│   ├── chunker/
│   ├── embedder/
│   ├── retriever/
│   ├── reranker/
│   ├── pack.longrag/
│   ├── memory.memorag/
│   ├── agent-orch/
│   ├── evaluator/
│   ├── policy/
│   └── costing/
└── /ops
    ├── runbooks/
    └── playbooks/
```

## 2) قراردادهای ارتباطی

### 2.1 CloudEvent — Ingestion
```json
{
  "specversion": "1.0",
  "id": "uuid-123",
  "source": "gitlab/webhook",
  "type": "doc.ingested.v1",
  "time": "2025-10-11T10:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "doc_id": "CRM-42",
    "version": "v5",
    "uri_raw": "s3://raw/crm/42.pdf",
    "content_type": "application/pdf",
    "lang": "fa",
    "tenant": "acme",
    "project": "alpha",
    "acl": ["role:pm", "team:ml"],
    "sha256": "a1b2c3..."
  }
}
```

### 2.2 Agent Orchestrator Interface (ابستراکشن)
```yaml
# /contracts/agent-interface.yaml
version: "1.0"
methods:
  - name: start_session
    inputs: { session_id, query, lang, tenant, token_budget }
  - name: invoke_tool
    inputs: { tool_name, input, traceparent }
  - name: evaluate_step
    inputs: { output, policy_context }
  - name: finalize_response
    inputs: { citations, cost, trace_id }
resilience:
  circuit_breaker: true
  retry_policy: exponential_backoff(max_retries=3)
  timeout_per_step: 10s
```

### 2.3 MCP Tool Catalog (نمونه: retriever.mcp)
```json
{
  "tool": "retriever.mcp",
  "version": "1.2.0",
  "slis": { "timeout_ms": 1200, "p95_ms": 1500 },
  "security": { "policy_class": "fast", "scopes": ["read:index"] },
  "inputs": { "$ref": "./schemas/retriever.inputs.schema.json" },
  "outputs": { "$ref": "./schemas/retriever.outputs.schema.json" },
  "errors": ["retryable", "fatal", "unauthorized", "quota_exceeded"]
}
```

## 3) پیام‌رسانی
- **اصلی**: NATS JetStream  
  - Stream: `doc.*`, `context.*`  
  - Consumer: durable, ack wait=30s, max deliveries=3  
- **پشتیبان**: Redis Streams  
  - Idempotency key = `doc_id + version + stage`

## 4) لایه داده

### 4.1 Postgres (متادیتای سند)
```sql
CREATE TABLE documents (
  doc_id TEXT PRIMARY KEY,
  tenant TEXT NOT NULL,
  project TEXT NOT NULL,
  lang TEXT DEFAULT 'en',
  latest_version TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE document_versions (
  doc_id TEXT,
  version TEXT,
  sha256 TEXT,
  uri_raw TEXT,
  uri_clean TEXT,
  lang TEXT DEFAULT 'en',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (doc_id, version)
);
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant = current_setting('app.tenant', true));
```

### 4.2 Qdrant (ایندکس برداری)
- Payload: `tenant`, `project`, `lang`, `acl`, `version`, `chunk_id`
- HNSW: `m=32`, `ef_construct=256`
- مدل‌های embedding:  
  - فارسی: `HooshvareLab/bert-fa-base-uncased`  
  - انگلیسی: `text-embedding-3-large`
- Re-ranker: مدل جداگانه برای هر زبان

## 5) امنیت
- **OPA Rego**: سیاست‌های دسترسی بر اساس tenant/role/lang
- **mTLS**: بین تمام سرویس‌ها با Istio
- **Supply Chain**:  
  - Trivy در CI (fail on CRITICAL)  
  - SBOM با Syft  
  - امضای تصویر با Cosign  
  - AdmissionPolicy: فقط تصاویر امضاشده

## 6) مشاهده‌پذیری
- **Trace**: OTEL → Tempo  
- **Log**: OTEL → Loki  
- **Metric**: OTEL → Prometheus → Grafana  
- **AI Quality**: Langfuse + RAGAS (برای هر زبان جداگانه)
- **هشدارها**:  
  - `HighRetrievalLatencyP99`  
  - `PersianRAGASLow`  
  - `AgentLoopFailureRateHigh`

## 7) CI/CD (GitLab)
```yaml
stages: [build, test, evaluate, deploy, monitor]

evaluate:
  script:
    - ragas evaluate --dataset en --lang en --metrics faithfulness,recall
    - ragas evaluate --dataset fa --lang fa --metrics faithfulness,recall
    - python scripts/resilience_test.py

resilience_test:
  script:
    - ./chaos/simulate_tool_failure.sh
    - ./chaos/simulate_network_delay.sh
```

## 8) Kubernetes
- **Helmfile**: استقرار Qdrant, NATS, MinIO, Langfuse
- **HPA**: بر اساس CPU (70%) و custom metric (درخواست در ثانیه)
- **Ingress**: Canary deployment با Istio (10% → 100%)
- **Backup**: Velero + replication بین مناطق

## 9) Portal و UI
- پشتیبانی از RTL برای فارسی
- بارگذاری p95 < 200ms
- امنیت: CSRF, session hardening, RBAC-aware rate limit
- ردیابی عملیات حساس (export/share) در Audit Trail

## 10) مدیریت حوادث (خلاصه)
- **تأخیر در بازیابی**: افزایش `ef_search` در Qdrant یا کاهش `k`
- **PII شناسایی‌شده**: re-index با redaction + مسیر امن
- **سرریز بودجه**: فعال‌سازی kill-switch مدل گران
- **شکست حلقهٔ ایجنت**: reset state + محدودیت `max_steps`
