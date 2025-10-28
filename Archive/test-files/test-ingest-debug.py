#!/usr/bin/env python3
"""
Debug script to test ingestion with full traceback
"""
import requests
import traceback

url = "http://localhost:8000/ingest"

# Prepare test data
files = {
    'file': ('README.md', open('README.md', 'rb'), 'text/markdown')
}

data = {
    'doc_id': 'test-debug-traceback',
    'tenant': 'test',
    'project': 'test',
    'lang': 'en',
    'title': 'Debug Traceback Test'
}

try:
    print("🔍 Testing ingestion with debug...")
    response = requests.post(url, files=files, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code != 200:
        print(f"\n❌ Error: {response.json()}")
    else:
        print(f"\n✅ Success: {response.json()}")
        
except Exception as e:
    print(f"\n❌ Exception: {e}")
    traceback.print_exc()

