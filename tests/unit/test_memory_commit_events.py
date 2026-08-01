from __future__ import annotations

import logging
import sqlite3

from steps.common import memory_commit_events


def _event() -> memory_commit_events.MemoryCommitEvent:
    return memory_commit_events.MemoryCommitEvent(
        ts_utc="2026-08-01T00:00:00Z",
        modality="test",
        targets={"sqlite": {"attempted": True, "committed": True}},
    )


def test_sqlite_audit_write_failure_is_visible_without_blocking_ingestion(
    tmp_path, monkeypatch, caplog
) -> None:
    def _fail_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("simulated audit database failure")

    monkeypatch.setattr(memory_commit_events.sqlite3, "connect", _fail_connect)
    cfg = {"paths": {"db_path": str(tmp_path / "memory.db"), "log_dir": str(tmp_path)}}

    with caplog.at_level(logging.WARNING, logger=memory_commit_events.__name__):
        memory_commit_events.emit_memory_commit_event(cfg, _event())

    assert "Memory commit event SQLite persistence failed" in caplog.text


def test_jsonl_audit_mirror_failure_is_visible_without_blocking_ingestion(
    tmp_path, monkeypatch, caplog
) -> None:
    def _fail_open(*_args, **_kwargs):
        raise OSError("simulated audit mirror failure")

    monkeypatch.setattr(memory_commit_events, "open", _fail_open, raising=False)
    cfg = {"paths": {"db_path": str(tmp_path / "memory.db"), "log_dir": str(tmp_path)}}

    with caplog.at_level(logging.WARNING, logger=memory_commit_events.__name__):
        memory_commit_events.emit_memory_commit_event(cfg, _event())

    assert "Memory commit event JSONL mirror failed" in caplog.text
