#!/usr/bin/env python3
"""
GoodQ Watchdog Status Checker
Provides detailed status of file processing
"""

import json
import psutil
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import get_runtime_paths, load_configs

_RUNTIME_PATHS = get_runtime_paths(
    load_configs({}),
    "processed",
    "failed",
    "watchdog_state_file",
)
WATCH_DIR = Path(_RUNTIME_PATHS["import_inbox"]).resolve()
PROCESSING_DIR = Path(_RUNTIME_PATHS["processing"]).resolve()
PROCESSED_DIR = Path(_RUNTIME_PATHS["processed"]).resolve()
FAILED_DIR = Path(_RUNTIME_PATHS["failed"]).resolve()
STATE_FILE = Path(_RUNTIME_PATHS["watchdog_state_file"]).resolve()
LOG_FILE = Path(_RUNTIME_PATHS["log_dir"]).resolve() / "watchdog.log"

# File types
VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
DOCUMENT_EXTS = {'.pdf', '.txt', '.md', '.doc', '.docx'}

def format_size(bytes_size):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} TB"

def get_file_type_icon(path):
    """Get icon for file type"""
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:
        return "[VID]"
    elif ext in AUDIO_EXTS:
        return "[AUD]"
    elif ext in IMAGE_EXTS:
        return "[IMG]"
    elif ext in DOCUMENT_EXTS:
        return "[DOC]"
    else:
        return "[???]"

def is_watchdog_running():
    """Check if watchdog process is running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            joined = ' '.join(cmdline) if cmdline else ''
            if joined and ('cli\\watchdog.py' in joined or 'goodq4all.cli.watchdog' in joined):
                return True, proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False, None

def load_state():
    """Load watchdog state from result files"""
    result_files = sorted(LOG_FILE.parent.glob("watchdog_*_results.json"), 
                         key=lambda x: x.stat().st_mtime, reverse=True)
    
    processed_count = 0
    failed_count = 0
    
    for result_file in result_files[:20]:  # Check last 20 result files
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('video'):
                    processed_count += 1
        except Exception:
            failed_count += 1
    
    return {"processed_count": processed_count, "failed_count": failed_count}

def get_recent_log_lines(n=10):
    """Get recent log lines"""
    if not LOG_FILE.exists():
        return []
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return lines[-n:] if lines else []
    except Exception as e:
        return [f"Error reading log: {e}"]

def count_files_in_dir(directory):
    """Count files in directory"""
    if not directory.exists():
        return 0
    return len([f for f in directory.iterdir() if f.is_file()])

def main():
    """Main status checker"""
    print("\n" + "=" * 60)
    print("  GoodQ Watchdog Status Report")
    print("=" * 60)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if watchdog is running
    is_running, pid = is_watchdog_running()
    if is_running:
        print(f"  Status: RUNNING (PID: {pid})")
    else:
        print(f"  Status: STOPPED")
        print(f"  Run START_WATCHDOG.bat to start")
    print()
    
    # Load state
    state = load_state()
    
    # Directory stats
    print("  Directories:")
    
    # Inbox
    inbox_files = []
    if WATCH_DIR.exists():
        inbox_files = [f for f in WATCH_DIR.iterdir() if f.is_file()]
    print(f"    Inbox (import_inbox):     {len(inbox_files)} files")
    
    # Processing
    processing_count = count_files_in_dir(PROCESSING_DIR)
    print(f"    Processing:               {processing_count} files")
    
    # Processed
    processed_count = count_files_in_dir(PROCESSED_DIR)
    print(f"    Processed:                {processed_count} files")
    
    # Failed
    failed_count = count_files_in_dir(FAILED_DIR)
    print(f"    Failed:                   {failed_count} files")
    print()
    
    # State stats
    print("  Processing History:")
    print(f"    Successfully processed:   {state.get('processed_count', 0)} files")
    print(f"    Failed:                   {state.get('failed_count', 0)} files")
    print()
    
    # Files in inbox
    if inbox_files:
        print(f"  Files in Inbox:")
        for file in sorted(inbox_files, key=lambda x: x.stat().st_size, reverse=True)[:10]:
            icon = get_file_type_icon(file)
            size = format_size(file.stat().st_size)
            print(f"    {icon} {file.name} ({size})")
        if len(inbox_files) > 10:
            print(f"    ... and {len(inbox_files) - 10} more")
        print()
    
    # Files being processed
    if PROCESSING_DIR.exists():
        processing_files = [f for f in PROCESSING_DIR.iterdir() if f.is_file()]
        if processing_files:
            print(f"  Currently Processing:")
            for file in processing_files:
                icon = get_file_type_icon(file)
                size = format_size(file.stat().st_size)
                print(f"    {icon} {file.name} ({size})")
            print()
    
    # Recent activity from logs
    print("  Recent Activity:")
    recent_lines = get_recent_log_lines(8)
    if recent_lines:
        for line in recent_lines:
            print(f"    {line.strip()}")
    else:
        print("    No recent activity")
    print()
    
    print("=" * 60)
    
    # Recommendations
    if not is_running and inbox_files:
        print("\n  [TIP] Tip: You have files waiting. Run START_WATCHDOG.bat to process them.")
    elif is_running and not inbox_files:
        print("\n  [SYMBOL] Watchdog is running and inbox is empty.")
    elif is_running and inbox_files:
        print(f"\n  ⏳ Watchdog is processing {len(inbox_files)} file(s)...")
    else:
        print("\n  [SYMBOL] All clear! Drop files into import_inbox to process them.")
    
    print()

if __name__ == '__main__':
    main()
