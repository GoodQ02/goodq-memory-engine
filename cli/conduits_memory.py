"""
Conduit Pack v1: UI-safe conduits for memory.db (derived tables only).

This module must not expose:
  - raw embeddings/vectors
  - absolute filesystem paths
  - raw transcripts
  - full summary content by default
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS segment_index_public (
  segment_id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  start REAL,
  end REAL,
  duration REAL,
  speaker TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_segpub_video ON segment_index_public(video_id);

CREATE TABLE IF NOT EXISTS scene_segment_alignment (
  video_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  overlap_start REAL,
  overlap_end REAL,
  overlap_seconds REAL,
  PRIMARY KEY (scene_id, segment_id)
);
CREATE INDEX IF NOT EXISTS idx_ssa_video ON scene_segment_alignment(video_id);
CREATE INDEX IF NOT EXISTS idx_ssa_scene ON scene_segment_alignment(scene_id);
CREATE INDEX IF NOT EXISTS idx_ssa_segment ON scene_segment_alignment(segment_id);

CREATE TABLE IF NOT EXISTS embedding_catalog_public (
  embedding_id TEXT PRIMARY KEY,
  scene_id TEXT,
  modality TEXT NOT NULL,
  created_at TEXT,
  faiss_id INTEGER,
  sentiment_label TEXT,
  sentiment_score REAL,
  has_emotions INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ecp_scene ON embedding_catalog_public(scene_id);
CREATE INDEX IF NOT EXISTS idx_ecp_modality ON embedding_catalog_public(modality);

CREATE TABLE IF NOT EXISTS summaries_public (
  summary_id TEXT PRIMARY KEY,
  summary_type TEXT,
  category TEXT,
  created_at TEXT,
  content_len INTEGER NOT NULL,
  content_sha256 TEXT,
  redacted_preview TEXT
);
CREATE INDEX IF NOT EXISTS idx_sp_type ON summaries_public(summary_type);
CREATE INDEX IF NOT EXISTS idx_sp_category ON summaries_public(category);

CREATE TABLE IF NOT EXISTS link_summary_public (
  relation TEXT PRIMARY KEY,
  link_count INTEGER NOT NULL,
  distinct_parents INTEGER NOT NULL,
  distinct_children INTEGER NOT NULL,
  first_timestamp TEXT,
  last_timestamp TEXT
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)).fetchone()
    return row is not None


def _truthy_env(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def summaries_preview_enabled(cfg: Optional[Dict[str, Any]] = None, *, default: bool = False) -> bool:
    if "GOODQ_SUMMARIES_PREVIEW" in os.environ:
        return _truthy_env("GOODQ_SUMMARIES_PREVIEW", default=default)
    if not isinstance(cfg, dict):
        return default
    ui = cfg.get("ui")
    if isinstance(ui, dict) and "summaries_preview" in ui:
        return bool(ui.get("summaries_preview"))
    obs = cfg.get("observability")
    if isinstance(obs, dict) and "summaries_preview" in obs:
        return bool(obs.get("summaries_preview"))
    return default


_ABS_PATH_RE = re.compile(r"([a-zA-Z]:[\\/][^\\s\"']+|/mnt/[a-zA-Z]/[^\\s\"']+)")


def _redact_paths(text: str) -> str:
    try:
        return _ABS_PATH_RE.sub("<PATH_REDACTED>", text)
    except Exception:
        return text


def _preview(text: str, *, limit: int = 220) -> str:
    s = " ".join(text.split())
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


@dataclass
class BuildStats:
    segment_rows: int = 0
    alignment_rows: int = 0
    embedding_rows: int = 0
    summaries_rows: int = 0
    link_rows: int = 0


def build_all(conn: sqlite3.Connection, *, cfg: Optional[Dict[str, Any]] = None) -> BuildStats:
    stats = BuildStats()

    if _table_exists(conn, "segments"):
        stats.segment_rows = _build_segment_index_public(conn)
        if _table_exists(conn, "scenes"):
            stats.alignment_rows = _build_scene_segment_alignment(conn)

    if _table_exists(conn, "embeddings"):
        stats.embedding_rows = _build_embedding_catalog_public(conn)

    if _table_exists(conn, "summaries"):
        stats.summaries_rows = _build_summaries_public(conn, cfg=cfg)

    if _table_exists(conn, "links"):
        stats.link_rows = _build_link_summary_public(conn)

    return stats


def _build_segment_index_public(conn: sqlite3.Connection) -> int:
    rows = conn.execute("SELECT id, video_hash, start, end, speaker, created_at FROM segments").fetchall()
    out: List[Tuple[Any, ...]] = []
    for seg_id, video_id, start, end, speaker, created_at in rows:
        dur = None
        try:
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                dur = float(end) - float(start)
        except Exception:
            dur = None
        out.append(
            (
                seg_id,
                video_id,
                float(start) if isinstance(start, (int, float)) else None,
                float(end) if isinstance(end, (int, float)) else None,
                dur,
                speaker if isinstance(speaker, str) and speaker.strip() else None,
                created_at if isinstance(created_at, str) and created_at.strip() else None,
            )
        )

    with conn:
        conn.executemany(
            """
            INSERT INTO segment_index_public(segment_id, video_id, start, end, duration, speaker, created_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(segment_id) DO UPDATE SET
              video_id = excluded.video_id,
              start = excluded.start,
              end = excluded.end,
              duration = excluded.duration,
              speaker = excluded.speaker,
              created_at = excluded.created_at
            """,
            out,
        )
    return len(out)


def _build_scene_segment_alignment(conn: sqlite3.Connection) -> int:
    scenes = conn.execute("SELECT id, video_hash, start, end FROM scenes").fetchall()
    segments = conn.execute("SELECT id, video_hash, start, end FROM segments").fetchall()

    scenes_by_video: Dict[str, List[Tuple[str, float, float]]] = {}
    for sid, vid, s, e in scenes:
        if not isinstance(vid, str) or not vid.strip():
            continue
        if not isinstance(s, (int, float)) or not isinstance(e, (int, float)):
            continue
        scenes_by_video.setdefault(vid, []).append((sid, float(s), float(e)))

    segs_by_video: Dict[str, List[Tuple[str, float, float]]] = {}
    for seg_id, vid, s, e in segments:
        if not isinstance(vid, str) or not vid.strip():
            continue
        if not isinstance(s, (int, float)) or not isinstance(e, (int, float)):
            continue
        segs_by_video.setdefault(vid, []).append((seg_id, float(s), float(e)))

    out: List[Tuple[Any, ...]] = []
    for vid, scs in scenes_by_video.items():
        segs = segs_by_video.get(vid) or []
        if not segs:
            continue
        for scene_id, sc_start, sc_end in scs:
            for seg_id, seg_start, seg_end in segs:
                if seg_end <= sc_start or seg_start >= sc_end:
                    continue
                ov_start = max(sc_start, seg_start)
                ov_end = min(sc_end, seg_end)
                ov_sec = ov_end - ov_start
                if ov_sec <= 0:
                    continue
                out.append((vid, scene_id, seg_id, ov_start, ov_end, ov_sec))

    with conn:
        conn.executemany(
            """
            INSERT INTO scene_segment_alignment(
              video_id, scene_id, segment_id, overlap_start, overlap_end, overlap_seconds
            )
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(scene_id, segment_id) DO UPDATE SET
              video_id = excluded.video_id,
              overlap_start = excluded.overlap_start,
              overlap_end = excluded.overlap_end,
              overlap_seconds = excluded.overlap_seconds
            """,
            out,
        )
    return len(out)


def _build_embedding_catalog_public(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT hash, scene_id, modality, created_at, faiss_id, sentiment_label, sentiment_score, emotions_json FROM embeddings"
    ).fetchall()
    out: List[Tuple[Any, ...]] = []
    for (embedding_id, scene_id, modality, created_at, faiss_id, sentiment_label, sentiment_score, emotions_json) in rows:
        has_emotions = 0
        if isinstance(emotions_json, str) and emotions_json.strip() and emotions_json.strip() not in ("{}", "[]", "null"):
            try:
                parsed = json.loads(emotions_json)
                has_emotions = 1 if parsed else 0
            except Exception:
                has_emotions = 1
        out.append(
            (
                embedding_id,
                scene_id if isinstance(scene_id, str) and scene_id.strip() else None,
                modality if isinstance(modality, str) and modality.strip() else "unknown",
                created_at if isinstance(created_at, str) and created_at.strip() else None,
                int(faiss_id) if isinstance(faiss_id, int) else None,
                sentiment_label if isinstance(sentiment_label, str) and sentiment_label.strip() else None,
                float(sentiment_score) if isinstance(sentiment_score, (int, float)) else None,
                int(has_emotions),
            )
        )

    with conn:
        conn.executemany(
            """
            INSERT INTO embedding_catalog_public(
              embedding_id, scene_id, modality, created_at, faiss_id, sentiment_label, sentiment_score, has_emotions
            )
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(embedding_id) DO UPDATE SET
              scene_id = excluded.scene_id,
              modality = excluded.modality,
              created_at = excluded.created_at,
              faiss_id = excluded.faiss_id,
              sentiment_label = excluded.sentiment_label,
              sentiment_score = excluded.sentiment_score,
              has_emotions = excluded.has_emotions
            """,
            out,
        )
    return len(out)


def _build_summaries_public(conn: sqlite3.Connection, *, cfg: Optional[Dict[str, Any]]) -> int:
    preview_enabled = summaries_preview_enabled(cfg, default=False)
    rows = conn.execute("SELECT id, summary_type, category, content, created_at FROM summaries").fetchall()
    out: List[Tuple[Any, ...]] = []
    for summary_id, summary_type, category, content, created_at in rows:
        content_s = content if isinstance(content, str) else ""
        sha = hashlib.sha256(content_s.encode("utf-8", errors="ignore")).hexdigest() if content_s else None
        redacted_preview = None
        if preview_enabled and content_s:
            redacted_preview = _preview(_redact_paths(content_s))
        out.append(
            (
                summary_id,
                summary_type if isinstance(summary_type, str) and summary_type.strip() else None,
                category if isinstance(category, str) and category.strip() else None,
                created_at if isinstance(created_at, str) and created_at.strip() else None,
                int(len(content_s)),
                sha,
                redacted_preview,
            )
        )

    with conn:
        conn.executemany(
            """
            INSERT INTO summaries_public(
              summary_id, summary_type, category, created_at, content_len, content_sha256, redacted_preview
            )
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(summary_id) DO UPDATE SET
              summary_type = excluded.summary_type,
              category = excluded.category,
              created_at = excluded.created_at,
              content_len = excluded.content_len,
              content_sha256 = excluded.content_sha256,
              redacted_preview = excluded.redacted_preview
            """,
            out,
        )
    return len(out)


def _build_link_summary_public(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT
          relation,
          COUNT(1) AS link_count,
          COUNT(DISTINCT parent_hash) AS distinct_parents,
          COUNT(DISTINCT child_hash) AS distinct_children,
          MIN(timestamp) AS first_timestamp,
          MAX(timestamp) AS last_timestamp
        FROM links
        GROUP BY relation
        """
    ).fetchall()

    out: List[Tuple[Any, ...]] = []
    for relation, link_count, distinct_parents, distinct_children, first_ts, last_ts in rows:
        if not isinstance(relation, str) or not relation.strip():
            continue
        out.append(
            (
                relation.strip(),
                int(link_count or 0),
                int(distinct_parents or 0),
                int(distinct_children or 0),
                first_ts if isinstance(first_ts, str) and first_ts.strip() else None,
                last_ts if isinstance(last_ts, str) and last_ts.strip() else None,
            )
        )

    with conn:
        conn.executemany(
            """
            INSERT INTO link_summary_public(
              relation, link_count, distinct_parents, distinct_children, first_timestamp, last_timestamp
            )
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(relation) DO UPDATE SET
              link_count = excluded.link_count,
              distinct_parents = excluded.distinct_parents,
              distinct_children = excluded.distinct_children,
              first_timestamp = excluded.first_timestamp,
              last_timestamp = excluded.last_timestamp
            """,
            out,
        )
    return len(out)

