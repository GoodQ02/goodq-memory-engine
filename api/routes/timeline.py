"""
Timeline API routes for GoodQ4All.
Provides unified temporal index access.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Path as PathParam

from api.utils.response_models import TimelineResponse, TimelineSegment
from api.utils.loaders import DataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos/{video_id}/timeline", tags=["timeline"])

_data_loader = None


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("✅ Data loader initialized for timeline")
    
    return _data_loader


@router.get("", response_model=TimelineResponse)
async def get_timeline(
    video_id: str = PathParam(..., description="Video identifier")
):
    """
    Get unified timeline for a video (summary version).
    
    Args:
        video_id: Video identifier
        
    Returns:
        Timeline with basic segment information
    """
    try:
        loader = get_data_loader()
        temporal_index = loader.load_temporal_index(video_id)
        
        if not temporal_index:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        
        segments = []
        for seg in temporal_index.get('segments', []):
            segment = TimelineSegment(
                segment_id=seg.get('segment_id', 0),
                start=seg.get('start', 0.0),
                end=seg.get('end', 0.0),
                scene_id=seg.get('scene_id'),
                audio_chunks=seg.get('audio_chunks', []),
                speaker_ids=seg.get('speaker_ids', []),
                transcript=seg.get('full_transcript', '')[:200] + '...' if len(seg.get('full_transcript', '')) > 200 else seg.get('full_transcript'),
                keywords=seg.get('keywords', [])[:5],  # Limit keywords
                objects=seg.get('objects', [])[:5],  # Limit objects
                clip_id=seg.get('clip_id'),
                dino_id=seg.get('dino_id'),
                representative_frame=seg.get('representative_frame')
            )
            segments.append(segment)
        
        return TimelineResponse(
            video_id=video_id,
            duration=temporal_index.get('duration', 0.0),
            total_scenes=len(set(seg.get('scene_id') for seg in temporal_index.get('segments', []) if seg.get('scene_id') is not None)),
            total_segments=len(segments),
            segments=segments,
            metadata={
                'phase6_complete': temporal_index.get('phase6_complete', False),
                'phase6_harmonized': temporal_index.get('phase6_harmonized', False)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get timeline: {str(e)}")


@router.get("/full", response_model=TimelineResponse)
async def get_full_timeline(
    video_id: str = PathParam(..., description="Video identifier")
):
    """
    Get complete unified timeline for a video (full version with all data).
    
    Args:
        video_id: Video identifier
        
    Returns:
        Complete timeline with all segment details
    """
    try:
        loader = get_data_loader()
        temporal_index = loader.load_temporal_index(video_id)
        
        if not temporal_index:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        
        segments = []
        for seg in temporal_index.get('segments', []):
            segment = TimelineSegment(
                segment_id=seg.get('segment_id', 0),
                start=seg.get('start', 0.0),
                end=seg.get('end', 0.0),
                scene_id=seg.get('scene_id'),
                audio_chunks=seg.get('audio_chunks', []),
                speaker_ids=seg.get('speaker_ids', []),
                transcript=seg.get('full_transcript'),
                keywords=seg.get('keywords', []),
                objects=seg.get('objects', []),
                clip_id=seg.get('clip_id'),
                dino_id=seg.get('dino_id'),
                representative_frame=seg.get('representative_frame')
            )
            segments.append(segment)
        
        return TimelineResponse(
            video_id=video_id,
            duration=temporal_index.get('duration', 0.0),
            total_scenes=len(set(seg.get('scene_id') for seg in temporal_index.get('segments', []) if seg.get('scene_id') is not None)),
            total_segments=len(segments),
            segments=segments,
            metadata={
                'phase6_complete': temporal_index.get('phase6_complete', False),
                'phase6_harmonized': temporal_index.get('phase6_harmonized', False),
                'version': temporal_index.get('version', 1)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get full timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get full timeline: {str(e)}")
