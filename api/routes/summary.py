"""
Summary API routes for GoodQ4All.
Provides dashboard, entity profile aggregation, and custom collections.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Path as PathParam, Body, BackgroundTasks
import asyncio

from api.utils.response_models import (
    SummaryDashboardResponse,
    EntityProfileResponse,
    SavedCollectionItem,
    SaveCollectionRequest,
    SaveCollectionResponse
)
from api.utils.loaders import DataLoader
from lib import summary_aggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])

_data_loader = None


def get_data_loader() -> DataLoader:
    """Lazy-load data loader."""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader


def _get_kg_db_path() -> Path:
    from steps.common.config_loader import load_configs
    cfg = load_configs({})
    return Path(cfg.get("paths", {}).get("knowledge_graph_db", "data/knowledge_graph.db"))


@router.get("/dashboard", response_model=SummaryDashboardResponse)
async def get_dashboard():
    """
    Get consolidated dashboard metrics across all ingested videos/scenes.
    """
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")
        
    try:
        loader = get_data_loader()
        data = summary_aggregator.get_summary_dashboard(db_path, loader)
        return data
    except Exception as e:
        logger.error(f"Failed to compile dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id:path}", response_model=EntityProfileResponse)
async def get_entity_profile(
    entity_id: str = PathParam(..., description="Stable entity identifier (e.g. 'person:Joe')")
):
    """
    Get detailed metrics, co-occurrences, and media timelines for a major entity.
    """
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")
        
    try:
        loader = get_data_loader()
        data = summary_aggregator.get_entity_profile(db_path, loader, entity_id)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to compile profile for {entity_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections", response_model=List[SavedCollectionItem])
async def list_collections():
    """
    List all active operator-saved collections.
    """
    db_path = _get_kg_db_path()
    try:
        data = summary_aggregator.load_collections(db_path)
        collections = data.get("collections") or []
        # Filter out deleted collections
        active_collections = [col for col in collections if col.get("status") == "active"]
        return active_collections
    except Exception as e:
        logger.error(f"Failed to list collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections", response_model=SaveCollectionResponse)
async def create_collection(request: SaveCollectionRequest = Body(...)):
    """
    Create a new manual playlist highlight collection.
    """
    db_path = _get_kg_db_path()
    try:
        req_dict = request.dict()
        new_col = summary_aggregator.add_collection(db_path, req_dict)
        return SaveCollectionResponse(
            success=True,
            message=f"Collection '{request.name}' successfully created.",
            collection=new_col
        )
    except Exception as e:
        logger.error(f"Failed to create collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: str = PathParam(..., description="Unique ID of the collection to soft-delete")
):
    """
    Soft-delete a custom collection.
    """
    db_path = _get_kg_db_path()
    try:
        success = summary_aggregator.soft_delete_collection(db_path, collection_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Active collection not found for ID: {collection_id}")
        return {"success": True, "message": f"Collection '{collection_id}' was soft-deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Concurrency Control & Duplicate-run Protection
_running_summarizations = set()
_summarization_lock = asyncio.Lock()


async def _generate_summary_worker(video_hash: str, cfg: dict):
    try:
        from steps.video_summarizer.step import run_step as run_video_summarizer
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_video_summarizer, cfg, video_hash)
    except Exception as e:
        logger.error(f"Background summary worker failed for video {video_hash}: {e}", exc_info=True)
    finally:
        async with _summarization_lock:
            _running_summarizations.discard(video_hash)


@router.get("/capabilities", response_model=dict)
async def get_summary_capabilities():
    """
    Get summary capabilities (e.g. whether LLM features are enabled).
    """
    try:
        from steps.common.config_loader import load_configs
        cfg = load_configs({})
        use_llm = cfg.get('llm', {}).get('features', {}).get('video_summarization', True)
        return {"video_summarization_enabled": bool(use_llm)}
    except Exception as e:
        logger.error(f"Failed to check capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch capabilities")


@router.get("/video/{video_hash}", response_model=dict)
async def get_video_summary(
    video_hash: str = PathParam(..., description="Target video hash")
):
    """
    Get the persisted narrative summary and provenance for a video hash.
    """
    import re
    import sqlite3
    import json
    
    if not video_hash or not re.match(r"^[a-fA-F0-9]{8,64}$", video_hash):
        raise HTTPException(status_code=400, detail="Invalid video hash format")
        
    from steps.common.config_loader import load_configs
    cfg = load_configs({})
    db_path = Path(cfg.get("paths", {}).get("db_path", "data/memory.db"))
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not initialized")
        
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'")
        if not cursor.fetchone():
            conn.close()
            return _check_kg_existence_fallback(video_hash)
            
        cursor.execute("SELECT content, created_at FROM summaries WHERE summary_type='video' AND category='video_summary'")
        rows = cursor.fetchall()
        conn.close()
        
        for content_json, created_at in rows:
            try:
                data = json.loads(content_json)
                if data.get("video_hash") == video_hash:
                    return {
                        "video_hash": video_hash,
                        "summary": data.get("summary", ""),
                        "method": data.get("method", "template"),
                        "provenance": data.get("provenance", {}),
                        "created_at": created_at
                    }
            except Exception:
                continue
                
        return _check_kg_existence_fallback(video_hash)
        
    except sqlite3.Error as se:
        logger.error(f"Database query error: {se}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database query failed")


def _check_kg_existence_fallback(video_hash: str) -> dict:
    import sqlite3
    kg_path = _get_kg_db_path()
    if kg_path.exists():
        try:
            conn_kg = sqlite3.connect(str(kg_path))
            row_kg = conn_kg.execute("SELECT 1 FROM scenes WHERE video_hash=? LIMIT 1", (video_hash,)).fetchone()
            conn_kg.close()
            if row_kg:
                return {
                    "video_hash": video_hash,
                    "summary": "Summary not yet generated for this video.",
                    "method": "none",
                    "provenance": {},
                    "created_at": None
                }
        except Exception as e:
            logger.warning(f"Failed to query KG fallback for existence: {e}")
            
    raise HTTPException(status_code=404, detail="Video summary not found")


@router.get("/video/{video_hash}/status", response_model=dict)
async def get_summary_status(
    video_hash: str = PathParam(..., description="Target video hash to check status")
):
    """
    Check if a summary task is currently running for this video hash.
    """
    import re
    if not video_hash or not re.match(r"^[a-fA-F0-9]{8,64}$", video_hash):
        raise HTTPException(status_code=400, detail="Invalid video hash format")
    async with _summarization_lock:
        status = "running" if video_hash in _running_summarizations else "idle"
    return {"status": status}


@router.post("/video/{video_hash}/generate", response_model=dict)
async def generate_video_summary(
    background_tasks: BackgroundTasks,
    video_hash: str = PathParam(..., description="Target video hash to summarize")
):
    """
    Trigger async generation/regeneration of video LLM summary with full audits and checks.
    """
    import re
    import sqlite3
    import requests
    from steps.common.config_loader import load_configs

    # 1. Input Validation
    if not video_hash or not re.match(r"^[a-fA-F0-9]{8,64}$", video_hash):
        raise HTTPException(status_code=400, detail="Invalid video hash format")

    # 2. Database Existence Check
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not initialized")

    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT 1 FROM scenes WHERE video_hash=? LIMIT 1", (video_hash,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"Video hash '{video_hash}' not found in database")
    except sqlite3.Error as se:
        logger.error(f"Database query error during video existence check: {se}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database query failed")

    # 3. LLM Pre-flight Connectivity Check
    cfg = load_configs({})
    use_llm = cfg.get('llm', {}).get('features', {}).get('video_summarization', True)
    if use_llm:
        llm_config = cfg.get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        try:
            base_url = api_url.rsplit("/chat/completions", 1)[0]
            # Simple GET probe to /models or base endpoint to verify responsiveness
            resp = requests.get(f"{base_url}/models", timeout=1.5)
        except Exception as le:
            logger.warning(f"LLM API pre-flight check failed for url={api_url}: {le}")
            raise HTTPException(status_code=503, detail="LLM service is offline or unreachable")

    # 4. Duplicate-Run Protection
    async with _summarization_lock:
        if video_hash in _running_summarizations:
            raise HTTPException(status_code=409, detail="A summarization task is already running for this video")
        _running_summarizations.add(video_hash)

    # 5. Queue Background Task
    background_tasks.add_task(_generate_summary_worker, video_hash, cfg)
    return {"success": True, "message": "Video summarization task successfully started"}
