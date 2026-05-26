"""
Scene Summarization Module
Generates natural language summaries of video scenes from rich metadata.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import json
import re

try:
    from steps.common.tag_utils import (
        dedupe_tokens,
        is_valid_entity_token,
        is_valid_tag_token,
        normalize_entity_token,
        normalize_tag_token,
    )
except Exception:
    def dedupe_tokens(tokens, **_kwargs):
        return [str(token).strip() for token in tokens if isinstance(token, str) and token.strip()]
    def is_valid_entity_token(token):
        return bool(str(token or "").strip())
    def is_valid_tag_token(token):
        return bool(str(token or "").strip())
    def normalize_entity_token(token):
        text = str(token or "").strip()
        return text or None
    def normalize_tag_token(token):
        text = str(token or "").strip()
        return text or None

def _format_list(items: list, max_items: int = 5) -> str:
    """Format a list for display"""
    if not items:
        return "none"
    items_str = [str(i) for i in items[:max_items]]
    suffix = f" (+{len(items) - max_items} more)" if len(items) > max_items else ""
    return ", ".join(items_str) + suffix


def _format_emotions(emotions: list, max_items: int = 3) -> str:
    """Format emotion list with scores"""
    if not emotions:
        return "neutral"
    formatted = []
    for i, emo in enumerate(emotions[:max_items]):
        if isinstance(emo, dict):
            label = emo.get('label', 'unknown')
            score = emo.get('score', 0)
            formatted.append(f"{label} ({score:.0%})")
    return ", ".join(formatted)


def _format_objects(objects: list, max_items: int = 5) -> str:
    """Format object list with counts"""
    if not objects:
        return "none"
    formatted = []
    for obj in objects[:max_items]:
        if isinstance(obj, dict):
            label = obj.get('label', 'unknown')
            formatted.append(label)
        else:
            formatted.append(str(obj))
    return ", ".join(formatted)


def _scene_keyframe(scene_meta: Dict[str, Any]) -> Dict[str, Any]:
    keyframe = scene_meta.get("keyframe")
    return keyframe if isinstance(keyframe, dict) else {}


def _scene_audio(scene_meta: Dict[str, Any]) -> Dict[str, Any]:
    audio = scene_meta.get("audio")
    return audio if isinstance(audio, dict) else {}


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def _coerce_numeric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _emotion_entries(scene_meta: Dict[str, Any], audio_meta: Dict[str, Any]) -> list:
    emotions = _first_non_empty(
        scene_meta.get("emotions"),
        audio_meta.get("emotions"),
    )
    if isinstance(emotions, list):
        return emotions

    emotion_scores = _first_non_empty(
        scene_meta.get("emotion_scores"),
        audio_meta.get("emotion_scores"),
    )
    if isinstance(emotion_scores, dict):
        ranked = []
        for label, score in emotion_scores.items():
            try:
                ranked.append({"label": str(label), "score": float(score)})
            except (TypeError, ValueError):
                continue
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    return []


def _dominant_emotion(scene_meta: Dict[str, Any], audio_meta: Dict[str, Any], emotions: list) -> str:
    dominant = _first_non_empty(
        scene_meta.get("dominant_emotion"),
        scene_meta.get("emotion"),
        audio_meta.get("emotion"),
        scene_meta.get("audio_emotion"),
        audio_meta.get("audio_emotion"),
    )

    if isinstance(dominant, str) and dominant.strip():
        return dominant.strip()

    if isinstance(dominant, list) and dominant:
        first = dominant[0]
        if isinstance(first, dict):
            label = first.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()

    if isinstance(dominant, dict):
        label = dominant.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()

    if emotions:
        first = emotions[0]
        if isinstance(first, dict):
            label = first.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()

    return "neutral"


def _sentiment(scene_meta: Dict[str, Any], audio_meta: Dict[str, Any]) -> tuple[str, float]:
    label = scene_meta.get("sentiment_label")
    score = scene_meta.get("sentiment_score")

    sentiment_payload = _first_non_empty(scene_meta.get("sentiment"), audio_meta.get("sentiment"))
    if isinstance(sentiment_payload, dict):
        label = _first_non_empty(label, sentiment_payload.get("label"))
        score = _first_non_empty(score, sentiment_payload.get("score"))
    elif isinstance(sentiment_payload, str):
        label = _first_non_empty(label, sentiment_payload)

    sentiment_label = str(label).strip() if label is not None else "neutral"
    try:
        sentiment_score = float(score)
    except (TypeError, ValueError):
        sentiment_score = 0.5

    return sentiment_label, sentiment_score


def _semantic_tags(scene_meta: Dict[str, Any]) -> list[str]:
    labels = []
    for detail in scene_meta.get("tag_details") or []:
        if isinstance(detail, dict):
            labels.append(detail.get("label"))
    labels.extend(scene_meta.get("tags") or [])
    keyframe = _scene_keyframe(scene_meta)
    audio = _scene_audio(scene_meta)
    labels.extend(keyframe.get("tags") or [])
    labels.extend(audio.get("tags") or [])
    return dedupe_tokens(
        labels,
        validator=is_valid_tag_token,
        normalizer=normalize_tag_token,
    )


def _semantic_entities(scene_meta: Dict[str, Any]) -> list[str]:
    labels = []
    for entity in scene_meta.get("ner_entities") or []:
        if isinstance(entity, dict):
            labels.append(entity.get("name") or entity.get("text"))
    labels.extend(scene_meta.get("entities") or [])
    keyframe = _scene_keyframe(scene_meta)
    audio = _scene_audio(scene_meta)
    labels.extend(keyframe.get("entities") or [])
    labels.extend(audio.get("entities") or [])
    for entity in audio.get("ner_entities") or []:
        if isinstance(entity, dict):
            labels.append(entity.get("name") or entity.get("text"))
    return dedupe_tokens(
        labels,
        validator=is_valid_entity_token,
        normalizer=normalize_entity_token,
    )


_PLACEHOLDER_SPEAKER_PATTERN = re.compile(r"^(?:SPEAKER|FACE)_\d+$", re.IGNORECASE)


def _normalize_speaker_label(raw: Any) -> Optional[str]:
    candidate = raw
    if isinstance(raw, dict):
        candidate = (
            raw.get("name")
            or raw.get("identity")
            or raw.get("person")
            or raw.get("speaker_id")
            or raw.get("speaker")
            or raw.get("label")
        )
    normalized = normalize_entity_token(candidate)
    return normalized or None


def _speaker_summary(scene_meta: Dict[str, Any]) -> Optional[str]:
    speaker_labels: list[str] = []
    anonymous_ids: set[str] = set()
    audio_meta = _scene_audio(scene_meta)

    raw_speakers = _first_non_empty(scene_meta.get("speakers"), audio_meta.get("speakers"))
    if isinstance(raw_speakers, list):
        for raw in raw_speakers:
            label = _normalize_speaker_label(raw)
            if not label:
                continue
            if _PLACEHOLDER_SPEAKER_PATTERN.fullmatch(label):
                anonymous_ids.add(label.casefold())
                continue
            speaker_labels.append(label)

    raw_segments = _first_non_empty(
        scene_meta.get("speaker_transcript"),
        audio_meta.get("speaker_transcript"),
    )
    if isinstance(raw_segments, list):
        for raw in raw_segments:
            label = _normalize_speaker_label(raw)
            if not label:
                continue
            if _PLACEHOLDER_SPEAKER_PATTERN.fullmatch(label):
                anonymous_ids.add(label.casefold())
                continue
            speaker_labels.append(label)

    raw_ids = _first_non_empty(scene_meta.get("speaker_ids"), audio_meta.get("speaker_ids"))
    if isinstance(raw_ids, list):
        for raw in raw_ids:
            label = _normalize_speaker_label(raw)
            if not label:
                continue
            if _PLACEHOLDER_SPEAKER_PATTERN.fullmatch(label):
                anonymous_ids.add(label.casefold())
                continue
            speaker_labels.append(label)

    speaker_labels = dedupe_tokens(speaker_labels, normalizer=normalize_entity_token)
    anonymous_count = len(anonymous_ids)
    if speaker_labels and anonymous_count:
        suffix = "anonymous speaker" if anonymous_count == 1 else f"{anonymous_count} anonymous speakers"
        return f"{', '.join(speaker_labels)} + {suffix}"
    if speaker_labels:
        return ", ".join(speaker_labels)
    if anonymous_count:
        return "1 anonymous speaker" if anonymous_count == 1 else f"{anonymous_count} anonymous speakers"
    return None


def generate_scene_summary_template(scene_meta: Dict[str, Any]) -> str:
    """
    Generate a template-based natural language summary of a scene.
    Fast, deterministic, no external dependencies.
    
    Args:
        scene_meta: Rich scene metadata dictionary
        
    Returns:
        Natural language summary string
    """
    # Extract key data
    index = scene_meta.get('index', 0)
    start = scene_meta.get('start', 0.0)
    end = scene_meta.get('end', 0.0)
    duration = scene_meta.get('duration', end - start)
    keyframe_meta = _scene_keyframe(scene_meta)
    audio_meta = _scene_audio(scene_meta)
    
    # Visual information
    caption = _first_non_empty(scene_meta.get('caption'), keyframe_meta.get('caption')) or ''
    objects = _first_non_empty(scene_meta.get('objects'), keyframe_meta.get('objects')) or []
    face_count = _coerce_numeric(
        _first_non_empty(
            scene_meta.get('face_count'),
            scene_meta.get('visible_face_count'),
            keyframe_meta.get('face_count'),
        ),
        default=0,
    )
    
    # Audio information
    transcript = _first_non_empty(scene_meta.get('transcript'), audio_meta.get('transcript')) or ''
    
    # Emotional context - check both top level and audio nested
    sentiment_label, sentiment_score = _sentiment(scene_meta, audio_meta)
    emotions = _emotion_entries(scene_meta, audio_meta)
    dominant_emotion = _dominant_emotion(scene_meta, audio_meta, emotions)
    
    # Tags and entities
    tags = _semantic_tags(scene_meta)
    entities = _semantic_entities(scene_meta)
    
    # Build summary parts
    parts = []
    
    # Time and index
    parts.append(f"Scene {index} ({start:.1f}s-{end:.1f}s, {duration:.1f}s duration)")
    
    # Visual description
    if caption:
        parts.append(f"Visual: {caption}")
    if objects:
        parts.append(f"Objects: {_format_objects(objects)}")
    if face_count > 0:
        parts.append(f"Faces detected: {face_count}")
    
    # Audio/transcript
    if transcript:
        # Truncate long transcripts
        transcript_summary = transcript if len(transcript) <= 100 else transcript[:97] + "..."
        parts.append(f'Transcript: "{transcript_summary}"')
    
    # Speaker information
    speaker_summary = _speaker_summary(scene_meta)
    if speaker_summary:
        parts.append(f"Speakers: {speaker_summary}")
    
    # Emotional context
    if emotions:
        parts.append(f"Emotions: {_format_emotions(emotions)}")
    elif dominant_emotion and dominant_emotion != 'neutral':
        parts.append(f"Emotion: {dominant_emotion}")
    
    if sentiment_label and sentiment_label != 'neutral':
        parts.append(f"Sentiment: {sentiment_label} ({sentiment_score:.0%})")
    
    # Additional context
    if tags:
        parts.append(f"Tags: {_format_list(tags, max_items=3)}")
    if entities:
        parts.append(f"Entities: {_format_list(entities, max_items=3)}")
    
    # Join all parts with newlines for readability
    summary = ". ".join(parts)
    
    return summary


def generate_scene_summary_llm(scene_meta: Dict[str, Any], cfg: Dict[str, Any]) -> Optional[str]:
    """
    Generate an LLM-based natural language summary of a scene.
    More contextual and natural, but requires LLM availability.
    
    Args:
        scene_meta: Rich scene metadata dictionary
        cfg: Configuration dictionary with LLM settings
        
    Returns:
        Natural language summary string, or None if LLM unavailable
    """
    try:
        import requests
        
        # Get LLM endpoint
        llm_config = cfg.get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        
        # Build context from metadata
        index = scene_meta.get('index', 0)
        start = scene_meta.get('start', 0.0)
        end = scene_meta.get('end', 0.0)
        duration = scene_meta.get('duration', end - start)
        caption = scene_meta.get('caption', 'No visual description')
        transcript = scene_meta.get('transcript', 'No audio')
        speakers = scene_meta.get('speakers', [])
        emotions = scene_meta.get('emotions', [])
        sentiment_label = scene_meta.get('sentiment_label', 'neutral')
        objects = scene_meta.get('objects', [])
        
        # Format emotions
        emotions_str = _format_emotions(emotions) if emotions else "neutral"
        speakers_str = _speaker_summary(scene_meta) or "unknown"
        objects_str = _format_objects(objects) if objects else "none visible"
        
        # Build prompt
        prompt = f"""Analyze this video scene and generate a concise 2-3 sentence summary:

Scene {index} ({start:.1f}s - {end:.1f}s, {duration:.1f}s)

Visual: {caption}
Objects: {objects_str}

Audio: {transcript if transcript else "No dialogue"}
Speakers: {speakers_str}
Emotions: {emotions_str}
Sentiment: {sentiment_label}

Summary:"""
        
        # Call LLM
        response = requests.post(
            api_url,
            json={
                "messages": [
                    {"role": "system", "content": "You are a video scene analyst. Generate concise, informative summaries."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 150,
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            return summary if summary else None
        
        return None
        
    except Exception as e:
        # Fall back to template if LLM fails
        print(f"[scene_summarizer] LLM summarization failed: {e}")
        return None


def generate_scene_summary(
    scene_meta: Dict[str, Any],
    cfg: Dict[str, Any],
    use_llm: bool = True
) -> str:
    """
    Generate a natural language summary of a scene.
    Tries LLM first if enabled, falls back to template.
    
    Args:
        scene_meta: Rich scene metadata dictionary
        cfg: Configuration dictionary
        use_llm: Whether to attempt LLM-based summarization
        
    Returns:
        Natural language summary string
    """
    summary = None
    
    # Try LLM if enabled
    if use_llm:
        summary = generate_scene_summary_llm(scene_meta, cfg)
    
    # Fall back to template
    if not summary:
        summary = generate_scene_summary_template(scene_meta)
    
    return summary
