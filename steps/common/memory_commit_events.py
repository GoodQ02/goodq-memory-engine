from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memory_commit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  scene_id TEXT,
  video_id TEXT,
  modality TEXT NOT NULL,
  model TEXT,
  embedding_id TEXT,
  component TEXT,
  attempted INTEGER NOT NULL,
  committed INTEGER NOT NULL,
  reason TEXT,
  targets_json TEXT NOT NULL,
  confidence_json TEXT,
  details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_mce_ts ON memory_commit_events(ts_utc);
CREATE INDEX IF NOT EXISTS idx_mce_scene ON memory_commit_events(scene_id);
CREATE INDEX IF NOT EXISTS idx_mce_modality ON memory_commit_events(modality);
"""


def _truthy_env(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _vector_debug_enabled() -> bool:
    return _truthy_env("GOODQ_VECTOR_DEBUG", default=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_confidence_payload() -> Dict[str, Any]:
    return {
        "intrinsic": None,
        "source": None,
        "temporal": None,
        "consistency": None,
        "overall": None,
    }


def _normalize_confidence(confidence: Any) -> Dict[str, Any]:
    defaults = default_confidence_payload()
    if isinstance(confidence, dict):
        for k in defaults.keys():
            if k in confidence:
                defaults[k] = confidence.get(k)
    return defaults


@dataclass
class MemoryCommitEvent:
    ts_utc: str
    modality: str
    targets: Dict[str, Dict[str, Any]]
    scene_id: Optional[str] = None
    video_id: Optional[str] = None
    model: Optional[str] = None
    embedding_id: Optional[str] = None
    component: Optional[str] = None
    attempted: Optional[bool] = None
    committed: Optional[bool] = None
    reason: Optional[str] = None
    confidence: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None

    def normalized(self) -> "MemoryCommitEvent":
        targets = self.targets if isinstance(self.targets, dict) else {}
        attempted_any = False
        committed_all_attempted = True
        for t in targets.values():
            if not isinstance(t, dict):
                continue
            attempted = bool(t.get("attempted", False))
            committed = bool(t.get("committed", False))
            attempted_any = attempted_any or attempted
            if attempted and not committed:
                committed_all_attempted = False
        attempted = attempted_any if self.attempted is None else bool(self.attempted)
        committed = (attempted and committed_all_attempted) if self.committed is None else bool(self.committed)
        reason = self.reason
        if not committed and not reason:
            reason = "commit_incomplete"
        confidence = _normalize_confidence(self.confidence)
        return MemoryCommitEvent(
            ts_utc=self.ts_utc,
            modality=self.modality,
            targets=targets,
            scene_id=self.scene_id,
            video_id=self.video_id,
            model=self.model,
            embedding_id=self.embedding_id,
            component=self.component,
            attempted=attempted,
            committed=committed,
            reason=reason,
            confidence=confidence,
            details=self.details if isinstance(self.details, dict) else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        ev = self.normalized()
        return {
            "ts_utc": ev.ts_utc,
            "scene_id": ev.scene_id,
            "video_id": ev.video_id,
            "modality": ev.modality,
            "model": ev.model,
            "embedding_id": ev.embedding_id,
            "component": ev.component,
            "attempted": bool(ev.attempted),
            "committed": bool(ev.committed),
            "reason": ev.reason,
            "targets": ev.targets,
            "confidence": ev.confidence,
            "details": ev.details,
        }

    def to_row(self) -> Tuple[Any, ...]:
        ev = self.normalized()
        return (
            ev.ts_utc,
            ev.scene_id,
            ev.video_id,
            ev.modality,
            ev.model,
            ev.embedding_id,
            ev.component,
            1 if ev.attempted else 0,
            1 if ev.committed else 0,
            ev.reason,
            json.dumps(ev.targets, ensure_ascii=False),
            json.dumps(ev.confidence, ensure_ascii=False) if ev.confidence else None,
            json.dumps(ev.details, ensure_ascii=False) if ev.details else None,
        )


_SCHEMA_VERSION = 2
_SCHEMA_INITIALIZED: set[Tuple[str, int]] = set()


def _ensure_schema(conn: sqlite3.Connection, db_path: str) -> None:
    cache_key = (db_path, _SCHEMA_VERSION)
    if cache_key in _SCHEMA_INITIALIZED:
        return
    try:
        # Best-effort: favor WAL for low-contention, append-only event writes.
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.executescript(_SCHEMA_SQL)
    try:
        cur = conn.execute("PRAGMA table_info('memory_commit_events')")
        cols = {row[1] for row in cur.fetchall()}
        if "confidence_json" not in cols:
            conn.execute("ALTER TABLE memory_commit_events ADD COLUMN confidence_json TEXT")
    except Exception:
        pass
    _SCHEMA_INITIALIZED.add(cache_key)


def _cfg_paths(cfg: Any) -> Dict[str, Any]:
    return (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}

def _configure_conn(conn: sqlite3.Connection, *, busy_timeout_ms: int) -> None:
    try:
        conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    except Exception:
        pass
    try:
        # Best-effort: reduce fsync pressure for observability-only writes.
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass


def emit_memory_commit_event(cfg: Dict[str, Any], event: Union[MemoryCommitEvent, Dict[str, Any]]) -> None:
    emit_memory_commit_events(cfg, [event])


def emit_memory_commit_events(cfg: Dict[str, Any], events: Sequence[Union[MemoryCommitEvent, Dict[str, Any]]]) -> None:
    if not events:
        return

    paths = _cfg_paths(cfg)
    db_path = paths.get("db_path")
    if not isinstance(db_path, str) or not db_path.strip():
        return

    normalized: List[MemoryCommitEvent] = []
    for ev in events:
        try:
            if isinstance(ev, MemoryCommitEvent):
                normalized.append(ev.normalized())
            elif isinstance(ev, dict):
                normalized.append(MemoryCommitEvent(**ev).normalized())
        except Exception:
            continue

    if not normalized:
        return

    debug = _vector_debug_enabled()
    if debug:
        for ev in normalized:
            try:
                targets = ",".join(sorted((ev.targets or {}).keys()))
                print(
                    f"[VECTOR_DEBUG] commit_event modality={ev.modality} scene_id={ev.scene_id}"
                    f" committed={ev.committed} attempted={ev.attempted} targets={targets} reason={ev.reason}"
                )
            except Exception:
                pass

    # SQLite persistence (authoritative)
    try:
        conn = sqlite3.connect(db_path, timeout=0.2, check_same_thread=False)
        try:
            _configure_conn(conn, busy_timeout_ms=200)
            _ensure_schema(conn, db_path)
            rows = [ev.to_row() for ev in normalized]
            with conn:
                try:
                    conn.executemany(
                        """
                        INSERT INTO memory_commit_events(
                          ts_utc, scene_id, video_id, modality, model, embedding_id, component,
                          attempted, committed, reason, targets_json, confidence_json, details_json
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        rows,
                    )
                except Exception:
                    # Backward-compatible insert for older schemas without confidence_json.
                    legacy_rows = [r[:11] + (r[12],) for r in rows if isinstance(r, tuple) and len(r) >= 13]
                    conn.executemany(
                        """
                        INSERT INTO memory_commit_events(
                          ts_utc, scene_id, video_id, modality, model, embedding_id, component,
                          attempted, committed, reason, targets_json, details_json
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        legacy_rows,
                    )
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as exc:
        # Never block ingestion on observability writes.
        if debug:
            try:
                print(f"[VECTOR_DEBUG] commit_events.sqlite_failed err={exc}")
            except Exception:
                pass

    # Optional JSONL mirror (debuggable, append-only)
    if not _truthy_env("GOODQ_COMMIT_EVENTS_JSONL", default=True):
        return
    log_dir = paths.get("log_dir")
    if not isinstance(log_dir, str) or not log_dir.strip():
        return
    if not os.path.isdir(log_dir):
        return
    jsonl_path = os.path.join(log_dir, "memory_commit_events.jsonl")
    try:
        with open(jsonl_path, "a", encoding="utf-8") as f:
            for ev in normalized:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        return
