import sys
sys.path.insert(0, 'L:/goodq4all')

import traceback
from pathlib import Path

video_path = 'L:/goodq4all/import_inbox/1987_1988.mp4'

print(f"[TEST] Video: {video_path}")
print(f"[TEST] Exists: {Path(video_path).exists()}")

# Test scene detection directly
try:
    from scenedetect import open_video, SceneManager, StatsManager
    from scenedetect.detectors import ContentDetector
    
    print("[TEST] Opening video...")
    video = open_video(video_path)
    print(f"[TEST] Frame rate: {video.frame_rate}")
    print(f"[TEST] Duration: {video.duration}s")
    
    stats_manager = StatsManager()
    scene_manager = SceneManager(stats_manager=stats_manager)
    
    # Use config values
    threshold = 15.0
    min_scene_len_sec = 1.5
    frame_rate = float(video.frame_rate)
    min_len_frames = max(1, int(round(frame_rate * min_scene_len_sec)))
    
    print(f"[TEST] Threshold: {threshold}")
    print(f"[TEST] Min scene length: {min_scene_len_sec}s = {min_len_frames} frames")
    
    detector = ContentDetector(threshold=threshold, min_scene_len=min_len_frames)
    scene_manager.add_detector(detector)
    
    print("[TEST] Running scene detection (this may take several minutes)...")
    scene_manager.detect_scenes(video)
    
    scene_list = scene_manager.get_scene_list() or []
    print(f"[TEST] Detected {len(scene_list)} scenes!")
    
    for idx, (start_time, end_time) in enumerate(scene_list[:10]):
        start_sec = start_time.get_seconds()
        end_sec = end_time.get_seconds()
        print(f"  Scene {idx}: {start_sec:.1f}s - {end_sec:.1f}s ({end_sec-start_sec:.1f}s)")
    
    if len(scene_list) > 10:
        print(f"  ... and {len(scene_list) - 10} more scenes")
    
    video.release()
    
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    traceback.print_exc()

print("[TEST] Done")
