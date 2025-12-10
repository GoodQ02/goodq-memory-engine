#!/usr/bin/env python3
"""Quick check of what data is available for the API"""
import sqlite3
from pathlib import Path

def check_database(db_path):
    """Check what's in a database"""
    print(f"\n{'='*60}")
    print(f"Database: {db_path.name}")
    print('='*60)
    
    if not db_path.exists():
        print("[FAIL] Database not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n[STATS] Tables ({len(tables)}):")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  • {table}: {count} rows")
        
        # Show sample data for key tables
        if count > 0 and table in ['videos', 'scenes', 'video_metadata', 'scene_metadata', 'transcripts', 'embeddings']:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
            cols = [desc[0] for desc in cursor.description]
            print(f"    Columns: {', '.join(cols)}")
    
    conn.close()

def check_output_directory():
    """Check what's in the output directory"""
    output_dir = Path("L:/goodq4all/output")
    data_output = Path("L:/_DATA/GoodQ_Data/output")
    
    print(f"\n{'='*60}")
    print("Output Directories")
    print('='*60)
    
    for dir_path in [output_dir, data_output]:
        if dir_path.exists():
            items = list(dir_path.iterdir())
            print(f"\n[DIR] {dir_path}:")
            if items:
                for item in items[:10]:
                    if item.is_dir():
                        file_count = len(list(item.rglob('*')))
                        print(f"  • {item.name}/ ({file_count} files)")
                    else:
                        size = item.stat().st_size / 1024
                        print(f"  • {item.name} ({size:.1f} KB)")
            else:
                print("  (empty)")
        else:
            print(f"\n[DIR] {dir_path}: [FAIL] Not found")

if __name__ == "__main__":
    base_dir = Path("L:/goodq4all")
    data_dir = base_dir / "data"
    
    # Check key databases
    dbs = [
        data_dir / "memory.db",
        data_dir / "knowledge_graph.db",
        data_dir / "unified_goodq.db",
        data_dir / "goodq.db"
    ]
    
    for db in dbs:
        check_database(db)
    
    check_output_directory()
    
    print(f"\n{'='*60}")
    print("[SYMBOL] Data check complete!")
    print('='*60)
