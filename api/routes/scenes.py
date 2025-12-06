"""
Scene API routes for GoodQ4All.
Provides access to scene-level data and metadata.
"""
from __future__ import annotations
from typing import List
import logging
from fastapi import APIRouter, HTTPException, Path as PathParam, Query

from api.utils.response_models import SceneResponse
from api.utils.loaders import DataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos/{video_id}/scenes", tags=["scenes"])

_data_loader = None


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("✅ Data loader initialized for scenes")
    
    return _data_loader


@router.get("", response_model=List[SceneResponse])
async def list_scenes(
    video_id: str = PathParam(..., description="Video identifier")
):
    """
    List all scenes for a video.
    
    Args:
        video_id: Video identifier
        
    Returns:
        List of scenes with metadata
    """
    try:
        loader = get_data_loader()
        temporal_index = loader.load_temporal_index(video_id)
        
        if not temporal_index:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        
        scenes = []
        for segment in temporal_index.get('segments', []):
            scene = SceneResponse(
                scene_id=segment.get('scene_id', 0),
                start=segment.get('start', 0.0),
                end=segment.get('end', 0.0),
                duration=segment.get('end', 0.0) - segment.get('start', 0.0),
                representative_frame=segment.get('representative_frame'),
                frame_paths=segment.get('frame_paths', []),
                clip_id=segment.get('clip_id'),
                dino_id=segment.get('dino_id'),
                keywords=segment.get('keywords', []),
                objects=segment.get('objects', []),
                transcript=segment.get('full_transcript'),
                speakers=segment.get('speaker_ids', []),
                audio_chunks=segment.get('audio_chunks', [])
            )
            scenes.append(scene)
        
        return scenes
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list scenes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list scenes: {str(e)}")


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(
    video_id: str = PathParam(..., description="Video identifier"),
    scene_id: int = PathParam(..., description="Scene identifier")
):
    """
    Get detailed metadata for a specific scene.
    
    Args:
        video_id: Video identifier
        scene_id: Scene identifier
        
    Returns:
        Complete scene metadata
    """
    try:
        loader = get_data_loader()
        temporal_index = loader.load_temporal_index(video_id)
        
        if not temporal_index:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        
        # Find the scene
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                scene = SceneResponse(
                    scene_id=segment.get('scene_id', 0),
                    start=segment.get('start', 0.0),
                    end=segment.get('end', 0.0),
                    duration=segment.get('end', 0.0) - segment.get('start', 0.0),
                    representative_frame=segment.get('representative_frame'),
                    frame_paths=segment.get('frame_paths', []),
                    clip_id=segment.get('clip_id'),
                    dino_id=segment.get('dino_id'),
                    keywords=segment.get('keywords', []),
                    objects=segment.get('objects', []),
                    transcript=segment.get('full_transcript'),
                    speakers=segment.get('speaker_ids', []),
                    audio_chunks=segment.get('audio_chunks', [])
                )
                return scene
        
        raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scene: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get scene: {str(e)}")


@router.get("/{scene_id}/similar", response_model=List[SceneResponse])
async def find_similar_scenes(
    video_id: str = PathParam(..., description="Video identifier"),
    scene_id: int = PathParam(..., description="Scene identifier"),
    top_k: int = Query(5, description="Number of similar scenes to return")
):
    """
    Find scenes visually similar to the specified scene.
    
    Args:
        video_id: Video identifier
        scene_id: Scene identifier
        top_k: Number of similar scenes to return
        
    Returns:
        List of similar scenes
    """
    try:
        loader = get_data_loader()
        temporal_index = loader.load_temporal_index(video_id)
        
        if not temporal_index:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        
        # Find the source scene
        source_clip_id = None
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                source_clip_id = segment.get('clip_id')
                break
        
        if not source_clip_id:
            raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")
        
        # TODO: Implement actual similarity search using Qdrant
        # For now, return placeholder response
        logger.warning("Similar scene search not yet fully implemented - returning empty list")
        
        return []
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find similar scenes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find similar scenes: {str(e)}")
