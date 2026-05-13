"""
GoodQ Observability Rollups (offline/on-demand).

Invoke:
  python -m cli.observability_rollup

This tool adds/updates derived summary tables only. It does not delete or compact raw event history.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Tuple


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS observability_rollup_state (
  key TEXT PRIMARY KEY,
  last_event_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_commit_events_daily (
  date_utc TEXT NOT NULL,
  modality TEXT NOT NULL,
  model TEXT,
  component TEXT,
  committed INTEGER NOT NULL,
  events INTEGER NOT NULL,
  targets_attempted_json TEXT NOT NULL,
  targets_committed_json TEXT NOT NULL,
  last_event_id INTEGER NOT NULL,
  last_ts_utc TEXT,
  PRIMARY KEY (date_utc, modality, model, component, committed)
);

CREATE TABLE IF NOT EXISTS retrieval_events_daily (
  date_utc TEXT NOT NULL,
  store TEXT NOT NULL,
  store_ref TEXT,
  retrieval_context TEXT,
  modality TEXT,
  model TEXT,
  hits INTEGER NOT NULL,
  score_count INTEGER NOT NULL,
  score_sum REAL NOT NULL,
  score_min REAL,
  score_max REAL,
  last_event_id INTEGER NOT NULL,
  last_ts_utc TEXT,
  PRIMARY KEY (date_utc, store, store_ref, retrieval_context, modality, model)
);

CREATE INDEX IF NOT EXISTS idx_red_date ON retrieval_events_daily(date_utc);
CREATE INDEX IF NOT EXISTS idx_red_store ON retrieval_events_daily(store);

CREATE INDEX IF NOT EXISTS idx_mced_date ON memory_commit_events_daily(date_utc);
CREATE INDEX IF NOT EXISTS idx_mced_modality ON memory_commit_events_daily(modality);
"""


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


def _store_ref(store: str, details: Any) -> Optional[str]:
    if isinstance(details, dict):
        ref = details.get("store_ref")
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
        if store == "qdrant":
            ref = details.get("collection")
            if isinstance(ref, str) and ref.strip():
                return ref.strip()
        if store == "faiss":
            ref = details.get("index_path")
            if isinstance(ref, str) and ref.strip():
                return ref.strip()
    return None


@dataclass
class _Agg:
    hits: int = 0
    score_count: int = 0
    score_sum: float = 0.0
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    last_event_id: int = 0
    last_ts_utc: Optional[str] = None

    def add(self, *, event_id: int, ts_utc: str, score: Any) -> None:
        self.hits += 1
        self.last_event_id = max(self.last_event_id, int(event_id or 0))
        if isinstance(ts_utc, str) and ts_utc.strip():
            if self.last_ts_utc is None or ts_utc > self.last_ts_utc:
                self.last_ts_utc = ts_utc
        try:
            s = float(score) if score is not None else None
        except Exception:
            s = None
        if s is None:
            return
        self.score_count += 1
        self.score_sum += s
        if self.score_min is None or s < self.score_min:
            self.score_min = s
        if self.score_max is None or s > self.score_max:
            self.score_max = s


def _safe_str(val: Any) -> Optional[str]:
    if not isinstance(val, str):
        return None
    s = val.strip()
    return s or None


def _parse_targets_json(targets_json: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(targets_json, str) or not targets_json.strip():
        return {}
    try:
        parsed = json.loads(targets_json)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in parsed.items():
        if not isinstance(k, str) or not k.strip():
            continue
        if isinstance(v, dict):
            out[k.strip()] = v
    return out


@dataclass
class _CommitAgg:
    events: int = 0
    last_event_id: int = 0
    last_ts_utc: Optional[str] = None
    targets_attempted: Dict[str, int] = field(default_factory=dict)
    targets_committed: Dict[str, int] = field(default_factory=dict)

    def add(self, *, event_id: int, ts_utc: str, targets: Dict[str, Dict[str, Any]]) -> None:
        self.events += 1
        self.last_event_id = max(self.last_event_id, int(event_id or 0))
        if isinstance(ts_utc, str) and ts_utc.strip():
            if self.last_ts_utc is None or ts_utc > self.last_ts_utc:
                self.last_ts_utc = ts_utc
        for name, info in (targets or {}).items():
            if not isinstance(info, dict):
                continue
            attempted = bool(info.get("attempted", False))
            committed = bool(info.get("committed", False))
            if attempted:
                self.targets_attempted[name] = int(self.targets_attempted.get(name, 0)) + 1
            if committed:
                self.targets_committed[name] = int(self.targets_committed.get(name, 0)) + 1


def _merge_counts(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    out = dict(a or {})
    for k, v in (b or {}).items():
        try:
            out[k] = int(out.get(k, 0)) + int(v or 0)
        except Exception:
            continue
    return out


def _read_counts_json(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in parsed.items():
        if not isinstance(k, str) or not k.strip():
            continue
        try:
            out[k.strip()] = int(v or 0)
        except Exception:
            continue
    return out


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GoodQ Observability Rollups (offline/on-demand)")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N new retrieval_events rows (0 = no limit)")
    parser.add_argument("--commits", action="store_true", help="Also roll up memory_commit_events into memory_commit_events_daily")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg, err = _load_configs()
    if cfg is None:
        print(f"FAIL: load_configs() failed: {err}")
        return 2

    paths = _cfg_paths(cfg)
    db_path = paths.get("db_path")
    if not isinstance(db_path, str) or not db_path.strip():
        print("FAIL: cfg['paths']['db_path'] missing")
        return 2

    try:
        conn = sqlite3.connect(db_path, timeout=2.0, check_same_thread=False)
    except Exception as exc:
        print(f"FAIL: could not open db: {exc}")
        return 2

    try:
        _best_effort_wal(conn)
        conn.executescript(_SCHEMA_SQL)

        did_work = False

        row = conn.execute(
            "SELECT last_event_id FROM observability_rollup_state WHERE key = ?",
            ("retrieval_events_daily",),
        ).fetchone()
        last_id = int(row[0]) if row and row[0] is not None else 0

        limit_sql = ""
        params: Tuple[Any, ...] = (last_id,)
        if isinstance(args.limit, int) and args.limit > 0:
            limit_sql = " LIMIT ?"
            params = (last_id, int(args.limit))

        cur = conn.execute(
            "SELECT id, ts_utc, store, retrieval_context, embedding_id, scene_id, modality, model, score, details_json"
            " FROM retrieval_events WHERE id > ? ORDER BY id ASC" + limit_sql,
            params,
        )

        agg: Dict[Tuple[str, str, Optional[str], str, Optional[str], Optional[str]], _Agg] = {}
        max_id = last_id
        rows = 0
        for (
            event_id,
            ts_utc,
            store,
            retrieval_context,
            _embedding_id,
            _scene_id,
            modality,
            model,
            score,
            details_json,
        ) in cur.fetchall():
            rows += 1
            max_id = max(max_id, int(event_id or 0))
            if not isinstance(ts_utc, str) or len(ts_utc) < 10:
                continue
            date_utc = ts_utc[:10]
            store_s = str(store) if store is not None else "unknown"
            ctx = str(retrieval_context).strip() if isinstance(retrieval_context, str) and retrieval_context.strip() else "unknown"
            mod = str(modality).strip() if isinstance(modality, str) and modality.strip() else None
            mdl = str(model).strip() if isinstance(model, str) and model.strip() else None

            details: Any = {}
            if isinstance(details_json, str) and details_json.strip():
                try:
                    details = json.loads(details_json)
                except Exception:
                    details = {}
            ref = _store_ref(store_s, details)

            key = (date_utc, store_s, ref, ctx, mod, mdl)
            bucket = agg.get(key)
            if bucket is None:
                bucket = _Agg()
                agg[key] = bucket
            bucket.add(event_id=int(event_id or 0), ts_utc=ts_utc, score=score)

        if rows == 0:
            print(f"OK: no new retrieval_events rows (last_event_id={last_id})")
        else:
            did_work = True

        if rows:
            with conn:
                for (date_utc, store_s, ref, ctx, mod, mdl), a in agg.items():
                    conn.execute(
                        """
                        INSERT INTO retrieval_events_daily(
                          date_utc, store, store_ref, retrieval_context, modality, model,
                          hits, score_count, score_sum, score_min, score_max, last_event_id, last_ts_utc
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(date_utc, store, store_ref, retrieval_context, modality, model) DO UPDATE SET
                          hits = hits + excluded.hits,
                          score_count = score_count + excluded.score_count,
                          score_sum = score_sum + excluded.score_sum,
                          score_min = CASE
                            WHEN score_min IS NULL THEN excluded.score_min
                            WHEN excluded.score_min IS NULL THEN score_min
                            WHEN excluded.score_min < score_min THEN excluded.score_min
                            ELSE score_min
                          END,
                          score_max = CASE
                            WHEN score_max IS NULL THEN excluded.score_max
                            WHEN excluded.score_max IS NULL THEN score_max
                            WHEN excluded.score_max > score_max THEN excluded.score_max
                            ELSE score_max
                          END,
                          last_event_id = CASE WHEN excluded.last_event_id > last_event_id THEN excluded.last_event_id ELSE last_event_id END,
                          last_ts_utc = CASE WHEN excluded.last_ts_utc > last_ts_utc THEN excluded.last_ts_utc ELSE last_ts_utc END
                        """,
                        (
                            date_utc,
                            store_s,
                            ref,
                            ctx,
                            mod,
                            mdl,
                            int(a.hits),
                            int(a.score_count),
                            float(a.score_sum),
                            a.score_min,
                            a.score_max,
                            int(a.last_event_id),
                            a.last_ts_utc,
                        ),
                    )

                conn.execute(
                    """
                    INSERT INTO observability_rollup_state(key, last_event_id)
                    VALUES(?,?)
                    ON CONFLICT(key) DO UPDATE SET last_event_id = excluded.last_event_id
                    """,
                    ("retrieval_events_daily", int(max_id)),
                )

            print(f"OK: rolled up {rows} retrieval_events rows into {len(agg)} daily buckets (last_event_id={max_id})")

        if args.commits:
            row = conn.execute(
                "SELECT last_event_id FROM observability_rollup_state WHERE key = ?",
                ("memory_commit_events_daily",),
            ).fetchone()
            last_id = int(row[0]) if row and row[0] is not None else 0

            limit_sql = ""
            params = (last_id,)
            if isinstance(args.limit, int) and args.limit > 0:
                limit_sql = " LIMIT ?"
                params = (last_id, int(args.limit))

            cur = conn.execute(
                "SELECT id, ts_utc, modality, model, component, committed, targets_json"
                " FROM memory_commit_events WHERE id > ? ORDER BY id ASC" + limit_sql,
                params,
            )

            agg2: Dict[Tuple[str, str, Optional[str], Optional[str], int], _CommitAgg] = {}
            max_id = last_id
            rows2 = 0
            for (event_id, ts_utc, modality, model, component, committed, targets_json) in cur.fetchall():
                rows2 += 1
                max_id = max(max_id, int(event_id or 0))
                if not isinstance(ts_utc, str) or len(ts_utc) < 10:
                    continue
                date_utc = ts_utc[:10]
                mod = _safe_str(modality) or "unknown"
                mdl = _safe_str(model)
                comp = _safe_str(component)
                committed_i = 1 if bool(committed) else 0
                targets = _parse_targets_json(targets_json)

                key = (date_utc, mod, mdl, comp, committed_i)
                bucket = agg2.get(key)
                if bucket is None:
                    bucket = _CommitAgg()
                    agg2[key] = bucket
                bucket.add(event_id=int(event_id or 0), ts_utc=ts_utc, targets=targets)

            if rows2 == 0:
                print(f"OK: no new memory_commit_events rows (last_event_id={last_id})")
            else:
                did_work = True

                with conn:
                    for (date_utc, mod, mdl, comp, committed_i), a in agg2.items():
                        existing = conn.execute(
                            """
                            SELECT events, targets_attempted_json, targets_committed_json, last_event_id, last_ts_utc
                            FROM memory_commit_events_daily
                            WHERE date_utc = ? AND modality = ? AND model IS ? AND component IS ? AND committed = ?
                            """,
                            (date_utc, mod, mdl, comp, int(committed_i)),
                        ).fetchone()
                        if existing:
                            existing_events = int(existing[0] or 0)
                            attempted_prev = _read_counts_json(existing[1])
                            committed_prev = _read_counts_json(existing[2])
                            last_event_prev = int(existing[3] or 0)
                            last_ts_prev = existing[4] if isinstance(existing[4], str) else None
                        else:
                            existing_events = 0
                            attempted_prev = {}
                            committed_prev = {}
                            last_event_prev = 0
                            last_ts_prev = None

                        attempted_new = _merge_counts(attempted_prev, a.targets_attempted)
                        committed_new = _merge_counts(committed_prev, a.targets_committed)
                        events_total = existing_events + int(a.events)
                        last_event_total = max(last_event_prev, int(a.last_event_id))
                        last_ts_total = a.last_ts_utc
                        if isinstance(last_ts_prev, str) and last_ts_prev.strip():
                            if last_ts_total is None or last_ts_prev > last_ts_total:
                                last_ts_total = last_ts_prev

                        conn.execute(
                            """
                            INSERT INTO memory_commit_events_daily(
                              date_utc, modality, model, component, committed,
                              events, targets_attempted_json, targets_committed_json,
                              last_event_id, last_ts_utc
                            )
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(date_utc, modality, model, component, committed) DO UPDATE SET
                              events = excluded.events,
                              targets_attempted_json = excluded.targets_attempted_json,
                              targets_committed_json = excluded.targets_committed_json,
                              last_event_id = excluded.last_event_id,
                              last_ts_utc = excluded.last_ts_utc
                            """,
                            (
                                date_utc,
                                mod,
                                mdl,
                                comp,
                                int(committed_i),
                                int(events_total),
                                json.dumps(attempted_new, ensure_ascii=False),
                                json.dumps(committed_new, ensure_ascii=False),
                                int(last_event_total),
                                last_ts_total,
                            ),
                        )

                    conn.execute(
                        """
                        INSERT INTO observability_rollup_state(key, last_event_id)
                        VALUES(?,?)
                        ON CONFLICT(key) DO UPDATE SET last_event_id = excluded.last_event_id
                        """,
                        ("memory_commit_events_daily", int(max_id)),
                    )

                print(
                    f"OK: rolled up {rows2} memory_commit_events rows into {len(agg2)} daily buckets (last_event_id={max_id})"
                )

        if not did_work:
            return 0
        return 0
    except Exception as exc:
        print(f"FAIL: rollup failed: {exc}")
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
