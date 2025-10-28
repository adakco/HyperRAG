# Grafana 12 - Trace & Service Graph Setup Guide

**Last Updated:** 2025-10-26  
**Grafana Version:** 12.x  

---

## Overview

This guide explains how to configure Traces and Service Graph visualization in Grafana 12 for HyperRAG services.

---

## Prerequisites

- Grafana 12.x installed
- Tempo configured and running
- Alloy collecting traces from HyperRAG services
- Prometheus metrics for service graph

---

## Step 1: Configure Tempo Data Source

### Add Tempo to Grafana

1. Go to **Configuration > Data Sources**
2. Click **Add data source**
3. Select **Tempo**
4. Configure:

```
Name: Tempo
URL: http://tempo:3200
Trace Query Type: TraceQL
```

### Service Graph Metrics

Enable Tempo to generate service graph metrics:

```yaml
# In tempo.yml
metrics_generator:
  registry:
    external_labels:
      source: tempo
      cluster: hyperrag

overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs, span-metrics]
```

---

## Step 2: Import Dashboard

### Download Dashboard

```bash
# The dashboard file is located at:
platform/infra/grafana/dashboards/hyperrag-complete-dashboard.json
```

### Import to Grafana

1. Go to **Dashboards > Import**
2. Upload `hyperrag-complete-dashboard.json`
3. Select **Tempo** as the data source for traces
4. Select **Prometheus** as the data source for metrics
5. Click **Import**

---

## Step 3: Configure Trace View

### TraceQL Query Parameters

In the Trace panel, use these parameters:

```traceql
# Show all traces from HyperRAG services
{service.namespace="hyperrag"}

# Filter by specific service
{service.name="hyperrag_ingestor"}

# Filter by trace duration
{service.namespace="hyperrag"} | duration > 100ms

# Filter by error
{service.namespace="hyperrag"} | status = error

# Filter by tenant
{service.namespace="hyperrag"} | tenant = "test"
```

### Trace View Options

```json
{
  "options": {
    "query": "{service.namespace=\"hyperrag\"}",
    "searchType": "search"
  }
}
```

---

## Step 4: Configure Service Graph

### Enable Service Graph in Tempo

Add to `tempo.yml`:

```yaml
overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs]
      registry:
        external_labels:
          source: tempo
```

### Service Graph Metrics

Tempo generates these metrics:

- `traces_service_graph_request_total`
- `traces_service_graph_request_failed_total`
- `traces_service_graph_request_server_seconds_sum`
- `traces_service_graph_request_client_seconds_sum`

### Node Graph Configuration

```json
{
  "datasource": "Prometheus",
  "type": "nodeGraph",
  "fieldConfig": {
    "defaults": {
      "custom": {
        "nodeViz": {
          "arcs": [
            {
              "field": "traces_service_graph_request_total",
              "id": "Requests"
            }
          ],
          "edges": {
            "arcs": [
              {
                "field": "traces_service_graph_request_total",
                "id": "Requests"
              }
            ]
          }
        }
      }
    }
  }
}
```

---

## Step 5: Verifying Trace Collection

### Check Alloy is Collecting

```bash
# Check Alloy logs
docker logs alloy | grep "trace"

# Check traces in Tempo
curl http://192.168.2.23:3200/api/search?tags=service.namespace=hyperrag
```

### Check Metrics Generation

```bash
# Query Tempo service graph metrics
curl "http://192.168.2.23:9090/api/v1/query?query=traces_service_graph_request_total"
```

---

## Trace View Parameters (Grafana 12)

### Search Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `service.namespace` | Service namespace | `hyperrag` |
| `service.name` | Service name | `hyperrag_ingestor` |
| `status` | Trace status | `ok`, `error` |
| `duration` | Duration filter | `> 100ms` |
| `tenant` | Tenant filter | `test` |

### TraceQL Syntax

```traceql
# Basic filter
{service.namespace="hyperrag"}

# With duration
{service.namespace="hyperrag"} | duration > 500ms

# With status
{service.namespace="hyperrag"} | status = error

# Multiple conditions
{service.namespace="hyperrag"} | service.name="ingestor" | duration > 1s

# Regex support
{service.name=~".*ingestor.*"}
```

---

## Service Graph Parameters

### Node Attributes

```json
{
  "nodeSize": {
    "max": 100,
    "min": 10
  },
  "fieldConfig": {
    "defaults": {
      "custom": {
        "nodeViz": {
          "arcs": [
            {
              "field": "traces_service_graph_request_total",
              "id": "Requests",
              "legend": true
            }
          ],
          "edges": {
            "arcs": [
              {
                "field": "traces_service_graph_request_total",
                "id": "Requests"
              }
            ],
            "mainStat": [
              {
                "field": "traces_service_graph_request_server_seconds_sum"
              }
            ],
            "secondaryStat": [
              {
                "field": "traces_service_graph_request_total"
              }
            ]
          }
        }
      }
    }
  }
}
```

### Edge Attributes

- **Requests**: Total requests between services
- **Latency**: Duration of requests
- **Errors**: Failed requests

---

## Dashboard Panels

### 1. Request Rate (Timeseries)

```promql
sum(rate(http_requests_total[5m])) by (service)
```

### 2. Error Rate (Timeseries)

```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
```

### 3. Traces (Traces Panel)

```traceql
{service.namespace="hyperrag"}
```

### 4. Service Dependency Graph (NodeGraph)

```promql
# Automatic service discovery from Tempo metrics
traces_service_graph_request_total
```

---

## Troubleshooting

### Issue: No Traces Appearing

**Solution:**
```bash
# Check Alloy is receiving traces
curl http://192.168.2.23:12345/metrics | grep trace

# Check Tempo is receiving traces
curl http://192.168.2.23:3200/api/search?tags=service.namespace=hyperrag

# Check service is sending to Alloy
# In service code, verify OTLP endpoint: http://192.168.2.23:4317
```

### Issue: Service Graph Not Showing

**Solution:**
```bash
# Check Tempo metrics generator is enabled
curl http://192.168.2.23:3200/api/overrides

# Check metrics exist
curl "http://192.168.2.23:9090/api/v1/query?query=traces_service_graph_request_total"

# Verify tempo.yml has metrics_generator enabled
```

### Issue: TraceQL Not Working

**Solution:**
```traceql
# Use correct syntax
{service.namespace="hyperrag"}

# Not: service.namespace="hyperrag"
# Correct: {service.namespace="hyperrag"}
```

---

## Best Practices

### 1. Configure Sampling

```yaml
# In service configuration
sampling_ratio = 0.1  # Sample 10% of traces
```

### 2. Filter Noisy Traces

```traceql
# Only show traces > 100ms
{service.namespace="hyperrag"} | duration > 100ms

# Only show errors
{service.namespace="hyperrag"} | status = error
```

### 3. Add Custom Tags

```python
# In service code
span.set_attribute("tenant", "test")
span.set_attribute("project", "alpha")
```

### 4. Configure Retention

```yaml
# In tempo.yml
storage.trace:
  retention: 168h  # 7 days
```

---

## Example Queries

### Show Slow Traces

```traceql
{service.namespace="hyperrag"} | duration > 1s
```

### Show Error Traces

```traceql
{service.namespace="hyperrag"} | status = error
```

### Show Traces by Service

```traceql
{service.namespace="hyperrag", service.name="ingestor"}
```

### Show Traces with Specific Tag

```traceql
{service.namespace="hyperrag", tenant="test"}
```

---

## Conclusion

With Grafana 12, you now have:

- ✅ **Distributed tracing** with TraceQL
- ✅ **Service dependency graph** visualization
- ✅ **Unified observability** across metrics, logs, and traces
- ✅ **Performance monitoring** with latency breakdowns

---

**References:**
- [Grafana Traces Documentation](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/traces/)
- [TraceQL Syntax](https://grafana.com/docs/tempo/latest/traceql/)
- [Service Graphs](https://grafana.com/docs/tempo/latest/metrics-generator/service-graphs/)

