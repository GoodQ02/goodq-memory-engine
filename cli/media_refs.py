"""
GoodQ UI-safe media reference tokens (local-only).

Token schema (v1):
  media_ref := {"kind": <string>, "rel": "<video_id>/<inner_rel_path>"}

Where:
  - video_id is the stable 64-hex video hash (NOT the human processing directory name).
  - inner_rel_path is a path *inside* the per-video processing directory (e.g. "video/scene_manifest.json").

This avoids leaking absolute paths or processing directory names into UI-safe conduits.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple


MEDIA_REF_SCHEMA_VERSION = 1

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

# Cache: processing_root -> {video_id -> absolute_processing_dir}
_VIDEO_DIR_CACHE: Dict[str, Dict[str, str]] = {}


def is_video_id_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX64_RE.fullmatch(value.strip()))


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _wsl_mount_path(win_path: str) -> Optional[str]:
    m = re.match(r"^([a-zA-Z]):[\\/](.*)$", win_path)
    if not m:
        return None
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def tokenize_processing_path(*, raw_path: str, processing_root: str, video_id: str) -> Optional[str]:
    """
    Convert an absolute on-disk path under cfg['paths']['processing'] into a UI-safe token rel:
      "<video_id>/<inner_rel_path>"

    Important: drops the *processing_dir* name component to avoid PII leakage.
    """

    if not (isinstance(raw_path, str) and raw_path.strip()):
        return None
    if not (isinstance(processing_root, str) and processing_root.strip()):
        return None
    if not (isinstance(video_id, str) and video_id.strip()):
        return None

    raw = raw_path.strip()
    root_win = os.path.normpath(processing_root)
    raw_win = os.path.normpath(raw)

    def under_root_win() -> Optional[str]:
        try:
            prefix = root_win.lower() + os.sep
            if raw_win.lower().startswith(prefix):
                rel = os.path.relpath(raw_win, root_win)
                rel_posix = _posix(rel)
                parts = [p for p in rel_posix.split("/") if p]
                if len(parts) < 2:
                    return None
                inner = "/".join(parts[1:])  # drop processing_dir component (may include PII)
                return f"{video_id}/{inner}"
        except Exception:
            return None
        return None

    out = under_root_win()
    if out:
        return out

    # Best-effort WSL path support: /mnt/<drive>/... mirrors Windows drive roots.
    root_wsl = _wsl_mount_path(root_win)
    if isinstance(root_wsl, str) and root_wsl:
        raw_posix = raw.replace("\\", "/")
        root_prefix = root_wsl.rstrip("/") + "/"
        if raw_posix.startswith(root_prefix):
            rel_posix = raw_posix[len(root_prefix) :]
            parts = [p for p in rel_posix.split("/") if p]
            if len(parts) < 2:
                return None
            inner = "/".join(parts[1:])
            return f"{video_id}/{inner}"

    return None


def _parse_rel(rel: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(rel, str):
        return None
    s = rel.strip().replace("\\", "/")
    if not s or "/" not in s:
        return None
    video_id, inner = s.split("/", 1)
    if not is_video_id_hash(video_id):
        return None
    inner = inner.strip().lstrip("/")
    if not inner or ".." in inner.split("/"):
        return None
    return video_id.lower(), inner


def _discover_processing_dirs(processing_root: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not isinstance(processing_root, str) or not processing_root.strip():
        return mapping
    root = os.path.normpath(processing_root)
    if not os.path.isdir(root):
        return mapping
    try:
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            manifest = os.path.join(entry.path, "video", "scene_manifest.json")
            if not os.path.isfile(manifest):
                continue
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                vid = data.get("video_id")
                if is_video_id_hash(vid):
                    mapping[str(vid).lower()] = entry.path
            except Exception:
                continue
    except Exception:
        return mapping
    return mapping


def resolve_media_ref(cfg: Dict[str, Any], rel: str) -> Optional[str]:
    """
    Resolve a UI-safe media_ref rel token into a local absolute path (best-effort).

    This is local-only and should never be used to populate UI-safe tables.
    """

    parsed = _parse_rel(rel)
    if not parsed:
        return None
    video_id, inner = parsed

    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    processing_root = paths.get("processing")
    if not isinstance(processing_root, str) or not processing_root.strip():
        return None
    processing_root = os.path.normpath(processing_root)

    mapping = _VIDEO_DIR_CACHE.get(processing_root)
    if mapping is None:
        mapping = _discover_processing_dirs(processing_root)
        _VIDEO_DIR_CACHE[processing_root] = mapping

    processing_dir = mapping.get(video_id)
    if not isinstance(processing_dir, str) or not processing_dir.strip():
        return None

    abs_path = os.path.normpath(os.path.join(processing_dir, inner.replace("/", os.sep)))
    try:
        prefix = os.path.normpath(processing_dir).lower() + os.sep
        if not abs_path.lower().startswith(prefix):
            return None
    except Exception:
        return None
    return abs_path

