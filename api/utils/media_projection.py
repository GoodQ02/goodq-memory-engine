"""Safe local media projections for API read models."""
from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import quote


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
