import sqlite3

import pytest

from steps.common import memory


class _FailOnLinkInsertConnection(sqlite3.Connection):
    def execute(self, sql, parameters=(), /):
        if (
            "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at)" in sql
            and not getattr(self, "_failed_once", False)
        ):
            self._failed_once = True
            raise sqlite3.OperationalError("forced mid-sequence failure")
        return super().execute(sql, parameters)


def test_scene_bundle_persistence_is_atomic(monkeypatch, tmp_path):
    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}}

    bootstrap = memory._connect(str(db_path))
    bootstrap.close()

    original_connect = memory.sqlite3.connect

    def _connect_with_failure(path, *args, **kwargs):
        kwargs["factory"] = _FailOnLinkInsertConnection
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(memory.sqlite3, "connect", _connect_with_failure)

    with pytest.raises(sqlite3.OperationalError, match="forced mid-sequence failure"):
        memory.register_scene_bundle(
            cfg,
            video_hash="video_hash_1",
            scene={"start": 0.0, "end": 1.0, "index": 0},
            scene_id="scene_0000",
        )

    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM scenes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM links").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0] == 0
    finally:
        conn.close()
