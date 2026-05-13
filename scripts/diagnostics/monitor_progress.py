#!/usr/bin/env python3
"""
Real-time progress monitor for GoodQ pipeline
Displays live progress updates from the progress.json file
"""
import json
import os
import time
import sys
import argparse
from pathlib import Path
from datetime import datetime


REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_progress_file():
    return Path(os.environ.get("GOODQ_PROGRESS_FILE", REPO_ROOT / "logs" / "progress.json"))


def clear_screen():
    """Clear the console screen"""
    print("\033[2J\033[H", end="")


def format_timestamp(ts_str):
    """Format ISO timestamp to readable string"""
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except:
        return ts_str


def format_duration(start_str):
    """Calculate and format duration from start time"""
    try:
        start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        duration = datetime.now() - start.replace(tzinfo=None)
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except:
        return "Unknown"


def display_progress(progress_data):
    """Display progress information in a formatted way"""
    clear_screen()
    
    print("=" * 80)
    print("  GoodQ Pipeline Progress Monitor")
    print("=" * 80)
    print()
    
    status = progress_data.get("status", "unknown")
    current_file = progress_data.get("current_file", "None")
    current_step = progress_data.get("current_step", "None")
    progress_percent = progress_data.get("progress_percent", 0)
    current_step_index = progress_data.get("current_step_index", 0)
    total_steps = progress_data.get("total_steps", 0)
    started_at = progress_data.get("started_at")
    
    # Status bar
    status_symbol = {
        "idle": "[SYMBOL]",
        "processing": "🟢",
        "completed": "[OK]",
        "failed": "[FAIL]"
    }.get(status, "[SYMBOL]")
    
    print(f"Status: {status_symbol} {status.upper()}")
    print(f"File: {current_file}")
    print()
    
    if status == "processing":
        # Progress bar
        bar_width = 50
        filled = int(bar_width * progress_percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"Progress: [{bar}] {progress_percent}%")
        print(f"Step: {current_step_index}/{total_steps} - {current_step}")
        print()
        
        if started_at:
            duration = format_duration(started_at)
            print(f"Elapsed Time: {duration}")
            print()
        
        # Steps completed
        steps_completed = progress_data.get("steps_completed", [])
        if steps_completed:
            print("Completed Steps:")
            print("-" * 80)
            for step in steps_completed[-5:]:  # Show last 5
                step_name = step.get("name", "Unknown")
                completed_at = step.get("completed_at", "")
                timestamp = format_timestamp(completed_at) if completed_at else ""
                result = step.get("result", {})
                
                # Show key results if available
                result_str = ""
                if isinstance(result, dict):
                    if "count" in result:
                        result_str = f" ({result['count']} items)"
                    elif "scenes" in result:
                        result_str = f" ({result['scenes']} scenes)"
                
                print(f"  [SYMBOL] {timestamp} - {step_name}{result_str}")
            print()
        
        # Details
        details = progress_data.get("details", {})
        if details:
            print("Current Details:")
            print("-" * 80)
            for key, value in details.items():
                print(f"  {key}: {value}")
            print()
    
    # Errors and warnings
    errors = progress_data.get("errors", [])
    warnings = progress_data.get("warnings", [])
    
    if errors:
        print("Errors:")
        print("-" * 80)
        for error in errors[-3:]:  # Show last 3
            msg = error.get("message", "Unknown error")
            step = error.get("step", "")
            timestamp = format_timestamp(error.get("timestamp", ""))
            print(f"  [FAIL] {timestamp} [{step}] {msg}")
        print()
    
    if warnings:
        print("Warnings:")
        print("-" * 80)
        for warning in warnings[-3:]:  # Show last 3
            msg = warning.get("message", "Unknown warning")
            step = warning.get("step", "")
            timestamp = format_timestamp(warning.get("timestamp", ""))
            print(f"  [WARN]  {timestamp} [{step}] {msg}")
        print()
    
    print("=" * 80)
    print(f"Last updated: {format_timestamp(progress_data.get('updated_at', ''))} | Press Ctrl+C to exit")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Monitor a GoodQ progress.json file.")
    parser.add_argument(
        "--progress-file",
        default=str(_default_progress_file()),
        help="Progress JSON path. Defaults to GOODQ_PROGRESS_FILE or repo logs/progress.json.",
    )
    args = parser.parse_args()
    progress_file = Path(args.progress_file)
    
    print("GoodQ Progress Monitor")
    print(f"Monitoring: {progress_file}")
    print("Waiting for progress updates...\n")
    
    try:
        while True:
            if progress_file.exists():
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        progress_data = json.load(f)
                    display_progress(progress_data)
                except json.JSONDecodeError:
                    print("Waiting for valid progress data...")
                except Exception as e:
                    print(f"Error reading progress: {e}")
            else:
                clear_screen()
                print("=" * 80)
                print("  GoodQ Pipeline Progress Monitor")
                print("=" * 80)
                print()
                print("[SYMBOL] Status: IDLE")
                print(f"Waiting for progress file: {progress_file}")
                print()
                print("=" * 80)
                print("Press Ctrl+C to exit")
                print("=" * 80)
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
