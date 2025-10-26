#!/bin/bash

# HyperRAG Services - Host Mode Stop Script
# This script stops all HyperRAG services running on the host machine

echo "🛑 Stopping HyperRAG Services..."

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file="/tmp/hyperrag-${service_name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo "🛑 Stopping $service_name (PID: $pid)..."
            kill $pid
            # Wait for process to stop
            for i in {1..10}; do
                if ! kill -0 $pid 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if kill -0 $pid 2>/dev/null; then
                echo "⚠️  Force killing $service_name..."
                kill -9 $pid
            fi
            echo "✅ $service_name stopped"
        else
            echo "⚠️  $service_name PID $pid not found"
        fi
        rm -f "$pid_file"
    else
        echo "⚠️  PID file for $service_name not found"
    fi
}

# Stop services in reverse order
echo "🔄 Stopping services..."

stop_service "memory-memorag"
stop_service "policy"
stop_service "pack-longrag"
stop_service "reranker"
stop_service "costing"
stop_service "normalizer"
stop_service "agent-orch"
stop_service "evaluator"
stop_service "embedder"
stop_service "retriever"
stop_service "chunker"
stop_service "ingestor"

echo ""
echo "🎉 All HyperRAG services stopped successfully!"

# Clean up any remaining processes
echo "🧹 Cleaning up any remaining processes..."
pkill -f "python.*main.py" 2>/dev/null || true

echo "✅ Cleanup complete"
