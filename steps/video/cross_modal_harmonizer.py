"""
Phase 6: Cross-Modal Harmonizer
Fuses scene embeddings with audio, transcript, and metadata into unified temporal index.
Creates the multimodal knowledge graph foundation for retrieval.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import Counter
import os
import json
import logging
import re
import sqlite3
from pathlib import Path

from steps.common.atomic_io import atomic_write_json
from steps.common.config_loader import get_runtime_paths

logger = logging.getLogger(__name__)

try:
    from steps.video.entity_extractor import extract_entities_from_scene, EntityExtractor
    ENTITY_EXTRACTION_AVAILABLE = True
except ImportError:
    ENTITY_EXTRACTION_AVAILABLE = False
    logger.warning("Entity extractor not available")

try:
    from steps.common.context_analyzer_llm import (
        analyze_scene_context_llm,
        _caption_is_low_signal as _scene_context_caption_is_low_signal,
        _extract_transcript_topic_hints as _scene_context_extract_transcript_topic_hints,
    )
    SCENE_CONTEXT_LLM_AVAILABLE = True
except ImportError:
    SCENE_CONTEXT_LLM_AVAILABLE = False
    logger.warning("Scene context analyzer not available")

    def _scene_context_caption_is_low_signal(caption: str) -> bool:
        return not bool(str(caption or "").strip())

    def _scene_context_extract_transcript_topic_hints(transcript: str) -> List[str]:
        return []

try:
    from steps.common.epistemic_formatter import EPISTEMIC_READ_MODEL_VERSION
except ImportError:
    EPISTEMIC_READ_MODEL_VERSION = 1


def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file with error handling."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
    return None


def _normalize_content_state(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"signal", "empty", "processing_error"}:
        return normalized
    return None


def _normalize_entity_rollup_record(entity: Any) -> Optional[Dict[str, str]]:
    if not isinstance(entity, dict):
        return None

    raw_text = (
        entity.get("text")
        or entity.get("name")
        or entity.get("label")
        or entity.get("entity")
    )
    text = str(raw_text or "").strip()
    if not text:
        return None

    raw_type = entity.get("type") or entity.get("entity_type") or "UNKNOWN"
    entity_type = str(raw_type or "UNKNOWN").strip() or "UNKNOWN"
    return {"text": text, "type": entity_type}


def _normalize_entity_channel_record(entity: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(entity, dict):
        return None

    normalized = _normalize_entity_rollup_record(entity)
    if normalized is None:
        return None

    source_modalities = entity.get("source_modalities")
    if isinstance(source_modalities, list):
        modalities = sorted(
            {
                str(modality).strip().lower()
                for modality in source_modalities
                if isinstance(modality, str) and modality.strip()
            }
        )
    else:
        source_modality = entity.get("source_modality")
        modalities = [str(source_modality).strip().lower()] if isinstance(source_modality, str) and source_modality.strip() else []

    source_steps = entity.get("source_steps")
    if isinstance(source_steps, list):
        steps = sorted(
            {
                str(step).strip().lower()
                for step in source_steps
                if isinstance(step, str) and step.strip()
            }
        )
    else:
        source_step = entity.get("source_step")
        steps = [str(source_step).strip().lower()] if isinstance(source_step, str) and source_step.strip() else []

    return {
        "text": normalized["text"],
        "type": normalized["type"],
        "source_modalities": modalities,
        "source_steps": steps,
    }


def _classify_entity_channel(record: Dict[str, Any]) -> Dict[str, bool]:
    source_modalities = {
        str(modality).strip().lower()
        for modality in record.get("source_modalities", [])
        if isinstance(modality, str) and modality.strip()
    }
    entity_type = str(record.get("type") or "").strip().upper()

    is_audio_backed = "audio" in source_modalities
    is_vision_backed = "vision" in source_modalities
    is_metadata_only = bool(source_modalities) and source_modalities.issubset({"metadata"})

    is_scene_present = False
    is_dialogue_mentioned = False

    if entity_type == "PERSON":
        is_scene_present = is_vision_backed
        is_dialogue_mentioned = is_audio_backed and not is_vision_backed
    elif entity_type == "LOCATION":
        is_scene_present = is_vision_backed or is_metadata_only
        is_dialogue_mentioned = is_audio_backed and not is_scene_present
    elif entity_type in {"CONCEPT", "EVENT", "ORGANIZATION", "OBJECT", "UNKNOWN"}:
        is_scene_present = is_vision_backed and entity_type != "OBJECT"
        is_dialogue_mentioned = is_audio_backed and not is_vision_backed
    else:
        is_scene_present = is_vision_backed or is_metadata_only
        is_dialogue_mentioned = is_audio_backed and not is_scene_present

    return {
        "scene_present": is_scene_present,
        "dialogue_mentioned": is_dialogue_mentioned,
    }


def _build_entity_channels(scene_entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    channels: Dict[str, List[Dict[str, str]]] = {
        "scene_present_entities": [],
        "dialogue_mentioned_entities": [],
        "visible_people": [],
        "mentioned_people": [],
        "candidate_visible_people": [],
        "conversation_owner": [],
        "scene_locations": [],
        "dialogue_topics": [],
    }
    seen: Dict[str, set[tuple[str, str]]] = {key: set() for key in channels}

    def _append(channel: str, text: str, entity_type: str) -> None:
        key = (text.casefold(), entity_type.upper())
        if key in seen[channel]:
            return
        channels[channel].append({"text": text, "type": entity_type.upper()})
        seen[channel].add(key)

    for entity in scene_entities:
        normalized = _normalize_entity_channel_record(entity)
        if normalized is None:
            continue
        text = normalized["text"]
        entity_type = str(normalized["type"] or "UNKNOWN").upper()
        channel_flags = _classify_entity_channel(normalized)
        if channel_flags["scene_present"]:
            _append("scene_present_entities", text, entity_type)
        if channel_flags["dialogue_mentioned"]:
            _append("dialogue_mentioned_entities", text, entity_type)

        if entity_type == "PERSON":
            if channel_flags["scene_present"]:
                _append("visible_people", text, entity_type)
            if channel_flags["dialogue_mentioned"]:
                _append("mentioned_people", text, entity_type)

        if entity_type == "LOCATION" and channel_flags["scene_present"]:
            _append("scene_locations", text, entity_type)

        if channel_flags["dialogue_mentioned"] and entity_type in {"PERSON", "CONCEPT", "EVENT", "ORGANIZATION", "LOCATION"}:
            _append("dialogue_topics", text, entity_type)

    return channels


def _resolve_scene_faces(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    keyframe_payload = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
    payload_faces = keyframe_payload.get("faces")
    if isinstance(payload_faces, list):
        return payload_faces
    return []


def _count_visible_person_objects(scene_objects: List[Dict[str, Any]]) -> int:
    count = 0
    for obj in scene_objects:
        if not isinstance(obj, dict):
            continue
        raw_label = obj.get("label") or obj.get("name") or obj.get("class")
        label = str(raw_label or "").strip().lower()
        if label == "person":
            count += 1
    return count


def _resolve_audio_emotion(scene_audio_payload: Dict[str, Any]) -> tuple[Optional[str], Dict[str, float]]:
    raw_scores = scene_audio_payload.get("emotion_scores")
    emotion_scores: Dict[str, float] = {}
    if isinstance(raw_scores, dict):
        for label, score in raw_scores.items():
            normalized_label = str(label or "").strip().lower()
            if not normalized_label:
                continue
            try:
                emotion_scores[normalized_label] = float(score)
            except (TypeError, ValueError):
                continue

    raw_emotion = scene_audio_payload.get("emotion") or scene_audio_payload.get("audio_emotion")
    normalized_emotion = str(raw_emotion or "").strip().lower() if raw_emotion else ""
    if not normalized_emotion and emotion_scores:
        normalized_emotion = max(emotion_scores.items(), key=lambda item: item[1])[0]
    if normalized_emotion in {"", "unknown", "unavailable", "none", "null"}:
        normalized_emotion = ""

    return (normalized_emotion or None), emotion_scores


def _resolve_scene_music_events(scene_audio_payload: Dict[str, Any]) -> List[Any]:
    music_events = scene_audio_payload.get("music_events")
    return music_events if isinstance(music_events, list) else []


def _extract_music_event_labels(music_events: List[Any]) -> List[str]:
    labels: List[str] = []
    for event in music_events:
        if isinstance(event, str):
            normalized = event.strip().lower()
            if normalized:
                labels.append(normalized)
            continue
        if not isinstance(event, dict):
            continue
        for key in ("label", "event", "name", "type", "category"):
            raw_value = event.get(key)
            normalized = str(raw_value or "").strip().lower()
            if normalized:
                labels.append(normalized)
                break
    return labels


def _resolve_scene_time_hints(scene_audio_payload: Dict[str, Any]) -> Dict[str, Any]:
    time_hints = scene_audio_payload.get("time_hints")
    return time_hints if isinstance(time_hints, dict) else {}


def _resolve_scene_metadata_time_hints(scene_audio_payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata_time_hints = scene_audio_payload.get("metadata_time_hints")
    if isinstance(metadata_time_hints, dict):
        return metadata_time_hints
    audio_meta = scene_audio_payload.get("audio_meta")
    if isinstance(audio_meta, dict):
        tag_time_hints = audio_meta.get("tag_time_hints")
        if isinstance(tag_time_hints, dict):
            return tag_time_hints
    return {}


def _scene_context_llm_enabled(cfg: Dict[str, Any]) -> bool:
    llm_cfg = cfg.get("llm", {})
    if not isinstance(llm_cfg, dict):
        llm_cfg = {}
    features = llm_cfg.get("features", {})
    if not isinstance(features, dict):
        features = {}
    return bool(features.get("scene_context_analysis", False))


def _sanitize_scene_context_llm(raw_context: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_context, dict):
        return None
    generic_tags = {
        "man",
        "woman",
        "people",
        "conversation",
        "indoor conversation",
        "room",
        "waiting",
        "friend",
        "friends",
        "family",
        "two women",
    }

    def _clean_text(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    def _clean_list(values: Any, *, limit: int) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        if not isinstance(values, list):
            return cleaned
        for value in values:
            normalized = _clean_text(value)
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
            if len(cleaned) >= limit:
                break
        return cleaned

    raw_tags = _clean_list(raw_context.get("context_tags"), limit=8)
    has_specific_tags = any(tag.casefold() not in generic_tags for tag in raw_tags)
    cleaned_tags = [
        tag
        for tag in raw_tags
        if not (has_specific_tags and tag.casefold() in generic_tags)
    ][:5]

    sanitized = {
        "narrative_summary": _clean_text(raw_context.get("narrative_summary")),
        "key_moments": _clean_list(raw_context.get("key_moments"), limit=3),
        "emotional_arc": _clean_text(raw_context.get("emotional_arc")),
        "context_tags": cleaned_tags,
        "activity_description": _clean_text(raw_context.get("activity_description")),
        "source": "scene_context_llm",
    }
    has_signal = any(
        sanitized[key]
        for key in (
            "narrative_summary",
            "key_moments",
            "emotional_arc",
            "context_tags",
            "activity_description",
        )
    )
    return sanitized if has_signal else None


def _scene_context_text_blob(scene_context: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("narrative_summary", "activity_description", "emotional_arc"):
        value = scene_context.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for key in ("key_moments", "context_tags"):
        values = scene_context.get(key)
        if isinstance(values, list):
            parts.extend(str(value).strip() for value in values if isinstance(value, str) and str(value).strip())
    return " ".join(parts).strip().lower()


def _extract_scene_object_labels(scene_objects: Any) -> List[str]:
    labels: List[str] = []
    if not isinstance(scene_objects, list):
        return labels
    for obj in scene_objects[:10]:
        if isinstance(obj, dict):
            raw_label = obj.get("label") or obj.get("name") or obj.get("class")
        else:
            raw_label = obj
        normalized = str(raw_label or "").strip().lower()
        if normalized:
            labels.append(normalized)
    return labels


def _derive_scene_context_epistemic(
    scene_meta: Dict[str, Any],
    scene_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not isinstance(scene_context, dict):
        return None

    transcript = str(scene_meta.get("transcript") or "").strip()
    caption = str(scene_meta.get("caption") or "").strip()
    face_count = int(scene_meta.get("face_count") or 0)
    emotions = scene_meta.get("emotions") if isinstance(scene_meta.get("emotions"), list) else []
    topic_hints = _scene_context_extract_transcript_topic_hints(transcript)
    context_blob = _scene_context_text_blob(scene_context)
    context_tags = [
        str(tag).strip().lower()
        for tag in scene_context.get("context_tags", [])
        if isinstance(tag, str) and str(tag).strip()
    ]
    object_labels = _extract_scene_object_labels(scene_meta.get("objects"))
    caption_lower = caption.lower()

    fallback_mode: Optional[str] = None
    if "low-signal scene" in context_tags:
        fallback_mode = "low_signal"
    elif "spoken monologue" in context_tags:
        fallback_mode = "spoken_monologue"

    evidence: List[Dict[str, Any]] = []
    limits: List[str] = []
    next_steps: List[Dict[str, str]] = []
    families: List[str] = []

    supported_topics = [hint for hint in topic_hints if hint and hint.casefold() in context_blob]
    for hint in supported_topics[:3]:
        evidence.append({"role": "support", "kind": "transcript_topic", "value": hint})
    if supported_topics:
        families.append("transcript")

    supported_visual: List[str] = []
    if caption and not _scene_context_caption_is_low_signal(caption):
        for tag in context_tags:
            if tag and tag in caption_lower and tag not in supported_visual:
                supported_visual.append(tag)
    for label in object_labels:
        if label in context_blob and label not in supported_visual:
            supported_visual.append(label)
    if face_count > 0 and any(token in context_blob for token in ("person", "people", "group conversation", "indoor conversation")):
        supported_visual.append("visible_faces")
    for value in supported_visual[:3]:
        evidence.append({"role": "support", "kind": "visual_signal", "value": value})
    if supported_visual:
        families.append("visual")

    top_emotion = None
    if emotions:
        top_emotion = str(emotions[0].get("label") or "").strip().lower()
    if top_emotion:
        emotional_arc = str(scene_context.get("emotional_arc") or "").strip().lower()
        role = "support" if top_emotion in emotional_arc else "related"
        evidence.append({"role": role, "kind": "audio_emotion", "value": top_emotion})
        families.append("audio")

    if fallback_mode:
        evidence.append({"role": "meta", "kind": "fallback_mode", "value": fallback_mode})
        if fallback_mode == "low_signal":
            limits.append("low_signal_scene")
            next_steps.append(
                {
                    "action": "inspect scene manually",
                    "rationale": "Low-signal fallback was used because transcript and visual evidence were weak.",
                }
            )
        else:
            next_steps.append(
                {
                    "action": "review monologue transcript",
                    "rationale": "Scene context relied on monologue fallback with transcript-led topic hints.",
                }
            )

    conflict_detected = False
    if topic_hints and not supported_topics and transcript:
        limits.append("transcript_topic_not_reflected")
        next_steps.append(
            {
                "action": "review transcript-led scene context",
                "rationale": "Extracted transcript topics were not explicitly preserved in the scene context output.",
            }
        )

    if not supported_topics and not supported_visual and not top_emotion and not fallback_mode:
        limits.append("evidence_coverage_limited")

    family_order = [family for family in ("transcript", "visual", "audio") if family in families]
    if fallback_mode:
        dominant_evidence = "fallback"
    elif "transcript" in families and "visual" in families:
        dominant_evidence = "mixed"
    elif "transcript" in families:
        dominant_evidence = "transcript"
    elif "visual" in families:
        dominant_evidence = "visual"
    elif "audio" in families:
        dominant_evidence = "audio"
    else:
        dominant_evidence = "unknown"

    if fallback_mode == "low_signal":
        state = "unknown"
    elif conflict_detected:
        state = "conflicted"
    elif len([item for item in evidence if item.get("role") == "support"]) >= 2:
        state = "supported"
    elif any(item.get("role") == "support" for item in evidence) or any(item.get("role") == "related" for item in evidence):
        state = "partially_supported"
    else:
        state = "unknown"

    evidence_family = "+".join(family_order) if family_order else ("fallback" if fallback_mode else "unknown")
    if not (evidence or limits or next_steps):
        return None
    return {
        "read_model_version": EPISTEMIC_READ_MODEL_VERSION,
        "state": state,
        "dominant_evidence": dominant_evidence,
        "evidence_family": evidence_family,
        "fallback_mode": fallback_mode,
        "conflict_detected": conflict_detected,
        "evidence": evidence,
        "limits": limits,
        "next_steps": next_steps[:3],
    }


def _extract_time_hint_tokens(time_hints: Any) -> List[str]:
    tokens: List[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).strip().lower() == "first_seen_ts":
                    continue
                _walk(value)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if isinstance(node, str):
            normalized = node.strip().lower()
            if normalized:
                tokens.append(normalized)

    _walk(time_hints)
    seen: set[str] = set()
    unique_tokens: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique_tokens.append(token)
    return unique_tokens


def _normalize_speaker_id(raw_speaker: Any) -> Optional[str]:
    if not isinstance(raw_speaker, str):
        return None
    speaker_id = raw_speaker.strip()
    return speaker_id or None


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _collect_scene_speaker_records(
    scene_audio_payload: Dict[str, Any],
    fallback_speakers: List[Dict[str, Any]],
    *,
    scene_start: float,
    scene_end: float,
) -> List[Dict[str, Any]]:
    def _from_segments(raw_segments: Any) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        if not isinstance(raw_segments, list):
            return records
        for segment in raw_segments:
            if not isinstance(segment, dict):
                continue
            speaker_id = _normalize_speaker_id(
                segment.get("speaker") or segment.get("speaker_id") or segment.get("label")
            )
            if not speaker_id:
                continue
            start = _coerce_float(segment.get("start"), scene_start)
            end = _coerce_float(segment.get("end"), scene_end)
            records.append(
                {
                    "speaker": speaker_id,
                    "start": start,
                    "end": end,
                    "text": str(segment.get("text") or "").strip(),
                }
            )

        if records:
            scene_duration = max(0.0, scene_end - scene_start)
            relative_like = all(
                0.0 <= record["start"] <= scene_duration + 1.0
                and 0.0 <= record["end"] <= scene_duration + 1.0
                for record in records
            )
            if relative_like:
                for record in records:
                    record["start"] += scene_start
                    record["end"] += scene_start

        filtered_records: List[Dict[str, Any]] = []
        for record in records:
            if record["end"] <= scene_start or record["start"] >= scene_end:
                continue
            filtered_records.append(record)
        return filtered_records

    for segment_key in ("speaker_transcript", "speaker_segments", "diarization"):
        records = _from_segments(scene_audio_payload.get(segment_key))
        if records:
            return records

    return _from_segments(fallback_speakers)


def _summarize_speaker_records(
    speaker_records: List[Dict[str, Any]],
    speaker_ids: List[str],
) -> Dict[str, Any]:
    duration_by_speaker: Dict[str, float] = {}
    for record in speaker_records:
        speaker_id = _normalize_speaker_id(record.get("speaker"))
        if not speaker_id:
            continue
        start = _coerce_float(record.get("start"), 0.0)
        end = _coerce_float(record.get("end"), start)
        duration = max(0.0, end - start)
        if duration <= 0.0:
            duration = 1.0
        duration_by_speaker[speaker_id] = duration_by_speaker.get(speaker_id, 0.0) + duration

    if not duration_by_speaker:
        normalized_ids = [speaker_id for speaker_id in (_normalize_speaker_id(s) for s in speaker_ids) if speaker_id]
        if len(normalized_ids) == 1:
            return {
                "speaker_count": 1,
                "dominant_speaker_id": normalized_ids[0],
                "dominant_speaker_share": 1.0,
                "dominance_confidence": "strong",
                "conversation_speaker_ids": [normalized_ids[0]],
            }
        return {
            "speaker_count": len({speaker_id for speaker_id in normalized_ids}),
            "dominant_speaker_id": None,
            "dominant_speaker_share": 0.0,
            "dominance_confidence": "none",
            "conversation_speaker_ids": sorted({speaker_id for speaker_id in normalized_ids}),
        }

    ranked_speakers = sorted(duration_by_speaker.items(), key=lambda item: (-item[1], item[0]))
    dominant_speaker_id, dominant_duration = ranked_speakers[0]
    total_duration = sum(duration_by_speaker.values())
    dominant_share = (dominant_duration / total_duration) if total_duration > 0 else 0.0
    if dominant_share >= 0.6:
        dominance_confidence = "strong"
    elif dominant_share >= 0.4:
        dominance_confidence = "weak"
    else:
        dominance_confidence = "fallback"
    conversation_speaker_ids = sorted({speaker_id for speaker_id, _ in ranked_speakers[:2]})
    return {
        "speaker_count": len(duration_by_speaker),
        "dominant_speaker_id": dominant_speaker_id,
        "dominant_speaker_share": round(dominant_share, 4),
        "dominance_confidence": dominance_confidence,
        "conversation_speaker_ids": conversation_speaker_ids,
    }


def _has_direct_address(text: str, name: str) -> bool:
    normalized_text = str(text or "").strip()
    normalized_name = str(name or "").strip()
    if not normalized_text or not normalized_name:
        return False
    pattern = rf"(^|[\s\"'(\[]){re.escape(normalized_name)}[,!?:](\s|$)"
    return re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None


def _text_mentions_name(text: str, name: str) -> bool:
    normalized_text = str(text or "").strip()
    normalized_name = str(name or "").strip()
    if not normalized_text or not normalized_name:
        return False
    pattern = rf"\b{re.escape(normalized_name)}\b"
    return re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None


def _has_adjacent_reply_confirmation(
    speaker_records: List[Dict[str, Any]],
    *,
    name: str,
    dominant_speaker_id: Optional[str],
) -> bool:
    if not dominant_speaker_id:
        return False

    ordered_records = sorted(
        speaker_records,
        key=lambda record: (
            _coerce_float(record.get("start"), 0.0),
            _coerce_float(record.get("end"), _coerce_float(record.get("start"), 0.0)),
        ),
    )

    for left_record, right_record in zip(ordered_records, ordered_records[1:]):
        left_speaker = _normalize_speaker_id(left_record.get("speaker"))
        right_speaker = _normalize_speaker_id(right_record.get("speaker"))
        if not left_speaker or not right_speaker or left_speaker == right_speaker:
            continue

        left_end = _coerce_float(left_record.get("end"), _coerce_float(left_record.get("start"), 0.0))
        right_start = _coerce_float(right_record.get("start"), left_end)
        if right_start - left_end > 3.0:
            continue

        left_has_direct_address = _has_direct_address(left_record.get("text", ""), name)
        right_has_direct_address = _has_direct_address(right_record.get("text", ""), name)
        if not (left_has_direct_address or right_has_direct_address):
            continue

        if dominant_speaker_id not in {left_speaker, right_speaker}:
            continue

        return True

    return False


def _derive_candidate_visible_people(
    *,
    entity_channels: Dict[str, List[Dict[str, str]]],
    scene: Dict[str, Any],
    scene_objects: List[Dict[str, Any]],
    scene_audio_payload: Dict[str, Any],
    fallback_speakers: List[Dict[str, Any]],
    scene_start: float,
    scene_end: float,
    speaker_ids: List[str],
) -> Dict[str, Any]:
    visible_faces = _resolve_scene_faces(scene)
    visible_face_count = len(visible_faces)
    visible_person_object_count = _count_visible_person_objects(scene_objects)
    visible_anonymous_people_count = visible_face_count if visible_face_count > 0 else visible_person_object_count
    crowd_risk = max(visible_face_count, visible_person_object_count) > 1
    source_modalities: List[str] = []
    if visible_person_object_count > 0:
        source_modalities.append("object_detect")
    if visible_face_count > 0:
        source_modalities.append("face_embed")

    speaker_records = _collect_scene_speaker_records(
        scene_audio_payload,
        fallback_speakers,
        scene_start=scene_start,
        scene_end=scene_end,
    )
    speaker_summary = _summarize_speaker_records(speaker_records, speaker_ids)
    continuity_members = [
        speaker_id
        for speaker_id in (
            _normalize_speaker_id(speaker_id)
            for speaker_id in speaker_summary.get("conversation_speaker_ids", [])
        )
        if speaker_id
    ]
    continuity_key = None
    if len(continuity_members) >= 2:
        continuity_key = "conversation:" + "|".join(sorted(set(continuity_members)))
    elif speaker_summary["dominant_speaker_id"]:
        continuity_key = speaker_summary["dominant_speaker_id"]
    if not continuity_key:
        normalized_speaker_ids = [
            speaker_id
            for speaker_id in (_normalize_speaker_id(speaker_id) for speaker_id in speaker_ids)
            if speaker_id
        ]
        if len(set(normalized_speaker_ids)) == 1:
            continuity_key = normalized_speaker_ids[0]

    visible_person_confidence: Optional[Dict[str, Any]] = None
    if source_modalities:
        visible_person_confidence = {
            "source_modalities": source_modalities,
            "frame_consistency": "keyframe_only",
            "face_support": visible_face_count > 0,
            "object_support": visible_person_object_count > 0,
            "crowd_risk": "high" if crowd_risk else "low",
        }

    candidate_visible_people: List[Dict[str, Any]] = []
    if visible_person_object_count >= 1 and visible_face_count >= 1 and not crowd_risk:
        candidate_visible_people = [
            {
                "text": "anonymous_person_1",
                "name": "anonymous_person_1",
                "type": "PERSON",
                "source": "visual_scene_presence",
                "confidence": "supported",
                "evidence": {
                    "source_modalities": source_modalities,
                    "frame_consistency": "keyframe_only",
                    "visible_person_object_count": visible_person_object_count,
                    "visible_face_count": visible_face_count,
                    "crowd_risk": "low",
                },
            }
        ]

    speaker_aligned_mentions: List[Dict[str, Any]] = []
    dominant_speaker_id = speaker_summary["dominant_speaker_id"]
    if dominant_speaker_id:
        aligned_records = [
            record
            for record in speaker_records
            if _normalize_speaker_id(record.get("speaker")) == dominant_speaker_id
        ]
        for person in entity_channels.get("mentioned_people", []):
            if not isinstance(person, dict):
                continue
            person_name = str(person.get("text") or "").strip()
            if not person_name:
                continue
            mention_count = sum(
                1 for record in aligned_records if _text_mentions_name(record.get("text", ""), person_name)
            )
            if mention_count <= 0:
                continue
            speaker_aligned_mentions.append(
                {
                    "text": person_name,
                    "type": "PERSON",
                    "count": mention_count,
                }
            )

    return {
        "visible_face_count": visible_face_count,
        "visible_person_object_count": visible_person_object_count,
        "visible_anonymous_people_count": visible_anonymous_people_count,
        "visible_person_confidence": visible_person_confidence,
        "speaker_count": speaker_summary["speaker_count"],
        "dominant_speaker_id": speaker_summary["dominant_speaker_id"],
        "dominant_speaker_share": speaker_summary["dominant_speaker_share"],
        "dominance_confidence": speaker_summary["dominance_confidence"],
        "conversation_speaker_ids": continuity_members,
        "continuity_key": continuity_key,
        "speaker_aligned_mentions": speaker_aligned_mentions,
        "candidate_visible_people": candidate_visible_people,
    }


def _segment_mentions_person(segment: Dict[str, Any], name: str) -> bool:
    name_cf = str(name or "").strip().casefold()
    if not name_cf:
        return False
    for person in segment.get("mentioned_people", []):
        if not isinstance(person, dict):
            continue
        if str(person.get("text") or "").strip().casefold() == name_cf:
            return True
    return False


def _resolve_segment_continuity_key(segment: Dict[str, Any]) -> Optional[str]:
    for field_name in ("speaker_pattern_id", "speaker_pattern", "continuity_key", "dominant_speaker_id"):
        value = _normalize_speaker_id(segment.get(field_name))
        if value:
            return value

        raw_value = segment.get(field_name)
        if isinstance(raw_value, str):
            normalized = raw_value.strip()
            if normalized.startswith("conversation:"):
                return normalized

    speaker_ids = segment.get("speaker_ids")
    if isinstance(speaker_ids, list):
        normalized_speaker_ids = [
            speaker_id
            for speaker_id in (_normalize_speaker_id(speaker_id) for speaker_id in speaker_ids)
            if speaker_id
        ]
        if len(set(normalized_speaker_ids)) == 1:
            return normalized_speaker_ids[0]

    return None


def _resolve_segment_continuity_members(segment: Dict[str, Any]) -> set[str]:
    raw_members = segment.get("conversation_speaker_ids")
    if isinstance(raw_members, list):
        normalized = {
            speaker_id
            for speaker_id in (_normalize_speaker_id(member) for member in raw_members)
            if speaker_id
        }
        if normalized:
            return normalized

    continuity_key = segment.get("continuity_key")
    if isinstance(continuity_key, str) and continuity_key.startswith("conversation:"):
        return {
            speaker_id
            for speaker_id in (
                _normalize_speaker_id(part)
                for part in continuity_key.split(":", 1)[1].split("|")
            )
            if speaker_id
        }

    dominant_speaker_id = _normalize_speaker_id(segment.get("dominant_speaker_id"))
    if dominant_speaker_id:
        return {dominant_speaker_id}

    speaker_ids = segment.get("speaker_ids")
    if isinstance(speaker_ids, list):
        return {
            speaker_id
            for speaker_id in (_normalize_speaker_id(member) for member in speaker_ids)
            if speaker_id
        }

    return set()


def _iter_continuity_chains(unified_segments: List[Dict[str, Any]]) -> List[tuple[int, int, str]]:
    chains: List[tuple[int, int, str]] = []
    index = 0
    while index < len(unified_segments):
        continuity_key = _resolve_segment_continuity_key(unified_segments[index])
        if not continuity_key:
            index += 1
            continue

        chain_end = index
        while chain_end + 1 < len(unified_segments):
            next_key = _resolve_segment_continuity_key(unified_segments[chain_end + 1])
            if next_key != continuity_key:
                break
            chain_end += 1

        if chain_end - index + 1 >= 2:
            chains.append((index, chain_end, continuity_key))

        index = chain_end + 1

    return chains


def _apply_interaction_dominance_window(unified_segments: List[Dict[str, Any]]) -> None:
    for segment in unified_segments:
        segment["interaction_dominance"] = None

    for chain_start, chain_end, continuity_key in _iter_continuity_chains(unified_segments):
        chain = unified_segments[chain_start:chain_end + 1]
        speaker_share_totals: Dict[str, float] = {}
        speaker_segment_counts: Counter[str] = Counter()
        for chain_segment in chain:
            speaker_id = _normalize_speaker_id(chain_segment.get("dominant_speaker_id"))
            dominant_share = float(chain_segment.get("dominant_speaker_share") or 0.0)
            if not speaker_id or dominant_share <= 0.0:
                continue
            speaker_share_totals[speaker_id] = speaker_share_totals.get(speaker_id, 0.0) + dominant_share
            speaker_segment_counts[speaker_id] += 1

        if not speaker_share_totals:
            continue

        ranked_speakers = sorted(
            speaker_share_totals.items(),
            key=lambda item: (-item[1], -speaker_segment_counts[item[0]], item[0]),
        )
        speaker_id, total_share = ranked_speakers[0]
        segments_for_speaker = speaker_segment_counts[speaker_id]
        average_share = total_share / segments_for_speaker if segments_for_speaker else 0.0
        stability = segments_for_speaker / len(chain)
        if average_share < 0.6 or segments_for_speaker < 2 or stability < 0.6:
            continue

        payload = {
            "speaker_id": speaker_id,
            "dominant_share": round(average_share, 4),
            "segments": segments_for_speaker,
            "stability": round(stability, 4),
            "confidence": "strong" if average_share >= 0.7 and stability >= 0.75 else "stable",
            "continuity_key": continuity_key,
        }
        for chain_segment in chain:
            chain_segment["interaction_dominance"] = payload


def _apply_conversation_owner_window(unified_segments: List[Dict[str, Any]]) -> None:
    for segment in unified_segments:
        segment["conversation_owner"] = None

    for chain_start, chain_end, continuity_key in _iter_continuity_chains(unified_segments):
        chain = unified_segments[chain_start:chain_end + 1]
        interaction_dominance = chain[0].get("interaction_dominance")
        if not isinstance(interaction_dominance, dict):
            continue
        dominant_speaker_id = _normalize_speaker_id(interaction_dominance.get("speaker_id"))
        if not dominant_speaker_id:
            continue

        person_display_names: Dict[str, str] = {}
        person_aligned_counts: Counter[str] = Counter()
        person_dominant_segment_counts: Counter[str] = Counter()
        person_mention_segment_ids: Dict[str, List[str]] = {}

        for chain_segment in chain:
            scene_id = str(chain_segment.get("scene_id") or "")
            segment_dominant_speaker_id = _normalize_speaker_id(chain_segment.get("dominant_speaker_id"))
            for person in chain_segment.get("speaker_aligned_mentions", []):
                if not isinstance(person, dict):
                    continue
                text = str(person.get("text") or "").strip()
                if not text:
                    continue
                normalized_text = text.casefold()
                person_display_names.setdefault(normalized_text, text)
                person_aligned_counts[normalized_text] += int(person.get("count") or 1)
                person_mention_segment_ids.setdefault(normalized_text, []).append(scene_id)
                if segment_dominant_speaker_id == dominant_speaker_id:
                    person_dominant_segment_counts[normalized_text] += int(person.get("count") or 1)

        if not person_aligned_counts:
            continue

        ranked_people = sorted(
            person_aligned_counts.items(),
            key=lambda item: (
                -item[1],
                person_display_names.get(item[0], item[0]),
            ),
        )
        candidate_key, candidate_count = ranked_people[0]
        if candidate_count < 2:
            continue
        if person_dominant_segment_counts.get(candidate_key, 0) < 1:
            continue

        total_mentions_in_chain = sum(person_aligned_counts.values())
        mention_dominance_ratio = (
            candidate_count / total_mentions_in_chain if total_mentions_in_chain > 0 else 0.0
        )
        if mention_dominance_ratio < 0.6:
            continue

        competitor_count = ranked_people[1][1] if len(ranked_people) > 1 else 0
        if competitor_count and (competitor_count / candidate_count) > 0.8:
            continue

        candidate_name = person_display_names.get(candidate_key, candidate_key)
        owner_payload = {
            "name": candidate_name,
            "text": candidate_name,
            "type": "PERSON",
            "confidence": "candidate",
            "source": "interaction_chain",
            "continuity_key": continuity_key,
            "chain_length": len(chain),
            "mention_dominance_ratio": round(mention_dominance_ratio, 4),
            "speaker_dominance_ratio": round(float(interaction_dominance.get("dominant_share") or 0.0), 4),
            "competitor_gap": candidate_count - competitor_count,
            "evidence": {
                "speaker_aligned_mentions": person_aligned_counts[candidate_key],
                "total_mentions": total_mentions_in_chain,
                "segments_involved": person_mention_segment_ids.get(candidate_key, []),
            },
        }

        for chain_segment in chain:
            chain_segment["conversation_owner"] = owner_payload


def _apply_scene_context_llm(
    unified_segments: List[Dict[str, Any]],
    scene_lookup: Dict[str, Dict[str, Any]],
    cfg: Dict[str, Any],
) -> None:
    for segment in unified_segments:
        segment["scene_context_llm"] = None
        segment["scene_context_epistemic"] = None

    if not SCENE_CONTEXT_LLM_AVAILABLE or not _scene_context_llm_enabled(cfg):
        return

    for segment in unified_segments:
        if _normalize_content_state(segment.get("content_state")) != "signal":
            continue

        scene = scene_lookup.get(str(segment.get("scene_id") or ""))
        if not isinstance(scene, dict):
            continue

        keyframe_payload = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
        transcript_text = str(segment.get("full_transcript") or "").strip()
        scene_objects = segment.get("detected_objects")
        if not isinstance(scene_objects, list):
            scene_objects = []
        face_count = int(segment.get("visible_face_count") or 0)

        if not transcript_text and not scene_objects and face_count <= 0:
            continue

        emotions_payload: List[Dict[str, Any]] = []
        emotion_scores = segment.get("audio_emotion_scores")
        if isinstance(emotion_scores, dict):
            sorted_emotions = sorted(
                (
                    (str(label).strip().lower(), score)
                    for label, score in emotion_scores.items()
                    if str(label).strip()
                ),
                key=lambda item: float(item[1]),
                reverse=True,
            )
            for label, score in sorted_emotions[:3]:
                try:
                    emotions_payload.append({"label": label, "score": float(score)})
                except (TypeError, ValueError):
                    continue
        elif isinstance(segment.get("audio_emotion"), str) and segment.get("audio_emotion"):
            emotions_payload.append({"label": str(segment.get("audio_emotion")).strip().lower(), "score": 1.0})

        scene_meta = {
            "index": scene.get("index"),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "caption": scene.get("caption") or keyframe_payload.get("caption") or "",
            "transcript": transcript_text,
            "objects": scene_objects,
            "face_count": face_count,
            "emotions": emotions_payload,
            "speakers": segment.get("speaker_ids") or [],
        }

        try:
            raw_context = analyze_scene_context_llm(scene_meta, cfg)
        except Exception as exc:
            logger.warning(
                "[HARMONIZER] Scene context analysis failed scene_id=%s exc_type=%s exc=%s",
                segment.get("scene_id"),
                type(exc).__name__,
                exc,
            )
            continue

        sanitized_context = _sanitize_scene_context_llm(raw_context)
        segment["scene_context_llm"] = sanitized_context
        if sanitized_context:
            segment["scene_context_epistemic"] = _derive_scene_context_epistemic(scene_meta, sanitized_context)


def _persist_harmonized_scene_fields(
    scene_data: Dict[str, Any],
    unified_segments: List[Dict[str, Any]],
) -> None:
    scenes = scene_data.get("scenes")
    if not isinstance(scenes, list):
        return

    unified_by_scene_id = {
        str(segment.get("scene_id")): segment
        for segment in unified_segments
        if isinstance(segment, dict) and segment.get("scene_id") is not None
    }
    persisted_fields = (
        "speaker_ids",
        "scene_present_entities",
        "dialogue_mentioned_entities",
        "visible_people",
        "mentioned_people",
        "candidate_visible_people",
        "conversation_owner",
        "speaker_aligned_mentions",
        "scene_locations",
        "dialogue_topics",
        "visible_face_count",
        "visible_person_object_count",
        "visible_anonymous_people_count",
        "visible_person_confidence",
        "music_events",
        "time_hints",
        "metadata_time_hints",
        "audio_emotion",
        "audio_emotion_scores",
        "scene_context_llm",
        "scene_context_epistemic",
        "speaker_voice_signature_count",
        "speaker_count",
        "dominant_speaker_id",
        "dominant_speaker_share",
        "dominance_confidence",
        "conversation_speaker_ids",
        "continuity_key",
        "interaction_dominance",
        "content_state",
    )

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id") or "")
        segment = unified_by_scene_id.get(scene_id)
        if not segment:
            continue
        for field_name in persisted_fields:
            scene[field_name] = segment.get(field_name)

    scene_data["phase6_harmonized"] = True


def _resolve_segment_content_state(
    scene: Dict[str, Any],
    *,
    full_transcript_text: str,
    scene_entities: List[Dict[str, Any]],
    scene_objects: List[Dict[str, Any]],
    speaker_ids: List[str],
    keywords: List[str],
) -> str:
    raw_state = _normalize_content_state(scene.get("content_state"))
    if raw_state == "processing_error":
        return raw_state

    keyframe_payload = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
    caption_text = scene.get("caption") or keyframe_payload.get("caption") or ""
    ocr_text = scene.get("ocr_text") or keyframe_payload.get("ocr_text") or ""
    raw_tags = scene.get("tags") or keyframe_payload.get("tags") or []
    has_tags = isinstance(raw_tags, list) and any(str(tag or "").strip() for tag in raw_tags)

    has_semantic_signal = bool(
        full_transcript_text
        or scene_entities
        or scene_objects
        or speaker_ids
        or keywords
        or str(caption_text).strip()
        or str(ocr_text).strip()
        or has_tags
        or scene.get("clip_id")
        or scene.get("dino_id")
    )
    if has_semantic_signal:
        return "signal"
    return raw_state or "empty"


def _load_required_audio_artifact(path: Path, artifact_name: str) -> tuple[Optional[Dict[str, Any]], bool]:
    """
    Load required audio artifact and return (data, integrity_ok).
    integrity_ok is False when artifact is missing or invalid.
    """
    if not path.exists():
        logger.warning(
            "[HARMONIZER] Missing required audio artifact artifact=%s path=%s",
            artifact_name,
            path,
        )
        return None, False
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            logger.warning(
                "[HARMONIZER] Invalid audio artifact payload artifact=%s path=%s payload_type=%s",
                artifact_name,
                path,
                type(data).__name__,
            )
            return None, False
        return data, True
    except Exception as e:
        logger.warning(
            "[HARMONIZER] Failed to parse audio artifact artifact=%s path=%s exc_type=%s exc=%s",
            artifact_name,
            path,
            type(e).__name__,
            e,
        )
        return None, False


def _load_commit_presence(cfg: Dict[str, Any], video_id: str, scene_ids: List[str] | None = None) -> Dict[str, Any]:
    """Best-effort: derive modality presence from committed memory events (authoritative)."""
    presence = {
        'available': False,
        'has_audio': False,
        'has_transcripts': False,
        'audio_scene_ids': set(),
        'transcript_scene_ids': set(),
    }

    try:
        runtime_paths = get_runtime_paths(cfg, 'db_path', require_canonical=False)
        db_path = runtime_paths['db_path']
    except KeyError:
        return presence

    if not isinstance(db_path, str) or not db_path:
        return presence
    if not os.path.exists(db_path):
        return presence

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        cur = conn.cursor()

        def _has_any_by_video(modality: str) -> bool:
            cur.execute(
                """
                SELECT 1
                FROM memory_commit_events
                WHERE video_id = ?
                  AND modality = ?
                  AND attempted = 1
                  AND committed = 1
                LIMIT 1
                """,
                (video_id, modality),
            )
            return cur.fetchone() is not None

        def _scene_ids_by_video(modality: str) -> set[str]:
            cur.execute(
                """
                SELECT DISTINCT scene_id
                FROM memory_commit_events
                WHERE video_id = ?
                  AND modality = ?
                  AND attempted = 1
                  AND committed = 1
                  AND scene_id IS NOT NULL
                  AND scene_id != ''
                """,
                (video_id, modality),
            )
            return {row[0] for row in cur.fetchall() if row and row[0]}

        def _scene_ids_in(modality: str, scene_ids_list: List[str]) -> set[str]:
            if not scene_ids_list:
                return set()
            placeholders = ",".join("?" for _ in scene_ids_list)
            cur.execute(
                f"""
                SELECT DISTINCT scene_id
                FROM memory_commit_events
                WHERE modality = ?
                  AND attempted = 1
                  AND committed = 1
                  AND scene_id IN ({placeholders})
                """,
                (modality, *scene_ids_list),
            )
            return {row[0] for row in cur.fetchall() if row and row[0]}

        scene_ids_list = [str(sid) for sid in (scene_ids or []) if sid]

        audio_scene_ids = _scene_ids_by_video('audio')
        transcript_scene_ids = _scene_ids_by_video('audio_transcript')
        if scene_ids_list:
            audio_scene_ids |= _scene_ids_in('audio', scene_ids_list)
            transcript_scene_ids |= _scene_ids_in('audio_transcript', scene_ids_list)

        presence['audio_scene_ids'] = audio_scene_ids
        presence['transcript_scene_ids'] = transcript_scene_ids
        presence['has_audio'] = _has_any_by_video('audio') or bool(audio_scene_ids)
        presence['has_transcripts'] = _has_any_by_video('audio_transcript') or bool(transcript_scene_ids)
        presence['available'] = True
        return presence
    except Exception as e:
        logger.warning(f"[HARMONIZER] Failed to query memory_commit_events for presence: {e}")
        return presence
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as e:
                logger.warning(
                    "[HARMONIZER] Failed to close commit presence DB connection: %s: %s",
                    type(e).__name__,
                    e,
                )


def align_audio_to_scenes(
    scenes: List[Dict[str, Any]],
    audio_segments: List[Dict[str, Any]]
) -> Dict[int, List[int]]:
    """
    Map audio chunks to video scenes based on temporal overlap.
    
    Args:
        scenes: List of scene dicts with 'start' and 'end' times
        audio_segments: List of audio segment dicts with 'start' and 'end'
        
    Returns:
        Dict mapping scene_id -> list of audio chunk IDs
    """
    scene_to_audio = {}
    
    for scene in scenes:
        scene_id = scene.get('id', scene.get('scene_id', 0))
        scene_start = scene.get('start', 0.0)
        scene_end = scene.get('end', 0.0)
        
        overlapping_chunks = []
        
        for chunk in audio_segments:
            chunk_id = chunk.get('id', chunk.get('chunk_id', 0))
            chunk_start = chunk.get('start', 0.0)
            chunk_end = chunk.get('end', 0.0)
            
            # Check for temporal overlap
            if chunk_start < scene_end and chunk_end > scene_start:
                overlapping_chunks.append(chunk_id)
        
        scene_to_audio[scene_id] = overlapping_chunks
    
    return scene_to_audio


def extract_keywords_from_transcript(transcript_segments: List[Dict[str, Any]], top_k: int = 10) -> List[str]:
    """
    Extract keywords from transcript segments (simplified version).
    
    Args:
        transcript_segments: List of transcript segment dicts
        top_k: Number of top keywords to extract
        
    Returns:
        List of keyword strings
    """
    # Simple keyword extraction: collect frequent words (excluding stopwords)
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'them', 'their', 'what', 'which', 'who', 'when', 'where', 'why', 'how'}
    
    word_counts = {}
    
    for segment in transcript_segments:
        text = segment.get('text', '')
        words = text.lower().split()
        
        for word in words:
            # Clean punctuation
            word = word.strip('.,!?;:()[]{}"\'-')
            
            if len(word) > 3 and word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    # Sort by frequency and return top_k
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:top_k]]


def _resolve_scene_objects(
    scene: Dict[str, Any],
    scene_id: Any,
    objects_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    for key in ("objects", "detected_objects"):
        payload_objects = scene.get(key)
        if isinstance(payload_objects, list):
            return payload_objects

    keyframe_payload = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
    keyframe_objects = keyframe_payload.get("objects")
    if isinstance(keyframe_objects, list):
        return keyframe_objects

    if isinstance(objects_data, dict):
        for lookup_key in (scene_id, str(scene_id)):
            scene_entry = objects_data.get(lookup_key)
            if isinstance(scene_entry, dict):
                scene_objects = scene_entry.get("objects")
                if isinstance(scene_objects, list):
                    return scene_objects

    return []


def run_cross_modal_harmonization(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 6 harmonization: Fuse all modalities into unified temporal index.
    
    This step combines:
    - Video scenes (Phase 5)
    - Scene visual embeddings (Phase 6)
    - Audio segmentation (Phase 3)
    - Transcripts (audio pipeline)
    - Diarization (speaker IDs)
    - Object detection (from frames)
    - Metadata tags
    
    Into a single multimodal temporal index suitable for retrieval.
    
    Args:
        item: Enriched item dict
        cfg: Configuration dict
        
    Returns:
        Dict with harmonization status
    """
    # Get video info
    video_path = item.get('source_path')
    video_id_raw = item.get('video_id') or item.get('video_hash') or item.get('id')
    video_id = str(video_id_raw).strip() if video_id_raw is not None else ""
    if not video_id:
        video_id = Path(video_path).stem if video_path else 'unknown'
    storage_key_raw = item.get('video_storage_key') or item.get('id') or video_id
    video_storage_key = str(storage_key_raw).strip() if storage_key_raw is not None else video_id
    if not video_storage_key:
        video_storage_key = video_id
    
    runtime_paths = get_runtime_paths(cfg, 'processing', require_canonical=False)
    processing_root = runtime_paths['processing']
    processing_dir_raw = item.get('processing_dir')
    if isinstance(processing_dir_raw, str) and processing_dir_raw.strip():
        processing_dir = processing_dir_raw
    else:
        processing_dir = os.path.join(processing_root, str(video_storage_key))
    audio_artifact_dir_raw = item.get('audio_artifact_dir')
    audio_artifact_dir: Optional[Path] = None
    if isinstance(audio_artifact_dir_raw, str) and audio_artifact_dir_raw.strip():
        audio_artifact_dir = Path(audio_artifact_dir_raw)
    else:
        logger.warning(
            "[HARMONIZER] Missing audio_artifact_dir for video_id=%s; audio/transcript modalities disabled",
            video_id,
        )
    
    logger.info(f"[HARMONIZER] Starting cross-modal fusion for {video_id}")
    
    # === LOAD ALL DATA SOURCES ===
    
    # Load scene manifest (Phase 5 + Phase 6)
    scene_manifest_path = item.get("scene_manifest_path")
    if scene_manifest_path and os.path.exists(scene_manifest_path):
        logger.debug(f"Using provided scene_manifest_path: {scene_manifest_path}")
    else:
        # Preferred canonical location
        scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
        
        # Fallback for older or mismatched pipelines
        if not os.path.exists(scene_manifest_path):
            alt_path = os.path.join(processing_dir, 'scene_manifest.json')
            if os.path.exists(alt_path):
                logger.warning(f"[HARMONIZER] Using fallback scene_manifest.json at: {alt_path}")
                scene_manifest_path = alt_path
    
    scene_data = load_json_safe(scene_manifest_path)
    
    if not scene_data:
        logger.warning(f"[HARMONIZER] No scene manifest found at {scene_manifest_path}, skipping harmonization")
        return {
            "harmonization_status": "skipped",
            "reason": "no_scene_manifest",
            "harmonized_scene_count": 0,
            "entity_extraction_available": ENTITY_EXTRACTION_AVAILABLE,
            "entities_extracted": 0,
        }
    
    scenes = scene_data.get('scenes', [])
    scene_lookup = {
        str(scene.get("scene_id")): scene
        for scene in scenes
        if isinstance(scene, dict) and scene.get("scene_id") is not None
    }
    manifest_video_id = scene_data.get('video_id') if isinstance(scene_data, dict) else None
    if isinstance(manifest_video_id, str) and manifest_video_id.strip():
        video_id = manifest_video_id.strip()
    else:
        scene_data['video_id'] = video_id

    # Preserve committed-modality truth (memory_commit_events) as metadata/checks,
    # but do not let it suppress scene payload transcript/audio truth.
    scene_ids_for_video = [str(s.get('id', s.get('scene_id', ''))) for s in scenes if s.get('id') or s.get('scene_id')]
    commit_presence = _load_commit_presence(cfg, str(video_id), scene_ids=scene_ids_for_video)
    audio_scene_ids = set(commit_presence.get('audio_scene_ids') or []) if commit_presence.get('available') else set()
    transcript_scene_ids = set(commit_presence.get('transcript_scene_ids') or []) if commit_presence.get('available') else set()
    has_audio_committed = bool(commit_presence.get('has_audio')) if commit_presence.get('available') else None
    has_transcripts_committed = bool(commit_presence.get('has_transcripts')) if commit_presence.get('available') else None

    scene_content_states: List[str] = []
    for scene in scenes:
        normalized = _normalize_content_state(scene.get('content_state'))
        if normalized:
            scene_content_states.append(normalized)
    all_scenes_classified = len(scene_content_states) == len(scenes) and len(scenes) > 0
    processing_error_scene_count = sum(1 for state in scene_content_states if state == 'processing_error')
    
    # Load audio segmentation (Phase 3)
    segmentation_data = None
    transcript_data = None
    diarization_data = None
    audio_artifact_integrity_ok = True
    if audio_artifact_dir is not None:
        segmentation_data = load_json_safe(str(audio_artifact_dir / 'segmentation.json'))
        transcript_data, transcript_ok = _load_required_audio_artifact(
            audio_artifact_dir / 'transcript.json',
            'transcript',
        )
        diarization_data, diarization_ok = _load_required_audio_artifact(
            audio_artifact_dir / 'diarization.json',
            'diarization',
        )
        audio_artifact_integrity_ok = transcript_ok and diarization_ok
    else:
        audio_artifact_integrity_ok = False
    audio_segments = segmentation_data.get('segments', []) if segmentation_data else []
    
    transcript_segments = transcript_data.get('segments', []) if transcript_data else []
    
    speakers = diarization_data.get('speakers', []) if diarization_data else []
    phase6_warning: Optional[str] = None
    harmonization_status = 'complete'
    if not audio_artifact_integrity_ok:
        # Classified runs: only processing_error scenes should degrade harmonization.
        # Legacy/unclassified runs retain prior conservative behavior.
        if (all_scenes_classified and processing_error_scene_count > 0) or (not all_scenes_classified):
            phase6_warning = 'missing_audio_artifacts'
            harmonization_status = 'degraded'
            logger.warning(
                "[HARMONIZER] Harmonization degraded warning=%s video_id=%s processing_error_scenes=%s classified=%s",
                phase6_warning,
                video_id,
                processing_error_scene_count,
                all_scenes_classified,
            )
        else:
            logger.info(
                "[HARMONIZER] Audio artifacts missing but scenes classified without processing errors; "
                "keeping harmonization_status=complete video_id=%s",
                video_id,
            )
    
    # Load object detection results (if available)
    objects_path = os.path.join(processing_dir, 'video', 'detected_objects.json')
    objects_data = load_json_safe(objects_path)
    
    logger.info(f"  Loaded: {len(scenes)} scenes, {len(audio_segments)} audio chunks, {len(transcript_segments)} transcript segments")
    
    # === BUILD TEMPORAL INDEX ===
    
    # Align audio chunks to scenes
    scene_audio_map = align_audio_to_scenes(scenes, audio_segments)
    
    # Build unified multimodal segments
    unified_segments = []
    total_entities_extracted = 0
    
    for scene in scenes:
        scene_id = scene.get('id', scene.get('scene_id', 0))
        scene_start = scene.get('start', 0.0)
        scene_end = scene.get('end', 0.0)
        
        # Get overlapping audio/transcript payloads from artifacts first.
        raw_audio_chunk_ids = scene_audio_map.get(scene_id, [])
        raw_scene_transcripts = [
            seg for seg in transcript_segments
            if seg.get('start', 0) < scene_end and seg.get('end', 0) > scene_start
        ]

        # Scene payload truth (authoritative for has_audio/has_transcript flags).
        scene_audio_payload = scene.get('audio') if isinstance(scene.get('audio'), dict) else {}
        payload_audio_path = scene_audio_payload.get('path')
        payload_audio_path = payload_audio_path.strip() if isinstance(payload_audio_path, str) else ''
        payload_audio_meta = scene_audio_payload.get('audio_meta')
        payload_audio_segments = scene_audio_payload.get('segments') if isinstance(scene_audio_payload.get('segments'), list) else []
        payload_transcript_text = scene_audio_payload.get('transcript')
        payload_transcript_text = payload_transcript_text.strip() if isinstance(payload_transcript_text, str) else ''

        # Prefer artifact overlap segments; fallback to scene payload segments; then fallback to full transcript text.
        scene_transcripts = list(raw_scene_transcripts)
        if not scene_transcripts and payload_audio_segments:
            scene_transcripts = [seg for seg in payload_audio_segments if isinstance(seg, dict)]
        if not scene_transcripts and payload_transcript_text:
            scene_transcripts = [{'start': scene_start, 'end': scene_end, 'text': payload_transcript_text}]
        audio_chunk_ids = list(raw_audio_chunk_ids)

        scene_transcript_texts = [
            str(seg.get('text', '')).strip()
            for seg in scene_transcripts
            if isinstance(seg, dict)
        ]
        scene_transcript_texts = [text for text in scene_transcript_texts if text]
        full_transcript_text = payload_transcript_text or ' '.join(scene_transcript_texts).strip()

        has_audio_for_scene = bool(
            audio_chunk_ids
            or payload_audio_path
            or isinstance(payload_audio_meta, dict)
            or payload_audio_segments
            or payload_transcript_text
        )
        has_transcript_for_scene = bool(full_transcript_text or scene_transcript_texts)

        # Extract keywords from truth-aligned transcripts
        keywords = extract_keywords_from_transcript(scene_transcripts, top_k=5)

        # Extract entities from truth-aligned text sources
        scene_entities = []
        if ENTITY_EXTRACTION_AVAILABLE:
            full_transcript = full_transcript_text
            keyframe_payload = scene.get('keyframe') if isinstance(scene.get('keyframe'), dict) else {}
            caption_text = scene.get('caption') or keyframe_payload.get('caption', '')
            ocr_text = scene.get('ocr_text') or keyframe_payload.get('ocr_text', '')
            tags = scene.get('tags') or keyframe_payload.get('tags', [])
            scene_entity_data = dict(scene)
            scene_entity_data.update({
                'transcription': full_transcript,
                'caption': caption_text,
                'ocr_text': ocr_text,
                'tags': tags,
                'start_time': scene_start,
            })
            entity_result = extract_entities_from_scene(
                scene_data=scene_entity_data,
                scene_id=str(scene_id),
                video_id=str(video_id),
                config=cfg,
            )
            if isinstance(entity_result, dict):
                scene_entities = entity_result.get('entities', []) or []
                total_entities_extracted += int(entity_result.get('entity_count', len(scene_entities)))

        entity_channels = _build_entity_channels(scene_entities)
        
        # Get speaker IDs (prefer scene-level payload truth, fallback to diarization artifact overlap)
        speaker_ids = []

        def _append_speaker_id(raw_id: Any) -> None:
            if not isinstance(raw_id, str):
                return
            speaker_id = raw_id.strip()
            if speaker_id and speaker_id not in speaker_ids:
                speaker_ids.append(speaker_id)

        scene_speaker_ids = scene.get('speaker_ids')
        if isinstance(scene_speaker_ids, list):
            for speaker_id in scene_speaker_ids:
                _append_speaker_id(speaker_id)

        payload_speakers = scene_audio_payload.get('speakers')
        if isinstance(payload_speakers, list):
            for speaker in payload_speakers:
                if isinstance(speaker, str):
                    _append_speaker_id(speaker)
                elif isinstance(speaker, dict):
                    _append_speaker_id(speaker.get('speaker', speaker.get('label')))

        for segment_key in ('speaker_transcript', 'speaker_segments', 'diarization'):
            speaker_segments = scene_audio_payload.get(segment_key)
            if not isinstance(speaker_segments, list):
                continue
            for segment in speaker_segments:
                if isinstance(segment, dict):
                    _append_speaker_id(segment.get('speaker'))

        if not speaker_ids:
            for speaker in speakers:
                if not isinstance(speaker, dict):
                    continue
                if speaker.get('start', 0) < scene_end and speaker.get('end', 0) > scene_start:
                    _append_speaker_id(
                        speaker.get('speaker')
                        or speaker.get('speaker_id')
                        or speaker.get('label')
                    )

        if not has_audio_for_scene:
            speaker_ids = []

        # Prefer live scene payload truth; fallback to the legacy Phase 6 object artifact.
        scene_objects = _resolve_scene_objects(scene, scene_id, objects_data)
        music_events = _resolve_scene_music_events(scene_audio_payload)
        time_hints = _resolve_scene_time_hints(scene_audio_payload)
        metadata_time_hints = _resolve_scene_metadata_time_hints(scene_audio_payload)
        audio_emotion, audio_emotion_scores = _resolve_audio_emotion(scene_audio_payload)
        speaker_voice_signatures = scene_audio_payload.get('speaker_voice_signatures') if isinstance(scene_audio_payload.get('speaker_voice_signatures'), list) else []
        candidate_visibility = _derive_candidate_visible_people(
            entity_channels=entity_channels,
            scene=scene,
            scene_objects=scene_objects,
            scene_audio_payload=scene_audio_payload,
            fallback_speakers=speakers,
            scene_start=scene_start,
            scene_end=scene_end,
            speaker_ids=speaker_ids,
        )
        entity_channels["candidate_visible_people"] = candidate_visibility["candidate_visible_people"]
        
        # Build unified segment
        unified_segment = {
            'scene_id': scene_id,
            'start': scene_start,
            'end': scene_end,
            'duration': scene_end - scene_start,
            'content_state': scene.get('content_state', 'signal'),
            
            # Visual embeddings
            'clip_id': scene.get('clip_id'),
            'dino_id': scene.get('dino_id'),
            'representative_frame': scene.get('representative_frame'),
            'frame_count': scene.get('frame_count', 0),
            
            # Audio alignment
            'audio_chunks': audio_chunk_ids,
            'speaker_ids': speaker_ids,
            
            # Semantic content
            'keywords': keywords,
            'entities': scene_entities,  # NEW: Extracted entities
            'scene_present_entities': entity_channels['scene_present_entities'],
            'dialogue_mentioned_entities': entity_channels['dialogue_mentioned_entities'],
            'visible_people': entity_channels['visible_people'],
            'mentioned_people': entity_channels['mentioned_people'],
            'candidate_visible_people': entity_channels['candidate_visible_people'],
            'speaker_aligned_mentions': candidate_visibility['speaker_aligned_mentions'],
            'scene_locations': entity_channels['scene_locations'],
            'dialogue_topics': entity_channels['dialogue_topics'],
            'transcript_segments': scene_transcript_texts,
            'full_transcript': full_transcript_text,
            
            # Metadata
            'scene_confidence': scene.get('confidence', 0.0),
            'has_visual_embeddings': bool(scene.get('clip_id') and scene.get('dino_id')),
            'has_audio': has_audio_for_scene,
            'has_transcript': has_transcript_for_scene,
            'has_speakers': has_audio_for_scene and len(speaker_ids) > 0,
            'visible_face_count': candidate_visibility['visible_face_count'],
            'visible_person_object_count': candidate_visibility['visible_person_object_count'],
            'visible_anonymous_people_count': candidate_visibility['visible_anonymous_people_count'],
            'visible_person_confidence': candidate_visibility['visible_person_confidence'],
            'speaker_voice_signature_count': len(speaker_voice_signatures),
            'music_events': music_events,
            'time_hints': time_hints,
            'metadata_time_hints': metadata_time_hints,
            'audio_emotion': audio_emotion,
            'audio_emotion_scores': audio_emotion_scores,
            'scene_context_llm': None,
            'scene_context_epistemic': None,
            'speaker_count': candidate_visibility['speaker_count'],
            'dominant_speaker_id': candidate_visibility['dominant_speaker_id'],
            'dominant_speaker_share': candidate_visibility['dominant_speaker_share'],
            'dominance_confidence': candidate_visibility['dominance_confidence'],
            'conversation_speaker_ids': candidate_visibility['conversation_speaker_ids'],
            'continuity_key': candidate_visibility['continuity_key'],
        }
        
        content_state = _resolve_segment_content_state(
            scene,
            full_transcript_text=full_transcript_text,
            scene_entities=scene_entities,
            scene_objects=scene_objects,
            speaker_ids=speaker_ids,
            keywords=keywords,
        )
        if scene_objects:
            unified_segment['detected_objects'] = scene_objects
        unified_segment['content_state'] = content_state
        
        unified_segments.append(unified_segment)

    _apply_interaction_dominance_window(unified_segments)
    _apply_conversation_owner_window(unified_segments)
    _apply_scene_context_llm(unified_segments, scene_lookup, cfg)
    
    # === CREATE TEMPORAL INDEX ===
    
    # Aggregate all entities across segments
    all_entities = []
    entity_counts = {}
    scene_present_entity_counts = {}
    dialogue_mentioned_entity_counts = {}
    visible_people_counts = {}
    mentioned_people_counts = {}
    candidate_visible_people_counts = {}
    conversation_owner_counts = {}
    interaction_dominance_counts: Dict[str, int] = {}
    music_event_counts: Dict[str, int] = {}
    time_hint_counts: Dict[str, int] = {}
    metadata_time_hint_counts: Dict[str, int] = {}
    audio_emotion_counts: Dict[str, int] = {}
    scene_context_tag_counts: Dict[str, int] = {}
    scene_context_epistemic_state_counts: Dict[str, int] = {}
    scene_context_epistemic_dominant_counts: Dict[str, int] = {}
    segment_content_states: List[str] = []
    for seg in unified_segments:
        segment_state = _normalize_content_state(seg.get('content_state')) or 'signal'
        segment_content_states.append(segment_state)
        for entity in seg.get('entities', []):
            normalized_entity = _normalize_entity_rollup_record(entity)
            if not normalized_entity:
                continue
            all_entities.append(normalized_entity)
            entity_text = normalized_entity['text'].lower()
            entity_type = normalized_entity['type']
            key = f"{entity_text}:{entity_type}"
            entity_counts[key] = entity_counts.get(key, 0) + 1
        for channel_name, counter in (
            ('scene_present_entities', scene_present_entity_counts),
            ('dialogue_mentioned_entities', dialogue_mentioned_entity_counts),
            ('visible_people', visible_people_counts),
            ('mentioned_people', mentioned_people_counts),
            ('candidate_visible_people', candidate_visible_people_counts),
        ):
            for entity in seg.get(channel_name, []):
                normalized_entity = _normalize_entity_rollup_record(entity)
                if not normalized_entity:
                    continue
                entity_text = normalized_entity['text'].lower()
                entity_type = normalized_entity['type']
                key = f"{entity_text}:{entity_type}"
                counter[key] = counter.get(key, 0) + 1
        conversation_owner = seg.get("conversation_owner")
        if isinstance(conversation_owner, dict):
            normalized_owner = _normalize_entity_rollup_record(conversation_owner)
            if normalized_owner:
                owner_key = f"{normalized_owner['text'].lower()}:{normalized_owner['type']}"
                conversation_owner_counts[owner_key] = conversation_owner_counts.get(owner_key, 0) + 1
        interaction_dominance = seg.get('interaction_dominance')
        if isinstance(interaction_dominance, dict):
            dominant_speaker_id = _normalize_speaker_id(interaction_dominance.get('speaker_id'))
            if dominant_speaker_id:
                interaction_dominance_counts[dominant_speaker_id] = interaction_dominance_counts.get(dominant_speaker_id, 0) + 1
        for event_label in _extract_music_event_labels(seg.get('music_events', [])):
            music_event_counts[event_label] = music_event_counts.get(event_label, 0) + 1
        for time_hint in _extract_time_hint_tokens(seg.get('time_hints', {})):
            time_hint_counts[time_hint] = time_hint_counts.get(time_hint, 0) + 1
        for time_hint in _extract_time_hint_tokens(seg.get('metadata_time_hints', {})):
            metadata_time_hint_counts[time_hint] = metadata_time_hint_counts.get(time_hint, 0) + 1
        normalized_audio_emotion = str(seg.get('audio_emotion') or '').strip().lower()
        if normalized_audio_emotion:
            audio_emotion_counts[normalized_audio_emotion] = audio_emotion_counts.get(normalized_audio_emotion, 0) + 1
        scene_context_llm = seg.get("scene_context_llm")
        if isinstance(scene_context_llm, dict):
            for tag in scene_context_llm.get("context_tags", []):
                normalized_tag = str(tag or "").strip().lower()
                if normalized_tag:
                    scene_context_tag_counts[normalized_tag] = scene_context_tag_counts.get(normalized_tag, 0) + 1
        scene_context_epistemic = seg.get("scene_context_epistemic")
        if isinstance(scene_context_epistemic, dict):
            normalized_state = str(scene_context_epistemic.get("state") or "").strip().lower()
            if normalized_state:
                scene_context_epistemic_state_counts[normalized_state] = (
                    scene_context_epistemic_state_counts.get(normalized_state, 0) + 1
                )
            dominant_evidence = str(scene_context_epistemic.get("dominant_evidence") or "").strip().lower()
            if dominant_evidence:
                scene_context_epistemic_dominant_counts[dominant_evidence] = (
                    scene_context_epistemic_dominant_counts.get(dominant_evidence, 0) + 1
                )

    semantic_entity_counts = {
        key: value
        for key, value in entity_counts.items()
        if not key.endswith(":object")
    }
    object_entity_counts = {
        key: value
        for key, value in entity_counts.items()
        if key.endswith(":object")
    }

    # Keep top_entities focused on semantic entities; object inventories are
    # already available per-segment via detected_objects and are exposed
    # separately below.
    top_entities = sorted(semantic_entity_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_objects = sorted(object_entity_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_scene_present_entities = sorted(scene_present_entity_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_dialogue_mentioned_entities = sorted(dialogue_mentioned_entity_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_visible_people = sorted(visible_people_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_mentioned_people = sorted(mentioned_people_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_candidate_visible_people = sorted(candidate_visible_people_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_conversation_owners = sorted(conversation_owner_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_interaction_dominance = sorted(interaction_dominance_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_music_events = sorted(music_event_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_time_hints = sorted(time_hint_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_metadata_time_hints = sorted(metadata_time_hint_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_audio_emotions = sorted(audio_emotion_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_scene_context_tags = sorted(scene_context_tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_scene_context_epistemic_states = sorted(
        scene_context_epistemic_state_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:20]
    top_scene_context_epistemic_dominant = sorted(
        scene_context_epistemic_dominant_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:20]
    
    has_audio_payload_truth = any(s.get('has_audio') for s in unified_segments)
    has_transcript_payload_truth = any(s.get('has_transcript') for s in unified_segments)
    if commit_presence.get('available') and has_transcript_payload_truth and has_transcripts_committed is False:
        logger.warning(
            "[HARMONIZER] Transcript payload present without committed audio_transcript vectors video_id=%s",
            video_id,
        )
    if commit_presence.get('available') and has_audio_payload_truth and has_audio_committed is False:
        logger.warning(
            "[HARMONIZER] Audio payload present without committed audio vectors video_id=%s",
            video_id,
        )

    temporal_index = {
        'version': 1,
        'video_id': video_id,
        'video_hash': video_id,
        'video_path': video_path,
        'total_scenes': len(scenes),
        'total_duration': max(s.get('end', 0) for s in scenes) if scenes else 0,
        
        # Multimodal segments
        'segments': unified_segments,
        
        # Extracted entities
        'total_entities': len(all_entities),
        'unique_entities': len(entity_counts),
        'segments_with_scene_present_entities': sum(1 for seg in unified_segments if seg.get('scene_present_entities')),
        'segments_with_dialogue_mentioned_entities': sum(1 for seg in unified_segments if seg.get('dialogue_mentioned_entities')),
        'segments_with_visible_people': sum(1 for seg in unified_segments if seg.get('visible_people')),
        'segments_with_mentioned_people': sum(1 for seg in unified_segments if seg.get('mentioned_people')),
        'segments_with_candidate_visible_people': sum(1 for seg in unified_segments if seg.get('candidate_visible_people')),
        'segments_with_interaction_dominance': sum(1 for seg in unified_segments if seg.get('interaction_dominance')),
        'segments_with_conversation_owner': sum(1 for seg in unified_segments if seg.get('conversation_owner')),
        'segments_with_music_events': sum(1 for seg in unified_segments if seg.get('music_events')),
        'segments_with_time_hints': sum(1 for seg in unified_segments if _extract_time_hint_tokens(seg.get('time_hints', {}))),
        'segments_with_metadata_time_hints': sum(1 for seg in unified_segments if _extract_time_hint_tokens(seg.get('metadata_time_hints', {}))),
        'segments_with_audio_emotion': sum(1 for seg in unified_segments if seg.get('audio_emotion')),
        'segments_with_speaker_voice_signatures': sum(1 for seg in unified_segments if seg.get('speaker_voice_signature_count', 0) > 0),
        'segments_with_scene_context_llm': sum(1 for seg in unified_segments if seg.get('scene_context_llm')),
        'segments_with_scene_context_epistemic': sum(1 for seg in unified_segments if seg.get('scene_context_epistemic')),
        'top_entities': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_entities
        ],
        'top_scene_present_entities': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_scene_present_entities
        ],
        'top_dialogue_mentioned_entities': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_dialogue_mentioned_entities
        ],
        'top_visible_people': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_visible_people
        ],
        'top_mentioned_people': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_mentioned_people
        ],
        'top_candidate_visible_people': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_candidate_visible_people
        ],
        'top_interaction_dominance': [
            {'speaker_id': key, 'count': value}
            for key, value in top_interaction_dominance
        ],
        'top_conversation_owners': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_conversation_owners
        ],
        'top_music_events': [
            {'event': key, 'count': value}
            for key, value in top_music_events
        ],
        'top_time_hints': [
            {'hint': key, 'count': value}
            for key, value in top_time_hints
        ],
        'top_metadata_time_hints': [
            {'hint': key, 'count': value}
            for key, value in top_metadata_time_hints
        ],
        'top_audio_emotions': [
            {'emotion': key, 'count': value}
            for key, value in top_audio_emotions
        ],
        'top_scene_context_tags': [
            {'tag': key, 'count': value}
            for key, value in top_scene_context_tags
        ],
        'top_scene_context_epistemic_states': [
            {'state': key, 'count': value}
            for key, value in top_scene_context_epistemic_states
        ],
        'top_scene_context_epistemic_dominant_evidence': [
            {'evidence': key, 'count': value}
            for key, value in top_scene_context_epistemic_dominant
        ],
        'top_objects': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_objects
        ],
        
        # Global metadata
        'has_visual_embeddings': any(s.get('has_visual_embeddings') for s in unified_segments),
        'has_audio': has_audio_payload_truth,
        'has_transcripts': has_transcript_payload_truth,
        'committed_modalities': {
            'available': bool(commit_presence.get('available')),
            'audio': has_audio_committed,
            'audio_transcript': has_transcripts_committed,
            'audio_scene_count': len(audio_scene_ids),
            'transcript_scene_count': len(transcript_scene_ids),
        },
        'content_summary': {
            'signal': sum(1 for state in segment_content_states if state == 'signal'),
            'empty': sum(1 for state in segment_content_states if state == 'empty'),
            'processing_error': sum(1 for state in segment_content_states if state == 'processing_error'),
        } if segment_content_states else None,
        
        # Processing metadata
        'phase5_complete': scene_data.get('phase5_complete', False),
        'phase6_complete': scene_data.get('phase6_complete', False),
        'phase6_harmonized': True
    }
    if phase6_warning:
        temporal_index['phase6_warning'] = phase6_warning
        temporal_index['harmonization_status'] = harmonization_status
    
    # === SAVE TEMPORAL INDEX ===
    
    temporal_index_path = os.path.join(processing_dir, 'temporal_index.json')
    os.makedirs(os.path.dirname(temporal_index_path), exist_ok=True)
    atomic_write_json(Path(temporal_index_path), temporal_index)

    # Persist additive harmonized fields back into scene_manifest.json so the
    # per-scene truth surface stays auditable and aligned with temporal_index.
    _persist_harmonized_scene_fields(scene_data, unified_segments)
    atomic_write_json(Path(scene_manifest_path), scene_data)
    
    logger.info(f"[HARMONIZER] [OK] Created temporal index with {len(unified_segments)} multimodal segments")
    logger.info(f"  Saved: {temporal_index_path}")
    
    return {
        'video_id': video_id,
        'harmonization_status': harmonization_status,
        'temporal_index_path': temporal_index_path,
        'unified_segments': len(unified_segments),
        'harmonized_scene_count': len(unified_segments),
        'has_visual': temporal_index['has_visual_embeddings'],
        'has_audio': temporal_index['has_audio'],
        'has_transcripts': temporal_index['has_transcripts'],
        'entity_extraction_available': ENTITY_EXTRACTION_AVAILABLE,
        'entities_extracted': total_entities_extracted,
        **({'phase6_warning': phase6_warning} if phase6_warning else {}),
    }
