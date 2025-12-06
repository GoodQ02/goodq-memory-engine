"""
Phase 6 Minimal Test Harness
Tests scene visual embeddings and harmonization in isolation
"""
import sys
import os

# Add project root to path
sys.path.insert(0, r"L:\goodq4all")

from steps.common.config_loader import load_configs

print("="*80)
print("PHASE 6 TEST HARNESS - MINIMAL DIAGNOSTICS")
print("="*80)

# Load config
print("\n[1] Loading configuration...")
try:
    cfg = load_configs({})
    print("✓ Config loaded successfully")
    print(f"  Config keys: {list(cfg.keys())[:10]}...")
except Exception as e:
    print(f"✗ Config load failed: {type(e).__name__}: {e}")
    sys.exit(1)

# Find a real processed video to test with
print("\n[2] Locating test video in processing directory...")
processing_root = r"L:\_DATA\GoodQ_Data\processing"
if not os.path.exists(processing_root):
    print(f"✗ Processing directory not found: {processing_root}")
    sys.exit(1)

# Find first video with scene_manifest
test_video = None
for vid_dir in os.listdir(processing_root):
    vid_path = os.path.join(processing_root, vid_dir)
    scene_manifest = os.path.join(vid_path, "video", "scene_manifest.json")
    if os.path.isdir(vid_path) and os.path.exists(scene_manifest):
        test_video = vid_dir
        break

if not test_video:
    print("✗ No video with scene_manifest.json found")
    sys.exit(1)

print(f"✓ Found test video: {test_video}")

# Construct minimal item
processing_dir = os.path.join(processing_root, test_video)
scene_manifest_path = os.path.join(processing_dir, "video", "scene_manifest.json")

item = {
    "video_id": test_video,
    "processing_dir": processing_dir,
    "scene_manifest": scene_manifest_path,
    "video_path": os.path.join(processing_dir, "video"),
}

print(f"\n[3] Test item constructed:")
print(f"  video_id: {item['video_id']}")
print(f"  processing_dir: {item['processing_dir']}")
print(f"  scene_manifest: {item['scene_manifest']}")

# Check scene manifest exists
if not os.path.exists(scene_manifest_path):
    print(f"✗ Scene manifest not found: {scene_manifest_path}")
    sys.exit(1)

import json
with open(scene_manifest_path, 'r') as f:
    scene_data = json.load(f)
    
print(f"  Scenes in manifest: {len(scene_data.get('scenes', []))}")

# Step 2: Test imports
print("\n[4] Testing Phase 6 module imports...")
try:
    from steps.video.scene_visual_embeddings import run_scene_visual_embeddings
    print("✓ scene_visual_embeddings imported")
except Exception as e:
    print(f"✗ Failed to import scene_visual_embeddings: {type(e).__name__}: {e}")
    sys.exit(1)

try:
    from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
    print("✓ cross_modal_harmonizer imported")
except Exception as e:
    print(f"✗ Failed to import cross_modal_harmonizer: {type(e).__name__}: {e}")
    sys.exit(1)

# Step 3: Test model loading
print("\n[5] Testing model loading (CLIP/DINO)...")
try:
    from steps.video.scene_embedder import SceneEmbedder
    embedder = SceneEmbedder(cfg)
    print("✓ SceneEmbedder instantiated successfully")
except Exception as e:
    print(f"✗ SceneEmbedder failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Run scene visual embeddings with error handling
print("\n[6] Running scene_visual_embeddings...")
try:
    result = run_scene_visual_embeddings(item, cfg)
    print("✓ scene_visual_embeddings completed")
    print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
except Exception as e:
    print(f"✗ scene_visual_embeddings failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Run harmonizer
print("\n[7] Running cross_modal_harmonization...")
try:
    result = run_cross_modal_harmonization(item, cfg)
    print("✓ cross_modal_harmonization completed")
    print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
except Exception as e:
    print(f"✗ cross_modal_harmonization failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("PHASE 6 TEST HARNESS COMPLETE")
print("="*80)
