#!/usr/bin/env python3
import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        new_lines.append(line)

        # Check if this is a Counter or Histogram definition
        if ('= Counter(' in line or '= Histogram(' in line) and not line.strip().endswith(','):
            # Look for the closing parenthesis
            j = i + 1
            while j < len(lines):
                next_line = lines[j].rstrip()
                if next_line.strip() == '),':
                    # Found the problematic closing, fix it
                    new_lines[-1] = new_lines[-1] + ','
                    new_lines.append('    registry=registry')
                    # Skip the problematic line
                    j += 1
                    break
                elif next_line.strip().endswith('),'):
                    # Already properly formatted
                    break
                j += 1

        i += 1

    # Write back
    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines) + '\n')

    print(f"Fixed {filepath}")

# Fix all service files
for root, dirs, files in os.walk('platform/services'):
    for file in files:
        if file == 'main.py':
            filepath = os.path.join(root, file)
            fix_file(filepath)

print("All metrics fixed!")
