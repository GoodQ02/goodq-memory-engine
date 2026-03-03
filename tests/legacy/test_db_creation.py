#!/usr/bin/env python3
"""Test that database creation works with current config"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from goodq4all.steps.common.config_loader import load_configs
from goodq4all.steps.common.memory import ensure_scene
import sqlite3
import os

print("=" * 70)
print("TESTING DATABASE CREATION")
print("=" * 70)

# Load config
cfg = load_configs()
print(f"\n[SYMBOL] Config loaded")

# Check if db_path is configured
db_path = cfg.get('paths', {}).get('db_path')
if not db_path:
    print("\n[FAIL] CRITICAL: db_path not found in config!")
    print("   Config paths:", cfg.get('paths', {}))
    sys.exit(1)

print(f"[SYMBOL] db_path configured: {db_path}")

# Check if directory exists
db_dir = os.path.dirname(db_path)
if not os.path.exists(db_dir):
    print(f"\n[FAIL] Database directory does not exist: {db_dir}")
    sys.exit(1)

print(f"[SYMBOL] Database directory exists: {db_dir}")

# Try to create a test scene
print(f"\n[NOTE] Creating test scene...")
test_scene_id = "test_scene_001"
test_video_path = "L:/goodq4all/import_inbox/sample.mp4"

try:
    scene_hash = ensure_scene(
        cfg=cfg,
        scene_id=test_scene_id,
        video_path=test_video_path,
        index=0,
        start_time=0.0,
        end_time=10.0,
        confidence=0.95
    )
    print(f"[SYMBOL] Scene created successfully!")
    print(f"  Scene hash: {scene_hash}")
except Exception as e:
    print(f"\n[FAIL] Failed to create scene: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify database was created
if not os.path.exists(db_path):
    print(f"\n[FAIL] Database file was NOT created at {db_path}")
    sys.exit(1)

print(f"[SYMBOL] Database file created: {db_path}")
print(f"  Size: {os.path.getsize(db_path)} bytes")

# Check tables
conn = sqlite3.connect(db_path)
cur = conn.cursor()
tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"[SYMBOL] Tables in database: {', '.join(tables)}")

# Check scene count
scene_count = cur.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
print(f"[SYMBOL] Scenes in database: {scene_count}")

conn.close()

print("\n" + "=" * 70)
print("[OK] DATABASE CREATION TEST PASSED!")
print("=" * 70)
