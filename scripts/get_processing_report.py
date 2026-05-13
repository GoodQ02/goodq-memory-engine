#!/usr/bin/env python3
"""
Generate real-time processing report for the UI
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

def analyze_processing():
    """Analyze current processing state"""
    base_dir = Path(__file__).parent
    
    # Find active workspace
    workspace_dir = base_dir / "logs" / "watchdog_20251108_130053" / "1987_1988"
    
    if not workspace_dir.exists():
        print(json.dumps({"status": "no_processing", "message": "No active processing found"}))
        return
    
    # Count scenes
    frames_dir = workspace_dir / "frames"
    audio_dir = workspace_dir / "audio"
    
    frames = list(frames_dir.glob("*.jpg")) if frames_dir.exists() else []
    audio_files = list(audio_dir.glob("*.wav")) if audio_dir.exists() else []
    
    # Get timestamps
    first_frame_time = min([f.stat().st_mtime for f in frames]) if frames else None
    last_frame_time = max([f.stat().st_mtime for f in frames]) if frames else None
    
    # Calculate stats
    if first_frame_time and last_frame_time and len(frames) > 1:
        elapsed_seconds = last_frame_time - first_frame_time
        scenes_per_minute = len(frames) / (elapsed_seconds / 60) if elapsed_seconds > 0 else 0
        seconds_per_scene = elapsed_seconds / len(frames) if len(frames) > 0 else 90
        
        # Estimate total scenes (rough estimate based on video duration)
        # 7.28GB at ~5-10 MB/min of video ≈ 90-120 minutes
        # With ~1-2 minute scenes = 60-90 scenes estimated
        estimated_total_scenes = 150  # Conservative estimate
        
        remaining_scenes = max(0, estimated_total_scenes - len(frames))
        estimated_remaining_seconds = remaining_scenes * seconds_per_scene
        
        eta = datetime.now() + timedelta(seconds=estimated_remaining_seconds)
    else:
        scenes_per_minute = 0
        seconds_per_scene = 90
        estimated_total_scenes = 150
        remaining_scenes = estimated_total_scenes
        eta = None
    
    report = {
        "status": "processing",
        "video": "1987_1988.mp4",
        "video_size_gb": 7.28,
        "year_born": 1987,
        "scenes_processed": len(frames),
        "audio_clips": len(audio_files),
        "processing_rate": {
            "scenes_per_minute": round(scenes_per_minute, 2),
            "seconds_per_scene": round(seconds_per_scene, 1)
        },
        "estimates": {
            "total_scenes": estimated_total_scenes,
            "remaining_scenes": remaining_scenes,
            "percent_complete": round((len(frames) / estimated_total_scenes * 100), 1) if estimated_total_scenes > 0 else 0,
            "eta": eta.isoformat() if eta else None,
            "eta_human": eta.strftime("%I:%M %p") if eta else "Calculating..."
        },
        "timestamps": {
            "started": datetime.fromtimestamp(first_frame_time).isoformat() if first_frame_time else None,
            "last_update": datetime.fromtimestamp(last_frame_time).isoformat() if last_frame_time else None
        },
        "scene_details": {
            "first_scene": frames[0].name if frames else None,
            "latest_scene": frames[-1].name if frames else None
        }
    }
    
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    analyze_processing()
