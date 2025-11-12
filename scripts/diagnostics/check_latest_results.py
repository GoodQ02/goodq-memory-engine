"""Check latest processing results"""
import sqlite3
from pathlib import Path

db_path = Path("data/memory.db")
if not db_path.exists():
    print("❌ Database not found")
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

# Check if scene lengths are good (should be ~300s = 5 minutes)
if avg_dur >= 180:  # At least 3 minutes
    print("✅ Scene detection working correctly (5-minute scenes)")
else:
    print("⚠️ Scenes are too short (should be ~300s)")

conn.close()
