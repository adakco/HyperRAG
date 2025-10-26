#!/usr/bin/env python3
"""
🔍 HyperRAG Pipeline Debug Test
===============================

This script tests the complete HyperRAG pipeline step by step
to identify where the issue is occurring.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import requests
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

class HyperRAGPipelineDebugger:
    """Debug the HyperRAG pipeline step by step"""
    
    def __init__(self):
        self.base_urls = {
            'ingestor': 'http://localhost:8000',
            'normalizer': 'http://localhost:8001',
            'retriever': 'http://localhost:8002',
            'chunker': 'http://localhost:8003',
            'embedder': 'http://localhost:8004',
            'evaluator': 'http://localhost:8005',
            'agent_orch': 'http://localhost:8006',
            'policy': 'http://localhost:8007',
            'costing': 'http://localhost:8008',
            'pack_longrag': 'http://localhost:8009',
            'memory_memorag': 'http://localhost:8010',
            'reranker': 'http://localhost:8011'
        }
        
        self.test_results = {
            'start_time': datetime.utcnow(),
            'steps': {},
            'summary': {}
        }

    async def debug_pipeline(self):
        """Debug the complete pipeline"""
        print("🔍 HYPERRAG PIPELINE DEBUG")
        print("=" * 50)
        print(f"🕐 Start Time: {self.test_results['start_time']}")
        print()
        
        try:
            # Step 1: Document Ingestion
            await self.step_1_ingestion()
            
            # Step 2: Check MinIO Storage
            await self.step_2_check_minio()
            
            # Step 3: Test Normalizer
            await self.step_3_normalizer()
            
            # Step 4: Test Chunker
            await self.step_4_chunker()
            
            # Step 5: Test Embedder
            await self.step_5_embedder()
            
            # Step 6: Check Qdrant
            await self.step_6_check_qdrant()
            
            # Step 7: Test Retriever
            await self.step_7_retriever()
            
        except Exception as e:
            logger.error("Pipeline debug failed", error=str(e))
            self.test_results['summary']['status'] = 'failed'
            self.test_results['summary']['error'] = str(e)
        
        finally:
            self.test_results['end_time'] = datetime.utcnow()
            await self.generate_debug_summary()

    async def step_1_ingestion(self):
        """Step 1: Test document ingestion"""
        print("📥 STEP 1: DOCUMENT INGESTION")
        print("-" * 30)
        
        # Create test document
        test_content = """
        HyperRAG Pipeline Test Document
        
        This is a test document to verify the complete HyperRAG pipeline.
        It contains information about the system architecture and capabilities.
        
        Key Features:
        - Document processing pipeline
        - Multi-language support
        - Vector search capabilities
        - Real-time evaluation
        """
        
        doc_id = f"pipeline-test-{int(time.time())}"
        
        # Create temporary file
        temp_file = Path("temp_pipeline_test.txt")
        temp_file.write_text(test_content)
        
        try:
            start_time = time.time()
            with open(temp_file, 'rb') as f:
                files = {'file': f}
                data = {
                    'doc_id': doc_id,
                    'tenant': 'test',
                    'project': 'pipeline-test',
                    'lang': 'en',
                    'title': 'Pipeline Test Document'
                }
                response = requests.post(
                    f"{self.base_urls['ingestor']}/ingest",
                    files=files,
                    data=data,
                    timeout=30
                )
            end_time = time.time()
            
            # Clean up
            temp_file.unlink()
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Document ingested successfully")
                print(f"📄 Doc ID: {doc_id}")
                print(f"🔢 Version: {result.get('version')}")
                print(f"⏱️ Time: {end_time - start_time:.3f}s")
                print(f"🔗 URI: {result.get('uri_raw')}")
                
                self.test_results['steps']['ingestion'] = {
                    'status': 'success',
                    'doc_id': doc_id,
                    'version': result.get('version'),
                    'uri_raw': result.get('uri_raw'),
                    'response_time': end_time - start_time
                }
            else:
                print(f"❌ Ingestion failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['ingestion'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Ingestion error: {str(e)}")
            self.test_results['steps']['ingestion'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_2_check_minio(self):
        """Step 2: Check MinIO storage"""
        print("🗄️ STEP 2: CHECK MINIO STORAGE")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping MinIO check - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        uri_raw = ingestion_result['uri_raw']
        
        print(f"📄 Checking document: {doc_id}")
        print(f"🔢 Version: {version}")
        print(f"🔗 URI: {uri_raw}")
        
        # Note: We can't directly check MinIO from here, but we can verify the URI format
        if uri_raw.startswith('s3://'):
            print("✅ URI format is correct (S3/MinIO)")
            self.test_results['steps']['minio'] = {
                'status': 'verified',
                'uri_format': 'correct'
            }
        else:
            print("❌ URI format is incorrect")
            self.test_results['steps']['minio'] = {
                'status': 'error',
                'uri_format': 'incorrect'
            }
        
        print()

    async def step_3_normalizer(self):
        """Step 3: Test normalizer"""
        print("🧹 STEP 3: TEST NORMALIZER")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping normalizer test - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        
        try:
            # Test normalizer with query parameters
            params = {
                'doc_id': doc_id,
                'version': str(version),  # Convert to string
                'uri_raw': f's3://raw/test/pipeline-test/{doc_id}/{version}',
                'lang': 'en',
                'tenant': 'test'
            }
            
            print(f"🧪 Testing normalizer for doc: {doc_id}")
            response = requests.post(
                f"{self.base_urls['normalizer']}/normalize",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Normalizer test successful!")
                print(f"📊 Result: {result}")
                self.test_results['steps']['normalizer'] = {
                    'status': 'success',
                    'result': result
                }
            else:
                print(f"❌ Normalizer test failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['normalizer'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Normalizer error: {str(e)}")
            self.test_results['steps']['normalizer'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_4_chunker(self):
        """Step 4: Test chunker"""
        print("✂️ STEP 4: TEST CHUNKER")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping chunker test - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        
        try:
            # Test chunker with query parameters
            params = {
                'doc_id': doc_id,
                'version': str(version),  # Convert to string
                'uri_clean': f's3://clean/test/pipeline-test/{doc_id}/{version}',
                'lang': 'en',
                'tenant': 'test'
            }
            
            print(f"🧪 Testing chunker for doc: {doc_id}")
            response = requests.post(
                f"{self.base_urls['chunker']}/chunk",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Chunker test successful!")
                print(f"📊 Result: {result}")
                self.test_results['steps']['chunker'] = {
                    'status': 'success',
                    'result': result
                }
            else:
                print(f"❌ Chunker test failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['chunker'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Chunker error: {str(e)}")
            self.test_results['steps']['chunker'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_5_embedder(self):
        """Step 5: Test embedder"""
        print("🧠 STEP 5: TEST EMBEDDER")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping embedder test - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        
        try:
            # Test embedder with query parameters
            params = {
                'doc_id': doc_id,
                'version': str(version),  # Convert to string
                'uri_processed': f's3://processed/test/pipeline-test/{doc_id}/{version}',
                'lang': 'en',
                'tenant': 'test'
            }
            
            print(f"🧪 Testing embedder for doc: {doc_id}")
            response = requests.post(
                f"{self.base_urls['embedder']}/embed",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Embedder test successful!")
                print(f"📊 Result: {result}")
                self.test_results['steps']['embedder'] = {
                    'status': 'success',
                    'result': result
                }
            else:
                print(f"❌ Embedder test failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['embedder'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Embedder error: {str(e)}")
            self.test_results['steps']['embedder'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_6_check_qdrant(self):
        """Step 6: Check Qdrant collections"""
        print("🗃️ STEP 6: CHECK QDRANT")
        print("-" * 30)
        
        try:
            # Check Qdrant collections
            response = requests.get('http://192.168.2.23:6333/collections', timeout=10)
            if response.status_code == 200:
                collections = response.json()
                print("✅ Qdrant is accessible")
                
                if 'result' in collections and 'collections' in collections['result']:
                    collection_list = collections['result']['collections']
                    print(f"📚 Found {len(collection_list)} collections:")
                    
                    for col in collection_list:
                        col_name = col['name']
                        print(f"   - {col_name}")
                        
                        # Check collection details
                        col_response = requests.get(f'http://192.168.2.23:6333/collections/{col_name}', timeout=10)
                        if col_response.status_code == 200:
                            col_info = col_response.json()
                            if 'result' in col_info:
                                points_count = col_info['result'].get('points_count', 0)
                                vectors_count = col_info['result'].get('indexed_vectors_count', 0)
                                print(f"     Points: {points_count}, Vectors: {vectors_count}")
                                
                                if col_name == 'documents' and points_count > 0:
                                    print(f"     🎯 Found {points_count} points in documents collection!")
                
                self.test_results['steps']['qdrant'] = {
                    'status': 'success',
                    'collections': collection_list
                }
            else:
                print(f"❌ Qdrant check failed: {response.status_code}")
                self.test_results['steps']['qdrant'] = {
                    'status': 'failed',
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            print(f"❌ Qdrant error: {str(e)}")
            self.test_results['steps']['qdrant'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_7_retriever(self):
        """Step 7: Test retriever"""
        print("🔍 STEP 7: TEST RETRIEVER")
        print("-" * 30)
        
        try:
            # Test retriever with a simple query
            data = {
                'query': 'HyperRAG pipeline test',
                'tenant': 'test',
                'project': 'pipeline-test',
                'lang': 'en',
                'limit': 5
            }
            
            print("🧪 Testing retriever with query: 'HyperRAG pipeline test'")
            response = requests.post(
                f"{self.base_urls['retriever']}/retrieve",
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                results_count = len(result.get('results', []))
                print(f"✅ Retriever test successful!")
                print(f"📊 Found {results_count} results")
                
                if results_count > 0:
                    print("🎯 Retrieval is working!")
                    first_result = result['results'][0]
                    content_preview = first_result['content'][:100] + "..." if len(first_result['content']) > 100 else first_result['content']
                    print(f"📄 First result preview: {content_preview}")
                else:
                    print("⚠️ No results found - this is expected if pipeline didn't complete")
                
                self.test_results['steps']['retriever'] = {
                    'status': 'success',
                    'results_count': results_count,
                    'result': result
                }
            else:
                print(f"❌ Retriever test failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['retriever'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Retriever error: {str(e)}")
            self.test_results['steps']['retriever'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def generate_debug_summary(self):
        """Generate debug summary"""
        print("📋 DEBUG SUMMARY")
        print("=" * 50)
        
        steps = self.test_results['steps']
        
        # Count successful steps
        successful_steps = sum(1 for step in steps.values() if step.get('status') == 'success')
        total_steps = len(steps)
        
        print(f"📊 Pipeline Steps: {successful_steps}/{total_steps} successful")
        print()
        
        # Step-by-step summary
        step_names = {
            'ingestion': '📥 Document Ingestion',
            'minio': '🗄️ MinIO Storage',
            'normalizer': '🧹 Normalizer',
            'chunker': '✂️ Chunker',
            'embedder': '🧠 Embedder',
            'qdrant': '🗃️ Qdrant',
            'retriever': '🔍 Retriever'
        }
        
        print("📋 STEP SUMMARY:")
        for step_key, step_name in step_names.items():
            step = steps.get(step_key, {})
            status = step.get('status', 'not_tested')
            if status == 'success':
                print(f"   ✅ {step_name}: Success")
            elif status == 'failed':
                print(f"   ❌ {step_name}: Failed")
            elif status == 'error':
                print(f"   ❌ {step_name}: Error")
            else:
                print(f"   ⚠️ {step_name}: {status}")
        
        print()
        
        # Identify the issue
        print("🔍 ISSUE IDENTIFICATION:")
        
        if steps.get('ingestion', {}).get('status') != 'success':
            print("❌ Issue: Document ingestion failed")
        elif steps.get('normalizer', {}).get('status') == 'failed':
            print("❌ Issue: Normalizer failed - check MinIO access")
        elif steps.get('chunker', {}).get('status') == 'failed':
            print("❌ Issue: Chunker failed - check normalizer output")
        elif steps.get('embedder', {}).get('status') == 'failed':
            print("❌ Issue: Embedder failed - check chunker output")
        elif steps.get('qdrant', {}).get('status') == 'success':
            qdrant_info = steps['qdrant']
            if 'collections' in qdrant_info:
                collections = qdrant_info['collections']
                documents_collection = next((c for c in collections if c['name'] == 'documents'), None)
                if documents_collection:
                    print("✅ Qdrant is working and has documents collection")
                else:
                    print("❌ Issue: No documents collection in Qdrant")
        elif steps.get('retriever', {}).get('status') == 'success':
            retriever_info = steps['retriever']
            if retriever_info.get('results_count', 0) == 0:
                print("❌ Issue: Retriever works but returns no results")
                print("   This suggests the pipeline didn't complete or Qdrant is empty")
            else:
                print("✅ Retriever is working and returning results")
        
        print()
        
        # Recommendations
        print("💡 RECOMMENDATIONS:")
        print("1. Check if all services are listening to NATS events")
        print("2. Verify MinIO bucket access and permissions")
        print("3. Check if the processing pipeline is triggered by events")
        print("4. Monitor service logs for errors")
        print("5. Test each service individually")
        
        print()
        print("=" * 50)
        print("🎯 Pipeline Debug Completed!")
        print("=" * 50)

async def main():
    """Main debug execution"""
    debugger = HyperRAGPipelineDebugger()
    await debugger.debug_pipeline()

if __name__ == "__main__":
    asyncio.run(main())
