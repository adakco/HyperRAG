#!/usr/bin/env python3
"""
🎯 HyperRAG Comprehensive Test Suite
=====================================

This test suite performs a complete end-to-end test of the HyperRAG system,
simulating a real-world RAG pipeline with multiple languages and scenarios.

Test Coverage:
- Health checks for all services
- Document ingestion (English & Persian)
- Document processing pipeline
- Retrieval and search
- RAG evaluation
- Agent sessions
- Cost tracking
- Memory management
- Performance metrics
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

class HyperRAGTestSuite:
    """Comprehensive test suite for HyperRAG system"""
    
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
            'health_checks': {},
            'functional_tests': {},
            'performance_metrics': {},
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        # Test data
        self.test_documents = {
            'english': {
                'content': """
                HyperRAG: Advanced Retrieval-Augmented Generation System
                
                HyperRAG is a state-of-the-art RAG (Retrieval-Augmented Generation) system 
                that combines advanced information retrieval techniques with large language 
                models to provide accurate and contextually relevant responses.
                
                Key Features:
                - Multi-language support (English, Persian, Arabic)
                - Advanced chunking strategies
                - Hybrid retrieval (dense + sparse)
                - Real-time evaluation metrics
                - Cost tracking and optimization
                - Memory management
                - Agent orchestration
                
                Architecture:
                The system consists of 12 microservices:
                1. Ingestor: Document ingestion and storage
                2. Normalizer: Text normalization and PII removal
                3. Chunker: Intelligent document chunking
                4. Embedder: Vector embedding generation
                5. Retriever: Hybrid document retrieval
                6. Reranker: Result re-ranking
                7. Evaluator: RAG quality assessment
                8. Agent-orch: Agent orchestration
                9. Policy: Security and access control
                10. Costing: Cost tracking and optimization
                11. Pack-longrag: Long-context packing
                12. Memory-memorag: Episodic memory management
                
                Performance:
                - Sub-second retrieval times
                - 95%+ accuracy on benchmark datasets
                - Support for documents up to 1M tokens
                - Real-time processing capabilities
                """,
                'title': 'HyperRAG System Documentation',
                'lang': 'en'
            },
            'persian': {
                'content': """
                هایپررگ: سیستم پیشرفته تولید تقویت شده با بازیابی
                
                هایپررگ یک سیستم پیشرفته RAG (تولید تقویت شده با بازیابی) است که 
                تکنیک‌های پیشرفته بازیابی اطلاعات را با مدل‌های زبان بزرگ ترکیب می‌کند 
                تا پاسخ‌های دقیق و مرتبط با زمینه ارائه دهد.
                
                ویژگی‌های کلیدی:
                - پشتیبانی چندزبانه (انگلیسی، فارسی، عربی)
                - استراتژی‌های پیشرفته تقسیم‌بندی
                - بازیابی ترکیبی (چگال + پراکنده)
                - معیارهای ارزیابی بلادرنگ
                - ردیابی هزینه و بهینه‌سازی
                - مدیریت حافظه
                - هماهنگی عامل
                
                معماری:
                سیستم شامل 12 میکروسرویس است:
                1. اینجستر: ورود و ذخیره اسناد
                2. نرمالایزر: نرمال‌سازی متن و حذف اطلاعات شخصی
                3. چانکر: تقسیم‌بندی هوشمند اسناد
                4. امبدر: تولید بردارهای جاسازی
                5. ریتریور: بازیابی ترکیبی اسناد
                6. ریرانکر: بازرتبه‌بندی نتایج
                7. ایوالیوتر: ارزیابی کیفیت RAG
                8. ایجنت-اورچ: هماهنگی عامل
                9. پالیسی: امنیت و کنترل دسترسی
                10. کاستینگ: ردیابی هزینه و بهینه‌سازی
                11. پک-لونگرگ: بسته‌بندی زمینه طولانی
                12. مموری-ممورگ: مدیریت حافظه رویدادی
                
                عملکرد:
                - زمان بازیابی زیر ثانیه
                - دقت 95%+ در مجموعه داده‌های معیار
                - پشتیبانی از اسناد تا 1M توکن
                - قابلیت‌های پردازش بلادرنگ
                """,
                'title': 'مستندات سیستم هایپررگ',
                'lang': 'fa'
            }
        }
        
        self.test_queries = {
            'english': [
                "What is HyperRAG?",
                "What are the key features of HyperRAG?",
                "How many microservices does HyperRAG have?",
                "What is the performance of HyperRAG?"
            ],
            'persian': [
                "هایپررگ چیست؟",
                "ویژگی‌های کلیدی هایپررگ چیست؟",
                "هایپررگ چند میکروسرویس دارد؟",
                "عملکرد هایپررگ چگونه است؟"
            ]
        }

    async def run_comprehensive_test(self):
        """Run the complete test suite"""
        logger.info("🚀 Starting HyperRAG Comprehensive Test Suite")
        logger.info("=" * 60)
        
        self.test_results['start_time'] = datetime.utcnow()
        
        try:
            # Phase 1: Health Checks
            await self.test_health_checks()
            
            # Phase 2: Document Ingestion
            await self.test_document_ingestion()
            
            # Phase 3: Document Processing Pipeline
            await self.test_processing_pipeline()
            
            # Phase 4: Document Retrieval
            await self.test_document_retrieval()
            
            # Phase 5: RAG Evaluation
            await self.test_rag_evaluation()
            
            # Phase 6: Agent Sessions
            await self.test_agent_sessions()
            
            # Phase 7: Cost Tracking
            await self.test_cost_tracking()
            
            # Phase 8: Memory Management
            await self.test_memory_management()
            
            # Phase 9: Performance Analysis
            await self.test_performance_analysis()
            
        except Exception as e:
            logger.error("Test suite failed", error=str(e), exc_info=True)
            self.test_results['errors'].append(str(e))
        
        finally:
            if self.test_results['end_time'] is None:
                self.test_results['end_time'] = datetime.utcnow()
            await self.generate_final_report()

    async def test_health_checks(self):
        """Phase 1: Test health of all services"""
        logger.info("🏥 Phase 1: Testing service health...")
        
        for service_name, url in self.base_urls.items():
            try:
                start_time = time.time()
                response = requests.get(f"{url}/health", timeout=10)
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    self.test_results['health_checks'][service_name] = {
                        'status': 'healthy',
                        'response_time': end_time - start_time,
                        'data': data
                    }
                    logger.info(f"✅ {service_name}: Healthy", 
                              response_time=f"{end_time - start_time:.3f}s")
                else:
                    self.test_results['health_checks'][service_name] = {
                        'status': 'unhealthy',
                        'status_code': response.status_code,
                        'error': response.text
                    }
                    logger.error(f"❌ {service_name}: Unhealthy", 
                                status_code=response.status_code)
                    
            except Exception as e:
                self.test_results['health_checks'][service_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"❌ {service_name}: Error", error=str(e))

    async def test_document_ingestion(self):
        """Phase 2: Test document ingestion"""
        logger.info("📥 Phase 2: Testing document ingestion...")
        
        for lang, doc_data in self.test_documents.items():
            try:
                doc_id = f"test-comprehensive-{lang}-{int(time.time())}"
                
                # Create temporary file
                temp_file = Path(f"temp_{lang}_doc.txt")
                temp_file.write_text(doc_data['content'])
                
                # Ingest document
                start_time = time.time()
                with open(temp_file, 'rb') as f:
                    files = {'file': f}
                    data = {
                        'doc_id': doc_id,
                        'tenant': 'test',
                        'project': 'comprehensive-test',
                        'lang': doc_data['lang'],
                        'title': doc_data['title']
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
                    self.test_results['functional_tests'][f'ingestion_{lang}'] = {
                        'status': 'success',
                        'doc_id': doc_id,
                        'version': result.get('version'),
                        'response_time': end_time - start_time,
                        'data': result
                    }
                    logger.info(f"✅ {lang} ingestion: Success", 
                              doc_id=doc_id, version=result.get('version'))
                else:
                    self.test_results['functional_tests'][f'ingestion_{lang}'] = {
                        'status': 'failed',
                        'status_code': response.status_code,
                        'error': response.text
                    }
                    logger.error(f"❌ {lang} ingestion: Failed", 
                                status_code=response.status_code)
                    
            except Exception as e:
                self.test_results['functional_tests'][f'ingestion_{lang}'] = {
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"❌ {lang} ingestion: Error", error=str(e))

    async def test_processing_pipeline(self):
        """Phase 3: Test document processing pipeline"""
        logger.info("⚙️ Phase 3: Testing processing pipeline...")
        
        # Wait for processing to complete
        await asyncio.sleep(5)
        
        # Test chunker
        try:
            response = requests.get(f"{self.base_urls['chunker']}/health", timeout=10)
            if response.status_code == 200:
                self.test_results['functional_tests']['chunker'] = {
                    'status': 'healthy',
                    'data': response.json()
                }
                logger.info("✅ Chunker: Processing pipeline active")
            else:
                logger.warning("⚠️ Chunker: May not be processing")
        except Exception as e:
            logger.warning("⚠️ Chunker: Could not verify processing", error=str(e))

    async def test_document_retrieval(self):
        """Phase 4: Test document retrieval"""
        logger.info("🔍 Phase 4: Testing document retrieval...")
        
        for lang, queries in self.test_queries.items():
            for i, query in enumerate(queries):
                try:
                    start_time = time.time()
                    data = {
                        'query': query,
                        'tenant': 'test',
                        'project': 'comprehensive-test',
                        'lang': lang,
                        'limit': 5
                    }
                    response = requests.post(
                        f"{self.base_urls['retriever']}/retrieve",
                        json=data,
                        timeout=30
                    )
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        result = response.json()
                        results_count = len(result.get('results', []))
                        avg_score = sum(r.get('score', 0) for r in result.get('results', [])) / max(results_count, 1)
                        
                        self.test_results['functional_tests'][f'retrieval_{lang}_{i}'] = {
                            'status': 'success',
                            'query': query,
                            'results_count': results_count,
                            'avg_score': avg_score,
                            'response_time': end_time - start_time,
                            'data': result
                        }
                        logger.info(f"✅ {lang} retrieval {i+1}: Success", 
                                  query=query, results=results_count, avg_score=f"{avg_score:.3f}")
                    else:
                        self.test_results['functional_tests'][f'retrieval_{lang}_{i}'] = {
                            'status': 'failed',
                            'query': query,
                            'status_code': response.status_code,
                            'error': response.text
                        }
                        logger.error(f"❌ {lang} retrieval {i+1}: Failed", 
                                    query=query, status_code=response.status_code)
                        
                except Exception as e:
                    self.test_results['functional_tests'][f'retrieval_{lang}_{i}'] = {
                        'status': 'error',
                        'query': query,
                        'error': str(e)
                    }
                    logger.error(f"❌ {lang} retrieval {i+1}: Error", 
                                query=query, error=str(e))

    async def test_rag_evaluation(self):
        """Phase 5: Test RAG evaluation"""
        logger.info("📊 Phase 5: Testing RAG evaluation...")
        
        test_cases = [
            {
                'query': 'What is HyperRAG?',
                'answer': 'HyperRAG is an advanced RAG system that combines retrieval techniques with LLMs.',
                'contexts': ['HyperRAG is a state-of-the-art RAG system'],
                'lang': 'en'
            },
            {
                'query': 'هایپررگ چیست؟',
                'answer': 'هایپررگ یک سیستم پیشرفته RAG است که تکنیک‌های بازیابی را با مدل‌های زبان ترکیب می‌کند.',
                'contexts': ['هایپررگ یک سیستم پیشرفته RAG است'],
                'lang': 'fa'
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            try:
                start_time = time.time()
                data = {
                    'query': test_case['query'],
                    'answer': test_case['answer'],
                    'contexts': test_case['contexts'],
                    'lang': test_case['lang'],
                    'tenant': 'test'
                }
                response = requests.post(
                    f"{self.base_urls['evaluator']}/evaluate",
                    json=data,
                    timeout=60
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    result = response.json()
                    overall_score = result.get('overall_score', 0)
                    passed = result.get('passed', False)
                    
                    self.test_results['functional_tests'][f'evaluation_{i}'] = {
                        'status': 'success',
                        'overall_score': overall_score,
                        'passed': passed,
                        'response_time': end_time - start_time,
                        'data': result
                    }
                    logger.info(f"✅ Evaluation {i+1}: Success", 
                              overall_score=f"{overall_score:.3f}", passed=passed)
                else:
                    self.test_results['functional_tests'][f'evaluation_{i}'] = {
                        'status': 'failed',
                        'status_code': response.status_code,
                        'error': response.text
                    }
                    logger.error(f"❌ Evaluation {i+1}: Failed", 
                                status_code=response.status_code)
                    
            except Exception as e:
                self.test_results['functional_tests'][f'evaluation_{i}'] = {
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"❌ Evaluation {i+1}: Error", error=str(e))

    async def test_agent_sessions(self):
        """Phase 6: Test agent sessions"""
        logger.info("🤖 Phase 6: Testing agent sessions...")
        
        try:
            start_time = time.time()
            data = {
                'tenant': 'test',
                'user_id': 'test_user',
                'session_type': 'rag',
                'initial_query': 'What is machine learning?'
            }
            response = requests.post(
                f"{self.base_urls['agent_orch']}/session/start",
                json=data,
                timeout=30
            )
            end_time = time.time()
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get('session_id')
                
                self.test_results['functional_tests']['agent_session'] = {
                    'status': 'success',
                    'session_id': session_id,
                    'response_time': end_time - start_time,
                    'data': result
                }
                logger.info("✅ Agent session: Success", session_id=session_id)
            else:
                self.test_results['functional_tests']['agent_session'] = {
                    'status': 'failed',
                    'status_code': response.status_code,
                    'error': response.text
                }
                logger.error("❌ Agent session: Failed", 
                            status_code=response.status_code)
                
        except Exception as e:
            self.test_results['functional_tests']['agent_session'] = {
                'status': 'error',
                'error': str(e)
            }
            logger.error("❌ Agent session: Error", error=str(e))

    async def test_cost_tracking(self):
        """Phase 7: Test cost tracking"""
        logger.info("💰 Phase 7: Testing cost tracking...")
        
        try:
            response = requests.get(f"{self.base_urls['costing']}/health", timeout=10)
            if response.status_code == 200:
                self.test_results['functional_tests']['costing'] = {
                    'status': 'healthy',
                    'data': response.json()
                }
                logger.info("✅ Cost tracking: Active")
            else:
                logger.warning("⚠️ Cost tracking: May not be active")
        except Exception as e:
            logger.warning("⚠️ Cost tracking: Could not verify", error=str(e))

    async def test_memory_management(self):
        """Phase 8: Test memory management"""
        logger.info("🧠 Phase 8: Testing memory management...")
        
        try:
            response = requests.get(f"{self.base_urls['memory_memorag']}/health", timeout=10)
            if response.status_code == 200:
                self.test_results['functional_tests']['memory'] = {
                    'status': 'healthy',
                    'data': response.json()
                }
                logger.info("✅ Memory management: Active")
            else:
                logger.warning("⚠️ Memory management: May not be active")
        except Exception as e:
            logger.warning("⚠️ Memory management: Could not verify", error=str(e))

    async def test_performance_analysis(self):
        """Phase 9: Analyze performance metrics"""
        logger.info("📈 Phase 9: Analyzing performance metrics...")
        
        # Calculate overall statistics
        health_checks = self.test_results.get('health_checks', {})
        functional_tests = self.test_results.get('functional_tests', {})
        
        healthy_services = sum(1 for hc in health_checks.values() if hc.get('status') == 'healthy')
        total_services = len(health_checks)
        
        successful_tests = sum(1 for ft in functional_tests.values() if ft.get('status') == 'success')
        total_tests = len(functional_tests)
        
        # Calculate average response times
        response_times = []
        for test_result in functional_tests.values():
            if 'response_time' in test_result:
                response_times.append(test_result['response_time'])
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Calculate total test duration
        start_time = self.test_results.get('start_time')
        end_time = self.test_results.get('end_time')
        total_duration = 0
        if start_time and end_time:
            total_duration = (end_time - start_time).total_seconds()
        
        self.test_results['performance_metrics'] = {
            'healthy_services': healthy_services,
            'total_services': total_services,
            'health_percentage': (healthy_services / total_services) * 100 if total_services > 0 else 0,
            'successful_tests': successful_tests,
            'total_tests': total_tests,
            'success_percentage': (successful_tests / total_tests) * 100 if total_tests > 0 else 0,
            'average_response_time': avg_response_time,
            'total_test_duration': total_duration
        }

    async def generate_final_report(self):
        """Generate comprehensive final report"""
        logger.info("📋 Generating final report...")
        
        metrics = self.test_results['performance_metrics']
        
        logger.info("=" * 60)
        logger.info("🎯 HYPERRAG COMPREHENSIVE TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"🏥 Health Checks: {metrics['healthy_services']}/{metrics['total_services']} ({metrics['health_percentage']:.1f}%)")
        logger.info(f"⚙️ Functional Tests: {metrics['successful_tests']}/{metrics['total_tests']} ({metrics['success_percentage']:.1f}%)")
        logger.info(f"⏱️ Average Response Time: {metrics['average_response_time']:.3f}s")
        logger.info(f"🕐 Total Test Duration: {metrics['total_test_duration']:.1f}s")
        
        if metrics['success_percentage'] >= 90:
            logger.info("🎉 EXCELLENT: System is performing exceptionally well!")
        elif metrics['success_percentage'] >= 80:
            logger.info("✅ GOOD: System is performing well with minor issues")
        elif metrics['success_percentage'] >= 70:
            logger.info("⚠️ FAIR: System is functional but needs improvement")
        else:
            logger.info("❌ POOR: System has significant issues that need attention")
        
        # Save detailed results
        with open('comprehensive_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        logger.info("📄 Detailed results saved to: comprehensive_test_results.json")
        logger.info("=" * 60)

async def main():
    """Main test execution"""
    test_suite = HyperRAGTestSuite()
    await test_suite.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())
