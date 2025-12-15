"""
CRITICAL FIX: Clear old 2-second scenes and reprocess with 5-minute minimum
"""
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("GOODQ DATABASE CLEANUP & REPROCESSING PREP")
print("=" * 80)
print()

# Paths
db_path = Path("L:/_DATA/GoodQ_Data/memory.db")
kg_path = Path("L:/_DATA/GoodQ_Data/knowledge_graph.db")
processing_dir = Path("L:/_DATA/GoodQ_Data/processing")
processed_dir = Path("L:/_DATA/GoodQ_Data/processed")
failed_dir = Path("L:/_DATA/GoodQ_Data/failed")

# Create backup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = db_path.parent / f"memory_backup_{timestamp}.db"
kg_backup_path = kg_path.parent / f"knowledge_graph_backup_{timestamp}.db"

print(f"[1/6] Creating backups...")
shutil.copy2(db_path, backup_path)
print(f"      [SYMBOL] memory.db → {backup_path.name}")
shutil.copy2(kg_path, kg_backup_path)
print(f"      [SYMBOL] knowledge_graph.db → {kg_backup_path.name}")
print()

# Clear processing directories
print(f"[2/6] Cleaning processing directories...")
if processing_dir.exists():
    for item in processing_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
            print(f"      [SYMBOL] Removed {item.name}")
        elif item.is_file():
            item.unlink()
            print(f"      [SYMBOL] Removed {item.name}")
print()

# Get current data stats
print(f"[3/6] Current database stats:")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM scenes")
scene_count = cursor.fetchone()[0]
cursor.execute("SELECT AVG(end - start) FROM scenes")
avg_duration = cursor.fetchone()[0]
print(f"      Scenes: {scene_count}")
print(f"      Avg Duration: {avg_duration:.2f} seconds")
print()

# Clear old data
print(f"[4/6] Clearing old scene data...")
cursor.execute("DELETE FROM scenes")
deleted_scenes = cursor.rowcount
cursor.execute("DELETE FROM embeddings")
deleted_embeddings = cursor.rowcount
cursor.execute("DELETE FROM segments")
deleted_segments = cursor.rowcount
cursor.execute("DELETE FROM links")
deleted_links = cursor.rowcount
conn.commit()
print(f"      [SYMBOL] Deleted {deleted_scenes} scenes")
print(f"      [SYMBOL] Deleted {deleted_embeddings} embeddings")
print(f"      [SYMBOL] Deleted {deleted_segments} segments")
print(f"      [SYMBOL] Deleted {deleted_links} links")
conn.close()
print()

# Clear knowledge graph
print(f"[5/6] Clearing knowledge graph...")
conn_kg = sqlite3.connect(str(kg_path))
cursor_kg = conn_kg.cursor()
cursor_kg.execute("DELETE FROM nodes")
cursor_kg.execute("DELETE FROM edges")
cursor_kg.execute("DELETE FROM media_nodes")
cursor_kg.execute("DELETE FROM node_media")
cursor_kg.execute("DELETE FROM temporal_events")
cursor_kg.execute("DELETE FROM event_nodes")
conn_kg.commit()
conn_kg.close()
print(f"      [SYMBOL] Knowledge graph cleared")
print()

# Move videos back to import_inbox if needed
print(f"[6/6] Checking video locations...")
import_inbox = Path("L:/goodq4all/import_inbox")
video_file = import_inbox / "1987_1988.mp4"

if video_file.exists():
    print(f"      [SYMBOL] Video ready: {video_file.name} ({video_file.stat().st_size / 1e9:.2f} GB)")
else:
    # Check if it's in processed or failed
    processed_video = processed_dir / "PROCESSED_1987_1988.mp4"
    failed_video = failed_dir / "FAILED_1987_1988.mp4"
    
    if processed_video.exists():
        shutil.move(str(processed_video), str(video_file))
        print(f"      [SYMBOL] Moved from processed: {video_file.name}")
    elif failed_video.exists():
        shutil.move(str(failed_video), str(video_file))
        print(f"      [SYMBOL] Moved from failed: {video_file.name}")
    else:
        print(f"      [WARN]  WARNING: Could not find 1987_1988.mp4")

print()
print("=" * 80)
print("CLEANUP COMPLETE!")
print("=" * 80)
print()
print("NEXT STEPS:")
print("1. Verify config.yaml has min_scene_len_sec: 300.0 (5 minutes)")
print("2. Start the watchdog: python scripts/watchdog_ingest.py")
print("3. Or run direct ingestion: python -m cli.run_ingestion --input-dir import_inbox")
print()
print(f"Backups saved:")
print(f"  - {backup_path}")
print(f"  - {kg_backup_path}")
print()
