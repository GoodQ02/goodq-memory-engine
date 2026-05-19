"""
Search API routes for GoodQ4All.
Provides multimodal search endpoints.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel

from api.utils.response_models import SearchResponse, SearchResult, default_confidence_payload
from api.utils.loaders import DataLoader
from retrieval.multimodal_search import MultimodalSearchEngine
from steps.common.config_loader import load_configs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# Global instances
_search_engine = None
_data_loader = None
_config = None

_SEARCH_CONTEXT_FIELDS = (
    "start",
    "end",
    "duration",
    "content_state",
    "audio_emotion",
    "time_hints",
    "speaker_ids",
    "speaker_count",
    "dominant_speaker_id",
    "continuity_key",
    "clip_id",
    "dino_id",
    "scene_context_llm",
    "scene_context_epistemic",
    "scene_context_arbitration",
    "interaction_dominance",
    "conversation_owner",
)


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return bool(value)
    return True


def _segment_object_labels(segment: dict) -> List[str]:
    """Normalize persisted object payloads into plain labels for search responses."""
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


def _frame_name(frame_ref: Any) -> Optional[str]:
    if not isinstance(frame_ref, str) or not frame_ref.strip():
        return None
    return Path(frame_ref).name


def _find_temporal_scene(
    loader: Any,
    scene_id: Any,
    video_id: Any = None,
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Find a persisted temporal-index scene without trusting vector payload hashes."""
    if scene_id is None:
        return None, None

    candidates: List[str] = []
    try:
        listed = loader.list_processed_videos()
        if isinstance(listed, list):
            candidates.extend(str(item) for item in listed if item)
    except Exception as e:
        logger.warning("Search hydration could not list processed videos error=%s", e)

    if video_id and (not candidates or str(video_id) in candidates):
        candidates.insert(0, str(video_id))

    seen: set[str] = set()
    target = str(scene_id)
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            temporal_index = loader.load_temporal_index(candidate)
        except Exception as e:
            logger.warning("Search hydration temporal load failed video_id=%s error=%s", candidate, e)
            continue
        if not isinstance(temporal_index, dict):
            continue
        segments = temporal_index.get("segments")
        if not isinstance(segments, list):
            continue
        for segment in segments:
            if isinstance(segment, dict) and str(segment.get("scene_id")) == target:
                return candidate, segment

    return None, None


def _hydrate_search_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach persisted scene truth to a vector hit when the temporal index can prove it."""
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    scene_id = payload.get("scene_id")
    if scene_id is None:
        return result

    try:
        loader = get_data_loader()
        canonical_video_id, segment = _find_temporal_scene(loader, scene_id, payload.get("video_id"))
    except Exception as e:
        logger.warning("Search hydration skipped scene_id=%s error=%s", scene_id, e)
        return result

    if not canonical_video_id or not isinstance(segment, dict):
        return result

    hydrated_payload = dict(payload)
    hydrated_payload["video_id"] = canonical_video_id
    hydrated_payload["scene_id"] = segment.get("scene_id", scene_id)
    if not _value_present(hydrated_payload.get("timestamp")):
        hydrated_payload["timestamp"] = segment.get("start")
    if not _value_present(hydrated_payload.get("representative_frame")):
        hydrated_payload["representative_frame"] = _frame_name(segment.get("representative_frame"))
    if not _value_present(hydrated_payload.get("transcript")):
        hydrated_payload["transcript"] = (
            segment.get("full_transcript")
            or segment.get("transcript")
            or payload.get("text_preview")
        )
    if not _value_present(hydrated_payload.get("keywords")):
        hydrated_payload["keywords"] = segment.get("keywords", [])
    if not _value_present(hydrated_payload.get("objects")):
        hydrated_payload["objects"] = _segment_object_labels(segment)
    for field_name in ("sentiment", "sentiment_label", "sentiment_score"):
        if not _value_present(hydrated_payload.get(field_name)):
            hydrated_payload[field_name] = segment.get(field_name)

    context = result.get("scene_context") if isinstance(result.get("scene_context"), dict) else {}
    hydrated_context = dict(context)
    hydrated_context.setdefault("video_id", canonical_video_id)
    hydrated_context.setdefault("scene_id", hydrated_payload["scene_id"])
    if _value_present(hydrated_payload.get("transcript")):
        hydrated_context.setdefault("transcript", hydrated_payload["transcript"])
    if _value_present(hydrated_payload.get("objects")):
        hydrated_context.setdefault("objects", hydrated_payload["objects"])
    for field_name in _SEARCH_CONTEXT_FIELDS:
        value = segment.get(field_name)
        if _value_present(value):
            hydrated_context.setdefault(field_name, value)

    provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    hydrated_provenance = dict(provenance)
    hydrated_provenance.setdefault("hydrated_from", "temporal_index")
    hydrated_provenance.setdefault("canonical_video_id", canonical_video_id)

    enriched = dict(result)
    enriched["payload"] = hydrated_payload
    enriched["scene_context"] = hydrated_context or None
    enriched["provenance"] = hydrated_provenance
    return enriched


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
            result = _hydrate_search_result(result)
            payload = result.get('payload', {})
            sentiment_fields = _extract_sentiment_fields(result)
            
            search_result = SearchResult(
                score=result.get('score', 0.0),
                modality=result.get('modality', 'unknown'),
                video_id=payload.get('video_id'),
                scene_id=payload.get('scene_id'),
                timestamp=payload.get('timestamp'),
                representative_frame=payload.get('representative_frame'),
                transcript=payload.get('transcript'),
                keywords=payload.get('keywords', []),
                objects=payload.get('objects', []),
                sentiment=sentiment_fields["sentiment"],
                sentiment_label=sentiment_fields["sentiment_label"],
                sentiment_score=sentiment_fields["sentiment_score"],
                context=result.get('scene_context'),
                provenance=result.get("provenance") if isinstance(result.get("provenance"), dict) else None,
                confidence=result.get("confidence") if isinstance(result.get("confidence"), dict) else default_confidence_payload(),
            )
            
            search_results.append(search_result)
        
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
            result = _hydrate_search_result(result)
            payload = result.get('payload', {})
            sentiment_fields = _extract_sentiment_fields(result)
            
            search_result = SearchResult(
                score=result.get('score', 0.0),
                modality='text',
                video_id=payload.get('video_id'),
                scene_id=payload.get('scene_id'),
                transcript=payload.get('transcript'),
                keywords=payload.get('keywords', []),
                sentiment=sentiment_fields["sentiment"],
                sentiment_label=sentiment_fields["sentiment_label"],
                sentiment_score=sentiment_fields["sentiment_score"],
                provenance=result.get("provenance") if isinstance(result.get("provenance"), dict) else None,
                confidence=result.get("confidence") if isinstance(result.get("confidence"), dict) else default_confidence_payload(),
            )
            
            search_results.append(search_result)
        
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
            result = _hydrate_search_result(result)
            payload = result.get('payload', {})
            sentiment_fields = _extract_sentiment_fields(result)
            
            search_result = SearchResult(
                score=result.get('score', 0.0),
                modality='visual',
                video_id=payload.get('video_id'),
                scene_id=payload.get('scene_id'),
                representative_frame=payload.get('representative_frame'),
                objects=payload.get('objects', []),
                keywords=payload.get('keywords', []),
                sentiment=sentiment_fields["sentiment"],
                sentiment_label=sentiment_fields["sentiment_label"],
                sentiment_score=sentiment_fields["sentiment_score"],
                provenance=result.get("provenance") if isinstance(result.get("provenance"), dict) else None,
                confidence=result.get("confidence") if isinstance(result.get("confidence"), dict) else default_confidence_payload(),
            )
            
            search_results.append(search_result)
        
        return SearchResponse(
            query=q,
            total_results=len(search_results),
            results=search_results,
            modalities_searched=['visual']
        )
        
    except Exception as e:
        logger.error(f"Visual search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Visual search failed: {str(e)}")
