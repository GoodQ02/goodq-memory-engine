"""
Scene API routes for GoodQ4All.
Provides access to scene-level data and metadata.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote
import logging
from fastapi import APIRouter, HTTPException, Path as PathParam, Query
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from api.utils.audio_evidence import public_audio_evidence, review_media

from api.utils.response_models import SceneResponse
from api.utils.scene_relationships import load_scene_relationships
from api.utils.loaders import DataLoader, source_media_type
from api.utils.media_projection import (
    document_meta_projection,
    frame_paths_projection,
    representative_frame_projection,
    sanitize_detected_objects,
    sanitize_visual_meta,
    sanitize_visual_observations,
)
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


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(item)
        elif isinstance(item, str) and item.strip():
            rows.append({"text": item.strip()})
    return rows


def _scene_sentiment_payload(segment: dict) -> tuple[dict | None, str | None]:
    sentiment = segment.get("sentiment")
    sentiment_payload = sentiment if isinstance(sentiment, dict) else None
    sentiment_label = segment.get("sentiment_label")
    if sentiment_label is None and isinstance(sentiment, str) and sentiment.strip():
        sentiment_label = sentiment.strip()
    if sentiment_label is None and isinstance(sentiment_payload, dict):
        label = sentiment_payload.get("label")
        if isinstance(label, str) and label.strip():
            sentiment_label = label.strip()
    return sentiment_payload, sentiment_label


def _find_temporal_segment(temporal_index: dict, scene_id: object) -> dict | None:
    for segment in temporal_index.get("segments", []):
        if isinstance(segment, dict) and str(segment.get("scene_id")) == str(scene_id):
            return segment
    return None


def _build_scene_response(video_id: str, segment: dict, *, original_audio_available: bool = False,
                          original_video_available: bool = False, original_source_path=None,
                          source_kind: str = "video") -> SceneResponse:
    """Project one persisted timeline segment into the stable scene API contract."""
    start = segment.get("start", 0.0)
    end = segment.get("end", 0.0)
    source_kind = segment.get("source_kind") or source_kind
    source_available = original_source_path is not None or original_video_available
    source_endpoint = f"/api/media/video/{quote(video_id, safe='')}/source" if source_available else None
    original_video_available = source_available and source_kind == "video"
    frame_projection = representative_frame_projection(video_id, segment.get("representative_frame"))
    if source_kind == "image" and source_endpoint:
        frame_projection = {
            "representative_frame": source_endpoint, "representative_frame_endpoint": source_endpoint,
            "representative_frame_available": True, "representative_frame_path_redacted": False,
        }
    frame_paths = frame_paths_projection(video_id, segment.get("frame_paths", []))
    sentiment_payload, sentiment_label = _scene_sentiment_payload(segment)
    return SceneResponse(
        video_id=video_id,
        source_kind=source_kind,
        document_text=segment.get("document_text"),
        document_meta=document_meta_projection(segment.get("document_meta")),
        original_source_available=source_available,
        original_source_endpoint=source_endpoint,
        original_source_media_type=source_media_type(original_source_path) if original_source_path is not None else None,
        scene_id=segment.get("scene_id", 0),
        start=start,
        end=end,
        duration=segment.get("duration", end - start),
        original_audio_available=original_audio_available,
        original_video_available=original_video_available,
        original_video_endpoint=(
            f"/api/media/video/{quote(video_id, safe='')}/source"
        ) if original_video_available else None,
        original_audio_endpoint=(
            f"/api/media/video/{quote(video_id, safe='')}/scene/"
            f"{quote(str(segment.get('scene_id')), safe='')}/audio"
        ) if original_audio_available else None,
        **frame_projection,
        **frame_paths,
        visual_caption=segment.get("visual_caption"),
        ocr_text=segment.get("ocr_text"),
        ocr_date_candidates=segment.get("ocr_date_candidates", []),
        clip_id=segment.get("clip_id"),
        dino_id=segment.get("dino_id"),
        keywords=segment.get("keywords", []),
        objects=_segment_object_labels(segment),
        caption_meta=sanitize_visual_meta(video_id, segment.get("caption_meta")),
        caption_observations=sanitize_visual_observations(video_id, segment.get("caption_observations")),
        ocr_observations=sanitize_visual_observations(video_id, segment.get("ocr_observations")),
        detect_meta=sanitize_visual_meta(video_id, segment.get("detect_meta")),
        detected_objects=sanitize_detected_objects(video_id, segment.get("detected_objects")),
        object_observations=sanitize_visual_observations(video_id, segment.get("object_observations")),
        transcript=segment.get("full_transcript") or segment.get("transcript"),
        speakers=segment.get("speaker_ids", []),
        audio_chunks=segment.get("audio_chunks", []),
        speaker_count=segment.get("speaker_count"),
        dominant_speaker_id=segment.get("dominant_speaker_id"),
        continuity_key=segment.get("continuity_key"),
        diarization_status=segment.get("diarization_status"),
        diarization_note=segment.get("diarization_note"),
        emotion_status=segment.get("emotion_status"),
        emotion_note=segment.get("emotion_note"),
        emotion_segments=segment.get("emotion_segments") or [],
        emotion_input=segment.get("emotion_input"),
        sound_events=segment.get("sound_events") or [],
        sound_event_meta=segment.get("sound_event_meta"),
        audio_evidence=public_audio_evidence(video_id, segment.get('audio_evidence')),
        speaker_voice_signature_count=segment.get("speaker_voice_signature_count"),
        speaker_voice_signature_meta=segment.get("speaker_voice_signature_meta"),
        audio_emotion=segment.get("audio_emotion"),
        audio_emotion_scores=segment.get("audio_emotion_scores"),
        audio_emotion_ranking=segment.get("audio_emotion_ranking") or [],
        audio_emotion_top_candidate=segment.get("audio_emotion_top_candidate"),
        audio_emotion_promotion_threshold=segment.get("audio_emotion_promotion_threshold"),
        text_emotion_ranking=segment.get("text_emotion_ranking") or [],
        text_emotion_meta=segment.get("text_emotion_meta"),
        clap_meta=segment.get("clap_meta"),
        transcript_meta=segment.get("transcript_meta"),
        transcript_outcome=segment.get("transcript_outcome"),
        transcript_outcome_reason=segment.get("transcript_outcome_reason"),
        sentiment=sentiment_payload,
        sentiment_label=sentiment_label,
        sentiment_score=segment.get("sentiment_score"),
        sentiment_meta=segment.get("sentiment_meta"),
        time_hints=segment.get("time_hints"),
        music_events=segment.get("music_events"),
        tags=segment.get("tags", []),
        tag_details=segment.get("tag_details", []),
        scene_present_entities=_list_dicts(segment.get("scene_present_entities")),
        entities=_list_dicts(segment.get("entities")),
        dialogue_mentioned_entities=_list_dicts(segment.get("dialogue_mentioned_entities")),
        mentioned_people=_list_dicts(segment.get("mentioned_people")),
        visible_people=_list_dicts(segment.get("visible_people")),
        scene_context_llm=segment.get("scene_context_llm"),
        scene_context_epistemic=segment.get("scene_context_epistemic"),
        scene_context_arbitration=segment.get("scene_context_arbitration"),
        content_state=segment.get("content_state"),
        candidate_visible_people=_list_dicts(segment.get("candidate_visible_people")),
        speaker_aligned_mentions=_list_dicts(segment.get("speaker_aligned_mentions")),
        transcript_entity_disagreements=_list_dicts(segment.get("transcript_entity_disagreements")),
        normalization_applied=bool(segment.get("normalization_applied", False)),
        normalization_source=segment.get("normalization_source"),
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
        
        audio_paths = loader.get_scene_audio_paths(video_id)
        source_kind = temporal_index.get("source_kind") or "video"
        resolver = loader.get_original_video_path if source_kind == "video" else loader.get_original_source_path
        original_source_path = await run_in_threadpool(resolver, video_id)
        scenes = []
        for segment in temporal_index.get('segments', []):
            scenes.append(_build_scene_response(
                video_id, segment,
                original_audio_available=str(segment.get("scene_id")) in audio_paths,
                original_source_path=original_source_path,
                source_kind=source_kind,
            ))
        
        return scenes
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list scenes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list scenes: {str(e)}")


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(
    video_id: str = PathParam(..., description="Video identifier"),
    scene_id: str = PathParam(..., description="Scene identifier")
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
        
        segment = _find_temporal_segment(temporal_index, scene_id)
        if segment is not None:
            source_kind = temporal_index.get("source_kind") or "video"
            resolver = loader.get_original_video_path if source_kind == "video" else loader.get_original_source_path
            return _build_scene_response(
                video_id, segment,
                original_audio_available=str(segment.get("scene_id")) in loader.get_scene_audio_paths(video_id),
                original_source_path=await run_in_threadpool(resolver, video_id),
                source_kind=source_kind,
            )
        
        raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scene: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get scene: {str(e)}")


@router.get("/{scene_id}/audio-evidence/{review_id}")
async def get_audio_evidence(video_id: str, scene_id: str, review_id: str):
    loader = get_data_loader()
    segment = _find_temporal_segment(loader.load_temporal_index(video_id) or {}, scene_id)
    if segment is None or not loader.is_search_result_active({**segment, 'video_id': video_id}):
        raise HTTPException(status_code=404, detail='Active scene evidence not found')
    try:
        root = Path(_config['paths']['db_path']).resolve().parent / 'processing'
        path = await run_in_threadpool(review_media, segment.get('audio_evidence'), review_id, root)
    except (ValueError, KeyError, TypeError, OSError):
        raise HTTPException(status_code=409, detail='Retained audio evidence is unavailable or changed')
    return FileResponse(path, media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@router.get("/{scene_id}/relationships")
async def get_scene_relationships(video_id: str, scene_id: str,
                                  limit: int = Query(100, ge=1, le=200)) -> dict:
    """Read stored relationships only for an active scene in this source."""
    loader = get_data_loader()
    timeline = loader.load_temporal_index(video_id)
    segment = _find_temporal_segment(timeline or {}, scene_id)
    if segment is None or not loader.is_search_result_active({**segment, "video_id": video_id}):
        raise HTTPException(status_code=404, detail="Active scene not found")
    manifest = loader.load_scene_manifest(video_id) or {}
    source_hash = str(manifest.get("video_hash") or manifest.get("video_id") or "")
    if not source_hash:
        raise HTTPException(status_code=409, detail="Source identity unavailable")
    cfg = load_configs({})
    path = (cfg.get("paths") or {}).get("knowledge_graph_db")
    if not path:
        return {"status": "unavailable", "relationships": [], "truncated": False}
    try:
        result = await run_in_threadpool(load_scene_relationships, Path(path),
                                        scene_id=scene_id, source_hash=source_hash,
                                        source_alias=video_id, limit=limit)
    except Exception:
        logger.exception("Stored relationship read failed")
        raise HTTPException(status_code=503, detail="Stored relationship evidence unavailable")
    result.update(video_id=video_id, epoch_id=cfg.get("epoch_id") or Path(path).parent.name)
    for relationship in result["relationships"]:
        relationship["evidence"].update(video_id=video_id, start=segment.get("start"), end=segment.get("end"))
    return result


@router.get("/{scene_id}/similar", response_model=List[SceneResponse])
async def find_similar_scenes(
    video_id: str = PathParam(..., description="Video identifier"),
    scene_id: str = PathParam(..., description="Scene identifier"),
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
        source_segment = _find_temporal_segment(temporal_index, scene_id)
        
        if not source_segment:
            raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")

        engine = get_search_engine()
        similar_results = engine.search_similar_scene(
            video_id=video_id,
            scene_id=scene_id,
            top_k=top_k,
            retrieval_context="human.ui.search",
        )

        scenes = []
        audio_paths_by_video = {}
        original_sources = {}
        current_video_ids = {
            str(value) for value in (video_id, temporal_index.get("video_id"), temporal_index.get("video_hash"))
            if value is not None
        }
        for result in similar_results:
            scene_context = result.get("scene_context") if isinstance(result.get("scene_context"), dict) else None
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else None
            hydrated_from_current_video = False
            payload_scene_id = (payload or {}).get("scene_id")
            result_source_video = (
                (payload or {}).get("video_id") or (payload or {}).get("video_hash")
                or (scene_context or {}).get("video_id") or (scene_context or {}).get("video_hash")
            )
            if payload_scene_id is not None and (
                result_source_video is None or str(result_source_video) in current_video_ids
            ):
                same_video_segment = _find_temporal_segment(temporal_index, payload_scene_id)
                if same_video_segment is not None:
                    scene_context = same_video_segment
                    hydrated_from_current_video = True
            scene_payload = scene_context or payload
            if not isinstance(scene_payload, dict):
                continue
            result_video_id = (
                video_id
                if hydrated_from_current_video
                else result_source_video or video_id
            )
            result_video_id = str(result_video_id)
            if isinstance(loader, DataLoader) and not loader.is_search_result_active({
                **scene_payload, "video_id": result_video_id,
            }):
                continue
            if result_video_id not in audio_paths_by_video:
                audio_paths_by_video[result_video_id] = loader.get_scene_audio_paths(result_video_id)
                kind = scene_payload.get("source_kind") or "video"
                resolver = loader.get_original_video_path if kind == "video" else loader.get_original_source_path
                original_sources[result_video_id] = await run_in_threadpool(resolver, result_video_id)
            scenes.append(_build_scene_response(
                result_video_id, scene_payload,
                original_audio_available=str(scene_payload.get("scene_id")) in audio_paths_by_video[result_video_id],
                original_source_path=original_sources[result_video_id],
            ))

        return scenes
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find similar scenes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find similar scenes: {str(e)}")
