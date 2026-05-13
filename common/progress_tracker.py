"""
Progress Tracking System for GoodQ Pipeline
Provides real-time progress updates for UI consumption
"""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, List
from threading import Lock
from datetime import datetime
from configs.paths import LOGS_DIR

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Thread-safe progress tracker for pipeline operations"""
    
    def __init__(self, progress_file: Path = LOGS_DIR / "progress.json"):
        self.progress_file = progress_file
        self.lock = Lock()
        self.current_file: Optional[str] = None
        self.current_step: Optional[str] = None
        self.total_steps: int = 0
        self.completed_steps: int = 0
        self.progress_percent: float = 0.0
        self.started_at: Optional[float] = None
        self.step_details: Dict[str, Any] = {}
        self.status: str = "idle"
        self.error: Optional[str] = None
        
    def start_file(self, filename: str, total_steps: int = 20):
        """Start tracking a new file"""
        with self.lock:
            self.current_file = filename
            self.total_steps = total_steps
            self.completed_steps = 0
            self.progress_percent = 0.0
            self.started_at = time.time()
            self.status = "processing"
            self.error = None
            self.step_details = {}
            self._save()
            logger.info(f"[PROGRESS] Started processing: {filename}")
    
    def update_step(self, step_name: str, sub_progress: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """
        Update current step with optional sub-progress
        
        Args:
            step_name: Name of the current step
            sub_progress: Optional 0-100 progress within this step (for granular tracking)
            details: Optional dict of step details
        """
        with self.lock:
            # Only increment step counter if step name changed
            if self.current_step != step_name:
                self.current_step = step_name
                self.completed_steps += 1
            
            # Calculate progress
            if sub_progress is not None:
                # Use sub-progress for granular within-step tracking
                base_progress = ((self.completed_steps - 1) / self.total_steps) * 100
                step_weight = (1 / self.total_steps) * 100
                self.progress_percent = base_progress + (step_weight * (sub_progress / 100))
            else:
                # Standard step-based progress
                self.progress_percent = (self.completed_steps / self.total_steps) * 100
            
            # Clamp to 0-100
            self.progress_percent = max(0, min(100, self.progress_percent))
            
            if details:
                self.step_details[step_name] = details
            self._save()
            elapsed = time.time() - (self.started_at or time.time())
            logger.info(f"[PROGRESS] Step {self.completed_steps}/{self.total_steps}: {step_name} ({self.progress_percent:.1f}%) - {elapsed:.1f}s elapsed")
    
    def complete_file(self, success: bool = True, error: Optional[str] = None):
        """Mark file processing as complete"""
        with self.lock:
            self.status = "completed" if success else "failed"
            self.error = error
            self.progress_percent = 100.0 if success else self.progress_percent
            elapsed = time.time() - (self.started_at or time.time())
            self._save()
            if success:
                logger.info(f"[PROGRESS] Completed: {self.current_file} in {elapsed:.1f}s")
            else:
                logger.error(f"[PROGRESS] Failed: {self.current_file} - {error}")
    
    def _save(self):
        """Save progress to file"""
        try:
            data = {
                "file": self.current_file,
                "step": self.current_step,
                "total_steps": self.total_steps,
                "completed_steps": self.completed_steps,
                "progress_percent": round(self.progress_percent, 2),
                "status": self.status,
                "error": self.error,
                "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
                "elapsed_seconds": round(time.time() - self.started_at, 2) if self.started_at else 0,
                "step_details": self.step_details,
                "timestamp": datetime.now().isoformat()
            }
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress state"""
        with self.lock:
            return {
                "file": self.current_file,
                "step": self.current_step,
                "total_steps": self.total_steps,
                "completed_steps": self.completed_steps,
                "progress_percent": round(self.progress_percent, 2),
                "status": self.status,
                "error": self.error,
                "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
                "elapsed_seconds": round(time.time() - self.started_at, 2) if self.started_at else 0,
                "step_details": self.step_details
            }

# Global progress tracker instance
_progress_tracker: Optional[ProgressTracker] = None

def get_progress_tracker() -> ProgressTracker:
    """Get or create global progress tracker"""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker()
    return _progress_tracker
