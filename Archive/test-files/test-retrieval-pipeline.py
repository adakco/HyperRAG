#!/usr/bin/env python3
"""
Test Complete Pipeline Including Retrieval
"""

import requests
import json
import time

BASE_URL = "http://localhost"

print("\n" + "="*80)
print("  Test Complete RAG Pipeline with Retrieval")
print("="*80)

# Step 1: Ingest document
print("\n📥 Step 1: Ingesting document...")
doc_id = f"retrieval-test-{int(time.time())}"

test_content = """
HyperRAG is a state-of-the-art RAG system developed in Iran.
The system uses Qdrant for vector search and Neo4j for knowledge graphs.
Key features include multi-language support, hybrid retrieval, and agent orchestration.
"""

with open("/tmp/test_doc.txt", "w") as f:
    f.write(test_content)

with open("/tmp/test_doc.txt", "rb") as f:
    files = {"file": f}
    data = {
        "doc_id": doc_id,
        "tenant": "test",
        "project": "test-project",
        "lang": "en"
    }
    response = requests.post(f"{BASE_URL}:8000/ingest", files=files, data=data, timeout=30)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Document ingested: {doc_id}")
    print(f"   Version: {result.get('version')}")
    uri_raw = result.get('uri_raw', '')
    version = result.get('version')
    
    # Wait for NATS events to process
    print("\n⏳ Waiting for pipeline to process (NATS events)...")
    time.sleep(5)
    
    # Step 2: Manually trigger chunking
    print("\n📦 Step 2: Chunking document...")
    chunk_response = requests.post(
        f"{BASE_URL}:8003/chunk",
        params={
            "doc_id": doc_id,
            "version": str(version),
            "uri_clean": f"s3://raw/test/test-project/{doc_id}/{version}",
            "lang": "en",
            "tenant": "test"
        },
        timeout=30
    )
    
    if chunk_response.status_code == 200:
        chunk_result = chunk_response.json()
        print(f"✅ Chunked: {chunk_result.get('total_chunks')} chunks")
        uri_processed = chunk_result.get('uri_processed')
        
        # Step 3: Generate embeddings
        print("\n🔢 Step 3: Generating embeddings...")
        embed_response = requests.post(
            f"{BASE_URL}:8004/embed",
            params={
                "doc_id": doc_id,
                "version": str(version),
                "uri_processed": uri_processed,
                "lang": "en",
                "tenant": "test",
                "project": "test-project"
            },
            timeout=60
        )
        
        if embed_response.status_code == 200:
            embed_result = embed_response.json()
            print(f"✅ Embedded: {embed_result.get('total_points')} points")
            
            # Wait a bit for Qdrant to index
            time.sleep(2)
            
            # Step 4: Retrieve
            print("\n🔍 Step 4: Testing retrieval...")
            retrieve_response = requests.post(
                f"{BASE_URL}:8002/retrieve",
                json={
                    "query": "HyperRAG features",
                    "tenant": "test",
                    "project": "test-project",
                    "lang": "en",
                    "limit": 5
                },
                timeout=30
            )
            
            if retrieve_response.status_code == 200:
                retrieve_result = retrieve_response.json()
                results = retrieve_result.get('results', [])
                print(f"\n📊 Retrieval Results: {len(results)} documents")
                
                if len(results) > 0:
                    print("\n   Top Results:")
                    for i, res in enumerate(results[:3]):
                        print(f"     {i+1}. Score: {res.get('score', 0):.3f}")
                        print(f"        Content: {res.get('content', '')[:60]}...")
                    print("\n✅ SUCCESS! Retrieval is working correctly!")
                else:
                    print("\n⚠️  WARNING: Retrieval returned 0 results")
                    print("   This might mean:")
                    print("   - Embeddings not stored correctly")
                    print("   - Project filter not matching")
                    print("   - Query not matching document content")
            else:
                print(f"\n❌ Retrieval failed: {retrieve_response.status_code}")
                print(f"   {retrieve_response.text}")
        else:
            print(f"\n❌ Embedding failed: {embed_response.status_code}")
            print(f"   {embed_response.text}")
    else:
        print(f"\n❌ Chunking failed: {chunk_response.status_code}")
        print(f"   {chunk_response.text}")
else:
    print(f"\n❌ Ingestion failed: {response.status_code}")
    print(f"   {response.text}")

print("\n" + "="*80 + "\n")

