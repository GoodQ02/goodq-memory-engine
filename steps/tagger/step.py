from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

_NER_PIPELINES: Dict[str, Any] = {}

try:
    from steps.common.tag_utils import (
        dedupe_tokens,
        is_valid_entity_token,
        normalize_entity_token,
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


def _usefulness_score(text: str) -> float:
    # Simple heuristic: scale by length and presence of informative tokens
    if not text:
        return 0.0
    tokens = [t for t in text.split() if len(t) > 3]
    keywords = sum(1 for t in tokens if t[0].isupper())
    return min(1.0, (len(tokens) / 200.0) + (keywords / 100.0))


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


def tagger(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"tags": [], "usefulness": 0.0, "entities": [], "ner_entities": []}
    ents, ner_entities = _extract_entities_transformers(text, cfg)
    ents = ents or _fallback_entities(text)
    ents = dedupe_tokens(
        ents,
        validator=is_valid_entity_token,
        normalizer=normalize_entity_token,
    )
    score = _usefulness_score(text)
    tags = ents[:5]
    return {
        "tags": tags,
        "usefulness": score,
        "entities": ents,
        "ner_entities": ner_entities,
    }
