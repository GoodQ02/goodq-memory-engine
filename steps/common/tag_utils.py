from __future__ import annotations
import re
from typing import Any, Callable, Iterable, List, Optional, Sequence

try:
    from lib.kg_realtime_integration import (
        _ENTITY_CONTRACTION_PARTS as _KG_CONTRACTION_PARTS,
        _ENTITY_STOPWORDS as _KG_STOPWORDS,
        _is_valid_entity_token as _kg_is_valid_entity_token,
        normalize_entity_name as _kg_normalize_entity_name,
    )
except Exception:
    _KG_STOPWORDS = {
        "i", "i'm", "you", "you're", "we", "we're", "they", "it's", "that's",
        "what", "well", "yeah", "okay", "why", "how", "look", "but", "and", "the",
    }
    _KG_CONTRACTION_PARTS = {"'m", "'re", "'s", "'ll", "'ve", "'d", "n't"}
    _kg_is_valid_entity_token = None
    _kg_normalize_entity_name = None


TokenValidator = Callable[[str], bool]
TokenNormalizer = Callable[[Any], Optional[str]]

_SEMANTIC_STOPWORDS = set(_KG_STOPWORDS) | {"unknown", "none"}
_SEMANTIC_CONTRACTION_PARTS = set(_KG_CONTRACTION_PARTS)
_SEMANTIC_PLACEHOLDER_PATTERN = re.compile(r"^(?:SPEAKER|FACE)_\d+$", re.IGNORECASE)


def _normalize_token(token: Any) -> Optional[str]:
    if token is None:
        return None
    text = re.sub(r"\s+", " ", str(token)).strip()
    if not text:
        return None
    return text


def _token_key(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9']+", "", text).casefold()


def normalize_tag_token(token: Any) -> Optional[str]:
    text = _normalize_token(token)
    if text is None:
        return None
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text).strip()
    return text or None


def normalize_entity_token(token: Any) -> Optional[str]:
    text = _normalize_token(token)
    if text is None:
        return None
    if _kg_normalize_entity_name is not None:
        normalized = _kg_normalize_entity_name(text)
        return normalized or None
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text).strip()
    return text or None


def is_semantic_stopword(token: Any) -> bool:
    text = normalize_tag_token(token)
    if text is None:
        return True
    compact = _token_key(text)
    if not compact:
        return True
    return compact in _SEMANTIC_STOPWORDS or compact in _SEMANTIC_CONTRACTION_PARTS


def is_valid_tag_token(token: Any) -> bool:
    text = normalize_tag_token(token)
    if text is None:
        return False
    compact = _token_key(text)
    if not compact:
        return False
    if compact in _SEMANTIC_STOPWORDS or compact in _SEMANTIC_CONTRACTION_PARTS:
        return False
    if compact.isdigit():
        return False
    return len(compact) >= 3 or text.isupper()


def is_valid_entity_token(token: Any) -> bool:
    text = _normalize_token(token)
    if text is None:
        return False
    if _SEMANTIC_PLACEHOLDER_PATTERN.fullmatch(text.strip()):
        return False
    if _kg_is_valid_entity_token is not None:
        return bool(_kg_is_valid_entity_token(text))
    return is_valid_tag_token(text)


def dedupe_tokens(
    tokens: Iterable[Any],
    *,
    casefold: bool = True,
    validator: Optional[TokenValidator] = None,
    normalizer: Optional[TokenNormalizer] = None,
) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in tokens:
        text = normalizer(raw) if normalizer is not None else _normalize_token(raw)
        if text is None:
            continue
        if validator is not None and not validator(text):
            continue
        key = text.casefold() if casefold else text
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def merge_tag_sources(
    *sources: Iterable[Any],
    casefold: bool = True,
    validator: Optional[TokenValidator] = None,
    normalizer: Optional[TokenNormalizer] = None,
) -> List[str]:
    merged: List[Any] = []
    for source in sources:
        if not source:
            continue
        merged.extend(source)
    return dedupe_tokens(
        merged,
        casefold=casefold,
        validator=validator,
        normalizer=normalizer,
    )


def canonicalize_taxonomy(item: dict[str, Any]) -> None:
    """Mutate an item in-place so tags/entities share a common vocabulary."""
    tags_sources: List[Iterable[Any]] = []
    entities_sources: List[Iterable[Any]] = []

    tags_value = item.get('tags')
    if isinstance(tags_value, Sequence) and not isinstance(tags_value, (str, bytes)):
        tags_sources.append(tags_value)

    entities_value = item.get('entities')
    if isinstance(entities_value, Sequence) and not isinstance(entities_value, (str, bytes)):
        entities_sources.append(entities_value)

    person_tag_exclusions: set[str] = {"santa", "santa claus", "saint nick", "st nick", "st. nick"}
    ner_entities = item.get('ner_entities')
    if isinstance(ner_entities, Sequence) and not isinstance(ner_entities, (str, bytes)):
        entity_labels = []
        for entity in ner_entities:
            if isinstance(entity, dict):
                e_name = entity.get('name') or entity.get('text')
                entity_labels.append(e_name)
                e_type = str(entity.get('type') or '').strip().upper()
                if e_type in {'PERSON', 'PER', 'CHARACTER'}:
                    norm_e = normalize_tag_token(e_name)
                    if norm_e:
                        person_tag_exclusions.add(norm_e.casefold())
        if entity_labels:
            entities_sources.append(entity_labels)

    entity_details = item.get('entity_details')
    if isinstance(entity_details, Sequence) and not isinstance(entity_details, (str, bytes)):
        for detail in entity_details:
            if isinstance(detail, dict):
                d_type = str(detail.get('type') or '').strip().upper()
                if d_type in {'PERSON', 'PER', 'CHARACTER'}:
                    norm_d = normalize_tag_token(detail.get('label') or detail.get('name'))
                    if norm_d:
                        person_tag_exclusions.add(norm_d.casefold())

    objs = item.get('objects')
    if isinstance(objs, Sequence):
        labels = []
        for obj in objs:
            if isinstance(obj, dict):
                labels.append(obj.get('label'))
        if labels:
            tags_sources.append(labels)

    place_tags = item.get('place_tags')
    if isinstance(place_tags, Sequence) and not isinstance(place_tags, (str, bytes)):
        tags_sources.append(place_tags)

    music_events = item.get('music_events')
    if isinstance(music_events, Sequence):
        labels = []
        for ev in music_events:
            if isinstance(ev, dict):
                labels.append(ev.get('label'))
        if labels:
            tags_sources.append(labels)

    time_hints = item.get('time_hints') if isinstance(item.get('time_hints'), dict) else {}
    if time_hints:
        temporal_tokens: List[str] = []
        for key in ('explicit_dates', 'times', 'weekdays', 'months', 'relative_phrases'):
            values = time_hints.get(key)
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                temporal_tokens.extend(values)
        if temporal_tokens:
            tags_sources.append(temporal_tokens)

    audio_summary = item.get('audio_summary')
    if isinstance(audio_summary, dict):
        for key in ('top_tags', 'top_entities'):
            values = audio_summary.get(key)
            if isinstance(values, Sequence):
                tokens = []
                for entry in values:
                    if isinstance(entry, dict):
                        if 'label' in entry:
                            tokens.append(entry.get('label'))
                        elif 'tag' in entry:
                            tokens.append(entry.get('tag'))
                if tokens:
                    if key == 'top_tags':
                        tags_sources.append(tokens)
                    else:
                        entities_sources.append(tokens)

    canonical_tags = [
        tag
        for tag in merge_tag_sources(
            *tags_sources,
            validator=is_valid_tag_token,
            normalizer=normalize_tag_token,
        )
        if tag.casefold() not in person_tag_exclusions
    ]
    canonical_entities = merge_tag_sources(
        *entities_sources,
        validator=is_valid_entity_token,
        normalizer=normalize_entity_token,
    )

    item['tags'] = canonical_tags
    item['entities'] = canonical_entities

    vocab_raw = [tok.casefold() for tok in (canonical_tags + canonical_entities)]
    vocab = dedupe_tokens(vocab_raw, casefold=False)
    if vocab:
        item['vocabulary'] = vocab
    else:
        item.pop('vocabulary', None)


def is_runaway_decoder_phrase(
    phrase_text: str,
    *,
    vocab_words: Optional[set[str]] = None,
    untimed_native: bool = False,
) -> bool:
    """Detect Whisper single-temperature repetition loops and hotword-list echoes."""
    if not isinstance(phrase_text, str) or not phrase_text.strip():
        return False
    from collections import Counter

    words = [w.strip("'").casefold() for w in re.findall(r"[A-Za-z0-9']+", phrase_text) if w.strip("'")]
    if len(words) >= 8:
        counts = Counter(words)
        top1 = counts.most_common(1)[0][1]
        if top1 >= 6 and (top1 / len(words)) >= 0.45:
            return True
        if len(words) >= 10:
            top2 = sum(c for _, c in counts.most_common(2))
            if top2 >= 8 and (top2 / len(words)) >= 0.70:
                return True
        if len(words) >= 16:
            top4 = sum(c for _, c in counts.most_common(4))
            if (top4 / len(words)) >= 0.80:
                return True
    if vocab_words and len(words) >= 4:
        in_vocab = sum(1 for w in words if w in vocab_words)
        if (in_vocab / len(words)) >= 0.85 and (untimed_native or "," in phrase_text or len(words) >= 6):
            return True
    return False


def reliable_transcript_for_entities(item: dict[str, Any]) -> str:
    """Return transcript text excluding rejected low-confidence segments and decoder loops."""
    if not isinstance(item, dict):
        return ""
    raw_tx = item.get("transcript") or item.get("transcription") or ""
    if isinstance(raw_tx, dict):
        raw_tx = raw_tx.get("text") or ""
    if not isinstance(raw_tx, str) or not raw_tx.strip():
        return ""

    tmeta = item.get("transcript_meta")
    if not isinstance(tmeta, dict):
        kept_lines = [
            line.strip()
            for line in raw_tx.splitlines()
            if line.strip() and not is_runaway_decoder_phrase(line)
        ]
        return "\n".join(kept_lines)

    rejected_indices: set[int] = set()
    rejected_texts: set[str] = set()
    tq = tmeta.get("transcription_quality")
    if isinstance(tq, dict):
        region_offset = 0
        for rr in tq.get("region_results") or []:
            if not isinstance(rr, dict):
                continue
            co = rr.get("confidence_override")
            if isinstance(co, dict):
                for seg in co.get("segments") or []:
                    if not isinstance(seg, dict):
                        continue
                    if str(seg.get("decision") or "").lower() == "reject":
                        seg_idx = seg.get("segment_index")
                        if type(seg_idx) is int and seg_idx >= 0:
                            rejected_indices.add(region_offset + seg_idx)
                        seg_text = str(seg.get("text") or "").strip()
                        if seg_text:
                            rejected_texts.add(re.sub(r"\s+", " ", seg_text).casefold())
            acc = rr.get("accepted_segment_count")
            if type(acc) is int and acc > 0:
                region_offset += acc

    vocab_words: set[str] = set()
    tctx = tmeta.get("transcription_context")
    if isinstance(tctx, dict):
        for w in tctx.get("words") or []:
            for sub in re.findall(r"[A-Za-z0-9']+", str(w or "")):
                cleaned = sub.strip("'").casefold()
                if cleaned:
                    vocab_words.add(cleaned)

    phrase_obs = tmeta.get("phrase_observations")
    if isinstance(phrase_obs, list) and phrase_obs:
        kept_phrases: List[str] = []
        for obs in phrase_obs:
            if not isinstance(obs, dict):
                continue
            p_text = str(obs.get("text") or "").strip()
            if not p_text:
                continue
            src_idx = obs.get("source_segment_index")
            if type(src_idx) is int and src_idx in rejected_indices:
                continue
            if re.sub(r"\s+", " ", p_text).casefold() in rejected_texts:
                continue
            untimed_native = (
                obs.get("reason") == "paired_native_timestamps_unavailable"
                or obs.get("status") == "unavailable"
            )
            if is_runaway_decoder_phrase(p_text, vocab_words=vocab_words, untimed_native=untimed_native):
                continue
            kept_phrases.append(p_text)
        return "\n".join(kept_phrases)

    kept_lines = [
        line.strip()
        for line in raw_tx.splitlines()
        if line.strip()
        and re.sub(r"\s+", " ", line.strip()).casefold() not in rejected_texts
        and not is_runaway_decoder_phrase(line, vocab_words=vocab_words)
    ]
    return "\n".join(kept_lines)
