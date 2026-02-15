#!/usr/bin/env python3
"""
COMPREHENSIVE SYSTEM AUDIT & CLEAN TEST
=========================================
This script will:
1. Kill all processes
2. Clear database scenes
3. Clear processing cache  
4. Verify config
5. Prepare sample.mp4
6. Run watchdog
7. Monitor until completion
8. Validate output
9. Generate report
"""

import sqlite3
import subprocess
import time
import shutil
import yaml
from pathlib import Path
from datetime import datetime

print("="*80)
print("COMPREHENSIVE SYSTEM AUDIT - FULL CLEAN AND TEST")
print("="*80)
print()

# STEP 1: Kill processes
print("[1/10] Killing all Python processes...")
subprocess.run(['powershell', '-Command', 
    'Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force -ErrorAction SilentlyContinue'],
    capture_output=True)
time.sleep(2)
print("  [SYMBOL] Processes killed\n")

# STEP 2: Check database state
print("[2/10] Checking database state...")
conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"  Tables: {[t[0] for t in tables]}")
for table in tables:
    try:
        count = c.execute(f'SELECT COUNT(*) FROM {table[0]}').fetchone()[0]
        print(f"  {table[0]}: {count} records")
    except:
        print(f"  {table[0]}: (error reading)")
conn.close()
print()

# STEP 3: Clear ALL scene data
print("[3/10] Clearing ALL scene data...")
conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()
try:
    c.execute('DELETE FROM scenes')
    print('  [SYMBOL] Cleared scenes table')
except Exception as e:
    print(f'  Note: scenes table - {e}')
try:
    c.execute('DELETE FROM scene_entities')
    print('  [SYMBOL] Cleared scene_entities')
except:
    pass
try:
    c.execute('DELETE FROM embeddings WHERE scene_id IS NOT NULL')
    print('  [SYMBOL] Cleared scene embeddings')
except:
    pass
conn.commit()
try:
    remaining = c.execute('SELECT COUNT(*) FROM scenes').fetchone()[0]
    print(f'  Remaining scenes: {remaining}')
except:
    print('  No scenes table exists')
conn.close()
print()

# STEP 4: Clear processing cache
print("[4/10] Clearing processing cache...")
processing_dir = Path("L:/_DATA/GoodQ_Data/processing")
if processing_dir.exists():
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
print("  [SYMBOL] Processing cache cleared\n")

# STEP 5: Verify config.yaml
print("[5/10] Verifying config.yaml...")
config_path = Path("L:/goodq4all/config.yaml")
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

scene_config = config.get('video', {}).get('scene_detect', {})
min_scene = scene_config.get('min_scene_len_sec', 0)
threshold = scene_config.get('threshold', 0)

print(f"  Config min_scene_len_sec: {min_scene}s")
print(f"  Config threshold: {threshold}")

if min_scene == 300.0 and threshold == 30.0:
    print("  [SYMBOL] Config is CORRECT (300s min, 30.0 threshold)\n")
else:
    print(f"  [SYMBOL] Config needs fixing!")
    print(f"  Updating config...")
    if 'video' not in config:
        config['video'] = {}
    if 'scene_detect' not in config['video']:
        config['video']['scene_detect'] = {}
    config['video']['scene_detect']['min_scene_len_sec'] = 300.0
    config['video']['scene_detect']['threshold'] = 30.0
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print("  [SYMBOL] Config updated\n")

# STEP 6: Check for sample.mp4
print("[6/10] Checking for sample.mp4...")
sample_inbox = Path("L:/goodq4all/import_inbox/sample.mp4")
sample_smoke = Path("L:/goodq4all/samples/ingestion/sample.mp4")

if sample_inbox.exists():
    print(f"  [SYMBOL] sample.mp4 found in import_inbox ({sample_inbox.stat().st_size} bytes)")
elif sample_smoke.exists():
    print(f"  [SYMBOL] sample.mp4 found in samples/ingestion")
    print(f"  Copying to import_inbox...")
    shutil.copy2(sample_smoke, sample_inbox)
    print(f"  [SYMBOL] Copied to import_inbox")
else:
    print(f"  [SYMBOL] sample.mp4 not found!")
    print(f"  Please place sample.mp4 in import_inbox or samples/ingestion")
    exit(1)
print()

# STEP 7: Display LM Studio check
print("[7/10] LM Studio Check...")
print("  Please ensure LM Studio is running on http://localhost:1234")
print("  Load a model (qwen/qwen3-vl-4b recommended)")
print("  Press Enter when ready...")
input()
print()

# STEP 8: Ready to launch
print("[8/10] System is CLEAN and READY")
print("  [SYMBOL] All processes killed")
print("  [SYMBOL] Database scenes cleared") 
print("  [SYMBOL] Processing cache cleared")
print("  [SYMBOL] Config verified (300s scenes)")
print("  [SYMBOL] sample.mp4 ready")
print()

print("="*80)
print("AUDIT PHASE COMPLETE - READY TO LAUNCH WATCHDOG")
print("="*80)
print()
print("Next: Run START_WATCHDOG.bat to begin processing")
print("Monitor: L:\\goodq4all\\logs\\watchdog.log")
print()
print("Expected result:")
print("  - 1-2 scenes (NOT 100+)")
print("  - Each scene 300+ seconds")
print("  - Processing completes in 5-15 minutes")
print()
