"""
VRAM Allocator for GoodQ Pipeline
Provides centralized GPU resource allocation, heartbeat tracking, and stale claim pruning.
"""

import os
import json
import time
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

def _get_registry_dir() -> Path:
    repo_processing = REPO_ROOT / "processing"
    try:
        repo_processing.mkdir(parents=True, exist_ok=True)
        test_file = repo_processing / ".write_test"
        test_file.touch()
        test_file.unlink()
        return repo_processing
    except (PermissionError, OSError):
        program_data = os.environ.get("ProgramData", "C:\\ProgramData")
        fallback_dir = Path(program_data) / "GoodQ4All" / "processing"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return fallback_dir

REGISTRY_DIR = _get_registry_dir()
REGISTRY_PATH = REGISTRY_DIR / "vram_registry.json"
LOCK_PATH = REGISTRY_DIR / "vram_registry.lock"


# Fraction allocations for GPU steps (matching steps.common.gpu_config)
STEP_VRAM_FRACTIONS = {
    "video_scene_detect": 0.20,
    "audio_transcribe": 0.25,
    "audio_diarize": 0.35,
    "face_embed": 0.20,
    "emotion_classify": 0.20,
    "text_embed": 0.15,
    "image_embed_clip": 0.25,
    "image_embed_dino": 0.25,
    "object_detect": 0.25,
    "object_track_yolo": 0.25,
    "image_caption": 0.20,
    "audio_embed_clap": 0.20,
    "audio_emotion": 0.15,
    "image_ocr": 0.15,
    "llm_chat": 0.40,
}


def pid_exists(pid: int) -> bool:
    """Check if a process with the given PID is active in the OS, with fallbacks."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass

    if os.name == "nt":
        # Windows fallback: query tasklist
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=creationflags
            )
            return str(pid) in result.stdout
        except Exception:
            return True  # Safe fallback if tasklist fails
    else:
        # POSIX fallback: use os.kill
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class FileLock:
    """A cross-process file lock utilizing exclusive file creation mode."""

    def __init__(self, timeout: float = 10.0, delay: float = 0.05):
        self.timeout = timeout
        self.delay = delay
        self.has_lock = False

    def __enter__(self):
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # O_EXCL ensures atomicity
                fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self.has_lock = True
                return self
            except (FileExistsError, PermissionError):
                # Check for stale lock file (>30 seconds)
                try:
                    if time.time() - LOCK_PATH.stat().st_mtime > 30.0:
                        try:
                            LOCK_PATH.unlink()
                        except FileNotFoundError:
                            pass
                except Exception:
                    pass
                time.sleep(self.delay)
        raise TimeoutError(f"Could not acquire lock on {LOCK_PATH} within {self.timeout} seconds")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.has_lock:
            try:
                LOCK_PATH.unlink()
            except FileNotFoundError:
                pass
            self.has_lock = False


class VRAMAllocator:
    """Manages VRAM allocation requests, processes registry, and heartbeat monitoring."""

    def __init__(self, budget_fraction: float = 0.90, stale_timeout_sec: float = 300.0):
        self.budget_fraction = budget_fraction
        self.stale_timeout_sec = stale_timeout_sec

    def _read_registry(self) -> Dict[str, Any]:
        if not REGISTRY_PATH.exists():
            return {}
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read VRAM registry: {e}")
            return {}

    def _write_registry(self, registry: Dict[str, Any]) -> None:
        try:
            from steps.common.atomic_io import atomic_write_json
            atomic_write_json(REGISTRY_PATH, registry)
        except Exception as e:
            logger.error(f"Failed to write VRAM registry: {e}")

    def query_gpu_memory(self) -> Tuple[int, int]:
        """Query total and used VRAM in MB via nvidia-smi. Return (total, used) or (0, 0) if failed."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    total = int(parts[0].strip())
                    used = int(parts[1].strip())
                    return total, used
        except Exception as e:
            logger.debug(f"nvidia-smi check failed: {e}")
        return 0, 0

    def clean_stale_claims(self, registry: Dict[str, Any]) -> Dict[str, Any]:
        """Prune claims with inactive processes in the OS or timed-out timestamps."""
        cleaned = {}
        now = time.time()
        for pid_str, claim in registry.items():
            try:
                pid = int(pid_str)
            except ValueError:
                continue

            # Check OS process activity
            is_active = False
            try:
                is_active = pid_exists(pid)
            except Exception:
                pass

            # Check timestamp timeout
            updated_at = claim.get("updated_at", 0.0)
            is_timed_out = (now - updated_at) > self.stale_timeout_sec

            if is_active and not is_timed_out:
                cleaned[pid_str] = claim
            else:
                logger.warning(
                    f"Purging stale VRAM claim for PID {pid} (active={is_active}, timed_out={is_timed_out})"
                )
        return cleaned

    def reserve(self, step_name: str, pid: int, command: str = "") -> bool:
        """Attempt to reserve VRAM for a step."""
        fraction = STEP_VRAM_FRACTIONS.get(step_name)
        if fraction is None:
            # Non-GPU step, always succeeds
            return True

        with FileLock():
            registry = self._read_registry()
            registry = self.clean_stale_claims(registry)

            total_vram, used_vram = self.query_gpu_memory()
            if total_vram == 0:
                # nvidia-smi not available or GPU disabled, proceed without blocking
                self._write_registry(registry)
                return True

            req_mb = int(total_vram * fraction)

            # Sum up VRAM reserved by active pipeline processes
            claimed_by_pipeline = sum(claim.get("claimed_vram_mb", 0) for claim in registry.values())

            # 1. Total pipeline claims must not exceed budget fraction
            pipeline_budget = total_vram * self.budget_fraction
            if claimed_by_pipeline + req_mb > pipeline_budget:
                logger.warning(
                    f"VRAM allocation rejected for '{step_name}': pipeline claims ({claimed_by_pipeline} MB) + "
                    f"request ({req_mb} MB) exceeds pipeline budget ({pipeline_budget:.0f} MB)"
                )
                self._write_registry(registry)
                return False

            # 2. Total physical VRAM usage must not exceed 95%
            physical_limit = total_vram * 0.95
            if used_vram + req_mb > physical_limit:
                logger.warning(
                    f"VRAM allocation rejected for '{step_name}': physical used ({used_vram} MB) + "
                    f"request ({req_mb} MB) exceeds physical limit ({physical_limit:.0f} MB)"
                )
                self._write_registry(registry)
                return False

            # Grant reservation
            now = time.time()
            registry[str(pid)] = {
                "step_name": step_name,
                "start_time": now,
                "command": command,
                "claimed_vram_mb": req_mb,
                "updated_at": now,
            }
            self._write_registry(registry)
            logger.info(f"Reserved {req_mb} MB VRAM for step '{step_name}' on PID {pid}")

            # Start background heartbeat daemon for this reservation
            self.start_heartbeat_daemon(pid)
            return True

    def update_pid(self, old_pid: int, new_pid: int) -> None:
        """Update a claim's process ID (e.g. from parent PID to subprocess PID)."""
        with FileLock():
            registry = self._read_registry()
            if str(old_pid) in registry:
                claim = registry.pop(str(old_pid))
                claim["updated_at"] = time.time()
                registry[str(new_pid)] = claim
                self._write_registry(registry)
                logger.info(f"Updated VRAM claim PID from {old_pid} to {new_pid} for step '{claim['step_name']}'")
                self.start_heartbeat_daemon(new_pid)

    def release(self, pid: int) -> None:
        """Release VRAM reservation."""
        with FileLock():
            registry = self._read_registry()
            if str(pid) in registry:
                claim = registry.pop(str(pid))
                self._write_registry(registry)
                logger.info(
                    f"Released VRAM claim of {claim.get('claimed_vram_mb', 0)} MB for step '{claim.get('step_name')}' on PID {pid}"
                )

    def refresh_heartbeat(self, pid: int) -> None:
        """Refresh the updated_at timestamp of a claim."""
        with FileLock():
            registry = self._read_registry()
            if str(pid) in registry:
                registry[str(pid)]["updated_at"] = time.time()
                self._write_registry(registry)

    def start_heartbeat_daemon(self, pid: int, interval: float = 15.0) -> None:
        """Start a daemon thread that periodically refreshes the heartbeat for pid while it exists."""

        def run():
            while True:
                time.sleep(interval)
                # Check if process is still running
                try:
                    if not pid_exists(pid):
                        break
                except Exception:
                    break

                # Check if the claim still exists in registry (hasn't been released manually)
                with FileLock():
                    registry = self._read_registry()
                    if str(pid) not in registry:
                        break

                try:
                    self.refresh_heartbeat(pid)
                except Exception:
                    pass

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def wait_and_reserve(
        self, step_name: str, pid: int, command: str = "", timeout_seconds: float = 60.0
    ) -> bool:
        """Wait until VRAM is available and reserve it, or timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if self.reserve(step_name, pid, command):
                return True
            time.sleep(1.0)
        return False
