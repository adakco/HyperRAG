#!/usr/bin/env python3
"""
HyperRAG System Test Script
Comprehensive testing of all services and functionality
"""

import asyncio
import json
import time
import requests
from typing import Dict, List, Optional
import uuid

class HyperRAGTester:
    """Comprehensive system tester"""
    
    def __init__(self):
        self.base_urls = {
            "ingestor": "http://localhost:8000",
            "normalizer": "http://localhost:8001",
            "retriever": "http://localhost:8002",
            "chunker": "http://localhost:8003",
            "embedder": "http://localhost:8004",
            "evaluator": "http://localhost:8005",
            "agent_orch": "http://localhost:8006",
            "policy": "http://localhost:8007",
            "costing": "http://localhost:8008",
            "pack_longrag": "http://localhost:8009",
            "memory_memorag": "http://localhost:8010",
            "reranker": "http://localhost:8011"
        }
        self.test_results = {}
    
    def test_service_health(self) -> bool:
        """Test all service health endpoints"""
        print("🔍 Testing service health...")
        
        all_healthy = True
        for service, url in self.base_urls.items():
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    print(f"  ✅ {service}: Healthy")
                    self.test_results[f"{service}_health"] = True
                else:
                    print(f"  ❌ {service}: Unhealthy (status: {response.status_code})")
                    self.test_results[f"{service}_health"] = False
                    all_healthy = False
            except Exception as e:
                print(f"  ❌ {service}: Error - {e}")
                self.test_results[f"{service}_health"] = False
                all_healthy = False
        
        return all_healthy
    
    def test_document_ingestion(self) -> bool:
        """Test document ingestion"""
        print("📥 Testing document ingestion...")
        
        # Test English document
        test_doc_en = "This is a test document about artificial intelligence and machine learning. It contains information about neural networks, deep learning, and natural language processing."
        
        try:
            # Create test file
            with open("test_doc_en.txt", "w") as f:
                f.write(test_doc_en)
            
            # Ingest document
            with open("test_doc_en.txt", "rb") as f:
                files = {"file": f}
                data = {
                    "doc_id": "test-doc-en-1",
                    "tenant": "test",
                    "project": "alpha",
                    "lang": "en",
                    "title": "Test English Document"
                }
                
                response = requests.post(
                    f"{self.base_urls['ingestor']}/ingest",
                    files=files,
                    data=data,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"  ✅ English document ingested: {result['doc_id']} v{result['version']}")
                self.test_results["ingestion_en"] = True
                return True
            else:
                print(f"  ❌ English document ingestion failed: {response.status_code}")
                self.test_results["ingestion_en"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ English document ingestion error: {e}")
            self.test_results["ingestion_en"] = False
            return False
    
    def test_document_retrieval(self) -> bool:
        """Test document retrieval"""
        print("🔍 Testing document retrieval...")
        
        try:
            # Test English retrieval
            retrieval_request = {
                "query": "What is artificial intelligence?",
                "lang": "en",
                "tenant": "test",
                "k_final": 3,
                "rerank": True
            }
            
            response = requests.post(
                f"{self.base_urls['retriever']}/retrieve",
                json=retrieval_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"  ✅ English retrieval: {len(result['results'])} results")
                self.test_results["retrieval_en"] = True
                return True
            else:
                print(f"  ❌ English retrieval failed: {response.status_code}")
                self.test_results["retrieval_en"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ English retrieval error: {e}")
            self.test_results["retrieval_en"] = False
            return False
    
    def test_evaluation(self) -> bool:
        """Test evaluation system"""
        print("📊 Testing evaluation system...")
        
        try:
            evaluation_request = {
                "lang": "en",
                "tenant": "test",
                "query": "What is artificial intelligence?",
                "answer": "Artificial intelligence is a branch of computer science that aims to create intelligent machines that work and react like humans.",
                "contexts": [
                    "This is a test document about artificial intelligence and machine learning.",
                    "It contains information about neural networks, deep learning, and natural language processing."
                ],
                "metrics": ["faithfulness", "answer_relevancy"]
            }
            
            response = requests.post(
                f"{self.base_urls['evaluator']}/evaluate",
                json=evaluation_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"  ✅ Evaluation completed: Overall score {result['overall_score']:.3f}")
                self.test_results["evaluation"] = True
                return True
            else:
                print(f"  ❌ Evaluation failed: {response.status_code}")
                self.test_results["evaluation"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ Evaluation error: {e}")
            self.test_results["evaluation"] = False
            return False
    
    def test_agent_session(self) -> bool:
        """Test agent orchestration"""
        print("🤖 Testing agent orchestration...")
        
        try:
            # Start agent session
            session_data = {
                "query": "What is artificial intelligence?",
                "lang": "en",
                "tenant": "test",
                "token_budget": 2000,
                "max_steps": 3
            }
            
            response = requests.post(
                f"{self.base_urls['agent_orch']}/sessions",
                params=session_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                session_id = result["session_id"]
                print(f"  ✅ Agent session started: {session_id}")
                
                # Wait for completion
                print("  ⏳ Waiting for agent completion...")
                time.sleep(10)
                
                # Check session status
                status_response = requests.get(
                    f"{self.base_urls['agent_orch']}/sessions/{session_id}",
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_result = status_response.json()
                    print(f"  ✅ Agent session status: {status_result['status']}")
                    self.test_results["agent_session"] = True
                    return True
                else:
                    print(f"  ❌ Agent session status check failed: {status_response.status_code}")
                    self.test_results["agent_session"] = False
                    return False
            else:
                print(f"  ❌ Agent session start failed: {response.status_code}")
                self.test_results["agent_session"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ Agent session error: {e}")
            self.test_results["agent_session"] = False
            return False
    
    def test_persian_support(self) -> bool:
        """Test Persian language support"""
        print("🇮🇷 Testing Persian language support...")
        
        # Test Persian document
        test_doc_fa = "این یک سند تست درباره هوش مصنوعی و یادگیری ماشین است. این سند شامل اطلاعاتی درباره شبکه‌های عصبی، یادگیری عمیق و پردازش زبان طبیعی می‌باشد."
        
        try:
            # Create test file
            with open("test_doc_fa.txt", "w", encoding="utf-8") as f:
                f.write(test_doc_fa)
            
            # Ingest Persian document
            with open("test_doc_fa.txt", "rb") as f:
                files = {"file": f}
                data = {
                    "doc_id": "test-doc-fa-1",
                    "tenant": "test",
                    "project": "alpha",
                    "lang": "fa",
                    "title": "سند تست فارسی"
                }
                
                response = requests.post(
                    f"{self.base_urls['ingestor']}/ingest",
                    files=files,
                    data=data,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"  ✅ Persian document ingested: {result['doc_id']} v{result['version']}")
                
                # Test Persian retrieval
                retrieval_request = {
                    "query": "هوش مصنوعی چیست؟",
                    "lang": "fa",
                    "tenant": "test",
                    "k_final": 3,
                    "rerank": True
                }
                
                retrieval_response = requests.post(
                    f"{self.base_urls['retriever']}/retrieve",
                    json=retrieval_request,
                    timeout=30
                )
                
                if retrieval_response.status_code == 200:
                    retrieval_result = retrieval_response.json()
                    print(f"  ✅ Persian retrieval: {len(retrieval_result['results'])} results")
                    self.test_results["persian_support"] = True
                    return True
                else:
                    print(f"  ❌ Persian retrieval failed: {retrieval_response.status_code}")
                    self.test_results["persian_support"] = False
                    return False
            else:
                print(f"  ❌ Persian document ingestion failed: {response.status_code}")
                self.test_results["persian_support"] = False
                return False
                
        except Exception as e:
            print(f"  ❌ Persian support error: {e}")
            self.test_results["persian_support"] = False
            return False
    
    def run_all_tests(self) -> Dict:
        """Run all tests"""
        print("🚀 Starting HyperRAG System Tests...")
        print("=" * 50)
        
        # Test service health
        if not self.test_service_health():
            print("❌ Service health check failed. Please ensure all services are running.")
            return self.test_results
        
        print()
        
        # Test document ingestion
        self.test_document_ingestion()
        print()
        
        # Wait for processing
        print("⏳ Waiting for document processing...")
        time.sleep(5)
        
        # Test document retrieval
        self.test_document_retrieval()
        print()
        
        # Test evaluation
        self.test_evaluation()
        print()
        
        # Test agent session
        self.test_agent_session()
        print()
        
        # Test Persian support
        self.test_persian_support()
        print()
        
        # Print summary
        self.print_test_summary()
        
        return self.test_results
    
    def print_test_summary(self):
        """Print test results summary"""
        print("=" * 50)
        print("📊 Test Results Summary:")
        print("=" * 50)
        
        passed = 0
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
            if result:
                passed += 1
        
        print("=" * 50)
        print(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! HyperRAG system is working correctly.")
        else:
            print("⚠️  Some tests failed. Please check the logs and fix the issues.")
        
        print("=" * 50)

def main():
    """Main test function"""
    tester = HyperRAGTester()
    results = tester.run_all_tests()
    
    # Clean up test files
    import os
    for filename in ["test_doc_en.txt", "test_doc_fa.txt"]:
        if os.path.exists(filename):
            os.remove(filename)
    
    return results

if __name__ == "__main__":
    main()
