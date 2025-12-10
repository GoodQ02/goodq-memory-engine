#!/usr/bin/env python3
"""Quick database and cache cleanup - NON-INTERACTIVE"""
import sqlite3
import subprocess
import time
import shutil
import yaml
from pathlib import Path

print("="*80)
print("QUICK CLEAN - Database & Cache")
print("="*80)

# Kill processes
print("\n[1/5] Killing Python processes...")
subprocess.run(['powershell', '-Command', 
    'Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force -ErrorAction SilentlyContinue'],
    capture_output=True)
time.sleep(2)
print("  ✓ Done")

# Check and clear database
print("\n[2/5] Clearing database scenes...")
try:
    conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
    c = conn.cursor()
    c.execute('DELETE FROM scenes')
    conn.commit()
    remaining = c.execute('SELECT COUNT(*) FROM scenes').fetchone()[0]
    print(f"  ✓ Scenes cleared (remaining: {remaining})")
    conn.close()
except Exception as e:
    print(f"  Note: {e}")

# Clear processing cache
print("\n[3/5] Clearing processing cache...")
processing_dir = Path("L:/_DATA/GoodQ_Data/processing")
if processing_dir.exists():
    for item in processing_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            elif item.suffix in ['.mp4', '.avi', '.mov', '.mkv']:
                item.unlink()
        except:
            pass
print("  ✓ Done")

# Verify config
print("\n[4/5] Verifying config...")
with open("L:/goodq4all/config.yaml", 'r') as f:
    config = yaml.safe_load(f)
min_scene = config.get('video', {}).get('scene_detect', {}).get('min_scene_len_sec', 0)
threshold = config.get('video', {}).get('scene_detect', {}).get('threshold', 0)
print(f"  min_scene_len_sec: {min_scene}s")
print(f"  threshold: {threshold}")
if min_scene == 300.0:
    print("  ✓ Config correct")
else:
    print("  ✗ Config needs 300.0")

# Check sample
print("\n[5/5] Checking sample.mp4...")
if Path("L:/goodq4all/import_inbox/sample.mp4").exists():
    size = Path("L:/goodq4all/import_inbox/sample.mp4").stat().st_size
    print(f"  ✓ Found in import_inbox ({size} bytes)")
elif Path("L:/goodq4all/smoke_inbox/sample.mp4").exists():
    print("  ✓ Found in smoke_inbox")
    shutil.copy2("L:/goodq4all/smoke_inbox/sample.mp4", "L:/goodq4all/import_inbox/sample.mp4")
    print("  ✓ Copied to import_inbox")
else:
    print("  ✗ Not found")

print("\n" + "="*80)
print("CLEAN COMPLETE - Ready for watchdog")
print("="*80)
