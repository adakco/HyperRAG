# HyperRAG API Documentation

## 1. Document Management APIs

### 1.1 Document Ingestion
**Endpoint**: `POST /ingest`  
**Port**: 8000

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=sample-doc" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=fa" \
  -F "title=سند نمونه" \
  -F "file=@document.pdf"
```

**Response**:
```json
{
  "doc_id": "sample-doc",
  "version": "v1",
  "status": "ingested",
  "uri_raw": "s3://raw/acme/alpha/sample-doc/v1",
  "sha256": "abc123...",
  "file_size": 1024,
  "trace_id": "xyz789..."
}
```

### 1.2 Document Status
**Endpoint**: `GET /documents/{doc_id}/status`  
**Port**: 8000

```bash
curl "http://localhost:8000/documents/sample-doc/status"
```

**Response**:
```json
{
  "doc_id": "sample-doc",
  "version": "v1",
  "status": "completed",
  "error": null
}
```

## 2. Retrieval APIs

### 2.1 Document Search
**Endpoint**: `POST /retrieve`  
**Port**: 8002

```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "موضوع اصلی چیست؟",
    "lang": "fa",
    "tenant": "acme",
    "k_final": 5,
    "rerank": true
  }'
```

**Response**:
```json
{
  "results": [
    {
      "chunk_id": "chunk-1",
      "doc_id": "doc-1",
      "content": "...",
      "score": 0.95,
      "metadata": {
        "title": "...",
        "created_at": "..."
      }
    }
  ],
  "metadata": {
    "total_results": 10,
    "search_time_ms": 150
  }
}
```

### 2.2 Re-ranking
**Endpoint**: `POST /rerank`  
**Port**: 8011

```bash
curl -X POST "http://localhost:8011/rerank" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "موضوع اصلی چیست؟",
    "documents": ["..."],
    "lang": "fa",
    "tenant": "acme"
  }'
```

## 3. Agent APIs

### 3.1 Start Agent Session
**Endpoint**: `POST /sessions`  
**Port**: 8006

```bash
curl -X POST "http://localhost:8006/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is AI?",
    "lang": "en",
    "tenant": "acme",
    "token_budget": 4000
  }'
```

**Response**:
```json
{
  "session_id": "sess-123",
  "status": "active",
  "trace_id": "trace-456"
}
```

### 3.2 Get Session Status
**Endpoint**: `GET /sessions/{session_id}`  
**Port**: 8006

```bash
curl "http://localhost:8006/sessions/sess-123"
```

## 4. Memory APIs

### 4.1 Store Memory
**Endpoint**: `POST /store`  
**Port**: 8010

```bash
curl -X POST "http://localhost:8010/store" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "acme",
    "content": "...",
    "memory_type": "episodic",
    "lang": "en"
  }'
```

### 4.2 Retrieve Memories
**Endpoint**: `POST /retrieve`  
**Port**: 8010

```bash
curl -X POST "http://localhost:8010/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "...",
    "lang": "en",
    "tenant": "acme",
    "memory_type": "both"
  }'
```

## 5. Evaluation APIs

### 5.1 Evaluate Response
**Endpoint**: `POST /evaluate`  
**Port**: 8005

```bash
curl -X POST "http://localhost:8005/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "...",
    "answer": "...",
    "contexts": ["..."],
    "lang": "fa",
    "tenant": "acme"
  }'
```

### 5.2 Get Evaluation Results
**Endpoint**: `GET /evaluation/{session_id}/results`  
**Port**: 8005

```bash
curl "http://localhost:8005/evaluation/sess-123/results"
```

## 6. Policy APIs

### 6.1 Evaluate Policy
**Endpoint**: `POST /evaluate`  
**Port**: 8007

```bash
curl -X POST "http://localhost:8007/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "execute_agent",
    "tenant": "acme",
    "user_id": "user-123",
    "resource": "agent-1"
  }'
```

### 6.2 Get Audit Logs
**Endpoint**: `GET /audit-logs`  
**Port**: 8007

```bash
curl "http://localhost:8007/audit-logs?tenant=acme"
```

## 7. Costing APIs

### 7.1 Track Cost
**Endpoint**: `POST /track-cost`  
**Port**: 8008

```bash
curl -X POST "http://localhost:8008/track-cost" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "retrieval",
    "tenant": "acme",
    "cost_amount": 0.001
  }'
```

### 7.2 Get Budget Info
**Endpoint**: `GET /budget/{tenant}`  
**Port**: 8008

```bash
curl "http://localhost:8008/budget/acme"
```

## 8. Pack LongRAG APIs

### 8.1 Pack Contexts
**Endpoint**: `POST /pack`  
**Port**: 8009

```bash
curl -X POST "http://localhost:8009/pack" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "...",
    "contexts": ["..."],
    "lang": "en",
    "tenant": "acme",
    "max_tokens": 4000
  }'
```

## 9. Health Check APIs

All services expose a health check endpoint:

```bash
# Check service health
curl "http://localhost:{PORT}/health"

# Example for Ingestor
curl "http://localhost:8000/health"
```

**Response**:
```json
{
  "status": "healthy",
  "service": "service_name"
}
```

## 10. Metrics APIs

All services expose a Prometheus metrics endpoint:

```bash
# Get service metrics
curl "http://localhost:{PORT}/metrics"

# Example for Retriever
curl "http://localhost:8002/metrics"
```

## Authentication

All APIs require JWT authentication. Add the following header to your requests:

```bash
Authorization: Bearer <jwt_token>
```

## Error Handling

All APIs use standard HTTP status codes:

- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 429: Too Many Requests
- 500: Internal Server Error

Error response format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": {}
  }
}
```

## Rate Limiting

Default rate limits per tenant:

- Ingestion: 100 requests/minute
- Retrieval: 1000 requests/minute
- Agent Sessions: 100 sessions/minute
- Memory Operations: 500 requests/minute

## Monitoring

All APIs include:

- Request tracing (OpenTelemetry)
- Metrics (Prometheus)
- Logging (structured JSON)
- Audit trail

## Security

- All endpoints support mTLS
- Multi-tenant isolation
- OPA policy enforcement
- PII protection
- Rate limiting
- Input validation

## Support

For API support:
- Email: api@hyperrag.ai
- Documentation: https://docs.hyperrag.ai
- Status: https://status.hyperrag.ai
