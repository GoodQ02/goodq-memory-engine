"""
Progress tracking system for GoodQ pipeline.
Provides real-time progress updates that can be read by UI and monitoring tools.
"""
from __future__ import annotations
import json
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List
from contextlib import contextmanager


class ProgressTracker:
    """Thread-safe progress tracking for pipeline execution"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.progress_file = Path("L:/goodq4all/logs/progress.json")
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_state: Dict[str, Any] = {
            "status": "idle",
            "current_file": None,
            "current_step": None,
            "steps_completed": [],
            "total_steps": 0,
            "current_step_index": 0,
            "progress_percent": 0,
            "started_at": None,
            "updated_at": None,
            "estimated_completion": None,
            "details": {},
            "errors": [],
            "warnings": [],
        }
        self._write_lock = threading.Lock()
        
    def start_processing(self, filename: str, total_steps: int = 20):
        """Start processing a new file"""
        with self._write_lock:
            self.current_state = {
                "status": "processing",
                "current_file": filename,
                "current_step": "initializing",
                "steps_completed": [],
                "total_steps": total_steps,
                "current_step_index": 0,
                "progress_percent": 0,
                "started_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "estimated_completion": None,
                "details": {},
                "errors": [],
                "warnings": [],
            }
            self._save()
    
    def update_step(self, step_name: str, step_index: int, details: Optional[Dict[str, Any]] = None):
        """Update current processing step"""
        with self._write_lock:
            self.current_state["current_step"] = step_name
            self.current_state["current_step_index"] = step_index
            self.current_state["progress_percent"] = int((step_index / max(self.current_state["total_steps"], 1)) * 100)
            self.current_state["updated_at"] = datetime.now().isoformat()
            if details:
                self.current_state["details"].update(details)
            self._save()
    
    def complete_step(self, step_name: str, result: Optional[Dict[str, Any]] = None):
        """Mark a step as completed"""
        with self._write_lock:
            step_info = {
                "name": step_name,
                "completed_at": datetime.now().isoformat(),
            }
            if result:
                step_info["result"] = result
            self.current_state["steps_completed"].append(step_info)
            self._save()
    
    def add_error(self, error: str, step: Optional[str] = None):
        """Add an error to the progress tracker"""
        with self._write_lock:
            error_info = {
                "message": error,
                "step": step or self.current_state.get("current_step"),
                "timestamp": datetime.now().isoformat(),
            }
            self.current_state["errors"].append(error_info)
            self._save()
    
    def add_warning(self, warning: str, step: Optional[str] = None):
        """Add a warning to the progress tracker"""
        with self._write_lock:
            warning_info = {
                "message": warning,
                "step": step or self.current_state.get("current_step"),
                "timestamp": datetime.now().isoformat(),
            }
            self.current_state["warnings"].append(warning_info)
            self._save()
    
    def finish_processing(self, status: str = "completed"):
        """Mark processing as finished"""
        with self._write_lock:
            self.current_state["status"] = status
            self.current_state["current_step"] = None
            self.current_state["progress_percent"] = 100 if status == "completed" else self.current_state["progress_percent"]
            self.current_state["updated_at"] = datetime.now().isoformat()
            self._save()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current progress state"""
        with self._write_lock:
            return dict(self.current_state)
    
    def _save(self):
        """Save progress state to file (must be called within lock)"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save progress: {e}")
    
    @contextmanager
    def step_context(self, step_name: str, step_index: int, details: Optional[Dict[str, Any]] = None):
        """Context manager for tracking a processing step"""
        self.update_step(step_name, step_index, details)
        try:
            yield self
        except Exception as e:
            self.add_error(str(e), step_name)
            raise
        finally:
            self.complete_step(step_name)


# Global singleton instance
_tracker = ProgressTracker()


def get_tracker() -> ProgressTracker:
    """Get the global progress tracker instance"""
    return _tracker


def start_processing(filename: str, total_steps: int = 20):
    """Convenience function to start processing"""
    return _tracker.start_processing(filename, total_steps)


def update_step(step_name: str, step_index: int, details: Optional[Dict[str, Any]] = None):
    """Convenience function to update step"""
    return _tracker.update_step(step_name, step_index, details)


def complete_step(step_name: str, result: Optional[Dict[str, Any]] = None):
    """Convenience function to complete step"""
    return _tracker.complete_step(step_name, result)


def add_error(error: str, step: Optional[str] = None):
    """Convenience function to add error"""
    return _tracker.add_error(error, step)


def add_warning(warning: str, step: Optional[str] = None):
    """Convenience function to add warning"""
    return _tracker.add_warning(warning, step)


def finish_processing(status: str = "completed"):
    """Convenience function to finish processing"""
    return _tracker.finish_processing(status)


def get_state() -> Dict[str, Any]:
    """Convenience function to get current state"""
    return _tracker.get_state()


@contextmanager
def step_context(step_name: str, step_index: int, details: Optional[Dict[str, Any]] = None):
    """Convenience context manager for tracking a processing step"""
    with _tracker.step_context(step_name, step_index, details) as tracker:
        yield tracker
