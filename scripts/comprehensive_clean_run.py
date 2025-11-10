#!/usr/bin/env python3
"""
Comprehensive Clean Run Test with Full Monitoring
Author: GoodQ Development Team
Created: 2025-11-07

This script performs a complete clean run test:
1. Stop all running processes
2. Clean all databases and indices
3. Start watchdog with monitoring
4. Track progress with self-healing capabilities
"""

import os
import sys
import time
import json
import psutil
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Configure paths
PROJECT_ROOT = Path("L:/goodq4all")
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_DB = DATA_DIR / "memory.db"
INBOX = PROJECT_ROOT / "import_inbox"
LOGS_DIR = PROJECT_ROOT / "logs"

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class CleanRunMonitor:
    """Comprehensive monitoring and self-healing for clean run"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.watchdog_process = None
        self.last_progress = {}
        self.stall_threshold = 300  # 5 minutes without progress
        self.log_file = LOGS_DIR / f"clean_run_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log"
        
    def log(self, message: str, level: str = "INFO"):
        """Log message to both console and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
    
    def print_header(self, text: str):
        """Print formatted header"""
        border = "=" * 80
        print(f"\n{Colors.CYAN}{border}{Colors.ENDC}")
        print(f"{Colors.CYAN}{text.center(80)}{Colors.ENDC}")
        print(f"{Colors.CYAN}{border}{Colors.ENDC}\n")
    
    def check_inbox(self) -> Tuple[int, float]:
        """Check import_inbox for files"""
        if not INBOX.exists():
            return 0, 0.0
        
        files = list(INBOX.glob("*.mp4"))
        total_size = sum(f.stat().st_size for f in files) / (1024**3)  # GB
        return len(files), total_size
    
    def stop_existing_processes(self):
        """Stop any existing watchdog or ingestion processes"""
        self.print_header("PHASE 1: STOPPING EXISTING PROCESSES")
        
        stopped = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('watchdog' in str(cmd).lower() for cmd in cmdline):
                    if 'python' in proc.info['name'].lower():
                        self.log(f"Stopping watchdog process (PID: {proc.pid})", "INFO")
                        proc.terminate()
                        proc.wait(timeout=10)
                        stopped.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
        
        if stopped:
            self.log(f"Stopped {len(stopped)} process(es)", "SUCCESS")
        else:
            self.log("No existing processes to stop", "INFO")
        
        time.sleep(2)  # Allow cleanup
    
    def clean_databases(self):
        """Clean all databases and create backups"""
        self.print_header("PHASE 2: CLEANING DATABASES")
        
        # Backup memory.db
        if MEMORY_DB.exists():
            backup_path = MEMORY_DB.parent / f"memory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            import shutil
            shutil.copy2(MEMORY_DB, backup_path)
            self.log(f"Created backup: {backup_path.name}", "INFO")
            
            # Clean tables
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            total_deleted = 0
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count_before = cursor.fetchone()[0]
                
                if count_before > 0:
                    cursor.execute(f"DELETE FROM {table}")
                    self.log(f"  Cleared {table}: {count_before} rows", "INFO")
                    total_deleted += count_before
            
            conn.commit()
            conn.close()
            
            self.log(f"Total rows deleted: {total_deleted}", "SUCCESS")
        else:
            self.log("memory.db not found - will be created fresh", "INFO")
        
        # Clean FAISS indices
        faiss_dir = DATA_DIR / "faiss"
        if faiss_dir.exists():
            index_files = list(faiss_dir.glob("**/*.index")) + list(faiss_dir.glob("**/*.pkl"))
            if index_files:
                backup_dir = DATA_DIR / f"faiss_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copytree(faiss_dir, backup_dir)
                self.log(f"Backed up FAISS to: {backup_dir.name}", "INFO")
                
                for idx_file in index_files:
                    idx_file.unlink()
                self.log(f"Removed {len(index_files)} FAISS index files", "SUCCESS")
        
        # Clean processing directory
        processing_dir = DATA_DIR / "processing"
        if processing_dir.exists():
            for item in processing_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            self.log("Cleaned processing directory", "SUCCESS")
    
    def get_database_stats(self) -> Dict:
        """Get current database statistics"""
        if not MEMORY_DB.exists():
            return {}
        
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
    
    def start_watchdog(self):
        """Start the watchdog process"""
        self.print_header("PHASE 3: STARTING WATCHDOG")
        
        watchdog_script = PROJECT_ROOT / "scripts" / "watchdog_ingest.py"
        
        if not watchdog_script.exists():
            self.log(f"ERROR: Watchdog script not found: {watchdog_script}", "ERROR")
            return False
        
        # Start watchdog in background
        try:
            self.watchdog_process = subprocess.Popen(
                [sys.executable, str(watchdog_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
                text=True,
                bufsize=1
            )
            
            self.log(f"Started watchdog (PID: {self.watchdog_process.pid})", "SUCCESS")
            time.sleep(5)  # Allow startup
            
            # Check if still running
            if self.watchdog_process.poll() is None:
                self.log("Watchdog running successfully", "SUCCESS")
                return True
            else:
                stdout, stderr = self.watchdog_process.communicate()
                self.log(f"Watchdog failed to start: {stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Failed to start watchdog: {e}", "ERROR")
            return False
    
    def monitor_progress(self, duration_minutes: int = 60):
        """Monitor ingestion progress with self-healing"""
        self.print_header("PHASE 4: MONITORING PROGRESS")
        
        self.log(f"Monitoring for {duration_minutes} minutes", "INFO")
        self.log(f"Stall threshold: {self.stall_threshold} seconds", "INFO")
        
        start_time = time.time()
        last_check = start_time
        last_stats = self.get_database_stats()
        stall_count = 0
        
        while time.time() - start_time < duration_minutes * 60:
            # Check if watchdog is still running
            if self.watchdog_process and self.watchdog_process.poll() is not None:
                self.log("CRITICAL: Watchdog process terminated!", "ERROR")
                stdout, stderr = self.watchdog_process.communicate()
                self.log(f"Stdout: {stdout[-500:]}", "ERROR")
                self.log(f"Stderr: {stderr[-500:]}", "ERROR")
                
                # Attempt restart
                self.log("Attempting to restart watchdog...", "WARN")
                if self.start_watchdog():
                    stall_count = 0
                else:
                    return False
            
            # Check progress every 30 seconds
            if time.time() - last_check >= 30:
                current_stats = self.get_database_stats()
                elapsed = int(time.time() - start_time)
                
                # Calculate progress
                progress_made = False
                for table, count in current_stats.items():
                    prev_count = last_stats.get(table, 0)
                    if count > prev_count:
                        progress_made = True
                        diff = count - prev_count
                        self.log(f"Progress: {table} +{diff} (total: {count})", "INFO")
                
                # Check for stalls
                if not progress_made and last_stats:
                    stall_count += 1
                    stall_time = stall_count * 30
                    self.log(f"No progress detected ({stall_time}s)", "WARN")
                    
                    if stall_time >= self.stall_threshold:
                        self.log("STALL DETECTED - Investigating...", "ERROR")
                        self.investigate_stall()
                        stall_count = 0  # Reset after investigation
                else:
                    stall_count = 0  # Reset on progress
                
                last_stats = current_stats
                last_check = time.time()
                
                # Print summary
                self.print_summary(elapsed, current_stats)
            
            time.sleep(5)
        
        self.log("Monitoring period complete", "SUCCESS")
        return True
    
    def investigate_stall(self):
        """Investigate why progress has stalled"""
        self.log("Running stall diagnostics...", "INFO")
        
        # Check watchdog log
        watchdog_log = LOGS_DIR / "watchdog.log"
        if watchdog_log.exists():
            with open(watchdog_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_50 = lines[-50:]
                
                # Look for errors
                errors = [l for l in last_50 if 'ERROR' in l or 'Exception' in l]
                if errors:
                    self.log("Found errors in watchdog log:", "ERROR")
                    for err in errors[-5:]:
                        self.log(f"  {err.strip()}", "ERROR")
        
        # Check processing directory
        processing_dir = DATA_DIR / "processing"
        if processing_dir.exists():
            files = list(processing_dir.iterdir())
            if files:
                self.log(f"Found {len(files)} items in processing/", "INFO")
                for f in files[:5]:
                    age = time.time() - f.stat().st_mtime
                    self.log(f"  {f.name} (age: {int(age/60)} min)", "INFO")
        
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        self.log(f"CPU: {cpu_percent}%, Memory: {memory.percent}%", "INFO")
    
    def print_summary(self, elapsed: int, stats: Dict):
        """Print current progress summary"""
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        print(f"\n{Colors.CYAN}{'='*80}{Colors.ENDC}")
        print(f"{Colors.BOLD}Progress Update - Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*80}{Colors.ENDC}")
        
        if stats:
            for table, count in sorted(stats.items()):
                print(f"  {table}: {count} rows")
        else:
            print("  No data yet")
        
        print(f"{Colors.CYAN}{'='*80}{Colors.ENDC}\n")
    
    def cleanup(self):
        """Cleanup and generate final report"""
        self.print_header("CLEANUP AND FINAL REPORT")
        
        if self.watchdog_process and self.watchdog_process.poll() is None:
            self.log("Stopping watchdog...", "INFO")
            self.watchdog_process.terminate()
            try:
                self.watchdog_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.watchdog_process.kill()
        
        # Final stats
        final_stats = self.get_database_stats()
        
        self.log("=" * 80, "INFO")
        self.log("FINAL STATISTICS", "INFO")
        self.log("=" * 80, "INFO")
        
        total_rows = sum(final_stats.values()) if final_stats else 0
        self.log(f"Total rows ingested: {total_rows}", "INFO")
        
        if final_stats:
            for table, count in sorted(final_stats.items()):
                self.log(f"  {table}: {count}", "INFO")
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.log(f"Total runtime: {int(elapsed/60)} minutes", "INFO")
        self.log(f"Log file: {self.log_file}", "INFO")


def main():
    """Execute comprehensive clean run test"""
    monitor = CleanRunMonitor()
    
    try:
        monitor.print_header("COMPREHENSIVE CLEAN RUN TEST")
        monitor.log("Initializing comprehensive clean run test", "INFO")
        
        # Pre-flight checks
        file_count, total_size = monitor.check_inbox()
        monitor.log(f"Files in inbox: {file_count} ({total_size:.2f} GB)", "INFO")
        
        if file_count == 0:
            monitor.log("No files in inbox to process!", "ERROR")
            return 1
        
        # Execute phases
        monitor.stop_existing_processes()
        monitor.clean_databases()
        
        if not monitor.start_watchdog():
            monitor.log("Failed to start watchdog - aborting", "ERROR")
            return 1
        
        # Monitor with self-healing
        success = monitor.monitor_progress(duration_minutes=60)
        
        if success:
            monitor.log("Clean run test completed successfully!", "SUCCESS")
            return 0
        else:
            monitor.log("Clean run test encountered issues", "WARN")
            return 1
            
    except KeyboardInterrupt:
        monitor.log("\nTest interrupted by user", "WARN")
        return 1
    except Exception as e:
        monitor.log(f"Unexpected error: {e}", "ERROR")
        import traceback
        monitor.log(traceback.format_exc(), "ERROR")
        return 1
    finally:
        monitor.cleanup()


if __name__ == "__main__":
    sys.exit(main())
