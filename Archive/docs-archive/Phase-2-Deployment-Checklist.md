# فاز 2: Deployment & Testing - چک‌لیست اقدامات

**تاریخ شروع:** 2025-10-26  
**وضعیت:** Ready to Start

---

## 📋 خلاصه فاز 1 (تکمیل شده)

✅ **مستندات کامل:**
- `Persian-Documentation.md` (16KB)
- `Services-Documentation.md` (18KB)
- `Service-Testing-Guide.md` (10KB)
- `Neo4j-Knowledge-Graph.md` (15KB)
- `Alloy-Setup-Guide.md`
- `Grafana-12-Traces-Guide.md`
- `Fix-Service-Name-Issue.md`

✅ **اصلاحات Service Names:**
- 12 سرویس با `SERVICE_NAME` اضافه شدند
- `fix-service-names.py` اجرا شد

✅ **Alloy Configuration:**
- `alloy-config.alloy` آماده
- Docker Compose با Alloy

✅ **Grafana Dashboards:**
- `hyperrag-complete-dashboard.json` (16KB)
- `hyperrag-overview.json` (5.5KB)
- `hyperrag-quality.json` (6.4KB)

✅ **Database Schema:**
- Schema کامل PostgreSQL
- Foreign keys و indexes

---

## 🎯 فاز 2: Deployment & Testing

### گام 1: Deploy Alloy روی سرور

**هدف:** راه‌اندازی Alloy برای جمع‌آوری telemetry

```bash
# روی سرور 192.168.2.23
cd /path/to/docker-compose

# بررسی فایل‌های Alloy
ls -la alloy-config.alloy
ls -la docker-compose.with-alloy.yml

# راه‌اندازی Alloy
docker-compose -f docker-compose.with-alloy.yml up -d alloy

# بررسی وضعیت
docker ps | grep alloy
curl http://192.168.2.23:12345/ready
```

**چک‌لیست:**
- [ ] Alloy container running
- [ ] Port 4317 accessible
- [ ] Port 4318 accessible  
- [ ] Port 12345 (UI) accessible
- [ ] Health endpoint returns OK

---

### گام 2: Restart سرویس‌های HyperRAG

**هدف:** اعمال تغییرات SERVICE_NAME

```bash
# در Mac (محل HyperRAG)
cd /Users/daniel/Documents/Hyper-RAG

# توقف سرویس‌ها
./stop-services-host.sh

# شروع مجدد
./start-services-host.sh

# بررسی همه سرویس‌ها
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011; do
  echo "Checking port $port..."
  curl -s http://localhost:$port/health || echo "❌ Port $port failed"
done
```

**چک‌لیست:**
- [ ] همه سرویس‌ها running
- [ ] Health checks OK
- [ ] Metrics endpoint accessible

---

### گام 3: تست Telemetry Flow

**هدف:** اطمینان از جریان درست داده

```bash
# 1. ارسال تست به Ingestor
curl -X POST http://localhost:8000/ingest \
  -F "doc_id=test-telemetry-$(date +%s)" \
  -F "tenant=test" \
  -F "project=alpha" \
  -F "lang=en" \
  -F "file=@test-doc.txt"

# 2. بررسی Alloy دریافت کرده
curl http://192.168.2.23:12345/metrics | grep otelcol_receiver_otlp_spans

# 3. بررسی Tempo
curl "http://192.168.2.23:3200/api/search?tags=service.name%3Dhyperrag-ingestor"

# 4. بررسی Prometheus
curl "http://192.168.2.23:9090/api/v1/query?query=hyperrag_ingestion_total"
```

**چک‌لیست:**
- [ ] Traces در Tempo هستند
- [ ] Metrics در Prometheus هستند
- [ ] Service name صحیح است (نه unknown_service)

---

### گام 4: Import Dashboards در Grafana

**هدف:** تنظیم داشبوردها

```bash
# 1. لاگین به Grafana
# http://192.168.2.23:3001
# Login: admin / admin

# 2. Add Data Sources
# - Prometheus: http://prometheus:9090
# - Tempo: http://tempo:3200
# - Loki: http://loki:3100

# 3. Import Dashboards
# - hyperrag-complete-dashboard.json
# - hyperrag-overview.json
# - hyperrag-quality.json

# 4. Verify Panels
# - Check Request Rate panel
# - Check Trace panel
# - Check Service Graph
```

**چک‌لیست:**
- [ ] همه data sources متصل هستند
- [ ] Dashboards import شدند
- [ ] Panels داده نمایش می‌دهند

---

### گام 5: Verify Service Graph

**هدف:** اطمینان از نمایش درست Service Graph

```bash
# Query در Grafana
# TraceQL: {service.namespace="hyperrag"}
# باید 12 سرویس نمایش داده شود
```

**چک‌لیست:**
- [ ] Service Graph نمایش داده می‌شود
- [ ] همه 12 سرویس نمایش داده می‌شود
- [ ] Edges (connections) نمایش داده می‌شود
- [ ] Metrics روی nodes نمایش داده می‌شود

---

## 🧪 تست‌های نهایی

### تست 1: Full Pipeline

```bash
# اجرای کامل pipeline
python3 test-complete-pipeline.py

# باید موفق باشد:
# ✅ Ingestion
# ✅ Normalization
# ✅ Chunking
# ✅ Embedding
# ✅ Retrieval
```

### تست 2: Trace در Grafana

```bash
# در Grafana
# 1. باز کردن Traces panel
# 2. Query: {service.name="hyperrag-ingestor"}
# 3. باید span‌های مربوط را ببینید
```

### تست 3: Service Graph

```bash
# در Grafana
# 1. باز کردن Service Graph panel
# 2. باید graph با nodes نمایش داده شود
# 3. هر node یک سرویس HyperRAG است
```

---

## 📊 معیارهای موفقیت

- ✅ Alloy telemetry جمع می‌کند
- ✅ Prometheus metrics دارد
- ✅ Tempo traces دارد
- ✅ Loki logs دارد
- ✅ Service Graph 12 سرویس نمایش می‌دهد
- ✅ Traces با نام صحیح سرویس هستند
- ✅ Dashboard‌ها کار می‌کنند
- ✅ Pipeline کامل موفق است

---

## 🚀 اقدامات پس از تکمیل فاز 2

1. **ثبت نتایج تست**
2. **ثبت screenshots**
3. **به‌روزرسانی مستندات در صورت نیاز**
4. **Push به Git**

---

## ⚠️ Troubleshooting

اگر مشکلی پیش آمد:

1. **Alloy دریافت نمی‌کند:**
   - چک کنید port 4317 باز است
   - چک کنید services به http://192.168.2.23:4317 ارسال می‌کنند

2. **Service Graph خالی است:**
   - چک کنید Tempo metrics_generator فعال است
   - چک کنید traces با service.name ارسال می‌شوند

3. **Dashboards خالی است:**
   - چک کنید data sources متصل هستند
   - چک کنید query‌ها درست است

---

**آماده برای شروع فاز 2؟**

