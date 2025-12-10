"""
Phase 2 Verification Script
Verifies all embedding and knowledge graph fixes are working
"""
import sys
from pathlib import Path

def verify_embedding_steps():
    """Verify all embedding steps have scene_id support"""
    print("="*80)
    print("VERIFYING EMBEDDING STEP FIXES")
    print("="*80)
    
    steps_to_check = [
        ("text_embed", "L:/goodq4all/steps/text_embed/step.py"),
        ("image_embed_clip", "L:/goodq4all/steps/image_embed_clip/step.py"),
        ("image_embed_dino", "L:/goodq4all/steps/image_embed_dino/step.py"),
        ("audio_embed_clap", "L:/goodq4all/steps/audio_embed_clap/step.py"),
    ]
    
    all_good = True
    
    for step_name, step_path in steps_to_check:
        print(f"\n{step_name}:")
        file_path = Path(step_path)
        
        if not file_path.exists():
            print(f"  [SYMBOL] File not found: {step_path}")
            all_good = False
            continue
        
        content = file_path.read_text()
        
        # Check for scene_id extraction
        has_scene_id_extract = 'scene_id = item.get("scene_id")' in content
        has_scene_id_param = 'scene_id=scene_id' in content
        has_upsert = 'upsert_embedding' in content
        
        print(f"  scene_id extraction: {'[SYMBOL]' if has_scene_id_extract else '[SYMBOL]'}")
        print(f"  scene_id parameter:  {'[SYMBOL]' if has_scene_id_param else '[SYMBOL]'}")
        print(f"  upsert_embedding:    {'[SYMBOL]' if has_upsert else '[SYMBOL]'}")
        
        if has_upsert and (has_scene_id_extract and has_scene_id_param):
            print(f"  Status: [SYMBOL] GOOD")
        elif has_upsert and not (has_scene_id_extract or has_scene_id_param):
            print(f"  Status: [SYMBOL] NEEDS FIX - missing scene_id support")
            all_good = False
        elif has_upsert:
            print(f"  Status: [SYMBOL] PARTIAL - some scene_id support")
            all_good = False
        else:
            print(f"  Status: ℹ No upsert_embedding (may not need scene_id)")
    
    return all_good

def verify_config_paths():
    """Verify config.yaml has all required paths"""
    print("\n" + "="*80)
    print("VERIFYING CONFIG.YAML PATHS")
    print("="*80)
    
    import yaml
    
    config_file = Path("L:/goodq4all/config.yaml")
    if not config_file.exists():
        print("[SYMBOL] config.yaml not found!")
        return False
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    required_paths = {
        'db_path': 'L:/_DATA/GoodQ_Data/memory.db',
        'faiss_index_path': 'L:/_DATA/GoodQ_Data/faiss_indices/text/faiss_text_index.bin',
        'faiss_clip_path': 'L:/_DATA/GoodQ_Data/faiss_indices/clip/faiss_clip_index.bin',
        'faiss_dino_path': 'L:/_DATA/GoodQ_Data/faiss_indices/dino/faiss_dino_index.bin',
        'faiss_audio_path': 'L:/_DATA/GoodQ_Data/faiss_indices/audio/faiss_audio_index.bin',
        'clip_id_map_db': 'L:/_DATA/GoodQ_Data/databases/clip_id_map.sqlite',
        'dino_id_map_db': 'L:/_DATA/GoodQ_Data/databases/dino_id_map.sqlite',
        'clap_id_map_db': 'L:/_DATA/GoodQ_Data/databases/clap_id_map.sqlite',
    }
    
    paths = config.get('paths', {})
    all_good = True
    
    for key, expected in required_paths.items():
        actual = paths.get(key)
        if actual == expected:
            print(f"[SYMBOL] {key:20s}: {actual}")
        elif actual:
            print(f"[SYMBOL] {key:20s}: {actual}")
            print(f"    Expected: {expected}")
            all_good = False
        else:
            print(f"[SYMBOL] {key:20s}: MISSING")
            print(f"    Expected: {expected}")
            all_good = False
    
    return all_good

def verify_graph_builder():
    """Verify knowledge graph builder enhancements"""
    print("\n" + "="*80)
    print("VERIFYING KNOWLEDGE GRAPH BUILDER")
    print("="*80)
    
    gb_file = Path("L:/goodq4all/steps/graph_builder/graph_builder.py")
    if not gb_file.exists():
        print("[SYMBOL] graph_builder.py not found!")
        return False
    
    content = gb_file.read_text()
    
    checks = {
        "Handles 'objects' field": "scene.get('objects'" in content,
        "Handles 'detections' field": "scene.get('detections'" in content,
        "_process_objects function": "def _process_objects" in content,
        "_process_faces function": "def _process_faces" in content,
        "_process_text function": "def _process_text" in content,
        "_process_audio function": "def _process_audio" in content,
        "_process_emotions function": "def _process_emotions" in content,
        "_build_cooccurrence_edges": "def _build_cooccurrence_edges" in content,
        "_build_temporal_edges": "def _build_temporal_edges" in content,
        "_build_semantic_edges": "def _build_semantic_edges" in content,
    }
    
    all_good = True
    for check_name, check_result in checks.items():
        status = "[SYMBOL]" if check_result else "[SYMBOL]"
        print(f"{status} {check_name}")
        if not check_result:
            all_good = False
    
    return all_good

def main():
    print("\n" + "="*80)
    print("PHASE 2 VERIFICATION")
    print("="*80 + "\n")
    
    results = {
        "Embedding Steps": verify_embedding_steps(),
        "Config Paths": verify_config_paths(),
        "Graph Builder": verify_graph_builder(),
    }
    
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    for component, passed in results.items():
        status = "[SYMBOL] PASS" if passed else "[SYMBOL] FAIL"
        print(f"{status}: {component}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n[SYMBOL] ALL VERIFICATIONS PASSED!")
        print("\nReady to proceed with:")
        print("  1. Clean previous sample.mp4 data")
        print("  2. Re-ingest sample.mp4 with fixed pipeline")
        print("  3. Verify embeddings have scene_id linkage")
        print("  4. Verify knowledge graph has all entity types")
        return 0
    else:
        print("\n[SYMBOL] SOME VERIFICATIONS FAILED")
        print("\nPlease review the issues above before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
