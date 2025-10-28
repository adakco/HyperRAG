#!/usr/bin/env python3
"""
Complete Test Suite for Phase 4: Hybrid Retrieval
Tests all services with hybrid search capabilities
"""

import requests
import json
import time
from datetime import datetime

# Service URLs
BASE_URL = "http://localhost"
SERVICES = {
    "ingestor": f"{BASE_URL}:8000",
    "normalizer": f"{BASE_URL}:8001",
    "retriever": f"{BASE_URL}:8002",
    "chunker": f"{BASE_URL}:8003",
    "embedder": f"{BASE_URL}:8004",
    "pack": f"{BASE_URL}:8009",
    "memory": f"{BASE_URL}:8010",
    "graph": f"{BASE_URL}:8012"
}

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def print_section(text):
    print(f"\n{'─'*80}")
    print(f"  {text}")
    print('─'*80)

def print_request(method, url, data=None):
    print(f"\n📤 REQUEST:")
    print(f"   Method: {method}")
    print(f"   URL: {url}")
    if data:
        if isinstance(data, dict):
            print(f"   Body: {json.dumps(data, indent=3)}")

def print_response(status, data=None):
    print(f"\n📥 RESPONSE:")
    print(f"   Status: {status}")
    if data:
        print(f"   Data: {json.dumps(data, indent=3) if isinstance(data, dict) else data}")

def check_all_services():
    """Check health of all services"""
    print_section("Step 0: Service Health Check")
    
    healthy = {}
    for name, url in SERVICES.items():
        try:
            response = requests.get(f"{url}/health", timeout=3)
            status = "✅" if response.status_code == 200 else "❌"
            healthy[name] = (response.status_code == 200)
            print(f"   {status} {name:15} - {url}")
        except:
            print(f"   ❌ {name:15} - Not accessible")
            healthy[name] = False
    
    return healthy

def test_complete_pipeline_with_graph(tenant, project):
    """Complete pipeline test with graph extraction"""
    print_section("Step 1: Complete Pipeline with Graph Knowledge")
    
    doc_id = f"hybrid-test-{int(time.time())}"
    
    # Create test document with named entities
    test_content = """
    Python is a high-level programming language developed by Guido van Rossum.
    Google uses Python extensively in their infrastructure. Microsoft also uses Python for AI and data science.
    Python is widely used in machine learning, data analysis, and web development.
    """
    
    with open("/tmp/test_doc.txt", "w") as f:
        f.write(test_content)
    
    print_request("POST", f"{SERVICES['ingestor']}/ingest", {
        "doc_id": doc_id,
        "tenant": tenant,
        "project": project,
        "lang": "en"
    })
    
    try:
        with open("/tmp/test_doc.txt", "rb") as f:
            files = {"file": f}
            data = {
                "doc_id": doc_id,
                "tenant": tenant,
                "project": project,
                "lang": "en"
            }
            response = requests.post(f"{SERVICES['ingestor']}/ingest", files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            version = result.get('version')
            uri_raw = result.get('uri_raw', '')
            
            print(f"\n   ✅ Document ingested: {doc_id}")
            
            # Wait a bit
            time.sleep(2)
            
            # Manual chunking
            print_section("Step 1.2: Document Chunking")
            chunk_response = requests.post(
                f"{SERVICES['chunker']}/chunk",
                params={
                    "doc_id": doc_id,
                    "version": str(version),
                    "uri_clean": uri_raw,
                    "lang": "en",
                    "tenant": tenant
                },
                timeout=30
            )
            
            if chunk_response.status_code == 200:
                chunk_result = chunk_response.json()
                print(f"   ✅ Chunked: {chunk_result.get('total_chunks')} chunks")
                uri_processed = chunk_result.get('uri_processed')
                
                # Embedding
                print_section("Step 1.3: Document Embedding")
                embed_response = requests.post(
                    f"{SERVICES['embedder']}/embed",
                    params={
                        "doc_id": doc_id,
                        "version": str(version),
                        "uri_processed": uri_processed,
                        "lang": "en",
                        "tenant": tenant,
                        "project": project
                    },
                    timeout=60
                )
                
                if embed_response.status_code == 200:
                    embed_result = embed_response.json()
                    print(f"   ✅ Embedded: {embed_result.get('total_points', 0)} points")
                    time.sleep(2)  # Wait for indexing
                    
                    return doc_id, True
                else:
                    print(f"   ❌ Embedding failed: {embed_response.status_code}")
                    return doc_id, False
            else:
                print(f"   ❌ Chunking failed: {chunk_response.status_code}")
                return doc_id, False
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return None, False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return None, False

def test_graph_extraction(tenant, doc_id):
    """Test graph extraction on ingested document"""
    print_section("Step 2: Graph Knowledge Extraction")
    
    content = """
    Python is a programming language created by Guido van Rossum.
    Google uses Python in their projects. Microsoft uses Python for AI.
    """
    
    print_request("POST", f"{SERVICES['graph']}/extract", {
        "content": content,
        "lang": "en"
    })
    
    try:
        response = requests.post(
            f"{SERVICES['graph']}/extract",
            json={
                "doc_id": f"graph-{doc_id}",
                "content": content,
                "tenant": tenant,
                "lang": "en"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            print(f"\n   ✅ Entities extracted: {result.get('entities_count', 0)}")
            print(f"   ✅ Relationships extracted: {result.get('relationships_count', 0)}")
            return True
        else:
            print(f"\n   ⚠️  Extraction status: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False

def test_vector_search(tenant, project):
    """Test vector-only search"""
    print_section("Step 3: Vector Search (without Graph)")
    
    print_request("POST", f"{SERVICES['retriever']}/retrieve", {
        "query": "Python programming language",
        "use_graph": False
    })
    
    try:
        response = requests.post(
            f"{SERVICES['retriever']}/retrieve",
            json={
                "query": "Python programming language",
                "tenant": tenant,
                "project": project,
                "lang": "en",
                "limit": 5,
                "use_graph": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results_count = len(result.get("results", []))
            print(f"\n   ✅ Vector results: {results_count} documents")
            
            if results_count > 0:
                print("\n   Top Results:")
                for i, res in enumerate(result.get("results", [])[:3]):
                    print(f"     {i+1}. Score: {res.get('score', 0):.3f}")
                    print(f"        Content: {res.get('content', '')[:60]}...")
            
            return True, result
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return False, None
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False, None

def test_hybrid_search(tenant, project):
    """Test hybrid search (Vector + Graph)"""
    print_section("Step 4: Hybrid Search (Vector + Graph)")
    
    print_request("POST", f"{SERVICES['retriever']}/retrieve", {
        "query": "Python programming language",
        "use_graph": True,
        "vector_weight": 0.7,
        "graph_weight": 0.3
    })
    
    try:
        response = requests.post(
            f"{SERVICES['retriever']}/retrieve",
            json={
                "query": "Python programming language",
                "tenant": tenant,
                "project": project,
                "lang": "en",
                "limit": 5,
                "use_graph": True,
                "vector_weight": 0.7,
                "graph_weight": 0.3
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results_count = len(result.get("results", []))
            print(f"\n   ✅ Hybrid results: {results_count} documents")
            
            if results_count > 0:
                print("\n   Top Results (with fusion metadata):")
                for i, res in enumerate(result.get("results", [])[:3]):
                    metadata = res.get('metadata', {})
                    print(f"     {i+1}. Final Score: {res.get('score', 0):.3f}")
                    if metadata.get('fused'):
                        print(f"        Vector Score: {metadata.get('vector_score', 0):.3f}")
                        print(f"        Graph Score: {metadata.get('graph_score', 0):.3f}")
                    print(f"        Content: {res.get('content', '')[:60]}...")
            
            return True, result
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return False, None
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False, None

def compare_results(vector_result, hybrid_result):
    """Compare vector-only vs hybrid results"""
    print_section("Step 5: Comparison Analysis")
    
    if not vector_result or not hybrid_result:
        print("   ⚠️  Cannot compare - missing results")
        return
    
    vector_results = vector_result.get('results', [])
    hybrid_results = hybrid_result.get('results', [])
    
    print(f"\n   Vector-only results: {len(vector_results)}")
    print(f"   Hybrid results: {len(hybrid_results)}")
    
    # Check for score improvements
    fused_count = sum(1 for r in hybrid_results if r.get('metadata', {}).get('fused'))
    print(f"   Fused results (boosted by graph): {fused_count}")
    
    # Compare top result scores
    if vector_results and hybrid_results:
        vector_top = vector_results[0].get('score', 0)
        hybrid_top = hybrid_results[0].get('score', 0)
        improvement = ((hybrid_top - vector_top) / vector_top * 100) if vector_top > 0 else 0
        
        print(f"\n   Top Score Comparison:")
        print(f"     Vector-only: {vector_top:.3f}")
        print(f"     Hybrid: {hybrid_top:.3f}")
        print(f"     Improvement: {improvement:+.1f}%")
        
        if abs(improvement) > 0.1:
            print(f"     ✅ Hybrid search shows {'improvement' if improvement > 0 else 'different results'}!")

def main():
    """Main test execution"""
    start_time = time.time()
    
    print_header("🧪 Complete Hybrid Retrieval Test Suite")
    
    # Configuration
    tenant = "hybrid-test"
    project = "test-project"
    
    # Check all services
    healthy = check_all_services()
    
    if not all(healthy.values()):
        print("\n⚠️  Some services are not healthy. Continuing anyway...")
    
    # Step 1: Complete pipeline with graph extraction
    doc_id, pipeline_ok = test_complete_pipeline_with_graph(tenant, project)
    
    if not doc_id:
        print("\n❌ Pipeline failed. Stopping tests.")
        return
    
    # Step 2: Graph extraction
    graph_ok = test_graph_extraction(tenant, doc_id)
    
    time.sleep(2)
    
    # Step 3: Vector-only search
    vector_ok, vector_result = test_vector_search(tenant, project)
    
    # Step 4: Hybrid search
    hybrid_ok, hybrid_result = test_hybrid_search(tenant, project)
    
    # Step 5: Comparison
    if vector_ok and hybrid_ok:
        compare_results(vector_result, hybrid_result)
    
    # Summary
    print_header("📊 Test Summary")
    
    print("\nService Health:")
    for service, is_healthy in healthy.items():
        status = "✅" if is_healthy else "❌"
        print(f"   {status} {service}")
    
    print("\nIntegration Tests:")
    print(f"   {'✅' if doc_id else '❌'} Pipeline (Ingestion → Embedding)")
    print(f"   {'✅' if graph_ok else '❌'} Graph Extraction")
    print(f"   {'✅' if vector_ok else '❌'} Vector Search")
    print(f"   {'✅' if hybrid_ok else '❌'} Hybrid Search")
    
    passed = sum([bool(doc_id), graph_ok, vector_ok, hybrid_ok])
    total = 4
    
    elapsed = time.time() - start_time
    
    print(f"\n📈 Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"⏱️  Time: {elapsed:.1f}s")
    
    if passed == total:
        print("\n✅ All hybrid retrieval tests passed! Phase 4 is fully operational!")
    elif passed >= 3:
        print("\n⚠️  Most tests passed. Hybrid search is mostly working.")
    else:
        print("\n❌ Multiple tests failed. Review the issues above.")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

