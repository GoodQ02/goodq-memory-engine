"""Check latest processing results against the canonical runtime config."""
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from steps.common.config_loader import load_configs

    runtime_cfg = load_configs()
except Exception as exc:
    print(f"[WARN] Could not load canonical config: {type(exc).__name__}: {exc}")
    runtime_cfg = {}

paths_cfg = runtime_cfg.get("paths", {}) if isinstance(runtime_cfg, dict) else {}
video_cfg = runtime_cfg.get("video", {}) if isinstance(runtime_cfg, dict) else {}
scene_cfg = video_cfg.get("scene_detect", {}) if isinstance(video_cfg, dict) else {}

db_path = Path(paths_cfg.get("db_path") or (REPO_ROOT / "data" / "memory.db"))
expected_min_scene = float(scene_cfg.get("min_scene_len_sec") or 30.0)
if not db_path.exists():
    print(f"[FAIL] Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get counts
cursor.execute('SELECT COUNT(*) FROM scenes')
scene_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM embeddings')
embed_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM segments')
seg_count = cursor.fetchone()[0]

print("=" * 60)
print("DATABASE STATISTICS")
print("=" * 60)
print(f"Scenes:     {scene_count}")
print(f"Embeddings: {embed_count}")
print(f"Segments:   {seg_count}")

# Get latest scenes
cursor.execute('''
    SELECT scene_id, duration, caption, video_path 
    FROM scenes 
    ORDER BY scene_id DESC 
    LIMIT 10
''')
scenes = cursor.fetchall()

print("\n" + "=" * 60)
print("LATEST 10 SCENES")
print("=" * 60)
for s in scenes:
    vid_name = Path(s[3]).name if s[3] else "Unknown"
    caption = s[2][:50] + "..." if s[2] and len(s[2]) > 50 else s[2] or "No caption"
    print(f"Scene {s[0]:3d}: {s[1]:6.1f}s | {vid_name[:25]:25s} | {caption}")

# Check scene durations
cursor.execute('''
    SELECT AVG(duration), MIN(duration), MAX(duration)
    FROM scenes
    WHERE scene_id > (SELECT MAX(scene_id) - 10 FROM scenes)
''')
avg_dur, min_dur, max_dur = cursor.fetchone()

print("\n" + "=" * 60)
print("SCENE DURATION ANALYSIS (Last 10 scenes)")
print("=" * 60)
print(f"Average: {avg_dur:.1f}s ({avg_dur/60:.1f} minutes)")
print(f"Min:     {min_dur:.1f}s ({min_dur/60:.1f} minutes)")
print(f"Max:     {max_dur:.1f}s ({max_dur/60:.1f} minutes)")
print(f"Configured minimum: {expected_min_scene:.1f}s")

# Check against the configured scene minimum rather than a retired fixed doctrine.
if avg_dur >= expected_min_scene:
    print("[OK] Scene detection is aligned with configured scene length")
else:
    print("[WARN] Recent scenes are shorter than configured minimum on average")

conn.close()
