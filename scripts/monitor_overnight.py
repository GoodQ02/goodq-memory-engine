#!/usr/bin/env python3
"""
Overnight monitoring script - checks processing status periodically
"""
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

def check_status():
    """Check current processing status"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "memory_db": {},
        "knowledge_graph": {},
        "recent_files": {},
        "warnings": [],
        "errors": []
    }
    
    # Check memory DB
    mem_db = Path("L:/GoodQ_Data/memory.db")
    if mem_db.exists():
        conn = sqlite3.connect(str(mem_db))
        c = conn.cursor()
        
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        
        for table in tables:
            count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            status["memory_db"][table] = count
        
        # Check for null/empty critical fields
        if 'scenes' in tables:
            null_captions = c.execute('''
                SELECT COUNT(*) FROM scenes 
                WHERE caption IS NULL OR caption = ''
            ''').fetchone()[0]
            
            if null_captions > 0:
                total_scenes = status["memory_db"].get("scenes", 0)
                status["warnings"].append(
                    f"{null_captions}/{total_scenes} scenes missing captions"
                )
        
        conn.close()
    else:
        status["errors"].append("Memory database not found")
    
    # Check knowledge graph
    kg_db = Path("L:/zenml_project/data/production_knowledge_graph.db")
    if kg_db.exists():
        conn = sqlite3.connect(str(kg_db))
        c = conn.cursor()
        
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        
        for table in tables:
            count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            status["knowledge_graph"][table] = count
        
        conn.close()
    else:
        status["warnings"].append("Production knowledge graph not found")
    
    # Check recent file activity
    data_dirs = [
        Path("L:/zenml_project/logs/production_run"),
        Path("L:/zenml_project/logs/ingest_full"),
    ]
    
    for data_dir in data_dirs:
        if data_dir.exists():
            # Count recent files (last hour)
            one_hour_ago = time.time() - 3600
            recent = [
                f for f in data_dir.rglob("*") 
                if f.is_file() and f.stat().st_mtime > one_hour_ago
            ]
            if recent:
                status["recent_files"][str(data_dir)] = len(recent)
    
    return status

def main():
    """Main monitoring loop"""
    output_file = Path("L:/zenml_project/logs/overnight_monitor.jsonl")
    
    print("🌙 Starting overnight monitoring...")
    print(f"   Logging to: {output_file}")
    print(f"   Check interval: 30 minutes")
    print(f"   Press Ctrl+C to stop")
    print()
    
    check_count = 0
    
    while True:
        try:
            check_count += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Check #{check_count}")
            
            status = check_status()
            
            # Log to file
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(status) + '\n')
            
            # Print summary
            print(f"  Memory DB: {sum(status['memory_db'].values())} total records")
            if status['knowledge_graph']:
                print(f"  Knowledge Graph: {sum(status['knowledge_graph'].values())} total records")
            
            if status['warnings']:
                print(f"  ⚠️  {len(status['warnings'])} warnings:")
                for w in status['warnings']:
                    print(f"     - {w}")
            
            if status['errors']:
                print(f"  ❌ {len(status['errors'])} errors:")
                for e in status['errors']:
                    print(f"     - {e}")
            
            if status['recent_files']:
                print(f"  📁 Recent activity: {sum(status['recent_files'].values())} files")
            
            print()
            
            # Wait 30 minutes
            time.sleep(1800)
            
        except KeyboardInterrupt:
            print("\n✓ Monitoring stopped")
            break
        except Exception as e:
            print(f"❌ Error during check: {e}")
            time.sleep(60)  # Wait a minute before retry

if __name__ == "__main__":
    main()
