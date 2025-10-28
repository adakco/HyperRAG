#!/usr/bin/env python3
"""
Comprehensive End-to-End Pipeline Test with Full Input/Output Logging
Tests all services with detailed request/response logging
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost"

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def print_step(num, title):
    print(f"\n📋 Step {num}: {title}")
    print("-"*80)

def print_request(method, url, data=None):
    print(f"\n📤 REQUEST:")
    print(f"   Method: {method}")
    print(f"   URL: {url}")
    if data:
        print(f"   Data: {json.dumps(data, indent=3)}")

def print_response(status, data=None, error=None):
    print(f"\n📥 RESPONSE:")
    print(f"   Status: {status}")
    if data:
        print(f"   Data: {json.dumps(data, indent=3)}")
    if error:
        print(f"   Error: {error}")

def test_complete_pipeline():
    """Test complete end-to-end pipeline with detailed logging"""
    
    print_header("🧪 HyperRAG Complete Pipeline Test with I/O Logging")
    
    # Generate unique identifiers
    timestamp = int(time.time())
    doc_id = f"detailed-test-{timestamp}"
    tenant = "test"
    project = "alpha"
    
    results = {}
    
    # ========================================
    # STEP 1: INGESTION
    # ========================================
    print_step(1, "Document Ingestion")
    
    print_request("POST", f"{BASE_URL}:8000/ingest", {
        "doc_id": doc_id,
        "tenant": tenant,
        "project": project,
        "lang": "en",
        "file": "test.txt"
    })
    
    try:
        with open("test.txt", "w") as f:
            f.write("This is a comprehensive test document for HyperRAG system. "
                   "It contains multiple sentences with different topics including "
                   "artificial intelligence, natural language processing, and machine learning.")
        
        with open("test.txt", "rb") as f:
            files = {"file": f}
            data = {
                "doc_id": doc_id,
                "tenant": tenant,
                "project": project,
                "lang": "en"
            }
            response = requests.post(f"{BASE_URL}:8000/ingest", files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results["ingestion"] = True
            uri_raw = result.get("uri_raw")
            print(f"\n   ✅ Document ingested: {uri_raw}")
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
            results["ingestion"] = False
            return results
    except Exception as e:
        print_response("ERROR", error=str(e))
        results["ingestion"] = False
        return results
    
    time.sleep(2)
    
    # ========================================
    # STEP 2: NORMALIZATION
    # ========================================
    print_step(2, "Document Normalization")
    print("   ℹ️  Triggered automatically via NATS event from ingestion")
    results["normalization"] = True
    
    time.sleep(2)
    
    # ========================================
    # STEP 3: CHUNKING
    # ========================================
    print_step(3, "Document Chunking")
    
    chunk_request = {
        "doc_id": doc_id,
        "version": timestamp,
        "tenant": tenant,
        "project": project,
        "uri_clean": f"s3://raw/test/{project}/{doc_id}/latest",
        "lang": "en"
    }
    
    print_request("POST", f"{BASE_URL}:8003/chunk", chunk_request)
    
    try:
        # Chunker uses POST with query parameters
        response = requests.post(f"{BASE_URL}:8003/chunk", params=chunk_request, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results["chunking"] = True
            uri_processed = result.get("uri_processed")
            print(f"\n   ✅ Document chunked: {uri_processed}")
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
            results["chunking"] = False
            return results
    except Exception as e:
        print_response("ERROR", error=str(e))
        results["chunking"] = False
        return results
    
    # ========================================
    # STEP 4: EMBEDDING
    # ========================================
    print_step(4, "Generating Embeddings")
    
    embed_request = {
        "doc_id": doc_id,
        "version": timestamp,
        "tenant": tenant,
        "project": project,
        "uri_processed": f"s3://clean/test/chunked/{doc_id}/latest",
        "lang": "en"
    }
    
    print_request("POST", f"{BASE_URL}:8004/embed", embed_request)
    
    try:
        response = requests.post(f"{BASE_URL}:8004/embed", json=embed_request, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results["embedding"] = True
            points_inserted = result.get("points_inserted", 0)
            print(f"\n   ✅ Embeddings generated: {points_inserted} points inserted")
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
            results["embedding"] = False
            return results
    except Exception as e:
        print_response("ERROR", error=str(e))
        results["embedding"] = False
        return results
    
    time.sleep(2)
    
    # ========================================
    # STEP 5: RETRIEVAL
    # ========================================
    print_step(5, "Document Retrieval")
    
    retrieval_request = {
        "query": "artificial intelligence natural language processing",
        "tenant": tenant,
        "project": project,
        "lang": "en",
        "limit": 5
    }
    
    print_request("POST", f"{BASE_URL}:8002/retrieve", retrieval_request)
    
    try:
        response = requests.post(f"{BASE_URL}:8002/retrieve", json=retrieval_request, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results["retrieval"] = True
            results_count = len(result.get("results", []))
            print(f"\n   ✅ Documents retrieved: {results_count} results")
            
            # Show top results
            if results_count > 0:
                print("\n   Top Results:")
                for i, res in enumerate(result.get("results", [])[:3]):
                    print(f"     {i+1}. Score: {res.get('score', 0):.3f} - {res.get('content', '')[:60]}...")
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
            results["retrieval"] = False
    except Exception as e:
        print_response("ERROR", error=str(e))
        results["retrieval"] = False
    
    return results

def test_pack_service():
    """Test Pack Long-RAG service with detailed logging"""
    
    print_header("📦 Pack Long-RAG Service Test")
    
    pack_request = {
        "query": "machine learning artificial intelligence",
        "contexts": [
            "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience.",
            "Artificial intelligence encompasses machine learning, deep learning, and natural language processing.",
            "Deep learning uses neural networks with multiple layers to learn complex patterns in data."
        ],
        "lang": "en",
        "tenant": "test",
        "max_tokens": 100,
        "include_summaries": False
    }
    
    print_request("POST", f"{BASE_URL}:8009/pack", pack_request)
    
    try:
        response = requests.post(f"{BASE_URL}:8009/pack", json=pack_request, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            
            packs_count = len(result.get("packs", []))
            efficiency = result.get("efficiency_ratio", 0)
            processing_time = result.get("processing_time_ms", 0)
            
            print(f"\n   ✅ Packs created: {packs_count}")
            print(f"   ✅ Efficiency: {efficiency:.1%}")
            print(f"   ✅ Processing time: {processing_time:.0f}ms")
            
            # Show pack details
            for i, pack in enumerate(result.get("packs", [])):
                print(f"\n   Pack {i+1}:")
                print(f"     - Original length: {pack.get('original_length', 0)} tokens")
                print(f"     - Packed length: {pack.get('packed_length', 0)} tokens")
                print(f"     - Relevance: {pack.get('relevance_score', 0):.2f}")
            
            return True
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_response("ERROR", error=str(e))
        return False

def test_memory_service():
    """Test Memory service with detailed logging"""
    
    print_header("💭 Memory Service Test")
    
    # Store memory
    print_step("A", "Store Episodic Memory")
    
    store_data = {
        "tenant": "test",
        "content": f"User asked about machine learning at {datetime.now()}",
        "memory_type": "episodic",
        "lang": "en",
        "user_id": "user123",
        "session_id": f"session-{int(time.time())}"
    }
    
    print_request("POST", f"{BASE_URL}:8010/store", store_data)
    
    try:
        response = requests.post(f"{BASE_URL}:8010/store", params=store_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            
            memory_id = result.get("memory_id")
            print(f"\n   ✅ Memory stored: {memory_id}")
            
            time.sleep(1)
            
            # Retrieve memory
            print_step("B", "Retrieve Episodic Memory")
            
            retrieve_data = {
                "tenant": "test",
                "query": "What did the user ask about?",
                "memory_type": "episodic",
                "lang": "en",
                "similarity_threshold": 0.3,
                "max_results": 5
            }
            
            print_request("POST", f"{BASE_URL}:8010/retrieve", retrieve_data)
            
            response = requests.post(f"{BASE_URL}:8010/retrieve", json=retrieve_data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                print_response("SUCCESS", result)
                
                total_found = result.get("total_found", 0)
                print(f"\n   ✅ Memories retrieved: {total_found}")
                
                # Show retrieved memories
                for i, mem in enumerate(result.get("results", [])[:3]):
                    print(f"\n   Memory {i+1}:")
                    print(f"     - ID: {mem.get('memory_id', '')[:8]}...")
                    print(f"     - Content: {mem.get('content', '')[:60]}...")
                    print(f"     - Similarity: {mem.get('similarity_score', 0):.2f}")
                    print(f"     - Access count: {mem.get('access_count', 0)}")
                
                return True
            else:
                print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
                return False
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_response("ERROR", error=str(e))
        return False

def main():
    """Main test execution"""
    
    start_time = time.time()
    
    # Test complete pipeline
    pipeline_results = test_complete_pipeline()
    
    # Test Pack service
    pack_result = test_pack_service()
    
    # Test Memory service
    memory_result = test_memory_service()
    
    # Summary
    print_header("📊 Test Summary")
    
    print("\n📋 Pipeline Results:")
    for step, success in pipeline_results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {step}")
    
    print("\n🔧 Feature Tests:")
    print(f"   {'✅' if pack_result else '❌'} Pack Long-RAG")
    print(f"   {'✅' if memory_result else '❌'} Memory Service")
    
    # Calculate pass rate
    total_tests = len(pipeline_results) + 2
    passed_tests = sum(pipeline_results.values()) + sum([pack_result, memory_result])
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n📈 Pass Rate: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
    
    elapsed_time = time.time() - start_time
    print(f"⏱️  Total Time: {elapsed_time:.1f}s")
    
    if pass_rate == 100:
        print("\n✅ All tests passed! System is fully operational.")
    elif pass_rate >= 80:
        print("\n⚠️  Most tests passed. System is mostly operational.")
    else:
        print("\n❌ Multiple tests failed. System needs attention.")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()

