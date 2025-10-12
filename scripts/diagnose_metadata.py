#!/usr/bin/env python3
"""Diagnose what metadata is actually in the database"""
import sqlite3
import json
from pathlib import Path

db_path = Path("L:/goodq4all/data/memory.db")

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 70)
print("DATABASE SCHEMA")
print("=" * 70)

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables: {', '.join(tables)}\n")

# Check scenes table
cursor.execute("PRAGMA table_info(scenes)")
scene_cols = cursor.fetchall()
print("Scenes table columns:")
for col in scene_cols:
    print(f"  - {col[1]} ({col[2]})")

print("\n" + "=" * 70)
print("SCENE DATA SAMPLE")
print("=" * 70)

cursor.execute("SELECT COUNT(*) FROM scenes")
total_scenes = cursor.fetchone()[0]
print(f"Total scenes: {total_scenes}")

# Check if any scenes have metadata
cursor.execute("SELECT COUNT(*) FROM scenes WHERE meta IS NOT NULL AND meta != '' AND meta != '{}'")
scenes_with_meta = cursor.fetchone()[0]
print(f"Scenes with populated meta: {scenes_with_meta}")

# Get sample scene
cursor.execute("SELECT * FROM scenes LIMIT 1")
row = cursor.fetchone()
if row:
    print("\n--- Sample Scene ---")
    col_names = [desc[0] for desc in cursor.description]
    for col_name, val in zip(col_names, row):
        if 'meta' in col_name.lower() and val:
            try:
                parsed = json.loads(val) if isinstance(val, str) else val
                print(f"{col_name}: {json.dumps(parsed, indent=2)[:300]}")
            except:
                print(f"{col_name}: {str(val)[:200]}")
        else:
            val_str = str(val)[:80] if val else "NULL"
            print(f"{col_name}: {val_str}")

# Check embeddings
print("\n" + "=" * 70)
print("EMBEDDINGS")
print("=" * 70)
cursor.execute("SELECT type, COUNT(*) FROM embeddings GROUP BY type")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
