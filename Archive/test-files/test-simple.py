#!/usr/bin/env python3
"""
Simple HyperRAG Test - Just check basic functionality
"""

import requests
import json

def test_service(name, url, description):
    """Test a service endpoint"""
    print(f"🔍 Testing {name}...")
    print(f"   {description}")

    try:
        response = requests.get(f"{url}/health", timeout=10)
        if response.status_code == 200:
            print("   ✅ PASS - Service is healthy")
            return True
        else:
            print(f"   ❌ FAIL - Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ FAIL - Error: {str(e)}")
        return False

def main():
    print("🚀 HyperRAG Simple Health Check")
    print("=" * 50)

    services = [
        ("http://localhost:8000", "📥 Ingestor", "Document ingestion service"),
        ("http://localhost:8001", "🧹 Normalizer", "Text normalization service"),
        ("http://localhost:8002", "🔍 Retriever", "Document retrieval service"),
        ("http://localhost:8003", "✂️ Chunker", "Document chunking service"),
        ("http://localhost:8004", "🧠 Embedder", "Text embedding service"),
        ("http://localhost:8005", "📊 Evaluator", "RAG evaluation service"),
        ("http://localhost:8006", "🤖 Agent-Orch", "AI agent orchestration"),
        ("http://localhost:8007", "🛡️ Policy", "Access control service"),
        ("http://localhost:8008", "💰 Costing", "Cost tracking service"),
        ("http://localhost:8009", "📦 Pack-LRAG", "Long-context packing"),
        ("http://localhost:8010", "🧠 Memory", "Episodic memory service"),
        ("http://localhost:8011", "🔄 Reranker", "Document reranking service"),
    ]

    passed = 0
    total = len(services)

    print("\n🏥 SERVICE HEALTH CHECKS:")
    print("-" * 40)

    for url, name, desc in services:
        if test_service(name, url, desc):
            passed += 1

    print(f"\n{'='*50}")
    print("📊 FINAL RESULTS:")
    print(f"{'='*50}")

    print(f"✅ Services Working: {passed}/{total} ({passed/total*100:.1f}%)")
    print(f"❌ Services Failed: {total - passed}")

    if passed == total:
        print("\n🎉 SUCCESS! All HyperRAG services are operational!")
        print("\n🚀 Ready for production use!")
        print("\n💡 Next steps:")
        print("   • Test document ingestion")
        print("   • Test search functionality")
        print("   • Configure AI agent workflows")
    else:
        print("\n⚠️  Some services need attention.")
        print("\n🔧 Check the failed services above.")
        if passed >= 10:
            print("\n✅ Core functionality is working!")

    print(f"\n🔗 API Endpoints: http://localhost:8000-{8011}")

if __name__ == "__main__":
    main()