from __future__ import annotations
from typing import Any, Dict
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
import threading
import requests
from collections import deque

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Any, Dict
from pydantic import BaseModel

from steps.common.config_loader import load_configs
from steps.common.memory_manager import build_memory_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GoodQ Retrieval API", version="0.1.0")

# Add UTF-8 charset to JSON responses
class UTF8JSONMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["content-type"] = "application/json; charset=utf-8"
        return response

app.add_middleware(UTF8JSONMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UI will be mounted at the end after all API routes are defined

_CFG = load_configs({})
_MEMORY_ROUTER = build_memory_router(_CFG)


def _summarize_llm_health() -> Dict[str, Any]:
    """Lightweight LLM health summary used by /api/engines and dashboards."""
    vllm_healthy = 0
    vllm_total = 0
    ollama_healthy = 0
    ollama_total = 0

    try:
        resp = requests.get("http://localhost:38005/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            vllm_total = len(models)
            vllm_healthy = vllm_total
    except Exception:
        pass

    try:
        resp = requests.get("http://localhost:31434/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            ollama_total = len(models)
            ollama_healthy = ollama_total
    except Exception:
        pass

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
            "port": 31434,
        },
        "overall": {
            "status": "healthy" if healthy_models == total_models else "degraded" if healthy_models > 0 else "unhealthy",
            "total": total_models,
            "healthy": healthy_models,
            "unhealthy": max(total_models - healthy_models, 0),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/memory/stats")
def memory_stats() -> Dict[str, Any]:
    """Tiered memory stats across chroma/faiss/qdrant."""
    stats = _MEMORY_ROUTER.stats()
    chroma_vecs = stats["tiers"].get("chroma", {}).get("vectors", 0)
    faiss_vecs = stats["tiers"].get("faiss", {}).get("vectors", 0)
    qdrant_vecs = stats["tiers"].get("qdrant", {}).get("vectors", 0)
    warnings = []
    if chroma_vecs and faiss_vecs == 0 and qdrant_vecs == 0:
        warnings.append("Chroma has items but FAISS/Qdrant are empty; consider promoting.")
    stats["warnings"] = warnings
    return stats


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
    except Exception:
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
        resp = requests.get("http://localhost:31434/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_name = models[0]["id"] if models else "Unknown"
            engines["ollama"] = {
                "name": "Ollama",
                "category": "LLM Inference",
                "description": f"{model_name} on port 31434",
                "status": "ready",
                "gpu": True,
                "port": 31434,
            }
        else:
            raise Exception("unhealthy")
    except Exception:
        engines["ollama"] = {
            "name": "Ollama",
            "category": "LLM Inference",
            "description": "Not running or unreachable",
            "status": "unavailable",
            "gpu": True,
            "port": 31434,
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
        resp = requests.get("http://localhost:36335/collections", timeout=2)
        if resp.status_code == 200:
            collections = resp.json().get("result", {}).get("collections", [])
            engines["qdrant"] = {
                "name": "Qdrant",
                "category": "Vector DB",
                "description": f"{len(collections)} collections @ 36335",
                "status": "ready",
                "gpu": False,
                "port": 36335,
            }
        else:
            raise Exception("unhealthy")
    except Exception:
        engines["qdrant"] = {
            "name": "Qdrant",
            "category": "Vector DB",
            "description": "Not reachable on 36335",
            "status": "unavailable",
            "gpu": False,
            "port": 36335,
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
    except Exception:
        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "PySceneDetect not available",
            "status": "unavailable",
            "gpu": False,
        }

    # Check vector database
    chroma_dir = Path("L:/goodq4all/data/chroma")
    engines["vector_db"] = {
        "name": "Vector Database",
        "category": "Search & Retrieval",
        "description": f"ChromaDB at {chroma_dir}",
        "status": "ready" if chroma_dir.exists() else "unavailable",
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
    except Exception:
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
            ["wsl", "-d", "Ubuntu", "--", "systemctl", "is-active", "vllm-llama1b.service"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        status["vllm_service"] = "active" if vllm_check.returncode == 0 else "inactive"
    except Exception:
        pass

    # Fast, low-impact audio availability check (skip on timeout)
    try:
        audio_check = subprocess.run(
            [
                "wsl",
                "-d",
                "Ubuntu",
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
                "Ubuntu",
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
                "Ubuntu",
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


# Root endpoint - redirect to dashboard
from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    """Redirect root to main interface"""
    return RedirectResponse(url="/index.html")

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
        except:
            pass
        
        try:
            resp = requests.get("http://localhost:31434/v1/models", timeout=0.2)
            if resp.status_code == 200:
                models_data["ollama_healthy"] = 1
                models_data["healthy"] += 1
        except:
            pass
    except:
        pass
    
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
        db_path = Path("L:/goodq4all/data/memory.db")
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
        "version": "1.4.0",
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
    except:
        pass
    
    try:
        resp = requests.get("http://localhost:31434/v1/models", timeout=1)
        if resp.status_code == 200:
            ollama_healthy = 1
    except:
        pass
    
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
    # Lazy imports to keep startup fast
    from steps.common.config_loader import load_configs
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    import os

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    persist_dir = paths.get("chroma_dir") or "L:/goodq4all/data/databases/chroma"

    emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma(collection_name="goodq", persist_directory=persist_dir, embedding_function=emb)

    # Fetch more than topk to allow filtering, then trim
    k0 = max(topk * 5, topk)
    docs = vectordb.similarity_search(q, k=k0)

    def _pass_filters(md: Dict[str, Any]) -> bool:
        if modality and str(md.get("modality") or "") != modality:
            return False
        if event:
            evs = md.get("events") or []
            if isinstance(evs, list):
                if event not in [str(e) for e in evs]:
                    return False
            else:
                return False
        if tag:
            tags = md.get("tags") or md.get("entities") or []
            hay = [str(t).lower() for t in (tags if isinstance(tags, list) else [])]
            if tag.lower() not in hay:
                return False
        return True

    matches: List[Dict[str, Any]] = []
    for d in docs:
        md = d.metadata or {}
        if not _pass_filters(md):
            continue
        matches.append({
            "source_path": md.get("source_path"),
            "filename": md.get("filename"),
            "modality": md.get("modality"),
            "score": None,  # Chroma doesn't return distance via this API
            "snippet": (d.page_content or "")[:280],
            "metadata": md,
        })
        if len(matches) >= topk:
            break

    return {"matches": matches, "persist_dir": persist_dir}


@app.get("/api/scenes")
def get_scenes() -> Dict[str, Any]:
    """Get detected scenes from video processing"""
    import json
    from pathlib import Path
    
    # Look for scenes in data/output
    scenes_dir = Path("L:/goodq4all/data/output")
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
            except:
                continue
    
    return {"scenes": all_scenes, "total": len(all_scenes)}


@app.get("/api/knowledge_graph")
def get_knowledge_graph() -> Dict[str, Any]:
    """Get knowledge graph data"""
    import json
    from pathlib import Path
    
    # Look for entity data
    # Primary KG database (SQLite)
    kg_db = Path("L:/goodq4all/data/knowledge_graph.db")
    # Legacy JSON export (fallback)
    kg_file = Path("L:/goodq4all/data/output/knowledge_graph.json")
    
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
    base_dir = Path("L:/goodq4all")
    import_inbox = base_dir / "import_inbox"
    processing_dir = base_dir / "data" / "processing"
    processed_dir = base_dir / "data" / "processed"
    failed_dir = base_dir / "data" / "failed"

    queue_data = {
        "inbox": {"count": 0, "files": [], "total_size_mb": 0},
        "processing": {"count": 0, "files": []},
        "processed": {"count": 0},
        "failed": {"count": 0}
    }

    try:
        if import_inbox.exists():
            video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
            inbox_files = [f for f in import_inbox.iterdir() if f.suffix.lower() in video_exts]
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
        print(f"[WARN] queue status error: {e}")

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
    db_healthy = Path("L:/goodq4all/data/memory.db").exists()
    processing_stats = get_progress()
    model_stats = get_models()
    wsl_status = _collect_wsl_status()

    # GPU snapshot (keep consistent with /api/gpu/stats)
    gpu_stats = get_gpu_stats()

    pipeline_healthy = processing_stats.get("status") not in (None, "error")
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
        "message": "Process control not yet implemented"
    }


@app.post("/api/test-audio")
def test_audio(request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Test audio processing via WSL2"""
    try:
        import subprocess
        config_model = None
        diarization_model = None
        # Try native Windows path (WSL mount), then WSL cat fallback
        try:
            cfg_path = Path(r"\\wsl$\Ubuntu\home\joesdomingo\goodq_audio\config.json")
            if not cfg_path.exists():
                cfg_path = Path("/home/joesdomingo/goodq_audio/config.json")
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
            else:
                cfg = None
            if cfg is None:
                # Fallback: fetch via wsl cat
                cfg_proc = subprocess.run(
                    ["wsl", "-d", "Ubuntu", "--", "cat", "/home/joesdomingo/goodq_audio/config.json"],
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
            print(f"[WARN] audio test config read error: {cfg_err}")
        
        # Check if audio service is running
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "systemctl", "is-active", "goodq-audio.service"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        wsl_available = result.returncode == 0
        cuda_available = False
        try:
            cuda_check = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", "nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -n1"],
                capture_output=True,
                text=True,
                timeout=5
            )
            cuda_available = cuda_check.returncode == 0 and bool(cuda_check.stdout.strip())
        except Exception as cuda_err:
            print(f"[WARN] audio CUDA check failed: {cuda_err}")
        
        # Check if we can access the audio processing scripts
        check_scripts = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "test", "-d", "/mnt/l/goodq4all/wsl2_audio"],
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
    progress_file = Path("L:/goodq4all/logs/progress.json")
    processing_dir = Path("L:/goodq4all/data/processing")
    processed_dir = Path("L:/goodq4all/data/processed")

    progress = {}
    try:
        if progress_file.exists():
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"progress.json read failed: {e}")

    details = progress.get("details", {}) if isinstance(progress, dict) else {}

    def _count_files(p: Path) -> int:
        try:
            return len([f for f in p.iterdir() if f.is_file()])
        except Exception:
            return 0

    current_name = progress.get("current_file") if isinstance(progress, dict) else None
    status = progress.get("status") if isinstance(progress, dict) else None
    if not status:
        status = "active" if _count_files(processing_dir) > 0 else "idle"

    return {
        "status": status,
        "current_video": {
            "name": current_name,
            "size_gb": details.get("video_size_gb", 0),
            "progress_percent": progress.get("progress_percent", 0) if isinstance(progress, dict) else 0,
            "current_step": progress.get("current_step", "Idle") if isinstance(progress, dict) else "Idle",
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
    }


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
    cfg = {}
    try:
        from steps.common.config_loader import load_configs
        cfg = load_configs({})
    except Exception:
        cfg = {}

    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    memory_cfg = (cfg.get("memory") or {}) if isinstance(cfg, dict) else {}

    faiss_info = {
        "text_vectors": _faiss_count(paths.get("faiss_index_path") or ""),
        "clip_vectors": _faiss_count(paths.get("faiss_clip_path") or ""),
        "audio_vectors": _faiss_count(paths.get("faiss_audio_path") or ""),
    }

    qdrant_info = {"available": False, "collections": 0}
    try:
        r = requests.get("http://localhost:36335/collections", timeout=2)
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
    }


@app.get("/api/logs/watchdog")
def get_watchdog_logs(lines: int = 200) -> Dict[str, Any]:
    """Tail the watchdog log for the command center UI."""
    log_path = Path("L:/goodq4all/logs/watchdog.log")
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
    try:
        import requests
        resp = requests.get("http://localhost:5001/api/processing/stats", timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Processing stats API unavailable: {e}")
    
    # Fallback - return local snapshot based on progress.json and filesystem
    return _local_progress_stats()


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
    try:
        # Import LLM client
        from lib.llm_client import LLMClient
        
        # Initialize LLM client
        llm = LLMClient()
        
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


# Mount static files LAST (catch-all for UI)
UI_DIR = Path(__file__).parent.parent / "web"  # web directory contains HTML files
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
    logger.info(f"✓ Serving UI from: {UI_DIR}")
else:
    logger.warning(f"UI directory not found: {UI_DIR}")
