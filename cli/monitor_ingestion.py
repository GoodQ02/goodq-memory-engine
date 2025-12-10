"""
GoodQ4All - Live Ingestion Monitor
Monitor active ingestion progress without launching new processes
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def format_time(seconds):
    """Format seconds into human readable time"""
    return str(timedelta(seconds=int(seconds)))

def get_latest_log():
    """Find the most recent watchdog log"""
    log_dir = Path("L:/goodq4all/logs")
    
    # Check for main watchdog.log first
    main_log = log_dir / "watchdog.log"
    if main_log.exists():
        return main_log
    
    # Fall back to dated watchdog logs
    watchdog_logs = list(log_dir.glob("watchdog_*.log"))
    
    if not watchdog_logs:
        return None
    
    # Get most recent
    return max(watchdog_logs, key=lambda p: p.stat().st_mtime)

def get_processing_videos():
    """Find videos currently being processed"""
    processing_dir = Path("L:/_DATA/GoodQ_Data/processing")
    
    if not processing_dir.exists():
        return []
    
    videos = []
    for video_dir in processing_dir.iterdir():
        if not video_dir.is_dir():
            continue
            
        # Look for status indicators
        metadata_file = video_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    videos.append({
                        'id': video_dir.name,
                        'name': metadata.get('video_name', 'Unknown'),
                        'path': str(video_dir),
                        'metadata': metadata
                    })
            except:
                pass
    
    return videos

def tail_log(log_path, lines=20):
    """Get last N lines from log file"""
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.readlines()[-lines:]
    except:
        return []

def monitor():
    """Main monitoring loop"""
    print("=" * 80)
    print("GoodQ4All - Live Ingestion Monitor")
    print("=" * 80)
    print()
    
    # Find active log
    log_file = get_latest_log()
    if not log_file:
        print("[FAIL] No watchdog logs found. Is the watchdog running?")
        return
    
    print(f"[SYMBOL] Monitoring log: {log_file.name}")
    print(f"   Last modified: {datetime.fromtimestamp(log_file.stat().st_mtime)}")
    print()
    
    # Check processing directory
    videos = get_processing_videos()
    if videos:
        print(f"[VIDEO] Videos in processing: {len(videos)}")
        for v in videos:
            print(f"   • {v['name']}")
        print()
    else:
        print("[VIDEO] No videos currently in processing directory")
        print()
    
    # Show recent log activity
    print("[SYMBOL] Recent log activity (last 30 lines):")
    print("-" * 80)
    
    log_lines = tail_log(log_file, 30)
    for line in log_lines:
        print(line.rstrip())
    
    print("-" * 80)
    print()
    print("[SYMBOL] Tips:")
    print("   • Run this script repeatedly to see progress")
    print("   • Check L:/_DATA/GoodQ_Data/processing/ for output files")
    print("   • Watch the log file directly for real-time updates")
    print(f"   • Log location: {log_file}")
    print()
    
    # Check if ingestion seems stuck
    log_age = time.time() - log_file.stat().st_mtime
    if log_age > 300:  # 5 minutes
        print(f"[WARN]  WARNING: Log hasn't been updated in {format_time(log_age)}")
        print("   The ingestion may be stuck or completed.")
    elif log_age > 60:
        print(f"ℹ️  Log last updated {int(log_age)}s ago (still active)")

if __name__ == "__main__":
    monitor()
