#!/bin/bash

echo "🔍 Testing Updated Infrastructure Connectivity..."
echo "================================================"

# Test PostgreSQL (new port)
echo "Testing PostgreSQL (port 5442)..."
if nc -z 192.168.2.23 5442 2>/dev/null; then
    echo "✅ PostgreSQL port 5442 is open"
else
    echo "❌ PostgreSQL port 5442 is not accessible"
fi

# Test Redis (new port)
echo "Testing Redis (port 6479)..."
if nc -z 192.168.2.23 6479 2>/dev/null; then
    echo "✅ Redis port 6479 is open"
else
    echo "❌ Redis port 6479 is not accessible"
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
echo "💡 اگر همه پورت‌ها باز هستند، می‌توانید سرویس‌ها را اجرا کنید:"
echo "   ./start-services-host.sh"
