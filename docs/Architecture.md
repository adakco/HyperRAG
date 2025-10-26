# MCP-Native Agentic HyperRAG — Architecture (vNext, Enterprise-Grade)
**Last updated:** 2025-10-11  
**Owner:** Chief Architect  
**Status:** Approved  

## 1) Executive Summary
این معماری یک سیستم Agentic HyperRAG را بر پایهٔ الگوی **MCP-Native** (Model-Controller-Provider) پیاده‌سازی می‌کند: هر قابلیت (بازیابی، حافظه، گراف دانش، ارزیابی، سیاست، هزینه‌یابی) به‌صورت یک ابزار استاندارد (MCP Tool) در دسترس ایجنت‌ها قرار می‌گیرد. سیستم از Dev تا Prod با پشتیبانی کامل از **چندزبانگی (به‌ویژه فارسی)**، **چندمستاجری ایمن**، **حاکمیت داده**، و **مقاومت عملیاتی** طراحی شده است.

## 2) اهداف طراحی
- **AI-Ready واقعی**: S3/MinIO به‌عنوان منبع حقیقت، متادیتای ساختاریافته، و ایندکس‌های مشتق (برداری و گرافی).
- **Agentic RAG استاندارد**: جدایش نگرانی‌ها، قراردادهای مشخص (JSON Schema + SemVer)، و قابلیت تعویض Orchestrator.
- **سه مرحلهٔ بالغ‌سازی**:  
  (۱) RAG حرفه‌ای → (۲) مدیریت Context طولانی → (۳) اجرای Agentic با حلقهٔ تصمیم‌گیری.
- **Enterprise-Grade**: احراز هویت (OIDC)، کنترل دسترسی (ABAC/RLS)، رمزنگاری (mTLS/SSE-KMS)، ردیابی کامل (Audit Trail).
- **چندزبانه و اخلاقی**: پشتیبانی از فارسی و انگلیسی، حذف PII، بررسی سوگیری، و طراحی حریم خصوصی از ابتدا.

## 3) نمای کلان (Planes & Layers)
```mermaid
flowchart TB
    G[API Gateway\n(OIDC+JWT, Rate-limit, traceparent)] --> R[Router via policy.opa.mcp]
    R --> AO[Agent Orchestrator\n(LangGraph *or* Temporal)]
    AO -->|MCP| RT[retriever.mcp\n(Hybrid + RRF + Re-rank)]
    AO -->|MCP| PK[pack.longrag.mcp\n(2–4k packs + summaries)]
    AO -->|MCP| MM[memory.memorag.mcp\n(global clues)]
    AO -->|MCP| KG[graph.kg.mcp\n(Neo4j)]
    AO -->|MCP| EV[evaluator.ragas.mcp]
    AO -->|MCP| PL[policy.opa.mcp]
    AO -->|MCP| CT[costing.billing.mcp]
    subgraph Data Plane
      S3[(MinIO/S3)] --- QD[(Qdrant)]
      PG[(Postgres Meta)] --- NJ[(NATS JetStream)]
      RD[(Redis Cache/Streams Fallback)]
      KGX[(Neo4j)]
    end
    subgraph Governance & Observability
      OTEL[OTEL Collector]
      LF[Langfuse] --- GRAF[Grafana/Prom/Loki/Tempo]
      OPA[OPA/ABAC] --- AUD[Audit Trail (S3 WORM)]
    end
```

## 4) جریان داده

### 4.1 Ingestion (Idempotent و چندزبانه)
1. سند از GitLab از طریق Webhook وارد می‌شود.
2. نسخهٔ خام در MinIO ذخیره می‌شود.
3. سرویس Normalizer:  
   - PII را حذف می‌کند.  
   - برای فارسی: کدگذاری UTF-8 و پردازش RTL اعمال می‌شود.
4. Chunker سند را بر اساس زبان (fa/en) تقسیم می‌کند.
5. Embedder با مدل مناسب زبان (فارسی/انگلیسی) بردار تولید می‌کند.
6. ایندکس در Qdrant با تگ `lang` و `tenant` ذخیره می‌شود.

### 4.2 Serving (Agentic Pipeline)
1. درخواست با `lang` و `tenant` وارد Gateway می‌شود.
2. Router بر اساس سیاست (OPA) مسیریابی می‌کند.
3. Orchestrator ابزارهای MCP را فراخوانی می‌کند:
   - `retriever.mcp`: بازیابی هیبریدی + re-rank با مدل زبانی مناسب.
   - `pack.longrag.mcp`: ساخت بستهٔ context با بودجهٔ توکن.
   - `memory.memorag.mcp`: استفاده از سرنخ‌های قبلی.
4. پاسخ نهایی با استناد تولید و به‌طور موازی توسط `evaluator.ragas.mcp` ارزیابی می‌شود.
5. تمام traceها در Langfuse و OTEL ذخیره می‌شوند.

## 5) چندمستاجری و امنیت
- **MinIO**: prefix یا bucket جداگانه برای هر tenant + SSE-KMS + Object Lock (WORM).
- **Qdrant**: فیلتر payload بر اساس `tenant`, `project`, `lang`, `acl`.
- **Postgres**: جداسازی داده با Row-Level Security (RLS) و partitioning.
- **شبکه**: mTLS بین تمام سرویس‌ها.
- **دسترسی**: ABAC با OPA بر اساس claimهای JWT (tenant, role, project, lang).
- **داده‌های حساس**: deny-by-default، sandbox ابزارها، allow-list عملیات خطرناک.

## 6) مشاهده‌پذیری و SLO
| شاخص (SLI)                | هدف          | آستانه هشدار   |
|--------------------------|--------------|----------------|
| Faithfulness (انگلیسی)   | ≥ 0.88       | < 0.80         |
| Faithfulness (فارسی)     | ≥ 0.85       | < 0.78         |
| Recall@10                | ≥ 0.90       | < 0.85         |
| p95 Latency (Fast)       | ≤ 1.5s       | > 2s           |
| p95 Latency (Secure)     | ≤ 3s         | > 4s           |
| هزینه در هر پرس‌وجو       | ≤ $0.002     | > $0.003       |
| موفقیت ایجنت            | ≥ 80%        | < 70%          |
| حوادث PII                | 0            | > 0            |

## 7) ریسک‌ها و کنترل‌ها
- **Tool Storming**: rate-limit + budget + backpressure.
- **Injection**: اعتبارسنجی schema، sandbox، deny-by-default.
- **Drift سیاست**: تست Rego در CI، امضای دیجیتال پالیسی.
- **وابستگی Orchestrator**: لایهٔ انتزاعی برای تعویض LangGraph/Temporal.
- **خطاهای زبان فارسی**: تست‌های اختصاصی در CI، پردازش RTL.
- **خرابی جزئی**: تست‌های Chaos Engineering + circuit breaker.
- **Disaster Recovery**: RPO ≤ 15 دقیقه، RTO ≤ 60 دقیقه، تمرین فصلی.

## 8) فازهای اجرا و معیارهای عبور
- **فاز ۱ (RAG حرفه‌ای)**:  
  Faithfulness ≥ 0.88 (en) / ≥ 0.85 (fa)، Recall@10 ≥ 0.90، p95 ≤ 1.5s، استناد ≥ 95%.
- **فاز ۲ (Long-Context)**:  
  کاهش ≥ 30% هزینه بدون افت کیفیت، hit rate بسته ≥ 40%.
- **فاز ۳ (Agentic)**:  
  موفقیت ≥ 80%، همسویی استناد ≥ 98%، بدون سرریز بودجه، گذر از تست‌های مقاومت.

## 9) مالکیت
- معماری: Chief Architect  
- DevOps: DevOps Lead  
- امنیت: Compliance Officer  
- محصول: Product Owner
