"""
GoodQ4All - Live Ingestion Monitor
Monitor active ingestion progress without launching new processes
"""

import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)
_PATH_FALLBACK_WARNED = False


def _resolve_runtime_paths() -> tuple[Path, Path]:
    global _PATH_FALLBACK_WARNED
    project_root = Path(__file__).resolve().parent.parent
    paths_cfg = {}
    try:
        from steps.common.config_loader import load_configs

        cfg = load_configs()
        paths_cfg = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    except Exception:
        paths_cfg = {}

    log_dir_raw = paths_cfg.get("log_dir")
    if log_dir_raw:
        log_dir = Path(log_dir_raw)
        if not log_dir.is_absolute():
            log_dir = (project_root / log_dir).resolve()
    else:
        log_dir = project_root / "logs"

    processing_raw = paths_cfg.get("processing")
    if processing_raw:
        processing_dir = Path(processing_raw)
    else:
        data_root = paths_cfg.get("data_root") or os.environ.get("GOODQ_DATA_ROOT")
        if data_root:
            base = Path(data_root)
            processing_dir = base / "processing" if base.name == "GoodQ_Data" else base / "GoodQ_Data" / "processing"
            if not _PATH_FALLBACK_WARNED:
                logger.warning(
                    "monitor_ingestion path fallback used path_key=%s derived_from=%s",
                    "paths.processing",
                    "paths.data_root_or_env",
                )
                _PATH_FALLBACK_WARNED = True
        else:
            processing_dir = project_root / "processing"
            if not _PATH_FALLBACK_WARNED:
                logger.warning(
                    "monitor_ingestion path fallback used path_key=%s derived_from=%s",
                    "paths.processing",
                    "cwd",
                )
                _PATH_FALLBACK_WARNED = True

    return log_dir, processing_dir


def format_time(seconds):
    """Format seconds into human readable time"""
    return str(timedelta(seconds=int(seconds)))

def get_latest_log():
    """Find the most recent watchdog log"""
    log_dir, _ = _resolve_runtime_paths()
    
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
    _, processing_dir = _resolve_runtime_paths()
    
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
    _, processing_dir = _resolve_runtime_paths()
    print(f"   • Check {processing_dir}/ for output files")
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
