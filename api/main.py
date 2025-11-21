from __future__ import annotations
from typing import Any, Dict
import sys
import logging
from pathlib import Path
from datetime import datetime
import threading
import requests

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Any, Dict
from pydantic import BaseModel

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
            resp = requests.get("http://localhost:8003/v1/models", timeout=0.2)
            if resp.status_code == 200:
                models_data["vllm_healthy"] = 1
                models_data["healthy"] += 1
        except:
            pass
        
        try:
            resp = requests.get("http://localhost:11434/v1/models", timeout=0.2)
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
            "wsl_audio": "available"
        },
        "gpu": gpu_data,
        "models": models_data,
        "processing": processing_data
    }


@app.get("/api/health/summary")
def get_health_summary() -> Dict[str, Any]:
    """Get health summary for all LLM models (vLLM + Ollama)"""
    # Check models directly
    vllm_healthy = 0
    ollama_healthy = 0
    
    try:
        resp = requests.get("http://localhost:8003/v1/models", timeout=1)
        if resp.status_code == 200:
            vllm_healthy = 1
    except:
        pass
    
    try:
        resp = requests.get("http://localhost:11434/v1/models", timeout=1)
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
            "models": ["Llama-1B-Speed"] if vllm_healthy > 0 else []
        },
        "ollama": {
            "status": "healthy" if ollama_healthy > 0 else "unhealthy",
            "healthy": ollama_healthy,
            "models": ["Phi4-Ollama"] if ollama_healthy > 0 else []
        }
    }


@app.get("/api/engines")
def get_engines() -> Dict[str, Any]:
    """Get pipeline engine status"""
    import subprocess
    import shutil
    
    engines = {}
    
    # Check vLLM on WSL
    try:
        import requests
        resp = requests.get("http://localhost:8003/v1/models", timeout=2)
        if resp.status_code == 200:
            model_data = resp.json().get("data", [])
            model_name = model_data[0]["id"].split("/")[-1] if model_data else "Unknown"
            engines["vllm_llama1b"] = {
                "name": "vLLM Llama-1B",
                "category": "LLM Inference",
                "description": f"Llama 1B Speed model on port 8003",
                "status": "ready",
                "gpu": True,
                "port": 8003
            }
        else:
            raise Exception("unhealthy")
    except:
        engines["vllm_llama1b"] = {
            "name": "vLLM Llama-1B",
            "category": "LLM Inference",
            "description": "Not running or unreachable",
            "status": "unavailable",
            "gpu": True,
            "port": 8003
        }
    
    # Check Ollama
    try:
        import requests
        resp = requests.get("http://localhost:11434/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_name = models[0]["id"] if models else "Unknown"
            engines["ollama"] = {
                "name": "Ollama",
                "category": "LLM Inference",
                "description": f"Phi4 and other models on port 11434",
                "status": "ready",
                "gpu": True,
                "port": 11434
            }
        else:
            raise Exception("unhealthy")
    except:
        engines["ollama"] = {
            "name": "Ollama",
            "category": "LLM Inference",
            "description": "Not running or unreachable",
            "status": "unavailable",
            "gpu": True,
            "port": 11434
        }
    
    # Check WSL audio processing
    wsl_available = shutil.which("wsl") is not None
    engines["wsl_audio"] = {
        "name": "WSL Audio Transcription",
        "category": "Audio Processing",
        "description": "Faster-Whisper with speaker diarization",
        "status": "ready" if wsl_available else "unavailable",
        "gpu": True
    }
    
    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    engines["ffmpeg"] = {
        "name": "FFmpeg",
        "category": "Video Processing",
        "description": f"Path: {ffmpeg_path}" if ffmpeg_path else "Not found",
        "status": "ready" if ffmpeg_path else "unavailable",
        "gpu": False
    }
    
    # Check Python environment
    engines["python_pipeline"] = {
        "name": "Python Pipeline",
        "category": "Orchestration",
        "description": f"Python {sys.version.split()[0]}",
        "status": "ready",
        "gpu": False
    }
    
    # Check scene detection
    try:
        from scenedetect import detect
        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "PySceneDetect for content-aware splitting",
            "status": "ready",
            "gpu": False
        }
    except:
        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "PySceneDetect not available",
            "status": "unavailable",
            "gpu": False
        }
    
    # Check vector database
    import os
    from pathlib import Path
    chroma_dir = Path("L:/goodq4all/data/chroma")
    engines["vector_db"] = {
        "name": "Vector Database",
        "category": "Search & Retrieval",
        "description": f"ChromaDB at {chroma_dir}",
        "status": "ready" if chroma_dir.exists() else "unavailable",
        "gpu": False
    }
    
    # Check audio diarization
    engines["audio_diarization"] = {
        "name": "Audio Diarization",
        "category": "Audio Processing",
        "description": "Pyannote speaker separation with OSD",
        "status": "ready",
        "gpu": True
    }
    
    return engines


@app.get("/api/engines")
def get_engines() -> Dict[str, Any]:
    """Get model engine health summary for dashboard"""
    vllm_healthy = 0
    vllm_total = 0
    ollama_healthy = 0
    ollama_total = 0
    
    # Check vLLM
    try:
        resp = requests.get("http://localhost:8003/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            vllm_total = len(models)
            vllm_healthy = vllm_total
    except:
        pass
    
    # Check Ollama
    try:
        resp = requests.get("http://localhost:11434/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            ollama_total = len(models)
            ollama_healthy = ollama_total
    except:
        pass
    
    # Determine status
    def get_status(healthy, total):
        if total == 0:
            return "unavailable"
        elif healthy == total:
            return "healthy"
        elif healthy > 0:
            return "degraded"
        else:
            return "down"
    
    return {
        "vllm": {
            "status": get_status(vllm_healthy, vllm_total),
            "healthy": vllm_healthy,
            "total": max(vllm_total, 1),  # Show at least 1 to avoid division by zero
            "port": 8003
        },
        "ollama": {
            "status": get_status(ollama_healthy, ollama_total),
            "healthy": ollama_healthy,
            "total": max(ollama_total, 1),
            "port": 11434
        },
        "timestamp": datetime.utcnow().isoformat()
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
    from steps.steps.common.config_loader import load_configs
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
                return json.load(f)
        except:
            pass
    
    # Return empty graph structure
    return {
        "nodes": [],
        "links": []
    }


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None


@app.get("/api/queue")
def get_queue() -> Dict[str, Any]:
    """Get current processing queue"""
    return {
        "queue": [],
        "active": 0,
        "pending": 0,
        "completed": 0
    }


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
    """Get WSL2 status"""
    import subprocess
    import shutil
    
    wsl_available = shutil.which("wsl") is not None
    
    if not wsl_available:
        return {
            "available": False,
            "status": "not_installed"
        }
    
    try:
        result = subprocess.run(
            ["wsl", "-l", "-v"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return {
            "available": True,
            "status": "running" if result.returncode == 0 else "stopped",
            "output": result.stdout
        }
    except:
        return {
            "available": True,
            "status": "unknown"
        }


@app.get("/api/command-center")
def get_command_center() -> Dict[str, Any]:
    """Get command center status with system health"""
    import subprocess
    
    # Check API health (always healthy if we're responding)
    api_healthy = True
    
    # Check database health
    db_healthy = False
    try:
        # Main memory database
        db_path = Path("L:/goodq4all/data/memory.db")
        db_healthy = db_path.exists()
    except:
        pass
    
    # Check WSL/GPU health
    wsl_healthy = False
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=2
        )
        wsl_healthy = result.returncode == 0
    except:
        pass
    
    # Check pipeline health (check if processes are running)
    pipeline_healthy = False
    try:
        # Check if processing stats API is running
        import requests
        resp = requests.get("http://localhost:5001/api/processing/stats", timeout=1)
        pipeline_healthy = resp.status_code == 200
    except:
        pass
    
    return {
        "status": "active",
        "health": {
            "api": api_healthy,
            "database": db_healthy,
            "wsl": wsl_healthy,
            "pipeline": pipeline_healthy
        },
        "logs": [
            {"level": "info", "timestamp": "now", "message": "Command center operational"},
            {"level": "success" if api_healthy else "error", "message": f"API: {'Healthy' if api_healthy else 'Degraded'}"},
            {"level": "success" if db_healthy else "error", "message": f"Database: {'Healthy' if db_healthy else 'Not Found'}"},
            {"level": "success" if wsl_healthy else "warning", "message": f"WSL/GPU: {'Healthy' if wsl_healthy else 'Unavailable'}"},
            {"level": "success" if pipeline_healthy else "warning", "message": f"Pipeline: {'Active' if pipeline_healthy else 'Standby'}"}
        ]
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
        
        # Check if vLLM service is running (as a proxy for WSL2 being available)
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "systemctl", "is-active", "vllm-llama1b.service"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        wsl_available = result.returncode == 0
        
        # Check if we can access the audio processing scripts
        check_scripts = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "test", "-d", "/mnt/l/goodq4all/goodq4all/audio"],
            capture_output=True,
            timeout=5
        )
        
        scripts_available = check_scripts.returncode == 0
        
        return {
            "success": wsl_available and scripts_available,
            "message": "Audio processing ready" if (wsl_available and scripts_available) else "WSL2 or audio scripts not available",
            "details": {
                "wsl2_active": wsl_available,
                "audio_scripts": scripts_available,
                "transcription_ready": wsl_available and scripts_available,
                "diarization_ready": wsl_available and scripts_available
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
        logger.error(f"Failed to get model health: {e}")
    
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
    
    # Fallback - return idle state
    return {
        "status": "idle",
        "current_video": {"name": None, "progress_percent": 0, "current_step": "Idle"},
        "scenes": {"detected": 0, "frames_extracted": 0, "audio_clips": 0},
        "processing_rate": {"scenes_per_minute": 0, "seconds_per_scene": 0},
        "totals": {"videos_completed": 0, "videos_active": 0},
        "timestamps": {"started_at": None, "updated_at": None}
    }


@app.get("/api/command-center")
def get_command_center() -> Dict[str, Any]:
    """Command center status - consolidates all system info"""
    import subprocess
    import requests
    
    # Get GPU stats
    gpu_stats = {"available": False}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu", 
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            name, util, mem_used, mem_total, temp = result.stdout.strip().split(",")
            gpu_stats = {
                "available": True,
                "name": name.strip(),
                "utilization": int(util.strip()),
                "memory_used": int(mem_used.strip()),
                "memory_total": int(mem_total.strip()),
                "temperature": int(temp.strip())
            }
    except:
        pass
    
    # Get processing stats
    processing_stats = get_progress()
    
    # Get model health
    model_stats = get_models()
    
    # Get WSL2 status
    wsl_status = {"available": False, "vllm_service": "unknown"}
    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "systemctl", "is-active", "vllm-llama1b.service"],
            capture_output=True,
            text=True,
            timeout=3
        )
        wsl_status = {
            "available": True,
            "vllm_service": "active" if result.returncode == 0 else "inactive"
        }
    except:
        pass
    
    return {
        "gpu": gpu_stats,
        "processing": processing_stats,
        "models": model_stats,
        "wsl": wsl_status,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/wsl2-status")
def get_wsl2_status() -> Dict[str, Any]:
    """Get WSL2 and vLLM service status"""
    import subprocess
    
    status = {
        "wsl_available": False,
        "vllm_service": "unknown",
        "audio_processing": "unknown"
    }
    
    try:
        # Check if WSL is available
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            text=True,
            timeout=3
        )
        status["wsl_available"] = result.returncode == 0
        
        if status["wsl_available"]:
            # Check vLLM service
            vllm_check = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "systemctl", "is-active", "vllm-llama1b.service"],
                capture_output=True,
                text=True,
                timeout=3
            )
            status["vllm_service"] = "active" if vllm_check.returncode == 0 else "inactive"
            
            # Check if Faster Whisper is available (python -c import test)
            audio_check = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-c", 
                 "python3 -c 'import faster_whisper' 2>/dev/null && echo 'ok' || echo 'error'"],
                capture_output=True,
                text=True,
                timeout=5
            )
            status["audio_processing"] = "available" if "ok" in audio_check.stdout else "unavailable"
            status["faster_whisper"] = "ready" if "ok" in audio_check.stdout else "not_installed"
    except Exception as e:
        logger.error(f"WSL2 status check failed: {e}")
    
    return status


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
