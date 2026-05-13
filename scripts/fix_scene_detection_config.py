"""
Fix scene detection configuration to use 5-minute minimum scenes
"""
import os
import json
from pathlib import Path

def main():
    print("="*80)
    print("  GoodQ4All - Scene Detection Configuration Fix")
    print("="*80)
    print()
    
    project_root = Path(__file__).parent.parent
    config_file = project_root / "config.json"
    
    if not config_file.exists():
        print(f"[WARN]  Config file not found: {config_file}")
        print("  Creating new configuration...")
        config = {}
    else:
        print(f"Loading: {config_file}")
        with open(config_file, 'r') as f:
            config = json.load(f)
    
    # Update scene detection settings
    if 'scene_detection' not in config:
        config['scene_detection'] = {}
    
    old_threshold = config.get('scene_detection', {}).get('threshold', 'unknown')
    old_min_scene_len = config.get('scene_detection', {}).get('min_scene_len', 'unknown')
    
    # Recommended settings for longer scenes
    config['scene_detection'].update({
        'threshold': 30.0,  # Higher threshold = fewer, longer scenes
        'min_scene_len': 300.0,  # 5 minutes minimum (300 seconds)
        'method': 'content',  # Use content-based detection
        'adaptive': True  # Adapt to video characteristics
    })
    
    print()
    print("Configuration changes:")
    print(f"  threshold: {old_threshold} -> {config['scene_detection']['threshold']}")
    print(f"  min_scene_len: {old_min_scene_len} -> {config['scene_detection']['min_scene_len']}s (5 minutes)")
    print(f"  method: {config['scene_detection']['method']}")
    print(f"  adaptive: {config['scene_detection']['adaptive']}")
    print()
    
    # Save configuration
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"[SYMBOL] Configuration saved to: {config_file}")
    
    # Also check if there's a scene detection step config
    scene_detect_config = project_root / "steps" / "video_scene_detect" / "config.json"
    if scene_detect_config.exists():
        print()
        print("Updating step-specific configuration...")
        with open(scene_detect_config, 'r') as f:
            step_config = json.load(f)
        
        step_config['min_scene_len'] = 300.0
        step_config['threshold'] = 30.0
        
        with open(scene_detect_config, 'w') as f:
            json.dump(step_config, f, indent=2)
        
        print(f"[SYMBOL] Step configuration updated: {scene_detect_config}")
    
    print()
    print("="*80)
    print("  [SYMBOL] Scene detection configured for 5-minute minimum scenes")
    print("="*80)


if __name__ == '__main__':
    main()
