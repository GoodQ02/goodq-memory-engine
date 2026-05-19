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
from collections import Counter, deque
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

_AUDIO_QDRANT_REQUIRED_FIELDS = (
    "run_id",
    "embedding_id",
    "component",
    "step",
    "model",
    "created_at",
    "commit_ts_utc",
)

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


def _latest_run_evidence(limit: int = 24) -> Dict[str, Any]:
    """Return sanitized read-only evidence projections for the latest structured run."""
    runs = run_index.list_runs(limit=1)
    if not runs:
        return _empty_run_evidence("no_indexed_runs")

    latest = runs[0]
    try:
        summary = run_summary.load_run_summary(run_root=latest.get("run_root") or latest["run_id"])
    except Exception as exc:
        logger.warning("latest run evidence summary unavailable error=%s", exc)
        return _empty_run_evidence("summary_unavailable")

    if not isinstance(summary, dict):
        return _empty_run_evidence("summary_unavailable")

    header = summary.get("run_header") if isinstance(summary.get("run_header"), dict) else {}
    overview = summary.get("file_job_overview") if isinstance(summary.get("file_job_overview"), dict) else {}
    outcome = summary.get("outcome_classification") if isinstance(summary.get("outcome_classification"), dict) else {}
    latest_episode = summary.get("latest_episode") if isinstance(summary.get("latest_episode"), dict) else {}

    temporal_path = _episode_artifact_path(latest_episode, "temporal_index.json")
    scene_results_path = _episode_artifact_path(latest_episode, "scene_ingest_results.json")
    step_runs_path = _find_step_runs_path(latest_episode, [temporal_path, scene_results_path])

    temporal_payload = _load_json_any(temporal_path)
    scene_results_payload = _load_json_any(scene_results_path)

    return {
        "available": True,
        "run": {
            "run_id": header.get("run_id") or latest.get("run_id"),
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
        "sentiment": _summarize_sentiment(temporal_payload),
        "knowledge_graph": _summarize_knowledge_graph(scene_results_payload, latest_episode),
        "audio_vector_proof": _summarize_audio_vector_proof(
            header=header,
            latest_episode=latest_episode,
            temporal_payload=temporal_payload,
            scene_results_payload=scene_results_payload,
        ),
        "safety_boundary": _run_evidence_safety_boundary(),
    }


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


def _summarize_sentiment(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "unavailable", "reason": "temporal_index_missing"}

    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
    audio_emotions: Counter[str] = Counter()
    sentiment_labels: Counter[str] = Counter()
    sentiment_scores: List[float] = []

    for segment in segments:
        if not isinstance(segment, dict):
            continue
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
        "status": "ok" if audio_emotions or sentiment_labels or top_audio else "not_observed",
        "segments_total": len(segments),
        "segments_with_audio_emotion": payload.get("segments_with_audio_emotion") or sum(audio_emotions.values()),
        "segments_with_sentiment": sum(sentiment_labels.values()),
        "top_audio_emotions": top_audio,
        "sentiment_labels": [
            {"label": label, "count": count}
            for label, count in sentiment_labels.most_common(8)
        ],
        "average_sentiment_score": _round_number(sum(sentiment_scores) / len(sentiment_scores)) if sentiment_scores else None,
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
    collection_candidates = _audio_qdrant_collection_candidates(header.get("epoch"))
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
    clap_ok = int(base["clap_ok"] or 0)
    proven = int(base["current_run_qdrant_proven"] or 0)

    if proven and (clap_ok == 0 or proven >= clap_ok):
        status = "current_run_audio_vector_proven"
        label = "Proven"
        impact = "Run-matched CLAP/Qdrant audio payloads satisfy the current-run provenance contract."
    elif proven:
        status = "partial"
        label = "Partial"
        impact = "Some run-matched audio vectors are proven, but coverage is not complete for CLAP-ok scenes."
    elif payloads:
        status = "provenance_unverified_audio_vector_exists"
        label = "Historical Only"
        impact = "Run-matched audio points exist, but required provenance or scene/video matching is incomplete."
    else:
        status = "no_current_run_evidence"
        label = "No Current-Run Evidence"
        impact = "No Qdrant audio payloads match the audited runtime run id."

    return {
        **base,
        "status": status,
        "label": label,
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
    return None, None


def _first_result_record(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
        return {}
    return payload if isinstance(payload, dict) else {}


def _audio_qdrant_collection_candidates(epoch: Any) -> List[str]:
    candidates: List[str] = []
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
