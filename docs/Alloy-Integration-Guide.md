# Grafana Alloy Integration Guide for HyperRAG

**Last Updated:** 2025-10-25  
**Purpose:** Connect HyperRAG services to Alloy for complete observability

---

## Overview

This guide shows how to integrate HyperRAG services running on `192.168.2.23` with Grafana Alloy for unified metrics, logs, and traces collection.

---

## Architecture

```
HyperRAG Services (192.168.2.23)
├── Ingestor (8000)
├── Normalizer (8001)
├── Retriever (8002)
├── Chunker (8003)
├── Embedder (8004)
├── Evaluator (8005)
├── Agent-Orch (8006)
├── Policy (8007)
├── Costing (8008)
├── Pack-LongRAG (8009)
├── Memory (8010)
└── Reranker (8011)
         ↓
    Grafana Alloy (4317, 4318)
         ↓
    ┌─────────────────┐
    │   Prometheus    │ Metrics
    │   Loki          │ Logs
    │   Tempo         │ Traces
    └─────────────────┘
         ↓
    Grafana Dashboard
```

---

## Setup Instructions

### Step 1: Update Services to Send to Alloy

Update service settings to point to Alloy:

```python
# In service Settings (e.g., platform/services/ingestor/main.py)
class Settings(BaseSettings):
    # Change OTEL endpoint to Alloy
    otel_endpoint: str = "http://192.168.2.23:4317"
```

### Step 2: Update Alloy Configuration

Edit `platform/infra/compose/alloy-config.alloy`:

```alloy
local.SERVER_URL = "192.168.2.23"

prometheus.scrape "hyperrag_services" {
    targets = [
        {"__address__" = "192.168.2.23:8000", "job" = "hyperrag_ingestor"},
        {"__address__" = "192.168.2.23:8001", "job" = "hyperrag_normalizer"},
        # ... add all services
    ]
}
```

### Step 3: Start All Services

```bash
# Start infrastructure (including Alloy)
cd platform/infra/compose
docker-compose -f docker-compose.with-alloy.yml up -d

# Start HyperRAG services
cd /Users/daniel/Documents/Hyper-RAG
./start-services-host.sh
```

### Step 4: Verify Alloy is Collecting

```bash
# Check Alloy logs
docker logs -f alloy

# Check endpoints
curl http://192.168.2.23:12345/ready
curl http://192.168.2.23:12345/metrics
```

---

## Configuration Details

### Alloy OTLP Receivers

```alloy
otelcol.receiver.otlp "default" {
    protocol {
        grpc {
            endpoint = "0.0.0.0:4317"
        }
        http {
            endpoint = "0.0.0.0:4318"
        }
    }
}
```

### Service Scraping

Alloy scrapes metrics from HyperRAG services using Prometheus metrics:

```alloy
prometheus.scrape "hyperrag_services" {
    targets = [
        {"__address__" = "192.168.2.23:8000", "job" = "hyperrag_ingestor"},
    ]
    
    forward_to = [prometheus.remote_write.prometheus.receiver]
    
    scrape_interval = "10s"
}
```

### Log Collection

Alloy collects logs from Docker containers:

```alloy
discovery.docker "all_containers" {
    host = "unix:///var/run/docker.sock"
    filters {
        label = ["alloy.exporter.discovery=true"]
    }
}

loki.write "endpoint" {
    endpoint = "http://loki:3100/loki/api/v1/push"
}
```

### Trace Collection

Alloy forwards traces to Tempo:

```alloy
otelcol.exporter.otlp "tempo" {
    endpoint = "http://tempo:4317"
    
    output {
        traces = [otelcol.processor.batch.default.input]
    }
}
```

---

## Service Integration

### Example: Ingestor Service

```python
# platform/services/ingestor/main.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure Alloy endpoint
otlp_exporter = OTLPSpanExporter(
    endpoint="http://192.168.2.23:4317",
    insecure=True
)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

---

## Grafana Dashboard Setup

### Access Dashboard

1. Open Grafana: http://192.168.2.23:3001
2. Login: `admin` / `admin`
3. Import Dashboard: Use `hyperrag-alloy-dashboard.json`

### Dashboard Panels

- **Request Rate**: Total requests per second by service
- **Error Rate**: 5xx errors by service
- **Processing Latency**: p95 latency by service
- **Service Health**: Up/down status of all services
- **Top Services**: Most active services by request count

---

## Monitoring Queries

### Service Health

```promql
up{job=~".*hyperrag.*"}
```

### Request Rate

```promql
sum(rate(http_requests_total[5m])) by (service)
```

### Error Rate

```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
```

### Latency (p95)

```promql
histogram_quantile(0.95, 
    sum(rate(hyperrag_processing_duration_seconds_bucket[5m])) 
    by (le, service)
)
```

---

## Troubleshooting

### Issue: No metrics appearing

**Solution:**
```bash
# Check if services are exposing metrics
curl http://192.168.2.23:8000/metrics

# Check if Alloy is scraping
curl http://192.168.2.23:12345/metrics

# Check Prometheus targets
curl http://192.168.2.23:9090/api/v1/targets
```

### Issue: Traces not appearing

**Solution:**
```bash
# Check if services send to Alloy
# Verify OTLP endpoint in service configuration
curl -v http://192.168.2.23:4317

# Check Alloy logs
docker logs alloy
```

### Issue: Logs not appearing in Loki

**Solution:**
```bash
# Check Loki health
curl http://192.168.2.23:3100/ready

# Check Alloy log forwarding
docker logs alloy | grep loki
```

---

## Performance Metrics

Expected metrics:

| Metric | Target |
|--------|--------|
| Scrape Interval | 10s |
| OTLP Batch Size | 1024 |
| Retention (Metrics) | 15 days |
| Retention (Traces) | 7 days |
| Retention (Logs) | 7 days |

---

## Advanced Configuration

### Custom Labels

```alloy
prometheus.scrape "hyperrag_services" {
    # Add custom labels
    relabel {
        source_labels = ["instance"]
        target_label = "server"
        replacement = "192.168.2.23"
    }
}
```

### Filtering

```alloy
# Only collect from specific services
prometheus.scrape "hyperrag_core" {
    targets = prometheus.exporter.unix.hyperrag.targets
    
    filter = {
        service = ["ingestor", "chunker", "retriever"]
    }
}
```

---

## Conclusion

With Alloy integration, you get:
- ✅ Unified metrics from all HyperRAG services
- ✅ Centralized log collection
- ✅ Distributed tracing
- ✅ Single dashboard for all observability
- ✅ Reduced operational overhead

---

**Next Steps:**
1. Deploy updated configuration
2. Start services
3. Import Grafana dashboard
4. Monitor system health

