"""
Real-time Processing Statistics API for GoodQ4All Dashboard
Reads ACTUAL processing data from progress.json and file system
"""

from flask import Flask, jsonify
from flask_cors import CORS
import json
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Paths
PROGRESS_FILE = Path("L:/goodq4all/logs/progress.json")
PROCESSING_DIR = Path("L:/_DATA/GoodQ_Data/processing")
OUTPUT_DIR = Path("L:/goodq4all/output")
LOGS_DIR = Path("L:/goodq4all/logs")

def read_progress_json():
    """Read current progress from progress.json"""
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read progress.json: {e}")
    return None

def count_completed_videos():
    """Count videos in output directory"""
    try:
        if OUTPUT_DIR.exists():
            return len([d for d in OUTPUT_DIR.iterdir() if d.is_dir()])
    except:
        pass
    return 0

def count_active_processing():
    """Count active processing directories"""
    try:
        if PROCESSING_DIR.exists():
            return len([d for d in PROCESSING_DIR.iterdir() if d.is_dir()])
    except:
        pass
    return 0

def get_processing_details():
    """Get detailed processing info from file system"""
    details = {
        "scenes_detected": 0,
        "frames_extracted": 0,
        "audio_clips": 0,
        "current_video": None,
        "video_size_gb": 0
    }
    
    try:
        if PROCESSING_DIR.exists():
            # Find first active processing dir
            proc_dirs = [d for d in PROCESSING_DIR.iterdir() if d.is_dir()]
            
            for proc_dir in proc_dirs:
                # Check for video file
                video_files = list(proc_dir.glob("*.mp4")) + list(proc_dir.glob("*.avi"))
                if video_files:
                    video_file = video_files[0]
                    details["current_video"] = video_file.name
                    details["video_size_gb"] = round(video_file.stat().st_size / (1024**3), 2)
                    
                    # Count scenes
                    scenes_dir = proc_dir / "scenes"
                    if scenes_dir.exists():
                        scene_count = len([d for d in scenes_dir.iterdir() if d.is_dir()])
                        details["scenes_detected"] = scene_count
                        
                        # Count frames
                        total_frames = 0
                        for scene_dir in scenes_dir.iterdir():
                            if scene_dir.is_dir():
                                frames_dir = scene_dir / "frames"
                                if frames_dir.exists():
                                    total_frames += len(list(frames_dir.glob("*.jpg")))
                        details["frames_extracted"] = total_frames
                    
                    # Count audio files
                    audio_dir = proc_dir / "audio"
                    if audio_dir.exists():
                        details["audio_clips"] = len(list(audio_dir.glob("*.wav")))
                    
                    break  # Only process first video
    except Exception as e:
        logger.error(f"Failed to get processing details: {e}")
    
    return details

def calculate_processing_rate():
    """Calculate processing speed from timestamps"""
    try:
        progress = read_progress_json()
        if progress and "started_at" in progress and "updated_at" in progress:
            started_str = progress["started_at"]
            updated_str = progress["updated_at"]
            
            # Handle both string timestamps and None/null values
            if not started_str or not updated_str:
                return {"scenes_per_minute": 0, "seconds_per_scene": 0}
            
            # Ensure we have strings
            if not isinstance(started_str, str) or not isinstance(updated_str, str):
                return {"scenes_per_minute": 0, "seconds_per_scene": 0}
            
            started = datetime.fromisoformat(started_str)
            updated = datetime.fromisoformat(updated_str)
            elapsed = (updated - started).total_seconds()
            
            details = progress.get("details", {})
            scenes_found = details.get("scenes_found", 0)
            
            if elapsed > 0 and scenes_found > 0:
                scenes_per_minute = (scenes_found / elapsed) * 60
                seconds_per_scene = elapsed / scenes_found
                return {
                    "scenes_per_minute": round(scenes_per_minute, 2),
                    "seconds_per_scene": round(seconds_per_scene, 1)
                }
    except Exception as e:
        logger.error(f"Failed to calculate processing rate: {e}")
    
    return {
        "scenes_per_minute": 0,
        "seconds_per_scene": 0
    }

@app.route('/api/processing/stats', methods=['GET'])
def get_processing_stats():
    """Return REAL processing statistics"""
    
    # Read progress.json
    progress = read_progress_json()
    
    # Get file system stats
    completed_videos = count_completed_videos()
    active_processing = count_active_processing()
    details = get_processing_details()
    rates = calculate_processing_rate()
    
    # Build response with REAL data
    stats = {
        "status": "active" if active_processing > 0 else "idle",
        "current_video": {
            "name": details.get("current_video") or (progress.get("current_file") if progress else None),
            "size_gb": details.get("video_size_gb", 0),
            "progress_percent": progress.get("progress_percent", 0) if progress else 0,
            "current_step": progress.get("current_step") if progress else "Idle"
        },
        "scenes": {
            "detected": details.get("scenes_detected", 0) or (progress.get("details", {}).get("scenes_found", 0) if progress else 0),
            "frames_extracted": details.get("frames_extracted", 0),
            "audio_clips": details.get("audio_clips", 0)
        },
        "processing_rate": rates,
        "totals": {
            "videos_completed": completed_videos,
            "videos_active": active_processing
        },
        "timestamps": {
            "started_at": progress.get("started_at") if progress else None,
            "updated_at": progress.get("updated_at") if progress else datetime.now().isoformat()
        }
    }
    
    return jsonify(stats)

@app.route('/api/processing/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    logger.info("🚀 Starting Processing Stats API on port 5001...")
    app.run(host='0.0.0.0', port=5001, debug=False)
