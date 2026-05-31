from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pytest

from steps.common.memory import _connect, register_scene_bundle
from retrieval.multimodal_search import MultimodalSearchEngine


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        Path(path).unlink()
    except OSError:
        pass


def test_sqlite_migration_is_idempotent(temp_db_path: str) -> None:
    # First connection runs migrations
    conn1 = _connect(temp_db_path)
    
    # Check tables exist
    cur = conn1.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    assert "schema_migrations" in tables
    assert "scene_text_fts" in tables

    # Check migration tracking record exists
    cur = conn1.execute("SELECT name, applied_at FROM schema_migrations")
    migrations = cur.fetchall()
    assert len(migrations) == 1
    assert migrations[0][0] == "create_scene_text_fts"
    conn1.close()

    # Second connection should run without error (idempotency check)
    conn2 = _connect(temp_db_path)
    cur = conn2.execute("SELECT name FROM schema_migrations")
    assert len(cur.fetchall()) == 1
    conn2.close()


def test_register_scene_bundle_populates_fts(temp_db_path: str) -> None:
    cfg = {"paths": {"db_path": temp_db_path}}
    
    # Ensure tables exist
    conn = _connect(temp_db_path)
    conn.close()

    # Register scene bundle with frame OCR and audio transcript
    bundle = {
        "video_hash": "test_video_123",
        "scene": {"start": 10.0, "end": 20.0, "index": 1, "confidence": 0.95},
        "scene_id": "scene_001",
        "frame": {
            "path": "dummy_frame.jpg",
            "data": {
                "ocr_text": "Welcome to the demonstration",
                "caption": "A demonstration video keyframe"
            }
        },
        "audio": {
            "path": "dummy_audio.wav",
            "data": {
                "transcript": "Hello and welcome to the show",
                "speaker_transcript": [
                    {"start": 10.5, "end": 15.0, "speaker": "SPEAKER_00", "text": "Hello and welcome"},
                    {"start": 15.1, "end": 19.5, "speaker": "SPEAKER_01", "text": "to the show"}
                ]
            }
        }
    }

    # Stub compute_file_hash to return dummy hashes
    import steps.common.memory as mem
    mem.compute_file_hash = lambda path: "dummy_hash_" + Path(path).name

    register_scene_bundle(
        cfg,
        video_hash=bundle["video_hash"],
        scene=bundle["scene"],
        scene_id=bundle["scene_id"],
        frame=bundle["frame"],
        audio=bundle["audio"]
    )

    # Verify database contents
    conn = sqlite3.connect(temp_db_path)
    try:
        cur = conn.execute("SELECT scene_id, content_type, text FROM scene_text_fts ORDER BY content_type")
        rows = cur.fetchall()
        assert len(rows) == 2
        # Row 1: ocr text
        assert len(rows[0][0]) == 64
        assert rows[0][1] == "ocr"
        assert rows[0][2] == "Welcome to the demonstration"

        # Row 2: transcript text
        assert len(rows[1][0]) == 64
        assert rows[1][1] == "transcript"
        assert rows[1][2] == "Hello and welcome to the show"
    finally:
        conn.close()


def test_reciprocal_rank_fusion() -> None:
    engine = MultimodalSearchEngine({"paths": {"db_path": ":memory:"}})
    
    # Run 1: Semantic results
    run1 = [
        {"id": "doc1", "score": 0.9, "payload": {"text": "apple banana"}},
        {"id": "doc2", "score": 0.8, "payload": {"text": "banana cherry"}},
        {"id": "doc3", "score": 0.7, "payload": {"text": "cherry grape"}},
    ]
    
    # Run 2: FTS lexical results (different order)
    run2 = [
        {"id": "doc2", "score": 10.0, "payload": {"text": "banana cherry"}},
        {"id": "doc1", "score": 5.0, "payload": {"text": "apple banana"}},
        {"id": "doc4", "score": 1.0, "payload": {"text": "grape orange"}},
    ]

    # Reciprocal Rank Fusion (k = 60)
    # doc1: rank 1 in run1 (1/61), rank 2 in run2 (1/62). Total = 1/61 + 1/62 = 0.03252
    # doc2: rank 2 in run1 (1/62), rank 1 in run2 (1/61). Total = 1/62 + 1/61 = 0.03252
    # doc3: rank 3 in run1 (1/63), not in run2. Total = 1/63 = 0.01587
    # doc4: not in run1, rank 3 in run2. Total = 1/63 = 0.01587
    # Since doc1 and doc2 both appear first and second, their fused score should be identical and top-ranked
    
    fused = engine.reciprocal_rank_fusion([run1, run2], k=60, top_k=4)
    
    assert len(fused) == 4
    assert fused[0]["id"] in ("doc1", "doc2")
    assert fused[1]["id"] in ("doc1", "doc2")
    
    # Normalized score of doc1 and doc2 (1st in one run, 2nd in another) is (1/61 + 1/62) / (2/61) = 0.991935
    assert fused[0]["score"] == pytest.approx(0.991935, abs=1e-5)
    assert fused[1]["score"] == pytest.approx(0.991935, abs=1e-5)
    
    # doc3 rank is 3. Normalized score is (1/63) / (2/61) = 61 / 126 = 0.4841
    assert fused[2]["score"] == pytest.approx(0.4841, abs=1e-4)


def test_fts_fallback_search(temp_db_path: str) -> None:
    # Create DB and tables
    conn = _connect(temp_db_path)
    
    # Insert mock records directly
    now = "2026-05-31T12:00:00"
    conn.execute(
        "INSERT INTO scenes(id, video_hash, start, end, meta, created_at) VALUES (?,?,?,?,?,?)",
        ("scene_01", "v_01", 0.0, 5.0, "{}", now),
    )
    conn.execute(
        "INSERT INTO scene_text_fts(scene_id, video_hash, content_type, text) VALUES (?,?,?,?)",
        ("scene_01", "v_01", "transcript", "how is Uncle Tony doing"),
    )
    conn.commit()
    conn.close()

    engine = MultimodalSearchEngine({"paths": {"db_path": temp_db_path}})
    
    # Exact keyword search
    results = engine.search_fts("Uncle Tony", top_k=5)
    assert len(results) == 1
    assert results[0]["id"] == "scene_01"
    assert results[0]["payload"]["text"] == "how is Uncle Tony doing"
    assert results[0]["payload"]["video_hash"] == "v_01"


def test_search_text_hybrid_blend(monkeypatch: pytest.MonkeyPatch, temp_db_path: str) -> None:
    engine = MultimodalSearchEngine({"paths": {"db_path": temp_db_path}})

    # Mock Qdrant client query to return semantic matches
    class FakeQdrantClient:
        def query(self, vector, top_k):
            return [
                {"id": "scene_01", "score": 0.85, "payload": {"scene_id": "scene_01", "text": "Tony at the dinner table"}}
            ]

    monkeypatch.setattr(engine, "_get_qdrant_client", lambda coll: FakeQdrantClient())
    monkeypatch.setattr(engine, "encode_text_query", lambda query: np.ones(384, dtype=np.float32))

    # Mock search_fts to return lexical matches
    monkeypatch.setattr(
        engine,
        "search_fts",
        lambda query, top_k: [
            {"id": "scene_02", "score": 1.0, "payload": {"scene_id": "scene_02", "text": "Uncle Tony eating pasta"}}
        ]
    )

    # Executing hybrid text search
    fused_results = engine.search_text("Tony", top_k=5)

    # RRF fuses both semantic (scene_01) and lexical (scene_02)
    assert len(fused_results) == 2
    assert {r["id"] for r in fused_results} == {"scene_01", "scene_02"}
