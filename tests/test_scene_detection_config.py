#!/usr/bin/env python3
"""Test scene detection config loading"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from steps.common.config_loader import load_configs

cfg = load_configs({})

print("=" * 60)
print("SCENE DETECTION CONFIG TEST")
print("=" * 60)

video_cfg = cfg.get('video', {})
print(f"\nvideo config: {video_cfg}")

scene_detect_cfg = video_cfg.get('scene_detect', {})
print(f"\nscene_detect: {scene_detect_cfg}")

scene_detection_cfg = video_cfg.get('scene_detection', {})
print(f"\nscene_detection: {scene_detection_cfg}")

# Test the actual parameter loading function
from steps.video_scene_detect.step import _load_params

test_item = {}
params = _load_params(cfg, test_item)

print("\n" + "=" * 60)
print("LOADED PARAMETERS")
print("=" * 60)
for key, value in params.items():
    print(f"  {key}: {value}")

print("\n" + "=" * 60)
print("EXPECTED: min_scene_len_sec should be 300.0 (5 minutes)")
print(f"ACTUAL: min_scene_len_sec = {params['min_scene_len_sec']}")
print("=" * 60)
