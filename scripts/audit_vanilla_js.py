#!/usr/bin/env python3
"""
Audit script to detect vanilla JavaScript patterns in the codebase.

Scans .html and .js files for patterns like:
- addEventListener()
- document.querySelector()
- fetch()
- innerHTML/textContent manipulation
- Manual DOM manipulation

Usage:
    python scripts/audit_vanilla_js.py [--strict] [--format json|text]
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict


# Patterns to detect vanilla JS usage
VANILLA_PATTERNS = {
    'addEventListener': {
        'pattern': r'\.addEventListener\s*\(',
        'severity': 'error',
        'description': 'Direct event binding (vanilla JS)',
        'fix': 'Use htmx event attributes (@click, @submit, etc.) or hx-* attributes'
    },
    'querySelector': {
        'pattern': r'(document|element)\.querySelector(All)?\s*\(',
        'severity': 'error',
        'description': 'DOM selection with querySelector',
        'fix': 'Use htmx targeting or Alpine.js x-ref'
    },
    'getElementById': {
        'pattern': r'document\.getElementById\s*\(',
        'severity': 'error',
        'description': 'DOM selection with getElementById',
        'fix': 'Use htmx targeting or Alpine.js x-ref'
    },
    'getElementsBy': {
        'pattern': r'document\.getElementsBy(ClassName|TagName)\s*\(',
        'severity': 'error',
        'description': 'DOM selection with getElementsBy*',
        'fix': 'Use htmx targeting or Alpine.js x-ref'
    },
    'innerHTML': {
        'pattern': r'\.innerHTML\s*=',
        'severity': 'error',
        'description': 'Manual innerHTML assignment',
        'fix': 'Use htmx for server-driven updates or Alpine.js x-html'
    },
    'textContent': {
        'pattern': r'\.textContent\s*=',
        'severity': 'error',
        'description': 'Manual textContent assignment',
        'fix': 'Use Alpine.js x-text or server-driven updates'
    },
    'fetch': {
        'pattern': r'fetch\s*\(',
        'severity': 'error',
        'description': 'Direct fetch calls (vanilla JS HTTP)',
        'fix': 'Use htmx hx-get, hx-post, etc.'
    },
    'XMLHttpRequest': {
        'pattern': r'XMLHttpRequest|new\s+XMLHttpRequest',
        'severity': 'error',
        'description': 'XMLHttpRequest usage',
        'fix': 'Use htmx for HTTP requests'
    },
    'setTimeout': {
        'pattern': r'setTimeout\s*\(',
        'severity': 'warning',
        'description': 'setTimeout usage (may need htmx polling)',
        'fix': 'Consider htmx polling or Alpine.js reactivity'
    },
    'setInterval': {
        'pattern': r'setInterval\s*\(',
        'severity': 'warning',
        'description': 'setInterval usage',
        'fix': 'Use htmx polling or Alpine.js with watchers'
    },
    'classList': {
        'pattern': r'\.classList\.(add|remove|toggle)',
        'severity': 'warning',
        'description': 'Class manipulation (consider Alpine.js)',
        'fix': 'Use Alpine.js :class binding for reactive styling'
    },
    'style_assignment': {
        'pattern': r'\.style\.\w+\s*=',
        'severity': 'warning',
        'description': 'Direct style manipulation',
        'fix': 'Use Alpine.js :style binding or Tailwind classes'
    },
    'onclick_attr': {
        'pattern': r'onclick\s*=',
        'severity': 'error',
        'description': 'Inline onclick handler',
        'fix': 'Use htmx attributes (hx-get, hx-post, etc.) or Alpine.js @click'
    },
    'onchange_attr': {
        'pattern': r'onchange\s*=',
        'severity': 'error',
        'description': 'Inline onchange handler',
        'fix': 'Use Alpine.js @change or hx-trigger="change"'
    },
    'onsubmit_attr': {
        'pattern': r'onsubmit\s*=',
        'severity': 'error',
        'description': 'Inline onsubmit handler',
        'fix': 'Use hx-post or hx-put on form'
    },
}

# Directories/files to skip
SKIP_PATTERNS = [
    '.venv',
    'node_modules',
    '__pycache__',
    '.git',
    'migrations',
    'staticfiles',
    '.min.js',
    'vendor',
    'lib/',
]


def should_skip(path: str) -> bool:
    """Check if file should be skipped."""
    for pattern in SKIP_PATTERNS:
        if pattern in path.replace('\\', '/'):
            return True
    return False


def scan_file(filepath: str) -> List[Dict]:
    """Scan a single file for vanilla JS patterns."""
    violations = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception as e:
        return [{
            'file': filepath,
            'line': 0,
            'pattern': 'read_error',
            'severity': 'error',
            'message': f'Failed to read file: {e}'
        }]
    
    for pattern_name, pattern_info in VANILLA_PATTERNS.items():
        pattern = pattern_info['pattern']
        try:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
        except re.error:
            continue
        
        for match in matches:
            # Calculate line number
            line_num = content[:match.start()].count('\n') + 1
            line_content = lines[line_num - 1].strip() if line_num <= len(lines) else ''
            
            violations.append({
                'file': filepath,
                'line': line_num,
                'column': match.start() - content.rfind('\n', 0, match.start()),
                'pattern': pattern_name,
                'severity': pattern_info['severity'],
                'description': pattern_info['description'],
                'fix': pattern_info['fix'],
                'code': line_content[:80],
            })
    
    return violations


def scan_directory(root: str) -> List[Dict]:
    """Recursively scan directory for vanilla JS patterns."""
    all_violations = []
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter directories
        dirnames[:] = [d for d in dirnames if not should_skip(os.path.join(dirpath, d))]
        
        for filename in filenames:
            if filename.endswith(('.html', '.js', '.jsx')):
                filepath = os.path.join(dirpath, filename)
                
                if should_skip(filepath):
                    continue
                
                violations = scan_file(filepath)
                all_violations.extend(violations)
    
    return all_violations


def format_text_output(violations: List[Dict], group_by_severity: bool = False) -> str:
    """Format violations as human-readable text."""
    if not violations:
        return "✅ No vanilla JS violations found!\n"
    
    output = []
    
    if group_by_severity:
        by_severity = defaultdict(list)
        for v in violations:
            by_severity[v['severity']].append(v)
        
        for severity in ['error', 'warning']:
            if severity in by_severity:
                output.append(f"\n{'ERROR' if severity == 'error' else 'WARNING'} ({len(by_severity[severity])} violations):")
                output.append("=" * 70)
                
                for v in by_severity[severity]:
                    output.append(f"\n  {v['file']}:{v['line']}:{v['column']}")
                    output.append(f"    Pattern: {v['pattern']}")
                    output.append(f"    {v['description']}")
                    output.append(f"    Code: {v['code']}")
                    output.append(f"    Fix: {v['fix']}")
    else:
        output.append("\nVanilla JS Violations Found:")
        output.append("=" * 70)
        
        for v in violations:
            output.append(f"\n  {v['file']}:{v['line']}:{v['column']}")
            output.append(f"    [{v['severity'].upper()}] {v['description']}")
            output.append(f"    Pattern: {v['pattern']}")
            output.append(f"    Code: {v['code']}")
            output.append(f"    Fix: {v['fix']}")
    
    # Summary
    errors = sum(1 for v in violations if v['severity'] == 'error')
    warnings = sum(1 for v in violations if v['severity'] == 'warning')
    
    output.append("\n" + "=" * 70)
    output.append(f"Summary: {errors} errors, {warnings} warnings ({len(violations)} total)")
    
    return "\n".join(output)


def format_json_output(violations: List[Dict]) -> str:
    """Format violations as JSON."""
    return json.dumps(violations, indent=2)


def main():
    import argparse
    import sys
    import io
    
    # Force UTF-8 output
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    parser = argparse.ArgumentParser(description='Audit codebase for vanilla JS patterns')
    parser.add_argument('--strict', action='store_true', help='Fail on warnings (exit code 1)')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--root', default='.', help='Root directory to scan')
    
    args = parser.parse_args()
    
    print(f"Scanning {args.root} for vanilla JS patterns...\n", file=sys.stderr)
    
    violations = scan_directory(args.root)
    
    if args.format == 'json':
        output = format_json_output(violations)
    else:
        output = format_text_output(violations, group_by_severity=True)
    
    print(output, file=sys.stdout)
    
    # Exit code
    if violations:
        errors = sum(1 for v in violations if v['severity'] == 'error')
        warnings = sum(1 for v in violations if v['severity'] == 'warning')
        
        if errors > 0:
            sys.exit(2)  # Hard failure on errors
        elif args.strict and warnings > 0:
            sys.exit(1)  # Soft failure on warnings (if strict)
        else:
            sys.exit(0)  # Success
    
    sys.exit(0)


if __name__ == '__main__':
    main()
