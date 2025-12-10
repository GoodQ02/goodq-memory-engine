#!/usr/bin/env python3
"""
Debug ingestion pipeline issues
"""
import subprocess
import sys
from pathlib import Path

# Test with sample video
sample_video = Path("L:/_DATA/GoodQ_Data/testing/test_input/sample.mp4")
if not sample_video.exists():
    print(f"Sample video not found: {sample_video}")
    sys.exit(1)
    
print(f"[OK] Found sample video: {sample_video}")

# Create temp directory
temp_dir = Path("L:/_DATA/GoodQ_Data/processing/test_debug")
temp_dir.mkdir(parents=True, exist_ok=True)

# Copy sample to temp
import shutil
temp_video = temp_dir / "test.mp4"
shutil.copy2(sample_video, temp_video)

# Try running ingestion with verbose output
cmd = [
    sys.executable, '-m', 'cli.run_ingestion',
    '--input-dir', str(temp_dir),
    '--workspace', 'L:/goodq4all/logs/test_debug_run',
    '--output', 'L:/goodq4all/logs/test_debug_run_results.json',
    '--step-timeout', '600',
    '--force',
    '--verbose'
]

print("=" * 80)
print("Running ingestion test...")
print("=" * 80)
print(f"Command: {' '.join(cmd)}")
print("=" * 80)

try:
    result = subprocess.run(
        cmd,
        cwd='L:/goodq4all',
        capture_output=False,  # Let output stream to console
        text=True,
        timeout=1800  # 30 min max
    )
    
    print("=" * 80)
    print(f"Exit code: {result.returncode}")
    
    if result.returncode == 0:
        print("[SUCCESS]")
    else:
        print(f"[FAILED] with code {result.returncode}")
        
except subprocess.TimeoutExpired:
    print("[TIMEOUT] after 30 minutes")
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
