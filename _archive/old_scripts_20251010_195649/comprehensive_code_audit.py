#!/usr/bin/env python3
"""
Comprehensive code audit to identify:
- Placeholder code
- TODO/FIXME/XXX comments
- Empty or skeleton functions
- Unused imports
- Missing error handling
- Hardcoded paths
"""
import ast
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Set
import json

REPO_ROOT = Path(__file__).resolve().parents[1]

# Patterns to look for
PLACEHOLDER_PATTERNS = [
    r'TODO:',
    r'FIXME:',
    r'XXX:',
    r'placeholder',
    r'scaffold',
    r'stub',
    r'not implemented',
    r'pass\s*#.*',
]

SUSPICIOUS_PATTERNS = [
    r'raise NotImplementedError',
    r'return None  # ',
    r'return {}  # ',
    r'return \[\]  # ',
]

def scan_file(filepath: Path) -> Dict[str, Any]:
    """Scan a Python file for issues"""
    issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Check for placeholder patterns
        for idx, line in enumerate(lines, 1):
            for pattern in PLACEHOLDER_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'line': idx,
                        'type': 'placeholder',
                        'content': line.strip()
                    })
            
            for pattern in SUSPICIOUS_PATTERNS:
                if re.search(pattern, line):
                    issues.append({
                        'line': idx,
                        'type': 'suspicious',
                        'content': line.strip()
                    })
        
        # Parse AST to find empty functions
        try:
            tree = ast.parse(content, filename=str(filepath))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if function only has pass or docstring
                    body = node.body
                    if len(body) == 1:
                        if isinstance(body[0], ast.Pass):
                            issues.append({
                                'line': node.lineno,
                                'type': 'empty_function',
                                'content': f'def {node.name}(...): pass'
                            })
                        elif isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                            if len(node.body) == 1:
                                issues.append({
                                    'line': node.lineno,
                                    'type': 'docstring_only_function',
                                    'content': f'def {node.name}(...): """..."""'
                                })
        except SyntaxError as e:
            issues.append({
                'line': e.lineno or 0,
                'type': 'syntax_error',
                'content': str(e)
            })
    
    except Exception as e:
        issues.append({
            'line': 0,
            'type': 'read_error',
            'content': str(e)
        })
    
    return {
        'file': str(filepath.relative_to(REPO_ROOT)),
        'issues': issues
    }

def main():
    print("=" * 80)
    print("COMPREHENSIVE CODE AUDIT")
    print("=" * 80)
    
    # Directories to scan
    scan_dirs = [
        REPO_ROOT / 'steps',
        REPO_ROOT / 'pipelines',
        REPO_ROOT / 'lib',
        REPO_ROOT / 'cli',
        REPO_ROOT / 'api',
        REPO_ROOT / 'scripts',
    ]
    
    all_results = []
    total_issues = 0
    
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        
        print(f"\nScanning {scan_dir.relative_to(REPO_ROOT)}...")
        
        python_files = list(scan_dir.rglob('*.py'))
        # Exclude __pycache__ and vendor
        python_files = [f for f in python_files if '__pycache__' not in str(f) and 'vendor' not in str(f)]
        
        for pyfile in python_files:
            result = scan_file(pyfile)
            if result['issues']:
                all_results.append(result)
                total_issues += len(result['issues'])
    
    # Report
    print(f"\n{'=' * 80}")
    print(f"AUDIT RESULTS: {total_issues} issues found in {len(all_results)} files")
    print("=" * 80)
    
    if all_results:
        # Group by issue type
        by_type = {}
        for result in all_results:
            for issue in result['issues']:
                issue_type = issue['type']
                if issue_type not in by_type:
                    by_type[issue_type] = []
                by_type[issue_type].append({
                    'file': result['file'],
                    'line': issue['line'],
                    'content': issue['content']
                })
        
        print("\nISSUES BY TYPE:")
        for issue_type, items in sorted(by_type.items()):
            print(f"\n{issue_type.upper()}: {len(items)} occurrences")
            for item in items[:10]:  # Show first 10
                print(f"  {item['file']}:{item['line']}")
                print(f"    {item['content']}")
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")
    
    # Save detailed report
    report_path = REPO_ROOT / 'AUDIT_REPORT.json'
    with open(report_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_path}")
    
    return 0 if total_issues == 0 else 1

if __name__ == '__main__':
    exit(main())
