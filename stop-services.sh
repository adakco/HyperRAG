#!/bin/bash

# HyperRAG Services Stop Script
# This script stops all the HyperRAG services

set -e

echo "🛑 Stopping HyperRAG Services..."

# Stop Python services
echo "🐍 Stopping Python services..."

# Stop Ingestor
if [ -f .ingestor.pid ]; then
    INGESTOR_PID=$(cat .ingestor.pid)
    if kill -0 $INGESTOR_PID 2>/dev/null; then
        echo "📥 Stopping Ingestor service (PID: $INGESTOR_PID)..."
        kill $INGESTOR_PID
        rm .ingestor.pid
    else
        echo "📥 Ingestor service already stopped"
        rm .ingestor.pid
    fi
fi

# Stop Normalizer
if [ -f .normalizer.pid ]; then
    NORMALIZER_PID=$(cat .normalizer.pid)
    if kill -0 $NORMALIZER_PID 2>/dev/null; then
        echo "🔧 Stopping Normalizer service (PID: $NORMALIZER_PID)..."
        kill $NORMALIZER_PID
        rm .normalizer.pid
    else
        echo "🔧 Normalizer service already stopped"
        rm .normalizer.pid
    fi
fi

# Stop Retriever
if [ -f .retriever.pid ]; then
    RETRIEVER_PID=$(cat .retriever.pid)
    if kill -0 $RETRIEVER_PID 2>/dev/null; then
        echo "🔍 Stopping Retriever service (PID: $RETRIEVER_PID)..."
        kill $RETRIEVER_PID
        rm .retriever.pid
    else
        echo "🔍 Retriever service already stopped"
        rm .retriever.pid
    fi
fi

# Stop Chunker
if [ -f .chunker.pid ]; then
    CHUNKER_PID=$(cat .chunker.pid)
    if kill -0 $CHUNKER_PID 2>/dev/null; then
        echo "✂️ Stopping Chunker service (PID: $CHUNKER_PID)..."
        kill $CHUNKER_PID
        rm .chunker.pid
    else
        echo "✂️ Chunker service already stopped"
        rm .chunker.pid
    fi
fi

# Stop Embedder
if [ -f .embedder.pid ]; then
    EMBEDDER_PID=$(cat .embedder.pid)
    if kill -0 $EMBEDDER_PID 2>/dev/null; then
        echo "🧠 Stopping Embedder service (PID: $EMBEDDER_PID)..."
        kill $EMBEDDER_PID
        rm .embedder.pid
    else
        echo "🧠 Embedder service already stopped"
        rm .embedder.pid
    fi
fi

# Stop Evaluator
if [ -f .evaluator.pid ]; then
    EVALUATOR_PID=$(cat .evaluator.pid)
    if kill -0 $EVALUATOR_PID 2>/dev/null; then
        echo "📊 Stopping Evaluator service (PID: $EVALUATOR_PID)..."
        kill $EVALUATOR_PID
        rm .evaluator.pid
    else
        echo "📊 Evaluator service already stopped"
        rm .evaluator.pid
    fi
fi

# Stop Agent Orchestrator
if [ -f .agent-orch.pid ]; then
    AGENT_ORCH_PID=$(cat .agent-orch.pid)
    if kill -0 $AGENT_ORCH_PID 2>/dev/null; then
        echo "🤖 Stopping Agent Orchestrator service (PID: $AGENT_ORCH_PID)..."
        kill $AGENT_ORCH_PID
        rm .agent-orch.pid
    else
        echo "🤖 Agent Orchestrator service already stopped"
        rm .agent-orch.pid
    fi
fi

# Stop Policy
if [ -f .policy.pid ]; then
    POLICY_PID=$(cat .policy.pid)
    if kill -0 $POLICY_PID 2>/dev/null; then
        echo "🔒 Stopping Policy service (PID: $POLICY_PID)..."
        kill $POLICY_PID
        rm .policy.pid
    else
        echo "🔒 Policy service already stopped"
        rm .policy.pid
    fi
fi

# Stop Costing
if [ -f .costing.pid ]; then
    COSTING_PID=$(cat .costing.pid)
    if kill -0 $COSTING_PID 2>/dev/null; then
        echo "💰 Stopping Costing service (PID: $COSTING_PID)..."
        kill $COSTING_PID
        rm .costing.pid
    else
        echo "💰 Costing service already stopped"
        rm .costing.pid
    fi
fi

# Stop Pack LongRAG
if [ -f .pack-longrag.pid ]; then
    PACK_LONGRAG_PID=$(cat .pack-longrag.pid)
    if kill -0 $PACK_LONGRAG_PID 2>/dev/null; then
        echo "📦 Stopping Pack LongRAG service (PID: $PACK_LONGRAG_PID)..."
        kill $PACK_LONGRAG_PID
        rm .pack-longrag.pid
    else
        echo "📦 Pack LongRAG service already stopped"
        rm .pack-longrag.pid
    fi
fi

# Stop Memory MemoRAG
if [ -f .memory-memorag.pid ]; then
    MEMORY_MEMORAG_PID=$(cat .memory-memorag.pid)
    if kill -0 $MEMORY_MEMORAG_PID 2>/dev/null; then
        echo "🧠 Stopping Memory MemoRAG service (PID: $MEMORY_MEMORAG_PID)..."
        kill $MEMORY_MEMORAG_PID
        rm .memory-memorag.pid
    else
        echo "🧠 Memory MemoRAG service already stopped"
        rm .memory-memorag.pid
    fi
fi

# Stop Reranker
if [ -f .reranker.pid ]; then
    RERANKER_PID=$(cat .reranker.pid)
    if kill -0 $RERANKER_PID 2>/dev/null; then
        echo "🔄 Stopping Reranker service (PID: $RERANKER_PID)..."
        kill $RERANKER_PID
        rm .reranker.pid
    else
        echo "🔄 Reranker service already stopped"
        rm .reranker.pid
    fi
fi

# Stop infrastructure services
echo "📦 Stopping infrastructure services..."
cd platform/infra/compose
docker-compose down

echo "✅ All HyperRAG services stopped successfully!"
