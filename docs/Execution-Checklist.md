# Execution Checklist — From Dev to Prod
**Owner:** Program Manager  
**Status:** Ready for Kickoff  

## A) Pre-Flight (Week 0)
- [ ] تخصیص مالکان: معماری، DevOps، امنیت، محصول
- [ ] ایجاد ساختار مخزن `/platform/*` در GitLab
- [ ] راه‌اندازی Secrets (Dev/Stage/Prod) + External Secrets Operator
- [ ] پیکربندی SLO در Grafana + AlertManager
- [ ] انتخاب مدل‌ها:  
  - Embedding: `bert-fa-base` (fa)، `text-embedding-3-large` (en)  
  - Re-ranker: مدل‌های جداگانه برای هر زبان  
  - LLM: مدل اصلی + مدل ارزان برای fallback
- [ ] تعریف بودجهٔ اولیهٔ توکن و هزینه

## B) Phase 1 — RAG حرفه‌ای (D0–D15)
- [ ] راه‌اندازی MinIO, Postgres, Qdrant, NATS, Redis
- [ ] پیاده‌سازی `retriever.mcp` (هیبرید + RRF + re-rank)
- [ ] پیاده‌سازی `evaluator.ragas.mcp` برای en و fa
- [ ] ادغام OPA برای routing و کنترل دسترسی
- [ ] پیاده‌سازی end-to-end tracing (traceparent از Gateway تا LLM)
- [ ] **معیار عبور**:  
  - Faithfulness ≥ 0.88 (en) / ≥ 0.85 (fa)  
  - Recall@10 ≥ 0.90  
  - p95 ≤ 1.5s  
  - استناد ≥ 95%

## C) Phase 2 — Long-Context (D16–D45)
- [ ] پیاده‌سازی `pack.longrag.mcp` (بسته‌های 2–4k + خلاصه)
- [ ] پیاده‌سازی `memory.memorag.mcp` (حافظهٔ episode/semantic)
- [ ] پیاده‌سازی cache بسته با invalidation بر اساس نسخهٔ سند
- [ ] تست‌های Chaos: تأخیر شبکه، شکست سرویس جزئی
- [ ] تمرین DR: RPO ≤ 15m, RTO ≤ 60m
- [ ] **معیار عبور**:  
  - کاهش ≥ 30% هزینه در اسناد طولانی  
  - hit rate بسته ≥ 40%  
  - بدون افت Faithfulness

## D) Phase 3 — Agentic (D46–D75)
- [ ] پیاده‌سازی Agent Orchestrator با لایهٔ انتزاعی (قابل تعویض)
- [ ] پیاده‌سازی guardrails: max_steps, max_cost, max_time
- [ ] پیاده‌سازی `costing.billing.mcp` + kill-switch مدل
- [ ] Red Team: تست injection در prompt، ابزار، حافظه
- [ ] تست‌های مقاومت: شکست ابزار در حین حلقه، timeout
- [ ] **معیار عبور**:  
  - موفقیت ایجنت ≥ 80%  
  - همسویی استناد ≥ 98%  
  - بدون سرریز بودجه  
  - گذر از تمام تست‌های مقاومت

## E) Hardening & Prod (D76–D90)
- [ ] فعال‌سازی چندمستاجری نهایی:  
  - MinIO: SSE-KMS + Object Lock  
  - Qdrant: فیلتر payload  
  - Postgres: RLS + partitioning
- [ ] فعال‌سازی supply chain security (Trivy/Syft/Cosign)
- [ ] پیکربندی Istio mTLS + HPA + PDB
- [ ] راه‌اندازی Velero Backup + replication
- [ ] تست امنیت UI: CSRF, rate limit, audit
- [ ] **دریچهٔ راه‌اندازی**:  
  - تمام معیارهای عبور تأیید شده  
  - تمرین DR انجام شده  
  - تأیید نهایی C-Level

## F) Runbooks (اجرایی)

### Retrieval Latency بالا
- افزایش `ef_search` در Qdrant  
- بررسی CPU/RAM در retriever  
- کاهش `k_dense`/`k_sparse` در مسیر fast

### هشدار PII
- اعمال مسیر secure  
- re-index با redaction  
- بررسی RCA و ثبت در Audit Trail

### سرریز بودجهٔ توکن
- کاهش kها  
- فعال‌سازی cache تهاجمی  
- فعال‌سازی kill-switch مدل گران

### شکست حلقهٔ ایجنت
- reset state جلسه  
- محدود کردن `max_steps`  
- بررسی لاگ در Loki  
- اطلاع‌رسانی به Slack

### خطای کدگذاری فارسی (Mojibake)
- اعمال UTF-8 force در Normalizer  
- فعال‌سازی renderer RTL در UI  
- تست مجدد با دادهٔ فارسی

## G) تأییدیه‌نامه
- [ ] Phase-1 ✅ | تاریخ: ____ | امضا: _____  
- [ ] Phase-2 ✅ | تاریخ: ____ | امضا: _____  
- [ ] Phase-3 ✅ | تاریخ: ____ | امضا: _____  
- [ ] راه‌اندازی نهایی ✅ | تاریخ: ____ | امضا: _____
