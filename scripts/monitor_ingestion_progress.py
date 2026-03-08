#!/usr/bin/env python3
"""
GoodQ Mission Progress Monitor
Real-time tracking of video ingestion operations.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sqlite3

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import get_runtime_paths, load_configs

_RUNTIME_PATHS = get_runtime_paths(load_configs({}), "output_directory")
PROCESSING_ROOT = Path(_RUNTIME_PATHS["processing"]).resolve()
WORKSPACE_ROOT = PROCESSING_ROOT / "_workspace"
DB_PATH = Path(_RUNTIME_PATHS["db_path"]).resolve()
LOG_PATH = Path(_RUNTIME_PATHS["log_dir"]).resolve() / "watchdog.log"

def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H", end="")

def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m {seconds%60:.0f}s"
    else:
        return f"{seconds/3600:.1f}h"

def get_latest_workspace() -> Optional[Path]:
    """Return the canonical run workspace if present."""
    workspace = WORKSPACE_ROOT / "scene_ingest"
    return workspace if workspace.exists() else None

def count_scenes(workspace: Path) -> Dict:
    """Count extracted scenes"""
    if not workspace.exists():
        return {"videos": 0, "scenes": 0, "frames": 0, "audio": 0}
    
    videos = [v for v in PROCESSING_ROOT.iterdir() if v.is_dir() and not v.name.startswith("_")]
    
    total_frames = sum(
        len(list((v / "video" / "frames").glob("*.jpg")))
        for v in videos
        if (v / "video" / "frames").exists()
    )
    total_audio = sum(
        len(list((v / "audio" / "chunks").glob("*.wav")))
        for v in videos
        if (v / "audio" / "chunks").exists()
    )
    
    return {
        "videos": len(videos),
        "scenes": max(total_frames, total_audio),
        "frames": total_frames,
        "audio": total_audio
    }

def check_database() -> Dict:
    """Check memory database status"""
    db_path = DB_PATH
    if not db_path.exists():
        return {"embeddings": 0, "scenes": 0, "links": 0}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count embeddings
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        embeddings = cursor.fetchone()[0]
        
        # Count scenes (if table exists)
        try:
            cursor.execute("SELECT COUNT(*) FROM scenes")
            scenes = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            scenes = 0
        
        # Count links
        try:
            cursor.execute("SELECT COUNT(*) FROM links")
            links = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            links = 0
        
        conn.close()
        return {"embeddings": embeddings, "scenes": scenes, "links": links}
    except Exception as e:
        return {"error": str(e)}

def check_watchdog_log() -> Dict:
    """Parse watchdog log for current status"""
    log_file = LOG_PATH
    if not log_file.exists():
        return {"status": "not_running", "current_file": None}
    
    # Read last 50 lines
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent = lines[-50:] if len(lines) > 50 else lines
        
        # Look for processing status
        current_file = None
        status = "idle"
        
        for line in reversed(recent):
            if "Processing video:" in line:
                current_file = line.split("Processing video:")[-1].strip()
                status = "processing"
                break
            elif "Successfully processed:" in line:
                status = "idle"
                break
            elif "Failed to process:" in line:
                status = "error"
                break
        
        return {"status": status, "current_file": current_file, "log_lines": len(lines)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def monitor_loop(refresh_interval: int = 5):
    """Main monitoring loop"""
    print("[TARGET] GoodQ Mission Progress Monitor")
    print("=" * 70)
    print()
    
    start_time = datetime.now()
    
    try:
        while True:
            clear_screen()
            
            # Header
            elapsed = (datetime.now() - start_time).total_seconds()
            print("━" * 70)
            print(f"[TARGET] GoodQ MISSION PROGRESS MONITOR")
            print(f"[TIMER]  Mission Duration: {format_duration(elapsed)}")
            print(f"[SYNC] Refreshing every {refresh_interval}s (Ctrl+C to stop)")
            print("━" * 70)
            print()
            
            # Watchdog status
            wd_status = check_watchdog_log()
            status_icon = {"idle": "⏸️", "processing": "[FAST]", "error": "[FAIL]", "not_running": "[SYMBOL]"}
            print(f"[SYMBOL] Watchdog Status: {status_icon.get(wd_status['status'], '[SYMBOL]')} {wd_status['status'].upper()}")
            
            if wd_status.get('current_file'):
                print(f"   Current Asset: {wd_status['current_file']}")
            
            if wd_status.get('log_lines'):
                print(f"   Log Entries: {wd_status['log_lines']}")
            
            print()
            
            # Workspace progress
            workspace = get_latest_workspace()
            if workspace:
                print(f"[SYMBOL] Active Workspace: {workspace.name}")
                scene_stats = count_scenes(workspace)
                print(f"   Videos: {scene_stats['videos']}")
                print(f"   Scenes Extracted: {scene_stats['scenes']}")
                print(f"   Frames: {scene_stats['frames']}")
                print(f"   Audio Clips: {scene_stats['audio']}")
            else:
                print("[SYMBOL] No active workspace found")
            
            print()
            
            # Database status
            db_stats = check_database()
            if 'error' in db_stats:
                print(f"[SAVE] Database: [FAIL] Error - {db_stats['error']}")
            else:
                print(f"[SAVE] Memory Database:")
                print(f"   Embeddings: {db_stats['embeddings']}")
                print(f"   Scenes: {db_stats['scenes']}")
                print(f"   Links: {db_stats['links']}")
            
            print()
            print("━" * 70)
            print()
            
            # Refresh
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\n[SYMBOL] Monitor stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monitor GoodQ ingestion progress")
    parser.add_argument('--refresh', type=int, default=5, help="Refresh interval in seconds")
    args = parser.parse_args()
    
    monitor_loop(args.refresh)
