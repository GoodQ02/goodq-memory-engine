"""
Test GPU-Accelerated Scene Detection
"""
import sys
import os
from pathlib import Path

# Add steps to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "steps"))


def _find_test_video():
    direct_file = os.environ.get("GOODQ_TEST_VIDEO")
    if direct_file and Path(direct_file).is_file():
        return Path(direct_file)

    candidate_dirs = []
    for env_name in ("GOODQ_TEST_VIDEO_DIR", "GOODQ_IMPORT_INBOX"):
        value = os.environ.get(env_name)
        if value:
            candidate_dirs.append(Path(value))

    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        candidate_dirs.append(Path(data_root) / "GoodQ_Data" / "processing")

    candidate_dirs.extend([
        PROJECT_ROOT / "import_inbox",
        PROJECT_ROOT / "samples" / "ingestion",
    ])

    for candidate_dir in candidate_dirs:
        if not candidate_dir.exists():
            continue
        for video in sorted(candidate_dir.rglob("*.mp4")):
            return video
    return None

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
    test_video = _find_test_video()
    
    if not test_video or not test_video.exists():
        print("\n[ERROR] No test video found")
        print("Set GOODQ_TEST_VIDEO or GOODQ_TEST_VIDEO_DIR, or place a sample in import_inbox.")
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
    print("[SYMBOL] GPU Scene Detection Test Complete!")
    print("="*80)

if __name__ == "__main__":
    test_gpu_scene_detection()
