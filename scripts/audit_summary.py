#!/usr/bin/env python3
"""
Generate summary of vanilla JS audit results.
"""

import json
import sys
from collections import Counter, defaultdict

with open('audit_results.json', 'r', encoding='utf-16') as f:
    data = json.load(f)

# Count by pattern
patterns = Counter(v['pattern'] for v in data)
severity = Counter(v['severity'] for v in data)
files = defaultdict(int)

for v in data:
    files[v['file']] += 1

print('=== VANILLA JS AUDIT SUMMARY ===\n')
print(f'Total violations: {len(data)}')
print(f'Errors: {severity["error"]}')
print(f'Warnings: {severity["warning"]}')
print(f'\n=== TOP PATTERNS ===')
for pattern, count in patterns.most_common(10):
    print(f'{pattern}: {count}')

print(f'\n=== TOP FILES (by violation count) ===')
sorted_files = sorted(files.items(), key=lambda x: x[1], reverse=True)
for file, count in sorted_files[:20]:
    print(f'{count:3d} - {file}')
