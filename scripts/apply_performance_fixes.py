"""
Apply performance optimizations to GoodQ configuration.

This will update config_open.yaml with optimized settings for faster processing.
"""

import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "config_open.yaml"
BACKUP_PATH = REPO_ROOT / "configs" / "config_open.yaml.backup"

def backup_config():
    """Create backup of current config."""
    config_path = CONFIG_PATH
    backup_path = BACKUP_PATH
    
    if config_path.exists():
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"[BACKUP] Created: {backup_path}")
        return True
    return False


def apply_optimizations():
    """Apply performance optimizations to config."""
    config_path = CONFIG_PATH
    
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}
    
    # Ensure video section exists
    if 'video' not in config:
        config['video'] = {}
    if 'scene_detect' not in config['video']:
        config['video']['scene_detect'] = {}
    
    scene_cfg = config['video']['scene_detect']
    
    # Apply optimizations
    changes = []
    
    if scene_cfg.get('threshold', 32.0) != 15.0:
        scene_cfg['threshold'] = 15.0
        changes.append("threshold: 32.0 → 15.0 (less sensitive scene detection)")
    
    if scene_cfg.get('min_scene_len_sec', 3.0) != 5.0:
        scene_cfg['min_scene_len_sec'] = 5.0
        changes.append("min_scene_len_sec: 3.0 → 5.0 (skip short scenes)")
    
    if scene_cfg.get('max_scenes', 500) != 100:
        scene_cfg['max_scenes'] = 100
        changes.append("max_scenes: 500 → 100 (cap for testing)")
    
    if scene_cfg.get('entity_refine', True) != False:
        scene_cfg['entity_refine'] = False
        changes.append("entity_refine: true → false (disable entity-based splitting)")
    
    if scene_cfg.get('entity_sample_rate', 1.0) != 0.25:
        scene_cfg['entity_sample_rate'] = 0.25
        changes.append("entity_sample_rate: 1.0 → 0.25 (sample less frequently)")
    
    if scene_cfg.get('entity_max_samples', 120) != 30:
        scene_cfg['entity_max_samples'] = 30
        changes.append("entity_max_samples: 120 → 30 (fewer samples per scene)")
    
    # Audio optimizations
    if 'audio' not in config:
        config['audio'] = {}
    if 'transcribe' not in config['audio']:
        config['audio']['transcribe'] = {}
    
    audio_cfg = config['audio']['transcribe']
    
    if audio_cfg.get('chunk_seconds', 10) != 30:
        audio_cfg['chunk_seconds'] = 30
        changes.append("audio.transcribe.chunk_seconds: 10 → 30 (larger chunks)")
    
    # Write back
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    if changes:
        print("[APPLIED] Performance optimizations:")
        for change in changes:
            print(f"  [SYMBOL] {change}")
        return True
    else:
        print("[INFO] No changes needed - already optimized")
        return True


def main():
    print("=" * 70)
    print("GoodQ Performance Optimization")
    print("=" * 70)
    print()
    
    print("[INFO] This will optimize your config for faster processing:")
    print("  - Reduce scene detection sensitivity")
    print("  - Skip short scenes")
    print("  - Cap at 100 scenes for testing")
    print("  - Disable entity refining")
    print("  - Optimize audio chunking")
    print()
    
    response = input("Apply optimizations? [y/N]: ").strip().lower()
    if response != 'y':
        print("[CANCELLED] No changes made")
        return
    
    print()
    if backup_config():
        if apply_optimizations():
            print()
            print("=" * 70)
            print("[SUCCESS] Optimizations applied!")
            print("=" * 70)
            print()
            print("Next steps:")
            print("1. Stop any running processing:")
            print("   Get-Process python* | Where StartTime -gt (Get-Date).AddHours(-1) | Stop-Process")
            print()
            print("2. Clear databases:")
            print("   .\\CLEAR_AND_REINGEST.bat")
            print()
            print("3. Test with limited scenes:")
            print("   cd <repo-root>")
            print("   conda activate %GOODQ_CONDA_ENV%   (default: goodq_core)")
            print("   python -m goodq4all.cli.run_ingestion --input-dir import_inbox --max-scenes 10 --force")
            print()
            print("4. Monitor progress:")
            print("   .\\MONITOR_PROGRESS.bat")
            print()
        else:
            print("[ERROR] Failed to apply optimizations")
    else:
        print("[ERROR] Failed to backup config")


if __name__ == "__main__":
    main()
