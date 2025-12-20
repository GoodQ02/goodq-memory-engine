"""
Conduit Pack v1: UI-safe conduits for knowledge_graph.db (derived tables only).

This module must not expose:
  - absolute filesystem paths (e.g., media_nodes.media_path)
  - raw transcript snippets or other free-form context blobs
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kg_entity_index_public (
  node_id TEXT PRIMARY KEY,
  node_type TEXT,
  name TEXT,
  first_seen REAL,
  last_seen REAL,
  occurrence_count INTEGER,
  created_at TEXT,
  has_properties INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_keip_type ON kg_entity_index_public(node_type);
CREATE INDEX IF NOT EXISTS idx_keip_name ON kg_entity_index_public(name);

CREATE TABLE IF NOT EXISTS kg_edge_summary_public (
  edge_type TEXT PRIMARY KEY,
  edge_count INTEGER NOT NULL,
  distinct_sources INTEGER NOT NULL,
  distinct_targets INTEGER NOT NULL,
  avg_weight REAL,
  min_weight REAL,
  max_weight REAL
);

CREATE TABLE IF NOT EXISTS entity_timeline_public (
  node_id TEXT NOT NULL,
  media_id INTEGER NOT NULL,
  scene_id TEXT,
  media_type TEXT,
  timestamp_start REAL,
  timestamp_end REAL,
  confidence REAL,
  PRIMARY KEY (node_id, media_id)
);
CREATE INDEX IF NOT EXISTS idx_etp_node ON entity_timeline_public(node_id);
CREATE INDEX IF NOT EXISTS idx_etp_scene ON entity_timeline_public(scene_id);

CREATE TABLE IF NOT EXISTS entity_scene_mentions_public (
  node_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  mention_count INTEGER NOT NULL,
  confidence_avg REAL,
  confidence_min REAL,
  confidence_max REAL,
  first_ts REAL,
  last_ts REAL,
  PRIMARY KEY (node_id, scene_id)
);
CREATE INDEX IF NOT EXISTS idx_esmp_node ON entity_scene_mentions_public(node_id);
CREATE INDEX IF NOT EXISTS idx_esmp_scene ON entity_scene_mentions_public(scene_id);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)).fetchone()
    return row is not None


@dataclass
class BuildStats:
    entities: int = 0
    edge_types: int = 0
    timeline_rows: int = 0
    mention_rows: int = 0


def build_all(conn: sqlite3.Connection) -> BuildStats:
    stats = BuildStats()
    if _table_exists(conn, "nodes"):
        stats.entities = _build_entity_index(conn)
    if _table_exists(conn, "edges"):
        stats.edge_types = _build_edge_summary(conn)
    if _table_exists(conn, "node_media") and _table_exists(conn, "media_nodes"):
        stats.timeline_rows = _build_entity_timeline(conn)
        stats.mention_rows = _build_entity_scene_mentions(conn)
    return stats


def _build_entity_index(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT id, node_type, name, first_seen, last_seen, occurrence_count, created_at, properties FROM nodes"
    ).fetchall()
    out: List[Tuple[Any, ...]] = []
    for node_id, node_type, name, first_seen, last_seen, occ, created_at, props in rows:
        node_id_s = str(node_id) if node_id is not None else None
        if not isinstance(node_id_s, str) or not node_id_s.strip():
            continue
        has_props = 0
        if isinstance(props, str) and props.strip() and props.strip() not in ("{}", "[]", "null"):
            try:
                parsed = json.loads(props)
                has_props = 1 if parsed else 0
            except Exception:
                has_props = 1
        out.append(
            (
                node_id_s.strip(),
                node_type if isinstance(node_type, str) and node_type.strip() else None,
                name if isinstance(name, str) and name.strip() else None,
                float(first_seen) if isinstance(first_seen, (int, float)) else None,
                float(last_seen) if isinstance(last_seen, (int, float)) else None,
                int(occ or 0) if isinstance(occ, int) else None,
                created_at if isinstance(created_at, str) and created_at.strip() else None,
                int(has_props),
            )
        )
    with conn:
        conn.executemany(
            """
            INSERT INTO kg_entity_index_public(
              node_id, node_type, name, first_seen, last_seen, occurrence_count, created_at, has_properties
            )
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(node_id) DO UPDATE SET
              node_type = excluded.node_type,
              name = excluded.name,
              first_seen = excluded.first_seen,
              last_seen = excluded.last_seen,
              occurrence_count = excluded.occurrence_count,
              created_at = excluded.created_at,
              has_properties = excluded.has_properties
            """,
            out,
        )
    return len(out)


def _build_edge_summary(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT
          edge_type,
          COUNT(1) AS edge_count,
          COUNT(DISTINCT source_id) AS distinct_sources,
          COUNT(DISTINCT target_id) AS distinct_targets,
          AVG(weight) AS avg_weight,
          MIN(weight) AS min_weight,
          MAX(weight) AS max_weight
        FROM edges
        GROUP BY edge_type
        """
    ).fetchall()
    out: List[Tuple[Any, ...]] = []
    for edge_type, edge_count, ds, dt, avg_w, min_w, max_w in rows:
        if not isinstance(edge_type, str) or not edge_type.strip():
            continue
        out.append(
            (
                edge_type.strip(),
                int(edge_count or 0),
                int(ds or 0),
                int(dt or 0),
                float(avg_w) if isinstance(avg_w, (int, float)) else None,
                float(min_w) if isinstance(min_w, (int, float)) else None,
                float(max_w) if isinstance(max_w, (int, float)) else None,
            )
        )
    with conn:
        conn.executemany(
            """
            INSERT INTO kg_edge_summary_public(
              edge_type, edge_count, distinct_sources, distinct_targets, avg_weight, min_weight, max_weight
            )
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(edge_type) DO UPDATE SET
              edge_count = excluded.edge_count,
              distinct_sources = excluded.distinct_sources,
              distinct_targets = excluded.distinct_targets,
              avg_weight = excluded.avg_weight,
              min_weight = excluded.min_weight,
              max_weight = excluded.max_weight
            """,
            out,
        )
    return len(out)


def _build_entity_timeline(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT
          nm.node_id,
          nm.media_id,
          mn.scene_id,
          mn.media_type,
          mn.timestamp_start,
          mn.timestamp_end,
          nm.confidence
        FROM node_media nm
        JOIN media_nodes mn ON mn.id = nm.media_id
        """
    ).fetchall()
    out: List[Tuple[Any, ...]] = []
    for node_id, media_id, scene_id, media_type, ts_start, ts_end, conf in rows:
        node_id_s = str(node_id) if node_id is not None else None
        if not isinstance(node_id_s, str) or not node_id_s.strip():
            continue
        out.append(
            (
                node_id_s.strip(),
                int(media_id),
                scene_id if isinstance(scene_id, str) and scene_id.strip() else None,
                media_type if isinstance(media_type, str) and media_type.strip() else None,
                float(ts_start) if isinstance(ts_start, (int, float)) else None,
                float(ts_end) if isinstance(ts_end, (int, float)) else None,
                float(conf) if isinstance(conf, (int, float)) else None,
            )
        )
    with conn:
        conn.executemany(
            """
            INSERT INTO entity_timeline_public(
              node_id, media_id, scene_id, media_type, timestamp_start, timestamp_end, confidence
            )
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(node_id, media_id) DO UPDATE SET
              scene_id = excluded.scene_id,
              media_type = excluded.media_type,
              timestamp_start = excluded.timestamp_start,
              timestamp_end = excluded.timestamp_end,
              confidence = excluded.confidence
            """,
            out,
        )
    return len(out)


def _build_entity_scene_mentions(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT
          nm.node_id,
          mn.scene_id,
          COUNT(1) AS mention_count,
          AVG(nm.confidence) AS confidence_avg,
          MIN(nm.confidence) AS confidence_min,
          MAX(nm.confidence) AS confidence_max,
          MIN(mn.timestamp_start) AS first_ts,
          MAX(mn.timestamp_end) AS last_ts
        FROM node_media nm
        JOIN media_nodes mn ON mn.id = nm.media_id
        WHERE mn.scene_id IS NOT NULL AND mn.scene_id != ''
        GROUP BY nm.node_id, mn.scene_id
        """
    ).fetchall()
    out: List[Tuple[Any, ...]] = []
    for node_id, scene_id, mention_count, avg_c, min_c, max_c, first_ts, last_ts in rows:
        node_id_s = str(node_id) if node_id is not None else None
        if not isinstance(node_id_s, str) or not node_id_s.strip():
            continue
        if not isinstance(scene_id, str) or not scene_id.strip():
            continue
        out.append(
            (
                node_id_s.strip(),
                scene_id.strip(),
                int(mention_count or 0),
                float(avg_c) if isinstance(avg_c, (int, float)) else None,
                float(min_c) if isinstance(min_c, (int, float)) else None,
                float(max_c) if isinstance(max_c, (int, float)) else None,
                float(first_ts) if isinstance(first_ts, (int, float)) else None,
                float(last_ts) if isinstance(last_ts, (int, float)) else None,
            )
        )
    with conn:
        conn.executemany(
            """
            INSERT INTO entity_scene_mentions_public(
              node_id, scene_id, mention_count, confidence_avg, confidence_min, confidence_max, first_ts, last_ts
            )
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(node_id, scene_id) DO UPDATE SET
              mention_count = excluded.mention_count,
              confidence_avg = excluded.confidence_avg,
              confidence_min = excluded.confidence_min,
              confidence_max = excluded.confidence_max,
              first_ts = excluded.first_ts,
              last_ts = excluded.last_ts
            """,
            out,
        )
    return len(out)
