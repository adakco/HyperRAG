#!/usr/bin/env python3
"""
Detailed HyperRAG Test with Comprehensive Logging
This script tests all HyperRAG functionality with detailed logging to identify issues
"""

import requests
import json
import time
import logging
from typing import Dict, Any

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hyperrag_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HyperRAGTester:
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
            "reranker": "http://localhost:8011",
        }
        self.results = {}

    def log_step(self, step: str, message: str, level: str = "info"):
        """Log a test step"""
        log_func = getattr(logger, level.lower())
        log_func(f"[{step}] {message}")

    def test_health_check(self, service: str, url: str) -> bool:
        """Test service health"""
        self.log_step(f"HEALTH_{service.upper()}", f"Testing {service} health at {url}")

        try:
            start_time = time.time()
            response = requests.get(f"{url}/health", timeout=10)
            end_time = time.time()

            self.log_step(f"HEALTH_{service.upper()}", f"Response status: {response.status_code}, Time: {end_time-start_time:.2f}s")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_step(f"HEALTH_{service.upper()}", f"Response data: {data}")
                    return True
                except json.JSONDecodeError as e:
                    self.log_step(f"HEALTH_{service.upper()}", f"Invalid JSON response: {e}", "error")
                    return False
            else:
                self.log_step(f"HEALTH_{service.upper()}", f"Bad status code: {response.status_code}", "error")
                return False

        except requests.exceptions.RequestException as e:
            self.log_step(f"HEALTH_{service.upper()}", f"Request failed: {e}", "error")
            return False

    def test_document_ingestion(self) -> bool:
        """Test document ingestion with detailed logging"""
        self.log_step("INGESTION", "Starting document ingestion test")

        url = f"{self.base_urls['ingestor']}/ingest"
        test_file_path = "README.md"

        # Check if test file exists
        try:
            with open(test_file_path, 'rb') as f:
                file_content = f.read()
            self.log_step("INGESTION", f"Test file exists: {test_file_path}, size: {len(file_content)} bytes")
        except FileNotFoundError:
            self.log_step("INGESTION", f"Test file not found: {test_file_path}", "error")
            return False

        # Prepare request data
        test_data = {
            "doc_id": f"test-detailed-{int(time.time())}",
            "tenant": "test",
            "project": "test",
            "lang": "en",
            "title": "Detailed Test Document"
        }

        self.log_step("INGESTION", f"Request data: {test_data}")
        self.log_step("INGESTION", f"File: {test_file_path}")

        try:
            with open(test_file_path, 'rb') as f:
                files = {'file': (test_file_path, f, 'text/markdown')}
                start_time = time.time()
                response = requests.post(url, data=test_data, files=files, timeout=30)
                end_time = time.time()

            self.log_step("INGESTION", f"Response status: {response.status_code}, Time: {end_time-start_time:.2f}s")
            self.log_step("INGESTION", f"Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_step("INGESTION", f"Response data: {data}")
                    return True
                except json.JSONDecodeError as e:
                    self.log_step("INGESTION", f"Invalid JSON response: {e}", "error")
                    self.log_step("INGESTION", f"Raw response: {response.text}", "error")
                    return False
            else:
                self.log_step("INGESTION", f"Error response: {response.text}", "error")
                return False

        except requests.exceptions.RequestException as e:
            self.log_step("INGESTION", f"Request failed: {e}", "error")
            return False

    def test_document_retrieval(self) -> bool:
        """Test document retrieval"""
        self.log_step("RETRIEVAL", "Starting document retrieval test")

        url = f"{self.base_urls['retriever']}/retrieve"

        test_data = {
            "query": "What is HyperRAG?",
            "tenant": "test",
            "project": "test",
            "lang": "en",
            "limit": 5
        }

        self.log_step("RETRIEVAL", f"Request data: {test_data}")

        try:
            start_time = time.time()
            response = requests.post(url, json=test_data, timeout=30)
            end_time = time.time()

            self.log_step("RETRIEVAL", f"Response status: {response.status_code}, Time: {end_time-start_time:.2f}s")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_step("RETRIEVAL", f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                    if isinstance(data, dict) and 'results' in data:
                        self.log_step("RETRIEVAL", f"Found {len(data['results'])} results")
                    return True
                except json.JSONDecodeError as e:
                    self.log_step("RETRIEVAL", f"Invalid JSON response: {e}", "error")
                    return False
            else:
                self.log_step("RETRIEVAL", f"Error response: {response.text}", "error")
                return False

        except requests.exceptions.RequestException as e:
            self.log_step("RETRIEVAL", f"Request failed: {e}", "error")
            return False

    def test_evaluation(self) -> bool:
        """Test RAG evaluation"""
        self.log_step("EVALUATION", "Starting evaluation test")

        url = f"{self.base_urls['evaluator']}/evaluate"

        test_data = {
            "query": "What is artificial intelligence?",
            "answer": "AI is a field of computer science focused on creating intelligent machines.",
            "contexts": ["Artificial intelligence is intelligence demonstrated by machines."],
            "lang": "en",
            "tenant": "test"
        }

        self.log_step("EVALUATION", f"Request data: {test_data}")

        try:
            start_time = time.time()
            response = requests.post(url, json=test_data, timeout=60)
            end_time = time.time()

            self.log_step("EVALUATION", f"Response status: {response.status_code}, Time: {end_time-start_time:.2f}s")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_step("EVALUATION", f"Evaluation result: {data}")
                    return True
                except json.JSONDecodeError as e:
                    self.log_step("EVALUATION", f"Invalid JSON response: {e}", "error")
                    return False
            else:
                self.log_step("EVALUATION", f"Error response: {response.text}", "error")
                return False

        except requests.exceptions.RequestException as e:
            self.log_step("EVALUATION", f"Request failed: {e}", "error")
            return False

    def test_agent_session(self) -> bool:
        """Test agent orchestration"""
        self.log_step("AGENT", "Starting agent session test")

        url = f"{self.base_urls['agent_orch']}/session/start"

        test_data = {
            "tenant": "test",
            "user_id": "test_user",
            "session_type": "rag",
            "initial_query": "What is machine learning?"
        }

        self.log_step("AGENT", f"Request data: {test_data}")

        try:
            start_time = time.time()
            response = requests.post(url, json=test_data, timeout=30)
            end_time = time.time()

            self.log_step("AGENT", f"Response status: {response.status_code}, Time: {end_time-start_time:.2f}s")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_step("AGENT", f"Agent session created: {data}")
                    return True
                except json.JSONDecodeError as e:
                    self.log_step("AGENT", f"Invalid JSON response: {e}", "error")
                    return False
            else:
                self.log_step("AGENT", f"Error response: {response.text}", "error")
                return False

        except requests.exceptions.RequestException as e:
            self.log_step("AGENT", f"Request failed: {e}", "error")
            return False

    def test_persian_support(self) -> bool:
        """Test Persian language support"""
        self.log_step("PERSIAN", "Starting Persian support test")

        url = f"{self.base_urls['ingestor']}/ingest"

        test_data = {
            "doc_id": f"test-persian-{int(time.time())}",
            "tenant": "test",
            "project": "test",
            "lang": "fa",
            "title": "تست فارسی"
        }

        # Create a simple Persian test file
        persian_content = "هوش مصنوعی یک زمینه علمی است که با ساخت ماشین‌های هوشمند سروکار دارد."
        test_file_path = "test_persian.txt"

        try:
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(persian_content)

            self.log_step("PERSIAN", f"Created test file: {test_file_path}")

            with open(test_file_path, 'rb') as f:
                files = {'file': (test_file_path, f, 'text/plain; charset=utf-8')}
                start_time = time.time()
                response = requests.post(url, data=test_data, files=files, timeout=30)
                end_time = time.time()

            self.log_step("PERSIAN", f"Response status: {response.status_code}, Time: {end_time-start_time:.2f}s")

            # Clean up test file
            import os
            os.remove(test_file_path)

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_step("PERSIAN", f"Persian document ingested: {data}")
                    return True
                except json.JSONDecodeError as e:
                    self.log_step("PERSIAN", f"Invalid JSON response: {e}", "error")
                    return False
            else:
                self.log_step("PERSIAN", f"Error response: {response.text}", "error")
                return False

        except Exception as e:
            self.log_step("PERSIAN", f"Test failed: {e}", "error")
            return False

    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        logger.info("🚀 Starting comprehensive HyperRAG testing")
        logger.info("=" * 60)

        # Test service health first
        logger.info("🏥 Testing service health...")
        health_results = {}
        for service, url in self.base_urls.items():
            health_results[service] = self.test_health_check(service, url)

        logger.info(f"Health results: {sum(health_results.values())}/{len(health_results)} services healthy")

        # Test functional capabilities
        logger.info("\n📋 Testing functional capabilities...")

        functional_tests = {
            "ingestion_en": self.test_document_ingestion,
            "retrieval_en": self.test_document_retrieval,
            "evaluation": self.test_evaluation,
            "agent_session": self.test_agent_session,
            "persian_support": self.test_persian_support
        }

        functional_results = {}
        for test_name, test_func in functional_tests.items():
            logger.info(f"\n🔍 Running {test_name}...")
            try:
                functional_results[test_name] = test_func()
            except Exception as e:
                logger.error(f"Test {test_name} crashed: {e}")
                functional_results[test_name] = False

        # Combine results
        all_results = {**health_results, **functional_results}

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("=" * 60)

        health_passed = sum(health_results.values())
        functional_passed = sum(functional_results.values())

        logger.info(f"🏥 Health Checks: {health_passed}/{len(health_results)} passed")
        logger.info(f"⚙️  Functional Tests: {functional_passed}/{len(functional_tests)} passed")
        logger.info(f"📈 Overall: {health_passed + functional_passed}/{len(all_results)} passed ({(health_passed + functional_passed)/len(all_results)*100:.1f}%)")

        # Detailed results
        logger.info("\n📋 Detailed Results:")
        for test, passed in all_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"  {test}: {status}")

        return all_results

def main():
    tester = HyperRAGTester()
    results = tester.run_all_tests()

    # Print final summary to console
    print("\n" + "=" * 60)
    print("🎯 FINAL SUMMARY")
    print("=" * 60)

    health_tests = [k for k in results.keys() if not k.startswith(('ingestion', 'retrieval', 'evaluation', 'agent', 'persian'))]
    functional_tests = [k for k in results.keys() if k not in health_tests]

    health_passed = sum(results[k] for k in health_tests)
    functional_passed = sum(results[k] for k in functional_tests)

    print(f"🏥 Health Checks: {health_passed}/{len(health_tests)} passed")
    print(f"⚙️  Functional Tests: {functional_passed}/{len(functional_tests)} passed")

    if all(results.values()):
        print("🎉 ALL TESTS PASSED! HyperRAG is fully operational!")
    else:
        print("⚠️  Some tests failed. Check hyperrag_test.log for details.")

    print("📄 Detailed logs saved to: hyperrag_test.log")

if __name__ == "__main__":
    main()
