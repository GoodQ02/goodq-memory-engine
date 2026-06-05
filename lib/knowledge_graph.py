from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    if value is None:
        return "{}"
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return "{}"


def _json_loads(value: Any) -> Dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class KnowledgeGraph:
    """SQLite-backed lightweight knowledge graph store."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def __enter__(self) -> "KnowledgeGraph":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if getattr(self, "conn", None) is not None:
            self.conn.close()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA busy_timeout=5000;

            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                first_seen REAL,
                last_seen REAL,
                created_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_type_name
                ON nodes (node_type, name);

            CREATE TABLE IF NOT EXISTS media_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_type TEXT NOT NULL,
                media_path TEXT NOT NULL,
                scene_id TEXT,
                timestamp_start REAL,
                timestamp_end REAL,
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_media_scene ON media_nodes(scene_id);
            CREATE INDEX IF NOT EXISTS idx_media_path ON media_nodes(media_path);

            CREATE TABLE IF NOT EXISTS node_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                context TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(node_id) REFERENCES nodes(id),
                FOREIGN KEY(media_id) REFERENCES media_nodes(id)
            );

            CREATE INDEX IF NOT EXISTS idx_node_media_node ON node_media(node_id);
            CREATE INDEX IF NOT EXISTS idx_node_media_media ON node_media(media_id);

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES nodes(id),
                FOREIGN KEY(target_id) REFERENCES nodes(id)
            );

            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                duration REAL,
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

            CREATE TABLE IF NOT EXISTS event_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                node_id INTEGER NOT NULL,
                role TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id),
                FOREIGN KEY(node_id) REFERENCES nodes(id)
            );

            CREATE INDEX IF NOT EXISTS idx_event_nodes_event ON event_nodes(event_id);
            CREATE INDEX IF NOT EXISTS idx_event_nodes_node ON event_nodes(node_id);
            """
        )
        self.conn.commit()

    def add_node(
        self,
        node_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> int:
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT id, properties, occurrence_count, first_seen, last_seen "
            "FROM nodes WHERE node_type = ? AND name = ?",
            (node_type, name),
        ).fetchone()

        incoming_props = dict(properties or {})
        ts = float(timestamp) if timestamp is not None else None

        if row is not None:
            existing_props = _json_loads(row["properties"])
            existing_props.update(incoming_props)
            first_seen = row["first_seen"]
            last_seen = row["last_seen"]
            if ts is not None:
                if first_seen is None or ts < float(first_seen):
                    first_seen = ts
                if last_seen is None or ts > float(last_seen):
                    last_seen = ts

            cur.execute(
                "UPDATE nodes SET properties = ?, occurrence_count = ?, first_seen = ?, last_seen = ? "
                "WHERE id = ?",
                (
                    _json_dumps(existing_props),
                    int(row["occurrence_count"] or 0) + 1,
                    first_seen,
                    last_seen,
                    int(row["id"]),
                ),
            )
            self.conn.commit()
            return int(row["id"])

        cur.execute(
            "INSERT INTO nodes (node_type, name, properties, occurrence_count, first_seen, last_seen, created_at) "
            "VALUES (?, ?, ?, 1, ?, ?, ?)",
            (node_type, name, _json_dumps(incoming_props), ts, ts, _utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_media_node(
        self,
        media_type: str,
        media_path: str,
        scene_id: Optional[str] = None,
        timestamp_start: Optional[float] = None,
        timestamp_end: Optional[float] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        cur = self.conn.cursor()

        row = None
        if scene_id:
            row = cur.execute(
                "SELECT id, properties FROM media_nodes WHERE scene_id = ? AND media_path = ?",
                (scene_id, media_path),
            ).fetchone()

        if row is not None:
            existing_props = _json_loads(row["properties"])
            existing_props.update(dict(properties or {}))
            cur.execute(
                "UPDATE media_nodes SET media_type = ?, timestamp_start = ?, timestamp_end = ?, properties = ? "
                "WHERE id = ?",
                (
                    media_type,
                    timestamp_start,
                    timestamp_end,
                    _json_dumps(existing_props),
                    int(row["id"]),
                ),
            )
            self.conn.commit()
            return int(row["id"])

        cur.execute(
            "INSERT INTO media_nodes (media_type, media_path, scene_id, timestamp_start, timestamp_end, properties, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                media_type,
                media_path,
                scene_id,
                timestamp_start,
                timestamp_end,
                _json_dumps(dict(properties or {})),
                _utc_now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def link_node_to_media(
        self,
        node_id: int,
        media_id: int,
        confidence: float = 1.0,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO node_media (node_id, media_id, confidence, context, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(node_id), int(media_id), float(confidence), _json_dumps(dict(context or {})), _utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_edge(
        self,
        source_id: int,
        target_id: int,
        edge_type: str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT id, weight, properties FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = ?",
            (int(source_id), int(target_id), edge_type),
        ).fetchone()

        if row is not None:
            merged_props = _json_loads(row["properties"])
            merged_props.update(dict(properties or {}))
            cur.execute(
                "UPDATE edges SET weight = ?, properties = ? WHERE id = ?",
                (float(weight), _json_dumps(merged_props), int(row["id"])),
            )
            self.conn.commit()
            return int(row["id"])

        cur.execute(
            "INSERT INTO edges (source_id, target_id, edge_type, weight, properties, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                int(source_id),
                int(target_id),
                edge_type,
                float(weight),
                _json_dumps(dict(properties or {})),
                _utc_now_iso(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_temporal_event(
        self,
        event_type: str,
        timestamp: float,
        duration: Optional[float] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO events (event_type, timestamp, duration, properties, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_type, float(timestamp), duration, _json_dumps(dict(properties or {})), _utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def link_event_to_node(self, event_id: int, node_id: int, role: Optional[str] = None) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO event_nodes (event_id, node_id, role, created_at) VALUES (?, ?, ?, ?)",
            (int(event_id), int(node_id), role, _utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_statistics(self) -> Dict[str, Any]:
        cur = self.conn.cursor()

        total_nodes = int(cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
        total_edges = int(cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0])
        total_media = int(cur.execute("SELECT COUNT(*) FROM media_nodes").fetchone()[0])
        total_events = int(cur.execute("SELECT COUNT(*) FROM events").fetchone()[0])

        nodes_by_type = {
            str(row["node_type"]): int(row["cnt"])
            for row in cur.execute(
                "SELECT node_type, COUNT(*) AS cnt FROM nodes GROUP BY node_type ORDER BY cnt DESC"
            ).fetchall()
        }
        edges_by_type = {
            str(row["edge_type"]): int(row["cnt"])
            for row in cur.execute(
                "SELECT edge_type, COUNT(*) AS cnt FROM edges GROUP BY edge_type ORDER BY cnt DESC"
            ).fetchall()
        }

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_media": total_media,
            "total_events": total_events,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type,
        }

    def get_node_media(self, node_id: int) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        rows = cur.execute(
            """
            SELECT m.id, m.media_type, m.media_path, m.scene_id, m.timestamp_start, m.timestamp_end,
                   nm.confidence, nm.context
            FROM node_media nm
            JOIN media_nodes m ON m.id = nm.media_id
            WHERE nm.node_id = ?
            ORDER BY m.timestamp_start ASC
            """,
            (int(node_id),),
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "media_id": int(row["id"]),
                    "media_type": row["media_type"],
                    "media_path": row["media_path"],
                    "scene_id": row["scene_id"],
                    "timestamp_start": row["timestamp_start"],
                    "timestamp_end": row["timestamp_end"],
                    "confidence": row["confidence"],
                    "context": _json_loads(row["context"]),
                }
            )
        return out

    def find_related_nodes(
        self,
        node_id: int,
        edge_type: Optional[str] = None,
        max_depth: int = 1,
    ) -> List[Dict[str, Any]]:
        if max_depth < 1:
            return []

        cur = self.conn.cursor()
        queue: List[tuple[int, int]] = [(int(node_id), 0)]
        seen = {int(node_id)}
        out: List[Dict[str, Any]] = []

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            if edge_type:
                rows = cur.execute(
                    """
                    SELECT e.source_id, e.target_id, e.edge_type, e.weight
                    FROM edges e
                    WHERE (e.source_id = ? OR e.target_id = ?) AND e.edge_type = ?
                    """,
                    (current, current, edge_type),
                ).fetchall()
            else:
                rows = cur.execute(
                    """
                    SELECT e.source_id, e.target_id, e.edge_type, e.weight
                    FROM edges e
                    WHERE (e.source_id = ? OR e.target_id = ?)
                    """,
                    (current, current),
                ).fetchall()

            for row in rows:
                src = int(row["source_id"])
                dst = int(row["target_id"])
                neighbor = dst if src == current else src
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                node_row = cur.execute(
                    "SELECT id, node_type, name, properties FROM nodes WHERE id = ?",
                    (neighbor,),
                ).fetchone()
                if node_row is None:
                    continue
                out.append(
                    {
                        "id": int(node_row["id"]),
                        "node_type": node_row["node_type"],
                        "name": node_row["name"],
                        "properties": _json_loads(node_row["properties"]),
                        "edge_type": row["edge_type"],
                        "weight": float(row["weight"]),
                        "depth": depth + 1,
                    }
                )
                queue.append((neighbor, depth + 1))

        return out

    def find_co_occurring_nodes(self, node_id: int) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        rows = cur.execute(
            """
            SELECT n.id, n.node_type, n.name, COUNT(*) AS co_occurrence_count
            FROM node_media nm1
            JOIN node_media nm2 ON nm1.media_id = nm2.media_id
            JOIN nodes n ON n.id = nm2.node_id
            WHERE nm1.node_id = ? AND nm2.node_id != ?
            GROUP BY n.id, n.node_type, n.name
            ORDER BY co_occurrence_count DESC, n.name ASC
            """,
            (int(node_id), int(node_id)),
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "node_type": row["node_type"],
                "name": row["name"],
                "co_occurrence_count": int(row["co_occurrence_count"]),
            }
            for row in rows
        ]

    def find_temporal_neighbors(self, center_timestamp: float, window: float) -> List[Dict[str, Any]]:
        start_ts = float(center_timestamp) - (float(window) / 2.0)
        end_ts = float(center_timestamp) + (float(window) / 2.0)
        cur = self.conn.cursor()

        media_rows = cur.execute(
            """
            SELECT id, scene_id, media_path, timestamp_start, timestamp_end
            FROM media_nodes
            WHERE timestamp_start IS NOT NULL
              AND timestamp_start BETWEEN ? AND ?
            ORDER BY timestamp_start ASC
            """,
            (start_ts, end_ts),
        ).fetchall()

        event_rows = cur.execute(
            """
            SELECT id, event_type, timestamp, duration, properties
            FROM events
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """,
            (start_ts, end_ts),
        ).fetchall()

        out: List[Dict[str, Any]] = []
        for row in media_rows:
            ts_start = row["timestamp_start"]
            ts_end = row["timestamp_end"]
            midpoint = float(ts_start) if ts_end is None else (float(ts_start) + float(ts_end)) / 2.0
            out.append(
                {
                    "type": "media",
                    "media_id": int(row["id"]),
                    "scene_id": row["scene_id"],
                    "media_path": row["media_path"],
                    "timestamp": midpoint,
                    "timestamp_start": ts_start,
                    "timestamp_end": ts_end,
                }
            )
        for row in event_rows:
            out.append(
                {
                    "type": "event",
                    "event_id": int(row["id"]),
                    "event_type": row["event_type"],
                    "timestamp": float(row["timestamp"]),
                    "duration": row["duration"],
                    "properties": _json_loads(row["properties"]),
                }
            )

        out.sort(key=lambda item: float(item.get("timestamp") or 0.0))
        return out

    def export_subgraph(self, node_ids: Iterable[int], output_path: str) -> None:
        node_set = {int(node_id) for node_id in node_ids}
        if not node_set:
            payload = {"nodes": [], "edges": [], "media": [], "events": []}
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return

        cur = self.conn.cursor()
        placeholders = ",".join("?" for _ in node_set)

        nodes = [
            dict(row)
            for row in cur.execute(
                f"SELECT id, node_type, name, properties, occurrence_count, first_seen, last_seen FROM nodes WHERE id IN ({placeholders})",
                tuple(node_set),
            ).fetchall()
        ]
        edges = [
            dict(row)
            for row in cur.execute(
                f"SELECT id, source_id, target_id, edge_type, weight, properties FROM edges "
                f"WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})",
                tuple(node_set) + tuple(node_set),
            ).fetchall()
        ]
        media = [
            dict(row)
            for row in cur.execute(
                f"""
                SELECT DISTINCT m.id, m.media_type, m.media_path, m.scene_id, m.timestamp_start, m.timestamp_end, m.properties
                FROM media_nodes m
                JOIN node_media nm ON m.id = nm.media_id
                WHERE nm.node_id IN ({placeholders})
                """,
                tuple(node_set),
            ).fetchall()
        ]
        events = [
            dict(row)
            for row in cur.execute(
                f"""
                SELECT DISTINCT e.id, e.event_type, e.timestamp, e.duration, e.properties
                FROM events e
                JOIN event_nodes en ON e.id = en.event_id
                WHERE en.node_id IN ({placeholders})
                """,
                tuple(node_set),
            ).fetchall()
        ]

        payload = {"nodes": nodes, "edges": edges, "media": media, "events": events}
        Path(output_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
