#!/usr/bin/env python3
"""
Fix unknown_service issue by adding SERVICE_NAME to OTEL TracerProvider
"""

import re
import os

SERVICES = {
    'ingestor': 'hyperrag-ingestor',
    'normalizer': 'hyperrag-normalizer',
    'chunker': 'hyperrag-chunker',
    'embedder': 'hyperrag-embedder',
    'retriever': 'hyperrag-retriever',
    'reranker': 'hyperrag-reranker',
    'evaluator': 'hyperrag-evaluator',
    'agent-orch': 'hyperrag-agent-orch',
    'policy': 'hyperrag-policy',
    'costing': 'hyperrag-costing',
    'pack.longrag': 'hyperrag-pack-longrag',
    'memory.memorag': 'hyperrag-memory',
}

def fix_service(service_name, service_label):
    """Fix a single service file"""
    file_path = f'platform/services/{service_name}/main.py'
    
    if not os.path.exists(file_path):
        print(f'⚠️  Skipping {service_name} - file not found')
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already fixed
    if 'Resource.create(attributes' in content:
        print(f'✅ {service_name} already fixed')
        return True
    
    # Add import if not exists
    if 'from opentelemetry.sdk.resources import Resource, SERVICE_NAME' not in content:
        # Add after opentelemetry imports
        content = re.sub(
            r'(from opentelemetry\.sdk\.trace import TracerProvider)',
            r'\1\nfrom opentelemetry.sdk.resources import Resource, SERVICE_NAME',
            content
        )
    
    # Replace TracerProvider initialization
    old_pattern = r'trace\.set_tracer_provider\(TracerProvider\(\)\)'
    new_code = f'resource = Resource.create(attributes={{SERVICE_NAME: "{service_label}"}})\ntrace.set_tracer_provider(TracerProvider(resource=resource))'
    
    if not re.search(old_pattern, content):
        print(f'⚠️  {service_name} - TracerProvider pattern not found')
        return False
    
    content = re.sub(old_pattern, new_code, content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f'✅ Fixed {service_name} -> {service_label}')
    return True

def main():
    print('🔧 Fixing service names in OTEL configuration...\n')
    
    fixed_count = 0
    for service_name, service_label in SERVICES.items():
        if fix_service(service_name, service_label):
            fixed_count += 1
    
    print(f'\n✅ Fixed {fixed_count}/{len(SERVICES)} services')
    print('\n📝 Next steps:')
    print('  1. Restart all services')
    print('  2. Check traces in Grafana')
    print('  3. Service graph should show all services')

if __name__ == '__main__':
    main()

