"""
GoodQ4All Project Organizer
Cleans up project structure and organizes files into proper directories
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"L:\goodq4all")

# Define organization rules
ORGANIZATION_RULES = {
    "tests": {
        "patterns": ["test_*.py", "*_test.py"],
        "exact": []
    },
    "docs": {
        "patterns": ["*.md"],
        "exact": [],
        "exclude": ["README.md", "LICENSE"]
    },
    "logs": {
        "patterns": ["*.log"],
        "exact": []
    },
    "scripts/backup": {
        "patterns": ["*_backup_*.py", "*_backup_*.html", "*.backup"],
        "exact": []
    },
    "scripts/diagnostics": {
        "patterns": ["check_*.py", "diagnose_*.py", "audit_*.py", "monitor_*.py", "verify_*.ps1"],
        "exact": ["FULL_SYSTEM_AUDIT.py", "RUN_FULL_DIAGNOSTIC.ps1"]
    },
    "scripts/setup": {
        "patterns": ["setup_*.ps1", "install_*.py", "configure_*.py", "FIX_*.ps1"],
        "exact": ["INSTALL_WEB_DEPS.ps1", "VALIDATE_PYTHON_PATHS.bat"]
    },
    "scripts/utilities": {
        "patterns": ["QUICK_*.py"],
        "exact": ["process_manager.py", "llm_client.py", "gpu_config.py"]
    },
    "web/backup": {
        "patterns": ["index_backup_*.html", "index_production*.html", "*.LEGACY_*"],
        "exact": ["scenes.html"]
    },
    "config": {
        "patterns": ["config.yaml.backup*"],
        "exact": []
    }
}

# Files to keep in root
ROOT_ESSENTIAL = {
    "__init__.py",
    ".gitignore",
    "README.md",
    "LICENSE",
    "config.yaml",
    "index.html",
    "api_server.py",
    "analytics_dashboard.py",
    "analytics_engine.py",
    "analytics_cli.py",
    "analytics_query.py",
    "LAUNCH_GOODQ.bat",
    ".env.local",
    ".env.local.template",
    ".env.agents",
    ".env.model_cache"
}

def organize_files():
    """Organize files according to rules"""
    print("=" * 80)
    print("GoodQ4All Project Organization")
    print("=" * 80)
    
    moved_files = []
    
    # Get all files in root
    root_files = [f for f in BASE_DIR.iterdir() if f.is_file()]
    
    for file_path in root_files:
        filename = file_path.name
        
        # Skip essential root files
        if filename in ROOT_ESSENTIAL:
            continue
        
        # Check against organization rules
        for dest_dir, rules in ORGANIZATION_RULES.items():
            should_move = False
            
            # Check patterns
            for pattern in rules["patterns"]:
                if file_path.match(pattern):
                    should_move = True
                    break
            
            # Check exact matches
            if filename in rules["exact"]:
                should_move = True
            
            if should_move:
                # Create destination directory
                dest_path = BASE_DIR / dest_dir
                dest_path.mkdir(parents=True, exist_ok=True)
                
                # Move file
                new_path = dest_path / filename
                try:
                    if new_path.exists():
                        print(f"⚠️  Skipping {filename} - already exists in {dest_dir}")
                    else:
                        shutil.move(str(file_path), str(new_path))
                        moved_files.append((filename, dest_dir))
                        print(f"✓ Moved {filename} → {dest_dir}/")
                except Exception as e:
                    print(f"❌ Error moving {filename}: {e}")
                
                break  # Only move to first matching destination
    
    print("\n" + "=" * 80)
    print(f"Organization Complete - Moved {len(moved_files)} files")
    print("=" * 80)
    
    return moved_files

if __name__ == "__main__":
    moved = organize_files()
    print(f"\nTotal files organized: {len(moved)}")
