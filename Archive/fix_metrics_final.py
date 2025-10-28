#!/usr/bin/env python3
import os
import re

def fix_metrics_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Fix Counter definitions - remove extra commas and registry lines
    content = re.sub(r'(= Counter\(\s*\n\s*\'[^\']+\',\s*\n\s*\'[^\']+\',\s*\n\s*\[[^\]]+\]\s*\n\s*\)),\s*\n\s*registry=registry,\s*\n\s*registry=registry',
                     r'\1,\n    registry=registry', content)

    # Fix Histogram definitions - remove extra commas and registry lines
    content = re.sub(r'(= Histogram\(\s*\n\s*\'[^\']+\',\s*\n\s*\'[^\']+\',\s*\n\s*\[[^\]]+\]\s*\n\s*\)),\s*\n\s*registry=registry,\s*\n\s*registry=registry',
                     r'\1,\n    registry=registry', content)

    # Fix any remaining issues
    content = re.sub(r'registry=registry,\s*\n\s*registry=registry', 'registry=registry', content)

    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Fixed metrics in {filepath}")

# Find all main.py files and fix them
for root, dirs, files in os.walk('platform/services'):
    for file in files:
        if file == 'main.py':
            filepath = os.path.join(root, file)
            if 'ingestor' not in filepath and 'chunker' not in filepath and 'embedder' not in filepath:
                fix_metrics_in_file(filepath)

print("All services fixed!")
