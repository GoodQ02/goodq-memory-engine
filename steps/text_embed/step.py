from __future__ import annotations
from typing import Any, Dict, List, Optional

import os
import hashlib
import json
import logging
import re

from steps.common.memory import upsert_embedding, to_faiss_id
from steps.common.faiss_utils import create_hnsw_id_index
from steps.common.memory_router import MemoryRouter
from steps.common.memory_stores import build_text_stores

logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from gpu_config import setup_step_gpu, GPUManager
except ImportError:
    try:
        from gpu_config import setup_step_gpu, GPUManager
    except ImportError:
        def setup_step_gpu(step_name):
            return {"device": "cpu", "step_name": step_name}
        class GPUManager:
            @staticmethod
            def clear_cache():
                pass


_ST = None  # sentence-transformers model
_FAISS = None

_SEMANTIC_STOPWORDS = {
    "a", "an", "and", "all", "always", "am", "any", "are", "around", "as", "at",
    "be", "because", "been", "being", "but", "by", "can", "could", "did", "do",
    "does", "done", "for", "from", "get", "got", "had", "has", "have", "he",
    "hello", "hey", "hi", "hold", "how", "i", "i'm", "i've", "i'll", "i'd", "if",
    "in", "into", "is", "it", "it's", "its", "just", "let's", "look", "me", "maybe",
    "my", "never", "no", "not", "now", "of", "ok", "okay", "once", "or", "our",
    "out", "people", "right", "same", "see", "she", "so", "than", "that's", "the",
    "their", "them", "then", "there", "these", "they", "they're", "this", "those",
    "to", "too", "until", "very", "was", "we", "we're", "well", "were", "what",
    "when", "where", "wherever", "which", "who", "why", "will", "with", "would",
    "whatever", "like", "many",
    "yeah", "yellow", "yes", "you", "you're", "your",
}
_SEMANTIC_CONTRACTION_PARTS = {"'m", "'re", "'s", "'ll", "'ve", "'d", "n't"}
_SEMANTIC_CONTRACTION_PATTERN = re.compile(r".+(?:'m|'re|'s|'ll|'ve|'d|n't)$", re.IGNORECASE)
_TRUSTED_SHORT_ENTITY_TYPES = {"PERSON", "PER", "CHARACTER", "LOCATION", "LOC", "GPE", "PLACE", "FAC"}
_POSITIVE_CUES = {
    "amazing", "beautiful", "excellent", "fun", "good", "great", "happy", "love",
    "nice", "pretty", "relax", "warmth", "wonderful",
}
_NEGATIVE_CUES = {
    "angry", "awkward", "boring", "crazy", "dull", "dullest", "filth", "gross", "hate",
    "insane", "mad", "problem", "sad", "sorry", "stink", "stunk", "tired", "ugly",
    "upset", "worry", "worst",
}
_FEAR_CUES = {"afraid", "awkward", "nervous", "presumptuous", "scared", "worry"}
_SURPRISE_CUES = {"can't believe", "did you notice", "hey", "oh!", "surprise", "wait a second", "wow"}
_DIALOGUE_HINT_PATTERNS = {
    "complaint": {
        "affected by",
        "can you relax",
        "no one has any interest",
        "wait a second",
        "where were you",
        "why even",
        "don't be silly",
        "not going to have this conversation",
    },
    "confrontation": {
        "can you relax",
        "leave me",
        "let me talk to you",
        "wait a second",
        "where were you",
        "why even",
    },
    "greeting": {
        "good to see you",
        "hello?",
        "it's for you",
        "you're back",
    },
    "awkward": {
        "can't believe you're here",
        "did you notice that",
        "interesting greeting",
        "surprise blindfold greeting",
    },
    "reunion": {
        "can't believe you're here",
        "good to see you",
        "you're back",
    },
}
_ARTIFACT_HINT_PATTERNS = {
    "phone_call": {
        "call you tomorrow",
        "hello?",
        "hold on",
        "it's for you",
    },
}
_ARTIFACT_GREETINGS = {"hello", "hey", "hi", "oh", "yeah", "yes"}
_ARTIFACT_ENTITY_CONTEXT_REJECTIONS = {
    "signal": {"mr. signal", "the signal"},
}
_MIN_SENTIMENT_CONFIDENCE = 0.8
_MIN_LEXICAL_CONTRADICTION_COUNT = 3
_MIN_LEXICAL_CONTRADICTION_LEAD = 2
_MIN_EMOTION_SCORE = 0.145
_MIN_EMOTION_MARGIN = 0.01


def _load_st() -> Any:
    global _ST
    if _ST is not None:
        return _ST
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("text_embed")
    device = gpu_config["device"]
    
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        from steps.common.model_provisioner import ensure_model_cached
        
        try:
            from steps.common.config_loader import load_configs
            offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
        except Exception:
            offline_mode = False
            
        provision_result = ensure_model_cached("sentence_transformer", offline=offline_mode)
        if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
            raise OSError(f"Failed to provision SentenceTransformer model: {provision_result.error or 'reason unknown'}")
            
        model_path = provision_result.local_path
        _ST = SentenceTransformer(model_path, device=device)
        
        mem_fraction = gpu_config.get("memory_fraction")
        if isinstance(mem_fraction, (int, float)):
            logger.info(f"[OK] SentenceTransformer loaded on {device} from {model_path} (GPU config: {mem_fraction:.1%} memory)")
        else:
            logger.info(f"[OK] SentenceTransformer loaded on {device} from {model_path}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load SentenceTransformer: {str(e)}")
        logger.info("[WARN]  Falling back to CPU mode")
        _ST = None
        GPUManager.clear_cache()
    return _ST


def _open_faiss(path: str):
    global _FAISS
    try:
        import faiss  # type: ignore
    except Exception as e:
        logger.warning(
            "text_embed operation failed operation=%s index_path=%s exc_type=%s exc=%s",
            "open_faiss.import",
            path,
            type(e).__name__,
            e,
        )
        return None, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    index = None
    if os.path.isfile(path):
        try:
            index = faiss.read_index(path)
        except Exception as e:
            logger.warning(
                "text_embed operation failed operation=%s index_path=%s exc_type=%s exc=%s",
                "open_faiss.read_index",
                path,
                type(e).__name__,
                e,
            )
            index = None
    if index is None:
        # HNSW index for cosine similarity
        dim = 384  # all-MiniLM-L6-v2
        index = create_hnsw_id_index(faiss, dim)
        faiss.write_index(index, path)
    _FAISS = faiss
    return index, faiss


def _content_fingerprint(item: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    # Prefer explicit frame_text/text_override to generate a unique text hash
    txt_override = item.get("frame_text") or item.get("text_override")
    if isinstance(txt_override, str) and txt_override.strip():
        h.update(txt_override.encode("utf-8", errors="ignore"))
        return h.hexdigest()
    src = item.get("source_path")
    if isinstance(src, str) and os.path.isfile(src):
        try:
            with open(src, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
        except Exception as e:
            logger.warning(
                "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "content_fingerprint.read_source",
                src,
                type(e).__name__,
                e,
            )
            h.update((src or "").encode("utf-8", errors="ignore"))
    else:
        h.update(repr(item).encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _coerce_scene_identity(item: Dict[str, Any]) -> Optional[str]:
    scene_id = item.get("scene_id")
    if scene_id is not None:
        scene_text = str(scene_id).strip()
        if scene_text:
            return scene_text

    scene_index = item.get("scene_index")
    if scene_index is None:
        return None

    try:
        return f"scene_{int(scene_index):04d}"
    except (TypeError, ValueError):
        scene_text = str(scene_index).strip()
        return scene_text or None


def _text_embedding_identity(item: Dict[str, Any], content_hash: Optional[str] = None) -> str:
    """Use scene scope for scene text so identical captions do not overwrite."""
    base_hash = content_hash or _content_fingerprint(item)
    scene_identity = _coerce_scene_identity(item)
    video_identity = item.get("video_id") or item.get("video_hash")
    if scene_identity is None and video_identity is None:
        return base_hash

    modality = str(item.get("modality") or "text").strip() or "text"
    identity_parts = {
        "component": "text_embed",
        "content_hash": base_hash,
        "modality": modality,
        "scene": scene_identity,
        "video": str(video_identity) if video_identity is not None else None,
    }
    return hashlib.sha256(
        json.dumps(identity_parts, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _gather_text(item: Dict[str, Any]) -> Optional[str]:
    # Pull text from known fields in priority order
    for k in ("frame_text", "transcript", "text", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    print(f'[WARN] _gather_text returning None')
    return None


def _coerce_str_list(value: Any) -> List[str]:
    out: List[str] = []
    if isinstance(value, str) and value.strip():
        out.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
    deduped: List[str] = []
    seen = set()
    for item in out:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _coerce_semantic_labels(value: Any) -> List[str]:
    out: List[str] = []
    if isinstance(value, str):
        return _coerce_str_list(value)
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        raw = item.get("name") or item.get("text") or item.get("entity") or item.get("value")
        if isinstance(raw, str) and raw.strip():
            out.append(raw.strip())
    deduped: List[str] = []
    seen = set()
    for item in out:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_semantic_label(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    text = text.strip(" ,;:.!?")
    if not text or "##" in text:
        return None
    return text


def _semantic_tokens(value: str) -> List[str]:
    return [token.strip("'") for token in re.findall(r"[A-Za-z0-9']+", value)]


def _is_meaningful_semantic_label(value: str, *, kind: str, trusted: bool = False) -> bool:
    text = _normalize_semantic_label(value)
    if not text:
        return False
    lowered = text.casefold()
    if lowered in _SEMANTIC_STOPWORDS or lowered in _SEMANTIC_CONTRACTION_PARTS:
        return False
    if re.fullmatch(r"[^\w]+", text):
        return False

    tokens = [token for token in _semantic_tokens(text) if token]
    if not tokens:
        return False

    substantive = [
        token for token in tokens
        if len(re.sub(r"[^A-Za-z0-9]+", "", token)) >= 3
        and token.casefold() not in _SEMANTIC_STOPWORDS
        and token.casefold() not in _SEMANTIC_CONTRACTION_PARTS
    ]
    if not substantive:
        return False

    if len(tokens) == 1:
        token = tokens[0]
        compact = re.sub(r"[^A-Za-z0-9]+", "", token)
        if len(compact) < 3:
            return False
        if "'" in token and _SEMANTIC_CONTRACTION_PATTERN.fullmatch(token):
            return False
        if token.isupper() and len(compact) >= 3:
            return True
        min_len = 3 if trusted else 4
        return bool(token[:1].isupper() and len(compact) >= min_len)

    if kind == "location":
        return True
    return len(substantive) >= 2


def _sanitize_semantic_list(value: Any, *, kind: str, limit: int, trusted: bool = False) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in _coerce_semantic_labels(value):
        text = _normalize_semantic_label(raw)
        if not text or not _is_meaningful_semantic_label(text, kind=kind, trusted=trusted):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _gather_entities(item: Dict[str, Any], *, limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    ner_entities = item.get("ner_entities")
    if isinstance(ner_entities, list):
        for entity in ner_entities:
            if not isinstance(entity, dict):
                continue
            raw = entity.get("name") or entity.get("text") or entity.get("entity") or entity.get("value")
            if not isinstance(raw, str) or not raw.strip():
                continue
            ent_type = entity.get("type") or entity.get("label") or entity.get("entity_type")
            ent_type_text = ent_type.strip().upper() if isinstance(ent_type, str) and ent_type.strip() else ""
            label = _normalize_semantic_label(raw)
            if not label or not _is_meaningful_semantic_label(
                label,
                kind="entity",
                trusted=ent_type_text in _TRUSTED_SHORT_ENTITY_TYPES,
            ):
                continue
            if _contextually_reject_entity(label, item):
                continue
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
            if len(out) >= limit:
                return out
    for label in _sanitize_semantic_list(item.get("entities"), kind="entity", limit=limit, trusted=False):
        if _contextually_reject_entity(label, item):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= limit:
            return out
    return out


def _gather_locations(item: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("location", "place"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
    for key in ("locations", "places"):
        out.extend(_coerce_str_list(item.get(key)))
    deduped: List[str] = []
    seen = set()
    for item_text in out:
        key = item_text.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item_text)
    return deduped


def _lexical_valence_counts(item: Dict[str, Any]) -> tuple[int, int]:
    text = _gather_text(item)
    if not isinstance(text, str) or not text.strip():
        return 0, 0
    lowered = text.lower()
    tokens = [token.strip("'") for token in re.findall(r"[A-Za-z0-9']+", lowered)]
    pos = sum(1 for token in tokens if token in _POSITIVE_CUES)
    neg = sum(1 for token in tokens if token in _NEGATIVE_CUES)
    return pos, neg


def _contains_phrase(text: str, phrases: set[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _count_token_occurrences(text: str, tokens: set[str]) -> int:
    words = [token.strip("'") for token in re.findall(r"[A-Za-z0-9']+", text.lower())]
    return sum(1 for token in words if token in tokens)


def _gather_artifact_hints(item: Dict[str, Any]) -> List[str]:
    text = _gather_text(item)
    if not isinstance(text, str) or not text.strip():
        return []

    lowered = text.lower()
    hints: List[str] = []
    for hint, phrases in _ARTIFACT_HINT_PATTERNS.items():
        if any(phrase in lowered for phrase in phrases):
            hints.append(hint)

    greeting_count = _count_token_occurrences(text, _ARTIFACT_GREETINGS)
    if greeting_count >= 6:
        hints.append("repeated_greeting")
    if greeting_count >= 8:
        hints.append("ambient_reaction")
    return hints


def _contextually_reject_entity(label: str, item: Dict[str, Any]) -> bool:
    phrases = _ARTIFACT_ENTITY_CONTEXT_REJECTIONS.get(label.casefold())
    if not phrases:
        return False
    text = _gather_text(item)
    if not isinstance(text, str) or not text.strip():
        return False
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _raw_emotion_label(item: Dict[str, Any]) -> Optional[str]:
    value = item.get("emotion")
    if isinstance(value, str):
        text = value.strip().lower()
        return text or None
    emotions = item.get("emotions")
    if not isinstance(emotions, dict):
        emotions = item.get("emotion_scores")
    if isinstance(emotions, dict):
        best_name = None
        best_score = float("-inf")
        for name, score in emotions.items():
            if not isinstance(name, str) or not name.strip():
                continue
            score_value = float(score) if isinstance(score, (int, float)) else 0.0
            if score_value > best_score:
                best_name = name.strip().lower()
                best_score = score_value
        return best_name or None
    return None


def _emotion_score_metrics(item: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    emotions = item.get("emotions")
    if not isinstance(emotions, dict):
        emotions = item.get("emotion_scores")
    if not isinstance(emotions, dict):
        return None, None

    ordered: List[float] = []
    for name, score in emotions.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(score, (int, float)):
            continue
        ordered.append(float(score))

    if not ordered:
        return None, None

    ordered.sort(reverse=True)
    top_score = ordered[0]
    runner_up = ordered[1] if len(ordered) > 1 else 0.0
    return top_score, top_score - runner_up


def _gather_emotion(item: Dict[str, Any]) -> Optional[str]:
    emotion = _raw_emotion_label(item)
    if not emotion:
        return None

    top_score, margin = _emotion_score_metrics(item)
    if top_score is not None and margin is not None:
        if top_score < _MIN_EMOTION_SCORE or margin < _MIN_EMOTION_MARGIN:
            return None

    text = _gather_text(item)
    pos, neg = _lexical_valence_counts(item)
    sentiment = _gather_sentiment_label(item)

    if emotion in {"calm", "neutral"}:
        return None
    if emotion == "happy":
        if sentiment == "positive" or pos > neg:
            return emotion
        return None
    if emotion in {"angry", "disgust", "sad"}:
        if sentiment == "negative" or neg > pos:
            return emotion
        return None
    if emotion == "fear":
        if isinstance(text, str) and _contains_phrase(text, _FEAR_CUES):
            return emotion
        if sentiment == "negative" and neg >= 2:
            return emotion
        return None
    if emotion == "surprise":
        if isinstance(text, str) and _contains_phrase(text, _SURPRISE_CUES):
            return emotion
        return None
    return None


def _gather_sentiment_label(item: Dict[str, Any]) -> Optional[str]:
    value = item.get("sentiment")
    score: Optional[float] = None
    label_text: Optional[str] = None
    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, str) and label.strip():
            label_text = label.strip().lower()
        raw_score = value.get("score")
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)
    elif isinstance(value, str) and value.strip():
        label_text = value.strip().lower()

    if label_text not in {"positive", "negative"}:
        return None
    if score is not None and score < _MIN_SENTIMENT_CONFIDENCE:
        return None

    pos, neg = _lexical_valence_counts(item)
    if (
        label_text == "positive"
        and neg >= _MIN_LEXICAL_CONTRADICTION_COUNT
        and neg >= pos + _MIN_LEXICAL_CONTRADICTION_LEAD
    ):
        return None
    if (
        label_text == "negative"
        and pos >= _MIN_LEXICAL_CONTRADICTION_COUNT
        and pos >= neg + _MIN_LEXICAL_CONTRADICTION_LEAD
    ):
        return None
    return label_text


def _gather_dialogue_hints(item: Dict[str, Any]) -> List[str]:
    text = _gather_text(item)
    if not isinstance(text, str) or not text.strip():
        return []

    lowered = text.lower()
    artifact_hints = set(_gather_artifact_hints(item))
    sentiment = _gather_sentiment_label(item)
    hints: List[str] = []
    for hint, phrases in _DIALOGUE_HINT_PATTERNS.items():
        if any(phrase in lowered for phrase in phrases):
            if hint == "complaint" and "phone_call" in artifact_hints and sentiment != "negative":
                continue
            hints.append(hint)
    return hints


def _build_semantic_text(base_text: str, item: Dict[str, Any]) -> str:
    sections = [base_text.strip()]
    entities = _gather_entities(item, limit=8)
    tags = _sanitize_semantic_list(item.get("tags"), kind="tag", limit=8)
    locations = _sanitize_semantic_list(_gather_locations(item), kind="location", limit=4)
    artifact_hints = _gather_artifact_hints(item)
    dialogue_hints = _gather_dialogue_hints(item)
    emotion = _gather_emotion(item)
    sentiment = _gather_sentiment_label(item)
    if entities:
        sections.append("Entities: " + ", ".join(entities))
    if locations:
        sections.append("Locations: " + ", ".join(locations))
    if tags:
        sections.append("Tags: " + ", ".join(tags))
    if dialogue_hints:
        sections.append("Dialogue: " + ", ".join(dialogue_hints))
    if artifact_hints:
        sections.append("Artifacts: " + ", ".join(artifact_hints))
    if emotion:
        sections.append(f"Emotion: {emotion}")
    if sentiment:
        sections.append(f"Sentiment: {sentiment}")
    speaker_count = item.get("speaker_count")
    if isinstance(speaker_count, int) and speaker_count > 0:
        sections.append(f"Speaker count: {speaker_count}")
    return "\n".join(part for part in sections if part)


def _preview_focus_phrases(item: Dict[str, Any]) -> List[str]:
    lowered_text = (_gather_text(item) or "").lower()
    if not lowered_text:
        return []

    phrases: List[str] = []
    dialogue_hints = _gather_dialogue_hints(item)
    for hint in dialogue_hints:
        hint_phrases = _DIALOGUE_HINT_PATTERNS.get(hint)
        if not isinstance(hint_phrases, set):
            continue
        for phrase in hint_phrases:
            if phrase in lowered_text:
                phrases.append(phrase)

    artifact_hints = _gather_artifact_hints(item)
    for hint in artifact_hints:
        hint_phrases = _ARTIFACT_HINT_PATTERNS.get(hint)
        if not isinstance(hint_phrases, set):
            continue
        for phrase in hint_phrases:
            if phrase in lowered_text:
                phrases.append(phrase)

    deduped: List[str] = []
    seen = set()
    for phrase in sorted(phrases, key=len, reverse=True):
        if phrase in seen:
            continue
        seen.add(phrase)
        deduped.append(phrase)
    return deduped


def _build_text_preview(item: Dict[str, Any], *, max_chars: int = 420) -> str:
    text = _gather_text(item)
    if not isinstance(text, str):
        return ""

    normalized = " ".join(text.strip().split())
    if len(normalized) <= max_chars:
        return normalized

    lowered = normalized.lower()
    focus_index: Optional[int] = None
    for phrase in _preview_focus_phrases(item):
        idx = lowered.find(phrase)
        if idx >= 0:
            focus_index = idx
            break

    if focus_index is None:
        focus_labels = _gather_entities(item, limit=4) + _sanitize_semantic_list(_gather_locations(item), kind="location", limit=2)
        for label in focus_labels:
            idx = lowered.find(label.lower())
            if idx >= 0:
                focus_index = idx
                break

    if focus_index is None:
        return normalized[:max_chars].rstrip()

    start = max(0, focus_index - (max_chars // 3))
    boundary = max(
        normalized.rfind(". ", 0, start),
        normalized.rfind("? ", 0, start),
        normalized.rfind("! ", 0, start),
        normalized.rfind("; ", 0, start),
    )
    if boundary >= 0:
        start = boundary + 2

    end = min(len(normalized), start + max_chars)
    if end < len(normalized):
        next_boundary_candidates = [
            normalized.find(". ", end),
            normalized.find("? ", end),
            normalized.find("! ", end),
            normalized.find("; ", end),
        ]
        next_boundary_candidates = [idx for idx in next_boundary_candidates if idx >= 0]
        if next_boundary_candidates:
            candidate_end = min(next_boundary_candidates) + 1
            if candidate_end - start <= max_chars + 80:
                end = candidate_end

    preview = normalized[start:end].strip()
    if start > 0:
        preview = "... " + preview
    if end < len(normalized):
        preview = preview.rstrip(" ,;:.!?") + " ..."
    return preview


def text_embed(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"embedding_meta": {"status": "no_text"}}
    semantic_text = _build_semantic_text(text, item)

    model = _load_st()
    if model is None:
        return {"embedding_meta": {"status": "unavailable", "engine": "sentence-transformers"}}

    try:
        vec = model.encode([semantic_text], normalize_embeddings=True)
        vector_list = vec.astype("float32")[0].tolist()
        entities = _gather_entities(item, limit=8)
        tags = _sanitize_semantic_list(item.get("tags"), kind="tag", limit=8)
        locations = _sanitize_semantic_list(_gather_locations(item), kind="location", limit=4)
        artifact_hints = _gather_artifact_hints(item)
        dialogue_hints = _gather_dialogue_hints(item)
        emotion = _gather_emotion(item)
        sentiment = _gather_sentiment_label(item)
        payload_meta = {
            "source_path": item.get("source_path"),
            "modality": item.get("modality", "text"),
            "scene_id": item.get("scene_id") or item.get("scene_index"),
            "scene_index": item.get("scene_index"),
            "video_id": item.get("video_id") or item.get("video_hash"),
            "video_hash": item.get("video_hash") or item.get("video_id"),
            "entities": entities,
            "tags": tags,
            "locations": locations,
            "artifact_hints": artifact_hints,
            "dialogue_hints": dialogue_hints,
            "emotion": emotion,
            "sentiment": sentiment,
            "speaker_count": item.get("speaker_count"),
            "text_preview": _build_text_preview(item),
        }
        scene_window = item.get("scene")
        if isinstance(scene_window, dict):
            payload_meta["start"] = scene_window.get("start")
            payload_meta["end"] = scene_window.get("end")

        content_hash = _content_fingerprint(item)
        embedding_id = _text_embedding_identity(item, content_hash)
        scene_identity = _coerce_scene_identity(item)
        video_identity = item.get("video_id") or item.get("video_hash")
        if scene_identity is not None:
            identity_scope = "scene"
        elif video_identity is not None:
            identity_scope = "video"
        else:
            identity_scope = "content"
        payload_meta["content_fingerprint"] = content_hash
        payload_meta["embedding_identity_scope"] = identity_scope

        # Add epoch_id for strict validation (derived from cfg paths.db_dir)
        _db_dir = (cfg.get("paths", {}) or {}).get("db_dir")
        if _db_dir:
            import os
            payload_meta["epoch_id"] = os.path.basename(_db_dir)

        # Add scene_hash (must equal UCF vector_key, which is the raw embedding_id)
        payload_meta["scene_hash"] = embedding_id

        # Route writes via MemoryRouter (faiss + qdrant as configured)
        stores = build_text_stores(cfg)
        router = MemoryRouter(stores)
        payload = {
            "id": embedding_id,
            "vector": vector_list,
            "payload": payload_meta,
        }
        payload_meta["ucf_promotion_status"] = "staged"
        router_results = router.insert([payload])
        _qdrant_committed = bool((router_results or {}).get("qdrant"))
        _faiss_id = to_faiss_id(embedding_id)
        _qdrant_collection = None
        try:
            _q_store = stores.get("qdrant")
            _qdrant_collection = getattr(getattr(getattr(_q_store, "client", None), "cfg", None), "collection", None)
        except Exception:
            pass

        # Persist mapping for recall/linking (FAISS id if available is not tracked here)
        isolated_epoch = bool(cfg.get("ingestion_isolation", False))
        embedding_ok = None if isolated_epoch else False
        embedding_reason = "not_applicable_isolated_epoch" if isolated_epoch else None
        if not isolated_epoch:
            try:
                scene_id = _coerce_scene_identity(item)
                upsert_embedding(cfg, payload["id"], to_faiss_id(payload["id"]), item.get("source_path", ""), item.get("modality", ""), scene_id=scene_id, vector=payload["vector"])
                embedding_ok = True
            except Exception as e:
                embedding_reason = f"exception:{type(e).__name__}"
                logger.warning(
                    "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "sqlite_embeddings.upsert",
                    item.get("source_path"),
                    type(e).__name__,
                    e,
                )

        try:
            from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso

            scene_id = _coerce_scene_identity(item)

            qdrant_ref = None
            try:
                q_store = stores.get("qdrant")
                q_client = getattr(q_store, "client", None)
                qdrant_ref = getattr(getattr(q_client, "cfg", None), "collection", None)
            except Exception as e:
                logger.warning(
                    "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "resolve_qdrant_ref",
                    item.get("source_path"),
                    type(e).__name__,
                    e,
                )
                qdrant_ref = None

            faiss_ref = None
            try:
                f_store = stores.get("faiss")
                faiss_ref = getattr(f_store, "index_path", None)
            except Exception as e:
                logger.warning(
                    "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "resolve_faiss_ref",
                    item.get("source_path"),
                    type(e).__name__,
                    e,
                )
                faiss_ref = None

            targets = {}
            for target, ok in (router_results or {}).items():
                present = target in (stores or {})
                ref = qdrant_ref if target == "qdrant" else faiss_ref if target == "faiss" else None
                reason = None
                if not present:
                    reason = "store_missing"
                elif not ok:
                    reason = "insert_failed_or_filtered"
                targets[str(target)] = {"attempted": bool(present), "committed": bool(ok), "ref": ref, "reason": reason, "count": 1}
            if not isolated_epoch:
                targets["sqlite_embeddings"] = {
                    "attempted": True,
                    "committed": bool(embedding_ok),
                    "ref": (cfg.get("paths", {}) or {}).get("db_path"),
                    "reason": embedding_reason,
                }
            emit_memory_commit_event(
                cfg,
                MemoryCommitEvent(
                    ts_utc=utc_now_iso(),
                    scene_id=scene_id,
                    video_id=str(item.get("video_id")) if item.get("video_id") is not None else None,
                    modality=str((payload.get("payload") or {}).get("modality") or "text") or "text",
                    model="all-MiniLM-L6-v2",
                    embedding_id=str(payload.get("id")) if payload.get("id") is not None else None,
                    component="text_embed",
                    targets=targets,
                    details={
                        "text_len": len(text) if isinstance(text, str) else None,
                        "semantic_text_len": len(semantic_text) if isinstance(semantic_text, str) else None,
                        "source_path": item.get("source_path"),
                        "content_fingerprint": content_hash,
                        "embedding_identity_scope": identity_scope,
                    },
                ),
            )
        except Exception as e:
            logger.warning(
                "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "emit_memory_commit_event",
                item.get("source_path"),
                type(e).__name__,
                e,
            )

        return {"embedding_meta": {
            "status": "ok",
            "engine": "all-MiniLM-L6-v2",
            "embedding_id": embedding_id,
            "qdrant_committed": _qdrant_committed,
            "faiss_id": _faiss_id,
            "vector_collection": _qdrant_collection,
        }}
    except Exception as e:
        logger.warning(
            "text_embed operation failed operation=%s source_path=%s exc_type=%s exc=%s",
            "embed_text",
            item.get("source_path"),
            type(e).__name__,
            e,
        )
        return {"embedding_meta": {"status": "error", "error": str(e)}}
