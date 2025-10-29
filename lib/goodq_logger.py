#!/usr/bin/env python3
"""
GoodQ Mission Logger - Q-Styled Logging for Secret Agent Operations
Branded logging system with progress tracking aligned with GoodQ's mission identity
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from contextlib import contextmanager

try:
    from tqdm import tqdm
    from tqdm.contrib.logging import logging_redirect_tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None
    logging_redirect_tqdm = None

# Mission-aligned color codes
class MissionColors:
    """Q Branch approved color scheme"""
    # Status colors
    SUCCESS = '\033[92m'      # Green - Mission accomplished
    WARNING = '\033[93m'      # Yellow - Proceed with caution
    ERROR = '\033[91m'        # Red - Mission compromised
    INFO = '\033[96m'         # Cyan - Intelligence briefing
    DEBUG = '\033[90m'        # Gray - Technical details
    
    # Special operations
    CLASSIFIED = '\033[95m'   # Magenta - Classified intel
    GADGET = '\033[94m'       # Blue - Q Branch tech
    AGENT = '\033[97m'        # Bright white - Agent activity
    
    # Emphasis
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    # Mission symbols (ASCII-safe for Windows console)
    SYMBOLS = {
        'agent': '007',
        'target': '[TARGET]',
        'mission': '[MISSION]',
        'intel': '[INTEL]',
        'gadget': '[Q-TECH]',
        'status': '[STATUS]',
        'success': '[SUCCESS]',
        'fail': '[FAILED]',
        'warning': '[CAUTION]',
        'classified': '[CLASSIFIED]',
        'progress': '[IN PROGRESS]',
        'complete': '[COMPLETE]',
    }


class MissionFormatter(logging.Formatter):
    """Q Branch approved log formatter"""
    
    LEVEL_SYMBOLS = {
        logging.DEBUG: MissionColors.SYMBOLS['intel'],
        logging.INFO: MissionColors.SYMBOLS['status'],
        logging.WARNING: MissionColors.SYMBOLS['warning'],
        logging.ERROR: MissionColors.SYMBOLS['fail'],
        logging.CRITICAL: MissionColors.SYMBOLS['classified'],
    }
    
    LEVEL_COLORS = {
        logging.DEBUG: MissionColors.DEBUG,
        logging.INFO: MissionColors.INFO,
        logging.WARNING: MissionColors.WARNING,
        logging.ERROR: MissionColors.ERROR,
        logging.CRITICAL: MissionColors.CLASSIFIED,
    }
    
    def __init__(self, colored: bool = True, mission_style: bool = True):
        super().__init__()
        self.colored = colored
        self.mission_style = mission_style
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with mission styling"""
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Get mission symbol and color
        symbol = self.LEVEL_SYMBOLS.get(record.levelno, '[LOG]')
        color = self.LEVEL_COLORS.get(record.levelno, '')
        
        # Build message
        if self.mission_style:
            # Q Branch style: [HH:MM:SS] [SYMBOL] Component: Message
            component = getattr(record, 'component', record.name.split('.')[-1])
            base_msg = f"[{timestamp}] {symbol} {component}: {record.getMessage()}"
        else:
            # Standard style with timestamp
            base_msg = f"[{timestamp}] [{record.levelname}] {record.getMessage()}"
        
        # Apply color if enabled
        if self.colored and color:
            return f"{color}{base_msg}{MissionColors.END}"
        return base_msg


class GoodQLogger:
    """
    GoodQ Mission Logger - Your Q Branch Technical Support
    
    Provides mission-styled logging with progress tracking, aligned with GoodQ's
    secret agent identity. Because every AI operation deserves proper tradecraft.
    """
    
    def __init__(
        self,
        name: str,
        log_file: Optional[Path] = None,
        level: int = logging.INFO,
        console: bool = True,
        mission_style: bool = True,
        component: Optional[str] = None
    ):
        """
        Initialize mission logger
        
        Args:
            name: Logger name (usually module name)
            log_file: Optional file path for log output
            level: Logging level
            console: Enable console output
            mission_style: Use Q Branch styling
            component: Component name for mission logs (e.g., 'Audio Intel', 'Vision Systems')
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False  # Don't propagate to root
        
        self.component = component or name.split('.')[-1]
        self.mission_style = mission_style
        self._progress_bars: Dict[str, Any] = {}
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(MissionFormatter(colored=True, mission_style=mission_style))
            self.logger.addHandler(console_handler)
        
        # File handler (always uncolored, detailed format)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)  # Always capture debug in files
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(file_handler)
    
    def _log_with_component(self, level: int, msg: str, **kwargs):
        """Log with component context"""
        extra = kwargs.get('extra', {})
        extra['component'] = self.component
        kwargs['extra'] = extra
        self.logger.log(level, msg, **kwargs)
    
    # Mission-styled logging methods
    def mission_start(self, mission_name: str):
        """Log mission start"""
        self._log_with_component(
            logging.INFO,
            f"{MissionColors.SYMBOLS['mission']} Mission '{mission_name}' initiated"
        )
    
    def mission_complete(self, mission_name: str, duration: Optional[float] = None):
        """Log mission completion"""
        duration_str = f" [Duration: {duration:.2f}s]" if duration else ""
        self._log_with_component(
            logging.INFO,
            f"{MissionColors.SYMBOLS['success']} Mission '{mission_name}' complete{duration_str}"
        )
    
    def agent_action(self, action: str, details: Optional[str] = None):
        """Log agent action"""
        msg = f"{MissionColors.SYMBOLS['agent']} {action}"
        if details:
            msg += f" - {details}"
        self._log_with_component(logging.INFO, msg)
    
    def intel_received(self, intel_type: str, details: str):
        """Log intelligence received"""
        self._log_with_component(
            logging.INFO,
            f"{MissionColors.SYMBOLS['intel']} {intel_type}: {details}"
        )
    
    def gadget_deployed(self, gadget: str, status: str = "active"):
        """Log Q Branch gadget deployment"""
        self._log_with_component(
            logging.INFO,
            f"{MissionColors.SYMBOLS['gadget']} {gadget} - Status: {status}"
        )
    
    def target_acquired(self, target: str, confidence: Optional[float] = None):
        """Log target acquisition"""
        conf_str = f" [Confidence: {confidence:.1%}]" if confidence else ""
        self._log_with_component(
            logging.INFO,
            f"{MissionColors.SYMBOLS['target']} Target acquired: {target}{conf_str}"
        )
    
    def classified(self, msg: str):
        """Log classified information"""
        self._log_with_component(
            logging.WARNING,
            f"{MissionColors.SYMBOLS['classified']} {msg}"
        )
    
    # Standard logging methods (Q Branch approved)
    def debug(self, msg: str):
        """Technical details for Q Branch engineers"""
        self._log_with_component(logging.DEBUG, msg)
    
    def info(self, msg: str):
        """Mission status update"""
        self._log_with_component(logging.INFO, msg)
    
    def warning(self, msg: str):
        """Proceed with caution"""
        self._log_with_component(logging.WARNING, msg)
    
    def error(self, msg: str):
        """Mission compromised"""
        self._log_with_component(logging.ERROR, msg)
    
    def critical(self, msg: str):
        """Critical mission failure"""
        self._log_with_component(logging.CRITICAL, msg)
    
    # Progress tracking (Q Branch style)
    def create_progress(
        self,
        task_id: str,
        total: int,
        desc: str,
        unit: str = "items"
    ) -> Optional[Any]:
        """
        Create mission progress tracker
        
        Args:
            task_id: Unique task identifier
            total: Total items to process
            desc: Task description (e.g., "Analyzing Intel", "Extracting Frames")
            unit: Unit name for progress
            
        Returns:
            Progress bar object or None if tqdm unavailable
        """
        if not TQDM_AVAILABLE:
            self.info(f"{desc}: 0/{total} {unit}")
            return None
        
        # Close existing progress bar if any
        if task_id in self._progress_bars:
            self._progress_bars[task_id].close()
        
        progress_bar = tqdm(
            total=total,
            desc=f"{MissionColors.SYMBOLS['progress']} {desc}",
            unit=unit,
            ncols=80,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
            file=sys.stdout
        )
        
        self._progress_bars[task_id] = progress_bar
        return progress_bar
    
    def update_progress(self, task_id: str, n: int = 1):
        """Update mission progress"""
        if task_id in self._progress_bars:
            self._progress_bars[task_id].update(n)
    
    def complete_progress(self, task_id: str):
        """Complete mission progress tracking"""
        if task_id in self._progress_bars:
            progress_bar = self._progress_bars.pop(task_id)
            progress_bar.close()
            # Log completion
            self.info(f"{MissionColors.SYMBOLS['complete']} {progress_bar.desc.split('] ')[-1]} completed")
    
    @contextmanager
    def mission_phase(self, phase_name: str):
        """
        Context manager for mission phases with timing
        
        Usage:
            with logger.mission_phase("Intelligence Gathering"):
                # ... gather intelligence
                pass
        """
        start_time = time.time()
        self.info(f">>> Phase: {phase_name}")
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.info(f"<<< Phase: {phase_name} [{duration:.2f}s]")
    
    @contextmanager
    def redirect_tqdm_logging(self):
        """Redirect logging through tqdm to prevent progress bar interference"""
        if TQDM_AVAILABLE and logging_redirect_tqdm:
            with logging_redirect_tqdm():
                yield
        else:
            yield
    
    def close_all_progress(self):
        """Close all active progress bars"""
        for task_id in list(self._progress_bars.keys()):
            self.complete_progress(task_id)


# Factory function for easy logger creation
def get_goodq_logger(
    name: str,
    component: Optional[str] = None,
    log_dir: Optional[Path] = None,
    level: int = logging.INFO
) -> GoodQLogger:
    """
    Get or create a GoodQ mission logger
    
    Args:
        name: Logger name (usually __name__)
        component: Component name for mission logs (e.g., 'Video Analysis', 'Audio Intel')
        log_dir: Optional log directory (defaults to L:/goodq4all/logs)
        level: Logging level
        
    Returns:
        GoodQLogger instance
    """
    if log_dir is None:
        log_dir = Path("L:/goodq4all/logs")
    
    # Create log file based on component or name
    log_file = log_dir / f"{component or name.replace('.', '_')}.log"
    
    return GoodQLogger(
        name=name,
        log_file=log_file,
        level=level,
        component=component,
        mission_style=True
    )


# Convenience functions for quick logging
class QuickMission:
    """Quick mission logging without creating logger instance"""
    
    @staticmethod
    def start(name: str):
        print(f"{MissionColors.INFO}[{datetime.now().strftime('%H:%M:%S')}] {MissionColors.SYMBOLS['mission']} Mission '{name}' initiated{MissionColors.END}")
    
    @staticmethod
    def success(msg: str):
        print(f"{MissionColors.SUCCESS}[{datetime.now().strftime('%H:%M:%S')}] {MissionColors.SYMBOLS['success']} {msg}{MissionColors.END}")
    
    @staticmethod
    def fail(msg: str):
        print(f"{MissionColors.ERROR}[{datetime.now().strftime('%H:%M:%S')}] {MissionColors.SYMBOLS['fail']} {msg}{MissionColors.END}")
    
    @staticmethod
    def status(msg: str):
        print(f"{MissionColors.INFO}[{datetime.now().strftime('%H:%M:%S')}] {MissionColors.SYMBOLS['status']} {msg}{MissionColors.END}")


# Module-level convenience logger for quick use
_default_logger: Optional[GoodQLogger] = None

def get_default_logger() -> GoodQLogger:
    """Get module-level default logger"""
    global _default_logger
    if _default_logger is None:
        _default_logger = get_goodq_logger('goodq4all', component='GoodQ')
    return _default_logger


# Export main classes and functions
__all__ = [
    'GoodQLogger',
    'get_goodq_logger',
    'get_default_logger',
    'MissionColors',
    'QuickMission',
]
