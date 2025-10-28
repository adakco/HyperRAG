#!/usr/bin/env python3
"""
Complete System Integration Test
Tests all HyperRAG services working together end-to-end
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
        else:
            print(f"   Body: {data[:200]}...")

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

def test_ingestion(tenant, project):
    """Test document ingestion"""
    print_section("Step 1: Document Ingestion")
    
    doc_id = f"integration-test-{int(time.time())}"
    
    # Create test document
    test_content = """
    HyperRAG is a state-of-the-art Retrieval Augmented Generation system developed in Iran.
    The system uses advanced AI techniques including vector search, knowledge graphs, and agentic orchestration.
    Key features include multi-language support for Persian and English, hybrid retrieval combining vectors and graphs,
    long-context management through intelligent packing, and memory systems for episodic and semantic memory.
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
            print(f"\n   ✅ Document ingested: {doc_id}")
            return doc_id, result
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return None, None
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return None, None

def test_memory_storage(tenant):
    """Test storing memory"""
    print_section("Step 2: Memory Storage")
    
    memory_content = f"User wants to know about HyperRAG system architecture at {datetime.now()}"
    
    print_request("POST", f"{SERVICES['memory']}/store", {
        "content": memory_content,
        "memory_type": "episodic"
    })
    
    try:
        response = requests.post(
            f"{SERVICES['memory']}/store",
            params={
                "tenant": tenant,
                "content": memory_content,
                "memory_type": "episodic",
                "lang": "en"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            print(f"\n   ✅ Memory stored: {result.get('memory_id', '')}")
            return True
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False

def test_graph_extraction(tenant):
    """Test knowledge graph extraction"""
    print_section("Step 3: Knowledge Graph Extraction")
    
    content = """
    HyperRAG system is built by an Iranian development team.
    The system integrates with Qdrant for vector search and Neo4j for knowledge graphs.
    It supports both Persian and English languages.
    """
    
    print_request("POST", f"{SERVICES['graph']}/extract", {
        "content": content,
        "lang": "en"
    })
    
    try:
        response = requests.post(
            f"{SERVICES['graph']}/extract",
            json={
                "doc_id": "test-graph-doc",
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
        print(f"\n   ⚠️  Error: {e}")
        return False

def test_pack_service(tenant):
    """Test context packing"""
    print_section("Step 4: Context Packing")
    
    contexts = [
        "HyperRAG uses vector search with Qdrant for semantic similarity.",
        "Neo4j knowledge graph stores entities and relationships.",
        "Memory system provides episodic and semantic memory capabilities.",
        "Agent orchestration enables complex reasoning workflows."
    ]
    
    print_request("POST", f"{SERVICES['pack']}/pack", {
        "contexts": contexts,
        "max_tokens": 150
    })
    
    try:
        response = requests.post(
            f"{SERVICES['pack']}/pack",
            json={
                "query": "What are the key features of HyperRAG?",
                "contexts": contexts,
                "lang": "en",
                "tenant": tenant,
                "max_tokens": 150,
                "include_summaries": False
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            print(f"\n   ✅ Packs created: {len(result.get('packs', []))}")
            print(f"   ✅ Efficiency: {result.get('efficiency_ratio', 0):.1%}")
            return True
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False

def test_retrieval(tenant, project):
    """Test document retrieval"""
    print_section("Step 5: Document Retrieval")
    
    print_request("POST", f"{SERVICES['retriever']}/retrieve", {
        "query": "HyperRAG architecture",
        "project": project
    })
    
    try:
        response = requests.post(
            f"{SERVICES['retriever']}/retrieve",
            json={
                "query": "HyperRAG architecture",
                "tenant": tenant,
                "project": project,
                "lang": "en",
                "limit": 5
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            results_count = len(result.get("results", []))
            print(f"\n   ✅ Retrieved: {results_count} documents")
            
            if results_count > 0:
                print("\n   Top Results:")
                for i, res in enumerate(result.get("results", [])[:3]):
                    print(f"     {i+1}. Score: {res.get('score', 0):.3f} - {res.get('content', '')[:60]}...")
            
            return True
        else:
            print_response("FAILED", error=f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False

def main():
    """Main test execution"""
    start_time = time.time()
    
    print_header("🧪 Complete HyperRAG System Integration Test")
    
    # Configuration
    tenant = "integration-test"
    project = "test-project"
    
    # Check all services
    healthy = check_all_services()
    
    if not all(healthy.values()):
        print("\n⚠️  Some services are not healthy. Continuing anyway...")
    
    # Step 1: Ingestion
    doc_id, ingest_result = test_ingestion(tenant, project)
    
    if not doc_id:
        print("\n❌ Ingestion failed. Stopping tests.")
        return
    
    version = ingest_result.get('version')
    time.sleep(2)
    
    # Step 1.5: Chunking (manual trigger for retrieval test)
    print_section("Step 1.5: Document Chunking")
    chunk_response = requests.post(
        f"{SERVICES['chunker']}/chunk",
        params={
            "doc_id": doc_id,
            "version": str(version),
            "uri_clean": ingest_result.get('uri_raw', ''),
            "lang": "en",
            "tenant": tenant
        },
        timeout=30
    )
    chunk_result = chunk_response.json() if chunk_response.status_code == 200 else None
    
    # Step 1.6: Embedding (manual trigger for retrieval test)
    print_section("Step 1.6: Document Embedding")
    if chunk_result:
        embed_response = requests.post(
            f"{SERVICES['embedder']}/embed",
            params={
                "doc_id": doc_id,
                "version": str(version),
                "uri_processed": chunk_result.get('uri_processed', ''),
                "lang": "en",
                "tenant": tenant,
                "project": project
            },
            timeout=60
        )
        embed_result = embed_response.json() if embed_response.status_code == 200 else None
        if embed_result:
            print(f"   ✅ Embedded: {embed_result.get('total_points', 0)} points")
        time.sleep(2)  # Wait for indexing
    
    # Step 2: Memory
    memory_ok = test_memory_storage(tenant)
    
    time.sleep(1)
    
    # Step 3: Graph Extraction
    graph_ok = test_graph_extraction(tenant)
    
    # Step 4: Pack
    pack_ok = test_pack_service(tenant)
    
    # Step 5: Retrieval
    retrieval_ok = test_retrieval(tenant, project)
    
    # Summary
    print_header("📊 Test Summary")
    
    print("\nService Health:")
    for service, is_healthy in healthy.items():
        status = "✅" if is_healthy else "❌"
        print(f"   {status} {service}")
    
    print("\nIntegration Tests:")
    print(f"   {'✅' if doc_id else '❌'} Document Ingestion")
    print(f"   {'✅' if memory_ok else '❌'} Memory Storage")
    print(f"   {'✅' if graph_ok else '⚠️ '} Graph Extraction")
    print(f"   {'✅' if pack_ok else '❌'} Context Packing")
    print(f"   {'✅' if retrieval_ok else '❌'} Document Retrieval")
    
    passed = sum([bool(doc_id), memory_ok, graph_ok, pack_ok, retrieval_ok])
    total = 5
    
    elapsed = time.time() - start_time
    
    print(f"\n📈 Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"⏱️  Time: {elapsed:.1f}s")
    
    if passed == total:
        print("\n✅ All integration tests passed! System is fully operational.")
    elif passed >= 3:
        print("\n⚠️  Most tests passed. System is mostly operational.")
    else:
        print("\n❌ Multiple tests failed. System needs attention.")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

