#!/usr/bin/env python3
"""Test full scene detection with proper config"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from steps.common.config_loader import load_configs

cfg = load_configs({})

print("Full cfg keys:", cfg.keys())
print("\ncfg['config'] keys:", cfg.get('config', {}).keys() if 'config' in cfg else "NO CONFIG KEY")
print("\nLooking for video in cfg:", cfg.get('video'))
print("\nLooking for video in cfg['config']:", cfg.get('config', {}).get('video'))

# Now test the actual _load_params as it's used
from steps.video_scene_detect.step import _load_params

# The step.py looks for cfg.get('video') directly
# But config_loader returns cfg['config']['video']
# This is a mismatch!

print("\n" + "=" * 60)
print("TESTING WITH CORRECT CFG STRUCTURE")
print("=" * 60)

# What _load_params expects
test_item = {}
params_wrong = _load_params(cfg, test_item)
print(f"\nUsing cfg directly: min_scene_len_sec = {params_wrong['min_scene_len_sec']}")

# What it should use
correct_cfg = cfg.get('config', {})
params_right = _load_params(correct_cfg, test_item)
print(f"Using cfg['config']: min_scene_len_sec = {params_right['min_scene_len_sec']}")
