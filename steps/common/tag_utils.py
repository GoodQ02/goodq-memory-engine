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

    ner_entities = item.get('ner_entities')
    if isinstance(ner_entities, Sequence) and not isinstance(ner_entities, (str, bytes)):
        entity_labels = []
        for entity in ner_entities:
            if isinstance(entity, dict):
                entity_labels.append(entity.get('name') or entity.get('text'))
        if entity_labels:
            entities_sources.append(entity_labels)

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

    canonical_tags = merge_tag_sources(
        *tags_sources,
        validator=is_valid_tag_token,
        normalizer=normalize_tag_token,
    )
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
