#!/usr/bin/env python3
"""
Real-time Ingestion Monitor
Monitors the ingestion process and detects stalls or errors
"""
import sqlite3
import time
from pathlib import Path
from datetime import datetime
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import get_runtime_paths, load_configs

_RUNTIME_PATHS = get_runtime_paths(load_configs({}), "watchdog_state_file")
DB_PATH = Path(_RUNTIME_PATHS["db_path"]).resolve()
LOG_PATH = Path(_RUNTIME_PATHS["log_dir"]).resolve() / "watchdog.log"
PROCESSING_PATH = Path(_RUNTIME_PATHS["processing"]).resolve()

class IngestionMonitor:
    def __init__(self):
        self.last_scene_count = 0
        self.last_log_size = 0
        self.stall_counter = 0
        self.max_stall_checks = 10  # 10 checks * 30 seconds = 5 minutes
        
    def get_stats(self):
        """Get current database stats"""
        if not DB_PATH.exists():
            return None
        
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            scene_count = cursor.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
            segment_count = cursor.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
            embedding_count = cursor.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            
            # Get latest scene if exists
            latest_scene = None
            if scene_count > 0:
                cursor.execute("SELECT id FROM scenes ORDER BY id DESC LIMIT 1")
                latest_scene = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "scenes": scene_count,
                "segments": segment_count,
                "embeddings": embedding_count,
                "latest_scene": latest_scene
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return None
    
    def get_log_tail(self, lines=10):
        """Get last N lines from log"""
        if not LOG_PATH.exists():
            return []
        
        try:
            with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception as e:
            print(f"Error reading log: {e}")
            return []
    
    def check_processing_activity(self):
        """Check if processing directory shows activity"""
        if not PROCESSING_PATH.exists():
            return {"active": False, "files": 0}
        
        files = list(PROCESSING_PATH.rglob("*"))
        file_count = len([f for f in files if f.is_file()])
        
        # Check if files have been modified recently
        recent_activity = False
        if files:
            latest_mtime = max(f.stat().st_mtime for f in files if f.is_file())
            time_since_mod = time.time() - latest_mtime
            recent_activity = time_since_mod < 300  # Within last 5 minutes
        
        return {
            "active": file_count > 0,
            "files": file_count,
            "recent_activity": recent_activity
        }
    
    def detect_stall(self, stats):
        """Detect if ingestion has stalled"""
        # Check if scene count changed
        if stats and stats["scenes"] > self.last_scene_count:
            self.stall_counter = 0
            self.last_scene_count = stats["scenes"]
            return False
        
        # Check if log file grew
        if LOG_PATH.exists():
            current_size = LOG_PATH.stat().st_size
            if current_size > self.last_log_size:
                self.stall_counter = 0
                self.last_log_size = current_size
                return False
        
        # Check processing activity
        proc_status = self.check_processing_activity()
        if proc_status["recent_activity"]:
            self.stall_counter = 0
            return False
        
        # Increment stall counter
        self.stall_counter += 1
        
        if self.stall_counter >= self.max_stall_checks:
            return True
        
        return False
    
    def print_status(self, stats, iteration):
        """Print formatted status"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 80)
        print(f"  GoodQ4All - Real-Time Ingestion Monitor")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Check: #{iteration} (every 30 seconds)")
        print()
        
        if stats:
            print("DATABASE STATS:")
            print(f"  ├─ Scenes:     {stats['scenes']:,}")
            print(f"  ├─ Segments:   {stats['segments']:,}")
            print(f"  ├─ Embeddings: {stats['embeddings']:,}")
            print(f"  └─ Latest Scene ID: {stats['latest_scene']}")
        else:
            print("DATABASE: Not available or empty")
        
        print()
        proc_status = self.check_processing_activity()
        print("PROCESSING STATUS:")
        print(f"  ├─ Active: {'Yes' if proc_status['active'] else 'No'}")
        print(f"  ├─ Files in processing: {proc_status['files']}")
        print(f"  └─ Recent activity: {'Yes' if proc_status['recent_activity'] else 'No'}")
        
        print()
        print("RECENT LOG ENTRIES:")
        log_lines = self.get_log_tail(8)
        for line in log_lines:
            print(f"  {line.rstrip()}")
        
        print()
        if self.stall_counter > 0:
            print(f"[WARN]  WARNING: No progress detected for {self.stall_counter * 30} seconds")
            print(f"   ({self.max_stall_checks - self.stall_counter} checks until stall alert)")
        else:
            print("[OK] System is processing normally")
        
        print()
        print("=" * 80)
        print("Press Ctrl+C to stop monitoring")
        print("=" * 80)
    
    def run(self, interval=30):
        """Run the monitor"""
        print("Starting GoodQ4All Ingestion Monitor...")
        print(f"Monitoring interval: {interval} seconds")
        print()
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                stats = self.get_stats()
                self.print_status(stats, iteration)
                
                # Check for stall
                if self.detect_stall(stats):
                    print("\n" + "!" * 80)
                    print("ALERT: Ingestion appears to have STALLED!")
                    print(f"No progress detected for {self.stall_counter * 30} seconds")
                    print("!" * 80)
                    
                    # Show extended log
                    print("\nExtended log (last 20 lines):")
                    for line in self.get_log_tail(20):
                        print(f"  {line.rstrip()}")
                    
                    response = input("\nContinue monitoring? (y/n): ")
                    if response.lower() != 'y':
                        print("Monitoring stopped by user.")
                        break
                    else:
                        self.stall_counter = 0  # Reset counter
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user.")
        except Exception as e:
            print(f"\n\nError during monitoring: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    monitor = IngestionMonitor()
    
    # Allow custom interval from command line
    interval = 30
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except ValueError:
            print(f"Invalid interval: {sys.argv[1]}, using default 30 seconds")
    
    monitor.run(interval)
