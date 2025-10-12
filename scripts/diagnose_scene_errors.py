#!/usr/bin/env python3
"""Diagnose scene errors in memory database"""
import sqlite3
import json
from collections import Counter
from pathlib import Path

db_path = Path("L:/goodq4all/data/memory.db")

if not db_path.exists():
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get total scene count
cursor.execute("SELECT COUNT(*) FROM scenes")
total_scenes = cursor.fetchone()[0]

# Get scenes with errors
cursor.execute("""
    SELECT id, meta
    FROM scenes
    WHERE meta LIKE '%error%' OR meta LIKE '%Error%' OR meta LIKE '%ERROR%'
    LIMIT 100
""")

error_types = Counter()
error_details = []

error_rows = cursor.fetchall()
print(f"\n=== Scene Error Summary ===\n")
print(f"Total scenes: {total_scenes}")
print(f"Scenes with errors: {len(error_rows)}")

for scene_id, meta_json in error_rows:
    try:
        meta = json.loads(meta_json) if meta_json else {}
        errors = meta.get('errors', {})
        
        if errors:
            for error_type, error_msg in errors.items():
                error_types[error_type] += 1
                if len(error_details) < 10:
                    error_details.append({
                        'scene_id': scene_id,
                        'type': error_type,
                        'message': error_msg[:200] if isinstance(error_msg, str) else str(error_msg)[:200]
                    })
    except Exception as e:
        print(f"Failed to parse scene {scene_id}: {e}")

print("\n=== Error Types (Top 10) ===")
for error_type, count in error_types.most_common(10):
    print(f"  {error_type}: {count}")

print("\n=== Sample Error Messages ===")
for detail in error_details:
    print(f"\nScene: {detail['scene_id']}")
    print(f"Type: {detail['type']}")
    print(f"Message: {detail['message']}")

# Check for scenes WITHOUT embeddings
cursor.execute("""
    SELECT COUNT(*)
    FROM scenes s
    LEFT JOIN embeddings e ON s.id = e.scene_id
    WHERE e.hash IS NULL
""")
scenes_without_embeddings = cursor.fetchone()[0]
print(f"\n=== Embedding Coverage ===")
print(f"Scenes without embeddings: {scenes_without_embeddings}/{total_scenes} ({scenes_without_embeddings/total_scenes*100:.1f}%)")

conn.close()
