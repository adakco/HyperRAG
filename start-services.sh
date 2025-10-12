#!/bin/bash

# HyperRAG Services Startup Script
# This script starts all the core services for the HyperRAG system

set -e

echo "🚀 Starting HyperRAG Services..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start infrastructure services
echo "📦 Starting infrastructure services (MinIO, Postgres, Qdrant, NATS, Redis, Neo4j, Observability)..."
cd platform/infra/compose
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

# Start Python services
echo "🐍 Starting Python services..."

# Ingestor service
echo "📥 Starting Ingestor service..."
cd ../../services/ingestor
python -m pip install -r requirements.txt
python main.py &
INGESTOR_PID=$!

# Normalizer service
echo "🔧 Starting Normalizer service..."
cd ../normalizer
python -m pip install -r requirements.txt
python main.py &
NORMALIZER_PID=$!

# Retriever service
echo "🔍 Starting Retriever service..."
cd ../retriever
python -m pip install -r requirements.txt
python main.py &
RETRIEVER_PID=$!

# Chunker service
echo "✂️ Starting Chunker service..."
cd ../chunker
python -m pip install -r requirements.txt
python main.py &
CHUNKER_PID=$!

# Embedder service
echo "🧠 Starting Embedder service..."
cd ../embedder
python -m pip install -r requirements.txt
python main.py &
EMBEDDER_PID=$!

# Evaluator service
echo "📊 Starting Evaluator service..."
cd ../evaluator
python -m pip install -r requirements.txt
python main.py &
EVALUATOR_PID=$!

# Agent Orchestrator service
echo "🤖 Starting Agent Orchestrator service..."
cd ../agent-orch
python -m pip install -r requirements.txt
python main.py &
AGENT_ORCH_PID=$!

# Policy service
echo "🔒 Starting Policy service..."
cd ../policy
python -m pip install -r requirements.txt
python main.py &
POLICY_PID=$!

# Costing service
echo "💰 Starting Costing service..."
cd ../costing
python -m pip install -r requirements.txt
python main.py &
COSTING_PID=$!

# Pack LongRAG service
echo "📦 Starting Pack LongRAG service..."
cd ../pack.longrag
python -m pip install -r requirements.txt
python main.py &
PACK_LONGRAG_PID=$!

# Memory MemoRAG service
echo "🧠 Starting Memory MemoRAG service..."
cd ../memory.memorag
python -m pip install -r requirements.txt
python main.py &
MEMORY_MEMORAG_PID=$!

# Reranker service
echo "🔄 Starting Reranker service..."
cd ../reranker
python -m pip install -r requirements.txt
python main.py &
RERANKER_PID=$!

# Wait a moment for services to start
sleep 10

# Check if services are running
echo "🔍 Checking service endpoints..."

# Check ingestor
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Ingestor service is running on http://localhost:8000"
else
    echo "❌ Ingestor service failed to start"
fi

# Check normalizer
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Normalizer service is running on http://localhost:8001"
else
    echo "❌ Normalizer service failed to start"
fi

# Check retriever
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    echo "✅ Retriever service is running on http://localhost:8002"
else
    echo "❌ Retriever service failed to start"
fi

# Check chunker
if curl -f http://localhost:8003/health > /dev/null 2>&1; then
    echo "✅ Chunker service is running on http://localhost:8003"
else
    echo "❌ Chunker service failed to start"
fi

# Check embedder
if curl -f http://localhost:8004/health > /dev/null 2>&1; then
    echo "✅ Embedder service is running on http://localhost:8004"
else
    echo "❌ Embedder service failed to start"
fi

# Check evaluator
if curl -f http://localhost:8005/health > /dev/null 2>&1; then
    echo "✅ Evaluator service is running on http://localhost:8005"
else
    echo "❌ Evaluator service failed to start"
fi

# Check agent orchestrator
if curl -f http://localhost:8006/health > /dev/null 2>&1; then
    echo "✅ Agent Orchestrator service is running on http://localhost:8006"
else
    echo "❌ Agent Orchestrator service failed to start"
fi

# Check policy
if curl -f http://localhost:8007/health > /dev/null 2>&1; then
    echo "✅ Policy service is running on http://localhost:8007"
else
    echo "❌ Policy service failed to start"
fi

# Check costing
if curl -f http://localhost:8008/health > /dev/null 2>&1; then
    echo "✅ Costing service is running on http://localhost:8008"
else
    echo "❌ Costing service failed to start"
fi

# Check pack longrag
if curl -f http://localhost:8009/health > /dev/null 2>&1; then
    echo "✅ Pack LongRAG service is running on http://localhost:8009"
else
    echo "❌ Pack LongRAG service failed to start"
fi

# Check memory memorag
if curl -f http://localhost:8010/health > /dev/null 2>&1; then
    echo "✅ Memory MemoRAG service is running on http://localhost:8010"
else
    echo "❌ Memory MemoRAG service failed to start"
fi

# Check reranker
if curl -f http://localhost:8011/health > /dev/null 2>&1; then
    echo "✅ Reranker service is running on http://localhost:8011"
else
    echo "❌ Reranker service failed to start"
fi

# Check infrastructure services
echo "🔍 Checking infrastructure services..."

# Check MinIO
if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "✅ MinIO is running on http://localhost:9000"
else
    echo "❌ MinIO failed to start"
fi

# Check Qdrant
if curl -f http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Qdrant is running on http://localhost:6333"
else
    echo "❌ Qdrant failed to start"
fi

# Check Postgres
if pg_isready -h localhost -p 5432 -U hyperrag > /dev/null 2>&1; then
    echo "✅ Postgres is running on localhost:5432"
else
    echo "❌ Postgres failed to start"
fi

# Check NATS
if curl -f http://localhost:8222/healthz > /dev/null 2>&1; then
    echo "✅ NATS is running on http://localhost:8222"
else
    echo "❌ NATS failed to start"
fi

# Check Redis
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo "✅ Redis is running on localhost:6379"
else
    echo "❌ Redis failed to start"
fi

# Check Neo4j
if curl -f http://localhost:7474 > /dev/null 2>&1; then
    echo "✅ Neo4j is running on http://localhost:7474"
else
    echo "❌ Neo4j failed to start"
fi

# Check Grafana
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is running on http://localhost:3000"
else
    echo "❌ Grafana failed to start"
fi

# Check Prometheus
if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is running on http://localhost:9090"
else
    echo "❌ Prometheus failed to start"
fi

# Check Jaeger
if curl -f http://localhost:16686 > /dev/null 2>&1; then
    echo "✅ Jaeger is running on http://localhost:16686"
else
    echo "❌ Jaeger failed to start"
fi

# Check Langfuse
if curl -f http://localhost:3001/api/public/health > /dev/null 2>&1; then
    echo "✅ Langfuse is running on http://localhost:3001"
else
    echo "❌ Langfuse failed to start"
fi

echo ""
echo "🎉 HyperRAG Services Startup Complete!"
echo ""
echo "📊 Service URLs:"
echo "  - Ingestor API: http://localhost:8000"
echo "  - Normalizer API: http://localhost:8001"
echo "  - Retriever API: http://localhost:8002"
echo "  - Chunker API: http://localhost:8003"
echo "  - Embedder API: http://localhost:8004"
echo "  - Evaluator API: http://localhost:8005"
echo "  - Agent Orchestrator API: http://localhost:8006"
echo "  - Policy API: http://localhost:8007"
echo "  - Costing API: http://localhost:8008"
echo "  - Pack LongRAG API: http://localhost:8009"
echo "  - Memory MemoRAG API: http://localhost:8010"
echo "  - Reranker API: http://localhost:8011"
echo "  - MinIO Console: http://localhost:9001 (admin/password123)"
echo "  - Qdrant Dashboard: http://localhost:6333/dashboard"
echo "  - Neo4j Browser: http://localhost:7474 (neo4j/password123)"
echo "  - Grafana: http://localhost:3000 (admin/admin123)"
echo "  - Prometheus: http://localhost:9090"
echo "  - Jaeger: http://localhost:16686"
echo "  - Langfuse: http://localhost:3001"
echo ""
echo "🛑 To stop all services, run: ./stop-services.sh"
echo "📝 Service PIDs: Ingestor=$INGESTOR_PID, Normalizer=$NORMALIZER_PID, Retriever=$RETRIEVER_PID, Chunker=$CHUNKER_PID, Embedder=$EMBEDDER_PID, Evaluator=$EVALUATOR_PID, AgentOrch=$AGENT_ORCH_PID, Policy=$POLICY_PID, Costing=$COSTING_PID, PackLongRAG=$PACK_LONGRAG_PID, MemoryMemoRAG=$MEMORY_MEMORAG_PID, Reranker=$RERANKER_PID"

# Save PIDs for stopping
echo "$INGESTOR_PID" > .ingestor.pid
echo "$NORMALIZER_PID" > .normalizer.pid
echo "$RETRIEVER_PID" > .retriever.pid
echo "$CHUNKER_PID" > .chunker.pid
echo "$EMBEDDER_PID" > .embedder.pid
echo "$EVALUATOR_PID" > .evaluator.pid
echo "$AGENT_ORCH_PID" > .agent-orch.pid
echo "$POLICY_PID" > .policy.pid
echo "$COSTING_PID" > .costing.pid
echo "$PACK_LONGRAG_PID" > .pack-longrag.pid
echo "$MEMORY_MEMORAG_PID" > .memory-memorag.pid
echo "$RERANKER_PID" > .reranker.pid

echo "✅ All services started successfully!"
