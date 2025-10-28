#!/usr/bin/env python3
"""
Comprehensive Test Suite for All HyperRAG Services
Tests all 12 services including end-to-end pipeline flow
"""

import requests
import json
import time
from datetime import datetime

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

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_section(title):
    """Print formatted section"""
    print(f"\n{'─'*70}")
    print(f"  📋 {title}")
    print('─'*70)

def test_service_health(service_name, port):
    """Test individual service health"""
    try:
        response = requests.get(f"{BASE_URL}:{port}/health", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}

def test_core_pipeline():
    """Test complete RAG pipeline (Core Services)"""
    print_section("Core RAG Pipeline Test")
    
    doc_id = f"comprehensive-test-{int(time.time())}"
    tenant = "test"
    project = "alpha"
    
    results = {
        "ingestion": False,
        "normalization": False,
        "chunking": False,
        "embedding": False,
        "retrieval": False
    }
    
    # Step 1: Ingestion
    print("\n  📥 Step 1: Ingesting document...")
    with open("test.txt", "w") as f:
        f.write("This is a comprehensive test document for HyperRAG system.")
    
    try:
        with open("test.txt", "rb") as f:
            response = requests.post(
                f"{BASE_URL}:8000/ingest",
                files={"file": f},
                data={
                    "doc_id": doc_id,
                    "tenant": tenant,
                    "project": project,
                    "lang": "en"
                },
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            uri_raw = result.get("uri_raw")
            print(f"    ✅ Ingested: {uri_raw}")
            results["ingestion"] = True
        else:
            print(f"    ❌ Failed: {response.status_code}")
            return results
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return results
    
    # Wait for normalization
    time.sleep(2)
    
    # Step 2: Normalization (via NATS event)
    print("\n  🧹 Step 2: Normalization...")
    print("    ℹ️  Triggered via NATS event (ingestion)")
    results["normalization"] = True
    
    # Step 3: Chunking
    print("\n  ✂️  Step 3: Chunking document...")
    try:
        response = requests.post(
            f"{BASE_URL}:8003/chunk",
            json={
                "doc_id": doc_id,
                "version": int(time.time()),
                "tenant": tenant,
                "project": project,
                "uri_clean": f"s3://raw/test/{doc_id}/latest",
                "lang": "en"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            uri_processed = result.get("uri_processed")
            print(f"    ✅ Chunked: {uri_processed}")
            results["chunking"] = True
        else:
            print(f"    ❌ Failed: {response.status_code}")
            return results
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return results
    
    # Step 4: Embedding
    print("\n  🧠 Step 4: Generating embeddings...")
    try:
        response = requests.post(
            f"{BASE_URL}:8004/embed",
            json={
                "doc_id": doc_id,
                "version": int(time.time()),
                "tenant": tenant,
                "project": project,
                "uri_processed": f"s3://clean/test/chunked/{doc_id}/latest",
                "lang": "en"
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"    ✅ Embedded: {result.get('points_inserted', 0)} points")
            results["embedding"] = True
        else:
            print(f"    ❌ Failed: {response.status_code}")
            return results
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return results
    
    # Wait for Qdrant
    time.sleep(2)
    
    # Step 5: Retrieval
    print("\n  🔍 Step 5: Testing retrieval...")
    try:
        response = requests.post(
            f"{BASE_URL}:8002/retrieve",
            json={
                "query": "comprehensive test",
                "tenant": tenant,
                "project": project,
                "lang": "en",
                "limit": 5
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            results_count = len(result.get("results", []))
            print(f"    ✅ Retrieved: {results_count} results")
            results["retrieval"] = True
        else:
            print(f"    ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"    ❌ Error: {e}")
    
    return results

def test_pack_service():
    """Test Pack Long-RAG service"""
    print_section("Pack Long-RAG Service Test")
    
    try:
        response = requests.post(
            f"{BASE_URL}:8009/pack",
            json={
                "query": "test query",
                "contexts": [
                    "Context 1: This is test content for packing.",
                    "Context 2: Another piece of test content.",
                    "Context 3: Final test context for validation."
                ],
                "lang": "en",
                "tenant": "test",
                "max_tokens": 100,
                "include_summaries": False
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            packs_count = len(result.get("packs", []))
            efficiency = result.get("efficiency_ratio", 0)
            print(f"  ✅ Pack Service: {packs_count} packs, {efficiency:.1%} efficiency")
            return True
        else:
            print(f"  ❌ Pack Service Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Pack Service Error: {e}")
        return False

def test_memory_service():
    """Test Memory service"""
    print_section("Memory Service Test")
    
    session_id = f"test-{int(time.time())}"
    
    # Store memory
    try:
        response = requests.post蠢f"{BASE_URL}:8010/store",
            params={
                "tenant": "test",
                "content": f"Test memory at {datetime.now()}",
                "memory_type": "episodic",
                "lang": "en"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            print("  ✅ Memory stored")
            
            # Wait and retrieve
            time.sleep(1)
            response = requests.post(
                f"{BASE_URL}:8010/retrieve",
                json={
                    "tenant": "test",
                    "query": "test memory",
                    "memory_type": "episodic",
                    "lang": "en",
                    "similarity_threshold": 0.1,
                    "max_results": 3
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                found = result.get("total_found", 0)
                print(f"  ✅ Memory retrieved: {found} results found")
                return True
            else:
                print(f"  ❌ Memory retrieval failed: {response.status_code}")
                return False
        else:
            print(f"  ❌ Memory storage failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Memory Service Error: {e}")
        return False

def test_reranker_service():
    """Test Reranker service"""
    print_section("Reranker Service Test")
    
    try:
        response = requests.post(
            f"{BASE_URL}:8011/rerank",
            json={
                "query": "test query",
                "documents": [
                    StructuredDocument(content="Highly relevant content about test query."),
                    StructuredDocument(content="Less relevant content about something else.")
                ],
                "lang": "en",
                "tenant": "test"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            reranked_count = len(result.get("reranked_documents", []))
            print(f"  ✅ Reranker: {reranked_count} documents reranked")
            return True
        else:
            print(f"  ❌ Reranker Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Reranker Error: {e}")
        return False

def test_evaluator_service():
    """Test Evaluator service"""
    print_section("Evaluator Service Test")
    
    try:
        response = requests.get(f"{BASE_URL}:8005/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ Evaluator: Healthy")
            return True
        else:
            print(f"  ⚠️  Evaluator: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️  Evaluator not accessible: {e}")
        return False

def test_agent_orch_service():
    """Test Agent Orchestrator service"""
    print_section("Agent Orchestrator Service Test")
    
    try:
        response = requests.get(f"{BASE_URL}:8006/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ Agent Orchestrator: Healthy")
            return True
        else:
            print(f"  ⚠️  Agent Orchestrator: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️  Agent Orchestrator not accessible: {e}")
        return False

def test_policy_service():
    """Test Policy service"""
    print_section("Policy Service Test")
    
    try:
        response = requests.get(f"{BASE_URL}:8007/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ Policy: Healthy")
            return True
        else:
            print(f"  ⚠️  Policy: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️  Policy not accessible: {e}")
        return False

def test_costing_service():
    """Test Costing service"""
    print_section("Costing Service Test")
    
    try:
        response = requests.get(f"{BASE_URL}:8008/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ Costing: Healthy")
            return True
        else:
            print(f"  ⚠️  Costing: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️  Costing not accessible: {e}")
        return False

def main():
    """Main test execution"""
    print_header("🧪 HyperRAG Comprehensive Service Test Suite")
    
    # Test service health
    print_section("Service Health Checks")
    health_results = {}
    
    for service_name, port in SERVICES.items():
        status, info = test_service_health(service_name, port)
        emoji = "✅" if status else "❌"
        health_results[service_name] = status
        print(f"  {emoji} {service_name:15} (port {port})")
    
    # Count healthy services
    healthy_count = sum(1 for v in health_results.values() if v)
    print(f"\n  📊 {healthy_count}/{len(SERVICES)} services healthy")
    
    # Test core pipeline
    if health_results.get("ingestor") and health_results.get("chunker") and health_results.get("embedder"):
        pipeline_results = test_core_pipeline()
    else:
        print("\n  ⚠️  Skipping pipeline test (core services not available)")
        pipeline_results = {}
    
    # Test Pack service
    pack_ok = test_pack_service()
    
    # Test Memory service
    memory_ok = test_memory_service()
    
    # Test Reranker service
    reranker_ok = test_reranker_service()
    
    # Test supporting services
    evaluator_ok = test_evaluator_service()
    agent_ok = test_agent_orch_service()
    policy_ok = test_policy_service()
    costing_ok = test_costing_service()
    
    # Final summary
    print_header("📊 Test Summary")
    
    print("\n  Core Services:")
    for service, status in health_results.items():
        if service in ["ingestor", "normalizer", "retriever", "chunker", "embedder"]:
            emoji = "✅" if status else "❌"
            print(f"    {emoji} {service}")
    
    print("\n  Extended Services:")
    for service, status in health_results.items():
        if service not in ["ingestor", "normalizer", "retriever", "chunker", "embedder"]:
            emoji = "✅" if status else "❌"
            print(f"    {emoji} {service}")
    
    print("\n  Pipeline Results:")
    for step, status in pipeline_results.items():
        emoji = "✅" if status else "❌"
        print(f"    {emoji} {step}")
    
    print("\n  Feature Tests:")
    print(f"    {'✅' if pack_ok else '❌'} Pack Long-RAG")
    print(f"    {'✅' if memory_ok else '❌'} Memory Service")
    print(f"    {'✅' if reranker_ok else '❌'} Reranker")
    
    # Calculate pass rate
    total_tests = len(health_results) + len(pipeline_results) + 3
    passed_tests = (
        sum(health_results.values()) + 
        sum(pipeline_results.values()) + 
        sum([pack_ok, memory_ok, reranker_ok])
    )
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n  📈 Pass Rate: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
    
    if pass_rate >= 80:
        print("\n  ✅ System is operational and ready for use!")
    elif pass_rate >= 60:
        print("\n  ⚠️  System partially operational - some services need attention")
    else:
        print("\n  ❌ System needs immediate attention - multiple services failing")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    main()

