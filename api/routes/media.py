"""
Media API routes for GoodQ4All.
Serves frames, audio chunks, and other media files.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Path as PathParam
from fastapi.responses import FileResponse
from pathlib import Path

from api.utils.loaders import DataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

_data_loader = None


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized for media")
    
    return _data_loader


@router.get("/video/{video_id}/scene/{scene_id}/frame/{frame_index}")
async def get_scene_frame(
    video_id: str = PathParam(..., description="Video identifier"),
    scene_id: int = PathParam(..., description="Scene identifier"),
    frame_index: int = PathParam(..., description="Frame index (0 for representative)")
):
    """
    Retrieve a specific frame from a scene.
    
    Args:
        video_id: Video identifier
        scene_id: Scene identifier
        frame_index: Frame index within scene (0 = representative frame)
        
    Returns:
        JPEG image file
    """
    try:
        loader = get_data_loader()
        frame_path = loader.get_frame_path(video_id, scene_id, frame_index)
        
        if not frame_path or not frame_path.exists():
            raise HTTPException(status_code=404, detail="Frame not found")
        
        # Security: Ensure path doesn't escape data directory
        if not str(frame_path).startswith(str(loader.data_root)):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(
            path=str(frame_path),
            media_type="image/jpeg",
            filename=frame_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve frame: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to serve frame: {str(e)}")


@router.get("/audio/{video_id}/{chunk_id}.wav")
async def get_audio_chunk(
    video_id: str = PathParam(..., description="Video identifier"),
    chunk_id: int = PathParam(..., description="Audio chunk identifier")
):
    """
    Retrieve a specific audio chunk.
    
    Args:
        video_id: Video identifier
        chunk_id: Chunk identifier
        
    Returns:
        WAV audio file
    """
    try:
        loader = get_data_loader()
        chunk_path = loader.get_audio_chunk_path(video_id, chunk_id)
        
        if not chunk_path or not chunk_path.exists():
            raise HTTPException(status_code=404, detail="Audio chunk not found")
        
        # Security: Ensure path doesn't escape data directory
        if not str(chunk_path).startswith(str(loader.data_root)):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(
            path=str(chunk_path),
            media_type="audio/wav",
            filename=chunk_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve audio chunk: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to serve audio chunk: {str(e)}")


@router.get("/video/{video_id}/frame/{frame_name}")
async def get_frame_by_name(
    video_id: str = PathParam(..., description="Video identifier"),
    frame_name: str = PathParam(..., description="Frame filename")
):
    """
    Retrieve a frame by filename.
    
    Args:
        video_id: Video identifier
        frame_name: Frame filename (e.g., "frame_0001.jpg")
        
    Returns:
        JPEG image file
    """
    try:
        loader = get_data_loader()
        
        # Construct frame path
        frame_path = loader.processing_dir / video_id / "video" / "frames" / frame_name
        
        if not frame_path.exists():
            # Try completed directory
            frame_path = loader.completed_dir / video_id / "video" / "frames" / frame_name
        
        if not frame_path.exists():
            raise HTTPException(status_code=404, detail="Frame not found")
        
        # Security: Ensure path doesn't escape data directory and filename is safe
        if not str(frame_path).startswith(str(loader.data_root)):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if ".." in frame_name or "/" in frame_name or "\\" in frame_name:
            raise HTTPException(status_code=403, detail="Invalid filename")
        
        return FileResponse(
            path=str(frame_path),
            media_type="image/jpeg",
            filename=frame_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve frame: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to serve frame: {str(e)}")
