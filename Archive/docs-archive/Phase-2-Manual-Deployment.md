# فاز 2: دستورالعمل Deployment دستی

**Last Updated:** 2025-10-26  
**Status:** Ready for Manual Deployment

---

## 📋 خلاصه اقدامات فاز 2

### گام 1: آماده‌سازی فایل‌ها در سرور

**آنت فایل‌های موردنیاز:**

```bash
# 1. کپی alloy-config.alloy
# از: /Users/daniel/Documents/Hyper-RAG/platform/infra/compose/alloy-config.alloy
# به: /app/rag-ai/rag-graph-langfuse-nats/compose/alloy-config.alloy

# 2. اضافه کردن Alloy service به docker-compose.yml موجود
```

---

## 🚀 راهنمای مرحله به مرحله

### مرحله 1: اضافه کردن Alloy به docker-compose.yml

**در سرور (192.168.2.23):**

```yaml
# Add to docker-compose.yml
services:
  # ... existing services ...
  
  alloy:
    image: grafana/alloy:latest
    container_name: alloy
    command: ["run", "--server.http.listen-addr=0.0.0.0:12345", "/etc/alloy/config.alloy"]
    ports:
      - "12345:12345"  # Alloy UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    volumes:
      - ./alloy-config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - rag_net
    depends_on:
      tempo:
        condition: service_started
      loki:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:12345/ready"]
      interval: 10s
      timeout: 5s
      retries: 3
```

---

### مرحله 2: راه‌اندازی Alloy

```bash
# در سرور
cd /app/rag-ai/rag-graph-langfuse-nats/compose

# Start Alloy
docker-compose up -d alloy

# بررسی وضعیت
docker logs -f alloy
```

**چک شود:**
- [ ] Container running
- [ ] No errors in logs
- [ ] Health check OK

---

### مرحله 3: Restart سرویس‌های HyperRAG

**در Mac (محل پروژه):**

```bash
cd /Users/daniel/Documents/Hyper-RAG

# توقف
./stop-services-host.sh

# شروع مجدد
./start-services-host.sh

# بررسی
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011; do
  echo "Checking $port..."
  curl -s http://localhost:$port/health && echo " ✅" || echo " ❌"
done
```

**چک شود:**
- [ ] All 12 services running
- [ ] Health checks OK
- [ ] No errors

---

### مرحله 4: Test Telemetry Flow

```bash
# 1. Send test request
curl -X POST http://localhost:8000/ingest \
  -F "doc_id=test-telemetry" \
  -F "tenant=test" \
  -F "project=alpha" \
  -F "lang=en" \
  -F "file=@test.txt"

# 2. Check Alloy receives data
curl http://192.168.2.23:12345/metrics | grep otelcol_receiver

# 3. Check Tempo
curl "http://192.168.2.23:3200/api/search?tags=service.name%3Dhyperrag-ingestor"

# 4. Check Prometheus
curl "http://192.168.2.23:9090/api/v1/query?query=hyperrag_ingestion_total"
```

**چک شود:**
- [ ] Alloy metrics show received data
- [ ] Traces in Tempo
- [ ] Metrics in Prometheus
- [ ] Service names correct (not unknown_service)

---

### مرحله 5: Import Dashboards

**در Grafana (http://192.168.2.23:3001):**

1. **اضافه کردن Data Sources:**
   - Prometheus: http://prometheus:9090
   - Tempo: http://tempo:3200
   - Loki: http://loki:3100

2. **Import Dashboards:**
   - `platform/infra/grafana/dashboards/hyperrag-complete-dashboard.json`
   - `platform/infra/grafana/dashboards/hyperrag-overview.json`
   - `platform/infra/grafana/dashboards/hyperrag-quality.json`

3. **Verify Panels:**
   - Request Rate panel shows data
   - Trace panel shows traces
   - Service Graph shows nodes

---

### مرحله 6: Verify Service Graph

**در Grafana:**

1. باز کردن dashboard: HyperRAG Complete Monitoring
2. رفتن به Service Graph panel
3. باید 12 service nodes نمایش داده شود:
   - hyperrag-ingestor
   - hyperrag-normalizer
   - hyperrag-chunker
   - hyperrag-embedder
   - hyperrag-retriever
   - hyperrag-reranker
   - hyperrag-evaluator
   - hyperrag-agent-orch
   - hyperrag-policy
   - hyperrag-costing
   - hyperrag-pack-longrag
   - hyperrag-memory

**چک شود:**
- [ ] All 12 services visible
- [ ] Edges showing connections
- [ ] Metrics on nodes working

---

## ✅ چک‌لیست نهایی

### Infrastructure
- [ ] Alloy running on server
- [ ] Ports 4317, 4318, 12345 accessible
- [ ] Alloy health check OK

### Services
- [ ] All 12 HyperRAG services running
- [ ] Health checks passing
- [ ] No errors in logs

### Telemetry
- [ ] Traces flowing to Tempo
- [ ] Metrics flowing to Prometheus
- [ ] Logs flowing to Loki
- [ ] Service names correct

### Dashboards
- [ ] Data sources configured
- [ ] Dashboards imported
- [ ] Panels showing data
- [ ] Service graph populated

### Validation
- [ ] Test request successful
- [ ] Traces visible in Grafana
- [ ] Service graph working
- [ ] All metrics accurate

---

## 🎯 معیارهای موفقیت

- ✅ Alloy collects telemetry successfully
- ✅ Service graph shows all services
- ✅ Traces have correct service names
- ✅ Dashboards populated with data
- ✅ Pipeline works end-to-end

---

## ⚠️ Troubleshooting

### Issue: Alloy not receiving data

**Solution:**
```bash
# Check Alloy logs
docker logs alloy

# Check if services can reach Alloy
telnet 192.168.2.23 4317

# Verify service OTEL endpoint
grep "endpoint" platform/services/*/main.py | grep 4317
```

### Issue: Service graph empty

**Solution:**
```bash
# Enable Tempo metrics generator
# Check tempo.yml has:
metrics_generator:
  processors: [service-graphs]

# Restart Tempo
docker-compose restart tempo
```

### Issue: Dashboards showing no data

**Solution:**
```bash
# Check data sources
curl http://192.168.2.23:9090/api/v1/targets | grep hyperrag

# Check queries
curl "http://192.168.2.23:9090/api/v1/query?query=hyperrag_ingestion_total"
```

---

## 📝 خلاصه دستورات

```bash
# 1. در سرور: Start Alloy
cd /app/rag-ai/rag-graph-langfuse-nats/compose
docker-compose up -d alloy

# 2. در Mac: Restart services
cd /Users/daniel/Documents/Hyper-RAG
./stop-services-host.sh
./start-services-host.sh

# 3. Test
curl -X POST http://localhost:8000/ingest ...

# 4. Check
curl http://192.168.2.23:12345/ready
curl http://192.168.2.23:3200/api/search

# 5. Import dashboards in Grafana
```

---

**Status:** Ready for Manual Deployment  
**Next Step:** Deploy Alloy and restart services

