from __future__ import annotations
import csv
import io
import json
import os
import hashlib
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import GoodQ mission logger
try:
    from lib.goodq_logger import get_goodq_logger
    from lib.mission_components import get_component_name, format_duration
    MISSION_LOGGER_AVAILABLE = True
except ImportError:
    MISSION_LOGGER_AVAILABLE = False
    get_goodq_logger = None
    get_component_name = None
    format_duration = None

logger = logging.getLogger(__name__)

_STEP_LOG_THREAD_LOCK = threading.Lock()
_LOCK_FILENAME = ".step_runs.lock"


class _StepLogFileLock:
    """Process-safe and thread-safe OS kernel file lock for step_runs ledger appends."""

    def __init__(
        self,
        lock_path: str | Path,
        *,
        timeout: float = 30.0,
        delay: float = 0.005,
    ) -> None:
        self.lock_path = Path(lock_path)
        self.timeout = float(timeout)
        self.delay = float(delay)
        self._has_thread_lock = False
        self._fd: Optional[int] = None
        self._has_file_lock = False

    @staticmethod
    def _try_acquire_os_lock(fd: int) -> bool:
        if os.name == "nt":
            import msvcrt

            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    @staticmethod
    def _release_os_lock(fd: int) -> None:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)

    def __enter__(self) -> "_StepLogFileLock":
        if not _STEP_LOG_THREAD_LOCK.acquire(timeout=self.timeout):
            raise TimeoutError(f"Could not acquire thread step_logger lock for {self.lock_path} within {self.timeout}s")
        self._has_thread_lock = True
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            deadline = time.monotonic() + self.timeout
            open_flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
            while True:
                try:
                    self._fd = os.open(str(self.lock_path), open_flags, 0o666)
                    break
                except PermissionError as open_err:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Could not open step_logger lock {self.lock_path} within {self.timeout}s"
                        ) from open_err
                    time.sleep(self.delay)

            while True:
                if self._try_acquire_os_lock(self._fd):
                    self._has_file_lock = True
                    return self
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire file step_logger lock {self.lock_path} within {self.timeout}s"
                    )
                time.sleep(self.delay)
        except BaseException:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError as close_err:
                    logger.debug("step_logger lock close failed path=%s exc=%s", self.lock_path, close_err)
                self._fd = None
            if self._has_thread_lock:
                self._has_thread_lock = False
                _STEP_LOG_THREAD_LOCK.release()
            raise

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if self._fd is not None:
                try:
                    if self._has_file_lock:
                        self._release_os_lock(self._fd)
                        self._has_file_lock = False
                except OSError as exc:
                    logger.debug("step_logger lock release unlock failed path=%s exc=%s", self.lock_path, exc)
                finally:
                    try:
                        os.close(self._fd)
                    except OSError as close_err:
                        logger.debug("step_logger lock close failed path=%s exc=%s", self.lock_path, close_err)
                    self._fd = None
        finally:
            if self._has_thread_lock:
                self._has_thread_lock = False
                _STEP_LOG_THREAD_LOCK.release()


def _append_bytes_locked(path: str, payload_bytes: bytes) -> None:
    """Append complete payload_bytes at EOF under active _StepLogFileLock, rolling back partial writes on error."""
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o666)
    initial_size: Optional[int] = None
    try:
        initial_size = os.lseek(fd, 0, os.SEEK_END)
        view = memoryview(payload_bytes)
        total_written = 0
        while total_written < len(view):
            written = os.write(fd, view[total_written:])
            if written <= 0:
                raise OSError(f"os.write returned {written} bytes for {path}")
            total_written += written
        os.fsync(fd)
    except BaseException:
        if initial_size is not None:
            try:
                os.ftruncate(fd, initial_size)
            except OSError as trunc_err:
                logger.debug("step_logger rollback ftruncate failed path=%s exc=%s", path, trunc_err)
        raise
    finally:
        os.close(fd)


def _format_csv_bytes(row: List[str], *, include_header: bool) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n" if os.name == "nt" else "\n")
    if include_header:
        writer.writerow(["ts", "step", "modality", "source_path", "duration_ms", "status", "error"])
    writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _fingerprint_item(item: Optional[Dict[str, Any]]) -> str:
    try:
        if not item:
            return ""
        sp = item.get("source_path") if isinstance(item, dict) else None  # type: ignore[assignment]
        h = hashlib.sha256()
        if isinstance(sp, str) and os.path.isfile(sp):
            with open(sp, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        h.update(repr(item).encode("utf-8", errors="ignore"))
        return h.hexdigest()
    except Exception as e:
        logger.warning(
            "step_logger operation failed operation=%s exc_type=%s exc=%s",
            "fingerprint_item",
            type(e).__name__,
            e,
        )
        return ""


_GPU_LIKELY_STEPS = {
    "image_caption",
    "image_embed_dino",
    "image_embed_clip",
    "face_embed",
    "object_detect",
    "audio_diarize",
    "audio_transcribe",
    "audio_emotion",
    "audio_embed_clap",
}


def log_step_run(
    cfg: Dict[str, Any],
    step_name: str,
    item: Optional[Dict[str, Any]],
    duration_ms: float,
    status: str,
    error: Optional[str] = None,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log step execution with Q Branch mission styling
    Maintains CSV/JSONL compatibility while adding mission-styled console output
    """
    # Mission-styled console logging (if available)
    if MISSION_LOGGER_AVAILABLE:
        try:
            component = get_component_name(step_name)
            mission_logger = get_goodq_logger(step_name, component=component)
            
            duration_s = duration_ms / 1000.0
            duration_str = format_duration(duration_s)
            
            if status == "ok":
                mission_logger.mission_complete(step_name, duration=duration_s)
            elif status == "skipped":
                reason = (extra or {}).get('reason', 'unknown')
                mission_logger.info(f"Operation bypassed - {reason} [{duration_str}]")
            elif status == "error":
                mission_logger.error(f"Operation failed - {error[:100] if error else 'Unknown error'} [{duration_str}]")
            else:
                mission_logger.info(f"Status: {status} [{duration_str}]")
        except Exception as e:
            logger.warning(
                "step_logger operation failed operation=%s step=%s status=%s exc_type=%s exc=%s",
                "mission_log",
                step_name,
                status,
                type(e).__name__,
                e,
            )
    
    # Original CSV/JSONL logging (preserved for compatibility, process-safe serialized)
    try:
        log_dir = (cfg.get("paths", {}) or {}).get("log_dir") or ""
        if not log_dir:
            return
        os.makedirs(log_dir, exist_ok=True)

        ts_now = datetime.utcnow().isoformat()
        modality = (item or {}).get("modality") if isinstance(item, dict) else None
        source_path = (item or {}).get("source_path") if isinstance(item, dict) else None
        csv_row = [
            ts_now,
            step_name,
            modality or "",
            source_path or "",
            f"{duration_ms:.2f}",
            status,
            (error or "")[:500],
        ]

        try:
            env_name = os.environ.get("CONDA_DEFAULT_ENV") or ""
        except Exception as e:
            logger.warning(
                "step_logger operation failed operation=%s step=%s exc_type=%s exc=%s",
                "resolve_env_name",
                step_name,
                type(e).__name__,
                e,
            )
            env_name = ""

        run_cfg = cfg.get("run") if isinstance(cfg, dict) else None
        if not isinstance(run_cfg, dict):
            run_cfg = {}

        entry: Dict[str, Any] = {
            "ts": ts_now,
            "step": step_name,
            "duration_ms": float(f"{duration_ms:.3f}"),
            "status": status,
            "error": (error or "")[:2000],
            "env": env_name,
            "modality": modality,
            "source_path": source_path,
            "item_hash": _fingerprint_item(item),
            "run_id": run_cfg.get("id"),
            "pipeline": run_cfg.get("pipeline"),
            "timer_unit": run_cfg.get("timer_unit", "ms"),
        }

        if run_cfg.get("started_at"):
            entry["run_started_at"] = run_cfg.get("started_at")
        if run_cfg.get("git_sha"):
            entry["git_sha"] = run_cfg.get("git_sha")
        if run_cfg.get("device"):
            entry["device"] = run_cfg.get("device")
        if run_cfg.get("dtype"):
            entry["dtype"] = run_cfg.get("dtype")

        if isinstance(item, dict):
            for key in ("video_id", "video_hash", "scene_id", "scene_index", "timestamp", "model_signature"):
                if key in item:
                    entry[key] = item.get(key)

        if extra and isinstance(extra, dict):
            entry["extra"] = extra

        flags: List[str] = []
        if status == "ok" and duration_ms < 5.0 and step_name in _GPU_LIKELY_STEPS:
            flags.append("improbable_duration")
        if flags:
            entry["flags"] = flags

        jsonl_bytes = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
        csv_path = os.path.join(log_dir, "step_runs.csv")
        jsonl_path = os.path.join(log_dir, "step_runs.jsonl")
        lock_path = os.path.join(log_dir, _LOCK_FILENAME)

        with _StepLogFileLock(lock_path):
            try:
                is_new_csv = not os.path.isfile(csv_path) or os.path.getsize(csv_path) == 0
                csv_bytes = _format_csv_bytes(csv_row, include_header=is_new_csv)
                _append_bytes_locked(csv_path, csv_bytes)
            except Exception as csv_err:
                logger.warning(
                    "step_logger operation failed operation=%s step=%s status=%s exc_type=%s exc=%s",
                    "write_step_run_csv",
                    step_name,
                    status,
                    type(csv_err).__name__,
                    csv_err,
                )
            _append_bytes_locked(jsonl_path, jsonl_bytes)
    except Exception as e:
        logger.warning(
            "step_logger operation failed operation=%s step=%s status=%s exc_type=%s exc=%s",
            "write_step_run",
            step_name,
            status,
            type(e).__name__,
            e,
        )
        return
