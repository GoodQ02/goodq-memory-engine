# Test scene detection directly on the 1987_1988 video
$ErrorActionPreference = "Stop"

Write-Host "================================="
Write-Host "SCENE DETECTION DEBUG TEST"
Write-Host "================================="

$video = "L:\goodq4all\import_inbox\1987_1988.mp4"

if (-not (Test-Path $video)) {
    Write-Host "[ERROR] Video not found: $video"
    exit 1
}

Write-Host "[TEST] Video: $video"

# Get video duration  
$duration = ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $video
Write-Host "[TEST] Duration: $duration seconds ($([math]::Round($duration/60, 2)) minutes)"

# Create test script to run scene detection
$testScript = @'
import sys
import json
from pathlib import Path

# Add goodq4all to path
sys.path.insert(0, 'L:/goodq4all')

from goodq4all.steps.common.config_loader import load_configs
from goodq4all.steps.video_scene_detect.step import video_scene_detect

video_path = 'L:/goodq4all/import_inbox/1987_1988.mp4'

cfg = load_configs()
print(f"[DEBUG] Config loaded")
print(f"[DEBUG] Video config: {cfg.get('config', {}).get('video', 'NOT FOUND')}")

item = {
    'modality': 'video',
    'source_path': video_path,
}

print(f"[DEBUG] Calling video_scene_detect...")
result = video_scene_detect(item, cfg)

scenes = result.get('scenes', [])
print(f"[DEBUG] Detected {len(scenes)} scenes")

for i, scene in enumerate(scenes[:10]):  # Show first 10
    print(f"  Scene {i}: {scene.get('start'):.1f}s - {scene.get('end'):.1f}s ({scene.get('duration'):.1f}s)")

if len(scenes) > 10:
    print(f"  ... and {len(scenes) - 10} more scenes")

'@

$testScript | Out-File -FilePath "L:\goodq4all\_test_scene.py" -Encoding UTF8

Write-Host "[TEST] Running scene detection..."
conda run -n goodq_zenml python "L:\goodq4all\_test_scene.py"

Write-Host "[TEST] Complete"
pause
