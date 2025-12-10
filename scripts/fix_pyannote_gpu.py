"""
Fix PyAnnote GPU transfer API usage across the codebase
"""
import os
import re
from pathlib import Path

def fix_file(file_path):
    """Fix PyAnnote .to() calls in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes = []
        
        # Pattern 1: pipeline.to(torch.device("cuda")) -> pipeline.to(torch.device("cuda"))
        pattern1 = r'\.to\(["\']cuda["\']\)'
        if re.search(pattern1, content):
            content = re.sub(pattern1, '.to(torch.device("cuda"))', content)
            changes.append('  - Fixed .to(torch.device("cuda")) -> .to(torch.device("cuda"))')
            
            # Ensure torch is imported
            if 'import torch' not in content:
                # Add import after other imports
                import_match = re.search(r'(import .*\n)+', content)
                if import_match:
                    insert_pos = import_match.end()
                    content = content[:insert_pos] + 'import torch\n' + content[insert_pos:]
                    changes.append("  - Added 'import torch'")
        
        # Pattern 2: .to(torch.device("cpu")) -> .to(torch.device("cpu"))
        pattern2 = r'\.to\(["\']cpu["\']\)'
        if re.search(pattern2, content):
            content = re.sub(pattern2, '.to(torch.device("cpu"))', content)
            changes.append('  - Fixed .to(torch.device("cpu")) -> .to(torch.device("cpu"))')
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes
        
        return False, []
        
    except Exception as e:
        return False, [f"  ERROR: {str(e)}"]


def main():
    print("="*80)
    print("  GoodQ4All - PyAnnote GPU Transfer Fix")
    print("="*80)
    print()
    
    project_root = Path(__file__).parent.parent
    
    # Files to check
    patterns_to_check = [
        'steps/**/*.py',
        'scripts/**/*.py',
        'pipelines/**/*.py'
    ]
    
    files_to_fix = []
    for pattern in patterns_to_check:
        files_to_fix.extend(project_root.glob(pattern))
    
    files_to_fix = list(set(files_to_fix))
    
    print(f"Checking {len(files_to_fix)} Python files...")
    print()
    
    fixed_count = 0
    
    for file_path in sorted(files_to_fix):
        if file_path.is_file():
            modified, changes = fix_file(file_path)
            if modified:
                print(f"[SYMBOL] Fixed: {file_path.relative_to(project_root)}")
                for change in changes:
                    print(change)
                print()
                fixed_count += 1
    
    print("="*80)
    if fixed_count > 0:
        print(f"  [SYMBOL] Fixed {fixed_count} files")
    else:
        print("  [SYMBOL] No files needed fixing (already correct)")
    print("="*80)


if __name__ == '__main__':
    main()
