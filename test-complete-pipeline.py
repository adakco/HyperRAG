#!/usr/bin/env python3
"""
🎯 HyperRAG Complete Pipeline Test
=================================

This script tests the complete HyperRAG pipeline by manually triggering
each step in sequence to verify the entire flow works.
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

class HyperRAGCompletePipelineTest:
    """Test the complete HyperRAG pipeline step by step"""
    
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

    async def run_complete_pipeline_test(self):
        """Run the complete pipeline test"""
        print("🎯 HYPERRAG COMPLETE PIPELINE TEST")
        print("=" * 50)
        print(f"🕐 Start Time: {self.test_results['start_time']}")
        print()
        
        try:
            # Step 1: Document Ingestion
            await self.step_1_ingestion()
            
            # Step 2: Manual Normalization
            await self.step_2_normalization()
            
            # Step 3: Manual Chunking
            await self.step_3_chunking()
            
            # Step 4: Manual Embedding
            await self.step_4_embedding()
            
            # Step 5: Check Qdrant
            await self.step_5_check_qdrant()
            
            # Step 6: Test Retrieval
            await self.step_6_retrieval()
            
        except Exception as e:
            logger.error("Complete pipeline test failed", error=str(e))
            self.test_results['summary']['status'] = 'failed'
            self.test_results['summary']['error'] = str(e)
        
        finally:
            self.test_results['end_time'] = datetime.utcnow()
            await self.generate_complete_summary()

    async def step_1_ingestion(self):
        """Step 1: Document ingestion"""
        print("📥 STEP 1: DOCUMENT INGESTION")
        print("-" * 30)
        
        # Create test document
        test_content = """
        HyperRAG Complete Pipeline Test Document
        
        This document is designed to test the complete HyperRAG pipeline.
        It contains information about the system architecture and capabilities.
        
        System Architecture:
        - Microservices-based architecture
        - 12 independent services
        - Event-driven processing
        - Real-time evaluation
        
        Key Features:
        - Multi-language support (English, Persian, Arabic)
        - Advanced document processing pipeline
        - Hybrid retrieval (dense + sparse search)
        - Real-time evaluation and monitoring
        - Cost tracking and optimization
        - Agent orchestration capabilities
        
        Performance Metrics:
        - Sub-second retrieval times
        - 95%+ accuracy on benchmark datasets
        - Support for documents up to 1M tokens
        - Real-time processing capabilities
        
        This document should be processed through the complete pipeline:
        ingestion → normalization → chunking → embedding → storage → retrieval
        """
        
        doc_id = f"complete-pipeline-test-{int(time.time())}"
        
        # Create temporary file
        temp_file = Path("temp_complete_pipeline_test.txt")
        temp_file.write_text(test_content)
        
        try:
            start_time = time.time()
            with open(temp_file, 'rb') as f:
                files = {'file': f}
                data = {
                    'doc_id': doc_id,
                    'tenant': 'test',
                    'project': 'complete-pipeline-test',
                    'lang': 'en',
                    'title': 'Complete Pipeline Test Document'
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

    async def step_2_normalization(self):
        """Step 2: Manual normalization"""
        print("🧹 STEP 2: MANUAL NORMALIZATION")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping normalization - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        uri_raw = ingestion_result['uri_raw']
        
        try:
            # Test normalizer with query parameters
            params = {
                'doc_id': doc_id,
                'version': str(version),
                'uri_raw': uri_raw,
                'lang': 'en',
                'tenant': 'test'
            }
            
            print(f"🧪 Testing normalizer for doc: {doc_id}")
            print(f"📄 URI: {uri_raw}")
            
            response = requests.post(
                f"{self.base_urls['normalizer']}/normalize",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Normalization successful!")
                print(f"📊 Result: {result}")
                self.test_results['steps']['normalization'] = {
                    'status': 'success',
                    'result': result
                }
            else:
                print(f"❌ Normalization failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['normalization'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Normalization error: {str(e)}")
            self.test_results['steps']['normalization'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_3_chunking(self):
        """Step 3: Manual chunking"""
        print("✂️ STEP 3: MANUAL CHUNKING")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping chunking - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        
        try:
            # Test chunker with query parameters
            params = {
                'doc_id': doc_id,
                'version': str(version),
                'uri_clean': f's3://clean/test/clean/{doc_id}/{version}',
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
                print("✅ Chunking successful!")
                print(f"📊 Result: {result}")
                self.test_results['steps']['chunking'] = {
                    'status': 'success',
                    'result': result
                }
            else:
                print(f"❌ Chunking failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['chunking'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Chunking error: {str(e)}")
            self.test_results['steps']['chunking'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_4_embedding(self):
        """Step 4: Manual embedding"""
        print("🧠 STEP 4: MANUAL EMBEDDING")
        print("-" * 30)
        
        ingestion_result = self.test_results['steps'].get('ingestion', {})
        if ingestion_result.get('status') != 'success':
            print("⚠️ Skipping embedding - ingestion failed")
            return
        
        doc_id = ingestion_result['doc_id']
        version = ingestion_result['version']
        
        try:
            # Test embedder with query parameters
            params = {
                'doc_id': doc_id,
                'version': str(version),
                'uri_processed': f's3://clean/test/chunked/{doc_id}/{version}',
                'lang': 'en',
                'tenant': 'test',
                'project': 'complete-pipeline-test'
            }
            
            print(f"🧪 Testing embedder for doc: {doc_id}")
            
            response = requests.post(
                f"{self.base_urls['embedder']}/embed",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Embedding successful!")
                print(f"📊 Result: {result}")
                self.test_results['steps']['embedding'] = {
                    'status': 'success',
                    'result': result
                }
            else:
                print(f"❌ Embedding failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['embedding'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Embedding error: {str(e)}")
            self.test_results['steps']['embedding'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def step_5_check_qdrant(self):
        """Step 5: Check Qdrant collections"""
        print("🗃️ STEP 5: CHECK QDRANT")
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

    async def step_6_retrieval(self):
        """Step 6: Test retrieval"""
        print("🔍 STEP 6: TEST RETRIEVAL")
        print("-" * 30)
        
        try:
            # Test retriever with a simple query
            data = {
                'query': 'HyperRAG complete pipeline test',
                'tenant': 'test',
                'project': 'complete-pipeline-test',
                'lang': 'en',
                'limit': 5
            }
            
            print("🧪 Testing retriever with query: 'HyperRAG complete pipeline test'")
            response = requests.post(
                f"{self.base_urls['retriever']}/retrieve",
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                results_count = len(result.get('results', []))
                print(f"✅ Retrieval test successful!")
                print(f"📊 Found {results_count} results")
                
                if results_count > 0:
                    print("🎯 Retrieval is working!")
                    first_result = result['results'][0]
                    content_preview = first_result['content'][:100] + "..." if len(first_result['content']) > 100 else first_result['content']
                    print(f"📄 First result preview: {content_preview}")
                else:
                    print("⚠️ No results found - pipeline may not have completed")
                
                self.test_results['steps']['retrieval'] = {
                    'status': 'success',
                    'results_count': results_count,
                    'result': result
                }
            else:
                print(f"❌ Retrieval test failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['steps']['retrieval'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Retrieval error: {str(e)}")
            self.test_results['steps']['retrieval'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def generate_complete_summary(self):
        """Generate complete summary"""
        print("📋 COMPLETE PIPELINE SUMMARY")
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
            'normalization': '🧹 Normalization',
            'chunking': '✂️ Chunking',
            'embedding': '🧠 Embedding',
            'qdrant': '🗃️ Qdrant',
            'retrieval': '🔍 Retrieval'
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
        elif steps.get('normalization', {}).get('status') == 'failed':
            print("❌ Issue: Normalization failed - check MinIO access")
        elif steps.get('chunking', {}).get('status') == 'failed':
            print("❌ Issue: Chunking failed - check normalizer output")
        elif steps.get('embedding', {}).get('status') == 'failed':
            print("❌ Issue: Embedding failed - check chunker output")
        elif steps.get('qdrant', {}).get('status') == 'success':
            qdrant_info = steps['qdrant']
            if 'collections' in qdrant_info:
                collections = qdrant_info['collections']
                documents_collection = next((c for c in collections if c['name'] == 'documents'), None)
                if documents_collection:
                    print("✅ Qdrant is working and has documents collection")
                else:
                    print("❌ Issue: No documents collection in Qdrant")
        elif steps.get('retrieval', {}).get('status') == 'success':
            retriever_info = steps['retrieval']
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
        print("🎯 Complete Pipeline Test Completed!")
        print("=" * 50)

async def main():
    """Main test execution"""
    test = HyperRAGCompletePipelineTest()
    await test.run_complete_pipeline_test()

if __name__ == "__main__":
    asyncio.run(main())
