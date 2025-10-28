#!/usr/bin/env python3
"""
Direct test of ingestor service to see full traceback
"""
import asyncio
import sys
sys.path.insert(0, 'platform/services/ingestor')

from main import IngestorService, Settings, DocumentIngestionRequest

async def test():
    settings = Settings()
    service = IngestorService(settings)
    
    # Initialize service
    await service.initialize()
    
    # Create test request
    request = DocumentIngestionRequest(
        doc_id="test-direct",
        tenant="test",
        project="test",
        lang="en",
        title="Direct Test",
        author=None,
        tags=[],
        acl=[]
    )
    
    # Read test file
    with open('README.md', 'rb') as f:
        file_content = f.read()
    
    try:
        print("🔍 Testing ingestion directly...")
        response = await service.ingest_document(request, file_content, "text/markdown")
        print(f"✅ Success: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.shutdown()

if __name__ == "__main__":
    asyncio.run(test())

