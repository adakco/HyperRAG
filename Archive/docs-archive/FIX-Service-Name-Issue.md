# Fixing Unknown Service Issue in Grafana

**Problem:** Traces show as `unknown_service` instead of actual service names  
**Root Cause:** OTEL TracerProvider not configured with `service.name` resource attribute

---

## Solution

Add `service.name` attribute to OTEL TracerProvider configuration in each service.

### Current Code (Incorrect)

```python
# Configure OpenTelemetry
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

### Fixed Code (Correct)

```python
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

# Configure OpenTelemetry
resource = Resource.create(attributes={SERVICE_NAME: "hyperrag-ingestor"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://192.168.2.23:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

---

## Required Changes

### For Each Service

Update `platform/services/{service_name}/main.py`:

1. **Add import:**
```python
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
```

2. **Replace TracerProvider initialization:**
```python
# Before
trace.set_tracer_provider(TracerProvider())

# After
resource = Resource.create(attributes={SERVICE_NAME: f"hyperrag-{service_name}"})
trace.set_tracer_provider(TracerProvider(resource=resource))
```

### Service Names Mapping

| Service File | Service Name |
|-------------|--------------|
| `platform/services/ingestor/main.py` | `hyperrag-ingestor` |
| `platform/services/normalizer/main.py` | `hyperrag-normalizer` |
| `platform/services/chunker/main.py` | `hyperrag-chunker` |
| `platform/services/embedder/main.py` | `hyperrag-embedder` |
| `platform/services/retriever/main.py` | `hyperrag-retriever` |
| `platform/services/reranker/main.py` | `hyperrag-reranker` |
| `platform/services/evaluator/main.py` | `hyperrag-evaluator` |
| `platform/services/agent-orch/main.py` | `hyperrag-agent-orch` |
| `platform/services/policy/main.py` | `hyperrag-policy` |
| `platform/services/costing/main.py` | `hyperrag-costing` |
| `platform/services/pack.longrag/main.py` | `hyperrag-pack-longrag` |
| `platform/services/memory.memorag/main.py` | `hyperrag-memory` |

---

## Automated Fix Script

Create a script to fix all services at once:

```python
# fix-service-names.py
import re
import os

SERVICES = {
    'ingestor': 'hyperrag-ingestor',
    'normalizer': 'hyperrag-normalizer',
    'chunker': 'hyperrag-chunker',
    'embedder': 'hyperrag-embedder',
    'retriever': 'hyperrag-retriever',
    'reranker': 'hyperrag-reranker',
    'evaluator': 'hyperrag-evaluator',
    'agent-orch': 'hyperrag-agent-orch',
    'policy': 'hyperrag-policy',
    'costing': 'hyperrag-costing',
    'pack.longrag': 'hyperrag-pack-longrag',
    'memory.memorag': 'hyperrag-memory',
}

for service_name, service_label in SERVICES.items():
    file_path = f'platform/services/{service_name}/main.py'
    
    if not os.path.exists(file_path):
        continue
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Add import if not exists
    if 'from opentelemetry.sdk.resources import Resource, SERVICE_NAME' not in content:
        content = content.replace(
            'from opentelemetry.sdk.trace import TracerProvider',
            'from opentelemetry.sdk.trace import TracerProvider\nfrom opentelemetry.sdk.resources import Resource, SERVICE_NAME'
        )
    
    # Replace TracerProvider initialization
    content = re.sub(
        r'trace\.set_tracer_provider\(TracerProvider\(\)\)',
        f'resource = Resource.create(attributes={{SERVICE_NAME: "{service_label}"}})\ntrace.set_tracer_provider(TracerProvider(resource=resource))',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f'✅ Fixed {service_name}')
```

---

## After Fixing

After applying the fix:

1. **Restart all services**
2. **Check in Grafana:**
   - Query: `{service.name="hyperrag-ingestor"}`
   - Should see traces with proper service names
3. **Service Graph will populate** with all services

---

## Additional Alloy Configuration

The Alloy config also needs to add resource attributes:

```alloy
otelcol.processor.resource "add_service_name" {
  attributes {
    key = "service.namespace"
    value = "hyperrag"
    
    action = "insert"
  }
  
  attributes {
    key = "deployment.environment"
    value = "production"
    
    action = "insert"
  }
  
  output {
    traces = [otelcol.exporter.otlp.to_tempo.input]
  }
}
```

Then update the receiver output:

```alloy
otelcol.receiver.otlp "default" {
  output {
    traces  = [otelcol.processor.resource.add_service_name.input]
    metrics = [otelcol.exporter.prometheus.to_prometheus.input]
    logs    = [otelcol.exporter.loki.to_loki.input]
  }
}
```

---

## Verification

After fixing, verify:

```bash
# Check traces in Tempo
curl "http://192.168.2.23:3200/api/search?tags=service.name%3Dhyperrag-ingestor"

# Should return traces with proper service names
```

---

## Summary

✅ **Problem**: Traces show as `unknown_service`  
✅ **Solution**: Add `SERVICE_NAME` to TracerProvider resource  
✅ **Files to fix**: 12 service files in `platform/services/`  
✅ **Result**: Service graph will show all HyperRAG services  

