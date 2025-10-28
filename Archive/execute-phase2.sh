#!/bin/bash
# Execute Phase 2: Deployment & Testing
# این اسکریپت مراحل فاز 2 را به ترتیب اجرا می‌کند

set -e

echo "🚀 شروع فاز 2: Deployment & Testing"
echo "===================================="
echo ""

# Step 1: Restart services
echo "📋 Step 1: Restarting services..."
./stop-services-host.sh
sleep 3
./start-services-host.sh

echo "✅ Services restarted"
echo ""

# Step 2: Wait for services to be ready
echo "📋 Step 2: Waiting for services..."
sleep 10

# Step 3: Check service health
echo "📋 Step 3: Checking service health..."
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011; do
  if curl -s http://localhost:$port/health > /dev/null; then
    echo "✅ Port $port OK"
  else
    echo "❌ Port $port FAILED"
  fi
done

echo ""
echo "📋 Step 4: Testing telemetry..."
echo ""

# Step 4: Run test
echo "🧪 Running test pipeline..."
python3 test-complete-pipeline.py

echo ""
echo "✅ فاز 2 کامل شد!"
echo ""
echo "📝 مراحل بعدی:"
echo "  1. Deploy Alloy on server (manually)"
echo "  2. Import dashboards in Grafana"
echo "  3. Verify service graph"
echo ""
echo "📄 راهنمای کامل در: docs/Phase-2-Manual-Deployment.md"

