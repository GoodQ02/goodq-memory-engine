from __future__ import annotations
from typing import Any, Dict

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Any, Dict
from pydantic import BaseModel

app = FastAPI(title="GoodQ Retrieval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search")
def search(q: str = Query(..., description="Search text"), topk: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    # Import lazily so the process starts fast and errors show clearly
    from steps.cli.retrieve import search_text_index

    results = search_text_index(q, topk=topk)
    return results


# Optional root
@app.get("/")
def root() -> Dict[str, Any]:
    return {"status": "ok", "endpoints": ["/search?q=...", "/api/status", "/api/engines", "/api/scenes", "/api/knowledge_graph"]}


@app.get("/api/status")
def get_status() -> Dict[str, Any]:
    """System status endpoint"""
    return {
        "status": "active",
        "version": "1.4.0",
        "components": {
            "api": "running",
            "pipeline": "ready",
            "wsl_audio": "available"
        }
    }


@app.get("/api/engines")
def get_engines() -> Dict[str, Any]:
    """Get pipeline engine status"""
    import subprocess
    import shutil
    
    engines = []
    
    # Check WSL audio processing
    wsl_script = r"~/goodq_audio/scripts/process.sh"
    wsl_available = shutil.which("wsl") is not None
    
    engines.append({
        "name": "WSL Audio Transcription",
        "type": "transcription",
        "status": "ready" if wsl_available else "unavailable",
        "gpu": True,
        "details": "Faster-Whisper with speaker diarization"
    })
    
    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    engines.append({
        "name": "FFmpeg",
        "type": "video_processing",
        "status": "ready" if ffmpeg_path else "unavailable",
        "gpu": False,
        "details": f"Path: {ffmpeg_path}" if ffmpeg_path else "Not found"
    })
    
    # Check Python environment
    engines.append({
        "name": "Python Pipeline",
        "type": "orchestration",
        "status": "ready",
        "gpu": False,
        "details": f"Python {sys.version.split()[0]}"
    })
    
    # Check LLM (if LMStudio is running)
    try:
        import requests
        resp = requests.get("http://localhost:1234/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            engines.append({
                "name": "LMStudio",
                "type": "llm",
                "status": "ready",
                "gpu": True,
                "details": f"{len(models)} models loaded"
            })
    except:
        engines.append({
            "name": "LMStudio",
            "type": "llm",
            "status": "unavailable",
            "gpu": True,
            "details": "Not running or unreachable"
        })
    
    return {"engines": engines}


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
    persist_dir = paths.get("chroma_dir") or os.path.join(os.getcwd(), "chroma")

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


@app.post("/api/chat/control-agent")
def chat_with_control_agent(request: ChatRequest) -> Dict[str, Any]:
    """Chat with the Control Agent for pipeline diagnostics and help"""
    try:
        # Import Control Agent
        from agents.control_agent import ControlAgent
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
        response = llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return {
            "success": True,
            "response": response,
            "model": llm.get_active_model(),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response": "Control Agent is currently unavailable. Please check that vLLM or Ollama is running."
        }
