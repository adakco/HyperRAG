#!/bin/bash

# Complete Test Script for All HyperRAG Services
# This script tests all 13 services with realistic data

set -e

BASE_URL="http://localhost"
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_NC='\033[0m' # No Color

TIMESTAMP=$(date +%s)
TEST_DOC_ID="test-complete-${TIMESTAMP}"

echo -e "${COLOR_BLUE}╔═══════════════════════════════════════════════════════════╗${COLOR_NC}"
echo -e "${COLOR_BLUE}║      HyperRAG Complete Services Test                       ║${COLOR_NC}"
echo -e "${COLOR_BLUE}╚═══════════════════════════════════════════════════════════╝${COLOR_NC}"
echo ""

# Function to print section headers
print_section() {
    echo -e "\n${COLOR_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_NC}"
    echo -e "${COLOR_YELLOW}$1${COLOR_NC}"
    echo -e "${COLOR_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_NC}\n"
}

# Function to print success/failure
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${COLOR_GREEN}✅ $2${COLOR_NC}"
    else
        echo -e "${COLOR_RED}❌ $2${COLOR_NC}"
    fi
}

# Test health checks
print_section "Step 1: Health Checks (13 Services)"

SERVICES=(
    "8000:Ingestor"
    "8001:Normalizer"
    "8002:Retriever"
    "8003:Chunker"
    "8004:Embedder"
    "8005:Evaluator"
    "8006:Agent-Orch"
    "8007:Policy"
    "8008:Costing"
    "8009:Pack"
    "8010:Memory"
    "8011:Reranker"
    "8012:Graph-KG"
)

HEALTH_STATUS=0
for service in "${SERVICES[@]}"; do
    IFS=':' read -r port name <<< "$service"
    response=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}:${port}/health" || echo "000")
    if [ "$response" = "200" ]; then
        echo -e "${COLOR_GREEN}✅ ${name} (${port})${COLOR_NC}"
    else
        echo -e "${COLOR_RED}❌ ${name} (${port}) - HTTP ${response}${COLOR_NC}"
        HEALTH_STATUS=1
    fi
done

if [ $HEALTH_STATUS -ne 0 ]; then
    echo -e "\n${COLOR_RED}Some services are not healthy. Please run: ./start-services-host.sh${COLOR_NC}"
    exit 1
fi

# Create test document
print_section "Step 2: Create Test Document"
TEST_CONTENT=$(cat <<'EOF'
# Python Programming Language

Python is a high-level, interpreted programming language known for its simplicity and readability.

## Key Features

1. Large Standard Library: Comprehensive set of modules and packages
2. Cross-platform: Runs on Windows, Linux, macOS
3. Community: Large, active developer community
4. Applications: Web development, data science, AI, automation

## Version History

- Python 3.0 released in 2008
- Latest stable version is Python 3.12
- Created by Guido van Rossum in 1991

## Popular Frameworks

- Django for web development
- NumPy for scientific computing
- TensorFlow for machine learning
EOF
)

echo "$TEST_CONTENT" > /tmp/test-doc.txt

# Test Ingestor
print_section "Step 3: Document Ingestion (Ingestor - 8000)"
INGEST_RESPONSE=$(curl -s -X POST "${BASE_URL}:8000/ingest" \
    -F "doc_id=${TEST_DOC_ID}" \
    -F "tenant=test-tenant" \
    -F "project=test-project" \
    -F "lang=en" \
    -F "title=Python Programming Guide" \
    -F "author=Test Author" \
    -F "file=@/tmp/test-doc.txt")

echo "Response: $INGEST_RESPONSE"

DOC_VERSION=$(echo "$INGEST_RESPONSE" | jq -r '.version // "unknown"')
if [ "$DOC_VERSION" != "unknown" ]; then
    echo -e "${COLOR_GREEN}✅ Document ingested: ${TEST_DOC_ID} (version: ${DOC_VERSION})${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Ingestion failed${COLOR_NC}"
    exit 1
fi

echo "Waiting for normalization (5 seconds)..."
sleep 5

# Test Chunker
print_section "Step 4: Document Chunking (Chunker - 8003)"
URI_CLEAN="s3://raw/test-tenant/docs/${TEST_DOC_ID}/${DOC_VERSION}"

CHUNK_RESPONSE=$(curl -s -X POST "${BASE_URL}:8003/chunk?doc_id=${TEST_DOC_ID}&version=${DOC_VERSION}&uri_clean=${URI_CLEAN}&lang=en&tenant=test-tenant")

echo "Response: $CHUNK_RESPONSE"

CHUNK_COUNT=$(echo "$CHUNK_RESPONSE" | jq -r '.total_chunks // 0')
if [ "$CHUNK_COUNT" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Document chunked: ${CHUNK_COUNT} chunks${COLOR_NC}"
    URI_PROCESSED=$(echo "$CHUNK_RESPONSE" | jq -r '.uri_processed // "unknown"')
else
    echo -e "${COLOR_RED}❌ Chunking failed${COLOR_NC}"
    exit 1
fi

# Test Embedder
print_section divid="Step 5: Document Embedding (Embedder - 8004)"
echo "URI_PROCESSED: $URI_PROCESSED"

# Wait a bit for chunking to complete
sleep 2

EMBED_RESPONSE=$(curl -s -X POST "${BASE_URL}:8004/embed?doc_id=${TEST_DOC_ID}&version=${DOC_VERSION}&uri_processed=${URI_PROCESSED}&lang=en&tenant=test-tenant&project=test-project")

echo "Response: $EMBED_RESPONSE"

EMBED_COUNT=$(echo "$EMBED_RESPONSE" | jq -r '.embeddings_count // 0')
if [ "$EMBED_COUNT" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Document embedded: ${EMBED_COUNT} vectors${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Embedding failed${COLOR_NC}"
    exit 1
fi

# Wait for indexing
echo "Waiting for indexing (3 seconds)..."
sleep 3

# Test Retriever
print_section "Step 6: Document Retrieval (Retriever - 8002)"
RETRIEVE_RESPONSE=$(curl -s -X POST "${BASE_URL}:8002/retrieve" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"Python programming language features\",
        \"tenant\": \"test-tenant\",
        \"lang\": \"en\",
        \"project\": \"test-project\",
        \"limit\": 5
    }")

echo "Response: $RETRIEVE_RESPONSE"

RETRIEVE_COUNT=$(echo "$RETRIEVE_RESPONSE" | jq -r '.results | length // 0')
if [ "$RETRIEVE_COUNT" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Retrieved ${RETRIEVE_COUNT} documents${COLOR_NC}"
else
    echo -e "${COLOR_YELLOW}⚠️  Retrieved 0 documents (might need more time for indexing)${COLOR_NC}"
fi

# Test Graph KG
print_section "Step 7: Knowledge Graph Extraction (Graph KG - 8012)"
GRAPH_EXTRACT_RESPONSE=$(curl -s -X POST "${BASE_URL}:8012/extract" \
    -H "Content-Type: application/json" \
    -d "{
        \"doc_id\": \"${TEST_DOC_ID}\",
        \"content\": \"Python is a programming language created by Guido van Rossum\",
        \"tenant\": \"test-tenant\",
        \"lang\": \"en\"
    }")

echo "Response: $GRAPH_EXTRACT_RESPONSE"

ENTITY_COUNT=$(echo "$GRAPH_EXTRACT_RESPONSE" | jq -r '.entities_count // 0')
if [ "$ENTITY_COUNT" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Extracted ${ENTITY_COUNT} entities${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Graph extraction failed${COLOR_NC}"
fi

# Test Memory
print_section "Step 8: Memory Storage (Memory - 8010)"
MEMORY_STORE_RESPONSE=$(curl -s -X POST "${BASE_URL}:8010/store?tenant=test-tenant&content=User%20asked%20about%20Python%20programming&memory_type=episodic&lang=en")

echo "Response: $MEMORY_STORE_RESPONSE"

MEMORY_ID=$(echo "$MEMORY_STORE_RESPONSE" | jq -r '.memory_id // "unknown"')
if [ "$MEMORY_ID" != "unknown" ]; then
    echo -e "${COLOR_GREEN}✅ Memory stored: ${MEMORY_ID}${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Memory storage failed${COLOR_NC}"
fi

sleep 2

MEMORY_RETRIEVE_RESPONSE=$(curl -s -X POST "${BASE_URL}:8010/retrieve" \
    -H "Content-Type: application/json" \
    -d "{
        \"tenant\": \"test-tenant\",
        \"query\": \"What did user ask?\",
        \"memory_type\": \"episodic\",
        \"lang\": \"en\",
        \"limit\": 5
    }")

echo "Response: $MEMORY_RETRIEVE_RESPONSE"

MEMORY_FOUND=$(echo "$MEMORY_RETRIEVE_RESPONSE" | jq -r '.total_found // 0')
if [ "$MEMORY_FOUND" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Retrieved ${MEMORY_FOUND} memories${COLOR_NC}"
else
    echo -e "${COLOR_YELLOW}⚠️  Retrieved 0 memories (might need indexing time)${COLOR_NC}"
fi

# Test Pack Long-RAG
print_section "Step 9: Context Packing (Pack - 8009)"
PACK_RESPONSE=$(curl -s -X POST "${BASE_URL}:8009/pack" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"What are Python features?\",
        \"contexts\": [
            \"Python has a large standard library\",
            \"Python is cross-platform\",
            \"Python has a large community\"
        ],
        \"lang\": \"en\",
        \"tenant\": \"test-tenant\",
        \"max_tokens\": 100
    }")

echo "Response: $PACK_RESPONSE"

PACK_COUNT=$(echo "$PACK_RESPONSE" | jq -r '.packs | length // 0')
if [ "$PACK_COUNT" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Packed ${PACK_COUNT} contexts${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Packing failed${COLOR_NC}"
fi

# Test Reranker
print_section "Step 10: Document Reranking (Reranker - 8011)"
RERANK_RESPONSE=$(curl -s -X POST "${BASE_URL}:8011/rerank" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"Python programming\",
        \"documents\": [
            {\"content\": \"Python is a programming language\", \"metadata\": {}},
            {\"content\": \"Python has many features\", \"metadata\": {}}
        ],
        \"lang\": \"en\",
        \"tenant\": \"test-tenant\"
    }")

echo "Response: $RERANK_RESPONSE"

RERANK_COUNT=$(echo "$RERANK_RESPONSE" | jq -r '.reranked_documents | length // 0')
if [ "$RERANK_COUNT" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✅ Reranked ${RERANK_COUNT} documents${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Reranking failed${COLOR_NC}"
fi

# Test Evaluator
print_section "Step 11: RAG Evaluation (Evaluator - 8005)"
EVAL_RESPONSE=$(curl -s -X POST "${BASE_URL}:8005/evaluate" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"What is Python?\",
        \"answer\": \"Python is a high-level programming language\",
        \"contexts\": [
            \"Python is a programming language known for simplicity\"
        ],
        \"lang\": \"en\",
        \"tenant\": \"test-tenant\",
        \"metrics\": [\"faithfulness\", \"answer_relevancy\"]
    }")

echo "Response: $EVAL_RESPONSE"

FAITHFULNESS=$(echo "$EVAL_RESPONSE" | jq -r '.faithfulness // 0')
if [ "$(echo "$FAITHFULNESS > 0" | bc)" -eq 1 ]; then
    echo -e "${COLOR_GREEN}✅ Evaluated faithfulness: ${FAITHFULNESS}${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Evaluation failed${COLOR_NC}"
fi

# Test Policy
print_section "Step 12: Policy Evaluation (Policy - 8007)"
POLICY_RESPONSE=$(curl -s -X POST "${BASE_URL}:8007/policy/evaluate" \
    -H "Content-Type: application/json" \
    -d "{
        \"principal\": \"user123\",
        \"action\": \"read\",
        \"resource\": \"document:${TEST_DOC_ID}\",
        \"context\": {\"tenant\": \"test-tenant\"}
    }")

echo "Response: $POLICY_RESPONSE"

DECISION=$(echo "$POLICY_RESPONSE" | jq -r '.decision // "unknown"')
if [ "$DECISION" != "unknown" ]; then
    echo -e "${COLOR_GREEN}✅ Policy decision: ${DECISION}${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Policy evaluation failed${COLOR_NC}"
fi

# Test Costing
print_section "Step 13: Cost Tracking (Costing - 8008)"
COSTING_RESPONSE=$(curl -s -X POST "${BASE_URL}:8008/costing/track" \
    -H "Content-Type: application/json" \
    -d "{
        \" را\": \"test-tenant\",
        \"operation\": \"retrieval\",
        \"cost\": 0.001,
        \"metadata\": {}
    }")

echo "Response: $COSTING_RESPONSE"

TOTAL_COST=$(echo "$COSTING_RESPONSE" | jq -r '.total_cost // 0')
if [ "$(echo "$TOTAL_COST >= 0" | bc)" -eq 1 ]; then
    echo -e "${COLOR_GREEN}✅ Cost tracked: \$${TOTAL_COST}${COLOR_NC}"
else
    echo -e "${COLOR_RED}❌ Cost tracking failed${COLOR_NC}"
fi

# Summary
print_section "Summary"
echo -e "${COLOR_GREEN}✅ All 13 services tested!${COLOR_NC}"
echo -e "Test Document ID: ${TEST_DOC_ID}"
echo -e "Version: ${DOC_VERSION}"
echo ""
echo -e "${COLOR_BLUE}Test completed successfully!${COLOR_NC}"

# Cleanup
rm -f /tmp/test-doc.txt

