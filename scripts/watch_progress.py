#!/usr/bin/env python3
"""
GoodQ Progress Monitor - Watch ingestion progress in real-time
"""

import time
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
LOGS_DIR = Path("L:/goodq4all/logs")
STEP_RUNS_FILE = LOGS_DIR / "step_runs.jsonl"

def get_recent_steps(n=20):
    """Get the most recent step runs"""
    if not STEP_RUNS_FILE.exists():
        return []
    
    with open(STEP_RUNS_FILE, 'r') as f:
        lines = f.readlines()
    
    steps = []
    for line in lines[-n:]:
        try:
            steps.append(json.loads(line))
        except:
            continue
    return steps

def get_active_processing():
    """Check for active processing directories"""
    watchdog_dirs = list(LOGS_DIR.glob("watchdog_*"))
    watchdog_dirs = [d for d in watchdog_dirs if d.is_dir()]
    watchdog_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    active = []
    for wdir in watchdog_dirs[:5]:  # Check last 5
        # Check if recently modified (within last 10 minutes)
        age = time.time() - wdir.stat().st_mtime
        if age < 600:  # 10 minutes
            # Count files
            frames = list(wdir.rglob("frames/*.jpg"))
            audio = list(wdir.rglob("audio/*.wav"))
            active.append({
                'dir': wdir.name,
                'age': age,
                'frames': len(frames),
                'audio': len(audio),
                'modified': datetime.fromtimestamp(wdir.stat().st_mtime)
            })
    return active

def format_elapsed(ms):
    """Format milliseconds to readable time"""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms/1000:.1f}s"
    else:
        return f"{ms/60000:.1f}m"

def main():
    """Main monitoring loop"""
    print("=" * 70)
    print("  GoodQ Progress Monitor")
    print("=" * 70)
    print("  Watching for active processing...")
    print("  Press Ctrl+C to stop")
    print("=" * 70)
    print()
    
    last_step_count = 0
    step_summary = defaultdict(lambda: {'count': 0, 'total_ms': 0})
    
    try:
        while True:
            # Clear screen (Windows)
            print("\033[2J\033[H", end='')
            
            print(f"=== GoodQ Progress Monitor === {datetime.now().strftime('%H:%M:%S')}\n")
            
            # Show active processing
            active = get_active_processing()
            if active:
                print("📁 Active Processing:")
                for proc in active:
                    print(f"   {proc['dir']}")
                    print(f"   ├─ Frames: {proc['frames']}")
                    print(f"   ├─ Audio: {proc['audio']}")
                    print(f"   └─ Last update: {int(proc['age'])}s ago")
                print()
            else:
                print("📁 No active processing detected\n")
            
            # Show recent steps
            steps = get_recent_steps(15)
            if steps:
                print("📊 Recent Steps:")
                current_asset = None
                for step in steps[-10:]:
                    asset = step.get('asset', '').split('\\')[-1] if step.get('asset') else 'unknown'
                    
                    # Track if we're on a new asset
                    if asset != current_asset:
                        if current_asset:
                            print()
                        current_asset = asset
                        print(f"   📄 {asset}")
                    
                    elapsed = format_elapsed(step.get('elapsed_ms', 0))
                    status = step.get('status', 'unknown')
                    step_name = step.get('step', 'unknown')
                    
                    status_icon = "✓" if status == "ok" else "⏭" if status == "skipped" else "✗"
                    print(f"      {status_icon} {step_name:25} {elapsed:>8} [{status}]")
                
                # Update summary
                new_steps = steps[last_step_count:]
                for step in new_steps:
                    name = step.get('step', 'unknown')
                    step_summary[name]['count'] += 1
                    step_summary[name]['total_ms'] += step.get('elapsed_ms', 0)
                last_step_count = len(steps)
                
                print()
                print(f"📈 Session Summary (last {len(steps)} steps):")
                # Show top 5 slowest steps
                slowest = sorted(step_summary.items(), 
                               key=lambda x: x[1]['total_ms'], 
                               reverse=True)[:5]
                for name, stats in slowest:
                    avg = stats['total_ms'] / stats['count'] if stats['count'] > 0 else 0
                    print(f"   {name:25} {stats['count']:3}x  avg: {format_elapsed(avg):>8}")
                
            else:
                print("📊 No recent steps found")
            
            print()
            print("Refreshing in 5 seconds... (Ctrl+C to stop)")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    main()
