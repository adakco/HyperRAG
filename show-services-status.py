#!/usr/bin/env python3
"""
HyperRAG Services Status Display
Simple script to show all service statuses and endpoints
"""

import requests
import json
import time

def get_service_info(url, name):
    """Get detailed service information"""
    try:
        # Health check
        health_response = requests.get(f"{url}/health", timeout=5)
        health_data = health_response.json() if health_response.status_code == 200 else {"status": "error"}

        # Try to get service info if available
        try:
            info_response = requests.get(f"{url}/info", timeout=5)
            if info_response.status_code == 200:
                info_data = info_response.json()
            else:
                info_data = {"version": "N/A", "description": "N/A"}
        except:
            info_data = {"version": "N/A", "description": "N/A"}

        return {
            "name": name,
            "url": url,
            "health": health_data,
            "info": info_data,
            "status": "✅ Active" if health_response.status_code == 200 else "❌ Down"
        }
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "health": {"status": "error", "error": str(e)},
            "info": {"version": "N/A", "description": "Connection failed"},
            "status": "❌ Down"
        }

def main():
    print("🚀 HyperRAG Services Status Report")
    print("=" * 80)

    services = [
        ("http://localhost:8000", "📥 Ingestor", "Document ingestion and storage"),
        ("http://localhost:8001", "🧹 Normalizer", "Text normalization and PII removal"),
        ("http://localhost:8002", "🔍 Retriever", "Intelligent document retrieval"),
        ("http://localhost:8003", "✂️ Chunker", "Document chunking and splitting"),
        ("http://localhost:8004", "🧠 Embedder", "Text embedding generation"),
        ("http://localhost:8005", "📊 Evaluator", "RAG quality assessment"),
        ("http://localhost:8006", "🤖 Agent-Orch", "AI agent orchestration"),
        ("http://localhost:8007", "🛡️ Policy", "Access control and security"),
        ("http://localhost:8008", "💰 Costing", "Cost tracking and monitoring"),
        ("http://localhost:8009", "📦 Pack-LRAG", "Long-context document packing"),
        ("http://localhost:8010", "🧠 Memory", "Episodic memory management"),
        ("http://localhost:8011", "🔄 Reranker", "Document re-ranking"),
    ]

    active_services = 0

    print("\n📊 SERVICE STATUS OVERVIEW:")
    print("-" * 80)

    for url, display_name, description in services:
        service_info = get_service_info(url, display_name.split()[1])

        status_emoji = "✅" if service_info["status"] == "✅ Active" else "❌"
        print("50")

        if service_info["status"] == "✅ Active":
            active_services += 1

    print(f"\n{'='*80}")
    print("🎯 FINAL SUMMARY:")
    print(f"{'='*80}")

    print(f"📈 Active Services: {active_services}/{len(services)} ({active_services/len(services)*100:.1f}%)")
    print(f"🔗 API Base URLs: http://localhost:8000-{8011}")
    print(f"🗄️ Database: PostgreSQL on 192.168.2.23:5442")
    print(f"⚡ Cache: Redis on 192.168.2.23:6479")
    print(f"📨 Message Queue: NATS on 192.168.2.23:4222")
    print(f"🔍 Vector DB: Qdrant on 192.168.2.23:6333")
    print(f"📦 Object Storage: MinIO on 192.168.2.23:9090")

    print(f"\n🎉 System Status: {'FULLY OPERATIONAL' if active_services == len(services) else 'PARTIALLY OPERATIONAL'}")

    print(f"\n💡 Available Features:")
    if active_services >= 10:
        print("   ✅ Complete RAG pipeline (ingest → process → search → AI agents)")
        print("   ✅ Multi-language support (Persian/English)")
        print("   ✅ Real-time monitoring and cost tracking")
        print("   ✅ Production-ready microservices architecture")

    print(f"\n🔧 Quick Commands:")
    print("   # Check all services:")
    print("   for i in {8000..8011}; do curl -s http://localhost:$i/health; done")
    print()
    print("   # Start all services:")
    print("   ./start-services-host.sh")
    print()
    print("   # Stop all services:")
    print("   ./stop-services-host.sh")
    print()
    print("   # Run full test:")
    print("   python3 test-system.py")

if __name__ == "__main__":
    main()
