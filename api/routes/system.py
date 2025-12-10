"""
System API routes for GoodQ4All.
Provides system status, control, and management endpoints.
"""
from __future__ import annotations
from typing import List
import logging
import os
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from pathlib import Path

from api.utils.response_models import SystemStatus, IngestRequest, IngestResponse, VideoListItem
from api.utils.loaders import DataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

_data_loader = None


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized for system")
    
    return _data_loader


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    Get current system status.
    
    Returns:
        System health and statistics
    """
    try:
        loader = get_data_loader()
        
        # Check if goodq_core environment is available
        goodq_core_available = False
        try:
            result = subprocess.run(
                ['conda', 'run', '-n', 'goodq_core', 'python', '-c', 'print("OK")'],
                capture_output=True,
                text=True,
                timeout=5
            )
            goodq_core_available = (result.returncode == 0)
        except Exception:
            pass
        
        # Check Qdrant availability
        qdrant_available = False
        try:
            import requests
            resp = requests.get('http://localhost:6333/collections', timeout=2)
            qdrant_available = (resp.status_code == 200)
        except Exception:
            pass
        
        # Count processed videos
        video_ids = loader.list_processed_videos()
        total_videos = len(video_ids)
        
        # Count total scenes
        total_scenes = 0
        for video_id in video_ids:
            metadata = loader.get_video_metadata(video_id)
            total_scenes += metadata.get('total_scenes', 0)
        
        return SystemStatus(
            status="healthy" if goodq_core_available else "degraded",
            goodq_core_available=goodq_core_available,
            qdrant_available=qdrant_available,
            total_videos_processed=total_videos,
            total_scenes_indexed=total_scenes,
            indexes={
                'goodq_text': 'active' if qdrant_available else 'unknown',
                'goodq_clip_scenes': 'active' if qdrant_available else 'unknown',
                'goodq_dino_scenes': 'active' if qdrant_available else 'unknown'
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/videos", response_model=List[VideoListItem])
async def list_videos():
    """
    List all processed videos.
    
    Returns:
        List of videos with basic metadata
    """
    try:
        loader = get_data_loader()
        video_ids = loader.list_processed_videos()
        
        videos = []
        for video_id in video_ids:
            metadata = loader.get_video_metadata(video_id)
            
            # Get thumbnail (representative frame from first scene)
            thumbnail = None
            temporal_index = loader.load_temporal_index(video_id)
            if temporal_index and temporal_index.get('segments'):
                first_segment = temporal_index['segments'][0]
                thumbnail = first_segment.get('representative_frame')
            
            video_item = VideoListItem(
                video_id=video_id,
                title=video_id,  # TODO: Extract actual title from metadata
                duration=metadata.get('duration'),
                total_scenes=metadata.get('total_scenes'),
                processed_date=None,  # TODO: Extract from file timestamp
                thumbnail=thumbnail
            )
            videos.append(video_item)
        
        return videos
        
    except Exception as e:
        logger.error(f"Failed to list videos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {str(e)}")


@router.post("/ingest", response_model=IngestResponse)
async def start_ingest(request: IngestRequest = Body(...)):
    """
    Start ingestion of a new file.
    
    Args:
        request: Ingest request with file path and options
        
    Returns:
        Ingest job ID and status
    """
    try:
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # TODO: Implement actual ingest job queue
        # For now, return placeholder response
        
        job_id = f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Ingest request received: {file_path} -> Job ID: {job_id}")
        
        return IngestResponse(
            job_id=job_id,
            status="queued",
            message=f"Ingestion queued for: {file_path.name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start ingest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start ingest: {str(e)}")


@router.post("/reindex")
async def rebuild_indexes():
    """
    Rebuild all vector indexes.
    
    Returns:
        Success message
    """
    try:
        # TODO: Implement actual index rebuild
        logger.warning("Index rebuild requested but not yet implemented")
        
        return {"status": "success", "message": "Index rebuild not yet implemented"}
        
    except Exception as e:
        logger.error(f"Failed to rebuild indexes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to rebuild indexes: {str(e)}")


@router.post("/reload")
async def reload_config():
    """
    Reload system configuration.
    
    Returns:
        Success message
    """
    try:
        # TODO: Implement config reload
        logger.info("Config reload requested")
        
        return {"status": "success", "message": "Config reload not yet implemented"}
        
    except Exception as e:
        logger.error(f"Failed to reload config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")
