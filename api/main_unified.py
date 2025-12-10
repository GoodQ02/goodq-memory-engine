"""
GoodQ4All Unified Production API Server
========================================
Single FastAPI server consolidating all endpoints:
- Health monitoring (models, GPU)
- Processing stats (real-time pipeline data)
- Search & retrieval
- Command center
- WSL status
- UI serving

Port: 30000
Author: GoodQ4All Team
Date: 2025-11-18
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List
import sys
import logging
from pathlib import Path
from datetime import datetime
import json
import subprocess
import shutil
import threading
import time
import os

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

# Add lib to path for LLM client
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# FastAPI App Setup
# ==============================================================================

app = FastAPI(
    title="GoodQ4All Unified API",
    version="2.0.0",
    description="Production-grade API serving all GoodQ4All functionality"
)

# UTF-8 charset middleware
class UTF8JSONMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["content-type"] = "application/json; charset=utf-8"
        return response

app.add_middleware(UTF8JSONMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# Global State & Caching
# ==============================================================================

# LLM client singleton
_llm_client = None
_client_lock = threading.Lock()

# Health cache
_health_cache = {}
_cache_lock = threading.Lock()
_last_health_update = None
HEALTH_CACHE_TTL = 5  # seconds

# Paths configuration
PROGRESS_FILE = Path("L:/goodq4all/logs/progress.json")
PROCESSING_DIR = Path("L:/_DATA/GoodQ_Data/processing")
OUTPUT_DIR = Path("L:/goodq4all/output")
CHROMA_DIR = Path("L:/_DATA/GoodQ_Data/chroma")
UI_DIR = Path("L:/goodq4all/_UI")

# ==============================================================================
# Helper Functions
# ==============================================================================

def get_llm_client():
    """Get or create LLM client singleton"""
    global _llm_client
    if _llm_client is None:
        with _client_lock:
            if _llm_client is None:  # Double-check
                try:
                    from llm_client import LLMClient
                    logger.info("Initializing LLM client...")
                    _llm_client = LLMClient()
                    logger.info(f"✓ LLM client initialized with {len(_llm_client.MODELS)} models")
                except Exception as e:
                    logger.error(f"Failed to initialize LLM client: {e}")
                    _llm_client = None
    return _llm_client


def get_gpu_stats() -> Dict[str, Any]:
    """Get GPU utilization via nvidia-smi"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            gpu_util, mem_used, mem_total, temp, name = result.stdout.strip().split(",")
            return {
                "available": True,
                "name": name.strip(),
                "utilization_percent": int(gpu_util.strip()),
                "memory_used_mb": int(mem_used.strip()),
                "memory_total_mb": int(mem_total.strip()),
                "memory_percent": round((int(mem_used.strip()) / int(mem_total.strip())) * 100, 1),
                "temperature_c": int(temp.strip())
            }
    except Exception as e:
        logger.debug(f"GPU stats unavailable: {e}")
    
    return {
        "available": False,
        "error": "nvidia-smi not accessible"
    }


def read_progress_json() -> Optional[Dict]:
    """Read current progress from progress.json"""
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read progress.json: {e}")
    return None


def get_processing_stats() -> Dict[str, Any]:
    """Calculate real-time processing statistics"""
    progress = read_progress_json()
    
    # Count completed videos
    completed_videos = 0
    try:
        if OUTPUT_DIR.exists():
            completed_videos = len([d for d in OUTPUT_DIR.iterdir() if d.is_dir()])
    except:
        pass
    
    # Count active processing
    active_processing = 0
    try:
        if PROCESSING_DIR.exists():
            active_processing = len([d for d in PROCESSING_DIR.iterdir() if d.is_dir()])
    except:
        pass
    
    # Get detailed processing info
    details = {
        "scenes_detected": 0,
        "frames_extracted": 0,
        "audio_clips": 0,
        "current_video": None,
        "video_size_gb": 0
    }
    
    try:
        if PROCESSING_DIR.exists():
            proc_dirs = [d for d in PROCESSING_DIR.iterdir() if d.is_dir()]
            for proc_dir in proc_dirs:
                video_files = list(proc_dir.glob("*.mp4")) + list(proc_dir.glob("*.avi"))
                if video_files:
                    video_file = video_files[0]
                    details["current_video"] = video_file.name
                    details["video_size_gb"] = round(video_file.stat().st_size / (1024**3), 2)
                    
                    scenes_dir = proc_dir / "scenes"
                    if scenes_dir.exists():
                        scene_count = len([d for d in scenes_dir.iterdir() if d.is_dir()])
                        details["scenes_detected"] = scene_count
                        
                        total_frames = 0
                        for scene_dir in scenes_dir.iterdir():
                            if scene_dir.is_dir():
                                frames_dir = scene_dir / "frames"
                                if frames_dir.exists():
                                    total_frames += len(list(frames_dir.glob("*.jpg")))
                        details["frames_extracted"] = total_frames
                    
                    audio_dir = proc_dir / "audio"
                    if audio_dir.exists():
                        details["audio_clips"] = len(list(audio_dir.glob("*.wav")))
                    break
    except Exception as e:
        logger.error(f"Failed to get processing details: {e}")
    
    # Calculate processing rate
    rates = {"scenes_per_minute": 0, "seconds_per_scene": 0}
    try:
        if progress and "started_at" in progress and "updated_at" in progress:
            started_str = progress["started_at"]
            updated_str = progress["updated_at"]
            
            if started_str and updated_str and isinstance(started_str, str) and isinstance(updated_str, str):
                started = datetime.fromisoformat(started_str)
                updated = datetime.fromisoformat(updated_str)
                elapsed = (updated - started).total_seconds()
                
                scenes_found = progress.get("details", {}).get("scenes_found", 0)
                if elapsed > 0 and scenes_found > 0:
                    rates = {
                        "scenes_per_minute": round((scenes_found / elapsed) * 60, 2),
                        "seconds_per_scene": round(elapsed / scenes_found, 1)
                    }
    except Exception as e:
        logger.error(f"Failed to calculate processing rate: {e}")
    
    return {
        "status": "active" if active_processing > 0 else "idle",
        "current_video": {
            "name": details.get("current_video") or (progress.get("current_file") if progress else None),
            "size_gb": details.get("video_size_gb", 0),
            "progress_percent": min(100, progress.get("progress_percent", 0) if progress else 0),
            "current_step": progress.get("current_step") if progress else "Idle"
        },
        "scenes": {
            "detected": details.get("scenes_detected", 0) or (progress.get("details", {}).get("scenes_found", 0) if progress else 0),
            "frames_extracted": details.get("frames_extracted", 0),
            "audio_clips": details.get("audio_clips", 0)
        },
        "processing_rate": rates,
        "totals": {
            "videos_completed": completed_videos,
            "videos_active": active_processing
        },
        "timestamps": {
            "started_at": progress.get("started_at") if progress else None,
            "updated_at": progress.get("updated_at") if progress else datetime.now().isoformat()
        }
    }


def update_health_cache():
    """Background thread to update health cache"""
    global _health_cache, _last_health_update
    
    while True:
        try:
            client = get_llm_client()
            if not client:
                time.sleep(HEALTH_CACHE_TTL)
                continue
            
            health_status = client.check_all_health(force=True)
            
            models_data = []
            for model in client.MODELS:
                status = health_status.get(model.name)
                if status:
                    models_data.append({
                        'name': model.name,
                        'endpoint': model.endpoint,
                        'backend': model.backend,
                        'port': model.port,
                        'model_id': model.model_id,
                        'is_healthy': status.is_healthy,
                        'response_time_ms': round(status.response_time_ms, 1),
                        'consecutive_failures': status.consecutive_failures,
                        'last_error': status.last_error,
                        'last_check': status.last_check.isoformat(),
                        'capabilities': model.capabilities,
                        'vram_gb': model.vram_gb,
                        'tokens_per_sec': model.tokens_per_sec,
                        'context_length': model.context_length,
                        'priority': model.priority,
                    })
            
            healthy_count = sum(1 for m in models_data if m['is_healthy'])
            vllm_healthy = sum(1 for m in models_data if m['backend'] == 'vllm' and m['is_healthy'])
            ollama_healthy = sum(1 for m in models_data if m['backend'] == 'ollama' and m['is_healthy'])
            
            response = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_models': len(models_data),
                'healthy_models': healthy_count,
                'unhealthy_models': len(models_data) - healthy_count,
                'vllm_healthy': vllm_healthy,
                'ollama_healthy': ollama_healthy,
                'models': models_data,
            }
            
            with _cache_lock:
                _health_cache = response
                _last_health_update = time.time()
            
            logger.debug(f"Health cache updated: {healthy_count}/{len(models_data)} healthy")
        except Exception as e:
            logger.error(f"Error updating health cache: {e}")
        
        time.sleep(HEALTH_CACHE_TTL)


# Start background health updater
_updater_thread = threading.Thread(target=update_health_cache, daemon=True)
_updater_thread.start()

# ==============================================================================
# API Routes
# ==============================================================================

# --- Root & Redirects ---

@app.get("/")
def root():
    """Redirect root to main interface"""
    return RedirectResponse(url="/index.html")


@app.get("/api")
def api_root() -> Dict[str, Any]:
    """API endpoint directory"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "endpoints": {
            "health": "/api/health",
            "status": "/api/status",
            "engines": "/api/engines",
            "processing": "/api/processing/stats",
            "gpu": "/api/gpu",
            "search": "/search?q=...",
            "scenes": "/api/scenes",
            "command_center": "/api/command-center"
        }
    }


# --- Health & Monitoring ---

@app.get("/api/health")
@app.head("/api/health")
def get_health() -> Dict[str, Any]:
    """Get cached health status for all LLM models"""
    try:
        with _cache_lock:
            if _health_cache and _last_health_update and (time.time() - _last_health_update) < 30:
                return _health_cache
        
        logger.warning("Health cache not ready")
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'total_models': 0,
            'healthy_models': 0,
            'unhealthy_models': 0,
            'models': [],
            'cache_status': 'initializing'
        }
    except Exception as e:
        logger.error(f"Error in get_health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health/summary")
def get_health_summary() -> Dict[str, Any]:
    """Get condensed health summary"""
    with _cache_lock:
        cache = _health_cache.copy() if _health_cache else {}
    
    return {
        "overall": {
            "total": cache.get("total_models", 0),
            "healthy": cache.get("healthy_models", 0),
            "unhealthy": cache.get("unhealthy_models", 0)
        },
        "vllm": {
            "healthy": cache.get("vllm_healthy", 0)
        },
        "ollama": {
            "healthy": cache.get("ollama_healthy", 0)
        },
        "timestamp": cache.get("timestamp", datetime.utcnow().isoformat())
    }


@app.get("/api/gpu")
def get_gpu() -> Dict[str, Any]:
    """Get GPU statistics"""
    return get_gpu_stats()


@app.get("/api/status")
@app.head("/api/status")
def get_status() -> Dict[str, Any]:
    """Aggregated system status"""
    gpu_data = get_gpu_stats()
    
    with _cache_lock:
        health = _health_cache.copy() if _health_cache else {}
    
    models_data = {
        "total": health.get("total_models", 0),
        "healthy": health.get("healthy_models", 0),
        "vllm_healthy": health.get("vllm_healthy", 0),
        "ollama_healthy": health.get("ollama_healthy", 0)
    }
    
    processing = get_processing_stats()
    
    return {
        "status": "active",
        "version": "2.0.0",
        "components": {
            "api": "running",
            "pipeline": processing["status"],
            "wsl_audio": "available"
        },
        "gpu": gpu_data,
        "models": models_data,
        "processing": {
            "status": processing["status"],
            "current_video": processing["current_video"]["name"],
            "progress_percent": processing["current_video"]["progress_percent"]
        }
    }


# --- Processing Stats ---

@app.get("/api/processing/stats")
def get_processing_stats_endpoint() -> Dict[str, Any]:
    """Get real-time processing statistics"""
    return get_processing_stats()


# --- Pipeline Engines ---

@app.get("/api/engines")
def get_engines() -> Dict[str, Any]:
    """Get pipeline engine status"""
    engines = {}
    
    # vLLM check (port 38005)
    try:
        import requests
        resp = requests.get("http://localhost:38005/v1/models", timeout=2)
        if resp.status_code == 200:
            engines["vllm_llama1b"] = {
                "name": "vLLM Llama-1B",
                "category": "LLM Inference",
                "description": "Llama 1B Speed model on port 38005",
                "status": "ready",
                "gpu": True,
                "port": 38005
            }
        else:
            raise Exception("unhealthy")
    except:
        engines["vllm_llama1b"] = {
            "name": "vLLM Llama-1B",
            "category": "LLM Inference",
            "description": "Not running",
            "status": "unavailable",
            "gpu": True,
            "port": 38005
        }
    
    # Ollama check
    try:
        import requests
        resp = requests.get("http://localhost:11434/v1/models", timeout=2)
        if resp.status_code == 200:
            engines["ollama"] = {
                "name": "Ollama",
                "category": "LLM Inference",
                "description": "Phi4 on port 11434",
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
            "description": "Not running",
            "status": "unavailable",
            "gpu": True,
            "port": 11434
        }
    
    # WSL audio
    wsl_available = shutil.which("wsl") is not None
    engines["wsl_audio"] = {
        "name": "WSL Audio Transcription",
        "category": "Audio Processing",
        "description": "Faster-Whisper with speaker diarization",
        "status": "ready" if wsl_available else "unavailable",
        "gpu": True
    }
    
    # FFmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    engines["ffmpeg"] = {
        "name": "FFmpeg",
        "category": "Video Processing",
        "description": f"Path: {ffmpeg_path}" if ffmpeg_path else "Not found",
        "status": "ready" if ffmpeg_path else "unavailable",
        "gpu": False
    }
    
    # Python pipeline
    engines["python_pipeline"] = {
        "name": "Python Pipeline",
        "category": "Orchestration",
        "description": f"Python {sys.version.split()[0]}",
        "status": "ready",
        "gpu": False
    }
    
    # Scene detection
    try:
        from scenedetect import detect
        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "PySceneDetect",
            "status": "ready",
            "gpu": False
        }
    except:
        engines["scene_detection"] = {
            "name": "Scene Detection",
            "category": "Video Analysis",
            "description": "Not available",
            "status": "unavailable",
            "gpu": False
        }
    
    # Vector DB
    engines["vector_db"] = {
        "name": "Vector Database",
        "category": "Search & Retrieval",
        "description": f"ChromaDB at {CHROMA_DIR}",
        "status": "ready" if CHROMA_DIR.exists() else "unavailable",
        "gpu": False
    }
    
    # Audio diarization
    engines["audio_diarization"] = {
        "name": "Audio Diarization",
        "category": "Audio Processing",
        "description": "Pyannote speaker separation with OSD",
        "status": "ready",
        "gpu": True
    }
    
    return engines


@app.get("/api/pipeline-engines")
def get_pipeline_engines() -> Dict[str, Any]:
    """Alias for /api/engines"""
    return get_engines()


# --- Command Center ---

@app.get("/api/command-center")
def get_command_center() -> Dict[str, Any]:
    """Command center dashboard data"""
    return {
        "system": get_status(),
        "engines": get_engines(),
        "processing": get_processing_stats(),
        "gpu": get_gpu_stats()
    }


# --- Search & Retrieval ---

@app.get("/search")
def search(q: str = Query(..., description="Search text"), topk: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Text search endpoint"""
    try:
        from steps.cli.retrieve import search_text_index
        results = search_text_index(q, topk=topk)
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"results": [], "error": str(e)}


@app.get("/api/scenes")
def get_scenes(limit: int = Query(20, ge=1, le=1000), offset: int = Query(0, ge=0)) -> Dict[str, Any]:
    """Get processed scenes"""
    return {
        "scenes": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "message": "Scene retrieval not yet implemented"
    }


@app.get("/api/entities")
def get_entities(limit: int = Query(500, ge=1, le=10000)) -> Dict[str, Any]:
    """Get knowledge graph entities"""
    return {
        "entities": [],
        "total": 0,
        "limit": limit,
        "message": "Entity retrieval not yet implemented"
    }


@app.get("/api/analytics/knowledge-graph")
def get_knowledge_graph_analytics() -> Dict[str, Any]:
    """Get knowledge graph analytics"""
    return {
        "total_entities": 0,
        "total_relationships": 0,
        "entity_types": {},
        "message": "Knowledge graph not yet populated"
    }


# --- Placeholder Routes ---

@app.get("/api/processes")
def get_processes() -> List[Dict[str, Any]]:
    """Get running processes"""
    return []


@app.get("/api/progress")
def get_progress() -> Dict[str, Any]:
    """Get processing progress"""
    return get_processing_stats()


@app.get("/api/wsl2-status")
def get_wsl2_status() -> Dict[str, Any]:
    """Get WSL2 status"""
    wsl_available = shutil.which("wsl") is not None
    return {
        "available": wsl_available,
        "status": "ready" if wsl_available else "unavailable"
    }


# ==============================================================================
# UI Serving (must be last)
# ==============================================================================

if UI_DIR.exists():
    logger.info(f"Mounting UI from {UI_DIR}")
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
else:
    logger.warning(f"UI directory not found: {UI_DIR}")


# ==============================================================================
# Server Startup
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 80)
    logger.info("🚀 GoodQ4All Unified API Server Starting...")
    logger.info("=" * 80)
    logger.info(f"📡 Port: 30000")
    logger.info(f"🎨 UI Directory: {UI_DIR}")
    logger.info(f"💾 Data Directory: L:/_DATA/GoodQ_Data")
    logger.info("=" * 80)
    
    uvicorn.run(
        "main_unified:app",
        host="0.0.0.0",
        port=30000,
        reload=True,
        reload_dirs=["L:/goodq4all/api"]
    )
