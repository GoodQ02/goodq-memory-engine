"""
GoodQ Observability Health Report (read-only).

Invoke:
  python -m cli.observability_health
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Best-effort to keep this tool read-only (avoid writing __pycache__ for subsequent imports).
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    try:
        cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
        return cur.fetchone() is not None
    except Exception:
        return False


def _count_rows(db_path: str, table: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.2, check_same_thread=False)
    except Exception as exc:
        return None, f"open_failed: {exc}"
    try:
        if not _table_exists(conn, table):
            return 0, "table_missing"
        cur = conn.execute(f"SELECT COUNT(1) FROM {table}")
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0, None
    except Exception as exc:
        return None, str(exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _load_configs() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        from steps.common.config_loader import load_configs

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            cfg = load_configs({})
        noise = buf.getvalue().strip() or None
        if not isinstance(cfg, dict):
            return None, f"load_configs returned {type(cfg)}"
        return cfg, noise
    except Exception as exc:
        return None, str(exc)


def _cfg_paths(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}


def _recent_log_files(root: Path, *, limit: int = 10) -> List[Path]:
    import heapq

    if limit <= 0:
        return []
    heap: List[Tuple[float, Path]] = []
    try:
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                n = name.lower()
                if not n.endswith((".log", ".txt", ".out", ".err")):
                    continue
                path = Path(dirpath) / name
                try:
                    mtime = path.stat().st_mtime
                except Exception:
                    continue
                if len(heap) < limit:
                    heapq.heappush(heap, (mtime, path))
                else:
                    if mtime > heap[0][0]:
                        heapq.heapreplace(heap, (mtime, path))
    except Exception:
        return []
    return [p for _, p in sorted(heap, key=lambda t: t[0], reverse=True)]


def _tail_contains(path: Path, needle: bytes, *, max_bytes: int = 200_000) -> bool:
    try:
        with path.open("rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes), os.SEEK_SET)
            except Exception:
                pass
            data = f.read()
        return needle in data
    except Exception:
        return False


def _scan_sqlite_lock_warnings(log_dir: Optional[str]) -> Tuple[List[Path], List[Path]]:
    if not isinstance(log_dir, str) or not log_dir.strip():
        return [], []
    root = Path(log_dir)
    if not root.exists():
        return [], []
    locked = []
    busy = []
    for path in _recent_log_files(root, limit=12):
        if _tail_contains(path, b"database is locked"):
            locked.append(path)
        if _tail_contains(path, b"database is busy"):
            busy.append(path)
    return locked, busy


def _provenance_coverage_sample(cfg: Dict[str, Any], *, top_k: int = 5) -> Tuple[Optional[float], Optional[str]]:
    try:
        from steps.common.qdrant_client import build_qdrant_client
        from steps.common.retrieval_events import RetrievalEventPolicy
    except Exception as exc:
        return None, f"qdrant_client_import_failed: {exc}"

    paths = _cfg_paths(cfg)
    db_path = paths.get("db_path")

    payload_filter = None
    try:
        if isinstance(db_path, str) and db_path.strip():
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.2, check_same_thread=False)
            try:
                if _table_exists(conn, "memory_commit_events"):
                    row = conn.execute(
                        """
                        SELECT video_id
                        FROM memory_commit_events
                        WHERE video_id IS NOT NULL AND modality = 'clip' AND committed = 1
                        ORDER BY ts_utc DESC
                        LIMIT 1
                        """
                    ).fetchone()
                    if row and isinstance(row[0], str) and row[0].strip():
                        video_id = row[0].strip()
                        payload_filter = {
                            "must": [
                                {"key": "video_id", "match": {"value": video_id}},
                                {"key": "model", "match": {"value": "clip"}},
                            ]
                        }
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    except Exception:
        payload_filter = None

    mem = cfg.get("memory") if isinstance(cfg, dict) else None
    dims = mem.get("dims") if isinstance(mem, dict) else None
    dim = dims.get("clip") if isinstance(dims, dict) else None
    if not isinstance(dim, int) or dim <= 0:
        dim = 512

    client = build_qdrant_client(
        cfg,
        dim,
        "clip",
        retrieval_event_policy=RetrievalEventPolicy(
            enabled=False,
            jsonl_fallback=False,
        ),
    )
    if client is None:
        return None, "qdrant_disabled_or_unavailable"

    try:
        hits = client.query(
            [0.001] * int(dim),
            top_k=top_k,
            payload_filter=payload_filter,
            retrieval_context="system.healthcheck",
        )
    except Exception as exc:
        return None, f"sample_query_failed: {exc}"

    if not hits:
        return None, "no_hits"

    attached = 0
    total = 0
    for h in hits:
        if not isinstance(h, dict):
            continue
        total += 1
        if isinstance(h.get("provenance"), dict):
            attached += 1
    if total == 0:
        return None, "hits_unexpected_shape"
    return attached / total, None


def _print_kv(label: str, value: Any) -> None:
    print(f"{label}: {value}")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GoodQ Observability Health Report (read-only)")
    parser.add_argument("--sample-k", type=int, default=5, help="Number of hits for provenance coverage sample")
    args = parser.parse_args(list(argv) if argv is not None else None)

    print("GoodQ Observability Health Report")
    print("================================")

    cfg, cfg_err = _load_configs()
    if cfg is None:
        _print_kv("CONFIG", f"FAIL ({cfg_err})")
        return 2
    if cfg_err:
        _print_kv("CONFIG", f"WARN (load_configs emitted output: {cfg_err.splitlines()[0]})")
    else:
        _print_kv("CONFIG", "PASS")

    paths = _cfg_paths(cfg)
    db_path = paths.get("db_path")
    log_dir = paths.get("log_dir")

    if not isinstance(db_path, str) or not db_path.strip():
        _print_kv("DB", "FAIL (cfg['paths']['db_path'] missing)")
        return 2
    _print_kv("DB Path", db_path)

    mce_count, mce_err = _count_rows(db_path, "memory_commit_events")
    if mce_count is None:
        _print_kv("memory_commit_events", f"FAIL ({mce_err})")
    elif mce_err == "table_missing":
        _print_kv("memory_commit_events", "WARN (table missing)")
    else:
        _print_kv("memory_commit_events", mce_count)

    re_count, re_err = _count_rows(db_path, "retrieval_events")
    if re_count is None:
        _print_kv("retrieval_events", f"WARN ({re_err})")
    elif re_err == "table_missing":
        _print_kv("retrieval_events", "WARN (table missing or never emitted)")
    else:
        _print_kv("retrieval_events", re_count)

    try:
        from steps.common.retrieval_events import retrieval_events_enabled

        enabled = retrieval_events_enabled(cfg, default=True)
        if enabled:
            _print_kv("Retrieval Events", "ENABLED")
        else:
            _print_kv("Retrieval Events", "DISABLED (WARN)")
    except Exception as exc:
        _print_kv("Retrieval Events", f"WARN (status unknown: {exc})")

    locked, busy = _scan_sqlite_lock_warnings(log_dir)
    if locked:
        _print_kv("SQLite Locks", f"WARN (database is locked seen in {len(locked)} recent log files)")
        for p in locked[:5]:
            print(f"  - {p}")
    elif busy:
        _print_kv("SQLite Locks", f"WARN (database is busy seen in {len(busy)} recent log files)")
        for p in busy[:5]:
            print(f"  - {p}")
    else:
        _print_kv("SQLite Locks", "OK (no recent lock strings observed)")

    cov, cov_err = _provenance_coverage_sample(cfg, top_k=max(1, int(args.sample_k)))
    if cov is not None:
        _print_kv("Provenance Coverage (sample)", f"{cov:.0%}")
    else:
        _print_kv("Provenance Coverage (sample)", f"WARN ({cov_err})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
