#!/usr/bin/env python3
"""
HyperRAG Services Demo Test
Simple demonstration of all service outputs
"""

import requests
import json
import time

def test_service(name, url, endpoint="/health", method="GET", data=None):
    """Test a service endpoint and show the response"""
    print(f"\n🔍 Testing {name}...")
    print(f"   URL: {url}{endpoint}")

    try:
        if method == "GET":
            response = requests.get(f"{url}{endpoint}", timeout=10)
        elif method == "POST":
            response = requests.post(f"{url}{endpoint}",
                                   json=data,
                                   headers={"Content-Type": "application/json"},
                                   timeout=10)

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"   ✅ Response: {json.dumps(result, indent=2, ensure_ascii=False)[:200]}...")
                return True
            except:
                print(f"   ✅ Response: {response.text[:200]}...")
                return True
        else:
            print(f"   ❌ Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"   ❌ Connection Error: {str(e)}")
        return False

def main():
    print("🚀 HyperRAG Services Demo Test")
    print("=" * 50)

    services = {
        "Ingestor": ("http://localhost:8000", "/health"),
        "Normalizer": ("http://localhost:8001", "/health"),
        "Retriever": ("http://localhost:8002", "/health"),
        "Chunker": ("http://localhost:8003", "/health"),
        "Embedder": ("http://localhost:8004", "/health"),
        "Evaluator": ("http://localhost:8005", "/health"),
        "Agent-Orch": ("http://localhost:8006", "/health"),
        "Policy": ("http://localhost:8007", "/health"),
        "Costing": ("http://localhost:8008", "/health"),
        "Pack-LRAG": ("http://localhost:8009", "/health"),
        "Memory": ("http://localhost:8010", "/health"),
        "Reranker": ("http://localhost:8011", "/health"),
    }

    results = {}

    print("\n📊 Health Check - All Services:")
    print("-" * 30)

    for name, (url, endpoint) in services.items():
        success = test_service(name, url, endpoint)
        results[name] = success

    print(f"\n{'='*50}")
    print("📋 SUMMARY:")
    print(f"{'='*50}")

    total = len(results)
    successful = sum(results.values())

    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print("20")

    print(f"\n🎯 Overall: {successful}/{total} services responding ({successful/total*100:.1f}%)")

    if successful == total:
        print("\n🎉 All services are working perfectly!")
        print("\n💡 You can now use HyperRAG for:")
        print("   📥 Document ingestion and processing")
        print("   🔍 Intelligent search and retrieval")
        print("   🤖 AI-powered agent interactions")
        print("   📊 Quality evaluation and monitoring")
    else:
        print(f"\n⚠️  {total - successful} services need attention.")

if __name__ == "__main__":
    main()
