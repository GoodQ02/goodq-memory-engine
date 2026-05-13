"""
[SEARCH] Comprehensive Exception Handler Audit for GoodQ

This script finds ALL exception handling patterns that might hide errors:
1. Bare except: clauses
2. except: pass patterns
3. Exception caught but not logged
4. Functions returning None/empty dict without explanation
5. Try/except blocks where error variable is unused
"""

import os
import re
from pathlib import Path
from collections import defaultdict


class ExceptionAuditor:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.findings = defaultdict(list)
        
    def audit_file(self, filepath: Path):
        """Audit a single Python file for exception handling issues."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[ERROR] Can't read {filepath}: {e}")
            return
        
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            
            # Pattern 1: Bare except:
            if re.match(r'^except\s*:', stripped):
                self.findings['bare_except'].append({
                    'file': str(filepath),
                    'line': i,
                    'code': line.rstrip()
                })
            
            # Pattern 2: except Exception: pass (or similar)
            if re.match(r'^except\s+\w+.*:\s*$', stripped):
                # Check if next line is just pass, return None, continue, etc.
                if i < len(lines):
                    next_line = lines[i].strip()
                    if next_line in ('pass', 'return', 'return None', 'return {}', 'continue'):
                        self.findings['silent_handler'].append({
                            'file': str(filepath),
                            'line': i,
                            'code': line.rstrip(),
                            'action': next_line
                        })
            
            # Pattern 3: Exception variable defined but never used
            match = re.match(r'^except\s+(\w+)\s+as\s+(\w+)\s*:', stripped)
            if match and i < len(lines) - 3:
                exc_var = match.group(2)
                # Check next 5 lines for usage
                next_block = ''.join(lines[i:min(i+5, len(lines))])
                if exc_var not in next_block:
                    self.findings['unused_exception'].append({
                        'file': str(filepath),
                        'line': i,
                        'code': line.rstrip(),
                        'unused_var': exc_var
                    })
            
            # Pattern 4: Functions that return None/empty dict with no logging
            if re.match(r'^\s*def\s+\w+', stripped):
                func_name = re.search(r'def\s+(\w+)', stripped).group(1)
                # Look through function for returns
                func_lines = []
                indent_level = len(line) - len(line.lstrip())
                for j in range(i, min(i+50, len(lines))):
                    if j > i and lines[j].strip() and not lines[j].startswith(' ' * (indent_level + 1)):
                        break
                    func_lines.append(lines[j])
                
                func_body = ''.join(func_lines)
                # Check for return None or return {} without preceding print/log
                returns = re.finditer(r'return\s+(None|\{\})', func_body)
                for ret_match in returns:
                    # Check if there's a print/log statement nearby
                    before_return = func_body[:ret_match.start()].split('\n')[-3:]
                    has_log = any('print(' in l or 'log.' in l or 'logger.' in l for l in before_return)
                    if not has_log:
                        self.findings['silent_return'].append({
                            'file': str(filepath),
                            'line': i,
                            'function': func_name,
                            'returns': ret_match.group(1)
                        })
            
            # Pattern 5: Status = "ok" when it should be conditional
            if '"ok"' in stripped and ('status' in stripped or 'Status' in stripped):
                # Check if it's a conditional or always "ok"
                if '=' in stripped and 'if' not in stripped and 'else' not in stripped:
                    # Check context - is this inside a try block?
                    for j in range(max(0, i-10), i):
                        if 'try:' in lines[j]:
                            self.findings['hardcoded_ok'].append({
                                'file': str(filepath),
                                'line': i,
                                'code': line.rstrip()
                            })
                            break
    
    def audit_all(self):
        """Audit all Python files in the directory."""
        python_files = list(self.base_path.rglob("*.py"))
        print(f"\n[SEARCH] Auditing {len(python_files)} Python files in {self.base_path}")
        print("="*70)
        
        for filepath in python_files:
            if '__pycache__' in str(filepath):
                continue
            self.audit_file(filepath)
        
        return self.findings
    
    def print_report(self):
        """Print a detailed report of findings."""
        print("\n" + "="*70)
        print("[STATS] EXCEPTION HANDLING AUDIT REPORT")
        print("="*70 + "\n")
        
        total_issues = sum(len(v) for v in self.findings.values())
        
        if total_issues == 0:
            print("[OK] No exception handling issues found!\n")
            return
        
        print(f"[WARN]  Found {total_issues} potential issues\n")
        
        # Report by category
        if self.findings['bare_except']:
            print(f"\n[SYMBOL] BARE EXCEPT CLAUSES ({len(self.findings['bare_except'])})")
            print("   Catches all exceptions including KeyboardInterrupt!")
            print("-"*70)
            for item in self.findings['bare_except'][:5]:  # Show first 5
                print(f"   {Path(item['file']).name}:{item['line']}")
                print(f"     {item['code']}")
            if len(self.findings['bare_except']) > 5:
                print(f"   ... and {len(self.findings['bare_except']) - 5} more")
        
        if self.findings['silent_handler']:
            print(f"\n[WARN]  SILENT EXCEPTION HANDLERS ({len(self.findings['silent_handler'])})")
            print("   Catches exceptions but doesn't log them")
            print("-"*70)
            for item in self.findings['silent_handler'][:5]:
                print(f"   {Path(item['file']).name}:{item['line']} → {item['action']}")
                print(f"     {item['code']}")
            if len(self.findings['silent_handler']) > 5:
                print(f"   ... and {len(self.findings['silent_handler']) - 5} more")
        
        if self.findings['unused_exception']:
            print(f"\n[SYMBOL] UNUSED EXCEPTION VARIABLES ({len(self.findings['unused_exception'])})")
            print("   Exception caught but never used or logged")
            print("-"*70)
            for item in self.findings['unused_exception'][:5]:
                print(f"   {Path(item['file']).name}:{item['line']} (variable: {item['unused_var']})")
                print(f"     {item['code']}")
            if len(self.findings['unused_exception']) > 5:
                print(f"   ... and {len(self.findings['unused_exception']) - 5} more")
        
        if self.findings['silent_return']:
            print(f"\n[SYMBOL] SILENT RETURNS ({len(self.findings['silent_return'])})")
            print("   Functions return None/empty without logging why")
            print("-"*70)
            for item in self.findings['silent_return'][:5]:
                print(f"   {Path(item['file']).name}:{item['line']} {item['function']}() → {item['returns']}")
            if len(self.findings['silent_return']) > 5:
                print(f"   ... and {len(self.findings['silent_return']) - 5} more")
        
        if self.findings['hardcoded_ok']:
            print(f"\n[OK] HARDCODED 'OK' STATUS ({len(self.findings['hardcoded_ok'])})")
            print("   Status set to 'ok' without validation")
            print("-"*70)
            for item in self.findings['hardcoded_ok'][:5]:
                print(f"   {Path(item['file']).name}:{item['line']}")
                print(f"     {item['code']}")
            if len(self.findings['hardcoded_ok']) > 5:
                print(f"   ... and {len(self.findings['hardcoded_ok']) - 5} more")
        
        print("\n" + "="*70)
        print("[TIP] RECOMMENDATIONS")
        print("="*70)
        print("1. Replace bare 'except:' with 'except Exception as e:'")
        print("2. Add logging: print(f'[ERROR] {func_name}: {str(e)}')")
        print("3. Use exception variables to provide context")
        print("4. Log before returning None/empty results")
        print("5. Make status conditional on actual success")
        print("\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit exception handling in Python code")
    default_path = Path(__file__).resolve().parents[1] / "steps"
    parser.add_argument('--path', default=str(default_path), help='Path to audit')
    parser.add_argument('--export', help='Export findings to JSON file')
    args = parser.parse_args()
    
    auditor = ExceptionAuditor(args.path)
    findings = auditor.audit_all()
    auditor.print_report()
    
    if args.export:
        import json
        output = {}
        for category, items in findings.items():
            output[category] = items
        
        with open(args.export, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"[SYMBOL] Findings exported to: {args.export}")


if __name__ == "__main__":
    main()
