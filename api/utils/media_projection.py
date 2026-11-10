"""Safe local media projections for API read models."""
from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
import re
from urllib.parse import quote


def project_legacy_name_matches(segment: dict) -> dict:
    """Exclude proven substring-only name matches without changing saved evidence."""
    texts = [segment.get(k) for k in ("full_transcript", "visual_caption", "ocr_text")]
    texts.extend(row.get("caption") for row in (segment.get("caption_observations") or [])
                 if isinstance(row, dict))
    source_text = "\n".join(value for value in texts if isinstance(value, str))
    rejected = set()
    independently_supported = set()
    for entity in segment.get("entities") or []:
        if not isinstance(entity, dict) or entity.get("entity_type") != "person":
            continue
        name = entity.get("name")
        if not isinstance(name, str) or not name:
            continue
        properties = entity.get("properties") or {}
        matched = properties.get("matched_text") if isinstance(properties, dict) else None
        steps = entity.get("source_steps") or []
        if not (isinstance(matched, str)
                and any(step in steps for step in ("image_caption", "transcription", "ocr"))):
            independently_supported.add(name.casefold())
            continue
        whole_name = rf"(?<!\w){re.escape(name)}(?!\w)"
        # matched_text is only the extractor's first 100 characters. The
        # triggering substring can be later in any retained source caption.
        if (name.casefold() in (matched + "\n" + source_text).casefold()
                and not re.search(whole_name, matched, re.IGNORECASE)
                and not re.search(whole_name, source_text, re.IGNORECASE)):
            rejected.add(name.casefold())
    rejected.difference_update(independently_supported)
    if not rejected:
        return segment
    projected = dict(segment)

    def keep_person(row):
        return not (isinstance(row, dict)
                    and str(row.get("entity_type") or row.get("type") or "person").lower() in {"person", "per"}
                    and str(row.get("name") or row.get("text") or "").casefold() in rejected)

    for field in ("entities", "scene_present_entities", "dialogue_mentioned_entities",
                  "visible_people", "mentioned_people", "dialogue_topics"):
        rows = segment.get(field)
        if isinstance(rows, list):
            projected[field] = [row for row in rows if keep_person(row)]
    disagreements = segment.get("transcript_entity_disagreements")
    if isinstance(disagreements, list):
        projected["transcript_entity_disagreements"] = [
            {**row,
             "entity_names": [name for name in row.get("entity_names", [])
                              if str(name).casefold() not in rejected],
             "mentioned_people": [person for person in row.get("mentioned_people", []) if keep_person(person)]}
            if isinstance(row, dict) else row for row in disagreements
        ]
    arbitration = segment.get("scene_context_arbitration")
    if isinstance(arbitration, dict) and isinstance(arbitration.get("hypotheses"), list):
        projected["scene_context_arbitration"] = {
            **arbitration, "hypotheses": [row for row in arbitration["hypotheses"] if not (
                isinstance(row, dict) and row.get("axis") == "conversation_focus"
                and row.get("evidence_family") == "identity"
                and str(row.get("claim", "")).casefold() in rejected)]}
    return projected


def document_meta_projection(meta: object) -> dict[str, object] | None:
    """Expose extraction scope without publishing local parser paths or diagnostics."""
    if not isinstance(meta, dict):
        return None
    fields = ("engine", "status", "text_scope", "parts_read", "omitted_parts", "omitted_features", "limitations")
    return {key: meta[key] for key in fields if key in meta}


def frame_name_from_reference(frame_reference: object) -> str | None:
    if not isinstance(frame_reference, str):
        return None

    raw = frame_reference.strip()
    if not raw:
        return None

    windows_name = PureWindowsPath(raw).name
    posix_name = PurePosixPath(raw).name
    frame_name = windows_name if len(windows_name) <= len(posix_name) else posix_name
    return frame_name or None


def is_path_like_reference(frame_reference: object) -> bool:
    if not isinstance(frame_reference, str):
        return False

    raw = frame_reference.strip()
    return (
        ":" in raw
        or "\\" in raw
        or "/" in raw
        or raw.startswith("file://")
        or raw.startswith("~")
    )


def frame_endpoint(video_id: str, frame_reference: object) -> str | None:
    if not isinstance(video_id, str) or not video_id.strip():
        return None

    frame_name = frame_name_from_reference(frame_reference)
    if not frame_name:
        return None

    return (
        f"/api/media/video/{quote(video_id, safe='')}/frame/"
        f"{quote(frame_name, safe='')}"
    )


def representative_frame_projection(video_id: str, frame_reference: object) -> dict[str, object]:
    endpoint = frame_endpoint(video_id, frame_reference)
    return {
        "representative_frame": endpoint,
        "representative_frame_available": endpoint is not None,
        "representative_frame_endpoint": endpoint,
        "representative_frame_path_redacted": (
            endpoint is not None and is_path_like_reference(frame_reference)
        ),
    }


def frame_paths_projection(video_id: str, frame_references: object) -> dict[str, object]:
    references = frame_references if isinstance(frame_references, list) else []
    endpoints = [
        endpoint
        for endpoint in (frame_endpoint(video_id, reference) for reference in references)
        if endpoint
    ]
    return {
        "frame_paths": endpoints,
        "frame_endpoints": endpoints,
        "frame_path_count": len(endpoints),
        "frame_paths_redacted": any(is_path_like_reference(reference) for reference in references),
    }


def thumbnail_projection(video_id: str, frame_reference: object) -> dict[str, object]:
    endpoint = frame_endpoint(video_id, frame_reference)
    return {
        "thumbnail": endpoint,
        "thumbnail_available": endpoint is not None,
        "thumbnail_endpoint": endpoint,
        "thumbnail_path_redacted": (
            endpoint is not None and is_path_like_reference(frame_reference)
        ),
    }


def _sanitize_visual_value(video_id: str, value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for k, v in value.items():
            if k in {"source_path", "path", "file_path"} and isinstance(v, str):
                endpoint = frame_endpoint(video_id, v)
                if endpoint:
                    sanitized["frame_endpoint"] = endpoint
                frame_name = frame_name_from_reference(v)
                if frame_name:
                    sanitized["frame_name"] = frame_name
                continue
            sanitized[str(k)] = _sanitize_visual_value(video_id, v)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_visual_value(video_id, item) for item in value]
    return value


def sanitize_visual_observations(video_id: str, observations: object) -> list[dict[str, object]]:
    if not isinstance(observations, list):
        return []
    out: list[dict[str, object]] = []
    for item in observations:
        if isinstance(item, dict):
            projected = _sanitize_visual_value(video_id, item)
            if isinstance(projected, dict):
                out.append(projected)
    return out


def sanitize_detected_objects(video_id: str, objects: object) -> list[dict[str, object]]:
    if not isinstance(objects, list):
        return []
    out: list[dict[str, object]] = []
    for item in objects:
        if isinstance(item, dict):
            projected = _sanitize_visual_value(video_id, item)
            if isinstance(projected, dict):
                out.append(projected)
    return out


def sanitize_visual_meta(video_id: str, meta: object) -> dict[str, object] | None:
    if not isinstance(meta, dict):
        return None
    projected = _sanitize_visual_value(video_id, meta)
    return projected if isinstance(projected, dict) else None
