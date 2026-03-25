from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

_NER_PIPELINES: Dict[str, Any] = {}

try:
    from steps.common.tag_utils import (
        dedupe_tokens,
        is_valid_entity_token,
        is_valid_tag_token,
        normalize_entity_token,
        normalize_tag_token,
    )
except Exception as e:
    def dedupe_tokens(tokens):
        seen = set()
        deduped = []
        for token in tokens:
            if token is None:
                continue
            text = str(token).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        return deduped
    def is_valid_entity_token(token):
        text = str(token or "").strip()
        return len(text) >= 3
    def normalize_entity_token(token):
        text = str(token or "").strip()
        return text or None
    def is_valid_tag_token(token):
        text = str(token or "").strip()
        return len(text) >= 3
    def normalize_tag_token(token):
        text = str(token or "").strip()
        return text or None


_PERSON_ENTITY_TYPES = {"PERSON", "PER", "CHARACTER"}
_TAG_TYPE_WEIGHTS = {
    "LOCATION": 3.0,
    "LOC": 3.0,
    "GPE": 3.0,
    "FAC": 2.5,
    "ORG": 2.0,
    "EVENT": 2.0,
}
_ENTITY_TYPE_WEIGHTS = {
    "PERSON": 4.0,
    "PER": 4.0,
    "CHARACTER": 4.0,
    "LOCATION": 3.0,
    "LOC": 3.0,
    "GPE": 3.0,
    "FAC": 2.5,
    "ORG": 2.0,
    "EVENT": 2.0,
}


def _get_ner_pipeline(model_id: str) -> Any:
    pipeline_obj = _NER_PIPELINES.get(model_id)
    if pipeline_obj is not None:
        return pipeline_obj
    from transformers import pipeline, logging as hf_logging  # type: ignore
    hf_logging.set_verbosity_error()
    pipe = pipeline(
        "token-classification",
        model=model_id,
        aggregation_strategy="simple",
    )
    _NER_PIPELINES[model_id] = pipe
    return pipe

def _speaker_transcript_text(item: Dict[str, Any]) -> str:
    speaker_transcript = item.get("speaker_transcript")
    if not isinstance(speaker_transcript, list):
        return ""
    parts: List[str] = []
    for segment in speaker_transcript:
        if not isinstance(segment, dict):
            continue
        text = segment.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return " ".join(parts)


def _gather_text(item: Dict[str, Any]) -> str:
    texts: List[str] = []
    seen: set[str] = set()
    for k in ("transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            text = v.strip()
            if text not in seen:
                seen.add(text)
                texts.append(text)
    speaker_text = _speaker_transcript_text(item)
    if speaker_text and speaker_text not in seen:
        texts.append(speaker_text)
    return "\n".join(texts)


def _usefulness_score(text: str, *, entity_count: int = 0, tag_count: int = 0) -> float:
    if not text:
        return 0.0
    tokens = [t for t in re.findall(r"[A-Za-z][A-Za-z']+", text) if len(t) > 3]
    source_count = max(1, len([part for part in text.split("\n") if part.strip()]))
    base = min(0.45, len(tokens) / 80.0)
    source_bonus = min(0.2, source_count * 0.05)
    entity_bonus = min(0.2, entity_count * 0.04)
    tag_bonus = min(0.15, tag_count * 0.03)
    return min(1.0, base + source_bonus + entity_bonus + tag_bonus)


def _extract_entities_transformers(text: str, cfg: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, str]]]:
    try:
        model_id = (
            ((cfg.get("config", {}) or {}).get("tagger", {}) or {}).get("ner_model")
            or "dslim/bert-base-NER"
        )
        nlp = _get_ner_pipeline(model_id)
        ents = nlp(text)
        labels = []
        structured = []
        seen_structured = set()
        for e in ents:
            word = (e.get("word") or "").strip()
            entity_group = (e.get("entity_group") or e.get("entity") or "").strip().upper()
            normalized = normalize_entity_token(word)
            if normalized and is_valid_entity_token(normalized):
                labels.append(normalized)
                key = (normalized.casefold(), entity_group)
                if key in seen_structured:
                    continue
                seen_structured.add(key)
                structured.append(
                    {
                        "name": normalized,
                        "type": entity_group,
                        "source_step": "tagger",
                        "source_modality": "text",
                    }
                )
        return list(dict.fromkeys(labels))[:20], structured[:20]
    except Exception as e:
        return [], []


def _fallback_entities(text: str) -> List[str]:
    pattern = re.compile(r"\b(?:[A-Z][A-Za-z']{1,}(?:\s+[A-Z][A-Za-z']{1,})*|[A-Z]{2,})\b")
    matches: List[str] = []
    for match in pattern.finditer(text):
        normalized = normalize_entity_token(match.group(0))
        if normalized and is_valid_entity_token(normalized):
            matches.append(normalized)
    return dedupe_tokens(matches)[:20]


def _coerce_entity_type(raw: Any) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.strip().upper()
    return ""


def _add_candidate(
    bucket: Dict[str, Dict[str, Any]],
    label: Any,
    score: float,
    source: str,
    *,
    validator,
    normalizer,
    candidate_type: str | None = None,
) -> None:
    normalized = normalizer(label)
    if normalized is None or not validator(normalized):
        return
    key = normalized.casefold()
    entry = bucket.get(key)
    if entry is None:
        entry = {
            "label": normalized,
            "score": 0.0,
            "sources": set(),
            "type": candidate_type,
        }
        bucket[key] = entry
    entry["score"] += float(score)
    entry["sources"].add(source)
    if candidate_type and not entry.get("type"):
        entry["type"] = candidate_type


def _sorted_candidates(bucket: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = sorted(
        bucket.values(),
        key=lambda item: (-float(item.get("score", 0.0)), str(item.get("label", "")).casefold()),
    )
    return [
        {
            "label": str(row["label"]),
            "score": round(float(row.get("score", 0.0)), 3),
            "sources": sorted(str(src) for src in row.get("sources", set())),
            "type": row.get("type"),
        }
        for row in rows
    ]


def _iter_object_labels(item: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for obj in item.get("objects") or []:
        if isinstance(obj, dict):
            labels.append(obj.get("label") or obj.get("class"))
        elif isinstance(obj, str):
            labels.append(obj)
    return [label for label in labels if isinstance(label, str) and label.strip()]


def _iter_music_labels(item: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for event in item.get("music_events") or []:
        if isinstance(event, dict):
            label = event.get("label")
            if isinstance(label, str) and label.strip():
                labels.append(label)
    return labels


def _iter_time_tokens(item: Dict[str, Any]) -> List[str]:
    time_hints = item.get("time_hints")
    if not isinstance(time_hints, dict):
        return []
    tokens: List[str] = []
    for key in ("explicit_dates", "times", "weekdays", "months", "relative_phrases"):
        values = time_hints.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value.strip():
                tokens.append(value)
    return tokens


def _rank_entities(ner_entities: List[Dict[str, str]], fallback_entities: List[str]) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = {}
    for entity in ner_entities:
        name = entity.get("name")
        ent_type = _coerce_entity_type(entity.get("type"))
        score = 6.0 + _ENTITY_TYPE_WEIGHTS.get(ent_type, 1.0)
        _add_candidate(
            bucket,
            name,
            score,
            "ner",
            validator=is_valid_entity_token,
            normalizer=normalize_entity_token,
            candidate_type=ent_type or None,
        )
    for name in fallback_entities:
        _add_candidate(
            bucket,
            name,
            2.5,
            "fallback",
            validator=is_valid_entity_token,
            normalizer=normalize_entity_token,
        )
    return _sorted_candidates(bucket)


def _rank_tags(
    item: Dict[str, Any],
    ner_entities: List[Dict[str, str]],
    fallback_entities: List[str],
) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = {}
    for label in _iter_object_labels(item):
        _add_candidate(
            bucket,
            label,
            5.0,
            "object",
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
        )
    for label in item.get("place_tags") or []:
        _add_candidate(
            bucket,
            label,
            4.5,
            "place",
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
        )
    for label in _iter_music_labels(item):
        _add_candidate(
            bucket,
            label,
            4.0,
            "music",
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
        )
    for label in _iter_time_tokens(item):
        _add_candidate(
            bucket,
            label,
            2.5,
            "time",
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
        )
    for entity in ner_entities:
        ent_type = _coerce_entity_type(entity.get("type"))
        if ent_type in _PERSON_ENTITY_TYPES:
            continue
        _add_candidate(
            bucket,
            entity.get("name"),
            3.0 + _TAG_TYPE_WEIGHTS.get(ent_type, 0.5),
            "typed_entity",
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
            candidate_type=ent_type or None,
        )
    for name in fallback_entities:
        if len(name.split()) < 2 and name[:1].isupper():
            continue
        _add_candidate(
            bucket,
            name,
            1.5,
            "fallback_entity",
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
        )
    return _sorted_candidates(bucket)


def tagger(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {
            "tags": [],
            "usefulness": 0.0,
            "entities": [],
            "ner_entities": [],
            "tag_details": [],
            "entity_details": [],
        }
    extracted_entities, ner_entities = _extract_entities_transformers(text, cfg)
    fallback_entities = _fallback_entities(text)
    if not extracted_entities:
        extracted_entities = fallback_entities
    entity_details = _rank_entities(ner_entities, extracted_entities)
    tag_details = _rank_tags(item, ner_entities, fallback_entities)
    entities = [entry["label"] for entry in entity_details[:10]]
    tags = [entry["label"] for entry in tag_details[:8]]
    score = _usefulness_score(text, entity_count=len(entities), tag_count=len(tags))
    return {
        "tags": tags,
        "usefulness": score,
        "entities": entities,
        "ner_entities": ner_entities,
        "tag_details": tag_details[:8],
        "entity_details": entity_details[:10],
    }
