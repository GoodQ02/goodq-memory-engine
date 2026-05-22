"""read-only aggregation surface for current runtime state.

This router exists to answer "what is happening right now?" across a long-running,
stateful local system. It must never grow into a control, mutation, or execution
surface.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, deque
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query

from api.utils.ingest_requests import is_supported_ingest_path
from goodq_version import GOODQ_VERSION
from lib import run_index, run_summary
from steps.common.config_loader import load_configs
from steps.common.memory_store import normalize_memory_tier_list

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runtime"])

_AUDIO_QDRANT_REQUIRED_FIELDS = (
    "run_id",
    "embedding_id",
    "component",
    "step",
    "model",
    "created_at",
    "commit_ts_utc",
)
_AUDIO_EMOTION_PROMOTION_THRESHOLD = 0.5

_CFG = load_configs({})
_PATHS_CFG: Dict[str, Any] = _CFG.get("paths", {}) or {}
_HOST_CFG: Dict[str, Any] = _CFG.get("host", {}) or {}
_HOST_DATA_ROOT = _HOST_CFG.get("data_root") or os.environ.get("GOODQ_DATA_ROOT")
_API_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _API_ROOT.parent
if _HOST_DATA_ROOT:
    _DEFAULT_DATA_ROOT = Path(str(_HOST_DATA_ROOT)) / "GoodQ_Data"
else:
    _DEFAULT_DATA_ROOT = Path(str(_PATHS_CFG.get("data_root") or (_PROJECT_ROOT / "data")))
_DATA_ROOT = Path(_PATHS_CFG.get("data_root") or _DEFAULT_DATA_ROOT)
_LOG_DIR = Path(_PATHS_CFG.get("log_dir") or (_PROJECT_ROOT / "logs"))
_DB_PATH = Path(_PATHS_CFG.get("db_path") or (_DATA_ROOT / "memory.db"))
_PROCESSING_PATH = Path(_PATHS_CFG.get("processing") or (_DATA_ROOT / "processing"))
_IMPORT_INBOX = Path(_PATHS_CFG.get("import_inbox") or (_DATA_ROOT / "import_inbox"))
_QDRANT_STORAGE = Path(_PATHS_CFG.get("qdrant_storage") or (_DATA_ROOT.parent / "qdrant_storage"))
_FAISS_DIR = Path(_PATHS_CFG.get("faiss_dir") or (_DATA_ROOT / "faiss"))
_MODEL_CACHE = Path(_PATHS_CFG.get("model_cache") or os.environ.get("HF_HOME") or (_DATA_ROOT / "cache"))
_REPORTS_ROOT = Path(os.environ.get("GOODQ_RUN_REPORTS_ROOT") or (_DATA_ROOT / "reports"))
_WSL_DISTRO = str(os.environ.get("GOODQ_WSL_DISTRO") or _HOST_CFG.get("wsl_distro") or "Ubuntu")
_WSL_USER = str(os.environ.get("GOODQ_WSL_USER") or "").strip()
if not _WSL_USER or _WSL_USER.lower() == "auto":
    _WSL_USER = str(os.environ.get("USER") or os.environ.get("USERNAME") or os.environ.get("LOGNAME") or "user")


def _get_ollama_models_url(cfg: Dict[str, Any]) -> tuple[str | None, int | None]:
    llm_cfg = cfg.get("llm", {}) or {}
    ollama_url = llm_cfg.get("ollama_url")
    if not ollama_url:
        return None, None
    base = str(ollama_url).rstrip("/")
    parsed = urlparse(base)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return f"{base}/models", port


def _summarize_llm_health() -> Dict[str, Any]:
    """Lightweight LLM health summary used by /api/engines and dashboards."""
    vllm_healthy = 0
    vllm_total = 0
    ollama_healthy = 0
    ollama_total = 0
    ollama_models_url, ollama_port = _get_ollama_models_url(_CFG)

    try:
        resp = requests.get("http://localhost:38005/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            vllm_total = len(models)
            vllm_healthy = vllm_total
    except Exception as e:
        logger.debug(f"vLLM health check failed: {e}")

    def _probe_ollama(url: str):
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                total = len(models)
                return True, total, total
        except Exception as e:
            logger.debug(f"Ollama probe failed: {e}")
        return False, 0, 0

    if ollama_models_url:
        ok, t, h = _probe_ollama(ollama_models_url)
        if ok:
            ollama_total, ollama_healthy = t, h

    def _status(healthy: int, total: int) -> str:
        if total == 0:
            return "unavailable"
        if healthy == total:
            return "healthy"
        if healthy > 0:
            return "degraded"
        return "down"

    total_models = max(vllm_total, 1) + max(ollama_total, 1)
    healthy_models = vllm_healthy + ollama_healthy

    return {
        "vllm": {
            "status": _status(vllm_healthy, vllm_total),
            "healthy": vllm_healthy,
            "total": max(vllm_total, 1),
            "port": 38005,
        },
        "ollama": {
            "status": _status(ollama_healthy, ollama_total),
            "healthy": ollama_healthy,
            "total": max(ollama_total, 1),
            "port": ollama_port,
        },
        "overall": {
            "status": "healthy" if healthy_models == total_models else "degraded" if healthy_models > 0 else "unhealthy",
            "total": total_models,
            "healthy": healthy_models,
            "unhealthy": max(total_models - healthy_models, 0),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


def _collect_engine_details() -> Dict[str, Any]:
    """Richer engine details (kept separate from summary for UI/backward compatibility)."""
    import shutil

    engines: Dict[str, Any] = {}

    try:
        resp = requests.get("http://localhost:38005/v1/models", timeout=2)
        if resp.status_code == 200:
            model_data = resp.json().get("data", [])
            model_name = model_data[0]["id"].split("/")[-1] if model_data else "Unknown"
            engines["vllm_llama1b"] = {
                "name": "vLLM Llama-1B",
                "category": "LLM Inference",
                "description": f"{model_name} on port 38005",
                "status": "ready",
                "gpu": True,
                "port": 38005,
            }
        else:
            raise Exception("unhealthy")
    except Exception as e:
        logger.debug(f"vLLM engine check failed: {e}")
        engines["vllm_llama1b"] = {
            "name": "vLLM Llama-1B",
            "category": "LLM Inference",
            "description": "Not running or unreachable",
            "status": "unavailable",
            "gpu": True,
            "port": 38005,
        }

    try:
        ollama_models_url, ollama_port = _get_ollama_models_url(_CFG)
        if not ollama_models_url:
            raise Exception("Ollama URL not configured")
        resp = requests.get(ollama_models_url, timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_name = models[0]["id"] if models else "Unknown"
            port_label = str(ollama_port) if ollama_port else "unknown"
            engines["ollama"] = {
                "name": "Ollama",
                "category": "LLM Inference",
                "description": f"{model_name} on port {port_label}",
                "status": "ready",
                "gpu": True,
                "port": ollama_port,
            }
        else:
            raise Exception("unhealthy")
    except Exception as e:
        logger.debug(f"Ollama engine check failed: {e}")
        engines["ollama"] = {
            "name": "Ollama",
            "category": "LLM Inference",
            "description": "Not running or unreachable",
            "status": "unavailable",
            "gpu": True,
            "port": None,
        }

    wsl_available = shutil.which("wsl") is not None
    engines["wsl_audio"] = {
        "name": "WSL Audio Transcription",
        "category": "Audio Processing",
        "description": "Faster-Whisper with speaker diarization",
        "status": "ready" if wsl_available else "unavailable",
        "gpu": True,
    }

    try:
        resp = requests.get("http://localhost:6333/collections", timeout=2)
        if resp.status_code == 200:
            collections = resp.json().get("result", {}).get("collections", [])
            engines["qdrant"] = {
                "name": "Qdrant",
                "category": "Vector DB",
                "description": f"{len(collections)} collections @ 6333",
                "status": "ready",
                "gpu": False,
                "port": 6333,
            }
        else:
            raise Exception("unhealthy")
    except Exception as e:
        logger.debug(f"Qdrant engine check failed: {e}")
        engines["qdrant"] = {
            "name": "Qdrant",
            "category": "Vector DB",
            "description": "Not reachable on 6333",
            "status": "unavailable",
            "gpu": False,
            "port": 6333,
        }

    ffmpeg_path = shutil.which("ffmpeg")
    engines["ffmpeg"] = {
        "name": "FFmpeg",
        "category": "Video Processing",
        "description": f"Path: {ffmpeg_path}" if ffmpeg_path else "Not found",
        "status": "ready" if ffmpeg_path else "unavailable",
        "gpu": False,
    }

    engines["python_pipeline"] = {
        "name": "Python Pipeline",
        "category": "Orchestration",
        "description": f"Python {sys.version.split()[0]}",
        "status": "ready",
        "gpu": False,
    }

    try:
        from scenedetect import detect  # noqa: F401

        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "PySceneDetect for content-aware splitting",
            "status": "ready",
            "gpu": False,
        }
    except Exception as e:
        logger.debug(f"Scene detection check failed: {e}")
        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "PySceneDetect not available",
            "status": "unavailable",
            "gpu": False,
        }

    qdrant_engine = engines.get("qdrant") or {}
    engines["vector_db"] = {
        "name": "Vector Database",
        "category": "Search & Retrieval",
        "description": f"Qdrant-backed retrieval ({qdrant_engine.get('description', 'service unavailable')})",
        "status": qdrant_engine.get("status", "unavailable"),
        "gpu": False,
    }

    engines["audio_diarization"] = {
        "name": "Audio Diarization",
        "category": "Audio Processing",
        "description": "Pyannote speaker separation with OSD",
        "status": "ready",
        "gpu": True,
    }

    return engines


def _collect_wsl_status() -> Dict[str, Any]:
    """Combine the previously separate WSL status checks into one shared helper."""
    import shutil

    status: Dict[str, Any] = {
        "available": False,
        "status": "not_installed",
        "vllm_service": "unknown",
        "audio_processing": "unknown",
        "faster_whisper": "not_installed",
        "active": False,
        "performance_boost": "2-5× faster",
        "gpu_name": None,
        "gpu_memory_total_mb": None,
        "gpu_memory_used_mb": None,
        "driver_version": None,
        "cuda_version": None,
    }

    wsl_available = shutil.which("wsl") is not None
    status["available"] = wsl_available
    if not wsl_available:
        return status

    try:
        result = subprocess.run(["wsl", "--status"], capture_output=True, text=True, timeout=3)
        status["status"] = "running" if result.returncode == 0 else "stopped"
        status["status_output"] = result.stdout
    except Exception as e:
        logger.debug(f"WSL status check failed: {e}")
        status["status"] = "unknown"

    try:
        list_result = subprocess.run(["wsl", "-l", "-v"], capture_output=True, text=True, timeout=5)
        status["list_output"] = list_result.stdout
    except Exception:
        pass

    try:
        vllm_check = subprocess.run(
            ["wsl", "-d", _WSL_DISTRO, "--", "systemctl", "is-active", "vllm-llama1b.service"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        status["vllm_service"] = "active" if vllm_check.returncode == 0 else "inactive"
    except Exception as e:
        logger.debug(f"vLLM service check failed: {e}")

    try:
        audio_check = subprocess.run(
            [
                "wsl",
                "-d",
                _WSL_DISTRO,
                "--",
                "bash",
                "-lc",
                "python3 - <<'PY'\nimport importlib.util\nok = importlib.util.find_spec('faster_whisper') is not None\nprint('ok' if ok else 'error')\nPY",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        status["audio_processing"] = "available" if "ok" in audio_check.stdout else "unavailable"
        status["faster_whisper"] = "ready" if "ok" in audio_check.stdout else "not_installed"
    except Exception as e:
        logger.debug(f"WSL2 audio check skipped: {e}")

    try:
        gpu_info = subprocess.run(
            [
                "wsl",
                "-d",
                _WSL_DISTRO,
                "--",
                "bash",
                "-lc",
                "nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader,nounits | head -n1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if gpu_info.returncode == 0 and gpu_info.stdout.strip():
            parts = [p.strip() for p in gpu_info.stdout.strip().split(",")]
            if len(parts) >= 4:
                status["gpu_name"] = parts[0]
                status["gpu_memory_total_mb"] = int(parts[1])
                status["gpu_memory_used_mb"] = int(parts[2])
                status["driver_version"] = parts[3]

        cuda_info = subprocess.run(
            [
                "wsl",
                "-d",
                _WSL_DISTRO,
                "--",
                "bash",
                "-lc",
                "nvidia-smi --query-gpu=cuda_version --format=csv,noheader,nounits | head -n1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if cuda_info.returncode == 0 and cuda_info.stdout.strip():
            status["cuda_version"] = cuda_info.stdout.strip()
    except Exception as e:
        logger.debug(f"WSL2 GPU probe failed: {e}")

    status["active"] = status.get("status") == "running" or status.get("vllm_service") == "active"
    return status


def _database_status(db_path: str | Path | None = None) -> Dict[str, Any]:
    path = Path(db_path) if db_path is not None else _DB_PATH
    data = {"exists": False, "scenes": 0}
    try:
        data["exists"] = path.exists()
        if not data["exists"]:
            return data

        read_only_uri = f"{path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(read_only_uri, uri=True, timeout=0.2) as conn:
            table_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scenes'"
            ).fetchone()
            if table_row is None:
                return data
            count_row = conn.execute("SELECT COUNT(*) FROM scenes").fetchone()
            data["scenes"] = int((count_row or [0])[0] or 0)
    except Exception as exc:
        logger.warning("api status database scene count unavailable path=%s error=%s", path, exc)
    return data


@router.get("/api/status")
@router.head("/api/status")
def get_status() -> Dict[str, Any]:
    """System status endpoint - fast aggregated health check."""
    gpu_data = {"gpu_utilization": 0, "gpu_memory_used": 0, "gpu_memory_total": 0}
    models_data = {"total": 2, "healthy": 0, "vllm_healthy": 0, "ollama_healthy": 0}
    processing_data = {"status": "idle", "current_video": None, "progress_percent": 0}

    try:
        try:
            resp = requests.get("http://localhost:38005/v1/models", timeout=0.2)
            if resp.status_code == 200:
                models_data["vllm_healthy"] = 1
                models_data["healthy"] += 1
        except Exception as e:
            logger.debug(f"vLLM quick health check failed: {e}")

        try:
            ollama_models_url, _ = _get_ollama_models_url(_CFG)
            if ollama_models_url:
                resp = requests.get(ollama_models_url, timeout=0.2)
                if resp.status_code == 200:
                    models_data["ollama_healthy"] = 1
                    models_data["healthy"] += 1
        except Exception as e:
            logger.debug(f"Ollama quick health check failed: {e}")
    except Exception as e:
        logger.debug(f"Model health checks failed: {e}")

    try:
        resp = requests.get("http://localhost:5001/api/processing/stats", timeout=0.3)
        if resp.status_code == 200:
            stats = resp.json()
            processing_data = {
                "status": stats.get("status", "idle"),
                "current_video": stats.get("current_video", {}).get("name"),
                "progress_percent": stats.get("current_video", {}).get("progress_percent", 0),
            }
    except Exception:
        pass

    database_data = _database_status()

    wsl_status = _collect_wsl_status()

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=0.3,
        )
        if result.returncode == 0:
            gpu_util, mem_used, mem_total = result.stdout.strip().split(",")
            gpu_data = {
                "gpu_utilization": int(gpu_util.strip()),
                "gpu_memory_used": int(mem_used.strip()),
                "gpu_memory_total": int(mem_total.strip()),
            }
    except Exception:
        pass

    return {
        "status": "active",
        "version": GOODQ_VERSION,
        "components": {
            "api": "running",
            "pipeline": processing_data["status"],
            "wsl_audio": "available" if wsl_status.get("available") else "unavailable",
        },
        "gpu": gpu_data,
        "models": models_data,
        "processing": processing_data,
        "database": database_data,
        "wsl": wsl_status,
    }


@router.get("/api/health/summary")
def get_health_summary() -> Dict[str, Any]:
    """Get health summary for all LLM models (vLLM + Ollama)."""
    vllm_healthy = 0
    ollama_healthy = 0
    total_vllm = 1
    total_ollama = 1

    try:
        resp = requests.get("http://localhost:38005/v1/models", timeout=1)
        if resp.status_code == 200:
            vllm_healthy = 1
    except Exception as e:
        logger.debug(f"vLLM health summary check failed: {e}")

    try:
        ollama_models_url, _ = _get_ollama_models_url(_CFG)
        if ollama_models_url:
            resp = requests.get(ollama_models_url, timeout=1)
            if resp.status_code == 200:
                ollama_healthy = 1
    except Exception as e:
        logger.debug(f"Ollama health summary check failed: {e}")

    total = 2
    healthy = vllm_healthy + ollama_healthy

    return {
        "overall": {
            "status": "healthy" if healthy == total else "degraded" if healthy > 0 else "unhealthy",
            "total": total,
            "healthy": healthy,
            "unhealthy": total - healthy,
        },
        "vllm": {
            "status": "healthy" if vllm_healthy > 0 else "unhealthy",
            "healthy": vllm_healthy,
            "total": total_vllm,
            "models": ["Llama-1B-Speed"] if vllm_healthy > 0 else [],
        },
        "ollama": {
            "status": "healthy" if ollama_healthy > 0 else "unhealthy",
            "healthy": ollama_healthy,
            "total": total_ollama,
            "models": ["Phi4-Ollama"] if ollama_healthy > 0 else [],
        },
    }


@router.get("/api/engines")
def get_engines() -> Dict[str, Any]:
    """Get model engine health aggregate (summary + details)."""
    details = _collect_engine_details()
    summary = _summarize_llm_health()
    return {
        "engines": details,
        "details": details,
        "summary": summary,
        "vllm": summary["vllm"],
        "ollama": summary["ollama"],
        "overall": summary["overall"],
        "timestamp": summary["timestamp"],
        **details,
    }


@router.get("/api/queue")
def get_queue() -> Dict[str, Any]:
    """Get current processing queue."""
    processing_dir = _PROCESSING_PATH
    processed_dir = _PROCESSING_PATH.parent / "processed"
    failed_dir = _PROCESSING_PATH.parent / "failed"

    queue_data = {
        "inbox": {"count": 0, "files": [], "total_size_mb": 0},
        "processing": {"count": 0, "files": []},
        "processed": {"count": 0},
        "failed": {"count": 0},
    }

    try:
        if _IMPORT_INBOX.exists():
            inbox_files = [
                f
                for f in _IMPORT_INBOX.iterdir()
                if f.is_file()
                and not f.name.startswith(".")
                and not f.name.startswith("PROCESSED_")
                and not f.name.startswith("FAILED_")
                and is_supported_ingest_path(f)
            ]
            queue_data["inbox"]["count"] = len(inbox_files)
            queue_data["inbox"]["files"] = [
                {"name": f.name, "size_mb": round(f.stat().st_size / (1024 ** 2), 2)}
                for f in inbox_files[:10]
            ]
            queue_data["inbox"]["total_size_mb"] = round(sum(f.stat().st_size for f in inbox_files) / (1024 ** 2), 2)

        if processing_dir.exists():
            processing_items = list(processing_dir.iterdir())
            queue_data["processing"]["count"] = len(processing_items)
            queue_data["processing"]["files"] = [d.name for d in processing_items[:5]]

        if processed_dir.exists():
            queue_data["processed"]["count"] = len(list(processed_dir.iterdir()))

        if failed_dir.exists():
            queue_data["failed"]["count"] = len(list(failed_dir.iterdir()))
    except Exception as e:
        logger.warning(f"Queue status error: {e}")

    return queue_data


def _bytes_to_mb(value: int) -> float:
    return round(value / (1024 ** 2), 2)


def _bytes_to_gb(value: int) -> float:
    return round(value / (1024 ** 3), 2)


def _safe_dir_size(path: Path, *, max_entries: int = 20000, max_seconds: float = 1.25) -> Dict[str, Any]:
    """Bounded directory size scan for UI diagnostics; never returns raw paths."""
    if not path.exists():
        return {
            "exists": False,
            "size_mb": 0,
            "file_count": 0,
            "dir_count": 0,
            "scan_status": "not_configured",
        }
    if path.is_file():
        try:
            return {
                "exists": True,
                "size_mb": _bytes_to_mb(path.stat().st_size),
                "file_count": 1,
                "dir_count": 0,
                "scan_status": "complete",
            }
        except Exception as exc:
            logger.debug("storage file stat failed name=%s error=%s", path.name, exc)
            return {"exists": True, "size_mb": 0, "file_count": 0, "dir_count": 0, "scan_status": "unreadable"}

    started = time.monotonic()
    total = 0
    file_count = 0
    dir_count = 0
    scanned = 0
    stack = [path]
    partial_reason: str | None = None

    while stack:
        if scanned >= max_entries:
            partial_reason = "entry_limit"
            break
        if time.monotonic() - started > max_seconds:
            partial_reason = "time_limit"
            break
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned >= max_entries:
                        partial_reason = "entry_limit"
                        break
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            dir_count += 1
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            file_count += 1
                            total += entry.stat(follow_symlinks=False).st_size
                    except Exception:
                        continue
        except Exception as exc:
            logger.debug("storage directory scan skipped name=%s error=%s", current.name, exc)
            continue

    status = "partial" if partial_reason else "complete"
    return {
        "exists": True,
        "size_mb": _bytes_to_mb(total),
        "file_count": file_count,
        "dir_count": dir_count,
        "scan_status": status,
        "partial_reason": partial_reason,
    }


def _storage_row(name: str, label: str, path: Path) -> Dict[str, Any]:
    row = {
        "name": name,
        "label": label,
        "path_label": label,
        "path_redacted": True,
    }
    row.update(_safe_dir_size(path))
    return row


def _safe_name_label(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    raw = value.strip()
    if not raw:
        return value

    windows_name = PureWindowsPath(raw).name
    posix_name = PurePosixPath(raw).name
    name = windows_name if len(windows_name) <= len(posix_name) else posix_name
    return name or value


def _path_redacted_label(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return "<local-only>"
    return None


def _latest_episode_preview(episode: Any) -> Dict[str, Any] | None:
    if not isinstance(episode, dict):
        return None

    artifact_count = 0
    artifact_paths_redacted = False
    for key in ("canonical_episode_artifacts", "files_read"):
        values = episode.get(key)
        if isinstance(values, list):
            artifact_count += len(values)
            artifact_paths_redacted = artifact_paths_redacted or bool(values)

    return {
        "episode": _safe_name_label(episode.get("episode")),
        "status": episode.get("status"),
        "scene_count": episode.get("scene_count"),
        "phase6_complete": episode.get("phase6_complete"),
        "qdrant_ok": episode.get("qdrant_ok"),
        "ts_utc": episode.get("ts_utc"),
        "artifact_count": artifact_count,
        "artifact_paths_redacted": artifact_paths_redacted,
    }


@router.get("/api/storage/summary")
def get_storage_summary() -> Dict[str, Any]:
    """Read-only storage growth surface with redacted local paths."""
    processed_dir = _PROCESSING_PATH.parent / "processed"
    failed_dir = _PROCESSING_PATH.parent / "failed"
    rows = [
        _storage_row("data_root", "<GOODQ_DATA_ROOT>\\GoodQ_Data", _DATA_ROOT),
        _storage_row("import_inbox", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\import_inbox", _IMPORT_INBOX),
        _storage_row("processing", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\epochs\\<epoch>\\processing", _PROCESSING_PATH),
        _storage_row("processed", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\processed", processed_dir),
        _storage_row("failed", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\failed", failed_dir),
        _storage_row("logs", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\epochs\\<epoch>\\logs", _LOG_DIR),
        _storage_row("qdrant_storage", "<GOODQ_DATA_ROOT>\\qdrant_storage", _QDRANT_STORAGE),
        _storage_row("faiss", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\epochs\\<epoch>\\faiss", _FAISS_DIR),
        _storage_row("model_cache", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\cache", _MODEL_CACHE),
        _storage_row("report_artifacts", "<GOODQ_DATA_ROOT>\\GoodQ_Data\\reports", _REPORTS_ROOT),
    ]

    disk: Dict[str, Any]
    try:
        usage = shutil.disk_usage(str(_DATA_ROOT if _DATA_ROOT.exists() else _PROJECT_ROOT))
        disk = {
            "available": True,
            "scope": "data root volume",
            "free_gb": _bytes_to_gb(usage.free),
            "total_gb": _bytes_to_gb(usage.total),
            "used_gb": _bytes_to_gb(usage.used),
            "used_percent": round((usage.used / usage.total) * 100, 1) if usage.total else None,
        }
    except Exception as exc:
        logger.warning("storage disk usage unavailable error=%s", exc)
        disk = {"available": False, "scope": "data root volume"}

    return {
        "status": "ok" if any(row.get("exists") for row in rows) else "not_configured",
        "mode": "read_only",
        "raw_paths": "redacted",
        "scan_policy": {"max_entries_per_root": 20000, "max_seconds_per_root": 1.25},
        "disk": disk,
        "roots": rows,
    }


@router.get("/api/gpu/stats")
def get_gpu_stats() -> Dict[str, Any]:
    """Get GPU statistics."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 5:
                return {
                    "available": True,
                    "name": parts[0],
                    "utilization_percent": int(parts[1]),
                    "memory_used_mb": int(parts[2]),
                    "memory_total_mb": int(parts[3]),
                    "memory_percent": round((int(parts[2]) / int(parts[3])) * 100, 1),
                    "temperature_c": int(parts[4]),
                }
    except Exception as e:
        logger.error(f"Error getting GPU stats: {e}")

    return {"available": False, "error": "GPU not available"}


@router.get("/api/wsl2-status")
def get_wsl2_status() -> Dict[str, Any]:
    """Get WSL2 status (consolidated helper)."""
    return _collect_wsl_status()


@router.get("/api/models")
def get_models() -> Dict[str, Any]:
    """Get LLM model health status - proxies health API."""
    try:
        resp = requests.get("http://localhost:5050/api/health", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Model health service unavailable: {e}")

    return {
        "timestamp": None,
        "total_models": 0,
        "healthy_models": 0,
        "vllm_total": 0,
        "vllm_healthy": 0,
        "ollama_total": 0,
        "ollama_healthy": 0,
        "models": [],
    }


def _latest_run_snapshot(limit: int = 12) -> Dict[str, Any]:
    """Inspect logs/watchdog_* folders for the most recent run and return summary counts."""
    runs = sorted(Path("logs").glob("watchdog_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        return {"available": False}
    run_dir = next((r for r in runs if r.is_dir()), None)
    if not run_dir:
        return {"available": False}

    subdirs = [d for d in run_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
    video_dir = subdirs[0] if subdirs else run_dir

    frames = sorted(video_dir.glob("frames/*.jpg"))
    audio = sorted(video_dir.glob("audio/*.wav"))

    return {
        "available": True,
        "run_id": run_dir.name,
        "video": video_dir.name,
        "scenes": len({f.stem.split('_')[1] for f in frames}) if frames else 0,
        "frames": len(frames),
        "audio": len(audio),
        "run_path": str(run_dir),
        "log_tail": _tail_log(run_dir / "watchdog.log", lines=100) if (run_dir / "watchdog.log").exists() else [],
    }


def _latest_run_preview(limit: int = 12) -> Dict[str, Any]:
    """Return a truthful preview of the most recent structured run artifact root."""
    runs = _runtime_visible_runs(limit=1)
    if not runs:
        return {"available": False}

    latest = runs[0]
    summary = _load_runtime_visible_run_summary(latest)
    header = summary.get("run_header") if isinstance(summary, dict) else {}
    overview = summary.get("file_job_overview") if isinstance(summary, dict) else {}
    outcome = summary.get("outcome_classification") if isinstance(summary, dict) else {}
    latest_episode = _latest_episode_preview(summary.get("latest_episode"))

    return {
        "available": True,
        "run_id": header.get("run_id"),
        "run_kind": header.get("run_kind") or latest.get("run_kind"),
        "scope": header.get("scope") or latest.get("scope"),
        "status": outcome.get("status") or header.get("status"),
        "epoch": header.get("epoch"),
        "source_dir": _path_redacted_label(header.get("source_dir")),
        "source_dir_redacted": bool(header.get("source_dir")),
        "raw_paths": "redacted",
        "start_time": header.get("start_time"),
        "end_time": header.get("end_time"),
        "total_duration_seconds": header.get("total_duration_seconds"),
        "episodes_total": overview.get("episodes_total"),
        "episodes_completed": overview.get("episodes_completed"),
        "episodes_failed": overview.get("episodes_failed"),
        "episodes_running": overview.get("episodes_running"),
        "episodes_pending": overview.get("episodes_pending"),
        "scenes_processed": overview.get("scenes_processed"),
        "latest_episode": latest_episode,
    }


def _latest_run_evidence(limit: int = 24) -> Dict[str, Any]:
    """Return sanitized read-only evidence projections for the latest structured run."""
    runs = _runtime_visible_runs(limit=1)
    if not runs:
        return _empty_run_evidence("no_indexed_runs")

    latest = runs[0]
    try:
        summary = _load_runtime_visible_run_summary(latest)
    except Exception as exc:
        logger.warning("latest run evidence summary unavailable error=%s", exc)
        return _empty_run_evidence("summary_unavailable")

    if not isinstance(summary, dict):
        return _empty_run_evidence("summary_unavailable")

    header = summary.get("run_header") if isinstance(summary.get("run_header"), dict) else {}
    overview = summary.get("file_job_overview") if isinstance(summary.get("file_job_overview"), dict) else {}
    outcome = summary.get("outcome_classification") if isinstance(summary.get("outcome_classification"), dict) else {}
    latest_episode = summary.get("latest_episode") if isinstance(summary.get("latest_episode"), dict) else {}

    scene_results_path = _episode_artifact_path(latest_episode, "scene_ingest_results.json")
    scene_results_payload = _load_json_any(scene_results_path)
    temporal_path = _episode_artifact_path(latest_episode, "temporal_index.json")
    if temporal_path is None:
        temporal_path = _artifact_path_from_scene_results(scene_results_payload, "temporal_index.json")
    step_runs_path = _find_step_runs_path(latest_episode, [temporal_path, scene_results_path])

    temporal_payload = _load_json_any(temporal_path)

    return {
        "available": True,
        "run": {
            "run_id": header.get("run_id") or latest.get("run_id"),
            "run_kind": header.get("run_kind") or latest.get("run_kind"),
            "scope": header.get("scope") or latest.get("scope"),
            "status": outcome.get("status") or header.get("status") or latest.get("status"),
            "epoch": header.get("epoch") or latest.get("epoch"),
            "episodes_total": overview.get("episodes_total"),
            "episodes_completed": overview.get("episodes_completed"),
            "episodes_failed": overview.get("episodes_failed"),
            "scenes_processed": overview.get("scenes_processed"),
        },
        "latest_episode": _episode_evidence_summary(latest_episode),
        "artifact_presence": {
            "step_runs_jsonl": bool(step_runs_path and step_runs_path.is_file()),
            "temporal_index_json": bool(temporal_path and temporal_path.is_file()),
            "scene_ingest_results_json": bool(scene_results_path and scene_results_path.is_file()),
        },
        "step_runs": _summarize_step_runs(step_runs_path, limit=limit),
        "temporal_index": _summarize_temporal_index(temporal_payload),
        "sentiment": _summarize_sentiment(temporal_payload, scene_results_payload=scene_results_payload),
        "knowledge_graph": _summarize_knowledge_graph(scene_results_payload, latest_episode),
        "projection_gaps": _summarize_projection_gaps(temporal_payload, scene_results_payload),
        "audio_vector_proof": _summarize_audio_vector_proof(
            header=header,
            latest_episode=latest_episode,
            temporal_payload=temporal_payload,
            scene_results_payload=scene_results_payload,
        ),
        "safety_boundary": _run_evidence_safety_boundary(),
    }


def _runtime_visible_runs(limit: int | None = None) -> List[Dict[str, Any]]:
    """Return report-index runs plus the current configured CLI output, newest first."""

    runs = list(run_index.list_runs(limit=None))
    configured = _configured_scene_results_run()
    if configured is not None:
        configured_path = str(configured.get("scene_results_path") or "")
        runs = [
            run
            for run in runs
            if str(run.get("scene_results_path") or "") != configured_path
        ]
        runs.append(configured)

    runs.sort(key=lambda run: (_run_entry_mtime(run), str(run.get("run_id") or "")), reverse=True)
    if isinstance(limit, int) and limit >= 0:
        return runs[:limit]
    return runs


def _load_runtime_visible_run_summary(run: Dict[str, Any]) -> Dict[str, Any]:
    if run.get("scope") == "configured_output_scene_results":
        return _configured_scene_results_summary(run)
    return run_summary.load_run_summary(run_root=run.get("run_root") or run["run_id"])


def _configured_scene_results_run() -> Dict[str, Any] | None:
    output_dir = _PATHS_CFG.get("output_directory")
    if not output_dir:
        return None
    scene_results_path = (Path(str(output_dir)) / "scene_ingest_results.json").resolve()
    if not scene_results_path.is_file():
        return None

    payload = _load_json_any(scene_results_path)
    if payload is None:
        return None

    scene_records = _scene_records_from_results(payload)
    scene_count = len(scene_records)
    runtime_run_id, runtime_source = _resolve_runtime_audio_run_id({}, {}, payload)
    first_record = _first_result_record(payload)
    video_name = _first_text_value(
        first_record.get("video_name") if isinstance(first_record, dict) else None,
        first_record.get("video") if isinstance(first_record, dict) else None,
        first_record.get("filename") if isinstance(first_record, dict) else None,
        "Configured CLI output",
    )
    run_id = runtime_run_id or f"configured_output:{scene_results_path.parent.parent.name}"
    stat = scene_results_path.stat()

    return {
        "run_id": run_id,
        "runtime_run_id": runtime_run_id,
        "runtime_run_id_source": runtime_source,
        "run_kind": "configured_scene_results",
        "scope": "configured_output_scene_results",
        "run_root": str(scene_results_path.parent.parent),
        "root_log_path": None,
        "scene_results_path": str(scene_results_path),
        "status": "completed" if scene_count > 0 else "unknown",
        "epoch": _epoch_name_from_path(scene_results_path),
        "source_dir": None,
        "started_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "episodes_total": 1 if scene_count > 0 else 0,
        "episodes_completed": 1 if scene_count > 0 else 0,
        "episodes_failed": 0,
        "episodes_running": 0,
        "episodes_pending": 0,
        "scenes_processed": scene_count,
        "latest_episode": {
            "episode": video_name,
            "status": "completed" if scene_count > 0 else "unknown",
            "run_dir": str(scene_results_path.parent.parent),
            "scene_count": scene_count,
            "files_read": [str(scene_results_path)],
            "canonical_episode_artifacts": [],
            "errors": [],
            "warnings": [],
        },
        "_sort_ts": stat.st_mtime,
    }


def _configured_scene_results_summary(run: Dict[str, Any]) -> Dict[str, Any]:
    latest_episode = run.get("latest_episode") if isinstance(run.get("latest_episode"), dict) else {}
    qdrant_cfg = _CFG.get("qdrant") if isinstance(_CFG.get("qdrant"), dict) else {}
    qdrant_collections = qdrant_cfg.get("collections") if isinstance(qdrant_cfg.get("collections"), dict) else {}
    return {
        "run_header": {
            "run_id": run.get("run_id"),
            "runtime_run_id": run.get("runtime_run_id"),
            "runtime_run_id_source": run.get("runtime_run_id_source"),
            "qdrant_collections": qdrant_collections,
            "run_kind": run.get("run_kind") or "configured_scene_results",
            "scope": run.get("scope") or "configured_output_scene_results",
            "epoch": run.get("epoch"),
            "status": run.get("status"),
            "source_dir": run.get("source_dir"),
            "start_time": run.get("started_at"),
            "end_time": "unknown",
            "total_duration_seconds": "unknown",
            "trigger_source": "cli.run_ingestion",
        },
        "file_job_overview": {
            "input_files": [latest_episode.get("episode")] if latest_episode.get("episode") else [],
            "episodes_total": run.get("episodes_total", 0),
            "episodes_completed": run.get("episodes_completed", 0),
            "episodes_failed": run.get("episodes_failed", 0),
            "episodes_running": run.get("episodes_running", 0),
            "episodes_pending": run.get("episodes_pending", 0),
            "scenes_processed": run.get("scenes_processed", latest_episode.get("scene_count") or 0),
            "steps_executed": "unknown",
        },
        "audio_wsl2_summary": {
            "jobs_found": "unknown",
            "notes": "not observed",
        },
        "agent_activity": [],
        "errors_warnings": {
            "errors": latest_episode.get("errors") if isinstance(latest_episode.get("errors"), list) else [],
            "warnings": latest_episode.get("warnings") if isinstance(latest_episode.get("warnings"), list) else [],
        },
        "outcome_classification": {
            "status": run.get("status") or "unknown",
        },
        "evidence": {
            "files_read": latest_episode.get("files_read") if isinstance(latest_episode.get("files_read"), list) else [],
            "canonical_episode_artifacts": [],
        },
        "latest_episode": latest_episode,
        "episodes": [latest_episode] if latest_episode else [],
    }


def _run_entry_mtime(run: Dict[str, Any]) -> float:
    if isinstance(run.get("_sort_ts"), (int, float)):
        return float(run["_sort_ts"])
    for key in ("scene_results_path", "root_log_path", "config_path"):
        value = run.get(key)
        if isinstance(value, str) and value.strip():
            try:
                return Path(value).stat().st_mtime
            except Exception:
                continue
    value = run.get("run_root")
    if isinstance(value, str) and value.strip():
        try:
            return Path(value).stat().st_mtime
        except Exception:
            return 0.0
    return 0.0


def _epoch_name_from_path(path: Path) -> str | None:
    parts = path.parts
    for index, part in enumerate(parts):
        if part.lower() == "epochs" and index + 1 < len(parts):
            return parts[index + 1]
    db_dir = _PATHS_CFG.get("db_dir")
    if db_dir:
        return Path(str(db_dir)).name
    return None


def _first_text_value(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _empty_run_evidence(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "artifact_presence": {
            "step_runs_jsonl": False,
            "temporal_index_json": False,
            "scene_ingest_results_json": False,
        },
        "step_runs": {"status": "unavailable", "reason": reason},
        "temporal_index": {"status": "unavailable", "reason": reason},
        "sentiment": {"status": "unavailable", "reason": reason},
        "knowledge_graph": {"status": "unavailable", "reason": reason},
        "projection_gaps": {"status": "unavailable", "reason": reason},
        "audio_vector_proof": {"status": "unavailable", "reason": reason, "label": "Not Exposed"},
        "safety_boundary": _run_evidence_safety_boundary(),
    }


def _run_evidence_safety_boundary() -> Dict[str, str]:
    return {
        "mode": "read_only",
        "source": "latest structured run summary and referenced episode artifacts",
        "raw_paths": "redacted",
        "raw_logs": "not_returned",
        "ingestion": "not_triggered",
        "control_agent": "not_activated",
        "mutation": "not_attempted",
        "llm_usage": "not_used",
    }


def _episode_evidence_summary(episode: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "episode": episode.get("episode"),
        "status": episode.get("status"),
        "scene_count": episode.get("scene_count"),
        "phase6_complete": episode.get("phase6_complete"),
        "qdrant_ok": episode.get("qdrant_ok"),
        "ts_utc": episode.get("ts_utc"),
        "error_count": len(episode.get("errors") or []) if isinstance(episode.get("errors"), list) else 0,
        "warning_count": len(episode.get("warnings") or []) if isinstance(episode.get("warnings"), list) else 0,
    }


def _episode_artifact_path(episode: Dict[str, Any], filename: str) -> Path | None:
    for key in ("canonical_episode_artifacts", "files_read"):
        values = episode.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            candidate = Path(value)
            if candidate.name == filename and candidate.is_file():
                return candidate

    run_dir_value = episode.get("run_dir")
    if isinstance(run_dir_value, str) and run_dir_value.strip():
        run_dir = Path(run_dir_value)
        if run_dir.is_dir():
            for candidate in run_dir.rglob(filename):
                if candidate.is_file():
                    return candidate
    return None


def _artifact_path_from_scene_results(payload: Any, filename: str) -> Path | None:
    """Follow explicit artifact pointers embedded in standalone scene results."""

    def iter_pointer_values(value: Any, depth: int = 0):
        if depth > 4:
            return
        if isinstance(value, dict):
            for key in (
                "temporal_index_path",
                "temporal_index_json",
                "temporal_index_file",
                "path",
            ):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    yield candidate
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from iter_pointer_values(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:32]:
                if isinstance(child, (dict, list)):
                    yield from iter_pointer_values(child, depth + 1)

    for value in iter_pointer_values(payload):
        candidate = Path(value)
        if candidate.name == filename and candidate.is_file():
            return candidate
    return None


def _find_step_runs_path(episode: Dict[str, Any], artifact_paths: List[Path | None]) -> Path | None:
    run_dir_value = episode.get("run_dir")
    if isinstance(run_dir_value, str) and run_dir_value.strip():
        run_dir = Path(run_dir_value)
        for candidate in (
            run_dir / "step_runs.jsonl",
            run_dir / "logs" / "step_runs.jsonl",
            run_dir / "workspace" / "step_runs.jsonl",
            run_dir / "output" / "step_runs.jsonl",
        ):
            if candidate.is_file():
                return candidate

    for artifact_path in artifact_paths:
        if artifact_path is None:
            continue
        for parent in artifact_path.parents:
            candidate = parent / "logs" / "step_runs.jsonl"
            if candidate.is_file():
                return candidate
    return None


def _load_json_any(path: Path | None) -> Any:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("latest run evidence artifact unreadable name=%s error=%s", path.name, exc)
        return None


def _summarize_step_runs(path: Path | None, limit: int = 24) -> Dict[str, Any]:
    if path is None or not path.is_file():
        return {"status": "unavailable", "reason": "step_runs_jsonl_missing"}

    rows: List[Dict[str, Any]] = []
    malformed = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except Exception:
                    malformed += 1
                    continue
                if isinstance(value, dict):
                    rows.append(value)
    except Exception as exc:
        logger.warning("latest run evidence step_runs unreadable error=%s", exc)
        return {"status": "unavailable", "reason": "step_runs_unreadable"}

    status_counts = Counter(str(row.get("status") or "unknown").lower() for row in rows)
    step_counts = Counter(str(row.get("step") or row.get("step_name") or "unknown") for row in rows)
    durations = [_safe_float(row.get("duration_ms")) for row in rows]
    duration_values = [value for value in durations if value is not None]

    failed_count = 0
    warning_count = malformed
    for row in rows:
        status = str(row.get("status") or "").lower()
        error_text = str(row.get("error") or "").strip()
        if status in {"error", "failed", "fail"} or error_text:
            failed_count += 1
        if status in {"warn", "warning"} or row.get("warning"):
            warning_count += 1

    recent_rows = rows[-max(1, min(int(limit or 24), 100)) :]
    return {
        "status": "ok" if rows else "empty",
        "row_count": len(rows),
        "recent_count": len(recent_rows),
        "failed_count": failed_count,
        "warning_count": warning_count,
        "malformed_count": malformed,
        "latest_ts_utc": _latest_timestamp(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "duration_ms": _duration_summary(duration_values),
        "top_steps": [
            {"step": step, "count": count}
            for step, count in step_counts.most_common(8)
        ],
        "recent": [
            {
                "ts": row.get("ts") or row.get("ts_utc") or row.get("timestamp"),
                "step": row.get("step") or row.get("step_name"),
                "status": row.get("status"),
                "duration_ms": _round_number(row.get("duration_ms")),
                "modality": row.get("modality"),
            }
            for row in recent_rows[-8:]
        ],
    }


def _summarize_temporal_index(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "unavailable", "reason": "temporal_index_missing"}

    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    return {
        "status": "ok",
        "version": payload.get("version"),
        "total_scenes": payload.get("total_scenes") or len(segments),
        "total_duration": _round_number(payload.get("total_duration")),
        "content_summary": payload.get("content_summary"),
        "phase5_complete": payload.get("phase5_complete"),
        "phase6_complete": payload.get("phase6_complete"),
        "phase6_harmonized": payload.get("phase6_harmonized"),
        "has_visual_embeddings": payload.get("has_visual_embeddings"),
        "has_audio": payload.get("has_audio"),
        "has_transcripts": payload.get("has_transcripts"),
        "segments_with_scene_context_llm": payload.get("segments_with_scene_context_llm"),
        "segments_with_audio_emotion": payload.get("segments_with_audio_emotion"),
        "segments_with_time_hints": payload.get("segments_with_time_hints"),
        "segments_with_music_events": payload.get("segments_with_music_events"),
        "top_time_hints": _safe_top_values(payload.get("top_time_hints")),
        "top_scene_context_tags": _safe_top_values(payload.get("top_scene_context_tags")),
    }


def _audio_emotion_score_buckets_from_records(records: List[Dict[str, Any]], *, nested_audio: bool = False) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[float]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source = record.get("audio") if nested_audio and isinstance(record.get("audio"), dict) else record
        scores = source.get("audio_emotion_scores") or source.get("emotion_scores")
        if not isinstance(scores, dict):
            continue
        normalized_scores: Dict[str, float] = {}
        for label, score in scores.items():
            normalized_label = str(label or "").strip().lower()
            score_value = _safe_float(score)
            if normalized_label and score_value is not None:
                normalized_scores[normalized_label] = score_value
        if not normalized_scores:
            continue
        top_label, top_score = max(normalized_scores.items(), key=lambda item: item[1])
        buckets.setdefault(top_label, []).append(top_score)

    rows: List[Dict[str, Any]] = []
    for label, values in buckets.items():
        rows.append(
            {
                "label": label,
                "count": len(values),
                "average_score": _round_number(sum(values) / len(values)),
                "max_score": _round_number(max(values)),
                "scope": "raw_score_not_promoted",
            }
        )
    return sorted(rows, key=lambda row: (row.get("count") or 0, row.get("max_score") or 0), reverse=True)[:8]


def _count_audio_emotion_score_records(records: List[Dict[str, Any]], *, nested_audio: bool = False) -> int:
    count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        source = record.get("audio") if nested_audio and isinstance(record.get("audio"), dict) else record
        scores = source.get("audio_emotion_scores") or source.get("emotion_scores")
        if isinstance(scores, dict) and any(_safe_float(value) is not None for value in scores.values()):
            count += 1
    return count


def _text_emotion_buckets_from_records(records: List[Dict[str, Any]], *, nested_audio: bool = False) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[float]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source = record.get("audio") if nested_audio and isinstance(record.get("audio"), dict) else record
        ranking = source.get("text_emotion_ranking") or source.get("emotions")
        if not isinstance(ranking, list):
            continue
        for row in ranking[:1]:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or row.get("emotion") or "").strip().lower()
            score = _safe_float(row.get("score"))
            if label and score is not None:
                buckets.setdefault(label, []).append(score)

    rows: List[Dict[str, Any]] = []
    for label, values in buckets.items():
        rows.append(
            {
                "emotion": label,
                "count": len(values),
                "average_score": _round_number(sum(values) / len(values)),
                "max_score": _round_number(max(values)),
            }
        )
    return sorted(rows, key=lambda row: (row.get("count") or 0, row.get("max_score") or 0), reverse=True)[:8]


def _summarize_sentiment(payload: Any, *, scene_results_payload: Any = None) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        scene_records = _scene_records_from_results(scene_results_payload)
        if not scene_records:
            return {"status": "unavailable", "reason": "temporal_index_missing"}

        audio_emotions: Counter[str] = Counter()
        sentiment_labels: Counter[str] = Counter()
        sentiment_scores: List[float] = []
        transcript_count = 0
        audio_score_count = _count_audio_emotion_score_records(scene_records, nested_audio=True)
        text_emotion_rows = _text_emotion_buckets_from_records(scene_records, nested_audio=True)

        for scene in scene_records:
            audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
            transcript = (
                audio.get("transcript")
                or audio.get("full_text")
                or audio.get("full_transcript")
                or scene.get("transcript")
                or scene.get("full_text")
                or scene.get("full_transcript")
            )
            segments = audio.get("segments") if isinstance(audio.get("segments"), list) else scene.get("segments")
            transcript_segments = (
                audio.get("transcript_segments")
                if isinstance(audio.get("transcript_segments"), list)
                else scene.get("transcript_segments")
            )
            if (
                (isinstance(transcript, str) and transcript.strip())
                or (isinstance(segments, list) and segments)
                or (isinstance(transcript_segments, list) and transcript_segments)
            ):
                transcript_count += 1

            audio_emotion = audio.get("audio_emotion") or audio.get("emotion") or scene.get("audio_emotion")
            if isinstance(audio_emotion, str) and audio_emotion.strip():
                audio_emotions[audio_emotion.strip().lower()] += 1

            label = audio.get("sentiment_label") or scene.get("sentiment_label")
            score = audio.get("sentiment_score") if audio.get("sentiment_score") is not None else scene.get("sentiment_score")
            sentiment = audio.get("sentiment") if isinstance(audio.get("sentiment"), dict) else scene.get("sentiment")
            if isinstance(sentiment, dict):
                label = label or sentiment.get("label")
                score = score if score is not None else sentiment.get("score")
            if isinstance(label, str) and label.strip():
                sentiment_labels[label.strip().lower()] += 1
            score_value = _safe_float(score)
            if score_value is not None:
                sentiment_scores.append(score_value)

        return {
            "status": "ok" if audio_emotions or sentiment_labels or transcript_count or audio_score_count else "not_observed",
            "source": "scene_ingest_results",
                "segments_total": len(scene_records),
                "segments_with_transcript": transcript_count,
                "segments_with_audio_emotion": sum(audio_emotions.values()),
                "segments_with_audio_emotion_scores": audio_score_count,
                "segments_with_audio_emotion_ranking": audio_score_count,
                "segments_with_text_emotion_ranking": sum(row.get("count", 0) for row in text_emotion_rows),
                "segments_with_sentiment": sum(sentiment_labels.values()),
            "top_audio_emotions": [
                {"label": label, "count": count}
                for label, count in audio_emotions.most_common(8)
            ],
                "top_audio_emotion_score_signals": _audio_emotion_score_buckets_from_records(scene_records, nested_audio=True),
                "top_text_emotions": text_emotion_rows,
                "sentiment_labels": [
                {"label": label, "count": count}
                for label, count in sentiment_labels.most_common(8)
            ],
                "average_sentiment_score": _round_number(sum(sentiment_scores) / len(sentiment_scores)) if sentiment_scores else None,
                "audio_emotion_policy": {
                    "promoted_label_threshold": _AUDIO_EMOTION_PROMOTION_THRESHOLD,
                    "promoted_labels": sum(audio_emotions.values()),
                    "ranked_score_segments": audio_score_count,
                    "scope": "ranked_scores_do_not_equal_labels",
                },
            }

    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    audio_emotions: Counter[str] = Counter()
    sentiment_labels: Counter[str] = Counter()
    sentiment_scores: List[float] = []
    transcript_count = 0
    audio_score_count = _count_audio_emotion_score_records(segments)
    text_emotion_rows = payload.get("top_text_emotions") if isinstance(payload.get("top_text_emotions"), list) else None
    if text_emotion_rows is None:
        text_emotion_rows = _text_emotion_buckets_from_records(segments)

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        transcript = segment.get("transcript") or segment.get("full_text") or segment.get("full_transcript")
        if (
            (isinstance(transcript, str) and transcript.strip())
            or isinstance(segment.get("segments"), list)
            or (isinstance(segment.get("transcript_segments"), list) and segment.get("transcript_segments"))
        ):
            transcript_count += 1
        audio_emotion = segment.get("audio_emotion")
        if isinstance(audio_emotion, str) and audio_emotion.strip():
            audio_emotions[audio_emotion.strip().lower()] += 1

        label = segment.get("sentiment_label")
        score = segment.get("sentiment_score")
        sentiment = segment.get("sentiment")
        if isinstance(sentiment, dict):
            label = label or sentiment.get("label")
            score = score if score is not None else sentiment.get("score")
        if isinstance(label, str) and label.strip():
            sentiment_labels[label.strip().lower()] += 1
        score_value = _safe_float(score)
        if score_value is not None:
            sentiment_scores.append(score_value)

    top_audio = _safe_top_values(payload.get("top_audio_emotions"))
    if not top_audio:
        top_audio = [{"label": label, "count": count} for label, count in audio_emotions.most_common(8)]

    return {
        "status": "ok" if audio_emotions or sentiment_labels or top_audio or audio_score_count else "not_observed",
        "source": "temporal_index",
        "segments_total": len(segments),
        "segments_with_transcript": payload.get("segments_with_transcript") or transcript_count,
        "segments_with_audio_emotion": payload.get("segments_with_audio_emotion") or sum(audio_emotions.values()),
        "segments_with_audio_emotion_scores": payload.get("segments_with_audio_emotion_scores") or audio_score_count,
        "segments_with_audio_emotion_ranking": payload.get("segments_with_audio_emotion_ranking") or audio_score_count,
        "segments_with_text_emotion_ranking": payload.get("segments_with_text_emotion_ranking")
        or sum(row.get("count", 0) for row in text_emotion_rows if isinstance(row, dict)),
        "segments_with_sentiment": sum(sentiment_labels.values()),
        "top_audio_emotions": top_audio,
        "top_audio_emotion_score_signals": _audio_emotion_score_buckets_from_records(segments),
        "top_text_emotions": text_emotion_rows,
        "sentiment_labels": [
            {"label": label, "count": count}
            for label, count in sentiment_labels.most_common(8)
        ],
        "average_sentiment_score": _round_number(sum(sentiment_scores) / len(sentiment_scores)) if sentiment_scores else None,
        "audio_emotion_policy": payload.get("audio_emotion_policy")
        if isinstance(payload.get("audio_emotion_policy"), dict)
        else {
            "promoted_label_threshold": _AUDIO_EMOTION_PROMOTION_THRESHOLD,
            "promoted_labels": payload.get("segments_with_audio_emotion") or sum(audio_emotions.values()),
            "ranked_score_segments": payload.get("segments_with_audio_emotion_ranking") or audio_score_count,
            "scope": "ranked_scores_do_not_equal_labels",
        },
    }


def _summarize_knowledge_graph(payload: Any, episode: Dict[str, Any]) -> Dict[str, Any]:
    record = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else payload
    if not isinstance(record, dict):
        return {
            "status": "unavailable",
            "reason": "scene_ingest_results_missing",
            "phase6_complete": episode.get("phase6_complete"),
            "qdrant_ok": episode.get("qdrant_ok"),
        }

    scenes = record.get("scenes") if isinstance(record.get("scenes"), list) else []
    scene_meta = record.get("scene_meta") if isinstance(record.get("scene_meta"), dict) else {}
    return {
        "status": record.get("knowledge_graph_status") or "unknown",
        "scene_count": scene_meta.get("scene_count") or len(scenes) or episode.get("scene_count"),
        "qdrant_ok": record.get("qdrant_ok"),
        "faiss_ok": record.get("faiss_ok"),
        "phase6_complete": record.get("phase6_complete") or episode.get("phase6_complete"),
        "phase6_qdrant_ok": record.get("phase6_qdrant_ok"),
        "phase6_faiss_ok": record.get("phase6_faiss_ok"),
        "control_agent_status": record.get("control_agent_status"),
        "control_agent_reason": record.get("control_agent_reason"),
        "content_summary": record.get("content_summary"),
        "modality_status": _simple_mapping(record.get("modality_status")),
    }


def _summarize_projection_gaps(temporal_payload: Any, scene_results_payload: Any) -> Dict[str, Any]:
    """Compare source scene truth with temporal-index projection without returning raw values."""

    scene_records = _scene_records_from_results(scene_results_payload)
    if not scene_records:
        return {"status": "unavailable", "reason": "scene_records_missing"}
    if not isinstance(temporal_payload, dict):
        return {"status": "unavailable", "reason": "temporal_index_missing"}

    segments = temporal_payload.get("segments") if isinstance(temporal_payload.get("segments"), list) else []
    segments_by_id: Dict[str, Dict[str, Any]] = {}
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        for candidate in _projection_scene_id_candidates(segment):
            segments_by_id.setdefault(candidate, segment)

    field_names = ("visual_caption", "sentiment", "clap_meta")
    source_present: Counter[str] = Counter()
    temporal_present: Counter[str] = Counter()
    missing_from_temporal: Counter[str] = Counter()
    sample_missing: List[Dict[str, Any]] = []

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        for field in field_names:
            if _projection_temporal_observed(segment, field):
                temporal_present[field] += 1

    for index, scene in enumerate(scene_records):
        if not isinstance(scene, dict):
            continue
        segment = _projection_matching_segment(scene, index, segments, segments_by_id)
        missing_fields: List[str] = []
        for field in field_names:
            if not _projection_source_observed(scene, field):
                continue
            source_present[field] += 1
            if not _projection_temporal_observed(segment, field):
                missing_from_temporal[field] += 1
                missing_fields.append(field)
        if missing_fields and len(sample_missing) < 8:
            sample_missing.append(
                {
                    "scene_id": _projection_scene_label(scene, index),
                    "fields": missing_fields,
                }
            )

    fields: Dict[str, Dict[str, Any]] = {}
    for field in field_names:
        missing = int(missing_from_temporal.get(field, 0))
        fields[field] = {
            "source_present": int(source_present.get(field, 0)),
            "temporal_present": int(temporal_present.get(field, 0)),
            "missing_from_temporal": missing,
            "status": "gap_detected" if missing else "ok",
        }

    total_missing = sum(int(missing_from_temporal.get(field, 0)) for field in field_names)
    return {
        "status": "gap_detected" if total_missing else "ok",
        "mode": "read_only",
        "source": "scene_ingest_results_vs_temporal_index",
        "scene_scope_count": len(scene_records),
        "temporal_scene_count": len(segments),
        "missing_projection_count": total_missing,
        "fields": fields,
        "sample_missing": sample_missing,
    }


def _projection_scene_id_candidates(record: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for key in ("scene_id", "id", "segment_id"):
        value = record.get(key)
        if value is not None and str(value).strip():
            candidates.append(str(value).strip())
    for key in ("index", "scene_index"):
        value = record.get(key)
        if value is None:
            continue
        try:
            candidates.append(f"scene_{int(value):04d}")
        except Exception:
            text = str(value).strip()
            if text:
                candidates.append(text)

    seen: set[str] = set()
    out: List[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def _projection_matching_segment(
    scene: Dict[str, Any],
    index: int,
    segments: List[Any],
    segments_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    for candidate in _projection_scene_id_candidates(scene):
        segment = segments_by_id.get(candidate)
        if isinstance(segment, dict):
            return segment
    if 0 <= index < len(segments) and isinstance(segments[index], dict):
        return segments[index]
    return {}


def _projection_scene_label(scene: Dict[str, Any], index: int) -> str:
    for key in ("scene_id", "id"):
        value = scene.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    value = scene.get("index", scene.get("scene_index", index))
    try:
        return f"scene_{int(value):04d}"
    except Exception:
        return f"scene_{index:04d}"


def _projection_source_observed(scene: Dict[str, Any], field: str) -> bool:
    keyframe = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    if field == "visual_caption":
        return _projection_value_observed(_first_projection_value(
            scene.get("visual_caption"),
            scene.get("caption"),
            keyframe.get("caption"),
        ))
    if field == "sentiment":
        return _projection_value_observed(_first_projection_value(
            scene.get("sentiment"),
            scene.get("sentiment_label"),
            scene.get("sentiment_score"),
            audio.get("sentiment"),
            audio.get("sentiment_label"),
            audio.get("sentiment_score"),
        ))
    if field == "clap_meta":
        return _projection_value_observed(_first_projection_value(scene.get("clap_meta"), audio.get("clap_meta")))
    return False


def _projection_temporal_observed(segment: Dict[str, Any], field: str) -> bool:
    if not isinstance(segment, dict):
        return False
    if field == "visual_caption":
        return _projection_value_observed(segment.get("visual_caption"))
    if field == "sentiment":
        return _projection_value_observed(_first_projection_value(
            segment.get("sentiment"),
            segment.get("sentiment_label"),
            segment.get("sentiment_score"),
        ))
    if field == "clap_meta":
        return _projection_value_observed(segment.get("clap_meta"))
    return False


def _first_projection_value(*values: Any) -> Any:
    for value in values:
        if _projection_value_observed(value):
            return value
    return None


def _projection_value_observed(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _summarize_audio_vector_proof(
    *,
    header: Dict[str, Any],
    latest_episode: Dict[str, Any],
    temporal_payload: Any,
    scene_results_payload: Any,
) -> Dict[str, Any]:
    """Read-only current-run CLAP/Qdrant proof summary for UI consumers."""

    scene_records = _scene_records_from_results(scene_results_payload)
    scene_total = len(scene_records) or _temporal_scene_count(temporal_payload)
    scene_ids, video_ids = _audio_scene_scope(scene_records, temporal_payload)
    clap_counts = _clap_status_counts(scene_records)
    runtime_run_id, runtime_run_id_source = _resolve_runtime_audio_run_id(
        header,
        latest_episode,
        scene_results_payload,
    )
    collection_candidates = _audio_qdrant_collection_candidates(header.get("epoch"), header=header)
    base = {
        "contract": "docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md",
        "scenes_total": scene_total,
        "scene_scope_count": scene_total,
        "scene_identifier_count": len(scene_ids),
        "clap_ok": clap_counts.get("ok", 0),
        "clap_skipped": clap_counts.get("skipped", 0),
        "clap_error": clap_counts.get("error", 0),
        "clap_missing": clap_counts.get("missing", 0),
        "runtime_run_id_resolved": bool(runtime_run_id),
        "runtime_run_id_source": runtime_run_id_source,
        "collection_candidates": collection_candidates,
        "required_payload_fields": list(_AUDIO_QDRANT_REQUIRED_FIELDS),
        "current_run_qdrant_proven": 0,
        "qdrant_run_matched_points": 0,
        "provenance_unverified": 0,
        "missing_required_fields": {},
        "scene_mismatch_count": 0,
        "video_mismatch_count": 0,
    }

    if not runtime_run_id:
        return {
            **base,
            "status": "no_current_run_evidence",
            "reason": "runtime_run_id_unresolved",
            "label": "No Current-Run Evidence",
            "impact": "CLAP or legacy audio vectors may exist, but the audited runtime run id is not exposed.",
        }

    if not collection_candidates:
        return {
            **base,
            "status": "not_exposed",
            "reason": "audio_collection_unresolved",
            "label": "Not Exposed",
            "impact": "Audio Qdrant collection name is not available to the read-only projector.",
        }

    qdrant_result = _scroll_qdrant_audio_payloads(runtime_run_id, collection_candidates)
    base["collection"] = qdrant_result.get("collection")
    base["collection_error"] = qdrant_result.get("error")
    payloads = qdrant_result.get("payloads") if isinstance(qdrant_result.get("payloads"), list) else []
    base["qdrant_run_matched_points"] = len(payloads)

    if qdrant_result.get("status") != "ok":
        return {
            **base,
            "status": "not_exposed",
            "reason": qdrant_result.get("status") or "qdrant_unavailable",
            "label": "Not Exposed",
            "impact": "Qdrant audio proof could not be read without mutating state.",
        }

    proof = _evaluate_qdrant_audio_payloads(payloads, scene_ids=scene_ids, video_ids=video_ids)
    base.update(proof)
    if not payloads:
        base["audio_payload_sample"] = _sample_qdrant_audio_payloads(collection_candidates)
    clap_ok = int(base["clap_ok"] or 0)
    proven = int(base["current_run_qdrant_proven"] or 0)

    if proven and (clap_ok == 0 or proven >= clap_ok):
        status = "current_run_audio_vector_proven"
        label = "Proven"
        reason = "run_matched_payloads_satisfy_contract"
        impact = "Run-matched CLAP/Qdrant audio payloads satisfy the current-run provenance contract."
    elif proven:
        status = "partial"
        label = "Partial"
        reason = "partial_current_run_audio_vector_coverage"
        impact = "Some run-matched audio vectors are proven, but coverage is not complete for CLAP-ok scenes."
    elif payloads:
        status = "provenance_unverified_audio_vector_exists"
        label = "Historical Only"
        reason = "run_matched_payloads_missing_required_provenance"
        impact = "Run-matched audio points exist, but required provenance or scene/video matching is incomplete."
    else:
        status = "no_current_run_evidence"
        label = "No Current-Run Evidence"
        reason = "no_qdrant_payloads_matched_run_id"
        impact = "No Qdrant audio payloads match the audited runtime run id."

    return {
        **base,
        "status": status,
        "label": label,
        "reason": reason,
        "impact": impact,
    }


def _scene_records_from_results(payload: Any) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    containers = payload if isinstance(payload, list) else [payload]
    for container in containers:
        if not isinstance(container, dict):
            continue
        scenes = container.get("scenes")
        if isinstance(scenes, list):
            records.extend(scene for scene in scenes if isinstance(scene, dict))
    return records


def _temporal_scene_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    total = _safe_float(payload.get("total_scenes"))
    if total is not None:
        return int(total)
    segments = payload.get("segments")
    return len(segments) if isinstance(segments, list) else 0


def _audio_scene_scope(scene_records: List[Dict[str, Any]], temporal_payload: Any) -> tuple[set[str], set[str]]:
    scene_ids: set[str] = set()
    video_ids: set[str] = set()

    def add_scene_values(record: Dict[str, Any]) -> None:
        for key in ("scene_id", "id"):
            value = record.get(key)
            if value is not None and str(value).strip():
                scene_ids.add(str(value).strip())
        scene_index = record.get("index", record.get("scene_index"))
        if scene_index is not None:
            try:
                scene_ids.add(f"scene_{int(scene_index):04d}")
            except Exception:
                scene_ids.add(str(scene_index).strip())
        for key in ("video_id", "video_hash"):
            value = record.get(key)
            if value is not None and str(value).strip():
                video_ids.add(str(value).strip())

    for scene in scene_records:
        add_scene_values(scene)
        audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
        add_scene_values(audio)

    if isinstance(temporal_payload, dict):
        segments = temporal_payload.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if isinstance(segment, dict):
                    add_scene_values(segment)
        video_id = temporal_payload.get("video_id")
        if video_id is not None and str(video_id).strip():
            video_ids.add(str(video_id).strip())

    return scene_ids, video_ids


def _clap_status_counts(scene_records: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for scene in scene_records:
        audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
        clap_meta = audio.get("clap_meta") if isinstance(audio.get("clap_meta"), dict) else scene.get("clap_meta")
        if not isinstance(clap_meta, dict):
            counts["missing"] += 1
            continue
        status = str(clap_meta.get("status") or "missing").strip().lower()
        if status in {"ok", "success"}:
            counts["ok"] += 1
        elif status in {"skipped", "skip"}:
            counts["skipped"] += 1
        elif status in {"error", "failed", "fail"}:
            counts["error"] += 1
        else:
            counts[status or "missing"] += 1
    return dict(counts)


def _resolve_runtime_audio_run_id(
    header: Dict[str, Any],
    latest_episode: Dict[str, Any],
    scene_results_payload: Any,
) -> tuple[str | None, str | None]:
    candidates: List[tuple[str, Any]] = []
    for source_name, source in (
        ("run_header", header),
        ("latest_episode", latest_episode),
        ("scene_results", _first_result_record(scene_results_payload)),
    ):
        if not isinstance(source, dict):
            continue
        for key in ("runtime_run_id", "goodq_run_id", "qdrant_run_id", "vector_run_id"):
            candidates.append((f"{source_name}.{key}", source.get(key)))

    for source, value in candidates:
        if value is not None and str(value).strip():
            return str(value).strip(), source

    scene_clap_run_ids: List[str] = []
    seen_scene_clap_run_ids: set[str] = set()
    for scene in _scene_records_from_results(scene_results_payload):
        audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
        for source_name, clap_meta in (
            ("scene_results.scenes.audio.clap_meta.run_id", audio.get("clap_meta")),
            ("scene_results.scenes.clap_meta.run_id", scene.get("clap_meta")),
        ):
            if not isinstance(clap_meta, dict):
                continue
            value = clap_meta.get("run_id")
            if value is None or not str(value).strip():
                continue
            run_id = str(value).strip()
            if run_id not in seen_scene_clap_run_ids:
                seen_scene_clap_run_ids.add(run_id)
                scene_clap_run_ids.append(run_id)
                clap_source = source_name
    if len(scene_clap_run_ids) == 1:
        return scene_clap_run_ids[0], clap_source

    generic_candidates: List[tuple[str, Any]] = []
    for source_name, source in (
        ("run_header", header),
        ("latest_episode", latest_episode),
        ("scene_results", _first_result_record(scene_results_payload)),
    ):
        if isinstance(source, dict):
            generic_candidates.append((f"{source_name}.run_id", source.get("run_id")))

    for source, value in generic_candidates:
        if value is not None and str(value).strip():
            return str(value).strip(), source
    return None, None


def _first_result_record(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
        return {}
    return payload if isinstance(payload, dict) else {}


def _audio_qdrant_collection_candidates(epoch: Any, *, header: Dict[str, Any] | None = None) -> List[str]:
    candidates: List[str] = []
    if isinstance(header, dict):
        header_collections = header.get("qdrant_collections")
        header_audio_collection = None
        if isinstance(header_collections, dict):
            header_audio_collection = header_collections.get("audio")
        for value in (
            header_audio_collection,
            header.get("audio_collection"),
            header.get("qdrant_audio_collection"),
        ):
            text = str(value).strip() if value is not None else ""
            if text:
                candidates.append(text)

    epoch_s = str(epoch).strip() if epoch is not None else ""
    if epoch_s:
        candidates.append(f"goodq_audio_{epoch_s}")

    qcfg = (_CFG.get("qdrant") or {}) if isinstance(_CFG, dict) else {}
    collections = qcfg.get("collections") if isinstance(qcfg.get("collections"), dict) else {}
    audio_collection = collections.get("audio") if isinstance(collections, dict) else None
    if isinstance(audio_collection, dict):
        audio_collection = audio_collection.get("name")
    if audio_collection is not None and str(audio_collection).strip():
        candidates.append(str(audio_collection).strip())

    candidates.append("goodq_audio")
    seen: set[str] = set()
    out: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def _qdrant_base_url() -> str:
    qcfg = (_CFG.get("qdrant") or {}) if isinstance(_CFG, dict) else {}
    host = str(qcfg.get("host") or "http://127.0.0.1:6333").strip()
    port = qcfg.get("port")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    if port is not None:
        parsed = urlparse(host)
        if parsed.hostname and parsed.port is None:
            host = f"{parsed.scheme}://{parsed.hostname}:{port}"
    return host.rstrip("/")


def _scroll_qdrant_audio_payloads(runtime_run_id: str, collection_candidates: List[str]) -> Dict[str, Any]:
    base_url = _qdrant_base_url()
    last_error: str | None = None
    for collection in collection_candidates:
        payloads: List[Dict[str, Any]] = []
        offset = None
        try:
            for _ in range(100):
                body: Dict[str, Any] = {
                    "limit": 256,
                    "with_payload": True,
                    "with_vector": False,
                    "filter": {
                        "must": [
                            {"key": "run_id", "match": {"value": runtime_run_id}},
                            {"key": "modality", "match": {"value": "audio"}},
                        ]
                    },
                }
                if offset is not None:
                    body["offset"] = offset
                resp = requests.post(
                    f"{base_url}/collections/{collection}/points/scroll",
                    json=body,
                    timeout=5,
                )
                if resp.status_code == 404:
                    last_error = "collection_not_found"
                    break
                if resp.status_code != 200:
                    last_error = f"qdrant_status_{resp.status_code}"
                    break
                data = resp.json().get("result", {}) or {}
                points = data.get("points") if isinstance(data.get("points"), list) else []
                for point in points:
                    point_payload = point.get("payload") if isinstance(point, dict) else None
                    if isinstance(point_payload, dict):
                        payloads.append(point_payload)
                offset = data.get("next_page_offset")
                if offset is None:
                    return {"status": "ok", "collection": collection, "payloads": payloads}
            if payloads:
                return {"status": "ok", "collection": collection, "payloads": payloads}
        except Exception as exc:
            last_error = f"exception:{type(exc).__name__}"
            logger.warning("audio vector proof qdrant read failed collection=%s error=%s", collection, exc)

    return {"status": last_error or "qdrant_unavailable", "payloads": []}


def _qdrant_audio_collection_names() -> Dict[str, Any]:
    base_url = _qdrant_base_url()
    try:
        resp = requests.get(f"{base_url}/collections", timeout=5)
        if resp.status_code != 200:
            return {"status": f"qdrant_status_{resp.status_code}", "collections": []}
        collections = resp.json().get("result", {}).get("collections", []) or []
        names = [
            str(item.get("name")).strip()
            for item in collections
            if isinstance(item, dict) and item.get("name") and "audio" in str(item.get("name")).lower()
        ]
        return {"status": "ok", "collections": sorted(set(names))}
    except Exception as exc:
        logger.warning("audio provenance qdrant collection list failed error=%s", exc)
        return {"status": f"exception:{type(exc).__name__}", "collections": []}


def _scroll_qdrant_audio_collection_payloads(collection: str, *, max_pages: int = 100) -> Dict[str, Any]:
    base_url = _qdrant_base_url()
    payloads: List[Dict[str, Any]] = []
    offset = None
    try:
        for _ in range(max_pages):
            body: Dict[str, Any] = {
                "limit": 256,
                "with_payload": True,
                "with_vector": False,
                "filter": {"must": [{"key": "modality", "match": {"value": "audio"}}]},
            }
            if offset is not None:
                body["offset"] = offset
            resp = requests.post(
                f"{base_url}/collections/{collection}/points/scroll",
                json=body,
                timeout=5,
            )
            if resp.status_code == 404:
                return {"status": "collection_not_found", "collection": collection, "payloads": payloads}
            if resp.status_code != 200:
                return {"status": f"qdrant_status_{resp.status_code}", "collection": collection, "payloads": payloads}
            data = resp.json().get("result", {}) or {}
            points = data.get("points") if isinstance(data.get("points"), list) else []
            for point in points:
                point_payload = point.get("payload") if isinstance(point, dict) else None
                if isinstance(point_payload, dict):
                    payloads.append(point_payload)
            offset = data.get("next_page_offset")
            if offset is None:
                return {"status": "ok", "collection": collection, "payloads": payloads}
    except Exception as exc:
        logger.warning("audio provenance qdrant collection scan failed collection=%s error=%s", collection, exc)
        return {"status": f"exception:{type(exc).__name__}", "collection": collection, "payloads": payloads}
    return {"status": "page_cap_reached", "collection": collection, "payloads": payloads}


def _latest_audio_provenance_snapshot(limit: int = 8) -> Dict[str, Any]:
    """Read-only inventory of run-tagged Qdrant audio payloads.

    This intentionally stays separate from latest structured-run proof. It can
    show that provenance-capable audio payloads exist without claiming they
    prove the currently selected /api/runs/latest/evidence run.
    """

    collection_result = _qdrant_audio_collection_names()
    collections = collection_result.get("collections") if isinstance(collection_result.get("collections"), list) else []
    base: Dict[str, Any] = {
        "status": "not_exposed",
        "label": "Not Exposed",
        "mode": "read_only",
        "source": "qdrant audio payload inventory; not latest structured run proof",
        "contract": "docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md",
        "required_payload_fields": list(_AUDIO_QDRANT_REQUIRED_FIELDS),
        "scanned_collections": len(collections),
        "collections": collections,
        "run_tagged_audio_runs": 0,
        "run_tagged_audio_points": 0,
        "provenance_capable_points": 0,
        "legacy_audio_points_sampled": 0,
        "runs": [],
        "latest_run": None,
        "safety_boundary": {
            "mode": "read_only",
            "mutation": False,
            "latest_run_claim": False,
        },
    }
    if collection_result.get("status") != "ok":
        return {
            **base,
            "reason": collection_result.get("status") or "qdrant_unavailable",
            "impact": "Qdrant collection inventory could not be read without mutating state.",
        }
    if not collections:
        return {
            **base,
            "status": "no_audio_collections",
            "label": "Not Exposed",
            "reason": "no_audio_collections_returned",
            "impact": "No Qdrant audio collections are visible to the read-only inventory.",
        }

    runs: Dict[str, Dict[str, Any]] = {}
    scan_errors: Dict[str, str] = {}

    for collection in collections:
        scan = _scroll_qdrant_audio_collection_payloads(collection)
        if scan.get("status") not in {"ok", "page_cap_reached"}:
            scan_errors[collection] = str(scan.get("status") or "unavailable")
        payloads = scan.get("payloads") if isinstance(scan.get("payloads"), list) else []
        for payload in payloads:
            if str(payload.get("modality") or "").strip().lower() != "audio":
                continue
            run_id = str(payload.get("run_id") or "").strip()
            if not run_id:
                base["legacy_audio_points_sampled"] += 1
                continue
            row = runs.setdefault(
                run_id,
                {
                    "run_id": run_id,
                    "collections": set(),
                    "run_tagged_points": 0,
                    "provenance_capable_points": 0,
                    "scene_ids": set(),
                    "video_ids": set(),
                    "latest_commit_ts_utc": None,
                    "latest_provenance_ts_utc": None,
                    "missing_required_fields": Counter(),
                    "component_mismatch_count": 0,
                    "step_mismatch_count": 0,
                    "sample_payload_keys": set(),
                },
            )
            row["collections"].add(collection)
            row["run_tagged_points"] += 1
            for key in payload.keys():
                if _is_safe_payload_shape_key(key):
                    row["sample_payload_keys"].add(str(key))
            scene_id = payload.get("scene_id")
            if scene_id is not None and str(scene_id).strip():
                row["scene_ids"].add(str(scene_id).strip())
            video_id = payload.get("video_id") or payload.get("video_hash")
            if video_id is not None and str(video_id).strip():
                row["video_ids"].add(str(video_id).strip())

            commit_ts = str(payload.get("commit_ts_utc") or payload.get("created_at") or "").strip()
            if commit_ts and (not row["latest_commit_ts_utc"] or commit_ts > row["latest_commit_ts_utc"]):
                row["latest_commit_ts_utc"] = commit_ts

            missing = [field for field in _AUDIO_QDRANT_REQUIRED_FIELDS if not payload.get(field)]
            for field in missing:
                row["missing_required_fields"][field] += 1
            component_ok = payload.get("component") == "audio_embed_clap"
            step_ok = payload.get("step") == "audio_embed_clap"
            if not component_ok:
                row["component_mismatch_count"] += 1
            if not step_ok:
                row["step_mismatch_count"] += 1
            if not missing and component_ok and step_ok:
                row["provenance_capable_points"] += 1
                if commit_ts and (not row["latest_provenance_ts_utc"] or commit_ts > row["latest_provenance_ts_utc"]):
                    row["latest_provenance_ts_utc"] = commit_ts

    normalized_runs: List[Dict[str, Any]] = []
    for row in runs.values():
        collection_list = sorted(row["collections"])
        normalized_runs.append(
            {
                "run_id": row["run_id"],
                "collection": collection_list[0] if len(collection_list) == 1 else "multiple",
                "collections": collection_list,
                "run_tagged_points": row["run_tagged_points"],
                "provenance_capable_points": row["provenance_capable_points"],
                "scene_count": len(row["scene_ids"]),
                "video_count": len(row["video_ids"]),
                "latest_commit_ts_utc": row["latest_commit_ts_utc"],
                "latest_provenance_ts_utc": row["latest_provenance_ts_utc"],
                "missing_required_fields": dict(sorted(row["missing_required_fields"].items())),
                "component_mismatch_count": row["component_mismatch_count"],
                "step_mismatch_count": row["step_mismatch_count"],
                "sample_payload_keys": sorted(row["sample_payload_keys"]),
            }
        )

    normalized_runs.sort(
        key=lambda row: (
            row.get("latest_provenance_ts_utc") or "",
            row.get("latest_commit_ts_utc") or "",
            row.get("provenance_capable_points") or 0,
        ),
        reverse=True,
    )
    latest_run = next((row for row in normalized_runs if row.get("provenance_capable_points")), None)
    limited_runs = normalized_runs[: max(1, int(limit or 1))]

    base.update(
        {
            "run_tagged_audio_runs": len(normalized_runs),
            "run_tagged_audio_points": sum(int(row.get("run_tagged_points") or 0) for row in normalized_runs),
            "provenance_capable_points": sum(int(row.get("provenance_capable_points") or 0) for row in normalized_runs),
            "runs": limited_runs,
            "latest_run": latest_run,
            "scan_errors": scan_errors,
        }
    )
    if latest_run:
        return {
            **base,
            "status": "ok",
            "label": "Run-Tagged Audio Proof Exists",
            "reason": "run_tagged_qdrant_audio_payloads_satisfy_contract",
            "impact": "Separate Qdrant inventory found run-tagged audio payloads with required provenance fields. This does not override latest structured-run proof.",
        }
    if normalized_runs:
        return {
            **base,
            "status": "historical_only",
            "label": "Historical Only",
            "reason": "run_tagged_audio_payloads_missing_required_provenance",
            "impact": "Run-tagged audio payloads exist, but required provenance fields are incomplete.",
        }
    return {
        **base,
        "status": "no_run_tagged_audio",
        "label": "No Run-Tagged Audio",
        "reason": "no_audio_payloads_with_run_id",
        "impact": "Audio collections are visible, but the inventory did not find run-tagged audio payloads.",
    }


def _sample_qdrant_audio_payloads(collection_candidates: List[str]) -> Dict[str, Any]:
    """Sample audio payload shape without exposing raw Qdrant payload values."""

    base_url = _qdrant_base_url()
    last_error: str | None = None
    for collection in collection_candidates:
        try:
            body: Dict[str, Any] = {
                "limit": 32,
                "with_payload": True,
                "with_vector": False,
                "filter": {"must": [{"key": "modality", "match": {"value": "audio"}}]},
            }
            resp = requests.post(
                f"{base_url}/collections/{collection}/points/scroll",
                json=body,
                timeout=5,
            )
            if resp.status_code == 404:
                last_error = "collection_not_found"
                continue
            if resp.status_code != 200:
                last_error = f"qdrant_status_{resp.status_code}"
                continue

            data = resp.json().get("result", {}) or {}
            points = data.get("points") if isinstance(data.get("points"), list) else []
            payloads = [
                point.get("payload")
                for point in points
                if isinstance(point, dict) and isinstance(point.get("payload"), dict)
            ]
            return {
                "status": "ok",
                "collection": collection,
                "sample_count": len(payloads),
                "payloads_have_run_id": any(payload.get("run_id") for payload in payloads),
                "missing_required_fields": _missing_required_field_counts(payloads),
            }
        except Exception as exc:
            last_error = f"exception:{type(exc).__name__}"
            logger.warning("audio vector proof qdrant sample failed collection=%s error=%s", collection, exc)

    return {
        "status": last_error or "qdrant_unavailable",
        "sample_count": 0,
        "payloads_have_run_id": False,
        "missing_required_fields": {},
    }


def _missing_required_field_counts(payloads: List[Dict[str, Any]]) -> Dict[str, int]:
    missing_required: Counter[str] = Counter()
    for payload in payloads:
        for field in _AUDIO_QDRANT_REQUIRED_FIELDS:
            if not payload.get(field):
                missing_required[field] += 1
    return dict(sorted(missing_required.items()))


def _is_safe_payload_shape_key(key: Any) -> bool:
    text = str(key or "").strip().lower()
    if not text:
        return False
    return not any(token in text for token in ("path", "dir", "file", "root", "stdout", "stderr", "trace", "raw"))


def _evaluate_qdrant_audio_payloads(
    payloads: List[Dict[str, Any]],
    *,
    scene_ids: set[str],
    video_ids: set[str],
) -> Dict[str, Any]:
    missing_required: Counter[str] = Counter()
    proven_scene_ids: set[str] = set()
    unverified = 0
    scene_mismatch = 0
    video_mismatch = 0

    for payload in payloads:
        missing = [field for field in _AUDIO_QDRANT_REQUIRED_FIELDS if not payload.get(field)]
        for field in missing:
            missing_required[field] += 1

        scene_id = payload.get("scene_id")
        video_id = payload.get("video_id")
        component_ok = payload.get("component") == "audio_embed_clap"
        step_ok = payload.get("step") == "audio_embed_clap"
        scene_ok = bool(scene_id) and (not scene_ids or str(scene_id) in scene_ids)
        video_ok = not video_ids or (bool(video_id) and str(video_id) in video_ids)
        if not scene_ok:
            scene_mismatch += 1
        if not video_ok:
            video_mismatch += 1

        if not missing and component_ok and step_ok and scene_ok and video_ok:
            proven_scene_ids.add(str(scene_id))
        else:
            unverified += 1

    return {
        "current_run_qdrant_proven": len(proven_scene_ids),
        "provenance_unverified": unverified,
        "missing_required_fields": dict(sorted(missing_required.items())),
        "scene_mismatch_count": scene_mismatch,
        "video_mismatch_count": video_mismatch,
    }


def _safe_top_values(value: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = enumerate(value)
    else:
        return rows

    for key, item in items:
        if isinstance(item, dict):
            label = (
                item.get("label")
                or item.get("name")
                or item.get("emotion")
                or item.get("tag")
                or item.get("time_hint")
                or item.get("hint")
                or item.get("entity")
                or item.get("key")
                or item.get("value")
                or key
            )
            count = item.get("count")
            if count is None:
                count = item.get("total")
            if count is None and isinstance(item.get("value"), (int, float)):
                count = item.get("value")
        elif isinstance(item, (list, tuple)) and item:
            label = item[0]
            count = item[1] if len(item) > 1 else None
        else:
            label = key if isinstance(value, dict) else item
            count = item if isinstance(value, dict) else None
        if label is None:
            continue
        row = {"label": str(label)}
        if count is not None and not isinstance(count, (dict, list, tuple)):
            row["count"] = _round_number(count)
        rows.append(row)
        if len(rows) >= 8:
            break
    return rows


def _simple_mapping(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, Any] = {}
    for key, item in value.items():
        if len(result) >= 12:
            break
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[str(key)] = item
        elif isinstance(item, dict):
            result[str(key)] = {
                str(child_key): child_value
                for child_key, child_value in item.items()
                if isinstance(child_value, (str, int, float, bool)) or child_value is None
            }
    return result


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _round_number(value: Any) -> float | int | None:
    number = _safe_float(value)
    if number is None:
        return None
    rounded = round(number, 3)
    return int(rounded) if rounded.is_integer() else rounded


def _duration_summary(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": _round_number(ordered[0]),
        "p50": _round_number(_percentile(ordered, 50)),
        "p95": _round_number(_percentile(ordered, 95)),
        "max": _round_number(ordered[-1]),
    }


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * (percentile / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    fraction = index - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def _latest_timestamp(rows: List[Dict[str, Any]]) -> Any:
    for row in reversed(rows):
        value = row.get("ts_utc") or row.get("ts") or row.get("timestamp")
        if value:
            return value
    return None


def _tail_log(path: Path, lines: int = 50) -> List[str]:
    if not path.exists():
        return []
    dq: deque[str] = deque(maxlen=lines)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                dq.append(line.rstrip("\n"))
    except Exception as e:
        logger.debug(f"Failed to tail log {path}: {e}")
        return []
    return list(dq)


@router.get("/api/runs/latest/preview")
def latest_run_preview(limit: int = 12) -> Dict[str, Any]:
    return _latest_run_preview(limit=limit)


@router.get("/api/runs/latest/evidence")
def latest_run_evidence(limit: int = Query(default=24, ge=1, le=100)) -> Dict[str, Any]:
    return _latest_run_evidence(limit=limit)


@router.get("/api/runs/audio-proof/latest")
def latest_audio_provenance_snapshot(limit: int = Query(default=8, ge=1, le=24)) -> Dict[str, Any]:
    return _latest_audio_provenance_snapshot(limit=limit)


def _sqlite_table_count(path: str, table: str) -> int:
    if not path or not os.path.isfile(path):
        return 0
    try:
        con = sqlite3.connect(path)
        try:
            row = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        finally:
            con.close()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def _sqlite_embedding_count(db_path: str, modalities: tuple[str, ...]) -> int:
    if not db_path or not os.path.isfile(db_path):
        return 0
    try:
        con = sqlite3.connect(db_path)
        try:
            placeholders = ",".join("?" for _ in modalities)
            row = con.execute(
                f"SELECT COUNT(*) FROM embeddings WHERE modality IN ({placeholders})",
                modalities,
            ).fetchone()
        finally:
            con.close()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def _positive_count(*values: int) -> int:
    for value in values:
        if value > 0:
            return value
    return 0


def _faiss_count(path: str, *, fallback_count: int = 0) -> int:
    if not os.path.isfile(path):
        return 0
    try:
        import faiss  # type: ignore
    except Exception:
        return fallback_count
    try:
        idx = faiss.read_index(path)
        return int(getattr(idx, "ntotal", 0))
    except Exception:
        return fallback_count


@router.get("/api/memory/stats")
def get_memory_stats() -> Dict[str, Any]:
    """Lightweight memory stats across tiers (faiss/qdrant)."""
    paths = (_CFG.get("paths") or {}) if isinstance(_CFG, dict) else {}
    memory_cfg = (_CFG.get("memory") or {}) if isinstance(_CFG, dict) else {}
    db_path = paths.get("db_path") or ""

    faiss_info = {
        "text_vectors": _faiss_count(
            paths.get("faiss_index_path") or "",
            fallback_count=_sqlite_embedding_count(db_path, ("text", "audio_transcript", "frame_text")),
        ),
        "clip_vectors": _faiss_count(
            paths.get("faiss_clip_path") or "",
            fallback_count=_positive_count(
                _sqlite_table_count(paths.get("clip_id_map_db") or "", "clip_id_map"),
                _sqlite_embedding_count(db_path, ("clip",)),
            ),
        ),
        "dino_vectors": _faiss_count(
            paths.get("faiss_dino_path") or "",
            fallback_count=_positive_count(
                _sqlite_table_count(paths.get("dino_id_map_db") or "", "dino_id_map"),
                _sqlite_embedding_count(db_path, ("dino",)),
            ),
        ),
        "audio_vectors": _faiss_count(
            paths.get("faiss_audio_path") or "",
            fallback_count=_positive_count(
                _sqlite_table_count(paths.get("clap_id_map_db") or "", "clap_id_map"),
                _sqlite_embedding_count(db_path, ("audio",)),
            ),
        ),
    }
    audio_vector_semantics = {
        "faiss.audio_vectors": "faiss_index_count_only_not_current_run_qdrant_proof",
        "current_run_success_contract": "docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md",
        "current_run_success_requires": [
            "clap_meta.status == ok",
            "qdrant_audio_payload.run_id matches audited runtime run_id",
            "required qdrant audio provenance fields are present",
        ],
    }

    qdrant_info = {"available": False, "collections": 0}
    try:
        r = requests.get("http://localhost:6333/collections", timeout=2)
        if r.status_code == 200:
            colls = r.json().get("result", {}).get("collections", []) or []
            qdrant_info["available"] = True
            qdrant_info["collections"] = len(colls)
    except Exception:
        pass

    return {
        "faiss": faiss_info,
        "qdrant": qdrant_info,
        "audio_vector_semantics": audio_vector_semantics,
        "routing": {
            "read_priority": normalize_memory_tier_list((memory_cfg.get("routing") or {}).get("read_priority") or []),
            "write_targets": normalize_memory_tier_list((memory_cfg.get("routing") or {}).get("write_targets") or []),
        },
        "latest_run": _latest_run_preview(limit=12),
    }


@router.get("/api/read/envelope")
def read_epistemic_envelope() -> Dict[str, Any]:
    """Serve a precomputed EpistemicReadEnvelope bundle without accepting arbitrary queries/commands."""
    bundle_path = os.environ.get("GOODQ_READONLY_ENVELOPE_PATH", "").strip()
    if not bundle_path:
        raise HTTPException(status_code=404, detail="Envelope bundle not configured (set GOODQ_READONLY_ENVELOPE_PATH).")

    p = Path(bundle_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Envelope bundle not found.")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Envelope bundle is not valid JSON.")

    if not isinstance(data, dict) or "envelope" not in data:
        raise HTTPException(status_code=400, detail="Envelope bundle must be an object with key 'envelope'.")

    decisions = data.get("nonActionDecisions", data.get("non_action_decisions", []))
    if decisions is None:
        decisions = []
    if not isinstance(decisions, list):
        raise HTTPException(status_code=400, detail="Envelope bundle decisions must be a list.")

    return {"envelope": data["envelope"], "nonActionDecisions": decisions}
