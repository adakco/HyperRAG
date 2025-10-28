#!/usr/bin/env python3
"""
Simplified Comprehensive Test Suite for All HyperRAG Services
"""

import requests
import time

BASE_URL = "http://localhost"
SERVICES = {
    "ingestor": 8000,
    "normalizer": 8001,
    "retriever": 8002,
    "chunker": 8003,
    "embedder": 8004,
    "evaluator": 8005,
    "agent-orch": 8006,
    "policy": 8007,
    "costing": 8008,
    "pack-longrag": 8009,
    "memory": 8010,
    "reranker": 8011
}

def test_health():
    """Test all service health"""
    print("\n" + "="*70)
    print("  Service Health Checks")
    print("="*70)
    
    healthy = 0
    for name, port in SERVICES.items():
        try:
            r = requests.get(f"{BASE_URL}:{port}/health", timeout=3)
            status = "✅" if r.status_code == 200 else "❌"
            healthy += 1 if r.status_code == 200 else 0
        except:
            status = "❌"
        
        print(f"  {status} {name:15} (port {port})")
    
    print(f"\n  📊 {healthy}/{len(SERVICES)} services healthy\n")
    return healthy

def test_pack():
    """Test Pack service"""
    print("="*70)
    print("  Pack Long-RAG Test")
    print("="*70)
    try:
        r = requests.post(f"{BASE_URL}:8009/pack", json={
            "query": "test",
            "contexts": ["Context 1", "Context 2"],
            "lang": "en",
            "tenant": "test",
            "max_tokens": 100
        }, timeout=10)
        
        if r.status_code == 200:
            result = r.json()
            print(f"  ✅ Pack: {len(result.get('packs', []))} packs, efficiency {result.get('efficiency_ratio', 0):.0%}")
            return True
        else:
            print(f"  ❌ Failed: HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_memory():
    """Test Memory service"""
    print("\n" + "="*70)
    print("  Memory Service Test")
    print("="*70)
    try:
        # Store
        r1 = requests.post(f"{BASE_URL}:8010/store", params={
            "tenant": "test",
            "content": "Test memory",
            "memory_type": "episodic",
            "lang": "en"
        }, timeout=10)
        
        if r1.status_code == 200:
            print("  ✅ Memory stored")
            
            time.sleep(1)
            
            # Retrieve
            r2 = requests.post(f"{BASE_URL}:8010/retrieve", json={
                "tenant": "test",
                "query": "test",
                "memory_type": "episodic",
                "lang": "en",
                "similarity_threshold": 0.1,
                "max_results": 3
            }, timeout=15)
            
            if r2.status_code == 200:
                result = r2.json()
                print(f"  ✅ Memory retrieved: {result.get('total_found', 0)} found")
                return True
            else:
                print(f"  ❌ Retrieval failed: HTTP {r2.status_code}")
                return False
        else:
            print(f"  ❌ Storage failed: HTTP {r1.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("  🧪 HyperRAG Comprehensive Service Test")
    print("="*70)
    
    health_ok = test_health()
    pack_ok = test_pack()
    memory_ok = test_memory()
    
    print("\n" + "="*70)
    print("  📊 Summary")
    print("="*70)
    print(f"  Health:  {health_ok}/{len(SERVICES)} services")
    print(f"  Pack:    {'✅' if pack_ok else '❌'}")
    print(f"  Memory:  {'✅' if memory_ok else '❌'}")
    
    rate = (health_ok + (1 if pack_ok else 0) + (1 if memory_ok else 0)) / (len(SERVICES) + 2)
    print(f"\n  Pass Rate: {rate:.0%}")
    
    if rate >= 0.8:
        print("  ✅ System operational!")
    elif rate >= 0.6:
        print("  ⚠️  System partially operational")
    else:
        print("  ❌ System needs attention")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

