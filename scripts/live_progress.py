"""
GoodQ Live Progress Monitor
Real-time ingestion progress with scene-by-scene updates
"""
import time
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path("L:/goodq4all/data/memory.db")
STEP_LOG = Path("L:/goodq4all/data/step_log.jsonl")
WORKSPACES = Path("L:/goodq4all/logs")

def clear_screen():
    """Clear the console"""
    print("\033[2J\033[H", end="")

def get_db_stats():
    """Get current database statistics"""
    if not DB_PATH.exists():
        return None
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Get scene count
        c.execute("SELECT COUNT(*) FROM scenes")
        scene_count = c.fetchone()[0]
        
        # Get embedding counts by modality
        c.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
        embeddings = dict(c.fetchall())
        
        # Get link count
        c.execute("SELECT COUNT(*) FROM links")
        link_count = c.fetchone()[0]
        
        conn.close()
        
        return {
            'scenes': scene_count,
            'embeddings': embeddings,
            'links': link_count
        }
    except Exception as e:
        return {'error': str(e)}

def get_recent_steps(n=10):
    """Get the most recent step log entries"""
    if not STEP_LOG.exists():
        return []
    
    try:
        with open(STEP_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent = lines[-n:] if len(lines) >= n else lines
            
            steps = []
            for line in recent:
                try:
                    entry = json.loads(line.strip())
                    steps.append(entry)
                except:
                    continue
            
            return steps
    except Exception as e:
        return []

def get_workspace_progress():
    """Get progress from workspace directories"""
    if not WORKSPACES.exists():
        return {}
    
    workspaces = sorted(WORKSPACES.glob("watchdog_*"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not workspaces:
        return {}
    
    latest = workspaces[0]
    
    # Find the video directory (should be the only non-results.json item)
    video_dirs = [d for d in latest.iterdir() if d.is_dir()]
    
    if not video_dirs:
        return {'workspace': latest.name, 'status': 'initializing'}
    
    video_dir = video_dirs[0]
    frames_dir = video_dir / "frames"
    audio_dir = video_dir / "audio"
    
    frame_count = len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0
    audio_count = len(list(audio_dir.glob("*.wav"))) if audio_dir.exists() else 0
    
    return {
        'workspace': latest.name,
        'video': video_dir.name,
        'frames': frame_count,
        'audio': audio_count,
        'last_modified': datetime.fromtimestamp(latest.stat().st_mtime)
    }

def format_step(step):
    """Format a step entry for display"""
    timestamp = step.get('timestamp', '').split('T')[1].split('.')[0] if 'timestamp' in step else '??:??:??'
    env = step.get('env', 'unknown').replace('goodq_', '')
    step_name = step.get('step', 'unknown')
    duration_ms = step.get('duration_ms', 0)
    status = step.get('status', 'unknown')
    
    # Color code by status
    if status == 'ok':
        status_icon = '✓'
        status_color = '\033[32m'  # Green
    elif status == 'skipped':
        status_icon = '⊘'
        status_color = '\033[33m'  # Yellow
    elif status == 'error':
        status_icon = '✗'
        status_color = '\033[31m'  # Red
    else:
        status_icon = '?'
        status_color = '\033[37m'  # White
    
    reset = '\033[0m'
    
    # Format duration
    if duration_ms < 1000:
        duration_str = f"{duration_ms:.0f}ms"
    else:
        duration_str = f"{duration_ms/1000:.1f}s"
    
    return f"  [{timestamp}] {status_color}{status_icon}{reset} {step_name:<25} {duration_str:>8}  ({env})"

def main():
    """Main monitoring loop"""
    print("\033[?25l")  # Hide cursor
    
    try:
        while True:
            clear_screen()
            
            # Header
            now = datetime.now().strftime("%H:%M:%S")
            print("╔" + "═" * 68 + "╗")
            print("║" + f" 🎬 GoodQ LIVE Progress Monitor".center(68) + "║")
            print("║" + f" {now}".center(68) + "║")
            print("╚" + "═" * 68 + "╝")
            print()
            
            # Workspace progress
            workspace = get_workspace_progress()
            if workspace:
                print("📂 Current Mission:")
                print(f"   Video: {workspace.get('video', 'N/A')}")
                print(f"   Workspace: {workspace.get('workspace', 'N/A')}")
                print(f"   Frames extracted: {workspace.get('frames', 0)}")
                print(f"   Audio clips: {workspace.get('audio', 0)}")
                
                if 'last_modified' in workspace:
                    elapsed = datetime.now() - workspace['last_modified']
                    if elapsed.total_seconds() < 30:
                        print(f"   Status: 🟢 ACTIVE (last update {int(elapsed.total_seconds())}s ago)")
                    else:
                        print(f"   Status: 🟡 IDLE ({int(elapsed.total_seconds())}s since last activity)")
                print()
            
            # Database stats
            db_stats = get_db_stats()
            if db_stats and 'error' not in db_stats:
                print("💾 Intelligence Database:")
                print(f"   Scenes analyzed: {db_stats['scenes']}")
                print(f"   Knowledge links: {db_stats['links']}")
                
                if db_stats['embeddings']:
                    print("   Embeddings by modality:")
                    for modality, count in sorted(db_stats['embeddings'].items()):
                        print(f"     {modality}: {count}")
                print()
            
            # Recent steps
            recent = get_recent_steps(12)
            if recent:
                print("⚡ Recent Operations:")
                for step in recent:
                    print(format_step(step))
                print()
            
            # Footer
            print("─" * 70)
            print("Press Ctrl+C to stop monitoring")
            
            # Wait before refresh
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\033[?25h")  # Show cursor
        print("\n\n✓ Monitoring stopped")
    except Exception as e:
        print("\033[?25h")  # Show cursor
        print(f"\n\nError: {e}")

if __name__ == "__main__":
    main()
