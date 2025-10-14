"""
Clear all databases for a fresh production run
"""
import sqlite3
from pathlib import Path
import shutil

# Database paths
MEMORY_DB = Path('L:/goodq4all/data/memory.db')
KNOWLEDGE_GRAPH_DB = Path('L:/goodq4all/L:/goodq4all/data/knowledge_graph.db')
CLAP_ID_MAP = Path('L:/GoodQ_Data/data/memory_db/clap_id_map.sqlite')

# FAISS indices
FAISS_AUDIO = Path('L:/GoodQ_Data/data/memory_db/faiss_audio.index')
FAISS_TEXT = Path('L:/GoodQ_Data/data/memory_db/faiss_text.index')
FAISS_DINO = Path('L:/GoodQ_Data/data/memory_db/faiss_dino.index')
FAISS_CLIP = Path('L:/GoodQ_Data/data/memory_db/faiss_clip.index')

# Logs
STEP_RUNS_LOG = Path('L:/GoodQ_Data/logs/step_runs.jsonl')
STEP_RUNS_CSV = Path('L:/GoodQ_Data/logs/step_runs.csv')

def clear_database_tables(db_path: Path):
    """Clear all tables in a database except schema"""
    if not db_path.exists():
        print(f"  Database doesn't exist: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    # Clear each table
    for table in tables:
        print(f"  Clearing table: {table}")
        cursor.execute(f"DELETE FROM {table}")
    
    # Reset sequences if they exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
    if cursor.fetchone():
        cursor.execute("DELETE FROM sqlite_sequence")
    
    conn.commit()
    conn.close()
    print(f"  ✓ Cleared {len(tables)} tables in {db_path.name}")

def delete_file_if_exists(file_path: Path):
    """Delete a file if it exists"""
    if file_path.exists():
        file_path.unlink()
        print(f"  ✓ Deleted {file_path.name}")
    else:
        print(f"  File doesn't exist: {file_path.name}")

def backup_logs():
    """Backup log files before clearing"""
    if STEP_RUNS_LOG.exists():
        backup_path = STEP_RUNS_LOG.with_suffix('.jsonl.bak')
        shutil.copy2(STEP_RUNS_LOG, backup_path)
        print(f"  ✓ Backed up logs to {backup_path.name}")

def main():
    print("=" * 60)
    print("CLEARING DATABASES FOR PRODUCTION RUN")
    print("=" * 60)
    
    print("\n1. Backing up logs...")
    backup_logs()
    
    print("\n2. Clearing memory database...")
    clear_database_tables(MEMORY_DB)
    
    print("\n3. Clearing knowledge graph database...")
    if KNOWLEDGE_GRAPH_DB.exists():
        clear_database_tables(KNOWLEDGE_GRAPH_DB)
    else:
        print("  Knowledge graph DB doesn't exist yet (will be created)")
    
    print("\n4. Clearing CLAP ID map...")
    if CLAP_ID_MAP.exists():
        clear_database_tables(CLAP_ID_MAP)
    
    print("\n5. Deleting FAISS indices...")
    delete_file_if_exists(FAISS_AUDIO)
    delete_file_if_exists(FAISS_TEXT)
    delete_file_if_exists(FAISS_DINO)
    delete_file_if_exists(FAISS_CLIP)
    
    print("\n6. Clearing step run logs...")
    if STEP_RUNS_LOG.exists():
        STEP_RUNS_LOG.write_text('')
        print(f"  ✓ Cleared {STEP_RUNS_LOG.name}")
    if STEP_RUNS_CSV.exists():
        STEP_RUNS_CSV.write_text('')
        print(f"  ✓ Cleared {STEP_RUNS_CSV.name}")
    
    print("\n" + "=" * 60)
    print("✓ DATABASES CLEARED - READY FOR PRODUCTION RUN")
    print("=" * 60)

if __name__ == '__main__':
    main()
