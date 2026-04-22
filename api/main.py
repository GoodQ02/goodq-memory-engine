from __future__ import annotations
from typing import Any, Dict
import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import threading
import requests
from collections import deque
from urllib.parse import urlparse
import glob
import glob

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Any, Dict
from pydantic import BaseModel
from lib.llm_client import LLMClient
from steps.common.llm_model_factory import build_llm_models
from goodq_version import GOODQ_VERSION

from steps.common.config_loader import load_configs
from steps.common.memory_manager import build_memory_router
from api.utils.ingest_requests import is_supported_ingest_path

# Import Phase 7 API routes
from api.routes import search, scenes, timeline, media, system, run_summary, run_index, ingest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GoodQ Retrieval API", version=GOODQ_VERSION)
_CFG = load_configs({})
_MEMORY_ROUTER = build_memory_router(_CFG)
_PATHS_CFG: Dict[str, Any] = _CFG.get("paths", {}) or {}
_HOST_CFG: Dict[str, Any] = _CFG.get("host", {}) or {}
_API_CFG: Dict[str, Any] = _CFG.get("api", {}) or {}


def _resolve_allowed_origins() -> List[str]:
    override = str(os.environ.get("GOODQ_API_ALLOWED_ORIGINS") or "").strip()
    if override:
        origins = [item.strip() for item in override.split(",") if item.strip()]
        if origins:
            return origins
    return [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:30000",
        "http://127.0.0.1:30000",
    ]

# Add UTF-8 charset to JSON responses
class UTF8JSONMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["content-type"] = "application/json; charset=utf-8"
        return response

app.add_middleware(UTF8JSONMiddleware)

if bool(_API_CFG.get("cors_enabled", False)):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount Phase 7 API routers
app.include_router(search.router)
app.include_router(scenes.router)
app.include_router(timeline.router)
app.include_router(media.router)
app.include_router(system.router)
app.include_router(ingest.router)
app.include_router(run_summary.router)
app.include_router(run_index.router)

# UI will be mounted at the end after all API routes are defined

_API_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _API_ROOT.parent
_HOST_DATA_ROOT = _HOST_CFG.get("data_root") or os.environ.get("GOODQ_DATA_ROOT")
if _HOST_DATA_ROOT:
    _DEFAULT_DATA_ROOT = Path(str(_HOST_DATA_ROOT)) / "GoodQ_Data"
else:
    _DEFAULT_DATA_ROOT = Path(str(_PATHS_CFG.get("data_root") or (_PROJECT_ROOT / "data")))
_DATA_ROOT = Path(_PATHS_CFG.get("data_root") or _DEFAULT_DATA_ROOT)
_LOG_DIR = Path(_PATHS_CFG.get("log_dir") or (_PROJECT_ROOT / "logs"))
_DB_PATH = Path(_PATHS_CFG.get("db_path") or (_DATA_ROOT / "memory.db"))
_KG_DB_PATH = Path(_PATHS_CFG.get("knowledge_graph_db") or (_DATA_ROOT / "knowledge_graph.db"))
_PROCESSING_PATH = Path(_PATHS_CFG.get("processing") or (_DATA_ROOT / "processing"))
_IMPORT_INBOX = Path(_PATHS_CFG.get("import_inbox") or (_DATA_ROOT / "import_inbox"))
_WSL_DISTRO = str(os.environ.get("GOODQ_WSL_DISTRO") or _HOST_CFG.get("wsl_distro") or "Ubuntu")
_WSL_USER = str(os.environ.get("GOODQ_WSL_USER") or "").strip()
if not _WSL_USER or _WSL_USER.lower() == "auto":
    _WSL_USER = str(os.environ.get("USER") or os.environ.get("USERNAME") or os.environ.get("LOGNAME") or "user")
_WSL_WORKSPACE = str(os.environ.get("GOODQ_WSL_WORKSPACE") or _HOST_CFG.get("wsl_workspace") or f"/home/{_WSL_USER}/goodq_audio")

# Enforce CONFIG_LOADING_CONTRACT: reuse the already-loaded cfg in submodules.
# (api/routes/search.py lazily calls load_configs() otherwise; keep it lazy but non-reloading.)
try:
    search._config = _CFG  # type: ignore[attr-defined]
    search.load_configs = lambda overrides=None: _CFG  # type: ignore[assignment]
except Exception as e:
    logger.debug(f"Search route config injection failed: {e}")

try:
    from api.utils import loaders as api_loaders
    api_loaders.configure_from_cfg(_CFG)
except Exception as e:
    logger.debug(f"DataLoader config injection failed: {e}")

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

    # Check Ollama on configured port
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
    import subprocess
    import shutil

    engines: Dict[str, Any] = {}

    # Check vLLM on WSL
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

    # Check Ollama
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

    # Check WSL audio processing
    wsl_available = shutil.which("wsl") is not None
    engines["wsl_audio"] = {
        "name": "WSL Audio Transcription",
        "category": "Audio Processing",
        "description": "Faster-Whisper with speaker diarization",
        "status": "ready" if wsl_available else "unavailable",
        "gpu": True,
    }

    # Check Qdrant vector DB (optional)
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

    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    engines["ffmpeg"] = {
        "name": "FFmpeg",
        "category": "Video Processing",
        "description": f"Path: {ffmpeg_path}" if ffmpeg_path else "Not found",
        "status": "ready" if ffmpeg_path else "unavailable",
        "gpu": False,
    }

    # Check Python environment
    engines["python_pipeline"] = {
        "name": "Python Pipeline",
        "category": "Orchestration",
        "description": f"Python {sys.version.split()[0]}",
        "status": "ready",
        "gpu": False,
    }

    # Check scene detection
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

    # Check vector database
    qdrant_engine = engines.get("qdrant") or {}
    engines["vector_db"] = {
        "name": "Vector Database",
        "category": "Search & Retrieval",
        "description": f"Qdrant-backed retrieval ({qdrant_engine.get('description', 'service unavailable')})",
        "status": qdrant_engine.get("status", "unavailable"),
        "gpu": False,
    }

    # Check audio diarization
    engines["audio_diarization"] = {
        "name": "Audio Diarization",
        "category": "Audio Processing",
        "description": "Pyannote speaker separation with OSD",
        "status": "ready",
        "gpu": True,
    }

    return engines


def _collect_wsl_status() -> Dict[str, Any]:
    """Combine the two historical WSL status endpoints into one shared helper."""
    import subprocess
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
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        status["status"] = "running" if result.returncode == 0 else "stopped"
        status["status_output"] = result.stdout
    except Exception as e:
        logger.debug(f"WSL status check failed: {e}")
        status["status"] = "unknown"

    try:
        list_result = subprocess.run(
            ["wsl", "-l", "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
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

    # Fast, low-impact audio availability check (skip on timeout)
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

    # WSL GPU snapshot (best effort)
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


def _build_health_logs(health: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compose lightweight log lines for the command-center view."""
    entries = []
    now = datetime.now().isoformat()
    entries.append({"level": "info", "timestamp": now, "message": "Command center operational"})
    entries.append({"level": "success" if health.get("api") else "error", "message": f"API: {'Healthy' if health.get('api') else 'Degraded'}"})
    entries.append({"level": "success" if health.get("database") else "error", "message": f"Database: {'Healthy' if health.get('database') else 'Not Found'}"})
    entries.append({"level": "success" if health.get("wsl") else "warning", "message": f"WSL/GPU: {'Healthy' if health.get('wsl') else 'Unavailable'}"})
    entries.append({"level": "success" if health.get("pipeline") else "warning", "message": f"Pipeline: {'Active' if health.get('pipeline') else 'Standby'}"})
    return entries


@app.get("/search")
def search(q: str = Query(..., description="Search text index"), topk: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Search endpoint - currently disabled"""
    return {
        "status": "disabled",
        "message": "Search functionality is being refactored",
        "query": q,
        "results": []
    }


@app.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint (UI is not served from this API process)."""
    return {"status": "ok", "docs": "/docs", "openapi": "/openapi.json"}

@app.get("/api")
def api_root() -> Dict[str, Any]:
    return {"status": "ok", "endpoints": ["/search?q=...", "/api/status", "/api/engines", "/api/scenes", "/api/knowledge_graph"]}


@app.get("/api/status")
@app.head("/api/status")
def get_status() -> Dict[str, Any]:
    """System status endpoint - fast aggregated health check"""
    import requests
    
    # Quick GPU check
    gpu_data = {"gpu_utilization": 0, "gpu_memory_used": 0, "gpu_memory_total": 0}
    models_data = {"total": 2, "healthy": 0, "vllm_healthy": 0, "ollama_healthy": 0}
    processing_data = {"status": "idle", "current_video": None, "progress_percent": 0}
    
    # Quick model health checks with very short timeouts
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
    
    # Quick processing check
    try:
        resp = requests.get("http://localhost:5001/api/processing/stats", timeout=0.3)
        if resp.status_code == 200:
            stats = resp.json()
            processing_data = {
                "status": stats.get("status", "idle"),
                "current_video": stats.get("current_video", {}).get("name"),
                "progress_percent": stats.get("current_video", {}).get("progress_percent", 0)
            }
    except:
        pass
    
    # Quick database presence check
    database_data = {"exists": False, "scenes": 0}
    try:
        db_path = _DB_PATH
        database_data["exists"] = db_path.exists()
        if database_data["exists"]:
            database_data["scenes"] = 1  # Minimal indicator so UI shows healthy
    except Exception:
        pass

    # Quick WSL/audio availability
    wsl_status = _collect_wsl_status()

    # Quick GPU check
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=0.3
        )
        if result.returncode == 0:
            gpu_util, mem_used, mem_total = result.stdout.strip().split(",")
            gpu_data = {
                "gpu_utilization": int(gpu_util.strip()),
                "gpu_memory_used": int(mem_used.strip()),
                "gpu_memory_total": int(mem_total.strip())
            }
    except:
        pass
    
    return {
        "status": "active",
        "version": GOODQ_VERSION,
        "components": {
            "api": "running",
            "pipeline": processing_data["status"],
            "wsl_audio": "available" if wsl_status.get("available") else "unavailable"
        },
        "gpu": gpu_data,
        "models": models_data,
        "processing": processing_data,
        "database": database_data,
        "wsl": wsl_status,
    }


@app.get("/api/health/summary")
def get_health_summary() -> Dict[str, Any]:
    """Get health summary for all LLM models (vLLM + Ollama)"""
    # Check models directly
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
            "unhealthy": total - healthy
        },
        "vllm": {
            "status": "healthy" if vllm_healthy > 0 else "unhealthy",
            "healthy": vllm_healthy,
            "total": total_vllm,
            "models": ["Llama-1B-Speed"] if vllm_healthy > 0 else []
        },
        "ollama": {
            "status": "healthy" if ollama_healthy > 0 else "unhealthy",
            "healthy": ollama_healthy,
            "total": total_ollama,
            "models": ["Phi4-Ollama"] if ollama_healthy > 0 else []
        }
    }


@app.get("/api/engines")
def get_engines() -> Dict[str, Any]:
    """Get model engine health aggregate (summary + details)."""
    details = _collect_engine_details()
    summary = _summarize_llm_health()
    return {
        "engines": details,
        "details": details,
        "summary": summary,
        # Preserve legacy top-level fields expected by the dashboard
        "vllm": summary["vllm"],
        "ollama": summary["ollama"],
        "overall": summary["overall"],
        "timestamp": summary["timestamp"],
        # Flatten engines for legacy consumers that expect the engines at the top level
        **details,
    }


@app.get("/vector_search")
def vector_search(
    q: str = Query(..., description="Search text"),
    topk: int = Query(20, ge=1, le=200),
    modality: Optional[str] = Query(None, description="Filter by modality"),
    event: Optional[str] = Query(None, description="Filter by music/event label"),
    tag: Optional[str] = Query(None, description="Filter by tag/entity"),
) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "reason": "vector_search is deprecated; use /api/search/* for canonical Qdrant-backed retrieval",
        "matches": [],
    }


@app.get("/api/scenes")
def get_scenes() -> Dict[str, Any]:
    """Get detected scenes from video processing"""
    import json
    from pathlib import Path
    
    # Look for scenes in data/output
    scenes_dir = _DATA_ROOT / "output"
    all_scenes = []
    
    if scenes_dir.exists():
        for scene_file in scenes_dir.glob("**/scenes.json"):
            try:
                with open(scene_file, 'r') as f:
                    data = json.load(f)
                    scenes = data.get("scenes", [])
                    for scene in scenes:
                        scene["source_file"] = str(scene_file.parent.name)
                        all_scenes.append(scene)
            except Exception as e:
                logger.debug(f"Failed to read scene file {scene_file}: {e}")
                continue
    
    return {"scenes": all_scenes, "total": len(all_scenes)}


@app.get("/api/knowledge_graph")
def get_knowledge_graph() -> Dict[str, Any]:
    """Get knowledge graph data"""
    import json
    from pathlib import Path
    
    # Look for entity data
    # Primary KG database (SQLite)
    kg_db = _KG_DB_PATH
    # Legacy JSON export (fallback)
    kg_file = _DATA_ROOT / "output" / "knowledge_graph.json"
    
    if kg_file.exists():
        try:
            with open(kg_file, 'r') as f:
                data = json.load(f)
                # Normalize to the expected payload shape
                if "network" in data:
                    network = data.get("network") or {}
                    nodes = network.get("nodes") or []
                    edges = network.get("edges") or network.get("links") or []
                else:
                    nodes = data.get("nodes") or []
                    edges = data.get("edges") or data.get("links") or []
                return {
                    "network": {
                        "nodes": nodes,
                        "edges": edges,
                    },
                    "overview": {
                        "total_entities": len(nodes),
                        "total_relationships": len(edges),
                        "total_media": len(data.get("media", [])) if isinstance(data.get("media"), list) else 0,
                        "total_events": len(data.get("events", [])) if isinstance(data.get("events"), list) else 0,
                    },
                }
        except:
            pass
    
    # Return empty graph structure (keeps UI happy)
    return {
        "network": {
            "nodes": [],
            "edges": []
        },
        "overview": {
            "total_entities": 0,
            "total_relationships": 0,
            "total_media": 0,
            "total_events": 0
        }
    }


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None


@app.get("/api/queue")
def get_queue() -> Dict[str, Any]:
    """Get current processing queue"""
    import_inbox = _IMPORT_INBOX
    processing_dir = _PROCESSING_PATH
    processed_dir = _PROCESSING_PATH.parent / "processed"
    failed_dir = _PROCESSING_PATH.parent / "failed"

    queue_data = {
        "inbox": {"count": 0, "files": [], "total_size_mb": 0},
        "processing": {"count": 0, "files": []},
        "processed": {"count": 0},
        "failed": {"count": 0}
    }

    try:
        if import_inbox.exists():
            inbox_files = [
                f
                for f in import_inbox.iterdir()
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
            queue_data["inbox"]["total_size_mb"] = round(
                sum(f.stat().st_size for f in inbox_files) / (1024 ** 2), 2
            )

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


@app.get("/api/recent-activity")
def get_recent_activity(limit: int = Query(5, ge=1, le=100)) -> Dict[str, Any]:
    """Get recent processing activity"""
    return {
        "activities": [],
        "limit": limit
    }


@app.get("/api/entities")
def get_entities(limit: int = Query(500, ge=1, le=1000)) -> Dict[str, Any]:
    """Get detected entities"""
    return {
        "entities": [],
        "total": 0,
        "limit": limit
    }


@app.get("/api/entities/{entity_id}/relationships")
def get_entity_relationships(entity_id: str) -> Dict[str, Any]:
    """Get relationships for a specific entity"""
    return {
        "entity_id": entity_id,
        "relationships": []
    }


@app.get("/api/analytics/knowledge-graph")
def get_analytics_knowledge_graph() -> Dict[str, Any]:
    """Get knowledge graph analytics"""
    return get_knowledge_graph()


@app.get("/api/analytics/timeline")
def get_analytics_timeline() -> Dict[str, Any]:
    """Get timeline analytics"""
    return {
        "timeline": [],
        "start_date": None,
        "end_date": None
    }


@app.get("/api/analytics/emotions")
def get_analytics_emotions() -> Dict[str, Any]:
    """Get emotion analytics"""
    return {
        "emotions": [],
        "distribution": {}
    }


@app.get("/api/analytics/embeddings")
def get_analytics_embeddings() -> Dict[str, Any]:
    """Get embedding analytics"""
    return {
        "embeddings": [],
        "dimensions": 0
    }


@app.get("/api/analytics/{tab_name}")
def get_analytics_tab(tab_name: str) -> Dict[str, Any]:
    """Get analytics for specific tab"""
    return {
        "tab": tab_name,
        "data": []
    }


@app.get("/api/pipeline-engines")
def get_pipeline_engines() -> Dict[str, Any]:
    """Get pipeline engines status (alias for /api/engines)"""
    return get_engines()


@app.get("/api/gpu/stats")
def get_gpu_stats() -> Dict[str, Any]:
    """Get GPU statistics"""
    import subprocess
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
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
                    "temperature_c": int(parts[4])
                }
    except Exception as e:
        logger.error(f"Error getting GPU stats: {e}")
    
    return {
        "available": False,
        "error": "GPU not available"
    }


@app.get("/api/wsl2-status")
def get_wsl2_status() -> Dict[str, Any]:
    """Get WSL2 status (consolidated helper)."""
    return _collect_wsl_status()


@app.get("/api/command-center")
def get_command_center() -> Dict[str, Any]:
    """Command center status - consolidates all system info."""
    db_healthy = _DB_PATH.exists()
    processing_stats = get_progress()
    model_stats = get_models()
    wsl_status = _collect_wsl_status()

    # GPU snapshot (keep consistent with /api/gpu/stats)
    gpu_stats = get_gpu_stats()

    pipeline_healthy = processing_stats.get("status") not in (None, "error", "disabled")
    health = {
        "api": True,
        "database": db_healthy,
        "wsl": wsl_status.get("available", False),
        "pipeline": pipeline_healthy,
    }

    return {
        "status": "active",
        "health": health,
        "gpu": gpu_stats,
        "processing": processing_stats,
        "models": model_stats,
        "wsl": wsl_status,
        "timestamp": datetime.now().isoformat(),
        "logs": _build_health_logs(health),
    }


@app.get("/api/processes")
def get_processes() -> Dict[str, Any]:
    """Get running processes with GPU status"""
    import subprocess
    
    # Get GPU status
    gpu_status = {"available": False, "gpus": []}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 5:
                        gpu_id, name, util, mem_used, mem_total = parts[:5]
                        temp = parts[5] if len(parts) > 5 else None
                        power = parts[6] if len(parts) > 6 else None
                        
                        mem_used_gb = round(int(mem_used) / 1024, 1)
                        mem_total_gb = round(int(mem_total) / 1024, 1)
                        mem_percent = round((int(mem_used) / int(mem_total)) * 100, 1)
                        
                        gpus.append({
                            "id": int(gpu_id),
                            "name": name,
                            "gpu_utilization": int(util),
                            "memory_used_gb": mem_used_gb,
                            "memory_total_gb": mem_total_gb,
                            "memory_percent": mem_percent,
                            "temperature_c": int(temp) if temp and temp.isdigit() else None,
                            "power_watts": int(float(power)) if power and power.replace('.','').isdigit() else None,
                            "process_count": 0
                        })
            
            if gpus:
                gpu_status = {"available": True, "gpus": gpus}
    except Exception as e:
        logger.debug(f"GPU status unavailable: {e}")
    
    return {
        "processes": [],
        "gpu_status": gpu_status
    }


@app.post("/api/processes/{name}/{action}")
def control_process(name: str, action: str) -> Dict[str, Any]:
    """Control a process (start/stop/restart)"""
    return {
        "process": name,
        "action": action,
        "success": False,
        "message": "disabled"
    }


@app.post("/api/test-audio")
def test_audio(request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Test audio processing via WSL2"""
    return {"success": False, "message": "disabled"}

    try:
        import subprocess
        config_model = None
        diarization_model = None
        # Try native Windows path (WSL mount), then WSL cat fallback
        try:
            workspace_parts = [part for part in _WSL_WORKSPACE.strip("/").split("/") if part]
            cfg_path = Path(f"\\\\wsl$\\{_WSL_DISTRO}\\" + "\\".join(workspace_parts) + "\\config.json")
            if not cfg_path.exists():
                cfg_path = Path(f"{_WSL_WORKSPACE}/config.json")
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
            else:
                cfg = None
            if cfg is None:
                # Fallback: fetch via wsl cat
                cfg_proc = subprocess.run(
                    ["wsl", "-d", _WSL_DISTRO, "--", "cat", f"{_WSL_WORKSPACE}/config.json"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if cfg_proc.returncode == 0 and cfg_proc.stdout:
                    cfg = json.loads(cfg_proc.stdout)
            if cfg:
                config_model = cfg.get("models", {}).get("whisper")
                diarization_model = cfg.get("models", {}).get("diarization")
        except Exception as cfg_err:
            logger.warning(f"Audio test config read error: {cfg_err}")
        
        # Check if audio service is running
        result = subprocess.run(
            ["wsl", "-d", _WSL_DISTRO, "--", "systemctl", "is-active", "goodq-audio.service"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        wsl_available = result.returncode == 0
        cuda_available = False
        try:
            cuda_check = subprocess.run(
                ["wsl", "-d", _WSL_DISTRO, "--", "bash", "-lc", "nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -n1"],
                capture_output=True,
                text=True,
                timeout=5
            )
            cuda_available = cuda_check.returncode == 0 and bool(cuda_check.stdout.strip())
        except Exception as cuda_err:
            logger.warning(f"Audio CUDA check failed: {cuda_err}")
        
        # Check if we can access the audio processing scripts
        check_scripts = subprocess.run(
            ["wsl", "-d", _WSL_DISTRO, "--", "test", "-d", f"{_WSL_WORKSPACE}/scripts"],
            capture_output=True,
            timeout=5
        )
        
        scripts_available = check_scripts.returncode == 0
        
        return {
            "success": wsl_available and scripts_available,
            "model": config_model or "medium",
            "cuda": cuda_available,
            "diarization": bool(diarization_model),
            "message": "Audio processing ready" if (wsl_available and scripts_available) else "WSL2 or audio scripts not available",
            "details": {
                "wsl2_active": wsl_available,
                "audio_scripts": scripts_available,
                "transcription_ready": wsl_available and scripts_available,
                "diarization_ready": wsl_available and scripts_available and bool(diarization_model)
            }
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "WSL2 timeout - service may be slow to respond"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Audio test failed: {str(e)}"
        }




@app.get("/api/models")
def get_models() -> Dict[str, Any]:
    """Get LLM model health status - proxies health API"""
    try:
        import requests
        resp = requests.get("http://localhost:5050/api/health", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        # Only debug-log to avoid noisy errors when the health service is not running
        logger.debug(f"Model health service unavailable: {e}")
    
    # Fallback
    return {
        "timestamp": None,
        "total_models": 0,
        "healthy_models": 0,
        "vllm_total": 0,
        "vllm_healthy": 0,
        "ollama_total": 0,
        "ollama_healthy": 0,
        "models": []
    }


def _local_progress_stats() -> Dict[str, Any]:
    """Best-effort processing stats based on local progress.json and filesystem."""
    progress_file = _LOG_DIR / "progress.json"
    processing_dir = _PROCESSING_PATH
    processed_dir = _PROCESSING_PATH.parent / "processed"

    progress = {}
    try:
        if progress_file.exists():
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"progress.json read failed: {e}")

    details = progress.get("details", {}) if isinstance(progress, dict) else {}
    raw_details_str = ""
    if isinstance(details, dict):
        raw_details_str = details.get("details") or details.get("status") or ""
    elif isinstance(details, str):
        raw_details_str = details

    def _count_files(p: Path) -> int:
        try:
            return len([f for f in p.iterdir() if f.is_file()])
        except Exception:
            return 0

    current_name = progress.get("current_file") if isinstance(progress, dict) else None
    status = progress.get("status") if isinstance(progress, dict) else None
    if not status:
        status = "active" if _count_files(processing_dir) > 0 else "idle"

    stats = {
        "status": status,
        "current_video": {
            "name": current_name,
            "size_gb": details.get("video_size_gb", 0),
            "progress_percent": progress.get("progress_percent", 0) if isinstance(progress, dict) else 0,
            "current_step": progress.get("current_step", "Idle") if isinstance(progress, dict) else "Idle",
            "current_step_index": progress.get("current_step_index"),
            "total_steps": progress.get("total_steps"),
            "details": raw_details_str,
        },
        "scenes": {
            "detected": details.get("scenes_detected", 0) or details.get("scenes_found", 0) or 0,
            "frames_extracted": details.get("frames_extracted", 0),
            "audio_clips": details.get("audio_clips", 0),
        },
        "processing_rate": {
            "scenes_per_minute": 0,
            "seconds_per_scene": 0,
        },
        "totals": {
            "videos_completed": _count_files(processed_dir),
            "videos_active": _count_files(processing_dir),
        },
        "timestamps": {
            "started_at": progress.get("started_at") if isinstance(progress, dict) else None,
            "updated_at": progress.get("updated_at") if isinstance(progress, dict) else datetime.utcnow().isoformat(),
        },
        "raw_progress": progress if isinstance(progress, dict) else {},
    }
    # Enrich with latest run snapshot from logs if available
    latest = _latest_run_snapshot()
    if latest.get("available"):
        if not stats["current_video"]["name"]:
            stats["current_video"]["name"] = latest.get("video")
        if stats["scenes"]["detected"] == 0 and latest.get("scenes", 0) > 0:
            stats["scenes"]["detected"] = latest.get("scenes", 0)
            stats["scenes"]["frames_extracted"] = latest.get("frames", 0)
            stats["scenes"]["audio_clips"] = latest.get("audio", 0)
        stats["latest_run"] = latest
    stats["log_tail"] = _tail_log(Path("logs/watchdog.log"))
    return stats


def _latest_run_snapshot(limit: int = 12) -> Dict[str, Any]:
    """
    Inspect logs/watchdog_* folders for the most recent run and return summary counts.
    """
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
    """
    Inspect logs/watchdog_* folders and return a quick preview of the most recent run.
    Exposes scene thumbnails/audio clips so the dashboard can show real artifacts.
    """
    return {"available": False, "disabled": True}

    runs = sorted(Path("logs").glob("watchdog_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        return {"available": False}
    run_dir = next((r for r in runs if r.is_dir()), None)
    if not run_dir:
        return {"available": False}

    # Pick first video folder inside the run (e.g., "01. 1987 - 1988")
    subdirs = [d for d in run_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
    video_dir = subdirs[0] if subdirs else run_dir

    frames = sorted(video_dir.glob("frames/*.jpg"))
    audio = sorted(video_dir.glob("audio/*.wav"))
    thumbs = frames[:limit]

    def to_url(p: Path) -> str:
        rel = p.relative_to(Path("logs"))
        return f"/logs/{rel.as_posix()}"

    return {
        "available": True,
        "run_id": run_dir.name,
        "video": video_dir.name,
        "scenes": len({f.stem.split('_')[1] for f in frames}) if frames else 0,
        "frames": len(frames),
        "audio": len(audio),
        "thumbnails": [{"url": to_url(p), "name": p.name} for p in thumbs],
        "run_path": str(run_dir),
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


@app.get("/api/runs/latest/preview")
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


@app.get("/api/memory/stats")
def get_memory_stats() -> Dict[str, Any]:
    """Lightweight memory stats across tiers (faiss/qdrant)."""
    cfg = _CFG

    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    memory_cfg = (cfg.get("memory") or {}) if isinstance(cfg, dict) else {}

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
            "read_priority": (memory_cfg.get("routing") or {}).get("read_priority") or [],
            "write_targets": (memory_cfg.get("routing") or {}).get("write_targets") or [],
        },
        "latest_run": _latest_run_preview(limit=12),
    }


@app.get("/api/logs/watchdog")
def get_watchdog_logs(lines: int = 200) -> Dict[str, Any]:
    """Tail the watchdog log for the command center UI."""
    return {"available": False, "lines": [], "disabled": True}

    log_path = _LOG_DIR / "watchdog.log"
    result: Dict[str, Any] = {
        "available": log_path.exists(),
        "path": str(log_path),
        "lines": []
    }
    if not log_path.exists():
        return result
    try:
        dq = deque(maxlen=lines)
        with log_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                dq.append(line.rstrip("\n"))
        result["lines"] = list(dq)
    except Exception as e:
        result["error"] = str(e)
    return result


@app.get("/api/processing/stats")
@app.get("/api/progress")
def get_progress() -> Dict[str, Any]:
    """Get current processing progress - proxies processing stats API or returns fallback"""
    return {"status": "disabled"}

    try:
        import requests
        resp = requests.get("http://localhost:5001/api/processing/stats", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            data["latest_run"] = _latest_run_snapshot()
            data["log_tail"] = _tail_log(Path("logs/watchdog.log"))
            return data
    except Exception as e:
        logger.debug(f"Processing stats API unavailable: {e}")
    
    # Fallback - return local snapshot based on progress.json and filesystem
    stats = _local_progress_stats()
    stats["latest_run"] = _latest_run_snapshot()
    stats["log_tail"] = _tail_log(Path("logs/watchdog.log"))
    return stats


@app.get("/api/pipeline-engines")
def get_pipeline_engines() -> Dict[str, Any]:
    """Alias for /api/engines for compatibility"""
    return get_engines()


@app.get("/api/scene/{scene_id}")
def get_scene(scene_id: str) -> Dict[str, Any]:
    """Get specific scene details"""
    return {
        "scene_id": scene_id,
        "details": {}
    }


@app.post("/api/chat/control-agent")
def chat_with_control_agent(request: ChatRequest) -> Dict[str, Any]:
    """Chat with the Control Agent for pipeline diagnostics and help"""
    return {"success": False, "error": "disabled", "response": "disabled"}

    try:
        # Initialize LLM client
        llm = LLMClient(
            models=build_llm_models(_CFG),
            health_check_interval=60,
            max_retries=3,
            timeout=30,
            cache_ttl=300,
            enable_health_checks=False,
        )
        
        # Build context-aware prompt
        system_prompt = """You are the GoodQ4All Control Agent, an AI assistant that helps users:
- Diagnose pipeline errors and failures
- Recommend configuration changes
- Explain system status and logs
- Suggest optimization strategies
- Answer questions about the video processing pipeline

Be concise, technical, and actionable. Format responses with markdown."""
        
        # Add context if provided
        user_message = request.message
        if request.context:
            user_message = f"Context: {request.context}\n\nQuestion: {request.message}"
        
        # Get response from LLM
        result = llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        # Extract message from OpenAI-compatible response
        message_content = result.get("choices", [{}])[0].get("message", {}).get("content", "No response generated")
        
        return {
            "success": True,
            "response": message_content,
            "model": llm.get_active_model(),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Control agent chat error: {error_detail}")
        return {
            "success": False,
            "error": str(e),
            "response": "Control Agent is currently unavailable. Please check that vLLM or Ollama is running.",
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }

# Read-only wiring: serve a precomputed EpistemicReadEnvelope bundle without accepting arbitrary queries/commands.
@app.get("/api/read/envelope")
def read_epistemic_envelope() -> Dict[str, Any]:
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

# Legacy UI/log static mounts intentionally disabled.
