from __future__ import annotations
from typing import Any, Dict, List

_NER_PIPELINES: Dict[str, Any] = {}

try:
    from steps.common.tag_utils import dedupe_tokens
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

def _gather_text(item: Dict[str, Any]) -> str:
    for k in ("transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _usefulness_score(text: str) -> float:
    # Simple heuristic: scale by length and presence of informative tokens
    if not text:
        return 0.0
    tokens = [t for t in text.split() if len(t) > 3]
    keywords = sum(1 for t in tokens if t[0].isupper())
    return min(1.0, (len(tokens) / 200.0) + (keywords / 100.0))


def _extract_entities_transformers(text: str, cfg: Dict[str, Any]) -> List[str]:
    try:
        model_id = (
            ((cfg.get("config", {}) or {}).get("tagger", {}) or {}).get("ner_model")
            or "dslim/bert-base-NER"
        )
        nlp = _get_ner_pipeline(model_id)
        ents = nlp(text)
        labels = []
        for e in ents:
            word = (e.get("word") or e.get("entity_group") or "").strip()
            if word:
                labels.append(word)
        return list(dict.fromkeys(labels))[:20]
    except Exception as e:
        return []


def _fallback_entities(text: str) -> List[str]:
    # crude fallback: capitalized words as entities
    words = [w.strip(".,;:!?") for w in text.split()]
    caps = [w for w in words if len(w) > 2 and w[0].isupper()]
    return list(dict.fromkeys(caps))[:20]


def tagger(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"tags": [], "usefulness": 0.0, "entities": []}
    ents = _extract_entities_transformers(text, cfg) or _fallback_entities(text)
    ents = dedupe_tokens(ents)
    score = _usefulness_score(text)
    tags = ents[:5]
    return {"tags": tags, "usefulness": score, "entities": ents}
