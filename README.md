# MCP-Native Agentic HyperRAG

A comprehensive RAG (Retrieval-Augmented Generation) system built with MCP (Model-Controller-Provider) architecture, supporting both Persian and English languages with enterprise-grade features.

## 🏗️ Architecture Overview

This system implements a three-phase approach:
1. **Phase 1**: Professional RAG with hybrid search and re-ranking
2. **Phase 2**: Long-context management with intelligent packing
3. **Phase 3**: Agentic execution with decision-making loops

### Core Components

- **Document Ingestion**: Multi-language document processing with PII removal
- **Intelligent Chunking**: Language-specific text segmentation
- **Hybrid Retrieval**: Dense + sparse vector search with RRF
- **Re-ranking**: Cross-encoder models for relevance scoring
- **Multi-tenant Security**: OPA policies and tenant isolation
- **Observability**: Comprehensive monitoring with OTEL, Grafana, and Langfuse

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose (for Docker mode)
- Python 3.9+ (for Host mode)
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Hyper-RAG
   ```

2. **Choose your deployment mode**:

   #### Option A: Docker Mode (Recommended for development)
   ```bash
   ./start-services.sh
   ```

   #### Option B: Host Mode (Recommended for production)
   ```bash
   # Make sure your infrastructure is running on 192.168.2.23
   # Then start services directly on host:
   ./start-services-host.sh
   ```

3. **Verify services are running**:

   **Docker Mode:**
   ```bash
   # Check service health
   curl http://localhost:8000/health  # Ingestor
   curl http://localhost:8001/health  # Chunker
   curl http://localhost:8002/health  # Retriever
   curl http://localhost:8004/health  # Embedder
   curl http://localhost:8005/health  # Evaluator
   curl http://localhost:8006/health  # Agent-Orch
   ```

   **Host Mode:**
   ```bash
   # Services run on the same ports but connect to infrastructure on 192.168.2.23
   curl http://localhost:8000/health  # Ingestor
   curl http://localhost:8001/health  # Chunker
   curl http://localhost:8002/health  # Retriever
   curl http://localhost:8004/health  # Embedder
   curl http://localhost:8005/health  # Evaluator
   curl http://localhost:8006/health  # Agent-Orch
   ```

### Service URLs

#### Application Services (Host Mode)
| Service | URL | Description |
|---------|-----|-------------|
| Ingestor API | http://localhost:8000 | Document ingestion |
| Chunker API | http://localhost:8001 | Intelligent text chunking |
| Retriever API | http://localhost:8002 | Hybrid search & re-ranking |
| Embedder API | http://localhost:8004 | Vector embedding generation |
| Evaluator API | http://localhost:8005 | RAGAS quality assessment |
| Agent-Orch API | http://localhost:8006 | MCP-Native agent orchestration |
| Normalizer API | http://localhost:8007 | PII removal & text normalization |
| Costing API | http://localhost:8008 | Cost tracking & billing |
| Reranker API | http://localhost:8009 | Cross-encoder re-ranking |
| Pack-LRAG API | http://localhost:8010 | Long-context packing |
| Policy API | http://localhost:8011 | Security & access control |
| Memory-MCP API | http://localhost:8012 | Episodic memory management |

#### Infrastructure Services (Running on 192.168.2.23)
| Service | URL | Description |
|---------|-----|-------------|
| MinIO Console | http://192.168.2.23:9090 | Object storage (admin/password123) |
| Qdrant Dashboard | http://192.168.2.23:6333/dashboard | Vector database |
| Neo4j Browser | http://192.168.2.23:7474 | Knowledge graph (neo4j/Adakpro123) |
| Grafana | http://192.168.2.23:3001 | Monitoring dashboard |
| Prometheus | http://192.168.2.23:9095 | Metrics collection |
| Tempo | http://192.168.2.23:3200 | Distributed tracing |
| Loki | http://192.168.2.23:3100 | Log aggregation |
| Langfuse | http://192.168.2.23:3000 | AI quality monitoring |
| PostgreSQL | 192.168.2.23:5432 | Metadata database (langfuse/Adakpro123) |
| NATS Monitor | http://192.168.2.23:8222 | Message queue monitoring |

## 📚 Usage Examples

### 1. Document Ingestion

```bash
# Ingest an English document
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=sample-doc-1" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=en" \
  -F "title=Sample English Document" \
  -F "file=@sample.txt"

# Ingest a Persian document
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=sample-doc-2" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=fa" \
  -F "title=سند نمونه فارسی" \
  -F "file=@sample_fa.txt"
```

### 2. Document Retrieval

```bash
# Search in English
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic?",
    "lang": "en",
    "tenant": "acme",
    "k_final": 5,
    "rerank": true
  }'

# Search in Persian
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

### 3. Check Document Status

```bash
# Check processing status
curl "http://localhost:8000/documents/sample-doc-1/status"
```

## 🔧 Configuration

### Environment Variables

Each service can be configured using environment variables:

```bash
# Database
DATABASE_URL=postgresql://hyperrag:password123@localhost:5432/hyperrag

# Redis
REDIS_URL=redis://localhost:6379

# NATS
NATS_URL=nats://localhost:4222

# Qdrant
QDRANT_URL=http://localhost:6333

# MinIO/S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123

# Models
PERSIAN_EMBEDDING_MODEL=HooshvareLab/bert-fa-base-uncased
ENGLISH_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Chunking Parameters

```bash
# Chunk size and overlap
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_CHUNK_SIZE=2000
MIN_CHUNK_SIZE=100
```

## 🏛️ Architecture Details

### Data Flow

1. **Ingestion**: Documents are uploaded and stored in MinIO
2. **Normalization**: PII removal and text normalization
3. **Chunking**: Language-specific text segmentation
4. **Embedding**: Vector generation using language-specific models
5. **Indexing**: Storage in Qdrant with metadata
6. **Retrieval**: Hybrid search with RRF and re-ranking

### Multi-tenant Security

- **Tenant Isolation**: Row-level security in PostgreSQL
- **Access Control**: OPA policies for fine-grained permissions
- **Data Encryption**: mTLS between services
- **Audit Trail**: Complete operation logging

### Language Support

#### Persian (فارسی)
- **Text Processing**: Hazm library for normalization
- **Embedding Model**: `HooshvareLab/bert-fa-base-uncased`
- **Chunking**: Sentence-aware segmentation
- **RTL Support**: Proper text rendering

#### English
- **Text Processing**: SpaCy and standard libraries
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Chunking**: Recursive character splitting
- **Re-ranking**: Cross-encoder models

## 📊 Monitoring & Observability

### Metrics

- **Retrieval Quality**: Faithfulness, Recall@10
- **Performance**: p95 latency, throughput
- **Cost**: Token usage, embedding costs
- **Reliability**: Success rates, error counts

### Dashboards

- **Grafana**: System metrics and performance
- **Langfuse**: AI quality and evaluation
- **Jaeger**: Distributed tracing
- **Prometheus**: Raw metrics collection

### SLO Targets

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Faithfulness (EN) | ≥ 0.88 | < 0.80 |
| Faithfulness (FA) | ≥ 0.85 | < 0.78 |
| Recall@10 | ≥ 0.90 | < 0.85 |
| p95 Latency (Fast) | ≤ 1.5s | > 2s |
| p95 Latency (Secure) | ≤ 3s | > 4s |
| Cost per Query | ≤ $0.002 | > $0.003 |

## 🔒 Security Features

### PII Protection
- **Detection**: Presidio analyzer for multiple languages
- **Anonymization**: Automatic PII replacement
- **Audit**: Complete PII detection logging

### Access Control
- **Authentication**: JWT with OIDC integration
- **Authorization**: ABAC with OPA policies
- **Tenant Isolation**: Complete data separation

### Data Protection
- **Encryption**: SSE-KMS for object storage
- **Network**: mTLS between all services
- **Compliance**: WORM storage for audit trails

## 🧪 Testing

### Unit Tests
```bash
# Run tests for each service
cd platform/services/ingestor
python -m pytest tests/

cd ../retriever
python -m pytest tests/
```

### Integration Tests
```bash
# Run end-to-end tests
python tests/integration/test_full_pipeline.py
```

### Performance Tests
```bash
# Load testing
python tests/performance/load_test.py
```

## 🚀 Deployment

### Development
```bash
./start-services.sh
```

### Production
```bash
# Using Helm
helm install hyperrag platform/infra/helmfile/

# Using Docker Compose
docker-compose -f platform/infra/compose/docker-compose.prod.yml up -d
```

### Kubernetes
```bash
# Deploy to Kubernetes
kubectl apply -f platform/infra/k8s/
```

## 📈 Performance Optimization

### Retrieval Optimization
- **Vector Index**: HNSW with optimized parameters
- **Batch Processing**: Parallel embedding generation
- **Caching**: Redis for frequent queries
- **Re-ranking**: Efficient cross-encoder models

### Resource Management
- **Connection Pooling**: Optimized database connections
- **Memory Management**: Efficient model loading
- **CPU Utilization**: Parallel processing where possible

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run linting
flake8 platform/
black platform/

# Run tests
pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📚 Documentation

### Complete Service Documentation

- **[Persian Documentation](docs/Persian-Documentation.md)** - مستند کامل فارسی شامل توضیح همه سرویس‌ها
- **[Services Documentation](docs/Services-Documentation.md)** - Technical reference برای تمام سرویس‌ها
- **[Testing Guide](docs/Service-Testing-Guide.md)** - راهنمای تست سرویس‌ها و pipeline

### Architecture and Development

- **[Architecture](docs/Architecture.md)** - معماری کلی سیستم
- **[Technical Spec](docs/Technical-Spec.md)** - مشخصات فنی
- **[Development Guide](docs/DEVELOPMENT.md)** - راهنمای توسعه

## 🆘 Support

- **Documentation**: [docs/](docs/)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: support@hyperrag.ai

## 🗺️ Roadmap

### Phase 1 (Completed)
- ✅ Document ingestion and processing
- ✅ Multi-language support (Persian/English)
- ✅ Hybrid retrieval with RRF
- ✅ Re-ranking capabilities
- ✅ Basic observability

### Phase 2 (In Progress)
- 🔄 Long-context management
- 🔄 Intelligent packing
- 🔄 Memory systems
- 🔄 Advanced caching

### Phase 3 (Planned)
- ⏳ Agent orchestration
- ⏳ Decision-making loops
- ⏳ Advanced guardrails
- ⏳ Cost optimization

---

**Built with ❤️ for the Persian and English AI community**
