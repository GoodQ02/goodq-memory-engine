#!/usr/bin/env python3
"""Show what's currently in the database"""
import sqlite3
import os

db_path = "L:/goodq4all/data/memory.db"

if not os.path.exists(db_path):
    print(f"[WARN] Database does not exist: {db_path}")
    exit(0)

size_mb = os.path.getsize(db_path) / (1024 * 1024)
print(f"\n📊 Database: {db_path}")
print(f"   Size: {size_mb:.2f} MB\n")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get all tables
tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]

if not tables:
    print("❌ NO TABLES IN DATABASE")
else:
    print(f"✓ Tables ({len(tables)}):\n")
    for table in tables:
        if table == 'sqlite_sequence':
            continue
        try:
            count = cur.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0]
            print(f"  • {table}: {count:,} rows")
            
            # Show sample if not empty
            if count > 0 and table == 'scenes':
                sample = cur.execute(f"SELECT scene_id, video_path, start_time, end_time FROM scenes LIMIT 3").fetchall()
                for s in sample:
                    print(f"      - {s[0]} ({s[2]:.1f}s-{s[3]:.1f}s)")
        except Exception as e:
            print(f"  • {table}: ERROR - {e}")

conn.close()
