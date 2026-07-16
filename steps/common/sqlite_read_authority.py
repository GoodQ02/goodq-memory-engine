"""Shared capability boundary for existing-file SQLite read projections."""

from __future__ import annotations

from pathlib import Path
import sqlite3


_DENIED_SQLITE_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_CREATE_VTABLE,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_DROP_VTABLE,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_ANALYZE,
    }
)


def _sqlite_read_authorizer(
    action_code: int,
    _first_argument: str | None,
    second_argument: str | None,
    _database_name: str | None,
    _trigger_name: str | None,
) -> int:
    if action_code in _DENIED_SQLITE_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action_code == sqlite3.SQLITE_PRAGMA and second_argument is not None:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_sqlite_read_connection(
    db_path: Path | str,
    *,
    unavailable_message: str = "SQLite database is unavailable",
    timeout: float = 5.0,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    """Open one existing SQLite file with live-WAL reads but no write authority."""

    path = Path(db_path)
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise FileNotFoundError(unavailable_message) from exc
    if not resolved.is_file():
        raise FileNotFoundError(unavailable_message)

    connection = sqlite3.connect(
        f"{resolved.as_uri()}?mode=ro",
        uri=True,
        timeout=timeout,
        check_same_thread=check_same_thread,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.set_authorizer(_sqlite_read_authorizer)
        enabled = connection.execute("PRAGMA query_only").fetchone()
        if enabled != (1,):
            raise sqlite3.OperationalError(
                "SQLite read connection could not enable query_only"
            )
    except Exception:
        connection.close()
        raise
    return connection
