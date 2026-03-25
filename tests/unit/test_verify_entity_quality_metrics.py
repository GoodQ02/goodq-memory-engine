from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.internal import verify_entity_quality as quality


def test_fetch_memory_taxonomy_collects_nested_scene_tokens(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE scenes (
                id TEXT PRIMARY KEY,
                video_hash TEXT,
                start REAL,
                end REAL,
                meta TEXT,
                created_at TEXT
            )
            """
        )
        meta = {
            "tags": ["Apartment"],
            "entities": ["Jerry"],
            "keyframe": {"tags": ["Comedy"], "entities": ["George"]},
            "audio": {"tags": ["Stand-up"], "entities": ["Elaine"]},
        }
        conn.execute(
            "INSERT INTO scenes(id, video_hash, start, end, meta, created_at) VALUES (?,?,?,?,?,?)",
            ("scene-1", "video-1", 0.0, 8.0, json.dumps(meta), "2026-03-24T12:00:00"),
        )
        conn.commit()

        taxonomy = quality._fetch_memory_taxonomy(conn, limit=10)
    finally:
        conn.close()

    assert taxonomy["tags"] == ["Apartment", "Comedy", "Stand-up"]
    assert taxonomy["entities"] == ["Jerry", "George", "Elaine"]


def test_tally_tokens_dedupes_by_normalized_key():
    rows = quality._tally_tokens(["Jerry", "jerry", "George", "Jerry!"], limit=10)
    assert rows[0] == {"label": "Jerry", "count": 3}
    assert rows[1] == {"label": "George", "count": 1}


def test_find_stopword_tokens_detects_semantic_leakage():
    offenders = quality._find_stopword_tokens(["I'm", "Jerry", "Well", "Apartment"])
    assert offenders == ["I'm", "Well"]
