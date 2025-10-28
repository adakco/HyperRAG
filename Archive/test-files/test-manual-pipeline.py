#!/usr/bin/env python3
"""
HyperRAG Manual Pipeline Test
============================
This test manually executes each step of the pipeline to ensure everything works.
"""

import asyncio
import json
import time
import requests
import uuid
from datetime import datetime
from typing import Dict, Any, List

class ManualPipelineTest:
    def __init__(self):
        self.base_urls = {
            "ingestor": "http://localhost:8000",
            "normalizer": "http://localhost:8001", 
            "chunker": "http://localhost:8003",
            "embedder": "http://localhost:8004",
            "retriever": "http://localhost:8002",
            "evaluator": "http://localhost:8005",
            "agent_orch": "http://localhost:8006"
        }
        self.test_results = {}
        self.doc_id = f"manual-pipeline-test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        self.version = int(time.time())
        
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def test_health_checks(self) -> bool:
        """Test all service health checks"""
        self.log("🏥 Testing service health checks...")
        
        healthy_services = 0
        total_services = len(self.base_urls)
        
        for service_name, base_url in self.base_urls.items():
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    self.log(f"✅ {service_name}: Healthy")
                    healthy_services += 1
                else:
                    self.log(f"❌ {service_name}: Unhealthy ({response.status_code})", "ERROR")
            except Exception as e:
                self.log(f"❌ {service_name}: Connection failed - {e}", "ERROR")
        
        self.log(f"📊 Health Summary: {healthy_services}/{total_services} services healthy")
        return healthy_services == total_services
    
    def test_document_ingestion(self) -> Dict[str, Any]:
        """Test document ingestion"""
        self.log("📥 Testing document ingestion...")
        
        # Create test document content
        test_content = f"""
HyperRAG Manual Pipeline Test Document

This document is designed to test the complete HyperRAG pipeline manually.
It contains comprehensive information about the system architecture and capabilities.

System Architecture:
- Microservices-based architecture
- 12 independent services working together
- Event-driven processing pipeline
- Real-time evaluation and monitoring

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

Test ID: {self.doc_id}
Timestamp: {datetime.now().isoformat()}
"""
        
        # Prepare test file
        test_file_content = test_content.strip()
        
        # Test ingestion
        try:
            files = {
                'file': ('test_document.txt', test_file_content, 'text/plain')
            }
            data = {
                'doc_id': self.doc_id,
                'tenant': 'test',
                'project': 'manual-pipeline-test',
                'lang': 'en'
            }
            
            response = requests.post(
                f"{self.base_urls['ingestor']}/ingest",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"✅ Document ingested successfully")
                self.log(f"📄 Doc ID: {result['doc_id']}")
                self.log(f"🔢 Version: {result['version']}")
                self.log(f"🔗 URI: {result.get('uri_raw', result.get('uri', 'N/A'))}")
                return result
            else:
                self.log(f"❌ Ingestion failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Ingestion error: {e}", "ERROR")
            return None
    
    def test_normalization(self, ingestion_result: Dict[str, Any]) -> Dict[str, Any]:
        """Test document normalization"""
        self.log("🧹 Testing document normalization...")
        
        if not ingestion_result:
            self.log("❌ Skipping normalization - no ingestion result", "ERROR")
            return None
            
        try:
            params = {
                'doc_id': ingestion_result['doc_id'],
                'version': str(ingestion_result['version']),
                'uri_raw': ingestion_result.get('uri_raw', ingestion_result.get('uri')),
                'lang': 'en',
                'tenant': 'test'
            }
            
            response = requests.post(
                f"{self.base_urls['normalizer']}/normalize",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"✅ Normalization successful!")
                self.log(f"📄 Clean URI: {result['uri_clean']}")
                self.log(f"📊 Token count: {result['token_count']}")
                return result
            else:
                self.log(f"❌ Normalization failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Normalization error: {e}", "ERROR")
            return None
    
    def test_chunking(self, normalization_result: Dict[str, Any]) -> Dict[str, Any]:
        """Test document chunking"""
        self.log("✂️ Testing document chunking...")
        
        if not normalization_result:
            self.log("❌ Skipping chunking - no normalization result", "ERROR")
            return None
            
        try:
            params = {
                'doc_id': normalization_result['doc_id'],
                'version': str(normalization_result['version']),
                'uri_clean': normalization_result['uri_clean'],
                'lang': 'en',
                'tenant': 'test'
            }
            
            response = requests.post(
                f"{self.base_urls['chunker']}/chunk",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"✅ Chunking successful!")
                self.log(f"📄 Total chunks: {result['total_chunks']}")
                self.log(f"📊 Total tokens: {result['total_tokens']}")
                return result
            else:
                self.log(f"❌ Chunking failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Chunking error: {e}", "ERROR")
            return None
    
    def test_embedding(self, chunking_result: Dict[str, Any]) -> Dict[str, Any]:
        """Test document embedding"""
        self.log("🧠 Testing document embedding...")
        
        if not chunking_result:
            self.log("❌ Skipping embedding - no chunking result", "ERROR")
            return None
            
        try:
            params = {
                'doc_id': chunking_result['doc_id'],
                'version': str(chunking_result['version']),
                'uri_processed': chunking_result.get('uri_processed', chunking_result.get('uri_clean', 's3://clean/test/clean/' + chunking_result['doc_id'] + '/' + str(chunking_result['version']))),
                'lang': 'en',
                'tenant': 'test'
            }
            
            response = requests.post(
                f"{self.base_urls['embedder']}/embed",
                params=params,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"✅ Embedding successful!")
                self.log(f"📄 Embedded chunks: {result.get('embedded_chunks', 'N/A')}")
                return result
            else:
                self.log(f"❌ Embedding failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Embedding error: {e}", "ERROR")
            return None
    
    def test_retrieval(self) -> Dict[str, Any]:
        """Test document retrieval"""
        self.log("🔍 Testing document retrieval...")
        
        test_queries = [
            "What is HyperRAG?",
            "What are the key features?",
            "How many microservices does it have?",
            "What languages are supported?"
        ]
        
        successful_queries = 0
        total_results = 0
        
        for i, query in enumerate(test_queries, 1):
            try:
                data = {
                    'query': query,
                    'lang': 'en',
                    'tenant': 'test',
                    'limit': 5
                }
                
                response = requests.post(
                    f"{self.base_urls['retriever']}/retrieve",
                    json=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    results_count = len(result.get('results', []))
                    total_results += results_count
                    
                    if results_count > 0:
                        self.log(f"✅ Query {i}: '{query}' - {results_count} results found")
                        successful_queries += 1
                    else:
                        self.log(f"⚠️ Query {i}: '{query}' - No results found")
                else:
                    self.log(f"❌ Query {i}: '{query}' - Failed ({response.status_code})", "ERROR")
                    
            except Exception as e:
                self.log(f"❌ Query {i}: '{query}' - Error: {e}", "ERROR")
        
        self.log(f"📊 Retrieval Summary: {successful_queries}/{len(test_queries)} queries successful, {total_results} total results")
        
        return {
            'successful_queries': successful_queries,
            'total_queries': len(test_queries),
            'total_results': total_results
        }
    
    def test_evaluation(self) -> Dict[str, Any]:
        """Test RAG evaluation"""
        self.log("📊 Testing RAG evaluation...")
        
        try:
            data = {
                'query': 'What is HyperRAG?',
                'answer': 'HyperRAG is a comprehensive Retrieval-Augmented Generation system.',
                'contexts': ['HyperRAG is a comprehensive RAG system with microservices architecture.'],
                'lang': 'en',
                'tenant': 'test'
            }
            
            response = requests.post(
                f"{self.base_urls['evaluator']}/evaluate",
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"✅ Evaluation completed")
                self.log(f"📊 Overall Score: {result.get('overall_score', 'N/A')}")
                self.log(f"🎯 Passed: {result.get('passed', 'N/A')}")
                return result
            else:
                self.log(f"❌ Evaluation failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Evaluation error: {e}", "ERROR")
            return None
    
    def test_agent_session(self) -> Dict[str, Any]:
        """Test agent session"""
        self.log("🤖 Testing agent session...")
        
        try:
            data = {
                'user_id': 'test-user',
                'lang': 'en',
                'tenant': 'test',
                'token_budget': 1000,
                'max_steps': 5
            }
            
            response = requests.post(
                f"{self.base_urls['agent_orch']}/session/start",
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"✅ Agent session started successfully")
                self.log(f"🆔 Session ID: {result.get('session_id', 'N/A')}")
                return result
            else:
                self.log(f"❌ Agent session failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Agent session error: {e}", "ERROR")
            return None
    
    def run_complete_test(self):
        """Run the complete manual pipeline test"""
        self.log("🎯 HYPERRAG MANUAL PIPELINE TEST")
        self.log("=" * 50)
        self.log(f"🕐 Start Time: {datetime.now()}")
        self.log("")
        
        # Test 1: Health Checks
        self.log("🏥 PHASE 1: SYSTEM HEALTH CHECK")
        self.log("-" * 40)
        health_ok = self.test_health_checks()
        self.log("")
        
        if not health_ok:
            self.log("❌ Health check failed - stopping test", "ERROR")
            return
        
        # Test 2: Document Ingestion
        self.log("📥 PHASE 2: DOCUMENT INGESTION")
        self.log("-" * 40)
        ingestion_result = self.test_document_ingestion()
        self.log("")
        
        if not ingestion_result:
            self.log("❌ Ingestion failed - stopping test", "ERROR")
            return
        
        # Test 3: Normalization
        self.log("🧹 PHASE 3: DOCUMENT NORMALIZATION")
        self.log("-" * 40)
        normalization_result = self.test_normalization(ingestion_result)
        self.log("")
        
        if not normalization_result:
            self.log("❌ Normalization failed - stopping test", "ERROR")
            return
        
        # Test 4: Chunking
        self.log("✂️ PHASE 4: DOCUMENT CHUNKING")
        self.log("-" * 40)
        chunking_result = self.test_chunking(normalization_result)
        self.log("")
        
        if not chunking_result:
            self.log("❌ Chunking failed - stopping test", "ERROR")
            return
        
        # Test 5: Embedding
        self.log("🧠 PHASE 5: DOCUMENT EMBEDDING")
        self.log("-" * 40)
        embedding_result = self.test_embedding(chunking_result)
        self.log("")
        
        if not embedding_result:
            self.log("❌ Embedding failed - stopping test", "ERROR")
            return
        
        # Test 6: Retrieval
        self.log("🔍 PHASE 6: DOCUMENT RETRIEVAL")
        self.log("-" * 40)
        retrieval_result = self.test_retrieval()
        self.log("")
        
        # Test 7: Evaluation
        self.log("📊 PHASE 7: RAG EVALUATION")
        self.log("-" * 40)
        evaluation_result = self.test_evaluation()
        self.log("")
        
        # Test 8: Agent Session
        self.log("🤖 PHASE 8: AGENT SESSION")
        self.log("-" * 40)
        agent_result = self.test_agent_session()
        self.log("")
        
        # Final Summary
        self.log("🎯 FINAL SUMMARY")
        self.log("=" * 50)
        
        successful_phases = 0
        total_phases = 8
        
        if health_ok:
            successful_phases += 1
        if ingestion_result:
            successful_phases += 1
        if normalization_result:
            successful_phases += 1
        if chunking_result:
            successful_phases += 1
        if embedding_result:
            successful_phases += 1
        if retrieval_result and retrieval_result['successful_queries'] > 0:
            successful_phases += 1
        if evaluation_result:
            successful_phases += 1
        if agent_result:
            successful_phases += 1
        
        success_rate = (successful_phases / total_phases) * 100
        
        self.log(f"📊 Overall Success Rate: {success_rate:.1f}%")
        self.log(f"✅ Successful Phases: {successful_phases}/{total_phases}")
        self.log("")
        
        self.log("📋 PHASE SUMMARY:")
        self.log(f"   {'✅' if health_ok else '❌'} 🏥 Health Check: {'passed' if health_ok else 'failed'}")
        self.log(f"   {'✅' if ingestion_result else '❌'} 📥 Document Ingestion: {'Success' if ingestion_result else 'Failed'}")
        self.log(f"   {'✅' if normalization_result else '❌'} 🧹 Normalization: {'Success' if normalization_result else 'Failed'}")
        self.log(f"   {'✅' if chunking_result else '❌'} ✂️ Chunking: {'Success' if chunking_result else 'Failed'}")
        self.log(f"   {'✅' if embedding_result else '❌'} 🧠 Embedding: {'Success' if embedding_result else 'Failed'}")
        self.log(f"   {'✅' if retrieval_result and retrieval_result['successful_queries'] > 0 else '❌'} 🔍 Retrieval: {'Success' if retrieval_result and retrieval_result['successful_queries'] > 0 else 'Failed'}")
        self.log(f"   {'✅' if evaluation_result else '❌'} 📊 Evaluation: {'Success' if evaluation_result else 'Failed'}")
        self.log(f"   {'✅' if agent_result else '❌'} 🤖 Agent Session: {'Success' if agent_result else 'Failed'}")
        self.log("")
        
        if success_rate >= 80:
            self.log("🟢 OVERALL ASSESSMENT: ✅ EXCELLENT")
        elif success_rate >= 60:
            self.log("🟡 OVERALL ASSESSMENT: ⚠️ GOOD")
        else:
            self.log("🔴 OVERALL ASSESSMENT: ❌ POOR")
        
        self.log(f"Success Rate: {success_rate:.1f}%")
        self.log("")
        self.log("=" * 50)
        self.log("🎯 HyperRAG Manual Pipeline Test Completed!")
        self.log("=" * 50)

def main():
    """Main function"""
    test = ManualPipelineTest()
    test.run_complete_test()

if __name__ == "__main__":
    main()
