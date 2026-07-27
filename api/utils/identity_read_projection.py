"""Read-only projections that bind identity artifacts to one epoch authority."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from api.utils.media_projection import frame_endpoint


_IDENTITY_ARTIFACTS = {
    "face_clusters": "face_clusters.json",
    "speaker_clusters": "speaker_clusters.json",
    "name_mentions": "name_mentions.json",
}


def identity_data_path(cfg: Mapping[str, Any]) -> Path:
    roster_path = (cfg.get("identity_search") or {}).get("roster_path")
    env_path = os.environ.get("GOODQ_IDENTITY_PATH")
    if roster_path:
        return Path(str(roster_path)).parent
    if env_path:
        path = Path(env_path)
        return path.parent if path.suffix.lower() in {".yaml", ".yml", ".json"} else path
    return Path(os.environ.get("GOODQ_DATA_ROOT", "L:/_DATA")) / "GoodQ_Data" / "identity"


def configured_epoch_id(cfg: Mapping[str, Any]) -> str | None:
    explicit = str(cfg.get("epoch_id") or "").strip()
    if explicit:
        return explicit
    db_path = str((cfg.get("paths") or {}).get("db_path") or "").strip()
    return Path(db_path).parent.name if db_path else None


def _artifact_epoch(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    epoch_id = payload.get("epoch_id") if isinstance(payload, dict) else None
    return str(epoch_id).strip() if epoch_id else None


def epoch_authority_projection(
    cfg: Mapping[str, Any],
    identity_root: Path | None = None,
) -> dict[str, Any]:
    root = identity_root or identity_data_path(cfg)
    configured = configured_epoch_id(cfg)
    artifact_epochs = {
        name: epoch
        for name, filename in _IDENTITY_ARTIFACTS.items()
        if (epoch := _artifact_epoch(root / filename))
    }
    distinct = sorted(set(artifact_epochs.values()))
    identity_epoch = distinct[0] if len(distinct) == 1 else None

    if len(artifact_epochs) != len(_IDENTITY_ARTIFACTS):
        state = "identity_artifacts_missing"
        message = "Identity artifacts are incomplete or do not declare an epoch."
    elif len(distinct) != 1:
        state = "identity_artifacts_conflict"
        message = "Identity artifacts declare conflicting epochs."
    elif not configured:
        state = "configured_epoch_missing"
        message = "The configured runtime does not declare an epoch."
    elif identity_epoch != configured:
        state = "epoch_mismatch"
        message = "Identity artifacts do not match the configured epoch."
    else:
        state = "ready"
        message = "Identity artifacts match the configured epoch."

    return {
        "configured_epoch_id": configured,
        "identity_epoch_id": identity_epoch,
        "identity_epoch_ids": artifact_epochs,
        "state": state,
        "ready": state == "ready",
        "message": message,
    }


def _epoch_root(cfg: Mapping[str, Any]) -> Path | None:
    db_path = str((cfg.get("paths") or {}).get("db_path") or "").strip()
    return Path(db_path).parent if db_path else None


def _context_frame(epoch_root: Path, frame_id: int) -> tuple[Path, float] | None:
    ledger = epoch_root / "ucf" / "ucf_ledger.db"
    if not ledger.is_file():
        return None
    try:
        uri = f"{ledger.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            row = conn.execute(
                "SELECT raw_ref, t_start FROM context_frames WHERE frame_id = ? LIMIT 1",
                (frame_id,),
            ).fetchone()
    except (OSError, sqlite3.Error):
        return None
    if not row or not row[0]:
        return None
    try:
        return Path(str(row[0])), float(row[1])
    except (TypeError, ValueError):
        return None


def _representative_frame(
    epoch_root: Path,
    raw_ref: Path,
    timestamp: float,
) -> tuple[str, Path] | None:
    processing_root = (epoch_root / "processing").resolve()
    try:
        relative = raw_ref.resolve().relative_to(processing_root)
    except (OSError, ValueError):
        return None
    if not relative.parts:
        return None
    video_id = relative.parts[0]
    index_path = processing_root / video_id / "temporal_index.json"
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    segments = payload.get("segments", []) if isinstance(payload, dict) else payload
    if not isinstance(segments, list):
        return None
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        try:
            contains = float(segment["start"]) <= timestamp <= float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        frame = segment.get("representative_frame")
        if not contains or not frame:
            continue
        frame_path = Path(str(frame))
        try:
            frame_path.resolve().relative_to(processing_root)
        except (OSError, ValueError):
            return None
        if frame_path.is_file():
            return video_id, frame_path
    return None


def _face_evidence(raw_ref: Path, face_id: str, face_index: int) -> dict[str, Any]:
    try:
        faces = json.loads(raw_ref.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(faces, list) or face_index < 0 or face_index >= len(faces):
        return {}
    face = faces[face_index]
    bbox = face.get("bbox") if isinstance(face, dict) else None
    return {
        "target_face_id": face_id,
        "target_face_index": face_index,
        "source_face_count": len(faces),
        "bbox": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
    }


def project_face_cluster_images(
    data: Mapping[str, Any],
    cfg: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    projected = dict(data)
    clusters = [dict(cluster) for cluster in data.get("clusters", []) if isinstance(cluster, dict)]
    projected["clusters"] = clusters
    if not authority.get("ready"):
        return projected
    epoch_root = _epoch_root(cfg)
    if epoch_root is None:
        return projected
    for cluster in clusters:
        face_ids = cluster.get("face_ids")
        if not isinstance(face_ids, list) or not face_ids:
            continue
        face_id = str(face_ids[0])
        try:
            raw_frame_id, raw_face_index = face_id.split("_", 1)
            frame_id = int(raw_frame_id)
            face_index = int(raw_face_index)
        except (TypeError, ValueError):
            continue
        context = _context_frame(epoch_root, frame_id)
        if context is None:
            continue
        representative = _representative_frame(epoch_root, *context)
        if representative is None:
            continue
        endpoint = frame_endpoint(representative[0], str(representative[1]))
        if endpoint:
            cluster["representative_frames"] = [
                {
                    "frame_url": endpoint,
                    **_face_evidence(context[0], face_id, face_index),
                }
            ]
    return projected
