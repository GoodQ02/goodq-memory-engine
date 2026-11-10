"""
Timeline API routes for GoodQ4All.
Provides unified temporal index access.
"""
from __future__ import annotations
import logging
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Path as PathParam
from starlette.concurrency import run_in_threadpool

from api.utils.response_models import TimelineResponse, TimelineSegment
from api.utils.loaders import DataLoader
from api.utils.audio_evidence import public_audio_evidence
from api.utils.media_projection import (
    document_meta_projection,
    frame_paths_projection,
    representative_frame_projection,
    sanitize_detected_objects,
    sanitize_visual_meta,
    sanitize_visual_observations,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos/{video_id}/timeline", tags=["timeline"])

_data_loader = None

_TIMELINE_TRUTH_METADATA_FIELDS = (
    "segments_with_candidate_visible_people",
    "segments_with_interaction_dominance",
    "segments_with_conversation_owner",
    "segments_with_speaker_aligned_mentions",
    "segments_with_transcript_entity_disagreements",
    "segments_with_full_name_partial_entity_disagreements",
    "segments_with_scene_context_llm",
    "segments_with_scene_context_epistemic",
    "segments_with_scene_context_arbitration",
    "segments_with_audio_emotion_scores",
    "segments_with_audio_emotion_ranking",
    "segments_with_text_emotion_ranking",
    "segments_with_sentiment",
    "top_audio_emotion_score_signals",
    "top_text_emotions",
    "top_sentiment_labels",
    "audio_emotion_policy",
    "top_candidate_visible_people",
    "top_interaction_dominance",
    "top_conversation_owners",
    "top_speaker_aligned_mentions",
    "top_scene_context_tags",
    "top_scene_context_epistemic_states",
    "top_scene_context_epistemic_dominant_evidence",
    "top_scene_context_arbitration_resolved_by",
    "top_scene_context_arbitration_unresolved_axes",
    "speaker_aligned_mention_variant_groups",
    "transcript_entity_disagreement_category_counts",
    "top_transcript_full_name_partial_entity_families",
    "top_transcript_entity_disagreement_families",
)


def _segment_object_labels(segment: dict) -> list[str]:
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


def _build_timeline_segment(video_id: str, seg: dict, truncate_transcript: bool = False,
                            source_kind: str = "video", original_image_available: bool = False) -> TimelineSegment:
    """Project one persisted segment into the stable timeline API contract."""
    full_transcript = seg.get("full_transcript") or seg.get("transcript")
    transcript = full_transcript
    if truncate_transcript and isinstance(full_transcript, str) and len(full_transcript) > 200:
        transcript = f"{full_transcript[:200]}..."
    frame_projection = representative_frame_projection(video_id, seg.get('representative_frame'))
    if original_image_available:
        endpoint = f"/api/media/video/{quote(video_id, safe='')}/source"
        frame_projection = {
            "representative_frame": endpoint, "representative_frame_endpoint": endpoint,
            "representative_frame_available": True, "representative_frame_path_redacted": False,
        }
    frame_paths = frame_paths_projection(video_id, seg.get('frame_paths', []))

    return TimelineSegment(
        source_kind=seg.get("source_kind") or source_kind,
        document_text=seg.get("document_text"),
        document_meta=document_meta_projection(seg.get("document_meta")),
        segment_id=seg.get('segment_id', 0),
        start=seg.get('start', 0.0),
        end=seg.get('end', 0.0),
        scene_id=seg.get('scene_id'),
        audio_chunks=seg.get('audio_chunks', []),
        speaker_ids=seg.get('speaker_ids', []),
        transcript=transcript,
        keywords=seg.get('keywords', [])[:5] if truncate_transcript else seg.get('keywords', []),
        objects=_segment_object_labels(seg)[:5] if truncate_transcript else _segment_object_labels(seg),
        clip_id=seg.get('clip_id'),
        dino_id=seg.get('dino_id'),
        **frame_projection,
        **{key: value for key, value in frame_paths.items() if key != "frame_paths"},
        visual_caption=seg.get('visual_caption'),
        ocr_text=seg.get('ocr_text'),
        ocr_date_candidates=seg.get('ocr_date_candidates', []),
        caption_meta=sanitize_visual_meta(video_id, seg.get('caption_meta')),
        caption_observations=sanitize_visual_observations(video_id, seg.get('caption_observations')),
        ocr_observations=sanitize_visual_observations(video_id, seg.get('ocr_observations')),
        detect_meta=sanitize_visual_meta(video_id, seg.get('detect_meta')),
        detected_objects=sanitize_detected_objects(video_id, seg.get('detected_objects')),
        object_observations=sanitize_visual_observations(video_id, seg.get('object_observations')),
        speaker_count=seg.get('speaker_count'),
        dominant_speaker_id=seg.get('dominant_speaker_id'),
        continuity_key=seg.get('continuity_key'),
        diarization_status=seg.get('diarization_status'),
        diarization_note=seg.get('diarization_note'),
        emotion_status=seg.get('emotion_status'),
        emotion_note=seg.get('emotion_note'),
        emotion_segments=seg.get('emotion_segments') or [],
        emotion_input=seg.get('emotion_input'),
        sound_events=seg.get('sound_events') or [],
        sound_event_meta=seg.get('sound_event_meta'),
        audio_evidence=public_audio_evidence(video_id, seg.get('audio_evidence')),
        speaker_voice_signature_count=seg.get('speaker_voice_signature_count'),
        speaker_voice_signature_meta=seg.get('speaker_voice_signature_meta'),
        audio_emotion=seg.get('audio_emotion'),
        audio_emotion_scores=seg.get('audio_emotion_scores'),
        audio_emotion_ranking=seg.get('audio_emotion_ranking') or [],
        audio_emotion_top_candidate=seg.get('audio_emotion_top_candidate'),
        audio_emotion_promotion_threshold=seg.get('audio_emotion_promotion_threshold'),
        text_emotion_ranking=seg.get('text_emotion_ranking') or [],
        text_emotion_meta=seg.get('text_emotion_meta'),
        clap_meta=seg.get('clap_meta'),
        transcript_meta=seg.get('transcript_meta'),
        transcript_outcome=seg.get('transcript_outcome'),
        transcript_outcome_reason=seg.get('transcript_outcome_reason'),
        sentiment=seg.get("sentiment"),
        sentiment_label=seg.get("sentiment_label"),
        sentiment_score=seg.get("sentiment_score"),
        sentiment_meta=seg.get("sentiment_meta"),
        time_hints=seg.get('time_hints'),
        music_events=seg.get('music_events'),
        tags=seg.get('tags', []),
        tag_details=seg.get('tag_details', []),
        scene_present_entities=seg.get('scene_present_entities', []),
        entities=seg.get('entities', []),
        dialogue_mentioned_entities=seg.get('dialogue_mentioned_entities', []),
        mentioned_people=seg.get('mentioned_people', []),
        visible_people=seg.get('visible_people', []),
        scene_context_llm=seg.get('scene_context_llm'),
        scene_context_epistemic=seg.get('scene_context_epistemic'),
        scene_context_arbitration=seg.get('scene_context_arbitration'),
        content_state=seg.get('content_state'),
        candidate_visible_people=seg.get('candidate_visible_people', []),
        speaker_aligned_mentions=seg.get("speaker_aligned_mentions", []),
        transcript_entity_disagreements=seg.get("transcript_entity_disagreements", []),
        normalization_applied=bool(seg.get("normalization_applied", False)),
        normalization_source=seg.get("normalization_source"),
        interaction_dominance=seg.get("interaction_dominance"),
        conversation_owner=seg.get("conversation_owner"),
    )


def _build_timeline_metadata(temporal_index: dict, include_version: bool = False) -> dict:
    """Project additive truth-model metadata from the persisted temporal index."""
    metadata = {
        'phase6_complete': temporal_index.get('phase6_complete', False),
        'phase6_harmonized': temporal_index.get('phase6_harmonized', False),
    }
    if include_version:
        metadata['version'] = temporal_index.get('version', 1)
    for field_name in _TIMELINE_TRUTH_METADATA_FIELDS:
        if field_name in temporal_index:
            metadata[field_name] = temporal_index[field_name]
    return metadata


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized for timeline")
    
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
        
        source_kind = temporal_index.get("source_kind") or "video"
        original_image_available = source_kind == "image" and await run_in_threadpool(loader.get_original_source_path, video_id) is not None
        segments = []
        for seg in temporal_index.get('segments', []):
            segments.append(_build_timeline_segment(video_id, seg, truncate_transcript=True,
                            source_kind=source_kind, original_image_available=original_image_available))
        
        return TimelineResponse(
            video_id=video_id,
            source_kind=temporal_index.get("source_kind") or "video",
            duration=temporal_index.get('total_duration', temporal_index.get('duration', 0.0)),
            total_scenes=len(set(seg.get('scene_id') for seg in temporal_index.get('segments', []) if seg.get('scene_id') is not None)),
            total_segments=len(segments),
            segments=segments,
            metadata=_build_timeline_metadata(temporal_index)
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
        
        source_kind = temporal_index.get("source_kind") or "video"
        original_image_available = source_kind == "image" and await run_in_threadpool(loader.get_original_source_path, video_id) is not None
        segments = []
        for seg in temporal_index.get('segments', []):
            segments.append(_build_timeline_segment(video_id, seg, truncate_transcript=False,
                            source_kind=source_kind, original_image_available=original_image_available))
        
        return TimelineResponse(
            video_id=video_id,
            source_kind=temporal_index.get("source_kind") or "video",
            duration=temporal_index.get('total_duration', temporal_index.get('duration', 0.0)),
            total_scenes=len(set(seg.get('scene_id') for seg in temporal_index.get('segments', []) if seg.get('scene_id') is not None)),
            total_segments=len(segments),
            segments=segments,
            metadata=_build_timeline_metadata(temporal_index, include_version=True)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get full timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get full timeline: {str(e)}")
