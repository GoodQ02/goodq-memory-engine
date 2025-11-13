"""
Test GPU-Accelerated Scene Detection
"""
import sys
import os
from pathlib import Path

# Add steps to path
sys.path.insert(0, str(Path(__file__).parent.parent / "steps"))

def test_gpu_scene_detection():
    print("="*80)
    print("GPU Scene Detection Test")
    print("="*80)
    
    # Check GPU availability
    import torch
    print(f"\n[1/4] GPU Check:")
    print(f"  CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    
    # Test video path
    test_video = Path("L:/goodq4all/data/processing")
    if test_video.exists():
        videos = list(test_video.rglob("*.mp4"))
        if videos:
            test_video = videos[0]
        else:
            test_video = None
    else:
        test_video = None
    
    if not test_video or not test_video.exists():
        print("\n[ERROR] No test video found in L:/goodq4all/data/processing")
        print("Please place a video file in the import_inbox and let it start processing")
        return
    
    print(f"\n[2/4] Test Video:")
    print(f"  Path: {test_video}")
    print(f"  Size: {test_video.stat().st_size / 1024**2:.2f} MB")
    
    # Test GPU scene detection
    print(f"\n[3/4] Running GPU Scene Detection:")
    from video_scene_detect.gpu_scene_detect import detect_scenes_gpu
    
    import time
    start_time = time.time()
    
    result = detect_scenes_gpu(
        str(test_video),
        threshold=30.0,
        min_scene_len_sec=300.0,
        batch_size=32
    )
    
    elapsed = time.time() - start_time
    
    print(f"\n[4/4] Results:")
    print(f"  Scenes Detected: {len(result['scenes'])}")
    print(f"  Video Duration: {result['duration']:.2f}s")
    print(f"  Processing Time: {elapsed:.2f}s")
    print(f"  Speed: {result['duration']/elapsed:.2f}x realtime")
    
    print(f"\n  First 5 Scenes:")
    for scene in result['scenes'][:5]:
        print(f"    Scene {scene['index']}: {scene['start']:.1f}s - {scene['end']:.1f}s ({scene['duration']:.1f}s)")
    
    # Check GPU utilization
    print(f"\n[GPU Stats]:")
    print(f"  Allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
    print(f"  Reserved: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")
    
    print("\n" + "="*80)
    print("✓ GPU Scene Detection Test Complete!")
    print("="*80)

if __name__ == "__main__":
    test_gpu_scene_detection()
