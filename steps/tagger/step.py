from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Tuple

_NER_PIPELINES: Dict[str, Any] = {}
logger = logging.getLogger(__name__)

try:
    from steps.common.tag_utils import (
        dedupe_tokens,
        is_runaway_decoder_phrase,
        is_valid_entity_token,
        is_valid_tag_token,
        normalize_entity_token,
        normalize_tag_token,
        reliable_transcript_for_entities,
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
    def is_runaway_decoder_phrase(phrase_text, *, vocab_words=None, untimed_native=False):
        return False
    def reliable_transcript_for_entities(item):
        val = item.get("transcript") if isinstance(item, dict) else ""
        return val.strip() if isinstance(val, str) else ''


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
_TRUSTED_SHORT_ENTITY_TYPES = {"PERSON", "PER", "CHARACTER", "LOCATION", "LOC", "GPE", "PLACE", "FAC"}
_SEMANTIC_CONTRACTION_PATTERN = re.compile(r".+(?:'m|'re|'s|'ll|'ve|'d|n't)$", re.IGNORECASE)
_VERBAL_CONTRACTION_TOKEN_RE = re.compile(
    r"^(?:there's|here's|where's|it's|that's|what's|who's|how's|he's|she's|let's|"
    r"[a-z]+(?:'m|'re|'ve|'ll|'d|n't))$",
    re.IGNORECASE,
)
_FALLBACK_BOUNDARY_TOKENS = {
    "the", "a", "an", "this", "that", "these", "those",
    "my", "your", "his", "her", "its", "our", "their",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "us", "them",
    "is", "are", "was", "were", "am", "be", "been", "being",
    "has", "have", "had", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must",
    "and", "or", "but", "if", "when", "while", "because", "since", "until", "unless",
    "with", "without", "from", "into", "onto", "upon", "about", "after", "before",
    "there", "here", "where", "what", "who", "whom", "whose", "why", "how",
    "hi", "hey", "hello", "bye", "goodbye", "yes", "yeah", "yep", "no", "nope", "okay", "ok", "well", "oh",
    "wow", "whoa", "yay", "give", "kiss", "sit", "look", "come", "say", "tell",
    "open", "put", "get", "take", "see", "watch", "thank", "thanks", "please",
}
_LOW_VALUE_ENTITY_TERMS = {
    "also", "can", "go", "he", "hold", "i'm", "im", "it", "listen", "meat", "oh",
    "really", "shake", "so", "sure", "to", "uh", "want",
}
_SINGLE_TOKEN_FALSE_POSITIVE_ENTITIES = {
    "kiss", "sit", "happy", "gaming", "yay", "whoa", "wow", "look", "come",
    "give", "nice", "good", "cute", "sweet", "ready", "wait", "stop",
}
_SINGLE_TOKEN_FALSE_POSITIVE_PERSONS = {
    "lion", "tiger", "bear", "puppy", "kitty", "bunny",
    "aunt", "uncle", "mayor", "doctor", "nurse", "teacher", "coach",
    "baby", "child", "kids", "boys", "girls", "man", "woman", "lady",
}
_ALWAYS_PERSON_TAG_EXCLUSIONS = {
    "santa", "santa claus", "saint nick", "st nick", "st. nick",
}
_ROSTER_DISPLAY_CACHE: Dict[str, Tuple[int, Dict[str, str]]] = {}


def _load_roster_display_map(raw_path: Any) -> Dict[str, str]:
    from pathlib import Path

    if not isinstance(raw_path, (str, Path)) or not str(raw_path).strip():
        return {}
    try:
        candidate = Path(str(raw_path).strip())
        if candidate.suffix.lower() not in {".yaml", ".yml"}:
            candidate = candidate / "family_roster.yaml"
        if not candidate.is_file():
            return {}
        resolved = str(candidate.resolve())
        mtime_ns = candidate.stat().st_mtime_ns
        cached = _ROSTER_DISPLAY_CACHE.get(resolved)
        if cached is not None and cached[0] == mtime_ns:
            return dict(cached[1])
        import yaml

        payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        mapping: Dict[str, str] = {}
        identities = payload.get("identities") if isinstance(payload, dict) else None
        if isinstance(identities, list):
            for entry in identities:
                if not isinstance(entry, dict):
                    continue
                display = str(entry.get("display_name") or "").strip()
                if display:
                    mapping.setdefault(display.casefold(), display)
                aliases = entry.get("aliases")
                if isinstance(aliases, (list, tuple, set)):
                    for alias in aliases:
                        alias_str = str(alias or "").strip()
                        if alias_str:
                            mapping.setdefault(alias_str.casefold(), alias_str)
        _ROSTER_DISPLAY_CACHE[resolved] = (mtime_ns, dict(mapping))
        return mapping
    except Exception:
        return {}


def _load_configured_person_map(cfg: Dict[str, Any] | None) -> Dict[str, str]:
    if not isinstance(cfg, dict):
        return {}
    mapping: Dict[str, str] = {}
    scopes = [cfg]
    nested = cfg.get("config")
    if isinstance(nested, dict):
        scopes.append(nested)
    for scope in scopes:
        candidate_lists: List[Any] = [scope.get("family_names")]
        user_cfg = scope.get("user")
        if isinstance(user_cfg, dict):
            candidate_lists.append(user_cfg.get("family_names"))
        for configured in candidate_lists:
            if isinstance(configured, (list, tuple, set)):
                for raw in configured:
                    val = str(raw or "").strip()
                    if val:
                        disp = val if any(c.isupper() for c in val) else val.title()
                        mapping.setdefault(val.casefold(), disp)
        id_search = scope.get("identity_search")
        if isinstance(id_search, dict):
            for k, v in _load_roster_display_map(id_search.get("roster_path")).items():
                mapping.setdefault(k, v)
        id_matching = scope.get("identity_matching")
        if isinstance(id_matching, dict):
            ref_sources = id_matching.get("reference_sources")
            if isinstance(ref_sources, list):
                for source in ref_sources:
                    if isinstance(source, dict):
                        for k, v in _load_roster_display_map(source.get("identity_path")).items():
                            mapping.setdefault(k, v)
    return mapping


def _split_fused_configured_persons(
    label: str,
    configured_persons: Dict[str, str] | None,
) -> List[str]:
    normalized = normalize_entity_token(_collapse_consecutive_duplicate_tokens(label))
    if not normalized:
        return []
    if not configured_persons:
        return [normalized]
    exact_key = normalized.casefold()
    if exact_key in configured_persons:
        return [configured_persons[exact_key]]
    tokens = _entity_tokens(normalized)
    if len(tokens) < 2 or len(tokens) > 8:
        return [normalized]
    n = len(tokens)
    memo: Dict[int, List[str] | None] = {n: []}
    for i in range(n - 1, -1, -1):
        best: List[str] | None = None
        for j in range(n, i, -1):
            span_key = " ".join(tokens[i:j]).casefold()
            if span_key in configured_persons and memo.get(j) is not None:
                best = [configured_persons[span_key], *(memo[j] or [])]
                break
        memo[i] = best
    parts = memo.get(0)
    if parts and len(parts) >= 2:
        return parts
    return [normalized]
_ENTITY_CONTEXT_REJECTIONS = {
    "god": {"oh my god", "my god", "god bless"},
    "justin case": {"a justin case"},
    "signal": {"mr. signal", "the signal", "this is the signal"},
    "batman": {"like batman"},
    "case": {"case closed", "crack this case"},
}


def _get_ner_pipeline(model_id: str, *, offline: bool | None = None) -> Any:
    pipeline_obj = _NER_PIPELINES.get(model_id)
    if pipeline_obj is not None:
        return pipeline_obj
    from steps.common.model_provisioner import ensure_model_cached
    if offline is None:
        from steps.common.config_loader import load_configs
        offline = load_configs({}).get("verification", {}).get("offline_mode", False)
        
    provision_result = ensure_model_cached(model_id, offline=offline)
    if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
        raise OSError(f"Failed to provision NER model: {provision_result.error or 'reason unknown'}")
        
    local_path = provision_result.local_path
    
    from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline, logging as hf_logging  # type: ignore
    hf_logging.set_verbosity_error()
    tokenizer = AutoTokenizer.from_pretrained(local_path, local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(local_path, local_files_only=True)
    pipe = pipeline(
        "token-classification",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",
    )
    _NER_PIPELINES[model_id] = pipe
    return pipe

def _speaker_transcript_text(item: Dict[str, Any]) -> str:
    speaker_transcript = item.get("speaker_transcript")
    if not isinstance(speaker_transcript, list):
        return ""
    vocab_words: set[str] = set()
    tmeta = item.get("transcript_meta")
    if isinstance(tmeta, dict):
        tctx = tmeta.get("transcription_context")
        if isinstance(tctx, dict):
            for w in tctx.get("words") or []:
                for sub in re.findall(r"[A-Za-z0-9']+", str(w or "")):
                    if sub.strip("'"):
                        vocab_words.add(sub.strip("'").casefold())
    parts: List[str] = []
    for segment in speaker_transcript:
        if not isinstance(segment, dict):
            continue
        text = segment.get("text")
        if isinstance(text, str) and text.strip():
            stripped = text.strip()
            if is_runaway_decoder_phrase(stripped, vocab_words=vocab_words or None):
                continue
            parts.append(stripped)
    return "\n".join(parts)


def _gather_text(item: Dict[str, Any]) -> str:
    texts: List[str] = []
    seen: set[str] = set()
    tmeta = item.get("transcript_meta")
    has_governed_phrases = (
        isinstance(tmeta, dict)
        and isinstance(tmeta.get("phrase_observations"), list)
        and bool(tmeta.get("phrase_observations"))
    )
    for k in ("document_text", "transcript", "ocr_text", "caption"):
        if k == "transcript":
            v = reliable_transcript_for_entities(item) if isinstance(tmeta, dict) else item.get(k)
        else:
            v = item.get(k)
        if isinstance(v, str) and v.strip():
            text = v.strip()
            if text not in seen:
                seen.add(text)
                texts.append(text)
    speaker_text = "" if has_governed_phrases else _speaker_transcript_text(item)
    if speaker_text:
        normalized_speaker = re.sub(r"\s+", " ", speaker_text).strip().casefold()
        covered = False
        for existing in texts:
            normalized_existing = re.sub(r"\s+", " ", existing).strip().casefold()
            if normalized_speaker and (
                normalized_speaker in normalized_existing or normalized_existing in normalized_speaker
            ):
                covered = True
                break
        if not covered and speaker_text not in seen:
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
    model_id = (
        ((cfg.get("config", {}) or {}).get("tagger", {}) or {}).get("ner_model")
        or "dslim/bert-base-NER"
    )
    nlp = _get_ner_pipeline(model_id, offline=(cfg.get("verification") or {}).get("offline_mode"))
    ents = nlp(text)
    labels = []
    structured = []
    seen_structured = set()
    for e in ents:
        word = (e.get("word") or "").strip()
        raw_group = (e.get("entity_group") or e.get("entity") or "").strip().upper()
        entity_group = {"PER": "PERSON", "LOC": "LOCATION"}.get(raw_group, raw_group)
        normalized = normalize_entity_token(word)
        trusted = entity_group in _TRUSTED_SHORT_ENTITY_TYPES
        if (
            normalized
            and is_valid_entity_token(normalized)
            and _is_meaningful_entity_label(normalized, trusted=trusted, entity_type=entity_group)
            and not _contextually_reject_entity(normalized, text)
            and _appears_as_entity_span(normalized, text, trusted=trusted)
        ):
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


def _collapse_consecutive_duplicate_tokens(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parts = value.split()
    if len(parts) < 2:
        return value.strip()
    collapsed: List[str] = []
    prev_key = ""
    for part in parts:
        key = re.sub(r"^[^\w]+|[^\w]+$", "", part).casefold()
        if key and len(key) >= 2 and key == prev_key:
            continue
        collapsed.append(part)
        prev_key = key
    return " ".join(collapsed)


def _split_fallback_span(text: str, span_start: int, span_text: str) -> List[Tuple[int, str]]:
    word_re = re.compile(r"[A-Za-z0-9']+")
    sub_spans: List[Tuple[int, str]] = []
    cur_tokens: List[str] = []
    cur_start: int | None = None
    for wm in word_re.finditer(span_text):
        tok = wm.group(0)
        tok_clean = tok.strip("'")
        lower = tok_clean.casefold()
        is_boundary = (
            not tok_clean
            or lower in _FALLBACK_BOUNDARY_TOKENS
            or _VERBAL_CONTRACTION_TOKEN_RE.fullmatch(tok_clean) is not None
        )
        if is_boundary:
            if cur_tokens and cur_start is not None:
                sub_spans.append((cur_start, " ".join(cur_tokens)))
                cur_tokens = []
                cur_start = None
            continue
        if cur_start is None:
            cur_start = span_start + wm.start()
        cur_tokens.append(tok)
    if cur_tokens and cur_start is not None:
        sub_spans.append((cur_start, " ".join(cur_tokens)))
    return sub_spans


def _fallback_entities(text: str) -> List[str]:
    pattern = re.compile(r"\b(?:[A-Z][A-Za-z']{1,}(?:[ \t]+[A-Z][A-Za-z']{1,})*|[A-Z]{2,})\b")
    matches: List[str] = []
    for match in pattern.finditer(text):
        for sub_start, sub_raw in _split_fallback_span(text, match.start(), match.group(0)):
            deduped_raw = _collapse_consecutive_duplicate_tokens(sub_raw)
            normalized = normalize_entity_token(deduped_raw)
            token_count = len(_entity_tokens(deduped_raw))
            if token_count == 1 and _is_sentence_start_match(text, sub_start):
                continue
            if (
                normalized
                and is_valid_entity_token(normalized)
                and _is_meaningful_entity_label(normalized, trusted=False)
                and not _contextually_reject_entity(normalized, text)
            ):
                matches.append(normalized)
    return dedupe_tokens(matches)[:20]


def _entity_tokens(value: str) -> List[str]:
    return [token.strip("'") for token in re.findall(r"[A-Za-z0-9']+", value) if token.strip("'")]


def _count_entity_mentions(label: str, text: str) -> int:
    if not isinstance(label, str) or not label.strip():
        return 0
    if not isinstance(text, str) or not text.strip():
        return 0
    tokens = _entity_tokens(label)
    if not tokens:
        return 0
    escaped = r"[ \t]+".join(re.escape(token) for token in tokens)
    matches = re.findall(rf"\b{escaped}\b", text, flags=re.IGNORECASE)
    return len(matches)


def _count_independent_token_mentions(token: str, full_label: str, text: str) -> int:
    token_mentions = _count_entity_mentions(token, text)
    label_mentions = _count_entity_mentions(full_label, text)
    return max(0, token_mentions - label_mentions)


def _canonicalize_unstable_compound_person_label(
    label: str,
    text: str,
    *,
    trusted: bool,
    entity_type: str | None = None,
    configured_persons: Dict[str, str] | None = None,
) -> str | None:
    normalized = normalize_entity_token(_collapse_consecutive_duplicate_tokens(label))
    if not normalized:
        return None
    if _contextually_reject_entity(normalized, text):
        return None
    if configured_persons and normalized.casefold() in configured_persons:
        return configured_persons[normalized.casefold()]

    tokens = _entity_tokens(normalized)
    if len(tokens) < 2:
        return normalized

    ent_type = _coerce_entity_type(entity_type)
    if ent_type and ent_type not in _PERSON_ENTITY_TYPES:
        return normalized

    phrase_mentions = _count_entity_mentions(normalized, text)
    tail_support = 0
    for token in tokens[1:]:
        tail_support += _count_independent_token_mentions(token, normalized, text)
    if phrase_mentions > 1 or tail_support > 0:
        return normalized

    head = normalize_entity_token(tokens[0])
    if (
        head
        and _is_meaningful_entity_label(head, trusted=trusted, entity_type=ent_type)
        and not _contextually_reject_entity(head, text)
        and _appears_as_entity_span(head, text, trusted=trusted)
    ):
        return head
    return None


def _is_meaningful_entity_label(value: str, *, trusted: bool, entity_type: str | None = None) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip(" ,;:.!?")
    if not text or not is_valid_entity_token(text):
        return False
    if text.casefold() in _LOW_VALUE_ENTITY_TERMS:
        return False
    if re.fullmatch(r"(?:SPEAKER|FACE)_\d+", text, re.IGNORECASE):
        return False

    tokens = _entity_tokens(text)
    if not tokens:
        return False

    substantive = [
        token for token in tokens
        if len(re.sub(r"[^A-Za-z0-9]+", "", token)) >= 3
        and is_valid_entity_token(token)
    ]
    if not substantive:
        return False

    if len(tokens) == 1:
        token = tokens[0]
        lower_tok = token.casefold()
        if lower_tok in _SINGLE_TOKEN_FALSE_POSITIVE_ENTITIES:
            return False
        ent_type = _coerce_entity_type(entity_type)
        if ent_type in _PERSON_ENTITY_TYPES and lower_tok in _SINGLE_TOKEN_FALSE_POSITIVE_PERSONS:
            return False
        compact = re.sub(r"[^A-Za-z0-9]+", "", token)
        if len(compact) < 3:
            return False
        if "'" in token and _SEMANTIC_CONTRACTION_PATTERN.fullmatch(token):
            return False
        if token.isupper() and len(compact) >= 3:
            return True
        min_len = 3 if trusted else 4
        return bool(token[:1].isupper() and len(compact) >= min_len)

    if not trusted and len(tokens) > 4:
        return False
    if any(_VERBAL_CONTRACTION_TOKEN_RE.fullmatch(tok) is not None for tok in tokens):
        return False
    first_token = tokens[0].casefold()
    last_token = tokens[-1].casefold()
    if first_token in _LOW_VALUE_ENTITY_TERMS or first_token in {"the", "a", "an"}:
        return False
    if last_token in {"the", "a", "an"}:
        return False

    return len(substantive) >= 2


def _contextually_reject_entity(label: str, text: str) -> bool:
    phrases = _ENTITY_CONTEXT_REJECTIONS.get(label.casefold())
    if not phrases:
        return False
    lowered = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return any(phrase in lowered for phrase in phrases)


def _appears_as_entity_span(label: str, text: str, *, trusted: bool) -> bool:
    if not isinstance(label, str) or not label.strip():
        return False
    if not isinstance(text, str) or not text.strip():
        return False

    tokens = _entity_tokens(label)
    if not tokens:
        return False

    escaped = r"[ \t]+".join(re.escape(token) for token in tokens)
    flags = 0 if (trusted and len(tokens) == 1 and len(tokens[0]) <= 4) else re.IGNORECASE
    return re.search(rf"\b{escaped}\b", text, flags) is not None


def _is_sentence_start_match(text: str, start_index: int) -> bool:
    prefix = text[:start_index].rstrip()
    if not prefix:
        return True
    return prefix[-1] in ".!?\n"


def _filter_ner_entities(
    text: str,
    ner_entities: List[Dict[str, str]],
    *,
    configured_persons: Dict[str, str] | None = None,
) -> List[Dict[str, str]]:
    filtered: List[Dict[str, str]] = []
    seen_keys: set[Tuple[str, str]] = set()
    for entity in ner_entities:
        if not isinstance(entity, dict):
            continue
        raw_name = str(entity.get("name") or "")
        ent_type = _coerce_entity_type(entity.get("type"))
        trusted = ent_type in _TRUSTED_SHORT_ENTITY_TYPES
        candidates = (
            _split_fused_configured_persons(raw_name, configured_persons)
            if (not ent_type or ent_type in _PERSON_ENTITY_TYPES)
            else [raw_name]
        )
        for cand_name in candidates:
            sanitized_name = _canonicalize_unstable_compound_person_label(
                cand_name,
                text,
                trusted=trusted,
                entity_type=ent_type,
                configured_persons=configured_persons,
            )
            if not (
                isinstance(sanitized_name, str)
                and _is_meaningful_entity_label(sanitized_name, trusted=trusted, entity_type=ent_type)
                and not _contextually_reject_entity(sanitized_name, text)
                and _appears_as_entity_span(sanitized_name, text, trusted=trusted)
            ):
                continue
            dedupe_key = (sanitized_name.casefold(), ent_type)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            cleaned = dict(entity)
            cleaned["name"] = sanitized_name
            filtered.append(cleaned)
    return filtered


def _filter_entity_labels(
    text: str,
    labels: List[str],
    *,
    trusted: bool,
    configured_persons: Dict[str, str] | None = None,
) -> List[str]:
    filtered: List[str] = []
    for label in labels:
        for cand_label in _split_fused_configured_persons(str(label or ""), configured_persons):
            sanitized_label = _canonicalize_unstable_compound_person_label(
                cand_label,
                text,
                trusted=trusted,
                configured_persons=configured_persons,
            )
            if not (
                isinstance(sanitized_label, str)
                and _is_meaningful_entity_label(sanitized_label, trusted=trusted)
                and not _contextually_reject_entity(sanitized_label, text)
            ):
                continue
            if trusted and not _appears_as_entity_span(sanitized_label, text, trusted=trusted):
                continue
            filtered.append(sanitized_label)
    return dedupe_tokens(filtered)


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
    multiword_heads: set[str] = set()
    for row in rows:
        label = str(row.get("label", "")).strip()
        if len(_entity_tokens(label)) < 2:
            continue
        if row.get("type"):
            head = _entity_tokens(label)[0].casefold()
            if head:
                multiword_heads.add(head)

    return [
        {
            "label": str(row["label"]),
            "score": round(float(row.get("score", 0.0)), 3),
            "sources": sorted(str(src) for src in row.get("sources", set())),
            "type": row.get("type"),
        }
        for row in rows
        if not (
            len(_entity_tokens(str(row.get("label", "")).strip())) == 1
            and row.get("sources") == {"fallback"}
            and str(row.get("label", "")).strip().casefold() in multiword_heads
        )
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


_CAPTION_TAG_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\btrumpet\b", "trumpet"),
    (r"\btrombone\b", "trombone"),
    (r"\bsaxophone\b", "saxophone"),
    (r"\bclarinet\b", "clarinet"),
    (r"\bflute\b", "flute"),
    (r"\bviolin\b", "violin"),
    (r"\bcello\b", "cello"),
    (r"\bguitar\b", "guitar"),
    (r"\bpiano\b", "piano"),
    (r"\bkeyboard\b", "keyboard"),
    (r"\bdrums?\b", "drums"),
    (r"\bchoir\b", "choir"),
    (r"\bband\b", "band"),
    (r"\borchestra\b", "orchestra"),
    (r"\bstage\b", "stage"),
    (r"\bclassroom\b", "classroom"),
    (r"\bkitchen\b", "kitchen"),
    (r"\broom\b", "indoor"),
    (r"\boutside\b|\boutdoors?\b", "outdoor"),
    (r"\bbeach\b", "beach"),
    (r"\bpark\b", "park"),
    (r"\byard\b", "yard"),
)

_MUSIC_CAPTION_TAGS = {
    "trumpet",
    "trombone",
    "saxophone",
    "clarinet",
    "flute",
    "violin",
    "cello",
    "guitar",
    "piano",
    "keyboard",
    "drums",
    "choir",
    "band",
    "orchestra",
}


def _iter_caption_tags(item: Dict[str, Any]) -> List[tuple[str, str]]:
    caption = item.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        return []

    text = caption.casefold()
    labels: List[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern, label in _CAPTION_TAG_PATTERNS:
        if not re.search(pattern, text):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        labels.append((label, "caption"))

    music_labels = {label for label, _source in labels if label in _MUSIC_CAPTION_TAGS}
    if music_labels:
        if "music" not in seen:
            seen.add("music")
            labels.append(("music", "caption_inference"))
        if (
            re.search(r"\b(play|playing|perform|performing|sing|singing|concert|recital)\b", text)
            and "performance" not in seen
        ):
            labels.append(("performance", "caption_inference"))

    return labels


def _rank_entities(text: str, ner_entities: List[Dict[str, str]], fallback_entities: List[str]) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = {}
    for entity in ner_entities:
        name = entity.get("name")
        ent_type = _coerce_entity_type(entity.get("type"))
        mention_bonus = max(0.0, (_count_entity_mentions(str(name or ""), text) - 1) * 1.5)
        score = 6.0 + _ENTITY_TYPE_WEIGHTS.get(ent_type, 1.0) + mention_bonus
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
        mention_bonus = max(0.0, (_count_entity_mentions(str(name or ""), text) - 1) * 1.5)
        _add_candidate(
            bucket,
            name,
            2.5 + mention_bonus,
            "fallback",
            validator=is_valid_entity_token,
            normalizer=normalize_entity_token,
        )
    return _sorted_candidates(bucket)


def _rank_tags(
    item: Dict[str, Any],
    ner_entities: List[Dict[str, str]],
    fallback_entities: List[str],
    *,
    configured_persons: Dict[str, str] | None = None,
) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = {}
    excluded_person_keys: set[str] = set(_ALWAYS_PERSON_TAG_EXCLUSIONS)
    if configured_persons:
        excluded_person_keys.update(configured_persons.keys())
    for entity in ner_entities:
        if _coerce_entity_type(entity.get("type")) in _PERSON_ENTITY_TYPES:
            norm_p = normalize_tag_token(entity.get("name"))
            if isinstance(norm_p, str) and norm_p:
                excluded_person_keys.add(norm_p.casefold())
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
    for label, source in _iter_caption_tags(item):
        normalized = normalize_tag_token(label)
        key = normalized.casefold() if isinstance(normalized, str) else None
        if key and key in bucket:
            bucket[key]["sources"].add(source)
            continue
        _add_candidate(
            bucket,
            label,
            3.5,
            source,
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
        norm_fb = normalize_tag_token(name)
        if isinstance(norm_fb, str) and norm_fb.casefold() in excluded_person_keys:
            continue
        if configured_persons and len(_split_fused_configured_persons(name, configured_persons)) >= 2:
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
    model_id = (
        ((cfg.get("config", {}) or {}).get("tagger", {}) or {}).get("ner_model")
        or "dslim/bert-base-NER"
    )
    meta: Dict[str, Any] = {
        "status": "ok",
        "engine": "transformers",
        "model_id": model_id,
        "requested_implementation": model_id,
        "effective_implementation": model_id,
        "fallback_chain": [],
        "typed_entity_count": 0,
    }
    text = _gather_text(item)
    if not text:
        meta.update(status="no_text", reason="no_text")
        return {
            "tags": [],
            "usefulness": 0.0,
            "entities": [],
            "ner_entities": [],
            "tag_details": [],
            "entity_details": [],
            "tagger_meta": meta,
        }
    try:
        extracted_entities, ner_entities = _extract_entities_transformers(text, cfg)
    except Exception as exc:
        logger.warning("NER inference failed; retaining pattern tags: %s", exc)
        extracted_entities, ner_entities = [], []
        meta.update(
            status="degraded",
            reason="ner_inference_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            engine="pattern_tags",
            effective_implementation="pattern_tags",
            fallback_chain=["pattern_tags"],
        )
    configured_persons = _load_configured_person_map(cfg)
    ner_entities = _filter_ner_entities(text, ner_entities, configured_persons=configured_persons)
    meta["typed_entity_count"] = len(ner_entities)
    if meta["status"] == "ok":
        meta["reason"] = "typed_entities_emitted" if ner_entities else "content_appropriate_empty"
    extracted_entities = _filter_entity_labels(
        text,
        extracted_entities,
        trusted=True,
        configured_persons=configured_persons,
    )
    fallback_entities = _fallback_entities(text)
    fallback_entities = _filter_entity_labels(
        text,
        fallback_entities,
        trusted=False,
        configured_persons=configured_persons,
    )
    if not extracted_entities:
        extracted_entities = fallback_entities
    entity_details = _rank_entities(text, ner_entities, fallback_entities)
    tag_details = _rank_tags(
        item,
        ner_entities,
        fallback_entities,
        configured_persons=configured_persons,
    )
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
        "tagger_meta": meta,
    }
