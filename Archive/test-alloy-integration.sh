#!/bin/bash
# Test Alloy Integration with HyperRAG Services

echo "🧪 تست Integration Alloy با HyperRAG"
echo "==================================="
echo ""

# Step 1: Send test request
echo "📋 Step 1: ارسال درخواست تست..."
DOC_ID="alloy-test-$(date +%s)"
curl -s -X POST http://localhost:8000/ingest \
  -F "doc_id=$DOC_ID" \
  -F "tenant=test" \
  -F "project=alpha" \
  -F "lang=en" \
  -F "file=@test.txt" > /dev/null

echo "✅ درخواasi ارسال شد: $DOC_ID"
echo ""

# Step 2: Wait a bit
echo "📋 Step 2: انتظار برای پردازش..."
sleep 5

# Step 3: Check metrics
echo "📋 Step 3: بررسی Metrics..."
echo ""
echo "📊 Checking ingestor metrics:"
curl -s http://localhost:8000/metrics | grep hyperrag_ingestion_total | head -3

echo ""
echo "📊 Checking retriever metrics:"
curl -s http://localhost:8002/metrics | grep hyperrag_retrieval_total | head -3

echo ""
echo "✅ تست کامل شد!"
echo ""
echo "📝 مراحل بعدی:"
echo "  1. بررسی Alloy logs: curl http://192.168.2.23:12345/metrics"
echo "  2. Import dashboards in Grafana"
echo "  3. Verify service graph"

