#!/usr/bin/env python3
"""
[TARGET] Configuration Values Test
Validates that settings are being loaded correctly
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from steps.common.config_loader import load_configs


def test_config_values():
    """Test that all critical settings have correct values"""
    print("=" * 70)
    print("[SEARCH] GoodQ Configuration Values Test")
    print("=" * 70)
    print()
    
    result = load_configs()
    cfg = result.get('config', {})
    paths = result.get('paths', {})
    
    # Test Video Settings
    print("[VIDEO] VIDEO SETTINGS:")
    scene_detect = cfg.get('video', {}).get('scene_detect', {})
    threshold = scene_detect.get('threshold', 'NOT SET')
    min_scene = scene_detect.get('min_scene_len_sec', 'NOT SET')
    max_scenes = scene_detect.get('max_scenes', 'NOT SET')
    entity_samples = scene_detect.get('entity_max_samples', 'NOT SET')
    
    print(f"   Scene Threshold: {threshold}")
    print(f"   Min Scene Length: {min_scene}s")
    print(f"   Max Scenes: {max_scenes if max_scenes > 0 else 'unlimited'}")
    print(f"   Entity Max Samples: {entity_samples}")
    
    # Validate
    if threshold == 15.0:
        print("   [OK] Scene threshold is CORRECT (15.0 for home movies)")
    else:
        print(f"   [FAIL] Scene threshold is WRONG (expected 15.0, got {threshold})")
    print()
    
    # Test Audio Settings
    print("[AUDIO] AUDIO SETTINGS:")
    audio = cfg.get('audio', {})
    transcribe = audio.get('transcribe', {})
    chunk_seconds = transcribe.get('chunk_seconds', 'NOT SET')
    model = transcribe.get('model', 'NOT SET')
    language = transcribe.get('language', 'NOT SET')
    
    print(f"   Transcribe Model: {model}")
    print(f"   Chunk Seconds: {chunk_seconds}")
    print(f"   Language: {language}")
    
    if chunk_seconds == 30:
        print("   [OK] Chunk seconds is CORRECT (30 for efficiency)")
    else:
        print(f"   [WARN]  Chunk seconds could be optimized (expected 30, got {chunk_seconds})")
    print()
    
    # Test New Settings
    print("[SYMBOL]️  NEW CONFIGURATION SECTIONS:")
    
    faiss = cfg.get('faiss', {})
    if faiss:
        print(f"   FAISS Index Type: {faiss.get('index_type', 'NOT SET')}")
        print(f"   FAISS Metric: {faiss.get('metric', 'NOT SET')}")
        print("   [OK] FAISS configuration found")
    else:
        print("   [WARN]  FAISS configuration missing")
    print()
    
    memory = cfg.get('memory', {})
    if memory:
        print(f"   Max Summaries/Video: {memory.get('max_summaries_per_video', 'NOT SET')}")
        print(f"   Retention Days: {memory.get('retention_days', 'NOT SET')}")
        print("   [OK] Memory management configuration found")
    else:
        print("   [WARN]  Memory management configuration missing")
    print()
    
    processing = cfg.get('processing', {})
    if processing:
        print(f"   Image Batch Size: {processing.get('batch_size_images', 'NOT SET')}")
        print(f"   Max Workers: {processing.get('max_workers', 'NOT SET')}")
        print("   [OK] Processing optimization configuration found")
    else:
        print("   [WARN]  Processing optimization configuration missing")
    print()
    
    kg = cfg.get('knowledge_graph', {})
    if kg:
        print(f"   KG Enabled: {kg.get('enabled', 'NOT SET')}")
        print(f"   Min Confidence: {kg.get('min_confidence', 'NOT SET')}")
        print("   [OK] Knowledge graph configuration found")
    else:
        print("   [WARN]  Knowledge graph configuration missing")
    print()
    
    print("=" * 70)
    print("[TARGET] Configuration Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    test_config_values()
