"""
Conduit Pack v1: UI-safe store stats conduits (counts/dims only).

Never store:
  - absolute paths
  - raw vectors
  - raw queries
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vector_store_stats_public (
  store_type TEXT NOT NULL,
  store_ref TEXT NOT NULL,
  dim INTEGER,
  points_count INTEGER,
  status TEXT,
  ts_utc TEXT NOT NULL,
  PRIMARY KEY (store_type, store_ref)
);

CREATE TABLE IF NOT EXISTS faiss_index_stats_public (
  index_ref TEXT PRIMARY KEY,
  modality TEXT,
  exists_flag INTEGER NOT NULL,
  size_bytes INTEGER,
  ntotal INTEGER,
  ts_utc TEXT NOT NULL
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class BuildStats:
    qdrant_rows: int = 0
    faiss_rows: int = 0


def build_all(conn: sqlite3.Connection, *, cfg: Dict[str, Any]) -> BuildStats:
    stats = BuildStats()
    stats.qdrant_rows = _build_qdrant_stats(conn, cfg=cfg)
    stats.faiss_rows = _build_faiss_stats(conn, cfg=cfg)
    return stats


def _build_qdrant_stats(conn: sqlite3.Connection, *, cfg: Dict[str, Any]) -> int:
    q = cfg.get("qdrant") if isinstance(cfg, dict) else None
    if not isinstance(q, dict) or not bool(q.get("enabled", False)):
        return 0
    host = q.get("host")
    collections = q.get("collections")
    if not isinstance(host, str) or not host.strip():
        return 0
    if not isinstance(collections, dict) or not collections:
        return 0

    ts = utc_now_iso()
    out: List[Tuple[Any, ...]] = []

    try:
        import requests

        session = requests.Session()
        for _k, coll in collections.items():
            if not isinstance(coll, str) or not coll.strip():
                continue
            name = coll.strip()
            dim = None
            points = None
            status = "unknown"
            try:
                r = session.get(f"{host}/collections/{name}", timeout=3)
                if r.status_code == 200:
                    payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    res = payload.get("result") if isinstance(payload, dict) else None
                    if isinstance(res, dict):
                        status = "ok"
                        # points_count is typically under result.points_count.
                        if isinstance(res.get("points_count"), int):
                            points = int(res.get("points_count"))
                        # vector size is nested under result.config.params.vectors.size (Qdrant 1.x).
                        cfg_res = res.get("config") if isinstance(res.get("config"), dict) else None
                        params = cfg_res.get("params") if isinstance(cfg_res, dict) else None
                        vectors = params.get("vectors") if isinstance(params, dict) else None
                        if isinstance(vectors, dict) and isinstance(vectors.get("size"), int):
                            dim = int(vectors.get("size"))
                else:
                    status = f"http_{int(r.status_code)}"
            except Exception:
                status = "unreachable"

            out.append(("qdrant", name, dim, points, status, ts))
    except Exception:
        return 0

    with conn:
        conn.executemany(
            """
            INSERT INTO vector_store_stats_public(store_type, store_ref, dim, points_count, status, ts_utc)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(store_type, store_ref) DO UPDATE SET
              dim = excluded.dim,
              points_count = excluded.points_count,
              status = excluded.status,
              ts_utc = excluded.ts_utc
            """,
            out,
        )
    return len(out)


def _build_faiss_stats(conn: sqlite3.Connection, *, cfg: Dict[str, Any]) -> int:
    paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
    faiss_dir = paths.get("faiss_dir")
    configured = []
    for k, v in paths.items():
        if not isinstance(k, str) or "faiss" not in k.lower():
            continue
        if isinstance(v, str) and v.strip() and v.lower().endswith(".index"):
            configured.append(v)

    candidates: List[str] = []
    for p in configured:
        if p not in candidates:
            candidates.append(p)

    if isinstance(faiss_dir, str) and faiss_dir.strip() and os.path.isdir(faiss_dir):
        try:
            for name in os.listdir(faiss_dir):
                if not name.lower().endswith(".index"):
                    continue
                p = os.path.join(faiss_dir, name)
                if p not in candidates:
                    candidates.append(p)
        except Exception:
            pass

    if not candidates:
        return 0

    ts = utc_now_iso()
    out: List[Tuple[Any, ...]] = []

    faiss = None
    try:
        import faiss  # type: ignore

        faiss = faiss
    except Exception:
        faiss = None

    for path in candidates:
        if not isinstance(path, str) or not path.strip():
            continue
        base = os.path.basename(path)
        if not base:
            continue
        exists = os.path.isfile(path)
        size_bytes = None
        if exists:
            try:
                size_bytes = int(os.path.getsize(path))
            except Exception:
                size_bytes = None
        ntotal = None
        if exists and faiss is not None:
            try:
                idx = faiss.read_index(path)  # type: ignore[attr-defined]
                ntotal = int(getattr(idx, "ntotal", 0))
            except Exception:
                ntotal = None

        modality = None
        lower = base.lower()
        if "audio" in lower:
            modality = "audio"
        elif "text" in lower:
            modality = "text"
        elif "clip" in lower:
            modality = "clip"
        elif "dino" in lower:
            modality = "dino"

        out.append((base, modality, 1 if exists else 0, size_bytes, ntotal, ts))

    with conn:
        conn.executemany(
            """
            INSERT INTO faiss_index_stats_public(index_ref, modality, exists_flag, size_bytes, ntotal, ts_utc)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(index_ref) DO UPDATE SET
              modality = excluded.modality,
              exists_flag = excluded.exists_flag,
              size_bytes = excluded.size_bytes,
              ntotal = excluded.ntotal,
              ts_utc = excluded.ts_utc
            """,
            out,
        )
    return len(out)
