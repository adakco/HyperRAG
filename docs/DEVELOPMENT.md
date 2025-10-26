# HyperRAG Development Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- Git
- Make

### Setup Development Environment

1. **Clone Repository**
```bash
git clone <repository-url>
cd hyperrag
```

2. **Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. **Install Dependencies**
```bash
# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

4. **Start Infrastructure Services**
```bash
# Start required services
./start-services.sh
```

## 🏗️ Project Structure

```
/platform
├── /infra                 # Infrastructure configuration
│   ├── /compose          # Docker Compose files
│   ├── /helmfile         # Kubernetes/Helm configuration
│   ├── /otel             # OpenTelemetry configuration
│   └── /grafana          # Grafana dashboards
├── /contracts            # Service contracts and schemas
│   ├── /cloudevents      # CloudEvent schemas
│   ├── /mcp              # MCP tool schemas
│   └── /rego             # OPA policies
├── /services             # Microservices
│   ├── /ingestor         # Document ingestion
│   ├── /normalizer       # Text normalization
│   ├── /chunker          # Text chunking
│   ├── /embedder         # Vector embedding
│   ├── /retriever        # Document retrieval
│   ├── /evaluator        # Quality evaluation
│   ├── /agent-orch       # Agent orchestration
│   ├── /policy           # Access control
│   ├── /costing          # Cost tracking
│   ├── /pack.longrag     # Long context
│   ├── /memory.memorag   # Memory management
│   └── /reranker         # Re-ranking
└── /ops                  # Operations
    ├── /runbooks         # Incident response
    └── /playbooks        # Deployment guides
```

## 💻 Development Workflow

### 1. Service Development

Each service follows a standard structure:
```
/service-name
├── main.py              # Service entry point
├── requirements.txt     # Dependencies
├── Dockerfile          # Container definition
└── tests/              # Unit tests
```

### 2. Running Tests

```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=. tests/
```

### 3. Code Style

```bash
# Format code
black .

# Check style
flake8

# Sort imports
isort .
```

### 4. Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## 🔧 Service Development

### 1. Creating a New Service

```bash
# Create service directory
mkdir platform/services/new-service
cd platform/services/new-service

# Create basic files
touch main.py requirements.txt Dockerfile
mkdir tests
```

### 2. Service Template

```python
"""
Service Template
Description of the service
"""

import asyncio
import structlog
from fastapi import FastAPI
from opentelemetry import trace

# Configure logging
logger = structlog.get_logger()

# Configure tracing
tracer = trace.get_tracer(__name__)

# Create FastAPI app
app = FastAPI(
    title="Service Name",
    description="Service description",
    version="1.0.0"
)

# Add routes
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
```

### 3. Adding OpenTelemetry

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Add instrumentor
FastAPIInstrumentor.instrument_app(app)
```

### 4. Adding Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

# Define metrics
request_counter = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)
```

## 📊 Monitoring Development

### 1. Adding Custom Metrics

```python
# Counter for operations
operation_counter = Counter(
    'service_operations_total',
    'Total number of operations',
    ['operation', 'status']
)

# Histogram for duration
operation_duration = Histogram(
    'service_operation_duration_seconds',
    'Operation duration in seconds',
    ['operation']
)

# Use in code
operation_counter.labels(
    operation='process',
    status='success'
).inc()

with operation_duration.labels(
    operation='process'
).time():
    # Do work
    pass
```

### 2. Adding Traces

```python
with tracer.start_as_current_span("operation_name") as span:
    span.set_attribute("key", "value")
    # Do work
```

### 3. Structured Logging

```python
logger.info("Operation completed",
            operation="process",
            duration_ms=150,
            status="success")

logger.error("Operation failed",
             operation="process",
             error=str(e),
             status="error")
```

## 🔒 Security Development

### 1. Adding OPA Policies

```rego
package hyperrag.policy

default allow = false

allow {
    input.tenant == input.jwt.claims.tenant
}
```

### 2. Adding Authentication

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Validate token
        payload = jwt.decode(token, settings.jwt_secret)
        return payload
    except:
        raise HTTPException(status_code=401)
```

### 3. Adding Authorization

```python
from fastapi import Security

async def check_permission(
    user = Depends(get_current_user),
    permission: str = "read"
):
    if permission not in user.permissions:
        raise HTTPException(status_code=403)
    return True

@app.get("/protected")
async def protected_route(
    _: bool = Depends(check_permission)
):
    return {"status": "success"}
```

## 📝 Testing Guidelines

### 1. Unit Tests

```python
import pytest
from fastapi.testclient import TestClient

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
```

### 2. Integration Tests

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_full_pipeline():
    # Test complete flow
    doc_id = "test-doc"
    
    # Ingest document
    ingest_result = await ingest_document(doc_id)
    assert ingest_result.status == "success"
    
    # Process document
    process_result = await process_document(doc_id)
    assert process_result.status == "success"
```

### 3. Performance Tests

```python
import asyncio
import time

async def test_performance():
    start_time = time.time()
    
    # Run parallel requests
    tasks = []
    for i in range(100):
        task = asyncio.create_task(process_request())
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    assert duration < 5.0  # Should complete in 5 seconds
```

## 🚀 Deployment

### 1. Building Images

```bash
# Build service image
docker build -t hyperrag/service-name .

# Push to registry
docker push hyperrag/service-name
```

### 2. Local Deployment

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f service-name
```

### 3. Kubernetes Deployment

```bash
# Deploy with Helm
cd platform/infra/helmfile
helmfile apply

# Check status
kubectl get pods -n hyperrag
```

## 📚 Documentation

### 1. API Documentation

- Use OpenAPI/Swagger annotations
- Keep examples up to date
- Include error responses
- Document authentication

### 2. Code Documentation

- Add docstrings to all functions
- Explain complex logic
- Include usage examples
- Document configuration

## 🐛 Debugging

### 1. Local Debugging

```bash
# Enable debug logging
export LOG_LEVEL=debug

# Run with debugger
python -m debugpy --listen 5678 main.py
```

### 2. Production Debugging

```bash
# Check logs
kubectl logs -f pod-name

# Get traces
curl http://localhost:16686

# Check metrics
curl http://localhost:9090
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Add tests
5. Submit pull request

## 📖 Additional Resources

- [Architecture Documentation](../Architecture.md)
- [Technical Specification](../Technical-Spec.md)
- [API Documentation](./API.md)
- [Deployment Guide](../platform/ops/playbooks/deployment.md)

## 🆘 Support

- **Technical Issues**: tech@hyperrag.ai
- **Documentation**: docs@hyperrag.ai
- **Security**: security@hyperrag.ai
