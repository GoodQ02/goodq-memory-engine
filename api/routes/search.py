"""
Search API routes for GoodQ4All.
Provides multimodal search endpoints.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel

from api.utils.response_models import SearchResponse, SearchResult, default_confidence_payload
from api.utils.loaders import DataLoader
from api.utils.media_projection import representative_frame_projection
from api.routes.runtime import (
    _audio_qdrant_collection_candidates,
    _evaluate_qdrant_audio_payloads,
    _scroll_qdrant_audio_payloads,
)
from retrieval.multimodal_search import MultimodalSearchEngine
from steps.common.config_loader import load_configs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# Global instances
_search_engine = None
_data_loader = None
_config = None


def _extract_sentiment_fields(result: dict) -> Dict[str, Any]:
    """Project sentiment from scene context first, then payload, without altering ranking behavior."""
    scene_context = result.get("scene_context") if isinstance(result.get("scene_context"), dict) else {}
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}

    sentiment = scene_context.get("sentiment")
    if not isinstance(sentiment, dict):
        sentiment = payload.get("sentiment") if isinstance(payload.get("sentiment"), dict) else None

    sentiment_label = scene_context.get("sentiment_label")
    if sentiment_label is None:
        sentiment_label = payload.get("sentiment_label")

    sentiment_score = scene_context.get("sentiment_score")
    if sentiment_score is None:
        sentiment_score = payload.get("sentiment_score")

    return {
        "sentiment": sentiment,
        "sentiment_label": sentiment_label,
        "sentiment_score": sentiment_score,
    }


def _list_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _segment_object_labels(segment: dict) -> List[str]:
    labels = _list_strings(segment.get("objects"))
    if labels:
        return labels

    detected_objects = segment.get("detected_objects")
    if not isinstance(detected_objects, list):
        return []

    extracted = []
    for obj in detected_objects:
        if isinstance(obj, dict) and obj.get("label"):
            extracted.append(str(obj["label"]))
    return extracted


def _segment_id_candidates(segment: dict) -> set[str]:
    candidates: set[str] = set()
    for key in ("scene_id", "segment_id", "id", "index", "scene_index"):
        value = segment.get(key)
        if value is not None and str(value).strip():
            candidates.add(str(value).strip())
            try:
                candidates.add(f"scene_{int(value):04d}")
            except (TypeError, ValueError):
                pass
    return candidates


def _segment_transcript(segment: dict) -> Optional[str]:
    for key in ("full_transcript", "transcript", "text"):
        value = segment.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _segment_representative_frame_reference(segment: dict) -> Any:
    for key in (
        "representative_frame",
        "representative_frame_path",
        "representative_frame_endpoint",
        "thumbnail",
        "keyframe",
    ):
        value = segment.get(key)
        if value not in (None, "", [], {}):
            return value

    frame_paths = segment.get("frame_paths")
    if isinstance(frame_paths, list):
        for value in frame_paths:
            if value not in (None, "", [], {}):
                return value
    return None


def _kg_evidence(segment: dict) -> Dict[str, Any]:
    scene_present_entities = _list_dicts(segment.get("scene_present_entities"))
    entities = _list_dicts(segment.get("entities"))
    dialogue_mentioned_entities = _list_dicts(segment.get("dialogue_mentioned_entities"))
    mentioned_people = _list_dicts(segment.get("mentioned_people"))
    candidate_visible_people = _list_dicts(segment.get("candidate_visible_people"))
    speaker_aligned_mentions = _list_dicts(segment.get("speaker_aligned_mentions"))
    relationships = _list_dicts(segment.get("relationships")) or _list_dicts(segment.get("kg_relationships"))
    entity_count = len(scene_present_entities) or len(entities) or len(dialogue_mentioned_entities) or len(mentioned_people)
    relationship_count = len(relationships)
    if relationship_count:
        relationship_state = "observed"
    elif len(scene_present_entities):
        relationship_state = "entity_presence_only"
    elif len(dialogue_mentioned_entities) or len(mentioned_people):
        relationship_state = "dialogue_entity_mentions_only"
    elif len(candidate_visible_people) or len(speaker_aligned_mentions):
        relationship_state = "candidate_identity_only"
    elif entity_count:
        relationship_state = "entity_presence_only"
    else:
        relationship_state = "not_observed"
    return {
        "source": "timeline_scene_entities",
        "entity_count": entity_count,
        "scene_present_count": len(scene_present_entities),
        "dialogue_mentioned_count": len(dialogue_mentioned_entities),
        "mentioned_people_count": len(mentioned_people),
        "candidate_visible_people_count": len(candidate_visible_people),
        "speaker_aligned_mention_count": len(speaker_aligned_mentions),
        "relationship_count": relationship_count,
        "relationship_state": relationship_state,
    }


def _timeline_enrichment_context(segment: dict) -> Dict[str, Any]:
    start = segment.get("start")
    end = segment.get("end")
    kg_evidence = _kg_evidence(segment)
    context = {
        "start": start,
        "end": end,
        "duration": (end - start) if isinstance(start, (int, float)) and isinstance(end, (int, float)) else segment.get("duration"),
        "transcript": _segment_transcript(segment),
        "tags": _list_strings(segment.get("tags")),
        "objects": _segment_object_labels(segment),
        "audio_emotion": segment.get("audio_emotion"),
        "audio_emotion_scores": segment.get("audio_emotion_scores"),
        "clap_meta": segment.get("clap_meta") if isinstance(segment.get("clap_meta"), dict) else None,
        "sentiment": segment.get("sentiment") if isinstance(segment.get("sentiment"), dict) else None,
        "sentiment_label": segment.get("sentiment_label"),
        "sentiment_score": segment.get("sentiment_score"),
        "scene_present_entities": _list_dicts(segment.get("scene_present_entities")),
        "entities": _list_dicts(segment.get("entities")),
        "dialogue_mentioned_entities": _list_dicts(segment.get("dialogue_mentioned_entities")),
        "mentioned_people": _list_dicts(segment.get("mentioned_people")),
        "visible_people": _list_dicts(segment.get("visible_people")),
        "candidate_visible_people": _list_dicts(segment.get("candidate_visible_people")),
        "speaker_aligned_mentions": _list_dicts(segment.get("speaker_aligned_mentions")),
        "transcript_entity_disagreements": _list_dicts(segment.get("transcript_entity_disagreements")),
        "relationships": _list_dicts(segment.get("relationships")) or _list_dicts(segment.get("kg_relationships")),
        "kg_evidence": kg_evidence if (
            kg_evidence["entity_count"]
            or kg_evidence["relationship_count"]
            or kg_evidence["candidate_visible_people_count"]
            or kg_evidence["speaker_aligned_mention_count"]
        ) else None,
        "speaker_count": segment.get("speaker_count"),
        "dominant_speaker_id": segment.get("dominant_speaker_id"),
        "continuity_key": segment.get("continuity_key"),
        "scene_context_llm": segment.get("scene_context_llm") if isinstance(segment.get("scene_context_llm"), dict) else None,
        "scene_context_epistemic": segment.get("scene_context_epistemic") if isinstance(segment.get("scene_context_epistemic"), dict) else None,
        "scene_context_arbitration": segment.get("scene_context_arbitration") if isinstance(segment.get("scene_context_arbitration"), dict) else None,
    }
    return {key: value for key, value in context.items() if value not in (None, [], {})}


def _lookup_timeline_enrichment(payload: dict) -> Dict[str, Any]:
    """Hydrate a search payload from persisted timeline data when a scene match is available."""
    scene_id = payload.get("scene_id")
    if scene_id is None or not str(scene_id).strip():
        return {}

    loader = get_data_loader()
    search_video_id = str(payload.get("video_id")).strip() if payload.get("video_id") is not None else None
    video_ids: List[str] = []

    try:
        processed_video_ids = list(loader.list_processed_videos())
    except Exception as exc:
        logger.debug("retrieval enrichment video inventory unavailable error=%s", exc)
        processed_video_ids = []

    if search_video_id and search_video_id in processed_video_ids:
        video_ids.append(search_video_id)
    elif search_video_id and not processed_video_ids:
        video_ids.append(search_video_id)

    for video_id in processed_video_ids:
        if video_id not in video_ids:
            video_ids.append(video_id)

    wanted_scene = str(scene_id).strip()
    for video_id in video_ids:
        try:
            temporal_index = loader.load_temporal_index(video_id)
        except Exception as exc:
            logger.debug("retrieval enrichment timeline load failed video_id=%s error=%s", video_id, exc)
            continue
        if not isinstance(temporal_index, dict):
            continue

        segments = temporal_index.get("segments")
        if not isinstance(segments, list):
            continue

        for segment in segments:
            if not isinstance(segment, dict) or wanted_scene not in _segment_id_candidates(segment):
                continue

            try:
                metadata = loader.get_video_metadata(video_id)
            except Exception:
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}

            start = segment.get("start")
            end = segment.get("end")
            duration = (end - start) if isinstance(start, (int, float)) and isinstance(end, (int, float)) else segment.get("duration")
            frame_projection = representative_frame_projection(video_id, _segment_representative_frame_reference(segment))
            context = _timeline_enrichment_context(segment)
            context.update({key: value for key, value in frame_projection.items() if value not in (None, [], {})})
            kg_evidence = context.get("kg_evidence") if isinstance(context.get("kg_evidence"), dict) else _kg_evidence(segment)
            entities = _list_dicts(segment.get("scene_present_entities"))
            relationships = _list_dicts(segment.get("relationships")) or _list_dicts(segment.get("kg_relationships"))
            return {
                "timeline_video_id": video_id,
                "display_title": metadata.get("title") or video_id,
                "start": start,
                "end": end,
                "duration": duration,
                "timestamp": start,
                **frame_projection,
                "transcript": _segment_transcript(segment),
                "keywords": _list_strings(segment.get("tags")) or _list_strings(segment.get("keywords")),
                "tags": _list_strings(segment.get("tags")),
                "objects": _segment_object_labels(segment),
                "audio_emotion": segment.get("audio_emotion"),
                "audio_emotion_scores": segment.get("audio_emotion_scores"),
                "clap_meta": segment.get("clap_meta") if isinstance(segment.get("clap_meta"), dict) else None,
                "sentiment": context.get("sentiment"),
                "sentiment_label": context.get("sentiment_label"),
                "sentiment_score": context.get("sentiment_score"),
                "scene_present_entities": entities,
                "entities": _list_dicts(segment.get("entities")),
                "dialogue_mentioned_entities": _list_dicts(segment.get("dialogue_mentioned_entities")),
                "mentioned_people": _list_dicts(segment.get("mentioned_people")),
                "visible_people": _list_dicts(segment.get("visible_people")),
                "candidate_visible_people": _list_dicts(segment.get("candidate_visible_people")),
                "speaker_aligned_mentions": _list_dicts(segment.get("speaker_aligned_mentions")),
                "transcript_entity_disagreements": _list_dicts(segment.get("transcript_entity_disagreements")),
                "kg_relationships": relationships,
                "kg_evidence": kg_evidence,
                "context": context,
                "scene_context_llm": context.get("scene_context_llm"),
                "scene_context_epistemic": context.get("scene_context_epistemic"),
                "scene_context_arbitration": context.get("scene_context_arbitration"),
                "provenance": {
                    "search_video_id": search_video_id,
                    "timeline_video_id": video_id,
                    "scene_id": wanted_scene,
                    "enrichment": "timeline_segment",
                    "kg_source": kg_evidence.get("source"),
                    "entity_count": kg_evidence.get("entity_count", 0),
                    "relationship_count": kg_evidence.get("relationship_count", 0),
                },
            }
    return {}


def _search_audio_vector_proof(payload: dict, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    """Project strict current-run audio proof for a retrieved scene without changing ranking."""

    context = enrichment.get("context") if isinstance(enrichment.get("context"), dict) else {}
    clap_meta = context.get("clap_meta") if isinstance(context.get("clap_meta"), dict) else enrichment.get("clap_meta")
    if not isinstance(clap_meta, dict):
        return {
            "status": "not_exposed",
            "label": "Not Exposed",
            "current_run_qdrant_proven": 0,
            "qdrant_run_matched_points": 0,
            "reason": "clap_meta_missing",
        }

    runtime_run_id = str(clap_meta.get("run_id") or "").strip()
    if not runtime_run_id:
        return {
            "status": "no_current_run_evidence",
            "label": "No Current-Run Evidence",
            "current_run_qdrant_proven": 0,
            "qdrant_run_matched_points": 0,
            "reason": "clap_run_id_missing",
        }

    header: Dict[str, Any] = {}
    collection = str(clap_meta.get("qdrant_collection") or "").strip()
    if collection:
        header["qdrant_audio_collection"] = collection

    collection_candidates = _audio_qdrant_collection_candidates(None, header=header)
    qdrant_result = _scroll_qdrant_audio_payloads(runtime_run_id, collection_candidates)
    payloads = qdrant_result.get("payloads") if isinstance(qdrant_result.get("payloads"), list) else []

    scene_ids = {
        str(value).strip()
        for value in (
            payload.get("scene_id"),
            clap_meta.get("scene_id"),
            enrichment.get("provenance", {}).get("scene_id") if isinstance(enrichment.get("provenance"), dict) else None,
        )
        if value is not None and str(value).strip()
    }
    video_ids = {
        str(value).strip()
        for value in (
            payload.get("video_id"),
            clap_meta.get("video_id"),
            payload.get("video_hash"),
            clap_meta.get("video_hash"),
        )
        if value is not None and str(value).strip()
    }

    proof = _evaluate_qdrant_audio_payloads(payloads, scene_ids=scene_ids, video_ids=video_ids)
    current_run_proven = int(proof.get("current_run_qdrant_proven") or 0)
    base = {
        "status": "current_run_audio_vector_proven" if current_run_proven else "no_current_run_evidence",
        "label": "Proven" if current_run_proven else "No Current-Run Evidence",
        "runtime_run_id": runtime_run_id,
        "collection": qdrant_result.get("collection"),
        "collection_candidates": collection_candidates,
        "qdrant_run_matched_points": len(payloads),
        "reason": "run_matched_payloads_satisfy_contract" if current_run_proven else "no_qdrant_payloads_matched_scene",
    }
    if qdrant_result.get("status") != "ok":
        base.update(
            {
                "status": "not_exposed",
                "label": "Not Exposed",
                "reason": qdrant_result.get("status") or "qdrant_unavailable",
            }
        )
    base.update(proof)
    return base


def _merge_dicts(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(base, dict) and not isinstance(extra, dict):
        return None
    merged: Dict[str, Any] = {}
    if isinstance(base, dict):
        merged.update(base)
    if isinstance(extra, dict):
        merged.update(extra)
    return merged


def _looks_like_local_path(value: str) -> bool:
    text = value.strip()
    return (
        len(text) >= 3
        and text[1] == ":"
        and text[2] in ("\\", "/")
    ) or (
        text.startswith("\\\\")
        or text.startswith("file://")
        or text.startswith("~/")
        or "\\GOODCUBE\\" in text
        or "\\_DATA\\" in text
        or "/GOODCUBE/" in text
        or "/_DATA/" in text
        or "\\GoodQ_Data\\" in text
        or "/GoodQ_Data/" in text
    )


def _sanitize_local_path_values(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        redacted = False
        for key, child in value.items():
            safe_child, child_redacted = _sanitize_local_path_values(child)
            sanitized[key] = safe_child
            redacted = redacted or child_redacted
        return sanitized, redacted

    if isinstance(value, list):
        sanitized_list = []
        redacted = False
        for child in value:
            safe_child, child_redacted = _sanitize_local_path_values(child)
            sanitized_list.append(safe_child)
            redacted = redacted or child_redacted
        return sanitized_list, redacted

    if isinstance(value, str) and _looks_like_local_path(value):
        return "<local-only>", True

    return value, False


def _sanitize_read_model_mapping(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return value

    sanitized, redacted = _sanitize_local_path_values(value)
    if redacted and isinstance(sanitized, dict):
        sanitized["raw_paths"] = "redacted"
    return sanitized


def _safe_number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _enriched_confidence(result: dict, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    confidence = result.get("confidence") if isinstance(result.get("confidence"), dict) else default_confidence_payload()
    confidence = dict(confidence)
    score = _safe_number(result.get("score"))
    if score is not None:
        if confidence.get("intrinsic") is None:
            confidence["intrinsic"] = score
        if confidence.get("overall") is None:
            confidence["overall"] = score

    if enrichment:
        if confidence.get("source") is None:
            confidence["source"] = "timeline_segment"
        epistemic = enrichment.get("scene_context_epistemic")
        if isinstance(epistemic, dict):
            state = epistemic.get("state")
            dominant = epistemic.get("dominant_evidence")
            if state:
                confidence["evidence_state"] = state
            if dominant:
                confidence["dominant_evidence"] = dominant
    return confidence


def _build_search_result(result: dict, modality: Optional[str] = None) -> SearchResult:
    payload = result.get("payload", {}) if isinstance(result.get("payload"), dict) else {}
    sentiment_fields = _extract_sentiment_fields(result)
    enrichment = _lookup_timeline_enrichment(payload)
    if sentiment_fields["sentiment"] is None and isinstance(enrichment.get("sentiment"), dict):
        sentiment_fields["sentiment"] = enrichment.get("sentiment")
    if sentiment_fields["sentiment_label"] is None:
        sentiment_fields["sentiment_label"] = enrichment.get("sentiment_label")
    if sentiment_fields["sentiment_score"] is None:
        sentiment_fields["sentiment_score"] = enrichment.get("sentiment_score")
    result_context = result.get("scene_context") if isinstance(result.get("scene_context"), dict) else None
    context = _merge_dicts(enrichment.get("context"), result_context)
    provenance = _merge_dicts(enrichment.get("provenance"), result.get("provenance") if isinstance(result.get("provenance"), dict) else None)
    video_id = payload.get("video_id")
    clap_meta = enrichment.get("clap_meta")
    safe_clap_meta = _sanitize_read_model_mapping(clap_meta) if isinstance(clap_meta, dict) else None
    audio_vector_proof = _search_audio_vector_proof(payload, enrichment)
    current_run_audio_proven = audio_vector_proof.get("status") == "current_run_audio_vector_proven"
    frame_projection = {
        "representative_frame": enrichment.get("representative_frame"),
        "representative_frame_available": bool(enrichment.get("representative_frame_available")),
        "representative_frame_endpoint": enrichment.get("representative_frame_endpoint"),
        "representative_frame_path_redacted": bool(enrichment.get("representative_frame_path_redacted")),
    }
    if not frame_projection["representative_frame_endpoint"]:
        frame_projection = representative_frame_projection(str(video_id or ""), payload.get("representative_frame"))

    return SearchResult(
        score=result.get("score", 0.0),
        modality=modality or result.get("modality", "unknown"),
        video_id=video_id,
        timeline_video_id=enrichment.get("timeline_video_id"),
        display_title=enrichment.get("display_title"),
        scene_id=payload.get("scene_id"),
        start=enrichment.get("start"),
        end=enrichment.get("end"),
        duration=enrichment.get("duration"),
        timestamp=payload.get("timestamp", enrichment.get("timestamp")),
        **frame_projection,
        transcript=payload.get("transcript", enrichment.get("transcript")),
        keywords=payload.get("keywords") or enrichment.get("keywords") or [],
        tags=enrichment.get("tags") or [],
        objects=payload.get("objects") or enrichment.get("objects") or [],
        audio_emotion=enrichment.get("audio_emotion"),
        audio_emotion_scores=enrichment.get("audio_emotion_scores"),
        clap_meta=safe_clap_meta,
        audio_vector_proof=audio_vector_proof,
        current_run_qdrant_audio_proven=current_run_audio_proven,
        current_run_audio_vector_proven=current_run_audio_proven,
        audio_qdrant_current_run_proven=current_run_audio_proven,
        scene_present_entities=enrichment.get("scene_present_entities") or [],
        entities=enrichment.get("entities") or [],
        dialogue_mentioned_entities=enrichment.get("dialogue_mentioned_entities") or [],
        mentioned_people=enrichment.get("mentioned_people") or [],
        visible_people=enrichment.get("visible_people") or [],
        candidate_visible_people=enrichment.get("candidate_visible_people") or [],
        speaker_aligned_mentions=enrichment.get("speaker_aligned_mentions") or [],
        transcript_entity_disagreements=enrichment.get("transcript_entity_disagreements") or [],
        kg_relationships=enrichment.get("kg_relationships") or [],
        kg_evidence=enrichment.get("kg_evidence"),
        sentiment=sentiment_fields["sentiment"],
        sentiment_label=sentiment_fields["sentiment_label"],
        sentiment_score=sentiment_fields["sentiment_score"],
        context=_sanitize_read_model_mapping(context),
        scene_context_llm=enrichment.get("scene_context_llm"),
        scene_context_epistemic=enrichment.get("scene_context_epistemic"),
        scene_context_arbitration=enrichment.get("scene_context_arbitration"),
        provenance=_sanitize_read_model_mapping(provenance),
        confidence=_enriched_confidence(result, enrichment),
    )


def get_search_engine():
    """Lazy-load search engine."""
    global _search_engine, _config
    
    if _search_engine is None:
        _config = load_configs({})
        _search_engine = MultimodalSearchEngine(_config)
        logger.info("[OK] Search engine initialized")
    
    return _search_engine


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized")
    
    return _data_loader


class MultimodalSearchRequest(BaseModel):
    """Multimodal search request."""
    query: str
    top_k: int = 10
    modalities: Optional[List[str]] = None
    fusion_weights: Optional[dict] = None


@router.post("/multimodal", response_model=SearchResponse)
async def search_multimodal(request: MultimodalSearchRequest = Body(...)):
    """
    Unified multimodal search across text, visual, and audio.
    
    Args:
        request: Search request with query and options
        
    Returns:
        Ranked search results with scores and context
    """
    try:
        engine = get_search_engine()
        
        # Execute search
        results = engine.search_multimodal(
            query=request.query,
            top_k=request.top_k,
            modalities=request.modalities
        )
        
        # Convert to response format
        search_results = []
        for result in results:
            search_results.append(_build_search_result(result))
        
        modalities_searched = request.modalities if request.modalities else ['text', 'visual']
        
        return SearchResponse(
            query=request.query,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=modalities_searched,
            fusion_weights=request.fusion_weights or {
                'text': engine.weight_text,
                'visual': engine.weight_visual,
                'audio': engine.weight_audio
            }
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/text", response_model=SearchResponse)
async def search_text(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, description="Number of results")
):
    """
    Text-only search across transcripts and captions.
    
    Args:
        q: Search query
        top_k: Number of results to return
        
    Returns:
        Search results from text modality
    """
    try:
        engine = get_search_engine()
        
        results = engine.search_text(q, top_k=top_k)
        
        search_results = []
        for result in results:
            search_results.append(_build_search_result(result, modality="text"))
        
        return SearchResponse(
            query=q,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=['text']
        )
        
    except Exception as e:
        logger.error(f"Text search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Text search failed: {str(e)}")


@router.get("/visual", response_model=SearchResponse)
async def search_visual(
    q: str = Query(..., description="Visual search query (text description)"),
    top_k: int = Query(10, description="Number of results")
):
    """
    Visual search using CLIP text-to-image similarity.
    
    Args:
        q: Text description of visual content
        top_k: Number of results to return
        
    Returns:
        Search results from visual modality
    """
    try:
        engine = get_search_engine()
        
        results = engine.search_visual(q, top_k=top_k)
        
        search_results = []
        for result in results:
            search_results.append(_build_search_result(result, modality="visual"))
        
        return SearchResponse(
            query=q,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=['visual']
        )
        
    except Exception as e:
        logger.error(f"Visual search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Visual search failed: {str(e)}")
