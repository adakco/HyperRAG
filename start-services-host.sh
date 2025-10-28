#!/bin/bash

# HyperRAG Services - Host Mode Startup Script
# This script starts all HyperRAG services directly on the host machine
# connecting to infrastructure running on 192.168.2.23

echo "🚀 Starting HyperRAG Services in Host Mode..."

# Set environment variables for all services
export DATABASE_URL="postgresql://adak:Adakpro123@192.168.2.23:5442/heyperrag"
export REDIS_URL="redis://192.168.2.23:6479"
export NATS_URL="nats://192.168.2.23:4222"
export QDRANT_URL="http://192.168.2.23:6333"
export MINIO_ENDPOINT="http://192.168.2.23:9190"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin123"
export LANGFUSE_HOST="http://192.168.2.23:3000"
export LLM_MODEL="deepseek/deepseek-chat-v3-0324:free"
export OPENROUTER_API_KEY="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"
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export EMBEDDING_MODEL="BAAI/bge-large-en-v1.5"

# Function to start a service
start_service() {
    local service_name=$1
    local port=$2
    local service_dir=$3

    echo "📦 Starting $service_name on port $port..."
    cd "platform/services/$service_dir" || exit 1

    # Check if already running
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "⚠️  $service_name is already running on port $port"
        cd - > /dev/null
        return 0
    fi

    # Start service in background
    python3 main.py &
    local pid=$!
    echo $pid > "/tmp/hyperrag-${service_name}.pid"

    # Wait for service to start
    local attempts=0
    while [ $attempts -lt 10 ]; do
        sleep 2
        if curl -s --max-time 5 "http://localhost:$port/health" > /dev/null 2>&1; then
            echo "✅ $service_name started successfully (PID: $pid)"
            cd - > /dev/null
            return 0
        fi
        if ! kill -0 $pid 2>/dev/null; then
            echo "❌ Failed to start $service_name (process died)"
            cd - > /dev/null
            return 1
        fi
        attempts=$((attempts + 1))
        echo "⏳ Waiting for $service_name to start... ($attempts/10)"
    done

    echo "❌ $service_name failed to respond on port $port"
    cd - > /dev/null
    return 1
}

# Start services one by one to avoid conflicts
echo "🔄 Starting services..."

echo "Starting core services..."
start_service "ingestor" "8000" "ingestor"
start_service "normalizer" "8001" "normalizer"
start_service "retriever" "8002" "retriever"
start_service "chunker" "8003" "chunker"
start_service "embedder" "8004" "embedder"

echo "Starting evaluation and orchestration services..."
start_service "evaluator" "8005" "evaluator"
start_service "agent-orch" "8006" "agent-orch"

echo "Starting utility services..."
start_service "policy" "8007" "policy"
start_service "costing" "8008" "costing"
start_service "pack-longrag" "8009" "pack.longrag"
start_service "memory-memorag" "8010" "memory.memorag"
start_service "reranker" "8011" "reranker"
start_service "graph-kg" "8012" "graph.kg"

echo ""
echo "🎉 All HyperRAG services started successfully!"
echo ""
echo "📋 Service Status:"
echo "   📥 Ingestor:    http://localhost:8000"
echo "   🧹 Normalizer:  http://localhost:8001"
echo "   🔍 Retriever:   http://localhost:8002"
echo "   ✂️  Chunker:     http://localhost:8003"
echo "   🧠 Embedder:    http://localhost:8004"
echo "   📊 Evaluator:   http://localhost:8005"
echo "   🤖 Agent-Orch:  http://localhost:8006"
echo "   🛡️  Policy:      http://localhost:8007"
echo "   💰 Costing:     http://localhost:8008"
echo "   📦 Pack-LRAG:   http://localhost:8009"
echo "   🧠 Memory:      http://localhost:8010"
echo "   🔄 Reranker:    http://localhost:8011"
echo "   🕸️  Graph-KG:    http://localhost:8012"
echo ""
echo "🔧 Infrastructure (on 192.168.2.23):"
echo "   🗄️  PostgreSQL:  192.168.2.23:5442"
echo "   ⚡ Redis:        192.168.2.23:6479"
echo "   📨 NATS:         192.168.2.23:4222"
echo "   🔍 Qdrant:       192.168.2.23:6333"
echo "   📦 MinIO:        192.168.2.23:9090"
echo "   📊 Langfuse:     192.168.2.23:3000"
echo ""
echo "💡 To stop services, run: ./stop-services-host.sh"
