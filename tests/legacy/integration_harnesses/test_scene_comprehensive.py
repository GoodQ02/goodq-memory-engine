import sys, time, json
sys.path.insert(0, 'L:/goodq4all')
from steps.common.config_loader import load_configs
from steps.video_scene_detect.step import _detect_with_scenedetect
from pathlib import Path

# Load config
cfg = load_configs({})

# Test scene detection
video_path = Path('L:/_DATA/GoodQ_Data/processing/video_c13c0423a28e2c54/1987_1988.mp4')

print(f'Testing scene detection on: {video_path.name}')
print('This will take a few minutes...\n')

start = time.time()
detection = _detect_with_scenedetect(str(video_path), 27.0, 2.0)
scenes = detection.get('scenes', [])
elapsed = time.time() - start

print(f'Scene detection took {elapsed:.1f}s')
print(f'Found {len(scenes)} scenes\n')

# Show first 10 and last 5
print('First 10 scenes:')
for scene in scenes[:10]:
    idx = scene['index']
    start_time = scene['start']
    end_time = scene['end']
    dur = scene['duration']
    print(f'  Scene {idx:3d}: {start_time:8.2f}s - {end_time:8.2f}s (duration: {dur:6.2f}s)')

if len(scenes) > 15:
    print('\n...\n')
    print('Last 5 scenes:')
    for scene in scenes[-5:]:
        idx = scene['index']
        start_time = scene['start']
        end_time = scene['end']
        dur = scene['duration']
        print(f'  Scene {idx:3d}: {start_time:8.2f}s - {end_time:8.2f}s (duration: {dur:6.2f}s)')

print(f'\nTotal scenes: {len(scenes)}')
print(f'Video should process ALL {len(scenes)} scenes, not just 1!')
print('\nNow checking database to see how many are actually registered...')

# Check database
import sqlite3
db_path = cfg['paths']['db_path']
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get video hash
import hashlib
hasher = hashlib.sha256()
with open(video_path, 'rb') as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        if not chunk:
            break
        hasher.update(chunk)
video_hash = hasher.hexdigest()

print(f'\nVideo hash: {video_hash[:16]}...')

# Check how many scenes are in DB for this video
cursor.execute('''
    SELECT COUNT(*) FROM scenes WHERE video_hash = ?
''', (video_hash,))
db_scene_count = cursor.fetchone()[0]

print(f'Scenes in database for this video: {db_scene_count}')
print(f'Scenes detected: {len(scenes)}')

if db_scene_count < len(scenes):
    print(f'\n** PROBLEM CONFIRMED: Only {db_scene_count} scenes in DB, should be {len(scenes)} **')
    print('This explains why processing appears to stop after scene 0!')
    
conn.close()
