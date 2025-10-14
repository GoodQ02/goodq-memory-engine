"""
🔧 Comprehensive Silent Failure Fixer

Automatically fixes the 123 exception handling issues found by audit_all_exceptions.py
This is the nuclear option - fixes ALL silent failures comprehensively.
"""

import os
import re
from pathlib import Path
from collections import defaultdict


class SilentFailureFixer:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.fixes_applied = defaultdict(list)
        self.backup_dir = Path("L:/goodq4all/data/backups/pre_silent_failure_fix")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def backup_file(self, filepath: Path):
        """Create backup before modifying."""
        rel_path = filepath.relative_to(self.base_path)
        backup_path = self.backup_dir / rel_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        import shutil
        shutil.copy2(filepath, backup_path)
        
    def fix_file(self, filepath: Path) -> int:
        """Fix all silent failures in a file. Returns number of fixes applied."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines(keepends=True)
        except Exception as e:
            print(f"[ERROR] Can't read {filepath}: {e}")
            return 0
        
        original_content = content
        fixes_count = 0
        modified_lines = list(lines)
        
        i = 0
        while i < len(modified_lines):
            line = modified_lines[i]
            stripped = line.strip()
            
            # Fix 1: Bare except: → except Exception as e: with logging
            if re.match(r'^\s*except\s*:\s*$', stripped):
                indent = len(line) - len(line.lstrip())
                indent_str = ' ' * indent
                
                # Replace line
                modified_lines[i] = f"{indent_str}except Exception as e:\n"
                
                # Add logging on next line
                if i + 1 < len(modified_lines) and modified_lines[i+1].strip() == 'pass':
                    modified_lines[i+1] = (
                        f"{indent_str}    print(f'[ERROR] Exception in {filepath.name} line {i+1}: {{str(e)}}')\n"
                        f"{indent_str}    pass\n"
                    )
                else:
                    # Insert logging before whatever comes next
                    modified_lines.insert(i+1, 
                        f"{indent_str}    print(f'[ERROR] Exception in {filepath.name} line {i+1}: {{str(e)}}')\n"
                    )
                    i += 1
                
                fixes_count += 1
                self.fixes_applied['bare_except'].append(f"{filepath.name}:{i+1}")
                
            # Fix 2: except Exception: pass → add logging
            elif re.match(r'^\s*except\s+\w+.*:\s*$', stripped):
                # Check if exception variable exists
                if ' as ' not in stripped:
                    # Add 'as e'
                    modified_lines[i] = re.sub(
                        r'(except\s+\w+)(.*:)',
                        r'\1 as e\2',
                        line
                    )
                    fixes_count += 1
                
                # Check if next line is just pass/return/continue
                if i + 1 < len(modified_lines):
                    next_stripped = modified_lines[i+1].strip()
                    if next_stripped in ('pass', 'return', 'return None', 'return {}', 'continue'):
                        indent = len(modified_lines[i+1]) - len(modified_lines[i+1].lstrip())
                        indent_str = ' ' * indent
                        
                        # Get exception variable name
                        exc_var_match = re.search(r'as\s+(\w+)', modified_lines[i])
                        exc_var = exc_var_match.group(1) if exc_var_match else 'e'
                        
                        # Insert logging before pass/return/continue
                        log_line = f"{indent_str}print(f'[ERROR] Exception in {filepath.name} line {i+1}: {{str({exc_var})}}')\n"
                        modified_lines.insert(i+1, log_line)
                        
                        fixes_count += 1
                        self.fixes_applied['silent_handler'].append(f"{filepath.name}:{i+1}")
                        i += 1  # Skip the inserted line
            
            # Fix 3: Functions returning None without logging
            elif re.match(r'^\s*def\s+\w+', stripped):
                func_match = re.search(r'def\s+(\w+)', stripped)
                if func_match:
                    func_name = func_match.group(1)
                    
                    # Look for return None/return {} in function body
                    func_indent = len(line) - len(line.lstrip())
                    j = i + 1
                    while j < len(modified_lines):
                        if modified_lines[j].strip() and not modified_lines[j].startswith(' ' * (func_indent + 1)):
                            break
                        
                        # Check for return None or return {}
                        if re.match(r'^\s*return\s+(None|\{\})\s*$', modified_lines[j]):
                            # Check if there's logging in previous 2 lines
                            has_log = False
                            for k in range(max(i, j-3), j):
                                if 'print(' in modified_lines[k] or 'log' in modified_lines[k].lower():
                                    has_log = True
                                    break
                            
                            if not has_log:
                                ret_indent = len(modified_lines[j]) - len(modified_lines[j].lstrip())
                                log_line = ' ' * ret_indent + f"print(f'[WARN] {func_name} returning {modified_lines[j].strip().split()[1]}')\n"
                                modified_lines.insert(j, log_line)
                                
                                fixes_count += 1
                                self.fixes_applied['silent_return'].append(f"{filepath.name}:{j+1} {func_name}()")
                                j += 1  # Skip inserted line
                        
                        j += 1
            
            i += 1
        
        # Write back if changes were made
        if fixes_count > 0:
            self.backup_file(filepath)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(modified_lines)
        
        return fixes_count
    
    def fix_all(self, dry_run=False):
        """Fix all Python files in the directory."""
        python_files = list(self.base_path.rglob("*.py"))
        python_files = [f for f in python_files if '__pycache__' not in str(f)]
        
        print(f"\n🔧 {'[DRY RUN] ' if dry_run else ''}Fixing silent failures in {len(python_files)} files")
        print("="*70)
        
        total_fixes = 0
        files_modified = 0
        
        for filepath in python_files:
            if dry_run:
                print(f"Would scan: {filepath.name}")
            else:
                fixes = self.fix_file(filepath)
                if fixes > 0:
                    total_fixes += fixes
                    files_modified += 1
                    print(f"✅ {filepath.name}: {fixes} fixes applied")
        
        print("\n" + "="*70)
        print(f"📊 RESULTS")
        print("="*70)
        print(f"Files modified: {files_modified}")
        print(f"Total fixes: {total_fixes}")
        
        if self.fixes_applied:
            print("\nBy category:")
            for category, items in self.fixes_applied.items():
                print(f"  {category}: {len(items)}")
        
        if not dry_run and files_modified > 0:
            print(f"\n💾 Backups saved to: {self.backup_dir}")
        
        print("\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix all silent failures comprehensively")
    parser.add_argument('--path', default='L:\\goodq4all\\steps', help='Path to fix')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("="*70)
    print("🔧 GoodQ Comprehensive Silent Failure Fixer")
    print("="*70)
    print()
    print("This will automatically fix:")
    print("  • Bare except: clauses")
    print("  • Silent exception handlers (except: pass)")
    print("  • Functions returning None without logging")
    print("  • Unused exception variables")
    print()
    
    if not args.dry_run and not args.yes:
        try:
            response = input("Apply fixes to ALL files? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                return
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
    
    fixer = SilentFailureFixer(args.path)
    fixer.fix_all(dry_run=args.dry_run)
    
    print("="*70)
    print("✅ COMPLETE")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Run: python L:\\goodq4all\\scripts\\validate_results.py")
    print("2. Test with: python L:\\goodq4all\\scripts\\audit_all_exceptions.py")
    print("3. Clear and re-ingest to verify fixes")
    print()


if __name__ == "__main__":
    main()
