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
from retrieval.multimodal_search import MultimodalSearchEngine
from steps.common.config_loader import load_configs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos/{video_id}/scenes", tags=["scenes"])

_data_loader = None
_search_engine = None
_config = None


def _segment_object_labels(segment: dict) -> List[str]:
    """Normalize persisted object payloads into plain labels for API responses."""
    labels = segment.get("objects")
    if isinstance(labels, list) and labels:
        return [str(label) for label in labels if label]

    detected_objects = segment.get("detected_objects")
    if isinstance(detected_objects, list):
        extracted = []
        for obj in detected_objects:
            if isinstance(obj, dict):
                label = obj.get("label")
                if label:
                    extracted.append(str(label))
        return extracted

    return []


def _build_scene_response(segment: dict) -> SceneResponse:
    """Project one persisted timeline segment into the stable scene API contract."""
    start = segment.get("start", 0.0)
    end = segment.get("end", 0.0)
    return SceneResponse(
        scene_id=segment.get("scene_id", 0),
        start=start,
        end=end,
        duration=segment.get("duration", end - start),
        representative_frame=segment.get("representative_frame"),
        frame_paths=segment.get("frame_paths", []),
        clip_id=segment.get("clip_id"),
        dino_id=segment.get("dino_id"),
        keywords=segment.get("keywords", []),
        objects=_segment_object_labels(segment),
        transcript=segment.get("full_transcript"),
        speakers=segment.get("speaker_ids", []),
        audio_chunks=segment.get("audio_chunks", []),
        speaker_count=segment.get("speaker_count"),
        dominant_speaker_id=segment.get("dominant_speaker_id"),
        continuity_key=segment.get("continuity_key"),
        diarization_status=segment.get("diarization_status"),
        emotion_status=segment.get("emotion_status"),
        speaker_voice_signature_count=segment.get("speaker_voice_signature_count"),
        speaker_voice_signature_meta=segment.get("speaker_voice_signature_meta"),
        audio_emotion=segment.get("audio_emotion"),
        sentiment=segment.get("sentiment"),
        sentiment_label=segment.get("sentiment_label"),
        sentiment_score=segment.get("sentiment_score"),
        time_hints=segment.get("time_hints"),
        content_state=segment.get("content_state"),
        candidate_visible_people=segment.get("candidate_visible_people", []),
        speaker_aligned_mentions=segment.get("speaker_aligned_mentions", []),
        interaction_dominance=segment.get("interaction_dominance"),
        conversation_owner=segment.get("conversation_owner"),
    )


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized for scenes")
    
    return _data_loader


def get_search_engine():
    """Lazy-load multimodal search engine."""
    global _search_engine, _config

    if _search_engine is None:
        _config = load_configs({})
        _search_engine = MultimodalSearchEngine(_config)
        logger.info("[OK] Search engine initialized for similar scenes")

    return _search_engine


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
            scenes.append(_build_scene_response(segment))
        
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
                return _build_scene_response(segment)
        
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
    Find semantically similar scenes using persisted multimodal scene memory.
    
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
        
        # Confirm the source scene exists before delegating to retrieval.
        source_segment = None
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                source_segment = segment
                break
        
        if not source_segment:
            raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")

        engine = get_search_engine()
        similar_results = engine.search_similar_scene(video_id=video_id, scene_id=scene_id, top_k=top_k)

        scenes = []
        for result in similar_results:
            scene_context = result.get("scene_context") if isinstance(result.get("scene_context"), dict) else None
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else None
            scene_payload = scene_context or payload
            if not isinstance(scene_payload, dict):
                continue
            scenes.append(_build_scene_response(scene_payload))

        return scenes
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find similar scenes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find similar scenes: {str(e)}")
