# Alloy Setup Guide for HyperRAG

**Last Updated:** 2025-10-26  
**Purpose:** Deploy Alloy on server to collect telemetry from HyperRAG services

---

## Current Status ✅

**All services are correctly configured!** They send data to:
- **Endpoint**: `http://192.168.2.23:4317`
- **Protocol**: OTLP gRPC

---

## Architecture Flow

```
HyperRAG Services (192.168.2.23)
├── Ingestor (localhost:8000)
├── Normalizer (localhost:8001)
├── Retriever (localhost:8002)
└── ... (all other services)
         ↓
    Send to: http://192.168.2.23:4317
         ↓
   Grafana Alloy (on server 192.168.2.23)
    ├── Port 4317: OTLP gRPC receiver
    ├── Port 4318: OTLP HTTP receiver
    └── Port 12345: Alloy UI
         ↓
    ┌──────────────────────────┐
    │   Forward to:            │
    ├── Prometheus (9090)      │ ← Metrics
    ├── Loki (3100)            │ ← Logs  
    └── Tempo (4317)           │ ← Traces
    └──────────────────────────┘
```

---

## Deployment Options

### Option 1: Alloy on Server (Recommended)

Alloy runs on the same server as infrastructure services.

#### Docker Compose Configuration

```bash
# On server 192.168.2.23
cd /path/to/docker-compose

# Start Alloy with configuration
docker run -d \
  --name alloy \
  --network rag_net \
  -p 4317:4317 \
  -p 4318:4318 \
  -p 12345:12345 \
  -v /path/to/alloy-config.alloy:/etc/alloy/config.alloy:ro \
  grafana/alloy:latest \
  run --server.http.listen-addr=0.0.0.0:12345 /etc/alloy/config.alloy
```

### Option 2: Use Docker Compose File

The configuration already includes Alloy:

```bash
# Use the provided docker-compose file
cd platform/infra/compose
docker-compose -f docker-compose.with-alloy.yml up -d alloy
```

---

## Verification Steps

### 1. Check Alloy is Running

```bash
# On server 192.168.2.23
docker ps | grep alloy

# Check Alloy health
curl http://192.168.2.23:12345/ready

# Check Alloy metrics
curl http://192.168.2.23:12345/metrics
```

### 2. Verify Services Send Data

```bash
# Check if services are sending to Alloy
# Look for OTLP connections in Alloy logs
docker logs alloy | grep "otlp"

# Check received spans
curl http://192.168.2.23:12345/metrics | grep otelcol_receiver
```

### 3. Verify Forwarding to Backends

```bash
# Check Prometheus receives metrics
curl "http://192.168.2.23:9090/api/v1/query?query=up{job=\"hyperrag_ingestor\"}"

# Check Loki receives logs
curl "http://192.168.2.23:3100/ready"

# Check Tempo receives traces
curl "http://192.168.2.23:3200/api/search?tags=service.namespace=hyperrag"
```

---

## Configuration Details

### Alloy Configuration (`alloy-config.alloy`)

```alloy
// 1. Receive OTLP data from services
otelcol.receiver.otlp "default" {
    protocol {
        grpc { endpoint = "0.0.0.0:4317" }
        http { endpoint = "0.0.0.0:4318" }
    }
}

// 2. Batch and process
otelcol.processor.batch "traces" { ... }
otelcol.processor.batch "metrics" { ... }
otelcol.processor.batch "logs" { ... }

// 3. Forward to backends
otelcol.exporter.otlp "tempo" {
    endpoint = "http://tempo:4317"
}

prometheus.remote_write "prometheus" {
    endpoint { url = "http://prometheus:9090/api/v1/write" }
}

loki.write "loki" {
    endpoint = "http://loki:3100/loki/api/v1/push"
}
```

### Service Configuration (Already Done ✅)

All services are configured in their `main.py`:

```python
otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

---

## Prometheus Scraping

Alloy automatically scrapes metrics from HyperRAG services:

```alloy
prometheus.scrape "hyperrag_services" {
    targets = [
        {"__address__" = "192.168.2.23:8000", "job" = "hyperrag_ingestor"},
        {"__address__" = "192.168.2.23:8001", "job" = "hyperrag_normalizer"},
        // ... all 12 services
    ]
    
    forward_to = [prometheus.remote_write.prometheus.receiver]
}
```

---

## Troubleshooting

### Issue: No data in Grafana

**Check:**
```bash
# 1. Verify Alloy is running
docker ps | grep alloy

# 2. Check Alloy is receiving data
curl http://192.168.2.23:12345/metrics | grep received

# 3. Verify services are sending
curl http://192.168.2.23:8000/health
```

### Issue: Alloy not receiving traces

**Solution:**
```bash
# Check service OTEL configuration
grep "endpoint=" platform/services/*/main.py | grep 4317

# Should show: endpoint="http://192.168.2.23:4317"

# Test if Alloy is accessible
nc -zv 192.168.2.23 4317
```

### Issue: Data not forwarding to backends

**Solution:**
```bash
# Check Alloy logs
docker logs alloy

# Look for errors like:
# - "connection refused" → Backend not running
# - "no route" → Configuration issue
```

---

## Service Data Flow

### Traces Flow

```
Service (8000) 
  → OTEL SDK 
  → http://192.168.2.23:4317 
  → Alloy (OTLP receiver)
  → Alloy (processor.batch)
  → Alloy (exporter.otlp.tempo)
  → Tempo (3200)
```

### Metrics Flow

```
Service (8000/metrics)
  → Prometheus scrape
  → http://192.168.2.23:9090/metrics
  → Alloy (prometheus.scrape)
  → Alloy (prometheus.remote_write)
  → Prometheus (9090/api/v1/write)
```

### Logs Flow

```
Service logging
  → structlog.JSONRenderer()
  → stdout
  → Promtail (docker log driver)
  → Loki (3100)
```

---

## Complete Deployment Command

```bash
# On server 192.168.2.23

# 1. Create network
docker network create rag_net

# 2. Start Alloy
docker run -d \
  --name alloy \
  --network rag_net \
  -p 4317:4317 \
  -p 4318:4318 \
  -p 12345:12345 \
  -v $(pwd)/alloy-config.alloy:/etc/alloy/config.alloy:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  grafana/alloy:latest \
  run --server.http.listen-addr=0.0.0.0:12345 /etc/alloy/config.alloy

# 3. Verify
curl http://192.168.2.23:12345/ready
```

---

## Testing End-to-End

### 1. Send Test Trace

```bash
# From any service
curl -X POST http://192.168.2.23:8000/ingest \
  -F "doc_id=test" \
  -F "tenant=test" \
  -F "project=test" \
  -F "lang=en" \
  -F "file=@test.txt"
```

### 2. Check Tempo

```bash
# Wait a few seconds
sleep 5

# Search for trace
curl "http://192.168.2.23:3200/api/search?tags=service.name=ingestor"
```

### 3. Check Grafana

```
1. Open http://192.168.2.23:3001
2. Go to Tempo data source
3. Search: {service.namespace="hyperrag"}
4. Should see traces!
```

---

## Summary

✅ **All services are already configured** to send to `http://192.168.2.23:4317`  
✅ **No changes needed to service code**  
✅ **Just deploy Alloy** on the server  
✅ **Alloy will collect** traces, metrics, and logs automatically  

---

**Next Steps:**

1. Deploy Alloy on server (use provided docker-compose or manual deployment)
2. Start Alloy container
3. Verify data flow: Services → Alloy → Backends
4. Import Grafana dashboard
5. Start monitoring!

