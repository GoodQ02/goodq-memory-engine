#!/usr/bin/env python3
"""
Comprehensive Code Audit - Find all potential silent failures
Scans entire codebase for error-hiding patterns
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# Patterns that indicate potential silent failures
SILENT_FAILURE_PATTERNS = [
    # Catching exceptions without logging
    (r'except.*:\s*pass', 'Bare except with pass - swallows all errors'),
    (r'except\s+Exception.*:\s*pass', 'Generic exception with pass'),
    (r'except.*:\s*continue', 'Exception silently continues loop'),
    (r'except.*:\s*return\s+None', 'Exception returns None without logging'),
    (r'except.*:\s*return\s+\{\}', 'Exception returns empty dict without logging'),
    (r'except.*:\s*return\s+\[\]', 'Exception returns empty list without logging'),
    
    # Functions returning success without validation
    (r'return\s+True\s*$', 'Returns True without validation (could be premature)'),
    (r'return\s+"ok"\s*$', 'Returns "ok" string without validation'),
    (r'return\s+\{"status":\s*"ok"\}', 'Returns ok status without validation'),
    
    # Empty implementations
    (r'def\s+\w+\(.*\):\s*pass', 'Function stub (not implemented)'),
    (r'def\s+\w+\(.*\):\s*\.\.\.', 'Function ellipsis (not implemented)'),
    
    # Logging without raising
    (r'logger\.error\(.*\)\s*$\s*return', 'Logs error but continues (should raise?)'),
    
    # TODO/FIXME/HACK comments
    (r'#\s*(TODO|FIXME|HACK|XXX|BUG)', 'Code marked for fixing'),
]

# Patterns that suggest missing validation
VALIDATION_PATTERNS = [
    (r'def\s+(\w+)\(.*\).*:\s*return\s+\[\]', 'Returns empty list without try/except'),
    (r'def\s+(\w+)\(.*\).*:\s*return\s+\{\}', 'Returns empty dict without try/except'),
    (r'def\s+(\w+)\(.*\).*:\s*return\s+""', 'Returns empty string without try/except'),
]

def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single file for silent failure patterns"""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            for pattern, description in SILENT_FAILURE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append((i, line.strip(), description))
        
        return findings
    except Exception as e:
        print(f"⚠️  Error scanning {file_path}: {e}")
        return []

def scan_directory(root_dir: Path, exclude_patterns: List[str] = None) -> Dict[str, List]:
    """Scan all Python files in directory"""
    if exclude_patterns is None:
        exclude_patterns = ['__pycache__', '.git', 'venv', 'env', '.pytest_cache']
    
    results = defaultdict(list)
    
    python_files = [
        f for f in root_dir.rglob("*.py")
        if not any(exclude in str(f) for exclude in exclude_patterns)
    ]
    
    print(f"📁 Scanning {len(python_files)} Python files...")
    print()
    
    for file_path in python_files:
        findings = scan_file(file_path)
        if findings:
            results[str(file_path.relative_to(root_dir))] = findings
    
    return results

def generate_report(results: Dict[str, List], output_file: Path):
    """Generate detailed audit report"""
    
    # Count findings by type
    finding_counts = defaultdict(int)
    total_files = len(results)
    total_issues = sum(len(findings) for findings in results.values())
    
    for findings in results.values():
        for _, _, description in findings:
            finding_counts[description] += 1
    
    # Write report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# GoodQ Codebase Audit Report\n")
        f.write(f"**Generated**: {Path(__file__).stat().st_mtime}\n")
        f.write(f"**Files scanned**: {total_files}\n")
        f.write(f"**Issues found**: {total_issues}\n")
        f.write("\n")
        f.write("---\n\n")
        
        f.write("## Summary by Issue Type\n\n")
        for description, count in sorted(finding_counts.items(), key=lambda x: -x[1]):
            f.write(f"- **{description}**: {count} occurrences\n")
        f.write("\n")
        f.write("---\n\n")
        
        f.write("## Detailed Findings\n\n")
        
        for file_path in sorted(results.keys()):
            findings = results[file_path]
            f.write(f"### `{file_path}`\n")
            f.write(f"**Issues found**: {len(findings)}\n\n")
            
            for line_num, line, description in findings:
                f.write(f"**Line {line_num}**: {description}\n")
                f.write(f"```python\n{line}\n```\n\n")
            
            f.write("---\n\n")
    
    return total_issues, total_files

def print_summary(results: Dict[str, List]):
    """Print summary to console"""
    
    finding_counts = defaultdict(int)
    total_files = len(results)
    total_issues = sum(len(findings) for findings in results.values())
    
    for findings in results.values():
        for _, _, description in findings:
            finding_counts[description] += 1
    
    print("=" * 70)
    print("🔍 AUDIT SUMMARY")
    print("=" * 70)
    print()
    print(f"📂 Files with issues: {total_files}")
    print(f"⚠️  Total issues found: {total_issues}")
    print()
    print("Issue Breakdown:")
    for description, count in sorted(finding_counts.items(), key=lambda x: -x[1]):
        print(f"   • {description}: {count}")
    print()
    print("=" * 70)
    print()
    
    # Show top offenders
    if results:
        print("Top 10 Files with Most Issues:")
        sorted_files = sorted(results.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        for file_path, findings in sorted_files:
            print(f"   • {file_path}: {len(findings)} issues")
        print()

def main():
    print("━" * 70)
    print("🎯 GoodQ COMPREHENSIVE CODE AUDIT")
    print("━" * 70)
    print()
    
    root_dir = Path("L:/goodq4all")
    
    # Scan codebase
    results = scan_directory(root_dir)
    
    # Print summary
    print_summary(results)
    
    # Generate report
    report_file = root_dir / "docs" / "AUDIT_REPORT.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    total_issues, total_files = generate_report(results, report_file)
    
    print(f"📄 Full report saved to: {report_file}")
    print()
    
    if total_issues > 0:
        print("⚠️  AUDIT FOUND ISSUES - Review report and fix silent failures")
    else:
        print("✅ AUDIT CLEAN - No obvious silent failures detected")
    
    print()

if __name__ == "__main__":
    main()
