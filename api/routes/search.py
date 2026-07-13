"""
Search API routes for GoodQ4All.
Provides multimodal search endpoints.
"""
from __future__ import annotations
import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse
import uuid

from fastapi import APIRouter, BackgroundTasks, Query, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from api.utils.response_models import SearchResponse, SearchResult, default_confidence_payload
from api.utils.loaders import DataLoader
from api.utils.media_projection import representative_frame_projection
from api.utils.action_jobs import ActionJobLedger, ActionJobTransitionError
from api.utils.temporal_summary_results import (
    TemporalSummaryResultConflict,
    TemporalSummaryResultStore,
)
from api.routes.runtime import (
    _audio_qdrant_collection_candidates,
    _evaluate_qdrant_audio_payloads,
    _scroll_qdrant_audio_payloads,
)
from retrieval.multimodal_search import MultimodalSearchEngine
from lib.llm_client import ModelConfig
from steps.common.config_loader import load_configs
from steps.common.llm_model_factory import build_llm_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# Global instances
_search_engine = None
_data_loader = None
_config = None


def configure_search_from_cfg(cfg: Dict[str, Any]) -> None:
    """Configure search config from canonical runtime config."""
    global _config
    _config = cfg


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
        "audio_emotion_ranking": _list_dicts(segment.get("audio_emotion_ranking")),
        "audio_emotion_top_candidate": segment.get("audio_emotion_top_candidate")
        if isinstance(segment.get("audio_emotion_top_candidate"), dict)
        else None,
        "audio_emotion_promotion_threshold": segment.get("audio_emotion_promotion_threshold"),
        "text_emotion_ranking": _list_dicts(segment.get("text_emotion_ranking")),
        "text_emotion_meta": segment.get("text_emotion_meta") if isinstance(segment.get("text_emotion_meta"), dict) else None,
        "clap_meta": segment.get("clap_meta") if isinstance(segment.get("clap_meta"), dict) else None,
        "sentiment": segment.get("sentiment") if isinstance(segment.get("sentiment"), dict) else None,
        "sentiment_label": segment.get("sentiment_label"),
        "sentiment_score": segment.get("sentiment_score"),
        "sentiment_meta": segment.get("sentiment_meta") if isinstance(segment.get("sentiment_meta"), dict) else None,
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
                "audio_emotion_ranking": _list_dicts(segment.get("audio_emotion_ranking")),
                "audio_emotion_top_candidate": segment.get("audio_emotion_top_candidate")
                if isinstance(segment.get("audio_emotion_top_candidate"), dict)
                else None,
                "audio_emotion_promotion_threshold": segment.get("audio_emotion_promotion_threshold"),
                "text_emotion_ranking": _list_dicts(segment.get("text_emotion_ranking")),
                "text_emotion_meta": segment.get("text_emotion_meta") if isinstance(segment.get("text_emotion_meta"), dict) else None,
                "clap_meta": segment.get("clap_meta") if isinstance(segment.get("clap_meta"), dict) else None,
                "sentiment": context.get("sentiment"),
                "sentiment_label": context.get("sentiment_label"),
                "sentiment_score": context.get("sentiment_score"),
                "sentiment_meta": context.get("sentiment_meta"),
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

    collection_proof = _evaluate_qdrant_audio_payloads(payloads, scene_ids=scene_ids, video_ids=video_ids)
    result_payloads = [
        item
        for item in payloads
        if isinstance(item, dict)
        and (not scene_ids or str(item.get("scene_id") or "").strip() in scene_ids)
        and (
            not video_ids
            or str(item.get("video_id") or item.get("video_hash") or "").strip() in video_ids
        )
    ]
    proof = _evaluate_qdrant_audio_payloads(result_payloads, scene_ids=scene_ids, video_ids=video_ids)
    current_run_proven = int(proof.get("current_run_qdrant_proven") or 0)
    base = {
        "status": "current_run_audio_vector_proven" if current_run_proven else "no_current_run_evidence",
        "label": "Proven" if current_run_proven else "No Current-Run Evidence",
        "proof_scope": "retrieval_result_scene",
        "runtime_run_id": runtime_run_id,
        "collection": qdrant_result.get("collection"),
        "collection_candidates": collection_candidates,
        "qdrant_run_matched_points": len(payloads),
        "qdrant_result_candidate_points": len(result_payloads),
        "reason": "run_matched_payloads_satisfy_contract" if current_run_proven else "no_qdrant_payloads_matched_scene",
        "collection_scope": {
            "qdrant_run_matched_points": len(payloads),
            "current_run_qdrant_proven": int(collection_proof.get("current_run_qdrant_proven") or 0),
            "scene_mismatch_count": int(collection_proof.get("scene_mismatch_count") or 0),
            "video_mismatch_count": int(collection_proof.get("video_mismatch_count") or 0),
            "required_fields_missing_count": int(collection_proof.get("required_fields_missing_count") or 0),
        },
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


def _safe_modality_scores(result: dict) -> Dict[str, float]:
    raw = result.get("modality_scores")
    if not isinstance(raw, dict):
        return {}
    scores: Dict[str, float] = {}
    for key, value in raw.items():
        number = _safe_number(value)
        if key is not None and number is not None:
            scores[str(key)] = number
    return scores


def _safe_modalities(result: dict) -> List[str]:
    raw = result.get("modalities")
    if isinstance(raw, list):
        values = [str(item) for item in raw if item is not None and str(item).strip()]
        if values:
            return values
    modality = result.get("modality")
    return [str(modality)] if modality is not None and str(modality).strip() else []


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
    loader = get_data_loader()
    phase6_complete = False
    if video_id:
        try:
            metadata = loader.get_video_metadata(str(video_id))
            phase6_complete = bool(metadata.get('phase6_complete', False))
        except Exception:
            pass

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
        modalities=_safe_modalities(result),
        modality_scores=_safe_modality_scores(result),
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
        audio_emotion_ranking=enrichment.get("audio_emotion_ranking") or [],
        audio_emotion_top_candidate=enrichment.get("audio_emotion_top_candidate"),
        audio_emotion_promotion_threshold=enrichment.get("audio_emotion_promotion_threshold"),
        text_emotion_ranking=enrichment.get("text_emotion_ranking") or [],
        text_emotion_meta=enrichment.get("text_emotion_meta"),
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
        sentiment_meta=enrichment.get("sentiment_meta"),
        context=_sanitize_read_model_mapping(context),
        scene_context_llm=enrichment.get("scene_context_llm"),
        scene_context_epistemic=enrichment.get("scene_context_epistemic"),
        scene_context_arbitration=enrichment.get("scene_context_arbitration"),
        provenance=_sanitize_read_model_mapping(provenance),
        confidence=_enriched_confidence(result, enrichment),
        phase6_complete=phase6_complete,
    )


def get_search_engine():
    """Lazy-load search engine."""
    global _search_engine, _config
    
    if _search_engine is None:
        if _config is None:
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
            modalities=request.modalities,
            retrieval_context="human.ui.search",
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
            },
            diagnostics=engine.last_search_diagnostics() if hasattr(engine, "last_search_diagnostics") else None,
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
        
        results = engine.search_text(
            q,
            top_k=top_k,
            retrieval_context="human.ui.search",
        )
        
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
        
        results = engine.search_visual(
            q,
            top_k=top_k,
            retrieval_context="human.ui.search",
        )
        
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


class TemporalSearchRequest(BaseModel):
    entities: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time_hint: Optional[str] = None
    source_file: Optional[str] = None
    modality: Optional[List[str]] = None
    max_results: int = 25
    grouping: str = "semantic_episode"


class TemporalSearchQueryInfo(BaseModel):
    entities: List[str]
    grouping: str


class TemporalEvidence(BaseModel):
    transcript: str
    visual_tags: List[str]
    artifact_paths: List[str]


class TemporalSearchResult(BaseModel):
    scene_id: str
    source_file: str
    start_time: float
    end_time: float
    timestamp_label: str
    entities: List[str]
    summary: str
    evidence: TemporalEvidence
    temporal_distance_from_previous: float
    semantic_similarity_from_previous: float


class TemporalSearchResponse(BaseModel):
    query: TemporalSearchQueryInfo
    results: List[TemporalSearchResult]


@router.post("/temporal", response_model=TemporalSearchResponse)
async def search_temporal(request: TemporalSearchRequest = Body(...)):
    """
    Execute chronological narrative search.
    """
    try:
        from retrieval.temporal_reasoning import temporal_search
        
        result_dict = temporal_search(
            entities=request.entities,
            start_date=request.start_date,
            end_date=request.end_date,
            time_hint=request.time_hint,
            source_file=request.source_file,
            modality=request.modality,
            max_results=request.max_results,
            grouping=request.grouping,
        )
        return result_dict
    except Exception as e:
        logger.error(f"Temporal search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Temporal search failed: {str(e)}")


_TEMPORAL_SUMMARY_JOB_OPERATION = "temporal_summary.generate"
_TEMPORAL_SUMMARY_AUTH_OPERATION = "generate_temporal_summary"
_TEMPORAL_SUMMARY_OWNER_INSTANCE = f"temporal-summary-api-{uuid.uuid4().hex}"
_TEMPORAL_JOB_ID_RE = re.compile(r"job_[0-9a-f]{32}")
_TEMPORAL_EPOCH_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")
_TEMPORAL_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TEMPORAL_AUTH_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_TEMPORAL_WARNING_CODE_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
_TEMPORAL_PREEXECUTION_FAILURE_CODES = frozenset(
    {
        "authorization_evidence_invalid",
        "authorization_failed",
        "authorization_interrupted",
        "authorization_prepare_failed",
        "job_scope_invalid",
    }
)


class TemporalSummarizeRequest(BaseModel):
    """One deterministic private request, never persisted in an action job."""

    model_config = ConfigDict(extra="forbid", strict=True)

    entities: Optional[List[str]] = Field(default=None, max_length=64)
    start_date: Optional[str] = Field(default=None, max_length=10)
    end_date: Optional[str] = Field(default=None, max_length=10)
    time_hint: Optional[str] = Field(default=None, max_length=512)
    source_file: Optional[str] = Field(default=None, max_length=255)
    modality: Optional[List[str]] = Field(default=None, max_length=3)
    max_results: int = Field(default=25, ge=1, le=100)
    grouping: Literal["semantic_episode"] = "semantic_episode"
    summary_style: Literal["narrative", "bullets", "executive"] = "narrative"

    @field_validator("entities")
    @classmethod
    def _validate_entities(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Temporal summary entities must be strings")
            cleaned = item.strip()
            identity = cleaned.casefold()
            if not cleaned or len(cleaned) > 128 or identity in seen:
                raise ValueError("Temporal summary entities are invalid")
            normalized.append(cleaned)
            seen.add(identity)
        return normalized or None

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_date_hint(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", cleaned) is None:
            raise ValueError("Temporal summary date is invalid")
        try:
            year = int(cleaned[:4])
            if len(cleaned) == 7:
                datetime.fromisoformat(f"{cleaned}-01")
            elif len(cleaned) == 10:
                datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError("Temporal summary date is invalid") from exc
        if not 1800 <= year <= 2200:
            raise ValueError("Temporal summary date is outside the supported range")
        return cleaned

    @field_validator("time_hint")
    @classmethod
    def _validate_time_hint(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("source_file")
    @classmethod
    def _validate_source_file(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if (
            not cleaned
            or cleaned in {".", ".."}
            or "/" in cleaned
            or "\\" in cleaned
            or ":" in cleaned
        ):
            raise ValueError("Temporal summary source file must be a basename")
        return cleaned

    @field_validator("modality")
    @classmethod
    def _validate_modality(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        allowed = {"audio", "text", "visual"}
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or item not in allowed or item in normalized:
                raise ValueError("Temporal summary modality is invalid")
            normalized.append(item)
        return normalized or None


@dataclass
class _FixedEndpointModelConfig(ModelConfig):
    fixed_endpoint: str = ""

    @property
    def endpoint(self) -> str:
        return self.fixed_endpoint


@dataclass(frozen=True)
class _TemporalExecutionSnapshot:
    epoch_id: str
    execution_policy_sha256: str
    models: tuple[_FixedEndpointModelConfig, ...]
    allow_service_activation: bool
    allow_environment_proxies: bool


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _parse_temporal_summary_action_body(
    body: object,
) -> tuple[str, dict[str, Any], bytes, str]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Invalid temporal summary action body")
    action = body.get("action")
    expected_fields = (
        {"action", "request"}
        if action == "prepare"
        else {
            "action",
            "job_id",
            "epoch_id",
            "request_sha256",
            "execution_policy_sha256",
            "confirmation_token",
            "request",
        }
        if action == "confirm"
        else set()
    )
    if set(body) != expected_fields:
        raise HTTPException(status_code=422, detail="Invalid temporal summary action body")
    try:
        request = TemporalSummarizeRequest.model_validate(body.get("request"))
        normalized = request.model_dump(mode="json", exclude_none=False)
        if (
            normalized["start_date"] is not None
            and normalized["end_date"] is not None
            and normalized["start_date"] > normalized["end_date"]
        ):
            raise ValueError("Temporal summary date range is invalid")
        request_bytes = _canonical_json_bytes(normalized)
    except (ValidationError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid temporal summary request")

    if action == "confirm" and (
        not isinstance(body.get("job_id"), str)
        or _TEMPORAL_JOB_ID_RE.fullmatch(body["job_id"]) is None
        or not isinstance(body.get("epoch_id"), str)
        or _TEMPORAL_EPOCH_ID_RE.fullmatch(body["epoch_id"]) is None
        or not isinstance(body.get("request_sha256"), str)
        or _TEMPORAL_SHA256_RE.fullmatch(body["request_sha256"]) is None
        or not isinstance(body.get("execution_policy_sha256"), str)
        or _TEMPORAL_SHA256_RE.fullmatch(body["execution_policy_sha256"]) is None
        or not isinstance(body.get("confirmation_token"), str)
        or not body["confirmation_token"]
        or body["confirmation_token"] != body["confirmation_token"].strip()
    ):
        raise HTTPException(status_code=422, detail="Invalid temporal summary action body")
    return action, normalized, request_bytes, hashlib.sha256(request_bytes).hexdigest()


def _temporal_summary_job_root(cfg: dict[str, Any]) -> Path:
    data_root = cfg.get("paths", {}).get("data_root")
    if not isinstance(data_root, str) or not data_root.strip():
        raise ValueError("GoodQ data root is not configured")
    return Path(data_root) / "control" / "action_jobs"


def _temporal_summary_result_root(cfg: dict[str, Any]) -> Path:
    data_root = cfg.get("paths", {}).get("data_root")
    if not isinstance(data_root, str) or not data_root.strip():
        raise ValueError("GoodQ data root is not configured")
    return Path(data_root) / "control" / "temporal_summary_results"


def _temporal_summary_result_root_from_job_root(job_root: Path) -> Path:
    if job_root.name != "action_jobs" or job_root.parent.name != "control":
        raise ValueError("Temporal summary job root is invalid")
    return job_root.parent / "temporal_summary_results"


def _temporal_summary_scope(
    *,
    epoch_id: str,
    request_sha256: str,
    execution_policy_sha256: str,
) -> dict[str, str]:
    return {
        "epoch_id": epoch_id,
        "request_sha256": request_sha256,
        "execution_policy_sha256": execution_policy_sha256,
    }


def _temporal_scope_from_record(record: dict[str, Any]) -> dict[str, str]:
    scope = record.get("scope")
    if (
        not isinstance(scope, dict)
        or set(scope)
        != {"epoch_id", "request_sha256", "execution_policy_sha256"}
        or not isinstance(scope.get("epoch_id"), str)
        or _TEMPORAL_EPOCH_ID_RE.fullmatch(scope["epoch_id"]) is None
        or not isinstance(scope.get("request_sha256"), str)
        or _TEMPORAL_SHA256_RE.fullmatch(scope["request_sha256"]) is None
        or not isinstance(scope.get("execution_policy_sha256"), str)
        or _TEMPORAL_SHA256_RE.fullmatch(scope["execution_policy_sha256"]) is None
    ):
        raise ValueError("Persisted temporal summary job scope is invalid")
    return scope


def _local_fixed_endpoint(model: ModelConfig) -> str:
    parsed = urlparse(str(model.base_url))
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Temporal summary model endpoint is invalid")
    try:
        local = host.casefold() == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    if not local or not isinstance(model.port, int) or not 1 <= model.port <= 65535:
        raise ValueError("Temporal summary model endpoint must be loopback-only")
    display_host = f"[{host}]" if ":" in host else host
    return f"{parsed.scheme}://{display_host}:{model.port}/v1"


def _resolve_temporal_execution_snapshot(
    cfg: dict[str, Any],
) -> _TemporalExecutionSnapshot:
    paths = cfg.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("Temporal summary paths are not configured")
    db_path = paths.get("db_path")
    kg_path = paths.get("knowledge_graph_db")
    if (
        not isinstance(db_path, str)
        or not db_path.strip()
        or not isinstance(kg_path, str)
        or not kg_path.strip()
    ):
        raise ValueError("Temporal summary epoch paths are not configured")
    db_epoch = Path(db_path).parent.name
    kg_epoch = Path(kg_path).parent.name
    if (
        db_epoch != kg_epoch
        or _TEMPORAL_EPOCH_ID_RE.fullmatch(db_epoch) is None
    ):
        raise ValueError("Temporal summary epoch paths are inconsistent")

    llm_cfg = cfg.get("llm")
    if not isinstance(llm_cfg, dict):
        raise ValueError("Temporal summary model policy is not configured")
    temporal_cfg = llm_cfg.get("temporal_summary", {})
    if not isinstance(temporal_cfg, dict):
        raise ValueError("Temporal summary model policy is invalid")
    allow_activation = temporal_cfg.get("allow_service_activation", False)
    if not isinstance(allow_activation, bool):
        raise ValueError("Temporal summary activation policy is invalid")

    resolved_models: list[_FixedEndpointModelConfig] = []
    policy_models: list[dict[str, Any]] = []
    for model in build_llm_models(cfg):
        if model.backend not in {"ollama", "vllm"}:
            raise ValueError("Temporal summary model backend is invalid")
        endpoint = _local_fixed_endpoint(model)
        capabilities = sorted(set(str(item) for item in model.capabilities))
        fixed = _FixedEndpointModelConfig(
            name=str(model.name),
            base_url=str(model.base_url),
            port=int(model.port),
            model_id=str(model.model_id),
            backend=model.backend,
            vram_gb=float(model.vram_gb),
            tokens_per_sec=int(model.tokens_per_sec),
            context_length=int(model.context_length),
            capabilities=capabilities,
            priority=int(model.priority),
            fixed_endpoint=endpoint,
        )
        resolved_models.append(fixed)
        policy_models.append(
            {
                "name": fixed.name,
                "model_id": fixed.model_id,
                "backend": fixed.backend,
                "endpoint": fixed.endpoint,
                "vram_gb": fixed.vram_gb,
                "tokens_per_sec": fixed.tokens_per_sec,
                "context_length": fixed.context_length,
                "capabilities": capabilities,
                "priority": fixed.priority,
            }
        )
    if not resolved_models:
        raise ValueError("Temporal summary model policy has no candidates")
    policy_sha256 = _canonical_sha256(
        {
            "models": policy_models,
            "allow_service_activation": allow_activation,
            "allow_environment_proxies": False,
        }
    )
    return _TemporalExecutionSnapshot(
        epoch_id=db_epoch,
        execution_policy_sha256=policy_sha256,
        models=tuple(resolved_models),
        allow_service_activation=allow_activation,
        allow_environment_proxies=False,
    )


def _get_temporal_summary_authority(_cfg: dict[str, Any]):
    from agents.mini_agent_client import MiniAgentClient

    return MiniAgentClient(profile="safe")


def _public_temporal_summary_job(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "job_id",
            "operation",
            "scope",
            "state",
            "created_at_utc",
            "updated_at_utc",
            "outcome",
            "audit_status",
        )
    }


def _temporal_authorization_error_code(envelope: object) -> str:
    if isinstance(envelope, dict) and isinstance(envelope.get("errors"), list):
        for error in envelope["errors"]:
            if isinstance(error, dict) and isinstance(error.get("code"), str):
                return error["code"]
    return "authorization_failed"


def _has_complete_temporal_authorization(record: dict[str, Any]) -> bool:
    return (
        isinstance(record.get("token_fingerprint"), str)
        and _TEMPORAL_SHA256_RE.fullmatch(record["token_fingerprint"]) is not None
        and isinstance(record.get("authorization_request_id"), str)
        and _TEMPORAL_AUTH_REQUEST_ID_RE.fullmatch(
            record["authorization_request_id"]
        )
        is not None
    )


def _record_temporal_summary_outcome(
    cfg: dict[str, Any],
    *,
    record: dict[str, Any],
    status: Literal["succeeded", "failed", "interrupted"],
    mutated: bool,
    duration_ms: int,
    error_codes: list[str],
) -> str:
    scope = _temporal_scope_from_record(record)
    try:
        audit = _get_temporal_summary_authority(cfg).record_external_execution_outcome(
            operation=_TEMPORAL_SUMMARY_AUTH_OPERATION,
            arguments={"job_id": record["job_id"], **scope},
            request_id=str(record.get("authorization_request_id") or ""),
            mode="ops",
            status=status,
            return_code=0 if status == "succeeded" else 1,
            duration_ms=duration_ms,
            side_effect_report={
                "mutated": mutated,
                "targets": [f"temporal-summary:{record['job_id']}"],
            },
            error_codes=error_codes,
        )
        if isinstance(audit, dict) and audit.get("audit_status") == "recorded":
            return "recorded"
    except Exception:
        logger.error(
            "Temporal summary external audit failed for job %s",
            record.get("job_id"),
        )
    return "failed"


def _temporal_model_evidence(
    result: dict[str, Any],
    models: tuple[_FixedEndpointModelConfig, ...],
) -> dict[str, str] | None:
    if result.get("source_count") == 0:
        return None
    used = result.get("model_used")
    for model in models:
        if used == model.name:
            return {"model_id": model.model_id, "provider": model.backend}
    raise ValueError("Temporal summary model evidence is invalid")


def _temporal_success_projection(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("status") != "success":
        raise ValueError("Temporal summary result did not succeed")
    source_ids = result.get("source_scene_ids")
    if not isinstance(source_ids, list):
        raise ValueError("Temporal summary source evidence is invalid")
    segments = result.get("segments") or []
    if not isinstance(segments, list):
        raise ValueError("Temporal summary segments are invalid")
    projected_segments: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("Temporal summary segment is invalid")
        projected_segments.append(
            {
                "scene_index": segment.get("scene_index"),
                "scene_id": segment.get("scene_id"),
                "text": segment.get("text"),
                "start_time": segment.get("start_time"),
                "end_time": segment.get("end_time"),
            }
        )
    warnings = result.get("warnings")
    if (
        not isinstance(warnings, list)
        or any(
            not isinstance(code, str)
            or _TEMPORAL_WARNING_CODE_RE.fullmatch(code) is None
            for code in warnings
        )
    ):
        raise ValueError("Temporal summary warning codes are invalid")
    return {
        "summary": result.get("summary"),
        "segments": projected_segments,
        "source_scene_ids": source_ids,
        "source_count": result.get("source_count"),
        "truncated": result.get("truncated"),
        "warning_codes": warnings,
    }


def _temporal_failure_code(result: object) -> str:
    if isinstance(result, dict) and isinstance(result.get("warnings"), list):
        for code in result["warnings"]:
            if isinstance(code, str) and _TEMPORAL_WARNING_CODE_RE.fullmatch(code):
                return code
    return "temporal_summary_failed"


async def _temporal_summary_worker(
    job_id: str,
    request_bytes: bytes,
    job_root: Path,
) -> None:
    ledger = ActionJobLedger(job_root)
    try:
        candidate = ledger.load(job_id)
    except (OSError, ValueError, json.JSONDecodeError):
        logger.error("Temporal summary worker could not inspect job %s", job_id)
        return
    if candidate is None or candidate.get("operation") != _TEMPORAL_SUMMARY_JOB_OPERATION:
        logger.error("Temporal summary worker rejected unrelated job %s", job_id)
        return
    try:
        scope = _temporal_scope_from_record(candidate)
    except ValueError:
        logger.error("Temporal summary worker rejected invalid job scope %s", job_id)
        try:
            ledger.transition(
                job_id,
                expected_states="queued",
                new_state="failed",
                outcome={
                    "code": "job_scope_invalid",
                    "message": "Temporal summary job scope is invalid",
                },
                audit_status="failed",
            )
        except Exception:
            logger.error("Temporal summary invalid scope state was not recorded for job %s", job_id)
        return
    if not _has_complete_temporal_authorization(candidate):
        logger.error("Temporal summary worker rejected incomplete authorization for job %s", job_id)
        try:
            ledger.transition(
                job_id,
                expected_states="queued",
                new_state="failed",
                outcome={
                    "code": "authorization_evidence_invalid",
                    "message": "Temporal summary authorization evidence is invalid",
                },
                audit_status="failed",
            )
        except Exception:
            logger.error("Temporal summary invalid authorization state was not recorded for job %s", job_id)
        return
    try:
        record = ledger.transition(
            job_id,
            expected_states="queued",
            new_state="running",
        )
    except (ActionJobTransitionError, FileNotFoundError, ValueError):
        logger.warning("Temporal summary worker could not claim queued job %s", job_id)
        return

    started_at_utc = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    result_store = TemporalSummaryResultStore(
        _temporal_summary_result_root_from_job_root(job_root)
    )

    snapshot: _TemporalExecutionSnapshot | None = None
    cfg: dict[str, Any] | None = None
    failure_code: str | None = None
    narrative_result: dict[str, Any] | None = None
    normalized_request: dict[str, Any] | None = None
    try:
        normalized_request = json.loads(request_bytes.decode("utf-8"))
        if not isinstance(normalized_request, dict):
            raise ValueError("Temporal summary request is not an object")
        if hashlib.sha256(request_bytes).hexdigest() != scope["request_sha256"]:
            raise ValueError("Temporal summary request digest changed")
        cfg = copy.deepcopy(load_configs({}))
        if _temporal_summary_job_root(cfg).resolve() != job_root.resolve():
            raise ValueError("Temporal summary runtime root changed")
        snapshot = _resolve_temporal_execution_snapshot(cfg)
        if (
            snapshot.epoch_id != scope["epoch_id"]
            or snapshot.execution_policy_sha256
            != scope["execution_policy_sha256"]
        ):
            raise ValueError("Temporal summary execution scope changed")

    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        logger.error("Temporal summary execution scope failed for job %s", job_id)
        failure_code = "execution_scope_changed"
    except Exception:
        logger.error("Temporal summary execution snapshot failed for job %s", job_id)
        failure_code = "execution_snapshot_unavailable"

    if failure_code is None and normalized_request is not None and cfg is not None and snapshot is not None:
        try:
            from functools import partial
            from retrieval.narrative_summarizer import synthesize_narrative

            call = partial(
                synthesize_narrative,
                **normalized_request,
                config=cfg,
                expected_epoch_id=snapshot.epoch_id,
                models=list(snapshot.models),
                allow_model_activation=snapshot.allow_service_activation,
                allow_environment_proxies=snapshot.allow_environment_proxies,
            )
            narrative_result = await asyncio.get_running_loop().run_in_executor(None, call)
            if not isinstance(narrative_result, dict) or narrative_result.get("status") != "success":
                failure_code = _temporal_failure_code(narrative_result)
        except Exception:
            logger.error("Temporal summary execution failed for job %s", job_id)
            failure_code = "temporal_summary_error"

    receipt: dict[str, Any]
    try:
        if failure_code is None and narrative_result is not None and snapshot is not None:
            receipt = result_store.write_success(
                job_id=job_id,
                epoch_id=scope["epoch_id"],
                request_sha256=scope["request_sha256"],
                execution_policy_sha256=scope["execution_policy_sha256"],
                started_at_utc=started_at_utc,
                result=_temporal_success_projection(narrative_result),
                model_evidence=_temporal_model_evidence(
                    narrative_result,
                    snapshot.models,
                ),
            )
        else:
            receipt = result_store.write_failure(
                job_id=job_id,
                epoch_id=scope["epoch_id"],
                request_sha256=scope["request_sha256"],
                execution_policy_sha256=scope["execution_policy_sha256"],
                started_at_utc=started_at_utc,
                error_code=failure_code or "temporal_summary_failed",
            )
    except ValueError:
        logger.error("Temporal summary result projection was rejected for job %s", job_id)
        try:
            receipt = result_store.write_failure(
                job_id=job_id,
                epoch_id=scope["epoch_id"],
                request_sha256=scope["request_sha256"],
                execution_policy_sha256=scope["execution_policy_sha256"],
                started_at_utc=started_at_utc,
                error_code="result_projection_invalid",
            )
        except Exception:
            logger.error("Temporal summary projection failure could not be persisted for job %s", job_id)
            return
    except Exception:
        logger.error("Temporal summary result could not be persisted for job %s", job_id)
        return

    succeeded = receipt["terminal_state"] == "succeeded"
    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    error_codes = [] if succeeded else [str(receipt["error_code"])]
    audit_status = _record_temporal_summary_outcome(
        cfg or {},
        record=record,
        status="succeeded" if succeeded else "failed",
        mutated=True,
        duration_ms=duration_ms,
        error_codes=error_codes,
    )
    try:
        ledger.transition(
            job_id,
            expected_states="running",
            new_state="succeeded" if succeeded else "failed",
            outcome={
                "code": "temporal_summary_generated" if succeeded else str(receipt["error_code"]),
                "message": (
                    "Temporal summary generation succeeded"
                    if succeeded
                    else "Temporal summary generation failed"
                ),
            },
            audit_status=audit_status,
        )
    except (ActionJobTransitionError, FileNotFoundError, ValueError):
        logger.error("Temporal summary terminal state could not be persisted for job %s", job_id)


def _reconcile_temporal_summary_jobs(cfg: dict[str, Any]) -> None:
    job_root = _temporal_summary_job_root(cfg)
    if not job_root.exists():
        return
    ledger = ActionJobLedger(job_root)
    result_store = TemporalSummaryResultStore(_temporal_summary_result_root(cfg))
    records = ledger.list_prior_owner_records(
        current_owner_instance=_TEMPORAL_SUMMARY_OWNER_INSTANCE,
        states={"pending_confirmation", "authorizing", "queued", "running"},
    )
    for record in records:
        if record.get("operation") != _TEMPORAL_SUMMARY_JOB_OPERATION:
            continue
        job_id = str(record.get("job_id") or "")
        state = str(record.get("state") or "")
        scope = _temporal_scope_from_record(record)
        receipt_path_exists = result_store.record_path(job_id).is_file()
        if state in {"pending_confirmation", "authorizing"}:
            if receipt_path_exists:
                raise RuntimeError("Temporal summary receipt precedes authorization claim")
            if _has_complete_temporal_authorization(record):
                continue
            ledger.transition(
                job_id,
                expected_states=state,
                new_state="failed",
                outcome={
                    "code": "authorization_interrupted",
                    "message": "Temporal summary authorization was interrupted by restart",
                },
            )
            continue

        if not _has_complete_temporal_authorization(record):
            raise RuntimeError("Temporal summary authorization evidence is incomplete")
        receipt = result_store.load_exact(job_id=job_id, **scope)
        if receipt is not None:
            if not _has_complete_temporal_authorization(record):
                raise RuntimeError("Temporal summary authorization evidence is incomplete")
            if state == "queued":
                record = ledger.transition(
                    job_id,
                    expected_states="queued",
                    new_state="running",
                )
            succeeded = receipt["terminal_state"] == "succeeded"
            audit_status = _record_temporal_summary_outcome(
                cfg,
                record=record,
                status="succeeded" if succeeded else "failed",
                mutated=True,
                duration_ms=0,
                error_codes=[] if succeeded else [str(receipt["error_code"])],
            )
            ledger.transition(
                job_id,
                expected_states="running",
                new_state="succeeded" if succeeded else "failed",
                outcome={
                    "code": "temporal_summary_recovered" if succeeded else str(receipt["error_code"]),
                    "message": (
                        "Temporal summary result was recovered from durable evidence"
                        if succeeded
                        else "Temporal summary failure was recovered from durable evidence"
                    ),
                },
                audit_status=audit_status,
            )
            continue

        audit_status = _record_temporal_summary_outcome(
            cfg,
            record=record,
            status="interrupted",
            mutated=False,
            duration_ms=0,
            error_codes=["execution_interrupted"],
        )
        ledger.transition(
            job_id,
            expected_states=state,
            new_state="interrupted",
            outcome={
                "code": "execution_interrupted",
                "message": "Temporal summary execution was interrupted before durable result",
            },
            audit_status=audit_status,
        )


async def _reconcile_temporal_summary_jobs_on_startup() -> None:
    _reconcile_temporal_summary_jobs(copy.deepcopy(load_configs({})))


router.add_event_handler("startup", _reconcile_temporal_summary_jobs_on_startup)


@router.get("/temporal/summarize/{job_id}", response_model=dict)
async def get_temporal_summary_job(job_id: str) -> dict[str, Any]:
    if _TEMPORAL_JOB_ID_RE.fullmatch(job_id) is None:
        raise HTTPException(status_code=404, detail="Temporal summary job not found")
    cfg = copy.deepcopy(load_configs({}))
    job_root = _temporal_summary_job_root(cfg)
    if not job_root.exists():
        raise HTTPException(status_code=404, detail="Temporal summary job not found")
    try:
        record = ActionJobLedger(job_root).load(job_id)
    except ValueError:
        record = None
    if record is None or record.get("operation") != _TEMPORAL_SUMMARY_JOB_OPERATION:
        raise HTTPException(status_code=404, detail="Temporal summary job not found")
    try:
        scope = _temporal_scope_from_record(record)
        receipt = TemporalSummaryResultStore(
            _temporal_summary_result_root(cfg)
        ).load_exact(job_id=job_id, **scope)
    except (RuntimeError, ValueError, TemporalSummaryResultConflict):
        raise HTTPException(
            status_code=409,
            detail={"code": "result_invalid", "job": _public_temporal_summary_job(record)},
        )
    state = record.get("state")
    if state == "succeeded":
        if receipt is None or receipt.get("terminal_state") != "succeeded":
            raise HTTPException(
                status_code=409,
                detail={"code": "result_invalid", "job": _public_temporal_summary_job(record)},
            )
    elif state == "failed":
        outcome = record.get("outcome")
        preexecution_failure = (
            receipt is None
            and isinstance(outcome, dict)
            and outcome.get("code") in _TEMPORAL_PREEXECUTION_FAILURE_CODES
        )
        if not preexecution_failure and (
            receipt is None or receipt.get("terminal_state") != "failed"
        ):
            raise HTTPException(
                status_code=409,
                detail={"code": "result_invalid", "job": _public_temporal_summary_job(record)},
            )
    elif receipt is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "result_invalid", "job": _public_temporal_summary_job(record)},
        )
    return {
        "status": state,
        "job": _public_temporal_summary_job(record),
        "receipt": receipt,
    }


@router.post("/temporal/summarize", response_model=dict)
async def summarize_temporal(
    background_tasks: BackgroundTasks,
    body: object = Body(...),
):
    """Prepare or confirm one exact asynchronous temporal-summary execution."""
    action, _normalized, request_bytes, request_sha256 = (
        _parse_temporal_summary_action_body(body)
    )
    try:
        cfg = copy.deepcopy(load_configs({}))
        snapshot = _resolve_temporal_execution_snapshot(cfg)
        job_root = _temporal_summary_job_root(cfg)
        ledger = ActionJobLedger(job_root)
    except Exception:
        logger.error("Temporal summary authority configuration is unavailable")
        raise HTTPException(status_code=503, detail="Temporal summary authority unavailable")
    scope = _temporal_summary_scope(
        epoch_id=snapshot.epoch_id,
        request_sha256=request_sha256,
        execution_policy_sha256=snapshot.execution_policy_sha256,
    )

    if action == "confirm":
        assert isinstance(body, dict)
        job_id = body["job_id"]
        declared_scope = _temporal_summary_scope(
            epoch_id=body["epoch_id"],
            request_sha256=body["request_sha256"],
            execution_policy_sha256=body["execution_policy_sha256"],
        )
        if declared_scope != scope:
            raise HTTPException(status_code=409, detail="Temporal summary scope changed")
        record = ledger.load(job_id)
        if (
            record is None
            or record.get("operation") != _TEMPORAL_SUMMARY_JOB_OPERATION
            or record.get("scope") != scope
        ):
            raise HTTPException(status_code=404, detail="Temporal summary job not found")
        state = record.get("state")
        if state not in {"pending_confirmation", "authorizing"}:
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_confirmable", "job": _public_temporal_summary_job(record)},
            )
        token = body["confirmation_token"]
        fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not isinstance(record.get("token_fingerprint"), str) or not hmac.compare_digest(
            record["token_fingerprint"], fingerprint
        ):
            raise HTTPException(status_code=403, detail="Confirmation token mismatch")

        recovered_authorizing = False
        owner = record.get("owner_instance")
        if owner != _TEMPORAL_SUMMARY_OWNER_INSTANCE:
            if not _has_complete_temporal_authorization(record):
                raise HTTPException(
                    status_code=409,
                    detail={"code": "job_owner_changed", "job": _public_temporal_summary_job(record)},
                )
            try:
                record = ledger.adopt_owner(
                    job_id,
                    expected_state=state,
                    expected_owner_instance=owner,
                    new_owner_instance=_TEMPORAL_SUMMARY_OWNER_INSTANCE,
                )
            except (ActionJobTransitionError, ValueError):
                current = ledger.load(job_id) or record
                raise HTTPException(
                    status_code=409,
                    detail={"code": "job_owner_changed", "job": _public_temporal_summary_job(current)},
                )
            recovered_authorizing = state == "authorizing"
        elif state == "authorizing":
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_confirmable", "job": _public_temporal_summary_job(record)},
            )

        if state == "pending_confirmation":
            try:
                record = ledger.transition(
                    job_id,
                    expected_states="pending_confirmation",
                    new_state="authorizing",
                )
            except ActionJobTransitionError:
                current = ledger.load(job_id) or record
                raise HTTPException(
                    status_code=409,
                    detail={"code": "job_not_confirmable", "job": _public_temporal_summary_job(current)},
                )

        tool_args = {"job_id": job_id, **scope}
        try:
            envelope, return_code = _get_temporal_summary_authority(cfg).authorize_action(
                prompt="Confirm one exact temporal summary",
                mode="ops",
                tool_name=_TEMPORAL_SUMMARY_AUTH_OPERATION,
                tool_args=tool_args,
                confirm=True,
                confirmation_token=token,
            )
        except Exception:
            logger.error("Temporal summary authorization claim failed")
            envelope, return_code = {}, 1
        result = envelope.get("result") if isinstance(envelope, dict) else None
        response_request_id = (
            envelope.get("request_id") if isinstance(envelope, dict) else None
        )
        request_id_matches = (
            isinstance(response_request_id, str)
            and isinstance(record.get("authorization_request_id"), str)
            and hmac.compare_digest(
                record["authorization_request_id"], response_request_id
            )
        )
        authorized = (
            return_code == 0
            and envelope.get("status") == "ok"
            and isinstance(result, dict)
            and result.get("allowed") is True
            and request_id_matches
        )
        error_code = _temporal_authorization_error_code(envelope)
        if (
            return_code == 0
            and isinstance(result, dict)
            and result.get("allowed") is True
            and not request_id_matches
        ):
            error_code = "authorization_request_mismatch"
        if (
            recovered_authorizing
            and error_code == "token_already_used"
            and request_id_matches
        ):
            authorized = True
        if not authorized:
            expired = error_code == "token_expired"
            try:
                record = ledger.transition(
                    job_id,
                    expected_states="authorizing",
                    new_state="expired" if expired else "failed",
                    outcome={
                        "code": "authorization_expired" if expired else "authorization_failed",
                        "message": (
                            "Temporal summary authorization expired"
                            if expired
                            else "Temporal summary authorization failed"
                        ),
                    },
                )
            except ActionJobTransitionError:
                record = ledger.load(job_id) or record
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "authorization_expired" if expired else "authorization_failed",
                    "job": _public_temporal_summary_job(record),
                },
            )
        try:
            record = ledger.transition(
                job_id,
                expected_states="authorizing",
                new_state="queued",
            )
        except ActionJobTransitionError:
            current = ledger.load(job_id) or record
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_queueable", "job": _public_temporal_summary_job(current)},
            )
        background_tasks.add_task(
            _temporal_summary_worker,
            job_id,
            bytes(request_bytes),
            job_root,
        )
        return JSONResponse(
            status_code=202,
            content={"success": True, "job": _public_temporal_summary_job(record)},
        )

    try:
        record, created = ledger.prepare_or_find_active_with_status(
            operation=_TEMPORAL_SUMMARY_JOB_OPERATION,
            scope=scope,
            owner_instance=_TEMPORAL_SUMMARY_OWNER_INSTANCE,
        )
    except ValueError:
        logger.error("Temporal summary job preparation failed")
        raise HTTPException(status_code=500, detail="Temporal summary job ledger unavailable")
    if not created:
        raise HTTPException(
            status_code=409,
            detail={"code": "active_job_exists", "job": _public_temporal_summary_job(record)},
        )

    authority = None
    token = None
    evidence_persisted = False
    tool_args = {"job_id": record["job_id"], **scope}
    try:
        authority = _get_temporal_summary_authority(cfg)
        envelope, return_code = authority.authorize_action(
            prompt="Prepare one exact temporal summary",
            mode="ops",
            tool_name=_TEMPORAL_SUMMARY_AUTH_OPERATION,
            tool_args=tool_args,
        )
        result = envelope.get("result") if isinstance(envelope, dict) else None
        token = result.get("confirmation_token") if isinstance(result, dict) else None
        request_id = envelope.get("request_id") if isinstance(envelope, dict) else None
        if (
            return_code != 3
            or envelope.get("status") != "needs_confirmation"
            or not isinstance(token, str)
            or not token
            or not isinstance(request_id, str)
            or _TEMPORAL_AUTH_REQUEST_ID_RE.fullmatch(request_id) is None
        ):
            raise RuntimeError("authorization_not_prepared")
        record = ledger.compare_and_update(
            record["job_id"],
            expected_state="pending_confirmation",
            token_fingerprint=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            authorization_request_id=request_id,
        )
        evidence_persisted = True
    except Exception:
        logger.error("Failed to prepare temporal summary authorization")
        if authority is not None and isinstance(token, str) and token and not evidence_persisted:
            try:
                authority.revoke_action_authorization(
                    prompt="Revoke unpersisted temporal summary authorization",
                    mode="ops",
                    tool_name=_TEMPORAL_SUMMARY_AUTH_OPERATION,
                    tool_args=tool_args,
                    confirmation_token=token,
                )
            except Exception:
                logger.error("Failed to revoke unpersisted temporal summary authorization")
        try:
            ledger.transition(
                record["job_id"],
                expected_states="pending_confirmation",
                new_state="failed",
                outcome={
                    "code": "authorization_prepare_failed",
                    "message": "Temporal summary authorization could not be prepared",
                },
            )
        except Exception:
            logger.error("Failed to persist temporal summary preparation failure")
        raise HTTPException(status_code=503, detail="Temporal summary authorization unavailable")

    return {
        "success": True,
        "confirmation_token": token,
        "job": _public_temporal_summary_job(record),
    }


