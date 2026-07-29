"""
Phase 6: Cross-Modal Harmonizer
Fuses scene embeddings with audio, transcript, and metadata into unified temporal index.
Creates the multimodal knowledge graph foundation for retrieval.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import Counter
from difflib import SequenceMatcher
import os
import json
import logging
import re
import sqlite3
from pathlib import Path

from steps.common.atomic_io import atomic_write_json
from steps.common.config_loader import get_runtime_paths

logger = logging.getLogger(__name__)
_AUDIO_EMOTION_PROMOTION_THRESHOLD = 0.5

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
        _is_low_value_topic_fragment as _scene_context_is_low_value_topic_fragment,
    )
    SCENE_CONTEXT_LLM_AVAILABLE = True
except ImportError:
    SCENE_CONTEXT_LLM_AVAILABLE = False
    logger.warning("Scene context analyzer not available")

    def _scene_context_caption_is_low_signal(caption: str) -> bool:
        return not bool(str(caption or "").strip())

    def _scene_context_extract_transcript_topic_hints(transcript: str) -> List[str]:
        return []

    def _scene_context_is_low_value_topic_fragment(value: str) -> bool:
        return not bool(str(value or "").strip())

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


_SPEAKER_ALIGNED_MENTION_TITLES = {
    "capt", "captain", "chief", "coach", "cmdr", "commander", "detective", "doctor",
    "dr", "governor", "gov", "judge", "lady", "madam", "mayor", "miss", "monsieur",
    "mr", "mrs", "ms", "officer", "president", "prof", "professor", "rev",
    "reverend", "senator", "sen", "señor", "senor", "señora", "senora", "sir",
}

_TRANSCRIPT_PERSON_TITLE_PATTERN = re.compile(
    r"\b(?P<title>Mr|Mrs|Ms|Miss|Dr|Doctor|Prof|Professor)\.?\s+(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)
_TRANSCRIPT_PERSON_FULL_NAME_PATTERN = re.compile(
    r"\b(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)
_TRANSCRIPT_PERSON_NON_NAME_LEAD_TOKENS = {
    "hey",
    "look",
    "maybe",
    "now",
    "okay",
    "ok",
    "please",
    "thanks",
    "thank",
    "well",
}


def _normalize_aligned_mention_variant_text(text: Any) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return ""
    normalized = re.sub(r"[^\w\s'-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _strip_aligned_mention_titles(text: str) -> str:
    tokens = text.split()
    while tokens:
        token = tokens[0].rstrip(".")
        if token in _SPEAKER_ALIGNED_MENTION_TITLES:
            tokens = tokens[1:]
            continue
        break
    return " ".join(tokens)


def _serialize_entity_count_pairs(pairs: List[tuple[str, int]]) -> List[Dict[str, Any]]:
    return [
        {
            "entity": key.rsplit(":", 1)[0],
            "type": key.rsplit(":", 1)[1],
            "count": value,
        }
        for key, value in pairs
    ]


def _normalize_transcript_person_surface(text: Any) -> str:
    normalized = str(text or "").strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _normalize_transcript_person_key(text: Any) -> str:
    normalized = _normalize_transcript_person_surface(text).lower()
    normalized = re.sub(r"[^\w\s'-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _extract_transcript_person_candidates(transcript: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    occupied_spans: List[tuple[int, int]] = []
    seen_keys: set[tuple[str, str]] = set()

    for match in _TRANSCRIPT_PERSON_TITLE_PATTERN.finditer(transcript):
        surface = _normalize_transcript_person_surface(match.group(0))
        normalized = _normalize_transcript_person_key(surface)
        if not normalized:
            continue
        candidate_key = ("title", normalized)
        if candidate_key in seen_keys:
            continue
        name_surface = _normalize_transcript_person_surface(match.group("name"))
        surname = name_surface.split()[-1] if name_surface else ""
        candidates.append(
            {
                "kind": "title",
                "surface": surface,
                "normalized": normalized,
                "title": match.group("title"),
                "name": name_surface,
                "surname_normalized": _normalize_transcript_person_key(surname),
                "span": match.span(),
            }
        )
        occupied_spans.append(match.span())
        seen_keys.add(candidate_key)

    def _overlaps_title(span: tuple[int, int]) -> bool:
        for occupied in occupied_spans:
            if span[0] < occupied[1] and occupied[0] < span[1]:
                return True
        return False

    for match in _TRANSCRIPT_PERSON_FULL_NAME_PATTERN.finditer(transcript):
        span = match.span()
        if _overlaps_title(span):
            continue
        surface = _normalize_transcript_person_surface(match.group("name"))
        normalized = _normalize_transcript_person_key(surface)
        if not normalized or len(normalized.split()) < 2:
            continue
        leading_token = normalized.split()[0].rstrip(".")
        if leading_token in _SPEAKER_ALIGNED_MENTION_TITLES:
            continue
        if leading_token in _TRANSCRIPT_PERSON_NON_NAME_LEAD_TOKENS:
            continue
        candidate_key = ("full", normalized)
        if candidate_key in seen_keys:
            continue
        candidates.append(
            {
                "kind": "full",
                "surface": surface,
                "normalized": normalized,
                "tokens": normalized.split(),
                "span": span,
            }
        )
        seen_keys.add(candidate_key)

    return candidates


def _segment_person_entity_names(segment: Dict[str, Any]) -> List[str]:
    entity_names: set[str] = set()
    for entity in segment.get("entities", []):
        normalized_entity = _normalize_entity_rollup_record(entity)
        if not normalized_entity:
            continue
        if normalized_entity["type"].upper() not in {"PERSON", "PER", "SPEAKER_IDENTITY"}:
            continue
        entity_names.add(normalized_entity["text"])
    return sorted(entity_names)


def _segment_person_channel_records(channel: Any) -> List[Dict[str, Any]]:
    if not isinstance(channel, list):
        return []

    records: List[Dict[str, Any]] = []
    seen_records: set[tuple[str, str, int | None]] = set()
    for entry in channel:
        normalized_entry = _normalize_entity_rollup_record(entry)
        if not normalized_entry:
            continue
        count_value: int | None = None
        if isinstance(entry, dict) and "count" in entry:
            try:
                count_value = max(int(entry.get("count", 1)), 1)
            except (TypeError, ValueError):
                count_value = 1
        record_key = (
            normalized_entry["text"],
            normalized_entry["type"],
            count_value,
        )
        if record_key in seen_records:
            continue
        record: Dict[str, Any] = {
            "text": normalized_entry["text"],
            "type": normalized_entry["type"],
        }
        if count_value is not None:
            record["count"] = count_value
        records.append(record)
        seen_records.add(record_key)
    return records


def _segment_local_person_surfaces(segment: Dict[str, Any]) -> set[str]:
    surfaces: set[str] = set()

    for name in _segment_person_entity_names(segment):
        normalized = _normalize_transcript_person_key(name)
        if normalized:
            surfaces.add(normalized)

    for channel_name in ("mentioned_people", "speaker_aligned_mentions"):
        for record in _segment_person_channel_records(segment.get(channel_name)):
            normalized = _normalize_transcript_person_key(record.get("text"))
            if normalized:
                surfaces.add(normalized)

    conversation_owner = segment.get("conversation_owner")
    if isinstance(conversation_owner, dict):
        normalized_owner = _normalize_transcript_person_key(conversation_owner.get("text"))
        if normalized_owner:
            surfaces.add(normalized_owner)

    return surfaces


_TRANSCRIPT_ENTITY_EXACT_PAIR_ALLOWLIST: Dict[tuple[str, str], Dict[str, str]] = {
    ("Jerry Seinfeld", "jerry"): {
        "normalized_surface": "Jerry",
        "source": "exact_pair_allowlist",
    }
}


def _resolve_transcript_entity_exact_pair_normalization(
    transcript_surface: str,
    local_surface: str,
) -> Optional[Dict[str, str]]:
    """Return a projection-only exact-pair normalization rule when one is allowlisted."""
    return _TRANSCRIPT_ENTITY_EXACT_PAIR_ALLOWLIST.get((transcript_surface, local_surface))


def _find_partial_surface_match(candidate_tokens: List[str], local_person_surfaces: set[str]) -> Optional[str]:
    if len(candidate_tokens) < 2:
        return None
    for local_surface in sorted(local_person_surfaces):
        local_tokens = local_surface.split()
        if len(local_tokens) != 1:
            continue
        if local_tokens[0] in {candidate_tokens[0], candidate_tokens[-1]}:
            return local_tokens[0]
    return None


def _find_spelling_drift_surface_match(candidate_tokens: List[str], local_person_surfaces: set[str]) -> Optional[str]:
    if len(candidate_tokens) < 2:
        return None
    for local_surface in sorted(local_person_surfaces):
        local_tokens = local_surface.split()
        if len(local_tokens) != len(candidate_tokens):
            continue
        if candidate_tokens[:-1] != local_tokens[:-1]:
            continue
        if candidate_tokens[-1] == local_tokens[-1]:
            continue
        similarity = SequenceMatcher(None, candidate_tokens[-1], local_tokens[-1]).ratio()
        if similarity >= 0.75:
            return local_surface
    return None


def _segment_transcript_entity_projection(segment: Dict[str, Any]) -> Dict[str, Any]:
    transcript = str(segment.get("full_transcript") or "").strip()
    if not transcript:
        return {
            "disagreements": [],
            "normalization_applied": False,
            "normalization_source": None,
        }

    entity_names = _segment_person_entity_names(segment)
    mentioned_people = _segment_person_channel_records(segment.get("mentioned_people"))
    speaker_aligned_mentions = _segment_person_channel_records(segment.get("speaker_aligned_mentions"))
    local_person_surfaces = _segment_local_person_surfaces(segment)

    disagreements: List[Dict[str, Any]] = []
    seen_family_keys: set[tuple[str, str]] = set()
    normalization_applied = False
    normalization_source: Optional[str] = None

    for candidate in _extract_transcript_person_candidates(transcript):
        category: Optional[str] = None
        family_key: Optional[str] = None
        reason: Optional[str] = None

        if candidate["kind"] == "title":
            surname_normalized = candidate.get("surname_normalized") or ""
            if surname_normalized and surname_normalized in local_person_surfaces:
                category = "title_elision_in_entity_projection"
                family_key = f"title::{surname_normalized}"
                reason = "transcript title form collapses cleanly to existing local person surface"
            else:
                category = "title_bearing_transcript_name_not_resolved"
                family_key = f"title_unresolved::{candidate['normalized']}"
                reason = "title-bearing transcript person reference is not represented in local person truth surfaces"
        else:
            candidate_tokens = candidate.get("tokens") or []
            partial_surface_match = _find_partial_surface_match(candidate_tokens, local_person_surfaces)
            if partial_surface_match:
                exact_pair_normalization = _resolve_transcript_entity_exact_pair_normalization(
                    candidate["surface"],
                    partial_surface_match,
                )
                if exact_pair_normalization:
                    normalization_applied = True
                    normalization_source = exact_pair_normalization["source"]
                    continue
                category = "transcript_full_name_reduced_to_partial_entity"
                family_key = f"partial::{partial_surface_match}"
                reason = "transcript full-name surface reduced to partial local person identity"
            else:
                spelling_surface_match = _find_spelling_drift_surface_match(candidate_tokens, local_person_surfaces)
                if spelling_surface_match:
                    category = "transcript_spelling_drift_vs_entity_name"
                    family_key = f"spelling::{candidate['normalized']}"
                    reason = "transcript person surface differs slightly from local person entity wording"

        if not category or not family_key or not reason:
            continue

        family_identity = (category, family_key)
        if family_identity in seen_family_keys:
            continue

        disagreements.append(
            {
                "category": category,
                "family_key": family_key,
                "scene_id": segment.get("scene_id"),
                "transcript_candidate": candidate["surface"],
                "entity_names": entity_names,
                "mentioned_people": mentioned_people,
                "speaker_aligned_mentions": speaker_aligned_mentions,
                "reason": reason,
            }
        )
        seen_family_keys.add(family_identity)

    return {
        "disagreements": disagreements,
        "normalization_applied": normalization_applied,
        "normalization_source": normalization_source,
    }


def _segment_transcript_entity_disagreements(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _segment_transcript_entity_projection(segment)["disagreements"]


def _build_transcript_entity_disagreement_summary(
    unified_segments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    category_counts: Counter[str] = Counter()
    family_counts: Counter[tuple[str, str]] = Counter()
    family_examples: Dict[tuple[str, str], Dict[str, Any]] = {}
    full_name_partial_family_counts: Counter[str] = Counter()
    full_name_partial_examples: Dict[str, Dict[str, Any]] = {}
    segments_with_disagreements = 0
    segments_with_full_name_partial_entity_disagreements = 0

    for segment in unified_segments:
        disagreements = segment.get("transcript_entity_disagreements")
        if not isinstance(disagreements, list):
            disagreements = _segment_transcript_entity_disagreements(segment)
        if disagreements:
            segments_with_disagreements += 1
        if any(
            isinstance(disagreement, dict)
            and disagreement.get("category") == "transcript_full_name_reduced_to_partial_entity"
            for disagreement in disagreements
        ):
            segments_with_full_name_partial_entity_disagreements += 1
        for disagreement in disagreements:
            category = disagreement["category"]
            family_key = disagreement["family_key"]
            category_counts[category] += 1
            family_counts[(category, family_key)] += 1
            family_examples.setdefault((category, family_key), disagreement)
            if category == "transcript_full_name_reduced_to_partial_entity":
                full_name_partial_family_counts[family_key] += 1
                full_name_partial_examples.setdefault(family_key, disagreement)

    ordered_category_counts = [
        {"category": category, "count": count}
        for category, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    top_families: List[Dict[str, Any]] = []
    for (category, family_key), count in sorted(
        family_counts.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    )[:20]:
        top_families.append(
            {
                "category": category,
                "family_key": family_key,
                "count": count,
                "example": family_examples[(category, family_key)],
            }
        )

    top_full_name_partial_families: List[Dict[str, Any]] = []
    for family_key, count in sorted(
        full_name_partial_family_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:20]:
        top_full_name_partial_families.append(
            {
                "family_key": family_key,
                "count": count,
                "example": full_name_partial_examples[family_key],
            }
        )

    return {
        "segments_with_transcript_entity_disagreements": segments_with_disagreements,
        "segments_with_full_name_partial_entity_disagreements": (
            segments_with_full_name_partial_entity_disagreements
        ),
        "transcript_entity_disagreement_category_counts": ordered_category_counts,
        "top_transcript_full_name_partial_entity_families": top_full_name_partial_families,
        "top_transcript_entity_disagreement_families": top_families,
    }


def _build_speaker_aligned_mention_variant_groups(
    speaker_aligned_mention_counts: Dict[str, int]
) -> List[Dict[str, Any]]:
    structured_mentions: List[Dict[str, Any]] = []
    for key, count in speaker_aligned_mention_counts.items():
        entity_text, entity_type = key.rsplit(":", 1)
        normalized_entity = _normalize_aligned_mention_variant_text(entity_text)
        if not normalized_entity:
            continue
        structured_mentions.append(
            {
                "entity": normalized_entity,
                "type": entity_type,
                "count": count,
                "tokens": normalized_entity.split(),
                "title_stripped": _strip_aligned_mention_titles(normalized_entity),
            }
        )

    structured_mentions.sort(key=lambda item: (item["type"], item["entity"]))
    assigned_variants: set[tuple[str, str]] = set()
    variant_groups: List[Dict[str, Any]] = []

    def _variant_payload(group_key: str, entity_type: str, reason: str, variants: List[Dict[str, Any]]) -> Dict[str, Any]:
        ordered_variants = sorted(
            (
                {"entity": item["entity"], "count": item["count"]}
                for item in variants
            ),
            key=lambda item: item["entity"],
        )
        return {
            "group_key": group_key,
            "type": entity_type,
            "reason": reason,
            "total_count": sum(item["count"] for item in variants),
            "variants": ordered_variants,
        }

    for base_variant in structured_mentions:
        variant_key = (base_variant["type"], base_variant["entity"])
        if variant_key in assigned_variants or base_variant["type"] != "PERSON":
            continue
        titled_matches = [
            item
            for item in structured_mentions
            if item["type"] == base_variant["type"]
            and item["entity"] != base_variant["entity"]
            and item["title_stripped"] == base_variant["entity"]
            and (item["type"], item["entity"]) not in assigned_variants
        ]
        if not titled_matches:
            continue
        variants = [base_variant, *titled_matches]
        variant_groups.append(
            _variant_payload(
                group_key=f"{base_variant['type'].lower()}::{base_variant['entity']}",
                entity_type=base_variant["type"],
                reason="title_stripped_overlap",
                variants=variants,
            )
        )
        assigned_variants.update((item["type"], item["entity"]) for item in variants)

    for single_token_variant in structured_mentions:
        variant_key = (single_token_variant["type"], single_token_variant["entity"])
        if (
            variant_key in assigned_variants
            or single_token_variant["type"] != "PERSON"
            or len(single_token_variant["tokens"]) != 1
        ):
            continue
        full_name_matches = [
            item
            for item in structured_mentions
            if item["type"] == single_token_variant["type"]
            and len(item["tokens"]) > 1
            and item["tokens"][0] == single_token_variant["entity"]
            and (item["type"], item["entity"]) not in assigned_variants
        ]
        if len(full_name_matches) != 1:
            continue
        full_name_variant = full_name_matches[0]
        variants = [single_token_variant, full_name_variant]
        variant_groups.append(
            _variant_payload(
                group_key=f"{single_token_variant['type'].lower()}::{full_name_variant['entity']}",
                entity_type=single_token_variant["type"],
                reason="single_token_full_name_overlap",
                variants=variants,
            )
        )
        assigned_variants.update((item["type"], item["entity"]) for item in variants)

    return sorted(variant_groups, key=lambda item: item["group_key"])


def _canonicalize_chain_person_mentions(
    person_display_names: Dict[str, str],
    person_aligned_counts: Counter[str],
    person_dominant_segment_counts: Counter[str],
    person_mention_segment_ids: Dict[str, List[str]],
) -> tuple[Dict[str, str], Counter[str], Counter[str], Dict[str, List[str]]]:
    variant_groups = _build_speaker_aligned_mention_variant_groups(
        {f"{key}:PERSON": value for key, value in person_aligned_counts.items()}
    )
    if not variant_groups:
        return (
            dict(person_display_names),
            Counter(person_aligned_counts),
            Counter(person_dominant_segment_counts),
            {key: list(value) for key, value in person_mention_segment_ids.items()},
        )

    canonical_display_names = dict(person_display_names)
    canonical_aligned_counts = Counter(person_aligned_counts)
    canonical_dominant_segment_counts = Counter(person_dominant_segment_counts)
    canonical_mention_segment_ids = {
        key: list(value) for key, value in person_mention_segment_ids.items()
    }

    for group in variant_groups:
        canonical_key = str(group.get("group_key") or "").split("::", 1)[-1].strip().lower()
        if not canonical_key:
            continue
        variant_keys = [
            _normalize_aligned_mention_variant_text(variant.get("entity"))
            for variant in group.get("variants", [])
            if isinstance(variant, dict)
        ]
        variant_keys = [key for key in variant_keys if key]
        if not variant_keys:
            continue

        canonical_aligned_counts[canonical_key] = sum(
            person_aligned_counts.get(variant_key, 0) for variant_key in variant_keys
        )
        canonical_dominant_segment_counts[canonical_key] = sum(
            person_dominant_segment_counts.get(variant_key, 0) for variant_key in variant_keys
        )

        seen_scene_ids: set[str] = set()
        merged_scene_ids: List[str] = []
        for variant_key in variant_keys:
            for scene_id in canonical_mention_segment_ids.get(variant_key, []):
                normalized_scene_id = str(scene_id or "").strip()
                if not normalized_scene_id or normalized_scene_id in seen_scene_ids:
                    continue
                seen_scene_ids.add(normalized_scene_id)
                merged_scene_ids.append(normalized_scene_id)
        canonical_mention_segment_ids[canonical_key] = sorted(merged_scene_ids)

        if canonical_key in person_display_names:
            canonical_display_names[canonical_key] = person_display_names[canonical_key]

        for variant_key in variant_keys:
            if variant_key == canonical_key:
                continue
            canonical_aligned_counts.pop(variant_key, None)
            canonical_dominant_segment_counts.pop(variant_key, None)
            canonical_mention_segment_ids.pop(variant_key, None)
            canonical_display_names.pop(variant_key, None)

    return (
        canonical_display_names,
        canonical_aligned_counts,
        canonical_dominant_segment_counts,
        canonical_mention_segment_ids,
    )


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
    if emotion_scores:
        top_label, top_score = max(emotion_scores.items(), key=lambda item: item[1])
        promoted_score = emotion_scores.get(normalized_emotion)
        if promoted_score is None or promoted_score < _AUDIO_EMOTION_PROMOTION_THRESHOLD:
            normalized_emotion = top_label if top_score >= _AUDIO_EMOTION_PROMOTION_THRESHOLD else ""
    if normalized_emotion in {"", "unknown", "unavailable", "none", "null"}:
        normalized_emotion = ""

    return (normalized_emotion or None), emotion_scores


def _rank_audio_emotion_scores(
    emotion_scores: Dict[str, float],
    *,
    promoted_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    promoted = str(promoted_label or "").strip().lower()
    rows: List[Dict[str, Any]] = []
    normalized_scores: List[tuple[str, float]] = []
    for label, score in emotion_scores.items():
        normalized_label = str(label or "").strip().lower()
        if not normalized_label:
            continue
        try:
            normalized_scores.append((normalized_label, float(score)))
        except (TypeError, ValueError):
            continue
    for rank, (label, score) in enumerate(
        sorted(normalized_scores, key=lambda item: (-item[1], item[0])),
        start=1,
    ):
        is_promoted = bool(promoted and label == promoted and score >= _AUDIO_EMOTION_PROMOTION_THRESHOLD)
        rows.append(
            {
                "label": label,
                "score": round(score, 3),
                "rank": rank,
                "promoted": is_promoted,
                "promotion_threshold": _AUDIO_EMOTION_PROMOTION_THRESHOLD,
                "scope": "promoted_label" if is_promoted else "ranked_score_not_promoted",
            }
        )
    return rows


def _rank_text_emotions(raw_emotions: Any) -> List[Dict[str, Any]]:
    rows: List[tuple[str, float]] = []
    if isinstance(raw_emotions, dict):
        iterable = raw_emotions.items()
    elif isinstance(raw_emotions, list):
        iterable = []
        for item in raw_emotions:
            if not isinstance(item, dict):
                continue
            iterable.append((item.get("label") or item.get("emotion"), item.get("score")))
    else:
        iterable = []

    for label, score in iterable:
        normalized_label = str(label or "").strip().lower()
        if not normalized_label:
            continue
        try:
            rows.append((normalized_label, float(score)))
        except (TypeError, ValueError):
            continue

    return [
        {"label": label, "score": round(score, 3), "rank": rank}
        for rank, (label, score) in enumerate(
            sorted(rows, key=lambda item: (-item[1], item[0])),
            start=1,
        )
    ]


def _resolve_audio_sentiment(
    scene_audio_payload: Dict[str, Any],
) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[float]]:
    sentiment = scene_audio_payload.get("sentiment")
    if not isinstance(sentiment, dict):
        return None, None, None

    label = sentiment.get("label")
    normalized_label = str(label).strip() if label is not None else None

    score_value: Optional[float] = None
    raw_score = sentiment.get("score")
    if raw_score is not None:
        try:
            score_value = float(raw_score)
        except (TypeError, ValueError):
            score_value = None

    return sentiment, normalized_label or None, score_value


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


def _time_hints_have_values(time_hints: Any) -> bool:
    if not isinstance(time_hints, dict):
        return False
    for key, value in time_hints.items():
        if str(key).strip().lower() == "first_seen_ts":
            continue
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _merge_time_hint_dicts(*hint_sources: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for hints in hint_sources:
        if not isinstance(hints, dict):
            continue
        for key, value in hints.items():
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                existing = merged.setdefault(key, [])
                if not isinstance(existing, list):
                    continue
                for item in value:
                    if item not in existing:
                        existing.append(item)
                continue
            if isinstance(value, dict):
                existing_dict = merged.setdefault(key, {})
                if isinstance(existing_dict, dict):
                    existing_dict.update(value)
                continue
            merged[key] = value
    return merged


def _resolve_scene_time_hints(scene_audio_payload: Dict[str, Any], scene_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    audio_hints = scene_audio_payload.get("time_hints")
    frame_hints: Any = None
    if isinstance(scene_payload, dict):
        if isinstance(scene_payload.get("time_hints"), dict):
            frame_hints = scene_payload.get("time_hints")
        keyframe = scene_payload.get("keyframe")
        if not _time_hints_have_values(frame_hints) and isinstance(keyframe, dict):
            frame_hints = keyframe.get("time_hints")

    if _time_hints_have_values(audio_hints) and _time_hints_have_values(frame_hints):
        return _merge_time_hint_dicts(audio_hints, frame_hints)
    if _time_hints_have_values(audio_hints):
        return audio_hints
    if _time_hints_have_values(frame_hints):
        return frame_hints
    return audio_hints if isinstance(audio_hints, dict) else {}


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

    raw_primary_tags = _clean_list(raw_context.get("primary_tags"), limit=8)
    raw_contextual_tags = _clean_list(raw_context.get("contextual_tags"), limit=8)
    raw_structural_tags = _clean_list(raw_context.get("structural_tags"), limit=8)
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
    sanitized["primary_tags"] = raw_primary_tags[:5]
    sanitized["contextual_tags"] = raw_contextual_tags[:5]
    sanitized["structural_tags"] = raw_structural_tags[:5]
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


def _collect_entity_texts(values: Any) -> List[str]:
    texts: List[str] = []
    if not isinstance(values, list):
        return texts
    for value in values:
        normalized = _normalize_entity_rollup_record(value)
        if normalized:
            texts.append(normalized["text"].strip().lower())
    return texts


_ARBITRATION_DISCOURSE_TOPIC_TOKENS = {
    "because",
    "every",
    "first",
    "goodbye",
    "great",
    "hello",
    "maybe",
    "thanks",
}
_LOW_VALUE_ARBITRATION_VISUAL_CLAIMS = {
    "conversation",
    "man",
    "person",
    "men",
    "men sitting",
    "men in a store",
    "woman",
    "man and woman",
    "woman in a suit",
    "spoken topic",
}


def _text_contains_phrase(text: str, phrase: str) -> bool:
    haystack = str(text or "").strip().casefold()
    needle = str(phrase or "").strip().casefold()
    if not haystack or not needle:
        return False
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", re.IGNORECASE)
    return bool(pattern.search(haystack))


def _collect_scene_identity_names(scene_meta: Dict[str, Any]) -> set[str]:
    identity_names: set[str] = set()
    owner = _normalize_entity_rollup_record(scene_meta.get("conversation_owner"))
    if owner:
        identity_names.add(owner["text"].casefold())
    for person in _collect_entity_texts(scene_meta.get("mentioned_people")):
        identity_names.add(person.casefold())
    for person in _collect_entity_texts(scene_meta.get("visible_people")):
        identity_names.add(person.casefold())
    for person in _collect_entity_texts(scene_meta.get("candidate_visible_people")):
        identity_names.add(person.casefold())
    return identity_names


def _is_supported_arbitration_topic(
    topic: str,
    *,
    identity_names: set[str],
) -> bool:
    normalized = str(topic or "").strip()
    lowered = normalized.casefold()
    if not normalized:
        return False
    if _scene_context_is_low_value_topic_fragment(normalized):
        return False
    if lowered in _ARBITRATION_DISCOURSE_TOPIC_TOKENS:
        return False
    if lowered.startswith("personal "):
        return False
    if lowered in identity_names:
        return False

    tokens = [token for token in re.findall(r"[A-Za-z0-9]+", normalized) if token]
    if not tokens:
        return False
    if len(tokens) == 1 and normalized[0].isupper():
        return False
    return True


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

    supported_topics = [hint for hint in topic_hints if hint and _text_contains_phrase(context_blob, hint)]
    for hint in supported_topics[:3]:
        evidence.append({"role": "support", "kind": "transcript_topic", "value": hint})
    if supported_topics:
        families.append("transcript")

    supported_visual: List[str] = []
    if caption and not _scene_context_caption_is_low_signal(caption):
        for tag in context_tags:
            if tag in _LOW_VALUE_ARBITRATION_VISUAL_CLAIMS:
                continue
            if tag and _text_contains_phrase(caption_lower, tag) and tag not in supported_visual:
                supported_visual.append(tag)
    for label in object_labels:
        if label in _LOW_VALUE_ARBITRATION_VISUAL_CLAIMS:
            continue
        if _text_contains_phrase(context_blob, label) and label not in supported_visual:
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


def _derive_scene_context_arbitration(
    scene_meta: Dict[str, Any],
    scene_context: Dict[str, Any],
    scene_context_epistemic: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(scene_context, dict):
        return None

    transcript = str(scene_meta.get("transcript") or "").strip()
    caption = str(scene_meta.get("caption") or "").strip()
    context_blob = _scene_context_text_blob(scene_context)
    identity_names = _collect_scene_identity_names(scene_meta)
    topic_hints = [
        hint
        for hint in _scene_context_extract_transcript_topic_hints(transcript)
        if _is_supported_arbitration_topic(hint, identity_names=identity_names)
    ]
    raw_primary_tags = scene_context.get("primary_tags")
    primary_tag_values = raw_primary_tags if isinstance(raw_primary_tags, list) else []
    primary_tags = {
        str(tag).strip().casefold()
        for tag in primary_tag_values
        if isinstance(tag, str) and tag.strip()
    }
    raw_contextual_tags = scene_context.get("contextual_tags")
    contextual_tag_values = raw_contextual_tags if isinstance(raw_contextual_tags, list) else []
    contextual_tags = {
        str(tag).strip().casefold()
        for tag in contextual_tag_values
        if isinstance(tag, str) and tag.strip()
    }
    has_tiered_tags = bool(primary_tags or contextual_tags or isinstance(scene_context.get("structural_tags"), list))

    if has_tiered_tags:
        supported_topics = [hint for hint in topic_hints if hint and hint.casefold() in primary_tags]
        contextual_topic_hints = [
            hint
            for hint in topic_hints
            if hint
            and hint.casefold() in contextual_tags
            and hint not in supported_topics
        ]
    else:
        supported_topics = [hint for hint in topic_hints if hint and _text_contains_phrase(context_blob, hint)]
        contextual_topic_hints = []
    object_labels = _extract_scene_object_labels(scene_meta.get("objects"))
    caption_lower = caption.lower()
    top_emotion = None
    emotions = scene_meta.get("emotions") if isinstance(scene_meta.get("emotions"), list) else []
    if emotions:
        top_emotion = str(emotions[0].get("label") or "").strip().lower() or None
    emotional_arc = str(scene_context.get("emotional_arc") or "").strip().lower()

    hypotheses: List[Dict[str, str]] = []
    evidence_conflicts: List[Dict[str, Any]] = []
    unresolved_axes: List[str] = []

    def _add_hypothesis(axis: str, claim: str, evidence_family: str, weight: str) -> None:
        normalized_claim = str(claim or "").strip()
        if not normalized_claim:
            return
        candidate = {
            "axis": axis,
            "claim": normalized_claim,
            "evidence_family": evidence_family,
            "weight": weight,
        }
        if candidate not in hypotheses:
            hypotheses.append(candidate)

    for topic in supported_topics[:2]:
        _add_hypothesis("topic", topic, "transcript", "primary")
    for topic in contextual_topic_hints[:2]:
        _add_hypothesis("context", topic, "transcript", "supporting")

    supported_visual: List[str] = []
    raw_tags = scene_context.get("context_tags")
    context_tags = [
        str(tag).strip().lower()
        for tag in raw_tags
        if isinstance(raw_tags, list) and isinstance(tag, str) and tag.strip()
    ]
    if caption and not _scene_context_caption_is_low_signal(caption):
        for tag in context_tags:
            if tag in _LOW_VALUE_ARBITRATION_VISUAL_CLAIMS:
                continue
            if _text_contains_phrase(caption_lower, tag) and tag not in supported_visual:
                supported_visual.append(tag)
    for label in object_labels:
        if label in _LOW_VALUE_ARBITRATION_VISUAL_CLAIMS:
            continue
        if _text_contains_phrase(context_blob, label) and label not in supported_visual:
            supported_visual.append(label)
    for tag in supported_visual[:2]:
        _add_hypothesis("setting", tag, "visual", "supporting")

    if top_emotion and top_emotion in emotional_arc:
        _add_hypothesis("tone", top_emotion, "audio", "supporting")

    owner = _normalize_entity_rollup_record(scene_meta.get("conversation_owner"))
    if owner:
        _add_hypothesis("conversation_focus", owner["text"], "identity", "supporting")
    else:
        mentioned_people = _collect_entity_texts(scene_meta.get("mentioned_people"))
        visible_people = _collect_entity_texts(scene_meta.get("visible_people"))
        candidate_people = _collect_entity_texts(scene_meta.get("candidate_visible_people"))
        for person in (mentioned_people + visible_people + candidate_people)[:1]:
            _add_hypothesis("conversation_focus", person, "identity", "supporting")

    reflected_transcript_topics = supported_topics + contextual_topic_hints
    if topic_hints and not reflected_transcript_topics and transcript:
        evidence_conflicts.append(
            {
                "axis": "topic",
                "reason": "transcript_topics_not_reflected",
                "transcript_topics": topic_hints[:3],
            }
        )
        unresolved_axes.append("topic")

    if top_emotion and top_emotion not in emotional_arc:
        evidence_conflicts.append(
            {
                "axis": "tone",
                "reason": "audio_emotion_not_reflected",
                "audio_emotion": top_emotion,
            }
        )
        unresolved_axes.append("tone")

    if not hypotheses and scene_context_epistemic and scene_context_epistemic.get("fallback_mode"):
        unresolved_axes.append("low_signal")

    resolved_by = "unknown"
    if isinstance(scene_context_epistemic, dict):
        resolved_by = str(scene_context_epistemic.get("dominant_evidence") or "").strip().lower() or "unknown"

    if not hypotheses and not evidence_conflicts and not unresolved_axes:
        return None

    return {
        "read_model_version": EPISTEMIC_READ_MODEL_VERSION,
        "resolved_by": resolved_by,
        "hypotheses": hypotheses[:4],
        "evidence_conflicts": evidence_conflicts[:3],
        "unresolved_axes": unresolved_axes[:3],
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

        (
            person_display_names,
            person_aligned_counts,
            person_dominant_segment_counts,
            person_mention_segment_ids,
        ) = _canonicalize_chain_person_mentions(
            person_display_names,
            person_aligned_counts,
            person_dominant_segment_counts,
            person_mention_segment_ids,
        )

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
    force = cfg.get("force_reprocess", False)
    for segment in unified_segments:
        if force:
            segment["scene_context_llm"] = None
            segment["scene_context_epistemic"] = None
            segment["scene_context_arbitration"] = None

    if not SCENE_CONTEXT_LLM_AVAILABLE or not _scene_context_llm_enabled(cfg):
        return

    for segment in unified_segments:
        if not force and segment.get("scene_context_llm") is not None:
            continue

        if _normalize_content_state(segment.get("content_state")) != "signal":
            continue

        scene = scene_lookup.get(str(segment.get("scene_id") or ""))
        if not isinstance(scene, dict):
            continue

        keyframe_payload = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
        scene_audio_payload = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
        transcript_text = str(segment.get("full_transcript") or "").strip()
        scene_objects = segment.get("detected_objects")
        if not isinstance(scene_objects, list):
            scene_objects = scene.get("objects")
        if not isinstance(scene_objects, list):
            scene_objects = keyframe_payload.get("objects")
        if not isinstance(scene_objects, list):
            scene_objects = []
        face_count = int(segment.get("visible_face_count") or 0)
        caption_text = str(scene.get("caption") or keyframe_payload.get("caption") or "").strip()
        ocr_text = str(segment.get("ocr_text") or scene.get("ocr_text") or keyframe_payload.get("ocr_text") or "").strip()
        music_events = segment.get("music_events") or scene.get("music_events") or scene_audio_payload.get("music_events") or []
        time_hints = (
            segment.get("time_hints")
            or scene.get("time_hints")
            or keyframe_payload.get("time_hints")
            or scene_audio_payload.get("time_hints")
            or {}
        )
        metadata_time_hints = (
            segment.get("metadata_time_hints")
            or scene.get("metadata_time_hints")
            or scene_audio_payload.get("metadata_time_hints")
            or {}
        )

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

        if (
            not transcript_text
            and not scene_objects
            and face_count <= 0
            and not caption_text
            and not ocr_text
            and not music_events
            and not time_hints
            and not metadata_time_hints
            and not emotions_payload
        ):
            continue

        scene_meta = {
            "index": scene.get("index"),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "caption": caption_text,
            "transcript": transcript_text,
            "objects": scene_objects,
            "ocr_text": ocr_text,
            "music_events": music_events,
            "time_hints": time_hints,
            "metadata_time_hints": metadata_time_hints,
            "face_count": face_count,
            "emotions": emotions_payload,
            "speakers": segment.get("speaker_ids") or [],
            "conversation_owner": segment.get("conversation_owner"),
            "visible_people": segment.get("visible_people") or [],
            "mentioned_people": segment.get("mentioned_people") or [],
            "candidate_visible_people": segment.get("candidate_visible_people") or [],
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
            segment["scene_context_arbitration"] = _derive_scene_context_arbitration(
                scene_meta,
                sanitized_context,
                segment.get("scene_context_epistemic"),
            )


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
        "visual_caption",
        "ocr_text",
        "ocr_date_candidates",
        "music_events",
        "time_hints",
        "metadata_time_hints",
        "audio_emotion",
        "audio_emotion_scores",
        "audio_emotion_ranking",
        "audio_emotion_top_candidate",
        "audio_emotion_promotion_threshold",
        "text_emotion_ranking",
        "text_emotion_meta",
        "clap_meta",
        "sentiment",
        "sentiment_label",
        "sentiment_score",
        "sentiment_meta",
        "scene_context_llm",
        "scene_context_epistemic",
        "scene_context_arbitration",
        "speaker_voice_signature_count",
        "speaker_voice_signature_meta",
        "speaker_count",
        "diarization_status",
        "diarization_error",
        "diarization_note",
        "emotion_status",
        "emotion_error",
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


def _empty_commit_presence() -> Dict[str, Any]:
    return {
        'available': False,
        'has_audio': False,
        'has_transcripts': False,
        'audio_scene_ids': set(),
        'transcript_scene_ids': set(),
    }


def _load_isolated_commit_presence(
    cfg: Dict[str, Any],
    video_id: str,
    scene_ids: List[str] | None = None,
) -> Dict[str, Any]:
    """Read the epoch-local commit ledger used by isolated ingestion runs.

    Isolation intentionally avoids writing observability rows into ``memory.db``.
    The append-only JSONL ledger is therefore the authoritative commit projection
    for that run; treating its absence as an empty SQLite table would make real
    committed vectors appear unavailable in the temporal index.
    """
    presence = _empty_commit_presence()
    paths = (cfg.get('paths') or {}) if isinstance(cfg, dict) else {}
    log_dir = paths.get('log_dir')
    if not isinstance(log_dir, str) or not log_dir.strip():
        return presence

    jsonl_path = Path(log_dir) / 'memory_commit_events.jsonl'
    if not jsonl_path.is_file():
        return presence

    selected_scene_ids = {str(scene_id) for scene_id in (scene_ids or []) if scene_id}
    audio_scene_ids: set[str] = set()
    transcript_scene_ids: set[str] = set()
    try:
        with jsonl_path.open('r', encoding='utf-8') as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if str(event.get('video_id') or '') != video_id:
                    continue
                if event.get('attempted') is not True or event.get('committed') is not True:
                    continue
                scene_id = str(event.get('scene_id') or '')
                if selected_scene_ids and scene_id not in selected_scene_ids:
                    continue
                modality = event.get('modality')
                if modality == 'audio' and scene_id:
                    audio_scene_ids.add(scene_id)
                elif modality == 'audio_transcript' and scene_id:
                    transcript_scene_ids.add(scene_id)
    except OSError as exc:
        logger.warning(
            '[HARMONIZER] Failed to read isolated commit ledger path=%s exc_type=%s exc=%s',
            jsonl_path,
            type(exc).__name__,
            exc,
        )
        return presence

    presence['available'] = True
    presence['audio_scene_ids'] = audio_scene_ids
    presence['transcript_scene_ids'] = transcript_scene_ids
    presence['has_audio'] = bool(audio_scene_ids)
    presence['has_transcripts'] = bool(transcript_scene_ids)
    return presence


def _load_commit_presence(cfg: Dict[str, Any], video_id: str, scene_ids: List[str] | None = None) -> Dict[str, Any]:
    """Derive modality presence from the run's authoritative commit ledger."""
    if isinstance(cfg, dict) and cfg.get('ingestion_isolation', False):
        return _load_isolated_commit_presence(cfg, video_id, scene_ids)

    presence = _empty_commit_presence()

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
        keyframe_payload = scene.get('keyframe') if isinstance(scene.get('keyframe'), dict) else {}
        visual_caption = (
            scene.get('visual_caption')
            or scene.get('caption')
            or keyframe_payload.get('caption')
            or ''
        )
        ocr_text = scene.get('ocr_text') or keyframe_payload.get('ocr_text') or ''
        raw_ocr_date_candidates = (
            scene.get('ocr_date_candidates')
            or scene.get('date_candidates')
            or keyframe_payload.get('date_candidates')
            or []
        )
        if isinstance(raw_ocr_date_candidates, list):
            ocr_date_candidates = [
                str(candidate).strip()
                for candidate in raw_ocr_date_candidates
                if str(candidate or '').strip()
            ]
        else:
            candidate_text = str(raw_ocr_date_candidates or '').strip()
            ocr_date_candidates = [candidate_text] if candidate_text else []
        scene_objects = _resolve_scene_objects(scene, scene_id, objects_data)
        music_events = _resolve_scene_music_events(scene_audio_payload)
        time_hints = _resolve_scene_time_hints(scene_audio_payload, scene)
        metadata_time_hints = _resolve_scene_metadata_time_hints(scene_audio_payload)
        audio_emotion, audio_emotion_scores = _resolve_audio_emotion(scene_audio_payload)
        audio_emotion_ranking = _rank_audio_emotion_scores(audio_emotion_scores, promoted_label=audio_emotion)
        audio_emotion_top_candidate = audio_emotion_ranking[0] if audio_emotion_ranking else None
        text_emotion_ranking = _rank_text_emotions(scene_audio_payload.get("emotions"))
        text_emotion_meta = (
            scene_audio_payload.get("emotion_meta")
            if isinstance(scene_audio_payload.get("emotion_meta"), dict)
            else None
        )
        sentiment, sentiment_label, sentiment_score = _resolve_audio_sentiment(scene_audio_payload)
        sentiment_meta = (
            scene_audio_payload.get("sentiment_meta")
            if isinstance(scene_audio_payload.get("sentiment_meta"), dict)
            else None
        )
        clap_meta = scene_audio_payload.get('clap_meta') if isinstance(scene_audio_payload.get('clap_meta'), dict) else None
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
            'visual_caption': visual_caption,
            'ocr_text': ocr_text,
            'ocr_date_candidates': ocr_date_candidates,
            
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
            'speaker_voice_signature_meta': scene_audio_payload.get('speaker_voice_signature_meta'),
            'diarization_status': scene_audio_payload.get('diarization_status'),
            'diarization_error': scene_audio_payload.get('diarization_error'),
            'diarization_note': scene_audio_payload.get('diarization_note'),
            'music_events': music_events,
            'time_hints': time_hints,
            'metadata_time_hints': metadata_time_hints,
            'audio_emotion': audio_emotion,
            'audio_emotion_scores': audio_emotion_scores,
            'audio_emotion_ranking': audio_emotion_ranking,
            'audio_emotion_top_candidate': audio_emotion_top_candidate,
            'audio_emotion_promotion_threshold': _AUDIO_EMOTION_PROMOTION_THRESHOLD,
            'text_emotion_ranking': text_emotion_ranking,
            'text_emotion_meta': text_emotion_meta,
            'clap_meta': clap_meta,
            'sentiment': sentiment,
            'sentiment_label': sentiment_label,
            'sentiment_score': sentiment_score,
            'sentiment_meta': sentiment_meta,
            'emotion_status': scene_audio_payload.get('emotion_status'),
            'emotion_error': scene_audio_payload.get('emotion_error'),
            'scene_context_llm': scene.get('scene_context_llm'),
            'scene_context_epistemic': scene.get('scene_context_epistemic'),
            'scene_context_arbitration': scene.get('scene_context_arbitration'),
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
    for segment in unified_segments:
        transcript_entity_projection = _segment_transcript_entity_projection(segment)
        segment["transcript_entity_disagreements"] = transcript_entity_projection["disagreements"]
        segment["normalization_applied"] = transcript_entity_projection["normalization_applied"]
        segment["normalization_source"] = transcript_entity_projection["normalization_source"]

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
    speaker_aligned_mention_counts: Dict[str, int] = {}
    music_event_counts: Dict[str, int] = {}
    time_hint_counts: Dict[str, int] = {}
    metadata_time_hint_counts: Dict[str, int] = {}
    audio_emotion_counts: Dict[str, int] = {}
    audio_emotion_score_counts: Dict[str, List[float]] = {}
    text_emotion_score_counts: Dict[str, List[float]] = {}
    sentiment_label_counts: Dict[str, int] = {}
    scene_context_tag_counts: Dict[str, int] = {}
    scene_context_epistemic_state_counts: Dict[str, int] = {}
    scene_context_epistemic_dominant_counts: Dict[str, int] = {}
    scene_context_arbitration_resolved_counts: Dict[str, int] = {}
    scene_context_arbitration_unresolved_counts: Dict[str, int] = {}
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
        for mention in seg.get("speaker_aligned_mentions", []):
            normalized_mention = _normalize_entity_rollup_record(mention)
            if not normalized_mention:
                continue
            mention_key = f"{normalized_mention['text'].lower()}:{normalized_mention['type']}"
            mention_count = mention.get("count", 1) if isinstance(mention, dict) else 1
            try:
                mention_count_value = max(int(mention_count), 1)
            except (TypeError, ValueError):
                mention_count_value = 1
            speaker_aligned_mention_counts[mention_key] = (
                speaker_aligned_mention_counts.get(mention_key, 0) + mention_count_value
            )
        for event_label in _extract_music_event_labels(seg.get('music_events', [])):
            music_event_counts[event_label] = music_event_counts.get(event_label, 0) + 1
        for time_hint in _extract_time_hint_tokens(seg.get('time_hints', {})):
            time_hint_counts[time_hint] = time_hint_counts.get(time_hint, 0) + 1
        for time_hint in _extract_time_hint_tokens(seg.get('metadata_time_hints', {})):
            metadata_time_hint_counts[time_hint] = metadata_time_hint_counts.get(time_hint, 0) + 1
        normalized_audio_emotion = str(seg.get('audio_emotion') or '').strip().lower()
        if normalized_audio_emotion:
            audio_emotion_counts[normalized_audio_emotion] = audio_emotion_counts.get(normalized_audio_emotion, 0) + 1
        audio_emotion_ranking = seg.get("audio_emotion_ranking")
        if isinstance(audio_emotion_ranking, list):
            for row in audio_emotion_ranking[:1]:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("label") or "").strip().lower()
                score = row.get("score")
                try:
                    score_value = float(score)
                except (TypeError, ValueError):
                    continue
                if label:
                    audio_emotion_score_counts.setdefault(label, []).append(score_value)
        text_emotion_ranking = seg.get("text_emotion_ranking")
        if isinstance(text_emotion_ranking, list):
            for row in text_emotion_ranking[:1]:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("label") or "").strip().lower()
                score = row.get("score")
                try:
                    score_value = float(score)
                except (TypeError, ValueError):
                    continue
                if label:
                    text_emotion_score_counts.setdefault(label, []).append(score_value)
        sentiment_label = str(seg.get("sentiment_label") or "").strip().lower()
        if sentiment_label:
            sentiment_label_counts[sentiment_label] = sentiment_label_counts.get(sentiment_label, 0) + 1
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
        scene_context_arbitration = seg.get("scene_context_arbitration")
        if isinstance(scene_context_arbitration, dict):
            resolved_by = str(scene_context_arbitration.get("resolved_by") or "").strip().lower()
            if resolved_by:
                scene_context_arbitration_resolved_counts[resolved_by] = (
                    scene_context_arbitration_resolved_counts.get(resolved_by, 0) + 1
                )
            unresolved_axes = scene_context_arbitration.get("unresolved_axes")
            if isinstance(unresolved_axes, list):
                for axis in unresolved_axes:
                    normalized_axis = str(axis or "").strip().lower()
                    if normalized_axis:
                        scene_context_arbitration_unresolved_counts[normalized_axis] = (
                            scene_context_arbitration_unresolved_counts.get(normalized_axis, 0) + 1
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
    top_speaker_aligned_mentions = sorted(
        speaker_aligned_mention_counts.items(),
        key=lambda item: (
            -item[1],
            item[0].rsplit(":", 1)[0],
            item[0].rsplit(":", 1)[1],
        ),
    )[:20]
    speaker_aligned_mention_variant_groups = _build_speaker_aligned_mention_variant_groups(
        speaker_aligned_mention_counts
    )
    transcript_entity_disagreement_summary = _build_transcript_entity_disagreement_summary(
        unified_segments
    )
    top_music_events = sorted(music_event_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_time_hints = sorted(time_hint_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_metadata_time_hints = sorted(metadata_time_hint_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_audio_emotions = sorted(audio_emotion_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    top_sentiment_labels = sorted(sentiment_label_counts.items(), key=lambda x: x[1], reverse=True)[:20]
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
    top_scene_context_arbitration_resolved = sorted(
        scene_context_arbitration_resolved_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:20]
    top_scene_context_arbitration_unresolved = sorted(
        scene_context_arbitration_unresolved_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:20]

    def _serialize_score_rollup(
        buckets: Dict[str, List[float]],
        *,
        key_name: str,
        scope: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for label, values in buckets.items():
            clean_values = [float(value) for value in values if isinstance(value, (int, float))]
            if not clean_values:
                continue
            row: Dict[str, Any] = {
                key_name: label,
                "count": len(clean_values),
                "average_score": round(sum(clean_values) / len(clean_values), 3),
                "max_score": round(max(clean_values), 3),
            }
            if scope:
                row["scope"] = scope
            rows.append(row)
        return sorted(
            rows,
            key=lambda row: (row.get("count") or 0, row.get("max_score") or 0),
            reverse=True,
        )[:20]

    top_audio_emotion_score_signals = _serialize_score_rollup(
        audio_emotion_score_counts,
        key_name="emotion",
        scope="ranked_score_signal",
    )
    top_text_emotions = _serialize_score_rollup(text_emotion_score_counts, key_name="emotion")
    
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

    content_summary = {
        'signal': sum(1 for state in segment_content_states if state == 'signal'),
        'empty': sum(1 for state in segment_content_states if state == 'empty'),
        'processing_error': sum(1 for state in segment_content_states if state == 'processing_error'),
    } if segment_content_states else None

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
        'segments_with_speaker_aligned_mentions': sum(1 for seg in unified_segments if seg.get('speaker_aligned_mentions')),
        'segments_with_music_events': sum(1 for seg in unified_segments if seg.get('music_events')),
        'segments_with_time_hints': sum(1 for seg in unified_segments if _extract_time_hint_tokens(seg.get('time_hints', {}))),
        'segments_with_metadata_time_hints': sum(1 for seg in unified_segments if _extract_time_hint_tokens(seg.get('metadata_time_hints', {}))),
        'segments_with_audio_emotion': sum(1 for seg in unified_segments if seg.get('audio_emotion')),
        'segments_with_audio_emotion_scores': sum(1 for seg in unified_segments if seg.get('audio_emotion_scores')),
        'segments_with_audio_emotion_ranking': sum(1 for seg in unified_segments if seg.get('audio_emotion_ranking')),
        'segments_with_text_emotion_ranking': sum(1 for seg in unified_segments if seg.get('text_emotion_ranking')),
        'segments_with_sentiment': sum(1 for seg in unified_segments if seg.get('sentiment_label')),
        'segments_with_speaker_voice_signatures': sum(1 for seg in unified_segments if seg.get('speaker_voice_signature_count', 0) > 0),
        'segments_with_scene_context_llm': sum(1 for seg in unified_segments if seg.get('scene_context_llm')),
        'segments_with_scene_context_epistemic': sum(1 for seg in unified_segments if seg.get('scene_context_epistemic')),
        'segments_with_scene_context_arbitration': sum(1 for seg in unified_segments if seg.get('scene_context_arbitration')),
        'segments_with_scene_context_arbitration_conflicts': sum(
            1
            for seg in unified_segments
            for arbitration in [seg.get('scene_context_arbitration')]
            if isinstance(arbitration, dict) and arbitration.get('evidence_conflicts')
        ),
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
        'top_speaker_aligned_mentions': _serialize_entity_count_pairs(top_speaker_aligned_mentions),
        'speaker_aligned_mention_variant_groups': speaker_aligned_mention_variant_groups,
        **transcript_entity_disagreement_summary,
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
        'top_audio_emotion_score_signals': top_audio_emotion_score_signals,
        'top_text_emotions': top_text_emotions,
        'top_sentiment_labels': [
            {'label': key, 'count': value}
            for key, value in top_sentiment_labels
        ],
        'audio_emotion_policy': {
            'promoted_label_threshold': _AUDIO_EMOTION_PROMOTION_THRESHOLD,
            'promoted_labels': sum(1 for seg in unified_segments if seg.get('audio_emotion')),
            'ranked_score_segments': sum(1 for seg in unified_segments if seg.get('audio_emotion_ranking')),
            'scope': 'ranked_scores_do_not_equal_labels',
        },
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
        'top_scene_context_arbitration_resolved_by': [
            {'resolved_by': key, 'count': value}
            for key, value in top_scene_context_arbitration_resolved
        ],
        'top_scene_context_arbitration_unresolved_axes': [
            {'axis': key, 'count': value}
            for key, value in top_scene_context_arbitration_unresolved
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
        'content_summary': content_summary,
        
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
    scene_data['phase5_complete'] = bool(scene_data.get('phase5_complete')) or bool(unified_segments)
    scene_data['total_scenes'] = len(unified_segments)
    scene_data['content_summary'] = content_summary
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
