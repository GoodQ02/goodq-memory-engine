from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS retrieval_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  store TEXT NOT NULL,
  retrieval_context TEXT,
  embedding_id TEXT,
  scene_id TEXT,
  modality TEXT,
  model TEXT,
  score REAL,
  details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_re_ts ON retrieval_events(ts_utc);
CREATE INDEX IF NOT EXISTS idx_re_embedding ON retrieval_events(embedding_id);
CREATE INDEX IF NOT EXISTS idx_re_scene ON retrieval_events(scene_id);
CREATE INDEX IF NOT EXISTS idx_re_store ON retrieval_events(store);
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

KNOWN_RETRIEVAL_CONTEXTS: tuple[str, ...] = (
    "human.ui.search",
    "human.cli.retrieve",
    "system.healthcheck",
    "system.dashboard",
    "agent.reasoning",
    "unknown",
)


def normalize_retrieval_context(raw: Optional[str]) -> str:
    if not isinstance(raw, str):
        return "unknown"
    s = raw.strip().lower()
    if not s:
        return "unknown"

    aliases = {
        "cli": "human.cli.retrieve",
        "cli.retrieve": "human.cli.retrieve",
        "ui": "human.ui.search",
        "ui.search": "human.ui.search",
        "api.search": "human.ui.search",
        "healthcheck": "system.healthcheck",
        "doctor": "system.healthcheck",
        "dashboard": "system.dashboard",
        "agent": "agent.reasoning",
    }
    s = aliases.get(s, s)

    if s in KNOWN_RETRIEVAL_CONTEXTS:
        return s
    if re.match(r"^(human|system|agent)\\.[a-z0-9_.-]+$", s):
        return s
    return "unknown"


def retrieval_events_jsonl_enabled(cfg: Optional[Dict[str, Any]] = None, *, default: bool = True) -> bool:
    if "GOODQ_RETRIEVAL_EVENTS_JSONL" in os.environ:
        return _truthy_env("GOODQ_RETRIEVAL_EVENTS_JSONL", default=default)

    if not isinstance(cfg, dict):
        return default

    obs = cfg.get("observability")
    if isinstance(obs, dict):
        re_cfg = obs.get("retrieval_events")
        if isinstance(re_cfg, dict):
            if "jsonl_fallback" in re_cfg:
                return bool(re_cfg.get("jsonl_fallback"))
            if "jsonl_enabled" in re_cfg:
                return bool(re_cfg.get("jsonl_enabled"))

    mem = cfg.get("memory")
    if isinstance(mem, dict):
        re_cfg = mem.get("retrieval_events")
        if isinstance(re_cfg, dict):
            if "jsonl_fallback" in re_cfg:
                return bool(re_cfg.get("jsonl_fallback"))
            if "jsonl_enabled" in re_cfg:
                return bool(re_cfg.get("jsonl_enabled"))

    return default


def retrieval_events_enabled(cfg: Optional[Dict[str, Any]] = None, *, default: bool = True) -> bool:
    # Env override (allows runtime disable without code/config changes).
    if "GOODQ_RETRIEVAL_EVENTS" in os.environ:
        return _truthy_env("GOODQ_RETRIEVAL_EVENTS", default=default)

    if not isinstance(cfg, dict):
        return default

    obs = cfg.get("observability")
    if isinstance(obs, dict):
        re_cfg = obs.get("retrieval_events")
        if isinstance(re_cfg, dict) and "enabled" in re_cfg:
            return bool(re_cfg.get("enabled"))

    mem = cfg.get("memory")
    if isinstance(mem, dict):
        re_cfg = mem.get("retrieval_events")
        if isinstance(re_cfg, dict) and "enabled" in re_cfg:
            return bool(re_cfg.get("enabled"))

    return default


@dataclass
class RetrievalEvent:
    ts_utc: str
    store: str
    retrieval_context: Optional[str] = None
    embedding_id: Optional[str] = None
    scene_id: Optional[str] = None
    modality: Optional[str] = None
    model: Optional[str] = None
    score: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

    def to_row(self) -> Tuple[Any, ...]:
        details_json = "{}"
        if isinstance(self.details, dict) and self.details:
            try:
                details_json = json.dumps(self.details, ensure_ascii=False)
            except Exception:
                details_json = "{}"
        return (
            self.ts_utc,
            self.store,
            self.retrieval_context,
            self.embedding_id,
            self.scene_id,
            self.modality,
            self.model,
            self.score,
            details_json,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts_utc": self.ts_utc,
            "store": self.store,
            "retrieval_context": self.retrieval_context,
            "embedding_id": self.embedding_id,
            "scene_id": self.scene_id,
            "modality": self.modality,
            "model": self.model,
            "score": self.score,
            "details": self.details if isinstance(self.details, dict) else {},
        }


_SCHEMA_INITIALIZED: set[str] = set()


def _ensure_schema(conn: sqlite3.Connection, db_path: str) -> None:
    if db_path in _SCHEMA_INITIALIZED:
        return
    try:
        # Best-effort: favor WAL for low-contention, append-only event writes.
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.executescript(_SCHEMA_SQL)
    _SCHEMA_INITIALIZED.add(db_path)

def _configure_conn(conn: sqlite3.Connection, *, busy_timeout_ms: int) -> None:
    try:
        conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass

def _cfg_paths(cfg: Any) -> Dict[str, Any]:
    return (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}


def _is_sqlite_locked_error(exc: Exception) -> bool:
    try:
        msg = str(exc).lower()
    except Exception:
        return False
    return "database is locked" in msg or "database is busy" in msg or "locked" in msg or "busy" in msg


def _fallback_log_dir(db_path: str, cfg: Optional[Dict[str, Any]], log_dir: Optional[str]) -> Optional[str]:
    if isinstance(log_dir, str) and log_dir.strip() and os.path.isdir(log_dir):
        return log_dir
    paths = _cfg_paths(cfg) if isinstance(cfg, dict) else {}
    cfg_log_dir = paths.get("log_dir")
    if isinstance(cfg_log_dir, str) and cfg_log_dir.strip() and os.path.isdir(cfg_log_dir):
        return cfg_log_dir
    try:
        parent = os.path.dirname(db_path)
        if parent and os.path.isdir(parent):
            return parent
    except Exception:
        pass
    return None


def _emit_jsonl_fallback(
    db_path: str,
    events: Sequence[RetrievalEvent],
    *,
    cfg: Optional[Dict[str, Any]] = None,
    log_dir: Optional[str] = None,
) -> None:
    if not retrieval_events_jsonl_enabled(cfg, default=True):
        return
    dest_dir = _fallback_log_dir(db_path, cfg, log_dir)
    if not dest_dir:
        return
    jsonl_path = os.path.join(dest_dir, "retrieval_events.jsonl")
    try:
        with open(jsonl_path, "a", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        return


def emit_retrieval_events(
    db_path: Optional[str],
    events: Sequence[Union[RetrievalEvent, Dict[str, Any]]],
    *,
    cfg: Optional[Dict[str, Any]] = None,
    enabled: Optional[bool] = None,
    log_dir: Optional[str] = None,
) -> None:
    if not events:
        return
    if not isinstance(db_path, str) or not db_path.strip():
        return

    allow = retrieval_events_enabled(cfg, default=(bool(enabled) if enabled is not None else True))
    if not allow:
        return

    normalized: List[RetrievalEvent] = []
    for ev in events:
        try:
            if isinstance(ev, RetrievalEvent):
                normalized.append(ev)
            elif isinstance(ev, dict):
                normalized.append(RetrievalEvent(**ev))
        except Exception:
            continue
    if not normalized:
        return

    debug = _vector_debug_enabled()
    if debug:
        try:
            store = normalized[0].store if normalized else "unknown"
            ctx = normalized[0].retrieval_context or "unknown"
            print(f"[VECTOR_DEBUG] retrieval_events.emit store={store} ctx={ctx} hits={len(normalized)}")
        except Exception:
            pass

    try:
        conn = sqlite3.connect(db_path, timeout=0.05, check_same_thread=False)
        try:
            _configure_conn(conn, busy_timeout_ms=50)
            _ensure_schema(conn, db_path)
            rows = [ev.to_row() for ev in normalized]
            with conn:
                conn.executemany(
                    """
                    INSERT INTO retrieval_events(
                      ts_utc, store, retrieval_context, embedding_id, scene_id, modality, model, score, details_json
                    )
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    rows,
                )
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as exc:
        if _is_sqlite_locked_error(exc):
            _emit_jsonl_fallback(db_path, normalized, cfg=cfg, log_dir=log_dir)
            if debug:
                try:
                    print(f"[VECTOR_DEBUG] retrieval_events.jsonl_fallback hits={len(normalized)}")
                except Exception:
                    pass
        return
