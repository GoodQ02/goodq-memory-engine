"""read-only aggregation surface for current runtime state.

This router exists to answer "what is happening right now?" across a long-running,
stateful local system. It must never grow into a control, mutation, or execution
surface.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
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

    database_data = {"exists": False, "scenes": 0}
    try:
        database_data["exists"] = _DB_PATH.exists()
        if database_data["exists"]:
            database_data["scenes"] = 1
    except Exception:
        pass

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
    runs = run_index.list_runs(limit=1)
    if not runs:
        return {"available": False}

    latest = runs[0]
    summary = run_summary.load_run_summary(run_root=latest.get("run_root") or latest["run_id"])
    header = summary.get("run_header") if isinstance(summary, dict) else {}
    overview = summary.get("file_job_overview") if isinstance(summary, dict) else {}
    outcome = summary.get("outcome_classification") if isinstance(summary, dict) else {}

    return {
        "available": True,
        "run_id": header.get("run_id"),
        "status": outcome.get("status") or header.get("status"),
        "epoch": header.get("epoch"),
        "source_dir": header.get("source_dir"),
        "start_time": header.get("start_time"),
        "end_time": header.get("end_time"),
        "total_duration_seconds": header.get("total_duration_seconds"),
        "episodes_total": overview.get("episodes_total"),
        "episodes_completed": overview.get("episodes_completed"),
        "episodes_failed": overview.get("episodes_failed"),
        "episodes_running": overview.get("episodes_running"),
        "episodes_pending": overview.get("episodes_pending"),
        "scenes_processed": overview.get("scenes_processed"),
        "latest_episode": summary.get("latest_episode"),
    }


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


def _faiss_count(path: str) -> int:
    try:
        import faiss  # type: ignore
    except Exception:
        return 0
    if not os.path.isfile(path):
        return 0
    try:
        idx = faiss.read_index(path)
        return int(getattr(idx, "ntotal", 0))
    except Exception:
        return 0


@router.get("/api/memory/stats")
def get_memory_stats() -> Dict[str, Any]:
    """Lightweight memory stats across tiers (faiss/qdrant)."""
    paths = (_CFG.get("paths") or {}) if isinstance(_CFG, dict) else {}
    memory_cfg = (_CFG.get("memory") or {}) if isinstance(_CFG, dict) else {}

    faiss_info = {
        "text_vectors": _faiss_count(paths.get("faiss_index_path") or ""),
        "clip_vectors": _faiss_count(paths.get("faiss_clip_path") or ""),
        "audio_vectors": _faiss_count(paths.get("faiss_audio_path") or ""),
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
