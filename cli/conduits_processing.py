"""
Conduit Pack v1: UI-safe conduits for processing artifacts (derived tables only).

Sources:
  - <processing_dir>/video/scene_manifest.json
  - <processing_dir>/temporal_index.json

This module strips:
  - absolute paths
  - raw transcripts / transcript segments
  - other large JSON blobs not needed for UI-safe indexing
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .media_refs import is_video_id_hash, tokenize_processing_path


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scene_manifest_public (
  video_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  scene_index INTEGER,
  start REAL,
  end REAL,
  duration REAL,
  frame_count INTEGER,
  has_audio INTEGER NOT NULL,
  has_transcript INTEGER NOT NULL,
  has_frame_text INTEGER NOT NULL,
  has_ocr_text INTEGER NOT NULL,
  has_caption INTEGER NOT NULL,
  clip_id TEXT,
  dino_id TEXT,
  media_refs_json TEXT NOT NULL,
  PRIMARY KEY (video_id, scene_id)
);
CREATE INDEX IF NOT EXISTS idx_smp_video ON scene_manifest_public(video_id);
CREATE INDEX IF NOT EXISTS idx_smp_scene ON scene_manifest_public(scene_id);

CREATE TABLE IF NOT EXISTS temporal_index_public (
  video_id TEXT PRIMARY KEY,
  version INTEGER,
  total_duration REAL,
  total_scenes INTEGER,
  total_entities INTEGER,
  unique_entities INTEGER,
  has_audio INTEGER,
  has_transcripts INTEGER,
  has_visual_embeddings INTEGER,
  phase5_complete INTEGER,
  phase6_complete INTEGER,
  phase6_harmonized INTEGER,
  segments_count INTEGER
);

CREATE TABLE IF NOT EXISTS temporal_segments_public (
  video_id TEXT NOT NULL,
  segment_index INTEGER NOT NULL,
  scene_id TEXT,
  start REAL,
  end REAL,
  duration REAL,
  frame_count INTEGER,
  has_audio INTEGER,
  has_transcript INTEGER,
  has_visual_embeddings INTEGER,
  keyword_count INTEGER,
  entity_count INTEGER,
  speaker_count INTEGER,
  clip_id TEXT,
  dino_id TEXT,
  representative_frame_ref TEXT,
  PRIMARY KEY (video_id, segment_index)
);
CREATE INDEX IF NOT EXISTS idx_tsp_video ON temporal_segments_public(video_id);
CREATE INDEX IF NOT EXISTS idx_tsp_scene ON temporal_segments_public(scene_id);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _safe_bool(val: Any) -> int:
    return 1 if bool(val) else 0


def _safe_num(val: Any) -> Optional[float]:
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _safe_int(val: Any) -> Optional[int]:
    if isinstance(val, int):
        return int(val)
    if isinstance(val, float) and val.is_integer():
        return int(val)
    return None


def _safe_str(val: Any) -> Optional[str]:
    if not isinstance(val, str):
        return None
    s = val.strip()
    return s or None


def _has_text(val: Any) -> bool:
    return isinstance(val, str) and bool(val.strip())


@dataclass
class BuildStats:
    videos_seen: int = 0
    scene_rows: int = 0
    temporal_rows: int = 0
    temporal_segment_rows: int = 0


def build_all(conn: sqlite3.Connection, *, processing_root: str) -> BuildStats:
    stats = BuildStats()
    if not isinstance(processing_root, str) or not processing_root.strip():
        return stats
    root = os.path.normpath(processing_root)
    if not os.path.isdir(root):
        return stats

    # Derived tables only: remove any historical rows keyed by non-hash video IDs to avoid PII-ish folder names.
    try:
        with conn:
            conn.execute(
                "DELETE FROM scene_manifest_public WHERE NOT (length(video_id)=64 AND video_id GLOB '[0-9A-Fa-f]*')"
            )
            conn.execute(
                "DELETE FROM temporal_index_public WHERE NOT (length(video_id)=64 AND video_id GLOB '[0-9A-Fa-f]*')"
            )
            conn.execute(
                "DELETE FROM temporal_segments_public WHERE NOT (length(video_id)=64 AND video_id GLOB '[0-9A-Fa-f]*')"
            )
    except Exception:
        pass

    scenes_out: List[Tuple[Any, ...]] = []
    temporal_out: List[Tuple[Any, ...]] = []
    segs_out: List[Tuple[Any, ...]] = []

    try:
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            stats.videos_seen += 1
            manifest_path = os.path.join(entry.path, "video", "scene_manifest.json")
            temporal_path = os.path.join(entry.path, "temporal_index.json")

            canonical_video_id: Optional[str] = None
            if os.path.isfile(manifest_path):
                data = _read_json(manifest_path)
                if isinstance(data, dict):
                    vid = _safe_str(data.get("video_id"))
                    canonical_video_id = vid if is_video_id_hash(vid) else None
                    scenes_out.extend(
                        scene_manifest_public_adapter(
                            data,
                            manifest_path=manifest_path,
                            processing_root=root,
                            video_id_override=canonical_video_id,
                        )
                    )

            if os.path.isfile(temporal_path):
                data = _read_json(temporal_path)
                if isinstance(data, dict):
                    v_row, seg_rows = temporal_index_public_adapter(
                        data,
                        temporal_path=temporal_path,
                        processing_root=root,
                        video_id_override=canonical_video_id,
                    )
                    if v_row is not None:
                        temporal_out.append(v_row)
                    if seg_rows:
                        segs_out.extend(seg_rows)
    except Exception:
        pass

    with conn:
        if scenes_out:
            conn.executemany(
                """
                INSERT INTO scene_manifest_public(
                  video_id, scene_id, scene_index, start, end, duration, frame_count,
                  has_audio, has_transcript, has_frame_text, has_ocr_text, has_caption,
                  clip_id, dino_id, media_refs_json
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(video_id, scene_id) DO UPDATE SET
                  scene_index = excluded.scene_index,
                  start = excluded.start,
                  end = excluded.end,
                  duration = excluded.duration,
                  frame_count = excluded.frame_count,
                  has_audio = excluded.has_audio,
                  has_transcript = excluded.has_transcript,
                  has_frame_text = excluded.has_frame_text,
                  has_ocr_text = excluded.has_ocr_text,
                  has_caption = excluded.has_caption,
                  clip_id = excluded.clip_id,
                  dino_id = excluded.dino_id,
                  media_refs_json = excluded.media_refs_json
                """,
                scenes_out,
            )

        if temporal_out:
            conn.executemany(
                """
                INSERT INTO temporal_index_public(
                  video_id, version, total_duration, total_scenes, total_entities, unique_entities,
                  has_audio, has_transcripts, has_visual_embeddings,
                  phase5_complete, phase6_complete, phase6_harmonized,
                  segments_count
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(video_id) DO UPDATE SET
                  version = excluded.version,
                  total_duration = excluded.total_duration,
                  total_scenes = excluded.total_scenes,
                  total_entities = excluded.total_entities,
                  unique_entities = excluded.unique_entities,
                  has_audio = excluded.has_audio,
                  has_transcripts = excluded.has_transcripts,
                  has_visual_embeddings = excluded.has_visual_embeddings,
                  phase5_complete = excluded.phase5_complete,
                  phase6_complete = excluded.phase6_complete,
                  phase6_harmonized = excluded.phase6_harmonized,
                  segments_count = excluded.segments_count
                """,
                temporal_out,
            )

        if segs_out:
            conn.executemany(
                """
                INSERT INTO temporal_segments_public(
                  video_id, segment_index, scene_id, start, end, duration, frame_count,
                  has_audio, has_transcript, has_visual_embeddings,
                  keyword_count, entity_count, speaker_count,
                  clip_id, dino_id, representative_frame_ref
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(video_id, segment_index) DO UPDATE SET
                  scene_id = excluded.scene_id,
                  start = excluded.start,
                  end = excluded.end,
                  duration = excluded.duration,
                  frame_count = excluded.frame_count,
                  has_audio = excluded.has_audio,
                  has_transcript = excluded.has_transcript,
                  has_visual_embeddings = excluded.has_visual_embeddings,
                  keyword_count = excluded.keyword_count,
                  entity_count = excluded.entity_count,
                  speaker_count = excluded.speaker_count,
                  clip_id = excluded.clip_id,
                  dino_id = excluded.dino_id,
                  representative_frame_ref = excluded.representative_frame_ref
                """,
                segs_out,
            )

    stats.scene_rows = len(scenes_out)
    stats.temporal_rows = len(temporal_out)
    stats.temporal_segment_rows = len(segs_out)
    return stats


def scene_manifest_public_adapter(
    data: Dict[str, Any],
    *,
    manifest_path: str,
    processing_root: str,
    video_id_override: Optional[str] = None,
) -> List[Tuple[Any, ...]]:
    """
    Adapter: scene_manifest.json -> whitelisted, path-sanitized per-scene rows.
    """

    video_id = _safe_str(video_id_override) if is_video_id_hash(video_id_override) else _safe_str(data.get("video_id"))
    if not is_video_id_hash(video_id):
        return []

    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        return []

    out: List[Tuple[Any, ...]] = []
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        scene_id = _safe_str(sc.get("scene_id"))
        if not scene_id:
            continue

        audio = sc.get("audio") if isinstance(sc.get("audio"), dict) else {}
        keyframe = sc.get("keyframe") if isinstance(sc.get("keyframe"), dict) else {}

        has_audio = bool(audio)
        has_transcript = False
        if isinstance(audio, dict):
            for k in ("transcript", "speaker_transcript", "full_text", "full_transcript"):
                if _has_text(audio.get(k)):
                    has_transcript = True
                    break
            if not has_transcript and isinstance(audio.get("speaker_segments"), list) and audio.get("speaker_segments"):
                has_transcript = True

        has_frame_text = _has_text(keyframe.get("frame_text"))
        has_ocr_text = _has_text(keyframe.get("ocr_text"))
        has_caption = _has_text(keyframe.get("caption"))

        # Media refs: always include manifest token; optionally include a single keyframe token.
        refs: List[Dict[str, str]] = [{"kind": "manifest", "rel": f"{video_id}/video/scene_manifest.json"}]
        rep = _safe_str(sc.get("representative_frame"))
        if rep:
            rel = tokenize_processing_path(raw_path=rep, processing_root=processing_root, video_id=video_id)
            if rel:
                refs.append({"kind": "keyframe", "rel": rel})
        if len(refs) == 1:
            frame_paths = sc.get("frame_paths")
            if isinstance(frame_paths, list):
                for fp in frame_paths:
                    fp_s = _safe_str(fp)
                    if not fp_s:
                        continue
                    rel = tokenize_processing_path(raw_path=fp_s, processing_root=processing_root, video_id=video_id)
                    if rel:
                        refs.append({"kind": "keyframe", "rel": rel})
                        break

        # Optional audio ref (only if under processing root).
        audio_path = _safe_str(audio.get("path")) if isinstance(audio, dict) else None
        if audio_path:
            rel = tokenize_processing_path(raw_path=audio_path, processing_root=processing_root, video_id=video_id)
            if rel:
                refs.append({"kind": "audio", "rel": rel})

        # De-dupe in stable order.
        seen = set()
        uniq: List[Dict[str, str]] = []
        for r in refs:
            kind = r.get("kind")
            rel = r.get("rel")
            if not (isinstance(kind, str) and kind.strip() and isinstance(rel, str) and rel.strip()):
                continue
            key = (kind.strip(), rel.strip())
            if key in seen:
                continue
            seen.add(key)
            uniq.append({"kind": kind.strip(), "rel": rel.strip()})

        out.append(
            (
                video_id,
                scene_id,
                _safe_int(sc.get("index")),
                _safe_num(sc.get("start")),
                _safe_num(sc.get("end")),
                _safe_num(sc.get("duration")),
                _safe_int(sc.get("frame_count")),
                _safe_bool(has_audio),
                _safe_bool(has_transcript),
                _safe_bool(has_frame_text),
                _safe_bool(has_ocr_text),
                _safe_bool(has_caption),
                _safe_str(sc.get("clip_id")),
                _safe_str(sc.get("dino_id")),
                json.dumps(uniq, ensure_ascii=False),
            )
        )
    return out


def temporal_index_public_adapter(
    data: Dict[str, Any],
    *,
    temporal_path: str,
    processing_root: str,
    video_id_override: Optional[str] = None,
) -> Tuple[Optional[Tuple[Any, ...]], List[Tuple[Any, ...]]]:
    """
    Adapter: temporal_index.json -> whitelisted, path-sanitized video row + per-segment rows.
    """

    video_id = _safe_str(video_id_override) if is_video_id_hash(video_id_override) else _safe_str(data.get("video_id"))
    if not is_video_id_hash(video_id):
        return None, []

    segments = data.get("segments")
    seg_rows: List[Tuple[Any, ...]] = []
    if isinstance(segments, list):
        for i, seg in enumerate(segments):
            if not isinstance(seg, dict):
                continue
            rep = _safe_str(seg.get("representative_frame"))
            rep_ref = tokenize_processing_path(raw_path=rep, processing_root=processing_root, video_id=video_id) if rep else None
            keywords = seg.get("keywords")
            entities = seg.get("entities")
            speaker_ids = seg.get("speaker_ids")
            seg_rows.append(
                (
                    video_id,
                    int(i),
                    _safe_str(seg.get("scene_id")),
                    _safe_num(seg.get("start")),
                    _safe_num(seg.get("end")),
                    _safe_num(seg.get("duration")),
                    _safe_int(seg.get("frame_count")),
                    _safe_bool(seg.get("has_audio")),
                    _safe_bool(seg.get("has_transcript")),
                    _safe_bool(seg.get("has_visual_embeddings")),
                    int(len(keywords)) if isinstance(keywords, list) else 0,
                    int(len(entities)) if isinstance(entities, list) else 0,
                    int(len(speaker_ids)) if isinstance(speaker_ids, list) else 0,
                    _safe_str(seg.get("clip_id")),
                    _safe_str(seg.get("dino_id")),
                    rep_ref,
                )
            )

    video_row = (
        video_id,
        _safe_int(data.get("version")),
        _safe_num(data.get("total_duration")),
        _safe_int(data.get("total_scenes")),
        _safe_int(data.get("total_entities")),
        _safe_int(data.get("unique_entities")),
        _safe_bool(data.get("has_audio")) if "has_audio" in data else None,
        _safe_bool(data.get("has_transcripts")) if "has_transcripts" in data else None,
        _safe_bool(data.get("has_visual_embeddings")) if "has_visual_embeddings" in data else None,
        _safe_bool(data.get("phase5_complete")) if "phase5_complete" in data else None,
        _safe_bool(data.get("phase6_complete")) if "phase6_complete" in data else None,
        _safe_bool(data.get("phase6_harmonized")) if "phase6_harmonized" in data else None,
        int(len(segments)) if isinstance(segments, list) else 0,
    )
    return video_row, seg_rows
