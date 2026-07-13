"""
GoodQ4All End-to-End Ingestion Test Suite
Tests the complete pipeline from video input to temporal index generation.
"""
from __future__ import annotations
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

# Ensure proper Python path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def test_config_loading():
    """Test that config loads successfully with Pydantic validation."""
    print("\n" + "="*80)
    print("TEST 1: Config Loading")
    print("="*80)
    
    try:
        from steps.common.config_loader import load_configs
        cfg = load_configs({})
        print("[PASS] Config loaded successfully")
        print(f"   Config keys: {list(cfg.keys())}")
        return True, cfg
    except Exception as e:
        print(f"[FAIL] Config loading failed: {e}")
        return False, None


def test_step_imports():
    """Test that all critical step modules can be imported."""
    print("\n" + "="*80)
    print("TEST 2: Step Module Imports")
    print("="*80)
    
    steps_to_test = [
        ("Video Scene Detect", "goodq4all.steps.video_scene_detect.step", "video_scene_detect"),
        ("Audio Transcribe", "goodq4all.steps.audio_transcribe.step", "audio_transcribe"),
        ("Image OCR", "goodq4all.steps.image_ocr.step", "image_ocr"),
        ("Image Caption", "goodq4all.steps.image_caption.step", "image_caption"),
        ("Object Detect", "goodq4all.steps.object_detect.step", "object_detect"),
        ("Face Embed", "goodq4all.steps.face_embed.step", "face_embed"),
        ("Text Embed", "goodq4all.steps.text_embed.step", "text_embed"),
    ]
    
    all_passed = True
    for name, module_path, func_name in steps_to_test:
        try:
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)
            print(f"[PASS] {name}: {module_path}.{func_name}")
        except Exception as e:
            print(f"[FAIL] {name}: Failed - {e}")
            all_passed = False
    
    return all_passed


def test_sample_ingestion(cfg: Dict[str, Any]):
    """Test ingestion on sample.mp4."""
    print("\n" + "="*80)
    print("TEST 3: Sample Video Ingestion (Phase 1-5)")
    print("="*80)
    
    sample_video = REPO_ROOT / "import_inbox" / "sample.mp4"
    
    if not sample_video.exists():
        print(f"[FAIL] Sample video not found: {sample_video}")
        return False, None
    
    print(f"[VIDEO] Video: {sample_video}")
    print(f"   Size: {sample_video.stat().st_size / (1024*1024):.2f} MB")
    
    try:
        from pipelines.direct_ingestion import run_direct_ingestion
        
        print("\n[WAIT] Starting ingestion...")
        start_time = time.time()
        
        result = run_direct_ingestion(str(sample_video), cfg)
        
        elapsed = time.time() - start_time
        print(f"\n[PASS] Ingestion completed in {elapsed:.1f} seconds")
        print(f"   Result keys: {list(result.keys())}")
        
        return True, result
        
    except Exception as e:
        print(f"\n[FAIL] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_artifacts(result: Dict[str, Any], cfg: Dict[str, Any]):
    """Verify that all expected artifacts were created."""
    print("\n" + "="*80)
    print("TEST 4: Artifact Verification")
    print("="*80)
    
    if not result:
        print("[FAIL] No result to verify")
        return False
    
    # CRITICAL: Always use video_name (the filename), NOT video_id (which is a hash)
    video_name = result.get('video_name')
    if not video_name:
        print("[FAIL] No video_name in result")
        print(f"   Available keys: {list(result.keys())}")
        return False
    
    # Construct processing directory from video_name
    processing_dir = Path(cfg['paths']['processing']) / video_name
    
    print(f"[DIR] Processing dir: {processing_dir}")
    
    # Check if directory exists first
    if not processing_dir.exists():
        print(f"[FAIL] Processing directory does not exist!")
        return False
    
    artifacts_to_check = [
        ("Scene Manifest", processing_dir / "scene_manifest.json"),
        ("Temporal Index", processing_dir / "temporal_index.json"),
        ("Audio Directory", processing_dir / "audio"),
        ("Frames Directory", processing_dir / "frames"),
    ]
    
    all_found = True
    for name, path in artifacts_to_check:
        if path.exists():
            if path.is_file():
                size = path.stat().st_size
                print(f"[PASS] {name}: {size:,} bytes")
            else:
                file_count = len(list(path.glob("*")))
                print(f"[PASS] {name}: {file_count} files")
        else:
            print(f"[FAIL] {name}: NOT FOUND - {path}")
            all_found = False
    
    return all_found


def test_temporal_index_structure(result: Dict[str, Any], cfg: Dict[str, Any]):
    """Verify temporal index has correct structure."""
    print("\n" + "="*80)
    print("TEST 5: Temporal Index Structure")
    print("="*80)
    
    if not result:
        print("[FAIL] No result to verify")
        return False
    
    # CRITICAL: Use video_name (the filename), NOT video_id (which is a hash)
    video_name = result.get('video_name')
    if not video_name:
        print("[FAIL] No video_name in result")
        return False
    
    processing_dir = Path(cfg['paths']['processing']) / video_name
    temporal_index_path = processing_dir / "temporal_index.json"
    
    if not temporal_index_path.exists():
        print(f"[FAIL] Temporal index not found: {temporal_index_path}")
        # List what files DO exist to help debug
        if processing_dir.exists():
            files = list(processing_dir.glob("*.json"))
            print(f"   Files in {processing_dir}: {[f.name for f in files]}")
        return False
    
    try:
        with open(temporal_index_path, 'r') as f:
            temporal_index = json.load(f)
        
        print(f"[PASS] Temporal index loaded")
        print(f"   Video ID: {temporal_index.get('video_id')}")
        print(f"   Scenes: {len(temporal_index.get('scenes', []))}")
        print(f"   Phase 5 complete: {temporal_index.get('phase5_complete', False)}")
        print(f"   Phase 6 complete: {temporal_index.get('phase6_complete', False)}")
        
        # Check scene structure
        scenes = temporal_index.get('scenes', [])
        if scenes:
            scene_0 = scenes[0]
            print(f"\n   Scene 0 keys: {list(scene_0.keys())}")
            required_keys = ['start', 'end', 'scene_id']
            missing_keys = [k for k in required_keys if k not in scene_0]
            if missing_keys:
                print(f"   [WARN]  Missing keys: {missing_keys}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to load/parse temporal index: {e}")
        return False


def test_retrieval(cfg: Dict[str, Any]):
    """Test multimodal retrieval engine."""
    print("\n" + "="*80)
    print("TEST 6: Multimodal Retrieval")
    print("="*80)
    
    try:
        from retrieval.multimodal_search import MultimodalSearchEngine
        
        print("[SEARCH] Initializing search engine...")
        engine = MultimodalSearchEngine(cfg)
        
        test_queries = ["baby", "walking", "birthday"]
        
        for query in test_queries:
            print(f"\n   Query: '{query}'")
            results = engine.search_multimodal(
                query,
                top_k=3,
                retrieval_context="system.healthcheck",
            )
            
            if results:
                print(f"   [PASS] Found {len(results)} results")
                for i, res in enumerate(results[:2], 1):
                    print(f"      {i}. Scene {res.get('scene_id')}, Score: {res.get('score', 0):.3f}")
            else:
                print(f"   [WARN]  No results found")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Retrieval failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("GOODQ4ALL END-TO-END VALIDATION SUITE")
    print("="*80)
    
    # Test 1: Config
    config_ok, cfg = test_config_loading()
    if not config_ok:
        print("\n[FAIL] CRITICAL: Config loading failed. Cannot proceed.")
        return 1
    
    # Test 2: Imports
    imports_ok = test_step_imports()
    
    # Test 3: Ingestion
    ingestion_ok, result = test_sample_ingestion(cfg)
    
    # Test 4: Artifacts
    artifacts_ok = False
    if ingestion_ok and result:
        artifacts_ok = test_artifacts(result, cfg)
    
    # Test 5: Temporal Index
    temporal_ok = False
    if ingestion_ok and result:
        temporal_ok = test_temporal_index_structure(result, cfg)
    
    # Test 6: Retrieval
    retrieval_ok = test_retrieval(cfg)
    
    # Final Summary
    print("\n" + "="*80)
    print("FINAL TEST RESULTS")
    print("="*80)
    
    tests = [
        ("Config Loading", config_ok),
        ("Step Imports", imports_ok),
        ("Sample Ingestion", ingestion_ok),
        ("Artifacts Created", artifacts_ok),
        ("Temporal Index", temporal_ok),
        ("Retrieval Engine", retrieval_ok),
    ]
    
    passed = sum(1 for _, ok in tests if ok)
    total = len(tests)
    
    for name, ok in tests:
        status = "[PASS] PASS" if ok else "[FAIL] FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'='*80}")
    print(f"SCORE: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*80}\n")
    
    if passed == total:
        print("[SYMBOL] ALL TESTS PASSED! GoodQ4All is fully operational.")
        return 0
    else:
        print("[WARN]  Some tests failed. Review output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
