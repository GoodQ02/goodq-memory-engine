#!/usr/bin/env python3
"""
GoodQ4All Process Manager
Centralized control for all system components with proper lifecycle management.
"""

import sys
import os
import json
import time
import psutil
import signal
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Import centralized path configuration
from configs.python_paths import get_conda_exe, get_env_python

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('L:/goodq4all/logs/process_manager.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path("L:/goodq4all")
LOGS_DIR = BASE_DIR / "logs"
PID_DIR = LOGS_DIR / "pids"
STATE_FILE = LOGS_DIR / "process_state.json"

# Ensure directories exist
PID_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class ProcessInfo:
    """Information about a managed process"""
    def __init__(self, name: str, command: List[str], cwd: Path, env: Optional[Dict] = None):
        self.name = name
        self.command = command
        self.cwd = cwd
        self.env = env or os.environ.copy()
        self.pid: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.started_at: Optional[datetime] = None
        self.log_file: Optional[Path] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            'name': self.name,
            'command': self.command,
            'cwd': str(self.cwd),
            'pid': self.pid,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'log_file': str(self.log_file) if self.log_file else None,
            'status': self.get_status()
        }
    
    def get_status(self) -> str:
        """Get current process status"""
        if not self.pid:
            return 'stopped'
        
        try:
            p = psutil.Process(self.pid)
            if p.is_running():
                return 'running'
            else:
                return 'stopped'
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 'stopped'
    
    def is_running(self) -> bool:
        """Check if process is running"""
        return self.get_status() == 'running'


class ProcessManager:
    """Manages all GoodQ4All processes"""
    
    def __init__(self):
        self.processes: Dict[str, ProcessInfo] = {}
        self.load_state()
        
    def load_state(self):
        """Load previous state"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    for name, info in data.items():
                        # Verify if process is still running
                        pid = info.get('pid')
                        if pid and self._is_pid_running(pid):
                            logger.info(f"Found running process: {name} (PID {pid})")
                            # Don't recreate process object, just track it
                            proc_info = ProcessInfo(
                                name=info['name'],
                                command=info['command'],
                                cwd=Path(info['cwd'])
                            )
                            proc_info.pid = pid
                            proc_info.started_at = datetime.fromisoformat(info['started_at']) if info.get('started_at') else None
                            proc_info.log_file = Path(info['log_file']) if info.get('log_file') else None
                            self.processes[name] = proc_info
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
    
    def save_state(self):
        """Save current state"""
        try:
            data = {name: proc.to_dict() for name, proc in self.processes.items()}
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _is_pid_running(self, pid: int) -> bool:
        """Check if PID is running"""
        try:
            p = psutil.Process(pid)
            return p.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def register_process(self, name: str, command: List[str], cwd: Path, env: Optional[Dict] = None):
        """Register a process definition"""
        self.processes[name] = ProcessInfo(name, command, cwd, env)
        logger.info(f"Registered process: {name}")
    
    def start(self, name: str) -> bool:
        """Start a process"""
        if name not in self.processes:
            logger.error(f"Process not registered: {name}")
            return False
        
        proc_info = self.processes[name]
        
        # Check if already running
        if proc_info.is_running():
            logger.warning(f"Process already running: {name} (PID {proc_info.pid})")
            return True
        
        # Setup log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"{name}_{timestamp}.log"
        proc_info.log_file = log_file
        
        try:
            # Open log file
            log_handle = open(log_file, 'w', encoding='utf-8')
            
            # Start process
            logger.info(f"Starting {name}...")
            logger.debug(f"Command: {' '.join(proc_info.command)}")
            logger.debug(f"CWD: {proc_info.cwd}")
            logger.debug(f"Log: {log_file}")
            
            process = subprocess.Popen(
                proc_info.command,
                cwd=proc_info.cwd,
                env=proc_info.env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            proc_info.process = process
            proc_info.pid = process.pid
            proc_info.started_at = datetime.now()
            
            # Write PID file
            pid_file = PID_DIR / f"{name}.pid"
            with open(pid_file, 'w') as f:
                f.write(str(process.pid))
            
            logger.info(f"[SYMBOL] Started {name} (PID {process.pid})")
            self.save_state()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")
            return False
    
    def stop(self, name: str, timeout: int = 30) -> bool:
        """Stop a process"""
        if name not in self.processes:
            logger.error(f"Process not registered: {name}")
            return False
        
        proc_info = self.processes[name]
        
        if not proc_info.pid:
            logger.warning(f"Process not running: {name}")
            return True
        
        try:
            logger.info(f"Stopping {name} (PID {proc_info.pid})...")
            
            # Get psutil process
            process = psutil.Process(proc_info.pid)
            
            # Try graceful shutdown first
            if sys.platform == 'win32':
                # On Windows, send CTRL_BREAK_EVENT
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            
            # Wait for process to exit
            try:
                process.wait(timeout=timeout)
                logger.info(f"[SYMBOL] Stopped {name}")
            except psutil.TimeoutExpired:
                logger.warning(f"Process {name} did not stop gracefully, killing...")
                process.kill()
                process.wait(timeout=5)
                logger.info(f"[SYMBOL] Killed {name}")
            
            # Clean up
            proc_info.pid = None
            proc_info.process = None
            proc_info.started_at = None
            
            # Remove PID file
            pid_file = PID_DIR / f"{name}.pid"
            pid_file.unlink(missing_ok=True)
            
            self.save_state()
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Process {name} already stopped or inaccessible: {e}")
            proc_info.pid = None
            proc_info.process = None
            self.save_state()
            return True
        except Exception as e:
            logger.error(f"Failed to stop {name}: {e}")
            return False
    
    def restart(self, name: str) -> bool:
        """Restart a process"""
        logger.info(f"Restarting {name}...")
        self.stop(name)
        time.sleep(2)  # Brief pause
        return self.start(name)
    
    def status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get status of processes"""
        if name:
            if name not in self.processes:
                return {'error': f'Process not found: {name}'}
            return self.processes[name].to_dict()
        else:
            return {name: proc.to_dict() for name, proc in self.processes.items()}
    
    def stop_all(self):
        """Stop all processes"""
        logger.info("Stopping all processes...")
        for name in list(self.processes.keys()):
            self.stop(name)
        logger.info("All processes stopped")
    
    def get_logs(self, name: str, lines: int = 100) -> List[str]:
        """Get recent log lines for a process"""
        if name not in self.processes:
            return [f"Process not found: {name}"]
        
        proc_info = self.processes[name]
        if not proc_info.log_file or not proc_info.log_file.exists():
            return ["No log file available"]
        
        try:
            with open(proc_info.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception as e:
            return [f"Error reading log: {e}"]


def create_goodq_manager() -> ProcessManager:
    """Create process manager with GoodQ4All components"""
    manager = ProcessManager()
    
    # Get paths from centralized configuration
    conda_exe = get_conda_exe()
    python_exe = get_env_python('goodq_zenml')
    
    # API Server
    manager.register_process(
        name='api_server',
        command=[str(python_exe), 'api_server.py'],
        cwd=BASE_DIR
    )
    
    # Watchdog
    manager.register_process(
        name='watchdog',
        command=[str(python_exe), 'scripts/watchdog_ingest.py'],
        cwd=BASE_DIR
    )
    
    # Analytics Dashboard (optional)
    manager.register_process(
        name='analytics',
        command=[str(python_exe), 'analytics_dashboard.py'],
        cwd=BASE_DIR
    )
    
    return manager


def main():
    """Main CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GoodQ4All Process Manager')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'logs', 'stop-all', 'start-all'],
                       help='Action to perform')
    parser.add_argument('process', nargs='?', help='Process name (api_server, watchdog, analytics)')
    parser.add_argument('--lines', type=int, default=100, help='Number of log lines to show')
    
    args = parser.parse_args()
    
    manager = create_goodq_manager()
    
    if args.action == 'start':
        if not args.process:
            print("Error: process name required for start")
            sys.exit(1)
        success = manager.start(args.process)
        sys.exit(0 if success else 1)
    
    elif args.action == 'stop':
        if not args.process:
            print("Error: process name required for stop")
            sys.exit(1)
        success = manager.stop(args.process)
        sys.exit(0 if success else 1)
    
    elif args.action == 'restart':
        if not args.process:
            print("Error: process name required for restart")
            sys.exit(1)
        success = manager.restart(args.process)
        sys.exit(0 if success else 1)
    
    elif args.action == 'status':
        status = manager.status(args.process)
        print(json.dumps(status, indent=2))
    
    elif args.action == 'logs':
        if not args.process:
            print("Error: process name required for logs")
            sys.exit(1)
        logs = manager.get_logs(args.process, args.lines)
        for line in logs:
            print(line, end='')
    
    elif args.action == 'stop-all':
        manager.stop_all()
    
    elif args.action == 'start-all':
        for name in ['api_server', 'watchdog']:
            manager.start(name)


if __name__ == '__main__':
    main()
