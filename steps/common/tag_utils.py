from __future__ import annotations
from typing import Any, Iterable, List, Optional, Sequence


def _normalize_token(token: Any) -> Optional[str]:
    if token is None:
        return None
    text = str(token).strip()
    if not text:
        return None
    return text


def dedupe_tokens(tokens: Iterable[Any], *, casefold: bool = True) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in tokens:
        text = _normalize_token(raw)
        if text is None:
            continue
        key = text.casefold() if casefold else text
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def merge_tag_sources(*sources: Iterable[Any], casefold: bool = True) -> List[str]:
    merged: List[Any] = []
    for source in sources:
        if not source:
            continue
        merged.extend(source)
    return dedupe_tokens(merged, casefold=casefold)


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

    canonical_tags = merge_tag_sources(*tags_sources)
    canonical_entities = merge_tag_sources(*entities_sources)

    item['tags'] = canonical_tags
    item['entities'] = canonical_entities

    vocab_raw = [tok.casefold() for tok in (canonical_tags + canonical_entities)]
    vocab = dedupe_tokens(vocab_raw, casefold=False)
    if vocab:
        item['vocabulary'] = vocab
    else:
        item.pop('vocabulary', None)
