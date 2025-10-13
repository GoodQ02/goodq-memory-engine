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

