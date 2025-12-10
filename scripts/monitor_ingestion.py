#!/usr/bin/env python3
"""
Real-time Ingestion Monitor with Alerting
Watches for stalls and unexpected errors during ingestion
"""

import time
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

PROJECT_ROOT = Path("L:/goodq4all")
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_DB = DATA_DIR / "memory.db"
LOGS_DIR = PROJECT_ROOT / "logs"

class IngestionMonitor:
    def __init__(self, check_interval: int = 30, stall_threshold: int = 300):
        self.check_interval = check_interval
        self.stall_threshold = stall_threshold
        self.last_stats = {}
        self.last_progress_time = time.time()
        self.start_time = time.time()
        
    def get_stats(self) -> Dict[str, int]:
        """Get current database statistics"""
        if not MEMORY_DB.exists():
            return {}
        
        try:
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            
            stats = {}
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            conn.close()
            return stats
        except Exception as e:
            print(f"[ERROR] Failed to read database: {e}")
            return {}
    
    def check_watchdog_log(self) -> Optional[str]:
        """Check watchdog log for recent errors"""
        watchdog_log = LOGS_DIR / "watchdog.log"
        if not watchdog_log.exists():
            return None
        
        try:
            with open(watchdog_log, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent = lines[-50:]
                
                errors = [l.strip() for l in recent if 'ERROR' in l or 'Exception' in l or 'Traceback' in l]
                if errors:
                    return '\n'.join(errors[-3:])
        except Exception as e:
            return f"Failed to read log: {e}"
        
        return None
    
    def calculate_progress_rate(self, stats: Dict[str, int]) -> float:
        """Calculate rows per minute"""
        if not self.last_stats:
            return 0.0
        
        total_now = sum(stats.values())
        total_before = sum(self.last_stats.values())
        rows_added = total_now - total_before
        
        time_diff = (time.time() - self.last_progress_time) / 60  # minutes
        if time_diff > 0:
            return rows_added / time_diff
        return 0.0
    
    def monitor(self):
        """Main monitoring loop"""
        print("=" * 80)
        print("INGESTION MONITOR STARTED".center(80))
        print("=" * 80)
        print(f"Check interval: {self.check_interval}s")
        print(f"Stall threshold: {self.stall_threshold}s")
        print("=" * 80)
        print()
        
        stall_time = 0
        
        while True:
            try:
                stats = self.get_stats()
                current_time = time.time()
                elapsed = int(current_time - self.start_time)
                
                # Check for progress
                progress_made = False
                if stats and self.last_stats:
                    for table, count in stats.items():
                        prev_count = self.last_stats.get(table, 0)
                        if count > prev_count:
                            progress_made = True
                            break
                elif stats and not self.last_stats:
                    progress_made = True
                
                # Update stall tracking
                if progress_made:
                    stall_time = 0
                    self.last_progress_time = current_time
                    rate = self.calculate_progress_rate(stats)
                    
                    # Print progress
                    hours = elapsed // 3600
                    minutes = (elapsed % 3600) // 60
                    seconds = elapsed % 60
                    
                    print(f"\n[{hours:02d}:{minutes:02d}:{seconds:02d}] [SYMBOL] PROGRESS DETECTED")
                    print(f"  Rate: {rate:.1f} rows/minute")
                    
                    for table, count in sorted(stats.items()):
                        prev_count = self.last_stats.get(table, 0)
                        diff = count - prev_count
                        if diff > 0:
                            print(f"  {table}: {count} (+{diff})")
                        else:
                            print(f"  {table}: {count}")
                    
                    self.last_stats = stats
                else:
                    stall_time += self.check_interval
                    
                    if stall_time >= self.stall_threshold:
                        print(f"\n[{elapsed}s] [SYMBOL] ALERT: STALL DETECTED ({stall_time}s without progress)")
                        
                        # Check for errors
                        errors = self.check_watchdog_log()
                        if errors:
                            print("\n[ERROR LOG]")
                            print(errors)
                        
                        print("\n[INVESTIGATION REQUIRED]")
                        print(f"  Last progress: {int(current_time - self.last_progress_time)}s ago")
                        
                        # Check processing directory
                        processing_dir = DATA_DIR / "processing"
                        if processing_dir.exists():
                            files = list(processing_dir.iterdir())
                            if files:
                                print(f"  Files in processing/: {len(files)}")
                                for f in files[:3]:
                                    age = int((time.time() - f.stat().st_mtime) / 60)
                                    print(f"    - {f.name} (age: {age} min)")
                        
                        stall_time = 0  # Reset after alerting
                    elif stall_time >= 60:
                        print(f"\n[{elapsed}s] ⏱ No progress for {stall_time}s...")
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n\nMonitor stopped by user")
                break
            except Exception as e:
                print(f"\n[ERROR] Monitor exception: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = IngestionMonitor(check_interval=30, stall_threshold=300)
    monitor.monitor()
