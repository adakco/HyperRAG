#!/bin/bash
# Deploy Alloy on Server
# This script deploys Alloy to the server for telemetry collection

set -e

echo "🚀 شروع Deploy Alloy..."

# Server information
SERVER="192.168.2.23"
SERVER_USER="root"
SERVER_PATH="/app/rag-ai/rag-graph-langfuse-nats/compose"

# Files to copy
ALLOY_CONFIG="platform/infra/compose/alloy-config.alloy"
DOCKER_COMPOSE="platform/infra/compose/docker-compose.with-alloy.yml"

echo ""
echo "📋 مراحل Deploy:"
echo "  1. Copy config files to server"
echo "  2. Add Alloy service to docker-compose.yml"
echo "  3. Start Alloy container"
echo "  4. Verify Alloy is working"
echo ""

# Copy files to server
echo "📤 کپی فایل‌ها به سرور..."
scp "$ALLOY_CONFIG" ${SERVER_USER}@${SERVER}:${SERVER_PATH}/alloy-config.alloy
scp "$DOCKER_COMPOSE" ${SERVER_USER}@${SERVER}:${SERVER_PATH}/docker-compose.with-alloy.yml

echo "✅ فایل‌ها کپی شدند"
echo ""
echo "⚠️  توجه: باید Alloy service را به docker-compose.yml اضافه کنید"
echo ""
echo "برای ادامه، به سرور SSH کنید:"
echo "  ssh ${SERVER_USER}@${SERVER}"
echo ""
echo "سپس اجرا کنید:"
echo "  cd ${SERVER_PATH}"
echo "  docker-compose -f docker-compose.with-alloy.yml up -d alloy"
echo ""
echo "یا Alloy service را به docker-compose.yml موجود اضافه کنید"
echo ""
echo "✅ آماده برای deployment در سرور!"

