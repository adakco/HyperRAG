# HyperRAG Service Testing Guide

**Last Updated:** 2025-10-25  
**Version:** 1.0

---

## فهرست مطالب

1. [Quick Start](#quick-start)
2. [Service-by-Service Testing](#service-by-service-testing)
3. [End-to-End Pipeline Test](#end-to-end-pipeline-test)
4. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```bash
# Ensure all services are running
./start-services-host.sh

# Check service status
curl http://localhost:8000/health  # Ingestor
curl http://localhost:8001/health  # Normalizer
curl http://localhost:8002/health  # Retriever
curl http://localhost:8003/health  # Chunker
curl http://localhost:8004/health  # Embedder
```

---

## Service-by-Service Testing

### 1. Ingestor Service Test

**Endpoint:** `POST /ingest`

```bash
# Upload a test document
curl -X POST http://localhost:8000/ingest \
  -F "doc_id=test-doc-001" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=en" \
  -F "file=@test-document.txt"
```

**Expected Response:**
```json
{
    "doc_id": "test-doc-001",
    "version": 1761400000,
    "status": "success",
    "uri_raw": "s3://raw/acme/alpha/test-doc-001/1761400000",
    "sha256": "abc123...",
    "file_size": 1234,
    "trace_id": "uuid..."
}
```

**Verification:**
```bash
# Check MinIO
# Browse to http://192.168.2.23:9090 and navigate to 'raw' bucket

# Check PostgreSQL
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT * FROM documents WHERE doc_id='test-doc-001';"
```

---

### 2. Normalizer Service Test

**Endpoint:** `POST /normalize`

```bash
curl -X POST "http://localhost:8001/normalize?doc_id=test-doc-001&version=1761400000&uri_raw=s3://raw/acme/alpha/test-doc-001/1761400000&lang=en&tenant=acme"
```

**Expected Response:**
```json
{
    "doc_id": "test-doc-001",
    "version": "1761400000",
    "uri_clean": "s3://clean/acme/clean/test-doc-001/1761400000",
    "lang": "en",
    "normalized_text": "cleaned text content...",
    "pii_entities": [],
    "token_count": 150,
    "processing_time_ms": 117
}
```

**Verification:**
```bash
# Check MinIO for cleaned document
# Browse to http://192.168.2.23:9090 → 'clean' bucket

# Check PostgreSQL
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT doc_id, version, uri_clean FROM document_versions WHERE doc_id='test-doc-001';"
```

---

### 3. Chunker Service Test

**Endpoint:** `POST /chunk`

```bash
curl -X POST "http://localhost:8003/chunk?doc_id=test-doc-001&version=1761400000&uri_clean=s3://clean/acme/clean/test-doc-001/1761400000&lang=en&tenant=acme"
```

**Expected Response:**
```json
{
    "doc_id": "test-doc-001",
    "version": "1761400000",
    "lang": "en",
    "chunks": [
        {
            "chunk_index": 0,
            "content": "chunk content...",
            "token_count": 150,
            "char_count": 750,
            "lang": "en"
        }
    ],
    "total_chunks": 1,
    "total_tokens": 150,
    "processing_time_ms": 110,
    "uri_processed": "s3://clean/acme/chunked/test-doc-001/1761400000"
}
```

**Verification:**
```bash
# Check PostgreSQL chunks table
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT * FROM document_chunks WHERE doc_id='test-doc-001';"

# Check chunk count in document_versions
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT chunk_count FROM document_versions WHERE doc_id='test-doc-001';"
```

---

### 4. Embedder Service Test

**Endpoint:** `POST /embed`

```bash
curl -X POST "http://localhost:8004/embed?doc_id=test-doc-001&version=1761400000&uri_processed=s3://clean/acme/chunked/test-doc-001/1761400000&lang=en&tenant=acme&project=alpha"
```

**Expected Response:**
```json
{
    "doc_id": "test-doc-001",
    "version": "1761400000",
    "lang": "en",
    "embeddings_count": 1,
    "vector_dimension": 3072,
    "processing_time_ms": 4985
}
```

**Verification:**
```bash
# Check Qdrant
curl -X POST "http://192.168.2.23:6333/collections/documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 1, "filter": {"must": [{"key": "doc_id", "match": {"value": "test-doc-001"}}]}, "with_payload": true, "with_vector": true}'

# Check PostgreSQL for embedding IDs
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT chunk_id, embedding FROM document_chunks WHERE doc_id='test-doc-001';"
```

---

### 5. Retriever Service Test

**Endpoint:** `POST /retrieve`

```bash
curl -X POST http://localhost:8002/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "lang": "en",
    "tenant": "acme",
    "project": "alpha",
    "k_dense": 10,
    "k_final": 5
  }'
```

**Expected Response:**
```json
{
    "query": "test query",
    "results": [
        {
            "chunk_id": "test-doc-001_1761400000_0",
            "content": "chunk content...",
            "doc_id": "test-doc-001",
            "version": "1761400000",
            "score": 0.95
        }
    ],
    "total": 1,
    "processing_time_ms": 350,
    "trace_id": "uuid..."
}
```

**Verification:**
```bash
# Check Qdrant search
curl -X POST "http://192.168.2.23:6333/collections/documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "filter": {"must": [{"key": "tenant", "match": {"value": "acme"}}]}, "with_payload": true}'
```

---

## End-to-End Pipeline Test

### Automated Test Script

```bash
# Run complete pipeline test
python3 test-complete-pipeline.py
```

**Test Flow:**
1. ✅ Document Ingestion
2. ✅ Document Normalization
3. ✅ Document Chunking
4. ✅ Embedding Generation
5. ✅ Qdrant Verification
6. ✅ Document Retrieval

### Manual Step-by-Step Test

```bash
# Step 1: Ingest
INGEST_RESULT=$(curl -X POST http://localhost:8000/ingest \
  -F "doc_id=complete-test-001" \
  -F "tenant=test" \
  -F "project=complete-pipeline-test" \
  -F "lang=en" \
  -F "file=@test-doc.txt")

DOC_ID=$(echo $INGEST_RESULT | jq -r '.doc_id')
VERSION=$(echo $INGEST_RESULT | jq -r '.version')
URI_RAW=$(echo $INGEST_RESULT | jq -r '.uri_raw')

# Step 2: Normalize
NORMALIZE_RESULT=$(curl -X POST "http://localhost:8001/normalize?doc_id=$DOC_ID&version=$VERSION&uri_raw=$URI_RAW&lang=en&tenant=test")

URI_CLEAN=$(echo $NORMALIZE_RESULT | jq -r '.uri_clean')

# Step 3: Chunk
CHUNK_RESULT=$(curl -X POST "http://localhost:8003/chunk?doc_id=$DOC_ID&version=$VERSION&uri_clean=$URI_CLEAN&lang=en&tenant=test")

URI_PROCESSED=$(echo $CHUNK_RESULT | jq -r '.uri_processed')

# Step 4: Embed
curl -X POST "http://localhost:8004/embed?doc_id=$DOC_ID&version=$VERSION&uri_processed=$URI_PROCESSED&lang=en&tenant=test&project=complete-pipeline-test"

# Step 5: Retrieve
curl -X POST http://localhost:8002/retrieve \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"test query\",
    \"lang\": \"en\",
    \"tenant\": \"test\",
    \"project\": \"complete-pipeline-test\",
    \"k_dense\": 10,
    \"k_final\": 5
  }"
```

---

## Troubleshooting

### Service Not Responding

```bash
# Check if service is running
ps aux | grep {service_name}

# Check service logs
# Logs are typically in the terminal where service was started

# Restart service
./stop-services-host.sh
./start-services-host.sh
```

### MinIO Connection Issues

```bash
# Verify MinIO is accessible
curl http://192.168.2.23:9190/minio/health/live

# Check bucket access
aws --endpoint-url=http://192.168.2.23:9190 s3 ls s3://raw/
```

### PostgreSQL Connection Issues

```bash
# Test PostgreSQL connection
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT NOW();"

# Check document tables
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "\dt"
```

### Qdrant Connection Issues

```bash
# Check Qdrant health
curl http://192.168.2.23:6333/collections

# List collections
curl http://192.168.2.23:6333/collections/documents

# Check points
curl -X POST "http://192.168.2.23:6333/collections/documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true}'
```

### NATS Connection Issues

```bash
# Check NATS connectivity
curl http://192.168.2.23:8222/healthz

# View NATS streams (if JetStream enabled)
nats stream ls
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli -h 192.168.2.23 -p 6479 PING

# Check keys
redis-cli -h 192.168.2.23 -p 6479 KEYS "*"
```

---

## Common Error Scenarios

### Error: "Connection refused"

**Cause:** Service not running  
**Solution:**
```bash
./start-services-host.sh
```

### Error: "Column 'X' does not exist"

**Cause:** Database schema not updated  
**Solution:**
```bash
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -f create-schema.sql
```

### Error: "NoSuchKey" from MinIO

**Cause:** Document not found at specified path  
**Solution:** Check URI format matches MinIO bucket structure

### Error: "Format error in JSON body"

**Cause:** Invalid UUID format for Qdrant point IDs  
**Solution:** Use `str(uuid.uuid4())` for point IDs

### Error: "0 results returned from retriever"

**Cause:** Project field mismatch or filter too restrictive  
**Solution:** 
- Ensure `project` field is set in embedder
- Verify filters match stored metadata
- Check Qdrant payload includes required fields

---

## Performance Testing

### Load Test

```bash
# Simple load test with Apache Bench
ab -n 100 -c 10 -p test-data.json http://localhost:8000/ingest
```

### Monitoring

```bash
# Prometheus metrics
curl http://localhost:9090/metrics

# Grafana dashboards
# Browse to http://localhost:3000
```

---

## Success Criteria

### Each Service Should:

1. ✅ Accept valid input without errors
2. ✅ Return expected output format
3. ✅ Update database correctly
4. ✅ Store files in correct MinIO locations
5. ✅ Publish events to NATS
6. ✅ Log operations with structured logging
7. ✅ Track metrics in Prometheus

### End-to-End Pipeline Should:

1. ✅ Process document from ingestion to retrieval
2. ✅ Return relevant results for test queries
3. ✅ Complete within acceptable latency (< 10s for full pipeline)
4. ✅ Maintain data consistency across all storage systems

---

**For more details, see:**
- [Services-Documentation.md](Services-Documentation.md) - Service details
- [Technical-Spec.md](Technical-Spec.md) - Technical specifications
- [Architecture.md](Architecture.md) - Architecture overview

