"""
Phase 6 Test Harness
Tests scene visual embeddings and harmonization on existing processed video.
"""
import sys
sys.path.insert(0, 'L:\\goodq4all')

from steps.video.scene_visual_embeddings import run_scene_visual_embeddings
from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
from steps.common.config_loader import load_configs
from pathlib import Path
import os
import json

def test_phase6():
    """Run Phase 6 on existing processing data."""
    
    # Load config
    print("[TEST] Loading config...")
    cfg = load_configs({})
    cfg['data_root'] = 'L:/_DATA/GoodQ_Data'
    print(f"[TEST] Data root: {cfg['data_root']}")
    
    # Find processed videos
    processing_dir = Path(cfg['data_root']) / 'processing'
    if not processing_dir.exists():
        print(f"[TEST] Processing dir not found: {processing_dir}")
        return
    
    # List all processed videos
    videos = [d for d in processing_dir.iterdir() if d.is_dir()]
    print(f"[TEST] Found {len(videos)} processed videos:")
    for v in videos[:5]:
        print(f"  - {v.name}")
    
    if not videos:
        print("[TEST] No processed videos found!")
        return
    
    # Use the first video
    video_dir = videos[0]
    video_id = video_dir.name
    print(f"\n[TEST] Testing Phase 6 on: {video_id}")
    
    # Check for scene manifest
    scene_manifest_path = video_dir / 'video' / 'scene_manifest.json'
    if not scene_manifest_path.exists():
        print(f"[TEST] No scene manifest found at: {scene_manifest_path}")
        return
    
    # Load scene manifest to get original video path
    with open(scene_manifest_path) as f:
        scene_data = json.load(f)
    
    source_video = scene_data.get('source_video', f"L:\\goodq4all\\import_inbox\\{video_id}.mp4")
    
    print(f"[TEST] Scene manifest: {scene_manifest_path}")
    print(f"[TEST] Source video: {source_video}")
    print(f"[TEST] Scenes: {len(scene_data.get('scenes', []))}")
    
    # Construct item dict for Phase 6
    item = {
        'id': video_id,
        'source_path': source_video,
        'processing_dir': str(video_dir),
        'scene_manifest': str(scene_manifest_path)
    }
    
    print("\n[TEST] Item keys:", list(item.keys()))
    print("="*80)
    
    # Run Phase 6: Scene Visual Embeddings
    print("\n[PHASE 6.1] Running scene visual embeddings...")
    try:
        result1 = run_scene_visual_embeddings(item, cfg)
        print(f"[PHASE 6.1] Result: {result1}")
    except Exception as e:
        print(f"[PHASE 6.1] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("="*80)
    
    # Run Phase 6: Cross-Modal Harmonization
    print("\n[PHASE 6.2] Running cross-modal harmonization...")
    try:
        result2 = run_cross_modal_harmonization(item, cfg)
        print(f"[PHASE 6.2] Result: {result2}")
    except Exception as e:
        print(f"[PHASE 6.2] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("="*80)
    
    # Check for temporal index
    temporal_index_path = video_dir / 'temporal_index.json'
    if temporal_index_path.exists():
        with open(temporal_index_path) as f:
            temporal_index = json.load(f)
        
        print(f"\n[TEST] [OK] Temporal index created!")
        print(f"[TEST] Path: {temporal_index_path}")
        print(f"[TEST] Total scenes: {temporal_index.get('total_scenes', 0)}")
        print(f"[TEST] Total segments: {len(temporal_index.get('segments', []))}")
        print(f"[TEST] Phase 5 complete: {temporal_index.get('phase5_complete', False)}")
        print(f"[TEST] Phase 6 complete: {temporal_index.get('phase6_complete', False)}")
        print(f"[TEST] Phase 6 harmonized: {temporal_index.get('phase6_harmonized', False)}")
        
        # Show a sample segment
        segments = temporal_index.get('segments', [])
        if segments:
            print(f"\n[TEST] Sample segment:")
            seg = segments[0]
            print(f"  Scene ID: {seg.get('scene_id')}")
            print(f"  Time: {seg.get('start'):.2f}s - {seg.get('end'):.2f}s")
            print(f"  CLIP ID: {seg.get('clip_id')}")
            print(f"  DINO ID: {seg.get('dino_id')}")
            print(f"  Keywords: {seg.get('keywords', [])}")
            print(f"  Has visual embeddings: {seg.get('has_visual_embeddings', False)}")
            print(f"  Has audio: {seg.get('has_audio', False)}")
            print(f"  Has transcript: {seg.get('has_transcript', False)}")
    else:
        print(f"\n[TEST] [FAIL] Temporal index NOT created")
    
    print("\n" + "="*80)
    print("[TEST] Phase 6 test complete!")

if __name__ == '__main__':
    test_phase6()
