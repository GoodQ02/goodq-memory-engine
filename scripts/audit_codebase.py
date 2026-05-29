#!/usr/bin/env python3
"""Comprehensive code audit to find silent failures and suspicious patterns

MISSION: CODE AUDIT
   _____ ____  ____  ____   ___
  / ____|  _ \|  _ \|  _ \ / _ \
 | |  __| | | | | | | |_) | | | |
 | | |_ | | | | | | |  __/| | | |
 | |__| | |_| | |_| | |   | |_| |
  \_____|____/|____/|_|    \___/

Identifies:
1. Silent exception handling (except: pass)
2. Suspicious return values in except blocks
3. Functions that always return success
4. Missing error logging
5. Placeholder/scaffold code
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


class CodeAuditor(ast.NodeVisitor):
    """AST visitor to find suspicious patterns"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.issues: List[Dict[str, Any]] = []
        self.current_function: Optional[str] = None
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_Try(self, node: ast.Try):
        """Check try-except blocks for silent failures"""
        for handler in node.handlers:
            # Check for bare except: pass
            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                self.issues.append({
                    "type": "silent_exception",
                    "severity": "high",
                    "line": handler.lineno,
                    "function": self.current_function,
                    "description": "Bare except with pass - silently ignores all errors",
                    "pattern": "except: pass"
                })
            
            # Check for except with suspicious returns
            elif len(handler.body) == 1 and isinstance(handler.body[0], ast.Return):
                ret_value = handler.body[0].value
                if ret_value is None:
                    pattern = "except: return None"
                elif isinstance(ret_value, ast.Constant):
                    if ret_value.value == {}:
                        pattern = "except: return {}"
                    elif ret_value.value == []:
                        pattern = "except: return []"
                    elif ret_value.value == "":
                        pattern = "except: return ''"
                    elif ret_value.value == 0:
                        pattern = "except: return 0"
                    else:
                        pattern = f"except: return {ret_value.value}"
                elif isinstance(ret_value, ast.Dict) and not ret_value.keys:
                    pattern = "except: return {}"
                elif isinstance(ret_value, ast.List) and not ret_value.elts:
                    pattern = "except: return []"
                else:
                    pattern = "except: return <value>"
                
                self.issues.append({
                    "type": "silent_return",
                    "severity": "medium",
                    "line": handler.lineno,
                    "function": self.current_function,
                    "description": "Exception caught but returns value without logging",
                    "pattern": pattern
                })
            
            # Check for except with no exception type (catches everything)
            if handler.type is None:
                self.issues.append({
                    "type": "bare_except",
                    "severity": "medium",
                    "line": handler.lineno,
                    "function": self.current_function,
                    "description": "Bare except catches all exceptions including KeyboardInterrupt",
                    "pattern": "except:"
                })
        
        self.generic_visit(node)


def scan_for_placeholders(filepath: Path) -> List[Dict[str, Any]]:
    """Scan for placeholder code patterns"""
    issues = []
    content = filepath.read_text(encoding='utf-8')
    
    placeholder_patterns = [
        (r'TODO', 'TODO comment'),
        (r'FIXME', 'FIXME comment'),
        (r'XXX', 'XXX comment'),
        (r'HACK', 'HACK comment'),
        (r'NotImplemented', 'Not implemented'),
        (r'raise NotImplementedError', 'Not implemented'),
        (r'pass\s*#.*stub', 'Stub implementation'),
        (r'return\s+None\s*#.*placeholder', 'Placeholder return'),
    ]
    
    for pattern, description in placeholder_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            line_num = content[:match.start()].count('\n') + 1
            issues.append({
                "type": "placeholder",
                "severity": "low",
                "line": line_num,
                "description": description,
                "pattern": match.group(0)
            })
    
    return issues


def scan_for_suspicious_logging(filepath: Path) -> List[Dict[str, Any]]:
    """Scan for missing error logging in except blocks"""
    issues = []
    content = filepath.read_text(encoding='utf-8')
    
    # Find except blocks that don't log errors
    except_blocks = re.finditer(r'except.*?:\s*\n(.*?)(?=\n(?:\s{0,4}\S|$))', content, re.DOTALL)
    
    for match in except_blocks:
        block_content = match.group(1)
        line_num = content[:match.start()].count('\n') + 1
        
        # Check if there's any logging
        has_logging = any(keyword in block_content for keyword in ['logger.', 'print(', 'log(', 'typer.echo'])
        
        if not has_logging and 'pass' not in block_content:
            issues.append({
                "type": "no_error_logging",
                "severity": "medium",
                "line": line_num,
                "description": "Exception handled without logging",
                "pattern": "except without logging"
            })
    
    return issues


def audit_file(filepath: Path) -> Dict[str, Any]:
    """Audit a single Python file"""
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content, filename=str(filepath))
        
        auditor = CodeAuditor(filepath)
        auditor.visit(tree)
        
        placeholder_issues = scan_for_placeholders(filepath)
        logging_issues = scan_for_suspicious_logging(filepath)
        
        all_issues = auditor.issues + placeholder_issues + logging_issues
        
        return {
            "file": str(filepath.relative_to(Path.cwd())),
            "issues": all_issues,
            "issue_count": len(all_issues),
            "status": "audited"
        }
    
    except SyntaxError as e:
        return {
            "file": str(filepath.relative_to(Path.cwd())),
            "issues": [],
            "issue_count": 0,
            "status": "syntax_error",
            "error": str(e)
        }
    except Exception as e:
        return {
            "file": str(filepath.relative_to(Path.cwd())),
            "issues": [],
            "issue_count": 0,
            "status": "error",
            "error": str(e)
        }


def main():
    """Run comprehensive code audit"""
    print("=" * 70)
    print("MISSION: CODE AUDIT")
    print("=" * 70)
    print("\n[BRIEFING] Scanning codebase for silent failures and suspicious patterns\n")
    
    # Scan directories
    repo_root = Path(__file__).parent.parent
    scan_dirs = [
        repo_root / "steps",
        repo_root / "cli",
        repo_root / "lib",
    ]
    
    all_results = []
    total_issues = 0
    high_severity = 0
    medium_severity = 0
    
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        
        print(f"\n[SCANNING] {scan_dir}")
        
        for py_file in scan_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            result = audit_file(py_file)
            all_results.append(result)
            total_issues += result["issue_count"]
            
            for issue in result.get("issues", []):
                if issue.get("severity") == "high":
                    high_severity += 1
                elif issue.get("severity") == "medium":
                    medium_severity += 1
    
    # Report findings
    print("\n" + "=" * 70)
    print("[INTELLIGENCE REPORT]")
    print("=" * 70)
    
    print(f"\nFiles Audited: {len(all_results)}")
    print(f"Total Issues: {total_issues}")
    print(f"  High Severity: {high_severity}")
    print(f"  Medium Severity: {medium_severity}")
    print(f"  Low Severity: {total_issues - high_severity - medium_severity}")
    
    # Show high severity issues
    if high_severity > 0:
        print("\n[CRITICAL FINDINGS] High Severity Issues:")
        print("-" * 70)
        for result in all_results:
            high_issues = [i for i in result.get("issues", []) if i.get("severity") == "high"]
            if high_issues:
                print(f"\n{result['file']}:")
                for issue in high_issues:
                    func = f" in {issue['function']}()" if issue.get('function') else ""
                    print(f"  Line {issue['line']}{func}: {issue['description']}")
                    print(f"    Pattern: {issue['pattern']}")
    
    # Show medium severity issues
    if medium_severity > 0:
        print("\n[WARNING] Medium Severity Issues:")
        print("-" * 70)
        for result in all_results:
            med_issues = [i for i in result.get("issues", []) if i.get("severity") == "medium"]
            if med_issues and len(med_issues) <= 5:  # Only show files with few issues
                print(f"\n{result['file']}:")
                for issue in med_issues:
                    func = f" in {issue.get('function', 'unknown')}()" if issue.get('function') else ""
                    print(f"  Line {issue['line']}{func}: {issue['description']}")
    
    # Summary
    print("\n" + "=" * 70)
    if high_severity == 0:
        print("[MISSION STATUS] No critical silent failures detected")
    else:
        print(f"[MISSION STATUS] Found {high_severity} critical issues requiring attention")
    print("=" * 70)
    
    print("\n[Q] \"The codebase audit is complete, Agent.\"")
    print("    \"Address critical findings before proceeding with mission objectives.\"")


if __name__ == "__main__":
    main()
