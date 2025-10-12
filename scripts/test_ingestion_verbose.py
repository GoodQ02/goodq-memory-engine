"""
Test ingestion with a small video to verify error detection works
"""
import subprocess
import sys
from pathlib import Path

# Use sample.mp4 for testing
test_video = Path("L:/goodq4all/import_inbox/sample.mp4")

if not test_video.exists():
    print(f"ERROR: Test video not found: {test_video}")
    sys.exit(1)

print(f"Testing ingestion with: {test_video.name}")
print(f"Size: {test_video.stat().st_size / 1024:.2f} KB\n")

# Create temp test directory
test_input = Path("L:/goodq4all/data/testing/test_input")
test_input.mkdir(parents=True, exist_ok=True)

# Copy video
import shutil
test_video_copy = test_input / test_video.name
if test_video_copy.exists():
    test_video_copy.unlink()
shutil.copy2(test_video, test_video_copy)

print(f"Copied to: {test_video_copy}")
print(f"File exists: {test_video_copy.exists()}\n")

# Run ingestion
cmd = [
    'conda', 'run', '-n', 'goodq_zenml',
    'python', '-m', 'goodq4all.cli.run_ingestion',
    '--input-dir', str(test_input),
    '--workspace', 'L:/goodq4all/logs/test_verbose',
    '--output', 'L:/goodq4all/logs/test_verbose/results.json',
    '--verbose',
    '--force'
]

print("Running ingestion...\n")
print(' '.join(cmd))
print()

result = subprocess.run(cmd, cwd='L:/goodq4all')

print(f"\nExit code: {result.returncode}")

if result.returncode == 0:
    print("✓ Ingestion completed successfully")
else:
    print("✗ Ingestion failed (as expected if errors > 50%)")

# Cleanup
try:
    test_video_copy.unlink()
    test_input.rmdir()
except Exception as e:
    print(f"Cleanup warning: {e}")
