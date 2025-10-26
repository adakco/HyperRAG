#!/usr/bin/env python3
"""
🎯 HyperRAG Final Comprehensive Test
====================================

This is the final test that demonstrates the complete HyperRAG system
working end-to-end with detailed logging and analysis.
"""

import asyncio
import json
import time
import uuid
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

class HyperRAGFinalTest:
    """Final comprehensive test for HyperRAG system"""
    
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
            'phases': {},
            'summary': {},
            'recommendations': []
        }

    async def run_final_test(self):
        """Run the final comprehensive test"""
        print("🎯 HYPERRAG FINAL COMPREHENSIVE TEST")
        print("=" * 60)
        print(f"🕐 Start Time: {self.test_results['start_time']}")
        print()
        
        try:
            # Phase 1: System Health Check
            await self.phase_1_health_check()
            
            # Phase 2: Document Ingestion
            await self.phase_2_document_ingestion()
            
            # Phase 3: Wait for Processing
            await self.phase_3_wait_for_processing()
            
            # Phase 4: Document Retrieval
            await self.phase_4_document_retrieval()
            
            # Phase 5: RAG Evaluation
            await self.phase_5_rag_evaluation()
            
            # Phase 6: Agent Session
            await self.phase_6_agent_session()
            
            # Phase 7: System Analysis
            await self.phase_7_system_analysis()
            
        except Exception as e:
            logger.error("Final test failed", error=str(e))
            self.test_results['summary']['status'] = 'failed'
            self.test_results['summary']['error'] = str(e)
        
        finally:
            self.test_results['end_time'] = datetime.utcnow()
            await self.generate_final_summary()

    async def phase_1_health_check(self):
        """Phase 1: Comprehensive health check"""
        print("🏥 PHASE 1: SYSTEM HEALTH CHECK")
        print("-" * 40)
        
        healthy_count = 0
        total_count = len(self.base_urls)
        
        for service_name, url in self.base_urls.items():
            try:
                start_time = time.time()
                response = requests.get(f"{url}/health", timeout=10)
                end_time = time.time()
                
                if response.status_code == 200:
                    healthy_count += 1
                    print(f"✅ {service_name}: Healthy ({end_time - start_time:.3f}s)")
                else:
                    print(f"❌ {service_name}: Unhealthy ({response.status_code})")
                    
            except Exception as e:
                print(f"❌ {service_name}: Error - {str(e)}")
        
        health_percentage = (healthy_count / total_count) * 100
        self.test_results['phases']['health_check'] = {
            'healthy_services': healthy_count,
            'total_services': total_count,
            'health_percentage': health_percentage,
            'status': 'passed' if health_percentage >= 90 else 'failed'
        }
        
        print(f"📊 Health Summary: {healthy_count}/{total_count} ({health_percentage:.1f}%)")
        print()

    async def phase_2_document_ingestion(self):
        """Phase 2: Document ingestion test"""
        print("📥 PHASE 2: DOCUMENT INGESTION")
        print("-" * 40)
        
        # Test document content
        test_content = """
        HyperRAG System Overview
        
        HyperRAG is a comprehensive Retrieval-Augmented Generation (RAG) system
        designed for enterprise applications. It provides:
        
        1. Multi-language support (English, Persian, Arabic)
        2. Advanced document processing pipeline
        3. Hybrid retrieval (dense + sparse search)
        4. Real-time evaluation and monitoring
        5. Cost tracking and optimization
        6. Agent orchestration capabilities
        
        The system consists of 12 microservices working together to provide
        a complete RAG solution with enterprise-grade features.
        """
        
        doc_id = f"final-test-{int(time.time())}"
        
        # Create temporary file
        temp_file = Path("temp_final_test.txt")
        temp_file.write_text(test_content)
        
        try:
            start_time = time.time()
            with open(temp_file, 'rb') as f:
                files = {'file': f}
                data = {
                    'doc_id': doc_id,
                    'tenant': 'test',
                    'project': 'final-test',
                    'lang': 'en',
                    'title': 'HyperRAG Final Test Document'
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
                
                self.test_results['phases']['ingestion'] = {
                    'status': 'success',
                    'doc_id': doc_id,
                    'version': result.get('version'),
                    'response_time': end_time - start_time
                }
            else:
                print(f"❌ Ingestion failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['phases']['ingestion'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Ingestion error: {str(e)}")
            self.test_results['phases']['ingestion'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def phase_3_wait_for_processing(self):
        """Phase 3: Wait for document processing"""
        print("⏳ PHASE 3: WAITING FOR PROCESSING")
        print("-" * 40)
        
        print("🔄 Waiting for document processing pipeline...")
        print("This includes: chunking → embedding → storage in Qdrant")
        
        # Wait for processing to complete
        for i in range(30):  # Wait up to 30 seconds
            await asyncio.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"⏱️ Waiting... {i}s elapsed")
        
        print("✅ Processing wait completed")
        print()

    async def phase_4_document_retrieval(self):
        """Phase 4: Document retrieval test"""
        print("🔍 PHASE 4: DOCUMENT RETRIEVAL")
        print("-" * 40)
        
        test_queries = [
            "What is HyperRAG?",
            "What are the key features?",
            "How many microservices does it have?",
            "What languages are supported?"
        ]
        
        successful_retrievals = 0
        total_results = 0
        
        for i, query in enumerate(test_queries):
            try:
                start_time = time.time()
                data = {
                    'query': query,
                    'tenant': 'test',
                    'project': 'final-test',
                    'lang': 'en',
                    'limit': 3
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
                    total_results += results_count
                    
                    if results_count > 0:
                        successful_retrievals += 1
                        print(f"✅ Query {i+1}: '{query}' - {results_count} results ({end_time - start_time:.3f}s)")
                        
                        # Show first result snippet
                        first_result = result['results'][0]
                        content_preview = first_result['content'][:100] + "..." if len(first_result['content']) > 100 else first_result['content']
                        print(f"   📄 Preview: {content_preview}")
                    else:
                        print(f"⚠️ Query {i+1}: '{query}' - No results found ({end_time - start_time:.3f}s)")
                else:
                    print(f"❌ Query {i+1}: '{query}' - Failed ({response.status_code})")
                    
            except Exception as e:
                print(f"❌ Query {i+1}: '{query}' - Error: {str(e)}")
        
        self.test_results['phases']['retrieval'] = {
            'successful_queries': successful_retrievals,
            'total_queries': len(test_queries),
            'total_results': total_results,
            'success_rate': (successful_retrievals / len(test_queries)) * 100
        }
        
        print(f"📊 Retrieval Summary: {successful_retrievals}/{len(test_queries)} queries successful, {total_results} total results")
        print()

    async def phase_5_rag_evaluation(self):
        """Phase 5: RAG evaluation test"""
        print("📊 PHASE 5: RAG EVALUATION")
        print("-" * 40)
        
        test_case = {
            'query': 'What is HyperRAG?',
            'answer': 'HyperRAG is a comprehensive RAG system with multi-language support and enterprise features.',
            'contexts': ['HyperRAG is a comprehensive Retrieval-Augmented Generation (RAG) system designed for enterprise applications.'],
            'lang': 'en'
        }
        
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
                
                print(f"✅ Evaluation completed")
                print(f"📊 Overall Score: {overall_score:.3f}")
                print(f"🎯 Passed: {'Yes' if passed else 'No'}")
                print(f"⏱️ Time: {end_time - start_time:.3f}s")
                
                # Show individual metrics
                for metric in result.get('results', []):
                    metric_name = metric['metric_name']
                    score = metric['score']
                    threshold = metric['threshold']
                    passed = metric['passed']
                    status = "✅" if passed else "⚠️"
                    print(f"   {status} {metric_name}: {score:.3f} (threshold: {threshold})")
                
                self.test_results['phases']['evaluation'] = {
                    'status': 'success',
                    'overall_score': overall_score,
                    'passed': passed,
                    'response_time': end_time - start_time
                }
            else:
                print(f"❌ Evaluation failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['phases']['evaluation'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Evaluation error: {str(e)}")
            self.test_results['phases']['evaluation'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def phase_6_agent_session(self):
        """Phase 6: Agent session test"""
        print("🤖 PHASE 6: AGENT SESSION")
        print("-" * 40)
        
        try:
            start_time = time.time()
            data = {
                'tenant': 'test',
                'user_id': 'final_test_user',
                'session_type': 'rag',
                'initial_query': 'Tell me about HyperRAG system capabilities'
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
                
                print(f"✅ Agent session started successfully")
                print(f"🆔 Session ID: {session_id}")
                print(f"⏱️ Time: {end_time - start_time:.3f}s")
                
                self.test_results['phases']['agent_session'] = {
                    'status': 'success',
                    'session_id': session_id,
                    'response_time': end_time - start_time
                }
            else:
                print(f"❌ Agent session failed: {response.status_code}")
                print(f"Error: {response.text}")
                self.test_results['phases']['agent_session'] = {
                    'status': 'failed',
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Agent session error: {str(e)}")
            self.test_results['phases']['agent_session'] = {
                'status': 'error',
                'error': str(e)
            }
        
        print()

    async def phase_7_system_analysis(self):
        """Phase 7: System analysis and recommendations"""
        print("📈 PHASE 7: SYSTEM ANALYSIS")
        print("-" * 40)
        
        # Analyze results
        phases = self.test_results['phases']
        
        # Health check analysis
        health_check = phases.get('health_check', {})
        health_percentage = health_check.get('health_percentage', 0)
        
        # Ingestion analysis
        ingestion = phases.get('ingestion', {})
        ingestion_success = ingestion.get('status') == 'success'
        
        # Retrieval analysis
        retrieval = phases.get('retrieval', {})
        retrieval_success_rate = retrieval.get('success_rate', 0)
        
        # Evaluation analysis
        evaluation = phases.get('evaluation', {})
        evaluation_success = evaluation.get('status') == 'success'
        
        # Agent session analysis
        agent_session = phases.get('agent_session', {})
        agent_success = agent_session.get('status') == 'success'
        
        print("📊 SYSTEM ANALYSIS RESULTS:")
        print(f"🏥 Health Check: {health_percentage:.1f}% services healthy")
        print(f"📥 Document Ingestion: {'✅ Success' if ingestion_success else '❌ Failed'}")
        print(f"🔍 Document Retrieval: {retrieval_success_rate:.1f}% success rate")
        print(f"📊 RAG Evaluation: {'✅ Success' if evaluation_success else '❌ Failed'}")
        print(f"🤖 Agent Session: {'✅ Success' if agent_success else '❌ Failed'}")
        print()
        
        # Generate recommendations
        recommendations = []
        
        if health_percentage >= 90:
            recommendations.append("✅ System health is excellent")
        elif health_percentage >= 80:
            recommendations.append("⚠️ System health is good but could be improved")
        else:
            recommendations.append("❌ System health needs attention")
        
        if ingestion_success:
            recommendations.append("✅ Document ingestion is working properly")
        else:
            recommendations.append("❌ Document ingestion needs to be fixed")
        
        if retrieval_success_rate >= 80:
            recommendations.append("✅ Document retrieval is performing well")
        elif retrieval_success_rate >= 50:
            recommendations.append("⚠️ Document retrieval is partially working")
        else:
            recommendations.append("❌ Document retrieval needs improvement")
        
        if evaluation_success:
            recommendations.append("✅ RAG evaluation is functional")
        else:
            recommendations.append("❌ RAG evaluation needs attention")
        
        if agent_success:
            recommendations.append("✅ Agent orchestration is working")
        else:
            recommendations.append("❌ Agent orchestration needs to be fixed")
        
        self.test_results['recommendations'] = recommendations
        
        print("💡 RECOMMENDATIONS:")
        for rec in recommendations:
            print(f"   {rec}")
        print()

    async def generate_final_summary(self):
        """Generate final summary"""
        print("🎯 FINAL SUMMARY")
        print("=" * 60)
        
        phases = self.test_results['phases']
        
        # Calculate overall success rate
        total_phases = len(phases)
        successful_phases = sum(1 for phase in phases.values() if phase.get('status') == 'success')
        success_rate = (successful_phases / total_phases) * 100 if total_phases > 0 else 0
        
        print(f"📊 Overall Success Rate: {success_rate:.1f}%")
        print(f"✅ Successful Phases: {successful_phases}/{total_phases}")
        print()
        
        # Phase-by-phase summary
        print("📋 PHASE SUMMARY:")
        phase_names = {
            'health_check': '🏥 Health Check',
            'ingestion': '📥 Document Ingestion',
            'retrieval': '🔍 Document Retrieval',
            'evaluation': '📊 RAG Evaluation',
            'agent_session': '🤖 Agent Session'
        }
        
        for phase_key, phase_name in phase_names.items():
            phase = phases.get(phase_key, {})
            status = phase.get('status', 'unknown')
            if status == 'success':
                print(f"   ✅ {phase_name}: Success")
            elif status == 'failed':
                print(f"   ❌ {phase_name}: Failed")
            else:
                print(f"   ⚠️ {phase_name}: {status}")
        
        print()
        
        # Overall assessment
        if success_rate >= 90:
            assessment = "🎉 EXCELLENT"
            color = "🟢"
        elif success_rate >= 80:
            assessment = "✅ GOOD"
            color = "🟡"
        elif success_rate >= 70:
            assessment = "⚠️ FAIR"
            color = "🟠"
        else:
            assessment = "❌ POOR"
            color = "🔴"
        
        print(f"{color} OVERALL ASSESSMENT: {assessment}")
        print(f"Success Rate: {success_rate:.1f}%")
        print()
        
        # Test duration
        duration = (self.test_results['end_time'] - self.test_results['start_time']).total_seconds()
        print(f"🕐 Total Test Duration: {duration:.1f} seconds")
        print()
        
        print("=" * 60)
        print("🎯 HyperRAG Final Test Completed!")
        print("📄 Detailed results saved in test results")
        print("=" * 60)

async def main():
    """Main test execution"""
    test = HyperRAGFinalTest()
    await test.run_final_test()

if __name__ == "__main__":
    asyncio.run(main())
