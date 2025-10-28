#!/usr/bin/env python3
"""
Comprehensive Test Suite for Knowledge Graph Service
Tests entity extraction, graph storage, and querying
"""

import requests
import json
import time

BASE_URL = "http://localhost:8012"

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_step(num, title):
    print(f"\n📋 Step {num}: {title}")
    print("-"*70)

def print_request(method, url, data=None):
    print(f"\n📤 REQUEST:")
    print(f"   {method} {url}")
    if data:
        print(f"   Data: {json.dumps(data, indent=2)}")

def print_response(status, data=None):
    print(f"\n📥 RESPONSE:")
    print(f"   Status: {status}")
    if data:
        print(f"   Data: {json.dumps(data, indent=2)}")

def test_health():
    """Test service health"""
    print_header("Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            print("\n✅ Graph KG Service is healthy!")
            return True
        else:
            print(f"\n   ❌ Failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_entity_extraction():
    """Test entity extraction from text"""
    print_header("Entity Extraction Test")
    
    test_document = """
    Apple Inc. is an American multinational technology company headquartered in Cupertino, California.
    The company was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in 1976.
    Apple designs and manufactures consumer electronics, including the iPhone, iPad, and MacBook.
    Tim Cook is the current CEO of Apple Inc.
    """
    
    request_data = {
        "doc_id": f"test-doc-{int(time.time())}",
        "content": test_document,
        "tenant": "test",
        "lang": "en"
    }
    
    print_request("POST", f"{BASE_URL}/extract", request_data)
    
    try:
        response = requests.post(f"{BASE_URL}/extract", json=request_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            
            print(f"\n✅ Entities extracted: {result.get('entities_count', 0)}")
            print(f"✅ Relationships extracted: {result.get('relationships_count', 0)}")
            
            # Show extracted entities
            print("\n📊 Extracted Entities:")
            for i, entity in enumerate(result.get('entities', [])[:5]):
                print(f"   {i+1}. {entity.get('label', '')} ({entity.get('type', '')})")
            
            return True
        else:
            print(f"\n   ❌ Failed: HTTP {response.status_code}")
 Precondition(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_graph_query(mock_ok=True):
    """Test graph querying"""
    print_header("Graph Query Test")
    
    request_data = {
        "query": "Apple",
        "tenant": "test",
        "max_results": 5
    }
    
    print_request("POST", f"{BASE_URL}/query", request_data)
    
    try:
        response = requests.post(f"{BASE_URL}/query", json=request_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print_response("SUCCESS", result)
            
            print(f"\n✅ Entities found: {result.get('total', 0)}")
            
            # Show query results
            print("\n📊 Query Results:")
            for i, res in enumerate(result.get('results', [])[:3]):
                print(f"   {i+1}. Label: {res.get('label', '')}, Type: {res.get('type', '')}")
            
            return True
        else:
            print(f"\n   ❌ Failed: HTTP {response.status_code}")
 Precondition(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_comprehensive_flow():
    """Test complete flow: extraction → storage → query"""
    print_header("Complete Flow Test")
    
    test_document = """
    Microsoft Corporation is an American multinational technology corporation headquartered in Redmond, Washington.
    The company was founded by Bill Gates and Paul Allen in 1975.
    Microsoft develops and manufactures software, including Windows, Office, and Azure cloud services.
    Satya Nadella has been the CEO of Microsoft since 2014.
    """
    
    # Step 1: Extract and store
    print_step(1, "Extract and Store Entities")
    
    extract_data = {
        "doc_id": "microsoft-test",
        "content": test_document,
        "tenant": "test",
        "lang": "en"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/extract", json=extract_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Stored {result.get('entities_count', 0)} entities")
            print(f"✅ Stored {result.get('relationships_count', 0)} relationships")
            
            time.sleep(1)
            
            # Step 2: Query the graph
            print_step(2, "Query Graph for Entities")
            
            query_data = {
                "query": "Microsoft",
                "tenant": "test",
                "max_results": 5
            }
            
            response = requests.post(f"{BASE_URL}/query", json=query_data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Found {result.get('total', 0)} matching entities")
                
                return True
            else:
                print(f"❌ Query failed: HTTP {response.status_code}")
                return False
        else:
            print(f"❌ Extraction failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main test execution"""
    print("\n" + "="*70)
    print("  🧪 Knowledge Graph Service Comprehensive Test")
    print("="*70)
    
    results = {
        "health": test_health(),
        "extraction": test_entity_extraction(),
        "query": test_graph_query(),
        "complete_flow": test_comprehensive_flow()
    }
    
    # Summary
    print_header("Test Summary")
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\n📊 Pass Rate: {passed}/{total} ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n✅ All tests passed! Knowledge Graph Service is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the service.")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

