from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from api.routes import summary as summary_route
from lib import summary_aggregator
from steps.common import config_loader


_VIDEO_HASH = "1234567890abcdef1234567890abcdef"


class _EmptyDataLoader:
    def list_processed_videos(self) -> list[str]:
        return []

    def load_temporal_index(self, _video_id: str):
        return None


def _seed_knowledge_graph(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                occurrence_count INTEGER,
                first_seen REAL,
                last_seen REAL,
                properties TEXT
            );
            CREATE TABLE edges (
                source_id INTEGER,
                target_id INTEGER,
                edge_type TEXT,
                properties TEXT
            );
            CREATE TABLE node_media (node_id INTEGER, media_id INTEGER);
            CREATE TABLE media_nodes (
                id INTEGER PRIMARY KEY,
                scene_id TEXT,
                media_path TEXT,
                properties TEXT
            );
            CREATE TABLE scenes (video_hash TEXT);
            """
        )
        conn.execute(
            """
            INSERT INTO nodes (
                id, node_type, name, occurrence_count, first_seen, last_seen, properties
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "person", "Joe", 2, 1.0, 2.0, "{}"),
        )
        conn.execute("INSERT INTO scenes (video_hash) VALUES (?)", (_VIDEO_HASH,))


def _seed_memory_database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE summaries (
                content TEXT,
                created_at TEXT,
                summary_type TEXT,
                category TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO summaries (content, created_at, summary_type, category)
            VALUES (?, ?, 'video', 'video_summary')
            """,
            (
                json.dumps(
                    {
                        "video_hash": _VIDEO_HASH,
                        "summary": "Fixture summary",
                        "method": "template",
                        "provenance": {"source": "fixture"},
                    }
                ),
                "2026-07-13T00:00:00Z",
            ),
        )


def test_summary_read_connection_does_not_create_missing_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        summary_aggregator.open_summary_read_connection(missing)

    assert not missing.exists()
    assert not missing.with_name(f"{missing.name}-wal").exists()
    assert not missing.with_name(f"{missing.name}-shm").exists()


def test_summary_read_connection_sees_live_wal_and_rejects_writes(tmp_path: Path) -> None:
    database = tmp_path / "live-wal.db"
    writer = sqlite3.connect(database)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("CREATE TABLE evidence (value TEXT)")
    writer.commit()
    writer.execute("INSERT INTO evidence (value) VALUES ('committed-in-wal')")
    writer.commit()
    assert database.with_name(f"{database.name}-wal").exists()

    reader = summary_aggregator.open_summary_read_connection(database)
    try:
        assert reader.execute("PRAGMA query_only").fetchone() == (1,)
        assert reader.execute("SELECT value FROM evidence").fetchone() == (
            "committed-in-wal",
        )
        with pytest.raises(sqlite3.DatabaseError):
            reader.execute("INSERT INTO evidence (value) VALUES ('forbidden')")
        with pytest.raises(sqlite3.DatabaseError):
            reader.execute("CREATE TABLE forbidden (id INTEGER)")
    finally:
        reader.close()
        writer.close()


@pytest.mark.parametrize(
    "statement",
    [
        "ATTACH DATABASE ? AS extra",
        "VACUUM INTO ?",
    ],
)
def test_summary_read_connection_rejects_external_database_creation(
    tmp_path: Path,
    statement: str,
) -> None:
    database = tmp_path / "existing.db"
    attached = tmp_path / "must-stay-absent.db"
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE evidence (value TEXT)")

    reader = summary_aggregator.open_summary_read_connection(database)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            reader.execute(statement, (str(attached),))
    finally:
        reader.close()

    assert not attached.exists()


def test_summary_read_connection_cannot_disable_query_only(tmp_path: Path) -> None:
    database = tmp_path / "existing.db"
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE evidence (value TEXT)")

    reader = summary_aggregator.open_summary_read_connection(database)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            reader.execute("PRAGMA query_only=OFF")
        assert reader.execute("PRAGMA query_only").fetchone() == (1,)
    finally:
        reader.close()


@pytest.mark.parametrize(
    "caller",
    [
        lambda path, loader: summary_aggregator.get_summary_dashboard(path, loader),
        lambda path, loader: summary_aggregator.get_entity_profile(
            path,
            loader,
            "person:Joe",
        ),
    ],
)
def test_summary_aggregator_missing_database_stays_absent(
    tmp_path: Path,
    caller,
) -> None:
    missing = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        caller(missing, _EmptyDataLoader())

    assert not missing.exists()


def test_all_summary_sqlite_readers_use_bounded_read_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    knowledge_graph = tmp_path / "knowledge_graph.db"
    memory_database = tmp_path / "memory.db"
    _seed_knowledge_graph(knowledge_graph)
    _seed_memory_database(memory_database)

    opened_paths: list[Path] = []
    opened_connections: list[sqlite3.Connection] = []
    real_open = summary_aggregator.open_summary_read_connection

    def tracked_open(path: Path | str) -> sqlite3.Connection:
        connection = real_open(path)
        opened_paths.append(Path(path))
        opened_connections.append(connection)
        return connection

    monkeypatch.setattr(
        summary_aggregator,
        "open_summary_read_connection",
        tracked_open,
    )
    monkeypatch.setattr(
        config_loader,
        "load_configs",
        lambda _overrides: {"paths": {"db_path": str(memory_database)}},
    )
    monkeypatch.setattr(
        summary_route,
        "_get_kg_db_path",
        lambda: knowledge_graph,
    )

    dashboard = summary_aggregator.get_summary_dashboard(
        knowledge_graph,
        _EmptyDataLoader(),
    )
    entity = summary_aggregator.get_entity_profile(
        knowledge_graph,
        _EmptyDataLoader(),
        "person:Joe",
    )
    video = asyncio.run(summary_route.get_video_summary(_VIDEO_HASH))
    fallback = summary_route._check_kg_existence_fallback(_VIDEO_HASH)

    assert dashboard["people"][0]["name"] == "Joe"
    assert entity["name"] == "Joe"
    assert video["summary"] == "Fixture summary"
    assert fallback["method"] == "none"
    assert opened_paths == [
        knowledge_graph,
        knowledge_graph,
        memory_database,
        knowledge_graph,
    ]
    assert len(opened_connections) == 4
    for connection in opened_connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connection.execute("SELECT 1")
