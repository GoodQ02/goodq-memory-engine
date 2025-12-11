"""Test ingestion with full logging"""
import sys
sys.path.insert(0, 'L:\\goodq4all')

from pipelines.direct_ingestion import run_direct_ingestion
from steps.common.config_loader import load_configs

# Load config
cfg = load_configs({})
print('[VALIDATION] Config loaded successfully')

# Check scene config
video_cfg = cfg.get('video', {})
scene_cfg = video_cfg.get('scene_detect', {})
print(f'[VALIDATION] Video scene config:')
print(f'  - threshold: {scene_cfg.get("threshold")}')
print(f'  - min_scene_len_sec: {scene_cfg.get("min_scene_len_sec")}')
print(f'  - entity_refine: {scene_cfg.get("entity_refine")}')

# Run ingestion
video_path = 'L:\\goodq4all\\import_inbox\\sample.mp4'
print(f'\n[INGESTION] Starting ingestion for: {video_path}')
print('=' * 80)

try:
    result = run_direct_ingestion(video_path, cfg)
    print('=' * 80)
    print('[INGESTION] Completed successfully!')
    print(f'[RESULT] Keys: {list(result.keys())}')
    if 'scene_meta' in result:
        print(f'[SCENE] Status: {result["scene_meta"].get("status")}')
        print(f'[SCENE] Count: {result["scene_meta"].get("scene_count")}')
except Exception as e:
    print('=' * 80)
    print(f'[ERROR] Ingestion failed: {e}')
    import traceback
    traceback.print_exc()
