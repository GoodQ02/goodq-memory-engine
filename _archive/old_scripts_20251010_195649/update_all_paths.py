"""
Update all scripts to use the new centralized paths configuration.
"""
from pathlib import Path

# Simple string replacements (no regex to avoid escape issues)
REPLACEMENTS = [
    # Old project name - forward slash
    ('L:/goodq4all', 'L:/goodq4all'),
    
    # Old project name - backslash  
    ('L:\\goodq4all', 'L:\\goodq4all'),
    ('L:\\\\goodq4all', 'L:\\\\goodq4all'),
    
    # Quoted references
    ('"goodq4all"', '"goodq4all"'),
    ("'goodq4all'", "'goodq4all'"),
    
    # Specific path updates - databases
    ('L:/goodq4all/data/memory.db', 'L:/_DATA/GoodQ_Data/databases/memory.db'),
    ('L:/goodq4all/data/knowledge_graph.db', 'L:/_DATA/GoodQ_Data/databases/knowledge_graph.db'),
    ('L:/goodq4all/data/production_knowledge_graph.db', 'L:/_DATA/GoodQ_Data/databases/production_knowledge_graph.db'),
    
    # Logs
    ('L:/goodq4all/logs/watchdog.log', 'L:/_DATA/GoodQ_Data/logs/watchdog.log'),
    ('L:/goodq4all/logs/production_run', 'L:/_DATA/GoodQ_Data/processing/production_run'),
    ('L:/goodq4all/logs/ingest_full', 'L:/_DATA/GoodQ_Data/completed/ingest_full'),
    ('L:/goodq4all/logs/overnight_monitor.jsonl', 'L:/_DATA/GoodQ_Data/logs/overnight_monitor.jsonl'),
    ('L:/goodq4all/logs/watchdog_state.json', 'L:/_DATA/GoodQ_Data/logs/watchdog_state.json'),
    ('L:/goodq4all/logs/video_ingest_results.json', 'L:/_DATA/GoodQ_Data/logs/video_ingest_results.json'),
    
    # Processing directories
    ('L:/goodq4all/data/processing', 'L:/_DATA/GoodQ_Data/processing'),
    ('L:/goodq4all/data/processed', 'L:/_DATA/GoodQ_Data/completed'),
    ('L:/goodq4all/data/failed', 'L:/_DATA/GoodQ_Data/processing/failed'),
    
    # Import statements (for Python files)
    ('from steps.', 'from steps.'),
    ('import steps.', 'import steps.'),
]

def update_file(filepath: Path):
    """Update a single file with path replacements."""
    try:
        content = filepath.read_text(encoding='utf-8')
        original_content = content
        
        # Apply all replacements using simple string replacement
        for old_text, new_text in REPLACEMENTS:
            content = content.replace(old_text, new_text)
        
        # If content changed, write it back
        if content != original_content:
            filepath.write_text(content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"  ⚠️  Error updating {filepath.name}: {e}")
        return False

def main():
    print("=" * 70)
    print("Updating All Project Paths")
    print("=" * 70)
    
    project_root = Path("L:/goodq4all")
    
    # Directories to update
    dirs_to_update = [
        project_root / "scripts",
        project_root / "steps",
        project_root / "pipelines",
        project_root / "api",
    ]
    
    updated_files = []
    skipped_files = []
    
    for directory in dirs_to_update:
        if not directory.exists():
            print(f"\n⚠️  Directory not found: {directory}")
            continue
        
        print(f"\n📁 Updating {directory.name}/")
        
        # Update Python files
        for pyfile in directory.rglob("*.py"):
            if update_file(pyfile):
                updated_files.append(pyfile)
                print(f"   ✓ {pyfile.relative_to(project_root)}")
            else:
                skipped_files.append(pyfile)
        
        # Update PowerShell files
        for psfile in directory.rglob("*.ps1"):
            if update_file(psfile):
                updated_files.append(psfile)
                print(f"   ✓ {psfile.relative_to(project_root)}")
            else:
                skipped_files.append(psfile)
    
    # Update batch files in root
    print(f"\n📁 Updating root batch files")
    for batfile in project_root.glob("*.bat"):
        if update_file(batfile):
            updated_files.append(batfile)
            print(f"   ✓ {batfile.name}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Update Summary")
    print("=" * 70)
    print(f"✓ Updated: {len(updated_files)} files")
    print(f"  Skipped: {len(skipped_files)} files (no changes needed)")
    print("\n✓ Path migration complete!")

if __name__ == "__main__":
    main()
