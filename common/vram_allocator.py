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
    # A device has one owner across checkouts and isolated corpus epochs. Never
    # fall back to a checkout-local file when the shared owner is unavailable.
    # Upgrades from the old checkout-local registry require quiescent workers.
    if os.name == "nt":
        return Path(os.environ.get("ProgramData", "C:\\ProgramData")) / "GoodQ4All" / "processing"
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "goodq4all" / "processing"

REGISTRY_DIR = _get_registry_dir()
REGISTRY_PATH = REGISTRY_DIR / "vram_registry.json"
LOCK_PATH = REGISTRY_DIR / "vram_registry.lock"


# Fraction allocations for GPU steps (matching steps.common.gpu_config)
STEP_VRAM_FRACTIONS = {
    "video_scene_detect": 0.20,
    "audio_transcribe": 0.25,
    "audio_transcribe_local": 0.25,
    "audio_diarize": 0.35,
    "emotion_classify": 0.20,
    "text_embed": 0.15,
    "image_embed_clip": 0.25,
    "image_embed_dino": 0.15,
    "object_detect": 0.25,
    "object_track_yolo": 0.25,
    "image_caption": 0.40,
    "image_ocr": 0.25,
    "audio_embed_clap": 0.20,
    "audio_emotion": 0.15,
    "llm_chat": 0.40,
}

_STEP_FORCE_CPU_ENV_VARS = {
    "image_caption": "GOODQ_IMAGE_CAPTION_FORCE_CPU",
    "object_detect": "GOODQ_OBJECT_DETECT_FORCE_CPU",
    "audio_embed_clap": "GOODQ_CLAP_FORCE_CPU",
    "image_embed_dino": "GOODQ_DINO_FORCE_CPU",
    "emotion_classify": "GOODQ_EMOTION_FORCE_CPU",
}


def validate_ocr_device_policy(cfg: Dict[str, Any], env: Dict[str, str]) -> bool:
    """Return selected CUDA usage, rejecting contradictory host CPU controls."""
    from steps.image_ocr.step import resolve_ocr_device

    uses_cuda = resolve_ocr_device(cfg).startswith("cuda")
    if uses_cuda and (
        env.get("GOODQ_FORCE_CPU") == "1"
        or env.get("GOODQ_NO_AUTO_GPU") == "1"
        or env.get("GOODQ_HOST_PROFILE", "").upper() == "BASELINE"
        or env.get("CUDA_VISIBLE_DEVICES", "0").strip() in {"", "-1"}
        or env.get("GOODQ_DEVICE", "").lower() == "cpu"
    ):
        raise RuntimeError("Selected OCR CUDA provider conflicts with host CPU policy")
    return uses_cuda


def step_uses_gpu_backend(
    step_name: str,
    *,
    env: Dict[str, str] | None = None,
    conda_env: str | None = None,
    cfg: Dict[str, Any] | None = None,
) -> bool:
    """Return True only when step_name has a GPU reservation entry and its effective backend is GPU."""
    if step_name not in STEP_VRAM_FRACTIONS:
        return False
    if step_name == "image_ocr":
        from steps.image_ocr.step import resolve_ocr_device

        # Selection is a configuration decision; admission may not silently
        # turn a CUDA request into a CPU execution.
        return resolve_ocr_device(cfg or {}).startswith("cuda")
    active_env = env if env is not None else os.environ
    if (
        str(active_env.get("GOODQ_FORCE_CPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_NO_AUTO_GPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_HOST_PROFILE", "")).strip().upper() == "BASELINE"
        or str(active_env.get("CUDA_VISIBLE_DEVICES", "0")).strip() in {"", "-1"}
        or str(active_env.get("GOODQ_DEVICE", "")).strip().lower() == "cpu"
    ):
        return False
    force_cpu_key = _STEP_FORCE_CPU_ENV_VARS.get(step_name)
    if force_cpu_key and str(active_env.get(force_cpu_key, "")).strip() == "1":
        return False
    if step_name == "object_detect":
        try:
            from steps.object_detect.step import resolve_effective_device as resolve_object_detect_device

            device = str(
                resolve_object_detect_device(
                    env=dict(active_env),
                    conda_env=conda_env or "goodq_object_detect",
                )
                or ""
            ).strip().lower()
            return device.startswith("cuda") or device == "unknown"
        except Exception:
            return True
    if step_name == "emotion_classify":
        try:
            from steps.emotion_classify.step import resolve_effective_device as resolve_emotion_device

            device = str(
                resolve_emotion_device(
                    env=dict(active_env),
                    conda_env=conda_env or "goodq_core",
                )
                or ""
            ).strip().lower()
            return device.startswith("cuda") or device == "unknown"
        except Exception:
            return True
    return True



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

    def __init__(
        self,
        budget_fraction: float = 0.90,
        stale_timeout_sec: float = 300.0,
        *,
        env: Dict[str, str] | None = None,
        conda_env: str | None = None,
        cfg: Dict[str, Any] | None = None,
    ):
        self.budget_fraction = budget_fraction
        self.stale_timeout_sec = stale_timeout_sec
        self.env = dict(env) if isinstance(env, dict) else None
        self.conda_env = conda_env
        self.cfg = cfg

    def _read_registry(self) -> Dict[str, Any]:
        from steps.common.atomic_io import read_text_during_atomic_replace

        try:
            registry = json.loads(read_text_during_atomic_replace(REGISTRY_PATH))
            if not isinstance(registry, dict):
                raise ValueError("Expected a reservation object")
            return registry
        except FileNotFoundError:
            return {}
        except Exception as e:
            raise RuntimeError(f"Failed to read VRAM registry {REGISTRY_PATH}: {e}") from e

    def _write_registry(self, registry: Dict[str, Any]) -> None:
        try:
            from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
            atomic_write_json_for_concurrent_readers(REGISTRY_PATH, registry)
        except Exception as e:
            # Admission, PID handoff and release must never claim an uncommitted change.
            raise RuntimeError(f"Failed to write VRAM registry {REGISTRY_PATH}: {e}") from e

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
                pid = int(claim.get("pid", pid_str))
            except (ValueError, TypeError):
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

    def reserve(
        self,
        step_name: str,
        pid: int,
        command: str = "",
        *,
        reservation_id: str | None = None,
        env: Dict[str, str] | None = None,
        conda_env: str | None = None,
        cfg: Dict[str, Any] | None = None,
    ) -> bool:
        """Attempt to reserve VRAM for a step."""
        effective_env = env if env is not None else getattr(self, "env", None)
        effective_conda_env = conda_env if conda_env is not None else getattr(self, "conda_env", None)
        effective_cfg = cfg if cfg is not None else getattr(self, "cfg", None)
        fraction = STEP_VRAM_FRACTIONS.get(step_name)
        if fraction is None or not step_uses_gpu_backend(
            step_name, env=effective_env, conda_env=effective_conda_env, cfg=effective_cfg
        ):
            # Non-GPU step or effective backend resolved to CPU, always succeeds
            return True

        active_env = effective_env if effective_env is not None else os.environ
        if step_name != "image_ocr" and str(active_env.get("GOODQ_BYPASS_VRAM_LIMITS", os.getenv("GOODQ_BYPASS_VRAM_LIMITS", ""))).strip() == "1":
            logger.info(f"Bypassing VRAM limit checks for step '{step_name}' via GOODQ_BYPASS_VRAM_LIMITS=1")
            return True

        with FileLock():
            registry = self._read_registry()
            registry = self.clean_stale_claims(registry)

            total_vram, used_vram = self.query_gpu_memory()
            if total_vram == 0:
                if step_name == "image_ocr":
                    raise RuntimeError("Cannot admit selected OCR CUDA provider: GPU memory is unavailable")
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
            claim_key = reservation_id or str(pid)
            if claim_key in registry:
                raise RuntimeError(f"VRAM reservation already exists: {claim_key}")
            registry[claim_key] = {
                "pid": pid,
                "step_name": step_name,
                "start_time": now,
                "command": command,
                "claimed_vram_mb": req_mb,
                "updated_at": now,
            }
            self._write_registry(registry)
            logger.info(f"Reserved {req_mb} MB VRAM for step '{step_name}' on PID {pid}")

            # Start background heartbeat daemon for this reservation
            self.start_heartbeat_daemon(claim_key)
            return True

    def update_pid(self, old_pid: int | str, new_pid: int) -> None:
        """Bind a reservation to its worker; retain unique launch keys across handoff."""
        with FileLock():
            registry = self._read_registry()
            if str(old_pid) in registry:
                claim = registry.pop(str(old_pid))
                claim["updated_at"] = time.time()
                claim["pid"] = new_pid
                key = str(new_pid) if isinstance(old_pid, int) else old_pid
                registry[key] = claim
                self._write_registry(registry)
                logger.info(f"Updated VRAM claim PID from {old_pid} to {new_pid} for step '{claim['step_name']}'")
                if isinstance(old_pid, int):
                    self.start_heartbeat_daemon(key)

    def release(self, pid: int | str) -> None:
        """Release VRAM reservation."""
        with FileLock():
            registry = self._read_registry()
            if str(pid) in registry:
                claim = registry.pop(str(pid))
                self._write_registry(registry)
                logger.info(
                    f"Released VRAM claim of {claim.get('claimed_vram_mb', 0)} MB for step '{claim.get('step_name')}' on PID {pid}"
                )

    def refresh_heartbeat(self, pid: int | str) -> None:
        """Refresh the updated_at timestamp of a claim."""
        with FileLock():
            registry = self._read_registry()
            if str(pid) in registry:
                registry[str(pid)]["updated_at"] = time.time()
                self._write_registry(registry)

    def start_heartbeat_daemon(self, pid: int | str, interval: float = 15.0) -> None:
        """Start a daemon thread that periodically refreshes the heartbeat for pid while it exists."""

        def run():
            while True:
                time.sleep(interval)
                try:
                    # Passive readers must not prevent atomic replacement on Windows.
                    with FileLock():
                        registry = self._read_registry()
                        if str(pid) not in registry:
                            break
                        owner_pid = registry[str(pid)].get("pid", pid)
                    if not pid_exists(int(owner_pid)):
                        break
                    self.refresh_heartbeat(pid)
                except Exception as exc:
                    logger.warning("Failed to refresh VRAM reservation %s: %s", pid, exc)

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def wait_and_reserve(
        self, step_name: str, pid: int, command: str = "", timeout_seconds: float = 60.0,
        *, reservation_id: str | None = None, cancel_event: threading.Event | None = None,
        env: Dict[str, str] | None = None, conda_env: str | None = None,
        cfg: Dict[str, Any] | None = None,
    ) -> bool:
        """Wait until VRAM is available and reserve it, or timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if cancel_event is not None and cancel_event.is_set():
                return False
            if self.reserve(
                step_name,
                pid,
                command,
                reservation_id=reservation_id,
                env=env,
                conda_env=conda_env,
                cfg=cfg,
            ):
                if cancel_event is not None and cancel_event.is_set():
                    self.release(reservation_id or pid)
                    return False
                return True
            if cancel_event is None:
                time.sleep(1.0)
            elif cancel_event.wait(1.0):
                return False
        return False
