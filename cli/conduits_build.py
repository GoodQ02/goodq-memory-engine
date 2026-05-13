"""
Conduit Pack v1 builder (offline/on-demand).

Invoke:
  python -m cli.conduits_build

This command builds/refreshes UI-safe, whitelisted conduits across:
  - memory.db (derived tables only)
  - knowledge_graph.db (derived tables only)
  - processing artifacts adapters (sanitized into derived tables)

Non-negotiable: never copy absolute paths, raw transcripts, or raw vectors into conduits.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple


# Best-effort: avoid writing __pycache__ for subsequent imports.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


_CONDUIT_SCHEMA_VERSION = 1

_VERSION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conduit_schema_version (
  name TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  built_ts_utc TEXT NOT NULL
);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _best_effort_wal(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass


def _set_version(conn: sqlite3.Connection, name: str) -> None:
    with conn:
        conn.executescript(_VERSION_SCHEMA_SQL)
        conn.execute(
            """
            INSERT INTO conduit_schema_version(name, version, built_ts_utc)
            VALUES (?,?,?)
            ON CONFLICT(name) DO UPDATE SET
              version = excluded.version,
              built_ts_utc = excluded.built_ts_utc
            """,
            (name, int(_CONDUIT_SCHEMA_VERSION), utc_now_iso()),
        )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GoodQ Conduit Pack v1 builder (offline/on-demand)")
    parser.add_argument("--skip-kg", action="store_true", help="Skip knowledge_graph.db conduits")
    parser.add_argument("--skip-processing", action="store_true", help="Skip processing artifact adapters")
    parser.add_argument("--skip-stats", action="store_true", help="Skip store stats conduits (Qdrant/FAISS)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg, err = _load_configs()
    if cfg is None:
        print(f"FAIL: load_configs() failed: {err}")
        return 2

    paths = _cfg_paths(cfg)
    db_path = paths.get("db_path")
    kg_path = paths.get("knowledge_graph_db")
    processing_root = paths.get("processing")

    if not isinstance(db_path, str) or not db_path.strip():
        print("FAIL: cfg['paths']['db_path'] missing")
        return 2

    exit_code = 0

    try:
        mem_conn = sqlite3.connect(db_path, timeout=2.0, check_same_thread=False)
    except Exception as exc:
        print(f"FAIL: could not open memory db: {exc}")
        return 2

    try:
        _best_effort_wal(mem_conn)
        _set_version(mem_conn, "conduit_pack")

        # Rollups (observability only)
        try:
            from cli import observability_rollup

            observability_rollup.main(["--commits"])
        except Exception as exc:
            print(f"WARN: observability_rollup failed: {exc}")

        # Existing UI conduits (scene_index_public, scene_modality_coverage)
        try:
            from cli import ui_conduits_rollup

            ui_conduits_rollup.main([])
        except Exception as exc:
            print(f"WARN: ui_conduits_rollup failed: {exc}")

        # Memory.db conduits
        try:
            from cli import conduits_memory

            conduits_memory.ensure_schema(mem_conn)
            s = conduits_memory.build_all(mem_conn, cfg=cfg)
            print(
                "OK: memory_db"
                f" segment_index_public={s.segment_rows} scene_segment_alignment={s.alignment_rows}"
                f" embedding_catalog_public={s.embedding_rows} summaries_public={s.summaries_rows}"
                f" link_summary_public={s.link_rows}"
            )
        except Exception as exc:
            print(f"FAIL: memory.db conduits failed: {exc}")
            exit_code = 2

        # Sensitive Source Wiring Pack v1 (schema-only; empty by default)
        try:
            from cli import conduits_sensitive_sources

            conduits_sensitive_sources.ensure_schema(mem_conn)
            _set_version(mem_conn, "sensitive_source_wiring_pack")
            print("OK: sensitive_sources (wiring pack v1)")
        except Exception as exc:
            print(f"WARN: sensitive source conduits failed: {exc}")

        # Processing artifact adapters (into memory.db tables)
        if exit_code == 0 and not args.skip_processing:
            if isinstance(processing_root, str) and processing_root.strip() and os.path.isdir(processing_root):
                try:
                    from cli import conduits_processing

                    conduits_processing.ensure_schema(mem_conn)
                    ps = conduits_processing.build_all(mem_conn, processing_root=processing_root)
                    print(
                        "OK: processing_adapters"
                        f" videos_seen={ps.videos_seen} scene_manifest_public={ps.scene_rows}"
                        f" temporal_index_public={ps.temporal_rows} temporal_segments_public={ps.temporal_segment_rows}"
                    )
                except Exception as exc:
                    print(f"WARN: processing adapters failed: {exc}")
            else:
                print("WARN: processing adapters skipped (cfg['paths']['processing'] missing or not a directory)")

        # Store stats (into memory.db tables)
        if exit_code == 0 and not args.skip_stats:
            try:
                from cli import conduits_store_stats

                conduits_store_stats.ensure_schema(mem_conn)
                ss = conduits_store_stats.build_all(mem_conn, cfg=cfg)
                print(f"OK: store_stats qdrant={ss.qdrant_rows} faiss={ss.faiss_rows}")
            except Exception as exc:
                print(f"WARN: store stats failed: {exc}")

    finally:
        try:
            mem_conn.close()
        except Exception:
            pass

    # Knowledge graph conduits
    if exit_code == 0 and not args.skip_kg:
        if not isinstance(kg_path, str) or not kg_path.strip():
            print("WARN: kg conduits skipped (cfg['paths']['knowledge_graph_db'] missing)")
        else:
            try:
                kg_conn = sqlite3.connect(kg_path, timeout=2.0, check_same_thread=False)
            except Exception as exc:
                print(f"WARN: could not open knowledge_graph db: {exc}")
            else:
                try:
                    _best_effort_wal(kg_conn)
                    _set_version(kg_conn, "conduit_pack")
                    try:
                        from cli import conduits_kg

                        conduits_kg.ensure_schema(kg_conn)
                        ks = conduits_kg.build_all(kg_conn)
                        print(
                            "OK: knowledge_graph_db"
                            f" kg_entity_index_public={ks.entities} kg_edge_summary_public={ks.edge_types}"
                            f" entity_timeline_public={ks.timeline_rows} entity_scene_mentions_public={ks.mention_rows}"
                        )
                    except Exception as exc:
                        print(f"WARN: kg conduits failed: {exc}")
                finally:
                    try:
                        kg_conn.close()
                    except Exception:
                        pass

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
