"""
Phase 10.4 Validation Test
Tests all critical imports and runs a basic ingestion check
"""
import sys
import os

# Ensure goodq4all is in path
sys.path.insert(0, 'L:\\goodq4all')
os.chdir('L:\\goodq4all')

print("=" * 60)
print("PHASE 10.4 - VALIDATION TEST")
print("=" * 60)

# Step 1: Test imports
print("\n[1/6] Testing Critical Imports...")
try:
    from goodq4all.steps.common.config_loader import load_configs
    print("  ✓ config_loader")
    
    from goodq4all.pipelines.direct_ingestion import run_direct_ingestion
    print("  ✓ direct_ingestion")
    
    from goodq4all.retrieval.multimodal_search import MultimodalSearchEngine
    print("  ✓ retrieval engine")
    
    print("✓ All imports successful\n")
except Exception as e:
    print(f"✗ Import failed: {e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Load config
print("[2/6] Loading Configuration...")
try:
    cfg = load_configs({})
    print(f"  ✓ Config loaded (type: {type(cfg).__name__})")
    
    # Check key paths
    if isinstance(cfg, dict):
        paths = cfg.get('paths', {})
        print(f"  Data root: {paths.get('data_root', 'NOT SET')}")
        print(f"  Processing: {paths.get('processing_dir', 'NOT SET')}")
    else:
        print(f"  Data root: {cfg.paths.data_root if hasattr(cfg, 'paths') else 'NOT SET'}")
    print()
except Exception as e:
    print(f"✗ Config load failed: {e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Check test video
print("[3/6] Checking Test Video...")
test_video = "L:\\goodq4all\\import_inbox\\sample.mp4"
if os.path.exists(test_video):
    size_mb = os.path.getsize(test_video) / (1024 * 1024)
    print(f"  ✓ Test video found: sample.mp4 ({size_mb:.2f} MB)\n")
else:
    print(f"  ✗ Test video not found: {test_video}\n")
    sys.exit(1)

# Step 4: Check processing directory
print("[4/6] Checking Data Directories...")
processing_root = "L:\\_DATA\\GoodQ_Data\\processing"
if not os.path.exists(processing_root):
    print(f"  Creating processing root: {processing_root}")
    os.makedirs(processing_root, exist_ok=True)
print(f"  ✓ Processing root exists\n")

# Step 5: Run ingestion
print("[5/6] Running Ingestion...")
print("  This may take several minutes...")
try:
    result = run_direct_ingestion(test_video, cfg)
    print("  ✓ Ingestion completed")
    print(f"  Result type: {type(result)}")
    if isinstance(result, dict):
        print(f"  Video ID: {result.get('video_id', 'N/A')}")
    print()
except Exception as e:
    print(f"  ✗ Ingestion failed: {e}")
    import traceback
    traceback.print_exc()
    print()

# Step 6: Check outputs
print("[6/6] Validating Outputs...")
video_id = "sample"
processing_dir = os.path.join(processing_root, video_id)

if os.path.exists(processing_dir):
    print(f"  ✓ Processing directory exists: {video_id}")
    
    # Check key files
    temporal_index = os.path.join(processing_dir, "temporal_index.json")
    scene_manifest = os.path.join(processing_dir, "video", "scene_manifest.json")
    
    if os.path.exists(temporal_index):
        import json
        with open(temporal_index) as f:
            ti = json.load(f)
        print(f"  ✓ Temporal index exists")
        print(f"    Phase 5: {ti.get('phase5_complete', False)}")
        print(f"    Phase 6: {ti.get('phase6_complete', False)}")
        print(f"    Scenes: {len(ti.get('scenes', []))}")
    else:
        print(f"  ✗ Temporal index missing")
    
    if os.path.exists(scene_manifest):
        print(f"  ✓ Scene manifest exists")
    else:
        print(f"  ✗ Scene manifest missing")
else:
    print(f"  ✗ Processing directory not found: {processing_dir}")

print("\n" + "=" * 60)
print("VALIDATION TEST COMPLETE")
print("=" * 60)
