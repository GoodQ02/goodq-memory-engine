"""
GoodQ4All - Global Path Correction Script
==========================================
This script corrects ALL path references from incorrect paths to canonical L:\_DATA locations.

CRITICAL FIXES:
- L:/_DATA/GoodQ_Data → L:/_DATA/GoodQ_Data
- L:/_DATA/GoodQ_Data → L:/_DATA/GoodQ_Data (relative paths)
- data/processing → L:/_DATA/GoodQ_Data/processing
"""

import os
import re
from pathlib import Path

# Path mappings
PATH_FIXES = {
    # Incorrect → Correct
    r'L:/_DATA/GoodQ_Data': r'L:/_DATA/GoodQ_Data',
    r'L:\\goodq4all\\data': r'L:\\_DATA\\GoodQ_Data',
    r'L:/_DATA/GoodQ_Data': r'L:/_DATA/GoodQ_Data',
    r'goodq4all\\data': r'L:\\_DATA\\GoodQ_Data',
    r'"L:/_DATA/GoodQ_Data/processing"': r'"L:/_DATA/GoodQ_Data/processing"',
    r"'L:/_DATA/GoodQ_Data/processing'": r"'L:/_DATA/GoodQ_Data/processing'",
    r'"L:/_DATA/GoodQ_Data/faiss_indices"': r'"L:/_DATA/GoodQ_Data/faiss_indices"',
}

def fix_file(filepath):
    """Fix paths in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        modified = False
        
        for old_path, new_path in PATH_FIXES.items():
            if re.search(old_path, content):
                content = re.sub(old_path, new_path, content)
                modified = True
        
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False

def main():
    """Run global path fix"""
    repo_root = Path("L:/goodq4all")
    
    print("=" * 80)
    print("GOODQ4ALL - GLOBAL PATH CORRECTION")
    print("=" * 80)
    print()
    
    # Files to fix
    python_files = list(repo_root.rglob("*.py"))
    yaml_files = list(repo_root.rglob("*.yaml"))
    json_files = list(repo_root.rglob("*.json"))
    
    all_files = python_files + yaml_files + json_files
    
    # Exclude archive and vendor
    all_files = [f for f in all_files if 'archive' not in str(f) and 'vendor' not in str(f)]
    
    print(f"Scanning {len(all_files)} files...")
    print()
    
    fixed_count = 0
    for filepath in all_files:
        if fix_file(filepath):
            fixed_count += 1
    
    print()
    print("=" * 80)
    print(f"✅ COMPLETE: Fixed {fixed_count} files")
    print("=" * 80)

if __name__ == "__main__":
    main()
