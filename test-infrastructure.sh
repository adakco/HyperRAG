#!/bin/bash

echo "🔍 Testing Infrastructure Connectivity..."
echo "========================================"

# Test PostgreSQL
echo "Testing PostgreSQL..."
if nc -z 192.168.2.23 5432 2>/dev/null; then
    echo "✅ PostgreSQL port 5432 is open"
else
    echo "❌ PostgreSQL port 5432 is not accessible"
fi

# Test Redis
echo "Testing Redis..."
if nc -z 192.168.2.23 6379 2>/dev/null; then
    echo "✅ Redis port 6379 is open"
else
    echo "❌ Redis port 6379 is not accessible"
fi

# Test NATS
echo "Testing NATS..."
if nc -z 192.168.2.23 4222 2>/dev/null; then
    echo "✅ NATS port 4222 is open"
else
    echo "❌ NATS port 4222 is not accessible"
fi

# Test Qdrant
echo "Testing Qdrant..."
if nc -z 192.168.2.23 6333 2>/dev/null; then
    echo "✅ Qdrant port 6333 is open"
else
    echo "❌ Qdrant port 6333 is not accessible"
fi

# Test MinIO
echo "Testing MinIO..."
if nc -z 192.168.2.23 9090 2>/dev/null; then
    echo "✅ MinIO port 9090 is open"
else
    echo "❌ MinIO port 9090 is not accessible"
fi

echo ""
echo "💡 اگر همه پورت‌ها بسته هستند، مطمئن شوید که:"
echo "   1. Docker containers روی سرور 192.168.2.23 در حال اجرا هستند"
echo "   2. فایروال اجازه اتصال می‌دهد"
echo "   3. آدرس IP سرور درست است"
