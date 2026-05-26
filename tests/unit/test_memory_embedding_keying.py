from __future__ import annotations

import sqlite3
from pathlib import Path


def _rows(db_path: Path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT hash, faiss_id, source_path, modality, scene_id FROM embeddings ORDER BY modality"
        ).fetchall()
    finally:
        conn.close()


def test_embeddings_preserve_same_hash_across_modalities_in_new_db(tmp_path: Path) -> None:
    from steps.common.memory import upsert_embedding

    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}}
    source_path = "episode-audio.wav"
    shared_hash = "abc123"

    upsert_embedding(cfg, shared_hash, 101, source_path, "audio", scene_id="scene_0001")
    upsert_embedding(cfg, shared_hash, None, source_path, "audio_transcript", scene_id="scene_0001")

    rows = _rows(db_path)

    assert rows == [
        (shared_hash, 101, source_path, "audio", "scene_0001"),
        (shared_hash, None, source_path, "audio_transcript", "scene_0001"),
    ]


def test_embeddings_legacy_table_avoids_cross_modality_overwrite(tmp_path: Path) -> None:
    from steps.common.memory import upsert_embedding

    db_path = tmp_path / "legacy_memory.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE embeddings (
                hash TEXT NOT NULL PRIMARY KEY,
                faiss_id INTEGER,
                source_path TEXT,
                modality TEXT,
                scene_id TEXT,
                created_at TEXT,
                sentiment_label TEXT,
                sentiment_score REAL,
                emotions_json TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    cfg = {"paths": {"db_path": str(db_path)}}
    source_path = "episode-audio.wav"
    shared_hash = "abc123"

    upsert_embedding(cfg, shared_hash, 101, source_path, "audio", scene_id="scene_0001")
    upsert_embedding(cfg, shared_hash, None, source_path, "audio_transcript", scene_id="scene_0001")

    rows = _rows(db_path)

    assert len(rows) == 2
    assert rows[0] == (shared_hash, 101, source_path, "audio", "scene_0001")
    assert rows[1] == (f"{shared_hash}:audio_transcript", None, source_path, "audio_transcript", "scene_0001")
