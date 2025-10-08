#!/usr/bin/env python3
"""
Audit pipeline for potential bugs and issues
"""
import ast
import re
from pathlib import Path
from collections import defaultdict

class PipelineAuditor:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.issues = defaultdict(list)
        
    def audit_all(self):
        """Run all audit checks"""
        print("="*70)
        print("PIPELINE BUG AUDIT")
        print("="*70)
        print()
        
        self.check_null_handling()
        self.check_db_writes()
        self.check_error_handling()
        self.check_placeholder_code()
        self.check_model_loading()
        
        self.print_report()
    
    def check_null_handling(self):
        """Check for missing null/None checks"""
        print("🔍 Checking for missing null handling...")
        
        steps_dir = self.project_root / "steps"
        for py_file in steps_dir.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Look for dict access without .get()
            dangerous_patterns = [
                (r'\[[\'\"](\w+)[\'\"]\]', "Direct dict access"),
                (r'\.(\w+)\s*\(', "Method call without null check"),
            ]
            
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Check for direct dict access
                if '[' in line and 'get(' not in line:
                    if re.search(r'result\[|data\[|meta\[|config\[', line):
                        self.issues['null_handling'].append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'line': i,
                            'code': line.strip(),
                            'issue': 'Potential KeyError - use .get() with default'
                        })
    
    def check_db_writes(self):
        """Check if all steps write to database"""
        print("🔍 Checking database writes...")
        
        steps_dir = self.project_root / "steps"
        for py_file in steps_dir.rglob("*.py"):
            if py_file.name.startswith('_'):
                continue
                
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if step has database write
            has_db_import = 'memory' in content.lower() or 'database' in content.lower()
            has_db_write = 'insert' in content or 'save' in content or 'write' in content
            
            if not has_db_write:
                self.issues['missing_db_writes'].append({
                    'file': str(py_file.relative_to(self.project_root)),
                    'issue': 'No apparent database write operation'
                })
    
    def check_error_handling(self):
        """Check for missing try/except blocks"""
        print("🔍 Checking error handling...")
        
        steps_dir = self.project_root / "steps"
        for py_file in steps_dir.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            try:
                tree = ast.parse(content)
                
                # Find functions without try/except
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith('_'):
                            continue
                        
                        has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
                        
                        if not has_try:
                            self.issues['missing_error_handling'].append({
                                'file': str(py_file.relative_to(self.project_root)),
                                'function': node.name,
                                'line': node.lineno,
                                'issue': 'Function lacks try/except error handling'
                            })
            except SyntaxError:
                self.issues['syntax_errors'].append({
                    'file': str(py_file.relative_to(self.project_root)),
                    'issue': 'File has syntax errors'
                })
    
    def check_placeholder_code(self):
        """Look for placeholder/scaffold code"""
        print("🔍 Checking for placeholder code...")
        
        patterns = [
            'TODO',
            'FIXME',
            'XXX',
            'HACK',
            'pass  # implement',
            'NotImplemented',
            'raise NotImplementedError',
            'placeholder',
            'mock_',
            'dummy_',
        ]
        
        for py_file in self.project_root.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                for pattern in patterns:
                    if pattern.lower() in line.lower():
                        self.issues['placeholders'].append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'line': i,
                            'code': line.strip(),
                            'pattern': pattern
                        })
    
    def check_model_loading(self):
        """Check model loading patterns"""
        print("🔍 Checking model loading...")
        
        for py_file in self.project_root.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for hardcoded model paths
            if 'model_path' in content or 'MODEL_PATH' in content:
                if '/models/' in content or 'C:' in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if 'model' in line.lower() and ('/' in line or 'C:' in line):
                            self.issues['hardcoded_paths'].append({
                                'file': str(py_file.relative_to(self.project_root)),
                                'line': i,
                                'code': line.strip(),
                                'issue': 'Hardcoded path - should use config'
                            })
    
    def print_report(self):
        """Print audit report"""
        print()
        print("="*70)
        print("AUDIT RESULTS")
        print("="*70)
        print()
        
        if not any(self.issues.values()):
            print("✅ No issues found!")
            return
        
        for category, items in self.issues.items():
            if not items:
                continue
            
            print(f"\n{'='*70}")
            print(f"⚠️  {category.upper().replace('_', ' ')} ({len(items)} issues)")
            print(f"{'='*70}\n")
            
            for issue in items[:10]:  # Show first 10
                print(f"File: {issue['file']}")
                if 'line' in issue:
                    print(f"Line: {issue['line']}")
                if 'function' in issue:
                    print(f"Function: {issue['function']}")
                if 'code' in issue:
                    print(f"Code: {issue['code'][:80]}")
                print(f"Issue: {issue['issue']}")
                print()
            
            if len(items) > 10:
                print(f"... and {len(items) - 10} more\n")

if __name__ == "__main__":
    auditor = PipelineAuditor("L:/zenml_project")
    auditor.audit_all()
