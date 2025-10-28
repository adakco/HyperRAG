#!/usr/bin/env python3
import requests, json

# Test 1: Health
r = requests.get("http://localhost:8012/health")
print("Health:", r.json())

# Test 2: Extract
r = requests.post("http://localhost:8012/extract", json={
    "doc_id": "test1",
    "content": "Apple Inc. is a company in California.",
    "tenant": "test",
    "lang": "en"
})
print("\nExtract:", r.status_code)
print(r.text[:200])

# Test 3: Query
r = requests.post("http://localhost:8012/query", json={
    "query": "Apple",
    "tenant": "test",
    "max_results": 5
})
print("\nQuery:", r.status_code)
print(r.text[:200])
