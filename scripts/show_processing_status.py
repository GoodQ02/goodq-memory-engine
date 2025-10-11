#!/usr/bin/env python3
"""
Quick Processing Status - Shows current pipeline activity
"""
import json
from pathlib import Path
from datetime import datetime

def get_latest_log_activity():
    """Get latest activity from logs"""
    log_dir = Path("L:/goodq4all/logs")
    
    # Get latest workspace
    workspaces = sorted([d for d in log_dir.glob("watchdog_*") if d.is_dir()],
                       key=lambda x: x.stat().st_mtime, reverse=True)
    
    if workspaces:
        latest = workspaces[0]
        print(f"📂 Current Workspace: {latest.name}")
        print(f"   Created: {datetime.fromtimestamp(latest.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Count scenes
        video_dirs = list(latest.iterdir())
        if video_dirs:
            for vdir in video_dirs[:3]:  # Show first 3 videos
                if vdir.is_dir():
                    frames = list((vdir / "frames").glob("*.jpg")) if (vdir / "frames").exists() else []
                    audio = list((vdir / "audio").glob("*.wav")) if (vdir / "audio").exists() else []
                    print(f"   📹 {vdir.name}")
                    print(f"      Frames: {len(frames)}, Audio clips: {len(audio)}")
    
    # Check step logs
    step_log = log_dir / "steps.jsonl"
    if step_log.exists():
        with open(step_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                print(f"\n🔧 Recent Pipeline Steps:")
                for line in lines[-5:]:
                    try:
                        data = json.loads(line)
                        print(f"   [{data.get('env', 'unknown')}] {data.get('step', 'unknown')}: {data.get('status', 'unknown')}")
                    except:
                        pass

def main():
    print("\n" + "="*70)
    print("  🚀 GoodQ Processing Status")
    print("="*70)
    print()
    
    # Files in processing
    processing = Path("L:/goodq4all/data/processing")
    if processing.exists():
        files = list(processing.glob("*"))
        if files:
            print(f"⚙️  Currently Processing: {len(files)} file(s)")
            for f in files:
                if f.is_file():
                    size_mb = f.stat().st_size / (1024*1024)
                    print(f"   • {f.name} ({size_mb:.1f} MB)")
            print()
    
    # Latest activity
    get_latest_log_activity()
    
    print("\n" + "="*70)
    print()

if __name__ == '__main__':
    main()
