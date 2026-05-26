"""Check latest processing results"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/memory.db")
if not db_path.exists():
    print("[FAIL] Database not found")
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

# Get latest scenes (id is TEXT, not INTEGER)
cursor.execute('''
    SELECT id, (end - start) as duration, meta 
    FROM scenes 
    ORDER BY created_at DESC 
    LIMIT 10
''')
scenes = cursor.fetchall()

print("\n" + "=" * 60)
print("LATEST 10 SCENES")
print("=" * 60)
for s in scenes:
    scene_id = s[0]
    duration = s[1]
    try:
        meta = json.loads(s[2]) if s[2] else {}
        caption = meta.get('caption', 'No caption')[:50]
        video_name = meta.get('video_path', 'Unknown')
        if video_name and '\\' in video_name:
            video_name = Path(video_name).name
    except:
        caption = "No caption"
        video_name = "Unknown"
    
    print(f"Scene {scene_id[:8]:8s}: {duration:6.1f}s ({duration/60:4.1f}m) | {video_name[:25]:25s} | {caption}")

# Check scene durations
cursor.execute('''
    SELECT AVG(end - start) as avg_dur, MIN(end - start) as min_dur, MAX(end - start) as max_dur
    FROM (SELECT * FROM scenes ORDER BY created_at DESC LIMIT 10)
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
    print("[OK] Scene detection working correctly (5-minute scenes)")
else:
    print("[WARN] Scenes are too short (should be ~300s)")

# Check for diarization segments
cursor.execute('''
    SELECT COUNT(*) FROM segments
    WHERE id LIKE '%09.%'
''')
new_seg_count = cursor.fetchone()[0]

print("\n" + "=" * 60)
print("DIARIZATION RESULTS")
print("=" * 60)
print(f"Total segments in database: {seg_count}")
print(f"Segments from latest video: {new_seg_count}")

if new_seg_count > 0:
    cursor.execute('''
        SELECT AVG(end - start) as avg_seg_dur, COUNT(DISTINCT speaker) as speaker_count
        FROM segments
        WHERE id LIKE '%09.%'
    ''')
    avg_seg_dur, speaker_count = cursor.fetchone()
    print(f"Average segment duration: {avg_seg_dur:.1f}s")
    print(f"Unique speakers detected: {speaker_count}")
    print("[OK] Audio diarization completed successfully")

conn.close()

# Check command center logs for performance metrics
log_path = Path("logs/command_center.log")
if log_path.exists():
    print("\n" + "=" * 60)
    print("PERFORMANCE METRICS")
    print("=" * 60)
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find audio diarization performance
    for line in reversed(lines):
        if 'realtime' in line.lower() and 'diarize' in line.lower():
            print(line.strip())
            break
    
    # Find scene detection performance
    for line in reversed(lines):
        if 'scene' in line.lower() and 'detect' in line.lower():
            print(line.strip())
            break
