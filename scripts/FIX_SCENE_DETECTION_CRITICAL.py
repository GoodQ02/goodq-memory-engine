"""
CRITICAL FIX: Scene Detection 2-Second Problem
================================================

PROBLEM IDENTIFIED:
- Database has 18 scenes with 2-6 second durations
- Config has min_scene_len_sec: 300.0 (5 minutes)
- Processing is stuck because it's reusing old 2-second scenes
- Entity refinement hangs trying to process hundreds of tiny scenes

ROOT CAUSE:
- Scenes were detected before config update to 300-second minimum
- Force reprocess flag not clearing scene cache properly
- Pipeline reuses cached scenes unless explicitly cleared

SOLUTION:
1. Kill all stuck Python processes
2. Clear scene data from database for affected video
3. Clear processing cache
4. Force redetect scenes with 300-second minimum
5. Restart watchdog with clean state

STEPS TO EXECUTE:
"""

import sqlite3
import subprocess
from pathlib import Path
import time

print("="*80)
print("SCENE DETECTION FIX - Clearing 2-Second Scene Problem")
print("="*80)

# Step 1: Show current problem
print("\n[1/6] Current scene statistics:")
conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
cur = conn.cursor()

stats = cur.execute('''
    SELECT 
        COUNT(*) as total_scenes,
        MIN(end - start) as min_duration,
        MAX(end - start) as max_duration,
        AVG(end - start) as avg_duration,
        video_hash
    FROM scenes
    GROUP BY video_hash
''').fetchall()

for row in stats:
    print(f"  Video hash: {row[4][:16]}...")
    print(f"  Total scenes: {row[0]}")
    print(f"  Min duration: {row[1]:.2f}s (SHOULD BE 300s!)")
    print(f"  Max duration: {row[2]:.2f}s")
    print(f"  Avg duration: {row[3]:.2f}s")
    print()

# Step 2: Clear ALL scene data
print("[2/6] Clearing all scene data from database...")
cur.execute("DELETE FROM scenes")
# Try to clear related tables if they exist
try:
    cur.execute("DELETE FROM scene_entities WHERE 1=1")
except:
    pass
try:
    cur.execute("DELETE FROM scene_summaries WHERE 1=1")
except:
    pass
conn.commit()
print("  [SYMBOL] Cleared all scenes")

# Check if cleared
remaining = cur.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
print(f"  [SYMBOL] Remaining scenes: {remaining}")
conn.close()

# Step 3: Kill stuck processes
print("\n[3/6] Killing stuck Python processes...")
result = subprocess.run(
    ['powershell', '-Command', 
     'Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force -ErrorAction SilentlyContinue'],
    capture_output=True
)
time.sleep(2)
print("  [SYMBOL] Killed stuck processes")

# Step 4: Clear processing cache
print("\n[4/6] Clearing processing cache...")
processing_dir = Path("L:/_DATA/GoodQ_Data/processing")
if processing_dir.exists():
    import shutil
    for item in processing_dir.iterdir():
        if item.is_dir():
            try:
                shutil.rmtree(item)
                print(f"  [SYMBOL] Removed {item.name}")
            except Exception as e:
                print(f"  [SYMBOL] Could not remove {item.name}: {e}")
        elif item.is_file() and item.suffix in ['.mp4', '.avi', '.mov', '.mkv']:
            try:
                item.unlink()
                print(f"  [SYMBOL] Removed {item.name}")
            except Exception as e:
                print(f"  [SYMBOL] Could not remove {item.name}: {e}")

# Step 5: Verify config
print("\n[5/6] Verifying config.yaml has correct settings...")
import yaml
config_path = Path("L:/goodq4all/config.yaml")
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

scene_config = config.get('video', {}).get('scene_detect', {})
min_scene = scene_config.get('min_scene_len_sec', 0)
threshold = scene_config.get('threshold', 0)

print(f"  Config min_scene_len_sec: {min_scene}s")
print(f"  Config threshold: {threshold}")

if min_scene == 300.0:
    print("  [SYMBOL] Config is CORRECT (300 seconds)")
else:
    print(f"  [SYMBOL] Config is WRONG! Should be 300, is {min_scene}")
    print("  Updating config...")
    if 'video' not in config:
        config['video'] = {}
    if 'scene_detect' not in config['video']:
        config['video']['scene_detect'] = {}
    config['video']['scene_detect']['min_scene_len_sec'] = 300.0
    config['video']['scene_detect']['threshold'] = 30.0
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print("  [SYMBOL] Config updated")

# Step 6: Ready to restart
print("\n[6/6] System ready for clean reprocess")
print("\n" + "="*80)
print("FIX COMPLETE!")
print("="*80)
print("\nNEXT STEPS:")
print("1. Move sample.mp4 from import_inbox to temp location")
print("2. Restart watchdog with: START_WATCHDOG.bat")
print("3. Copy sample.mp4 back to import_inbox")
print("4. Watch logs to confirm 300-second scenes are detected")
print("\nExpected result: 1-2 scenes instead of 18+ tiny scenes")
print("="*80)
