# HyperRAG Incident Response Runbooks

## 1. High Retrieval Latency

### Symptoms
- p95 latency > 2s for fast mode
- p95 latency > 4s for secure mode
- Increased error rates in retrieval operations

### Diagnosis
1. Check Qdrant metrics in Grafana
2. Verify CPU/Memory usage
3. Check network latency between services
4. Review recent configuration changes

### Resolution
1. Increase `ef_search` in Qdrant:
```bash
curl -X POST http://localhost:6333/collections/documents/config \
  -H 'Content-Type: application/json' \
  -d '{"ef_search": 200}'
```

2. Reduce `k` parameters if needed:
```python
retrieval_request = {
    "k_dense": 10,  # Reduced from 20
    "k_sparse": 10, # Reduced from 20
    "k_final": 5    # Reduced from 10
}
```

3. Enable aggressive caching:
```bash
redis-cli
> CONFIG SET maxmemory-policy allkeys-lru
> CONFIG SET maxmemory "2gb"
```

## 2. PII Detection Alert

### Symptoms
- PII detection alerts in monitoring
- Increased PII entity count in logs
- Failed document processing

### Diagnosis
1. Check normalizer logs
2. Review document processing status
3. Verify PII detection patterns

### Resolution
1. Enable secure processing mode:
```bash
curl -X POST http://localhost:8001/config \
  -H 'Content-Type: application/json' \
  -d '{"processing_mode": "secure", "pii_threshold": "strict"}'
```

2. Re-process affected documents:
```bash
curl -X POST http://localhost:8001/reprocess \
  -H 'Content-Type: application/json' \
  -d '{"doc_ids": ["affected-doc-1", "affected-doc-2"]}'
```

3. Update PII patterns if needed:
```bash
# Update PII detection rules
vi platform/services/normalizer/config/pii_patterns.json
# Restart normalizer service
./stop-services.sh
./start-services.sh
```

## 3. Token Budget Overflow

### Symptoms
- Cost alerts in monitoring
- Failed agent sessions
- High token usage warnings

### Diagnosis
1. Check cost tracking metrics
2. Review agent session logs
3. Analyze token usage patterns

### Resolution
1. Enable budget controls:
```bash
curl -X POST http://localhost:8008/config \
  -H 'Content-Type: application/json' \
  -d '{"enforce_budget": true, "alert_threshold": 0.8}'
```

2. Activate cost optimization:
```bash
# Enable cost optimization features
curl -X POST http://localhost:8006/config \
  -H 'Content-Type: application/json' \
  -d '{
    "use_cheaper_models": true,
    "cache_aggressively": true,
    "optimize_token_usage": true
  }'
```

3. Set hard limits:
```bash
# Update budget limits
curl -X POST http://localhost:8008/limits \
  -H 'Content-Type: application/json' \
  -d '{
    "max_tokens_per_request": 2000,
    "max_cost_per_session": 0.05,
    "daily_budget": 10.0
  }'
```

## 4. Agent Loop Failure

### Symptoms
- Failed agent sessions
- Timeout errors
- Stuck in decision loops

### Diagnosis
1. Check agent orchestrator logs
2. Review tool execution history
3. Verify service health status

### Resolution
1. Reset agent state:
```bash
curl -X POST http://localhost:8006/sessions/{session_id}/reset \
  -H 'Content-Type: application/json'
```

2. Configure circuit breakers:
```bash
# Update circuit breaker settings
curl -X POST http://localhost:8006/config \
  -H 'Content-Type: application/json' \
  -d '{
    "max_steps": 5,
    "timeout_seconds": 30,
    "failure_threshold": 3
  }'
```

3. Enable fallback mode:
```bash
# Activate fallback strategies
curl -X POST http://localhost:8006/config \
  -H 'Content-Type: application/json' \
  -d '{
    "use_fallback": true,
    "simplified_mode": true
  }'
```

## 5. Persian Text Encoding Issues

### Symptoms
- Mojibake in Persian text
- Failed RTL processing
- Incorrect character display

### Diagnosis
1. Check text encoding in logs
2. Verify UTF-8 handling
3. Review RTL processing

### Resolution
1. Force UTF-8 encoding:
```bash
# Update normalizer settings
curl -X POST http://localhost:8001/config \
  -H 'Content-Type: application/json' \
  -d '{
    "force_utf8": true,
    "rtl_enabled": true
  }'
```

2. Fix RTL rendering:
```bash
# Update UI settings
vi platform/ui/config/rtl.json
# Restart UI services
./restart-ui.sh
```

3. Reprocess affected documents:
```bash
curl -X POST http://localhost:8001/reprocess \
  -H 'Content-Type: application/json' \
  -d '{
    "doc_ids": ["affected-doc"],
    "force_encoding": "utf-8",
    "rtl_mode": true
  }'
```

## 6. Memory System Overload

### Symptoms
- High memory usage
- Slow memory retrieval
- Failed memory operations

### Diagnosis
1. Check memory service metrics
2. Review memory usage patterns
3. Verify storage capacity

### Resolution
1. Clean old memories:
```bash
# Run memory cleanup
curl -X POST http://localhost:8010/cleanup \
  -H 'Content-Type: application/json' \
  -d '{
    "older_than_days": 30,
    "memory_type": "episodic"
  }'
```

2. Optimize memory storage:
```bash
# Configure memory optimization
curl -X POST http://localhost:8010/config \
  -H 'Content-Type: application/json' \
  -d '{
    "compression_enabled": true,
    "deduplication_enabled": true
  }'
```

3. Set retention policies:
```bash
# Update retention settings
curl -X POST http://localhost:8010/retention \
  -H 'Content-Type: application/json' \
  -d '{
    "episodic_days": 30,
    "semantic_days": 90,
    "auto_cleanup": true
  }'
```

## Emergency Contacts

- **System Administrator**: admin@hyperrag.ai
- **Security Team**: security@hyperrag.ai
- **DevOps Lead**: devops@hyperrag.ai
- **Persian Language Expert**: persian@hyperrag.ai

## Monitoring URLs

- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686
- Langfuse: http://localhost:3001

## Service Health Check

```bash
# Check all services
./test-system.py --health-check

# Check specific service
curl http://localhost:{PORT}/health
```
