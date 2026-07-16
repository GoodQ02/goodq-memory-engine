from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


logger = logging.getLogger(__name__)


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


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return default


@dataclass(frozen=True)
class RetrievalEventPolicy:
    enabled: bool = True
    jsonl_fallback: bool = True
    log_dir: Optional[str] = None


def _existing_log_directory(cfg: Any) -> Optional[str]:
    if not isinstance(cfg, dict):
        return None
    paths = cfg.get("paths")
    if not isinstance(paths, dict):
        return None
    raw = paths.get("log_dir")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        resolved = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return str(resolved) if resolved.is_dir() else None


def resolve_retrieval_event_policy(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    default_enabled: bool = True,
    default_jsonl_fallback: bool = True,
) -> RetrievalEventPolicy:
    enabled = default_enabled
    jsonl_fallback = default_jsonl_fallback
    if isinstance(cfg, dict):
        observability = cfg.get("observability")
        if isinstance(observability, dict):
            policy_cfg = observability.get("retrieval_events")
            if isinstance(policy_cfg, dict):
                enabled = _coerce_bool(
                    policy_cfg.get("enabled"),
                    default=default_enabled,
                )
                jsonl_fallback = _coerce_bool(
                    policy_cfg.get("jsonl_fallback"),
                    default=default_jsonl_fallback,
                )

    if "GOODQ_RETRIEVAL_EVENTS" in os.environ:
        enabled = _coerce_bool(
            os.environ.get("GOODQ_RETRIEVAL_EVENTS"),
            default=enabled,
        )
    if "GOODQ_RETRIEVAL_EVENTS_JSONL" in os.environ:
        jsonl_fallback = _coerce_bool(
            os.environ.get("GOODQ_RETRIEVAL_EVENTS_JSONL"),
            default=jsonl_fallback,
        )

    return RetrievalEventPolicy(
        enabled=enabled,
        jsonl_fallback=jsonl_fallback,
        log_dir=_existing_log_directory(cfg),
    )


def retrieval_events_jsonl_enabled(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    default: bool = True,
) -> bool:
    return resolve_retrieval_event_policy(
        cfg,
        default_jsonl_fallback=default,
    ).jsonl_fallback


def retrieval_events_enabled(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    default: bool = True,
) -> bool:
    return resolve_retrieval_event_policy(
        cfg,
        default_enabled=default,
    ).enabled


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


_SCHEMA_NAMES = {
    "retrieval_events",
    "idx_re_ts",
    "idx_re_embedding",
    "idx_re_scene",
    "idx_re_store",
}


def _ensure_schema(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE name IN (?,?,?,?,?)",
        tuple(sorted(_SCHEMA_NAMES)),
    ).fetchall()
    existing = {str(row[0]) for row in rows}
    if existing == _SCHEMA_NAMES:
        return
    try:
        # Best-effort: favor WAL for low-contention, append-only event writes.
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        logger.debug("retrieval_event_schema_setup reason=journal_mode_unavailable")
    conn.executescript(_SCHEMA_SQL)

def _configure_conn(conn: sqlite3.Connection, *, busy_timeout_ms: int) -> None:
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    conn.execute("PRAGMA synchronous=NORMAL")


def _is_sqlite_locked_error(exc: Exception) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    error_code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(error_code, int) and (error_code & 0xFF) in (5, 6):
        return True
    try:
        message = str(exc).strip().lower()
    except Exception:
        return False
    canonical_messages = (
        "database is locked",
        "database is busy",
        "database table is locked",
        "database table is busy",
        "database schema is locked",
        "database schema is busy",
    )
    return any(
        message == canonical or message.startswith(f"{canonical}:")
        for canonical in canonical_messages
    )


def _warn_persistence_unavailable(*, reason: str, event_count: int) -> None:
    logger.warning(
        "retrieval_event_persistence_unavailable reason=%s event_count=%s",
        reason,
        int(event_count),
    )


def _existing_database_rw_uri(db_path: str) -> str:
    resolved = Path(db_path).expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise FileNotFoundError("retrieval event database is not a regular file")
    return f"{resolved.as_uri()}?mode=rw"


def _emit_jsonl_fallback(
    events: Sequence[RetrievalEvent],
    *,
    policy: RetrievalEventPolicy,
) -> bool:
    if not isinstance(policy.log_dir, str) or not policy.log_dir.strip():
        _warn_persistence_unavailable(
            reason="fallback_unavailable",
            event_count=len(events),
        )
        return False
    destination = Path(policy.log_dir)
    if not destination.is_dir():
        _warn_persistence_unavailable(
            reason="fallback_unavailable",
            event_count=len(events),
        )
        return False
    jsonl_path = destination / "retrieval_events.jsonl"
    try:
        with jsonl_path.open("a", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        _warn_persistence_unavailable(
            reason="fallback_write_failed",
            event_count=len(events),
        )
        return False
    return True


def emit_retrieval_events(
    db_path: Optional[str],
    events: Sequence[Union[RetrievalEvent, Dict[str, Any]]],
    *,
    policy: RetrievalEventPolicy,
) -> None:
    if not events:
        return
    if not policy.enabled:
        return
    if not isinstance(db_path, str) or not db_path.strip():
        _warn_persistence_unavailable(
            reason="missing_database",
            event_count=len(events),
        )
        return

    normalized: List[RetrievalEvent] = []
    invalid_count = 0
    for ev in events:
        try:
            if isinstance(ev, RetrievalEvent):
                normalized.append(ev)
            elif isinstance(ev, dict):
                normalized.append(RetrievalEvent(**ev))
            else:
                invalid_count += 1
        except Exception:
            invalid_count += 1
    if invalid_count:
        _warn_persistence_unavailable(
            reason="invalid_event",
            event_count=invalid_count,
        )
    if not normalized:
        return

    try:
        database_uri = _existing_database_rw_uri(db_path)
    except (OSError, RuntimeError):
        _warn_persistence_unavailable(
            reason="missing_database",
            event_count=len(normalized),
        )
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
        conn = sqlite3.connect(
            database_uri,
            uri=True,
            timeout=0.05,
            check_same_thread=False,
        )
        try:
            _configure_conn(conn, busy_timeout_ms=50)
            _ensure_schema(conn)
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
                logger.debug("retrieval_event_connection_close reason=close_failed")
    except Exception as exc:
        if _is_sqlite_locked_error(exc):
            if policy.jsonl_fallback:
                used_fallback = _emit_jsonl_fallback(normalized, policy=policy)
            else:
                used_fallback = False
                _warn_persistence_unavailable(
                    reason="sqlite_locked",
                    event_count=len(normalized),
                )
            if debug and used_fallback:
                try:
                    print(f"[VECTOR_DEBUG] retrieval_events.jsonl_fallback hits={len(normalized)}")
                except Exception:
                    pass
        else:
            _warn_persistence_unavailable(
                reason="sqlite_error",
                event_count=len(normalized),
            )
        return
