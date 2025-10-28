#!/usr/bin/env python3
import os
import re

def fix_metrics_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Pattern to match Counter and Histogram definitions without registry
    counter_pattern = r'(= Counter\(\s*\n\s*\'[^\']+\',\s*\n\s*\'[^\']+\',\s*\n\s*\[[^\]]+\]\s*\n\s*\))'
    histogram_pattern = r'(= Histogram\(\s*\n\s*\'[^\']+\',\s*\n\s*\'[^\']+\',\s*\n\s*\[[^\]]+\]\s*\n\s*\))'

    # Replace Counter definitions
    content = re.sub(counter_pattern, r'\1,\n    registry=registry', content)

    # Replace Histogram definitions
    content = re.sub(histogram_pattern, r'\1,\n    registry=registry', content)

    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Fixed metrics in {filepath}")

# Find all main.py files
for root, dirs, files in os.walk('platform/services'):
    for file in files:
        if file == 'main.py':
            filepath = os.path.join(root, file)
            if 'ingestor' not in filepath and 'chunker' not in filepath and 'embedder' not in filepath:
                fix_metrics_in_file(filepath)

print("All remaining services fixed!")
