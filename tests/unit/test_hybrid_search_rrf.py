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


def test_register_scene_bundle_summary_embedding_and_routing(monkeypatch: pytest.MonkeyPatch, temp_db_path: str) -> None:
    cfg = {
        "paths": {"db_path": temp_db_path},
        "qdrant": {
            "enabled": True,
            "host": "http://mock_qdrant",
            "collections": {
                "text": "goodq_text"
            }
        }
    }
    
    # Stub compute_file_hash to return dummy hashes
    import steps.common.memory as mem
    monkeypatch.setattr(mem, "compute_file_hash", lambda path: "dummy_hash_" + Path(path).name)

    # Mock _load_st
    class FakeST:
        def encode(self, texts, normalize_embeddings=True):
            return np.ones((len(texts), 384), dtype=np.float32)
    monkeypatch.setattr("steps.text_embed.step._load_st", lambda: FakeST())

    # Stub scene summarizer to return a summary
    import steps.common.scene_summarizer
    monkeypatch.setattr(steps.common.scene_summarizer, "generate_scene_summary", lambda *args, **kwargs: "Mock summary text")

    # Mock the router
    class FakeStore:
        def __init__(self, dim, index_path=None):
            self.dim = dim
            self.index_path = index_path
            self.inserted = []
        def insert(self, points):
            self.inserted.extend(points)
            return True

    class FakeRouter:
        def __init__(self):
            self.stores = {
                "qdrant": FakeStore(384),
                "faiss": FakeStore(384, "mock_faiss.index")
            }
        def insert(self, points):
            res = {}
            for k, store in self.stores.items():
                res[k] = store.insert(points)
            return res

    fake_router = FakeRouter()
    monkeypatch.setattr("steps.common.memory_manager.build_memory_router", lambda c: fake_router)

    # 1. Normal case: dimension matches 384
    # Mock Qdrant client to report 384 dim
    q_client = fake_router.stores["qdrant"]
    class FakeQClient:
        def __init__(self):
            self.cfg = type("Cfg", (), {"host": "http://mock_qdrant", "collection": "goodq_text", "enabled": True})()
            class FakeSession:
                def get(self, url, timeout=None):
                    pass
            self.session = FakeSession()
            self.upsert_called = []
        def upsert(self, points):
            self.upsert_called.extend(points)
            return True
            
    fake_q_client = FakeQClient()
    q_client.client = fake_q_client
    
    # Mock session.get to return 200 with dim=384
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"result": {"config": {"params": {"vectors": {"size": 384}}}}}
    monkeypatch.setattr(fake_q_client.session, "get", lambda url, timeout=None: FakeResponse())

    # Register scene bundle
    bundle = {
        "video_hash": "test_video_summary",
        "scene": {"start": 0.0, "end": 10.0, "index": 1},
        "scene_id": "scene_summary_01"
    }

    res = register_scene_bundle(
        cfg,
        video_hash=bundle["video_hash"],
        scene=bundle["scene"],
        scene_id=bundle["scene_id"]
    )

    # Verify summary vector is appended in normal points
    inserted_points = fake_router.stores["qdrant"].inserted
    summary_point = next((p for p in inserted_points if p["id"] == "scene_summary_01_summary"), None)
    assert summary_point is not None
    assert summary_point["vector"] == [1.0] * 384
    assert summary_point["payload"]["text"] == "Mock summary text"

    # Verify SQLite row exists in embeddings table
    conn = sqlite3.connect(temp_db_path)
    cur = conn.execute("SELECT hash, modality, scene_id FROM embeddings WHERE hash='scene_summary_01_summary'")
    row = cur.fetchone()
    assert row is not None
    assert row[1] == "text"
    assert row[2] == "scene_summary_01"
    
    # Verify MemoryCommitEvent table contains the event
    cur = conn.execute("SELECT scene_id, modality, embedding_id, targets_json FROM memory_commit_events WHERE embedding_id='scene_summary_01_summary'")
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "scene_summary_01"
    assert row[1] == "text"
    targets = json.loads(row[3])
    assert targets["qdrant"]["committed"] is True
    assert targets["faiss"]["committed"] is True
    conn.close()

    # 2. Mismatch case: dimension matches 512 (mismatch!)
    fake_router_mismatch = FakeRouter()
    monkeypatch.setattr("steps.common.memory_manager.build_memory_router", lambda c: fake_router_mismatch)

    q_client_m = fake_router_mismatch.stores["qdrant"]
    fake_q_client_m = FakeQClient()
    q_client_m.client = fake_q_client_m
    
    # Mock session.get to return 200 with dim=512
    class FakeResponseMismatch:
        status_code = 200
        def json(self):
            return {"result": {"config": {"params": {"vectors": {"size": 512}}}}}
    monkeypatch.setattr(fake_q_client_m.session, "get", lambda url, timeout=None: FakeResponseMismatch())

    # Mock build_qdrant_client to return a mock client for fallback collection
    fallback_q_client = FakeQClient()
    monkeypatch.setattr("steps.common.qdrant_client.build_qdrant_client", lambda c, dim, key: fallback_q_client)

    bundle_m = {
        "video_hash": "test_video_summary",
        "scene": {"start": 0.0, "end": 10.0, "index": 2},
        "scene_id": "scene_summary_02"
    }

    res_m = register_scene_bundle(
        cfg,
        video_hash=bundle_m["video_hash"],
        scene=bundle_m["scene"],
        scene_id=bundle_m["scene_id"]
    )

    # Verify summary vector is NOT in standard inserted points (since it was mismatch and routed to fallback)
    inserted_points_m = fake_router_mismatch.stores["qdrant"].inserted
    summary_point_m = next((p for p in inserted_points_m if p["id"] == "scene_summary_02_summary"), None)
    assert summary_point_m is None

    # Verify summary vector was routed to fallback client's upsert
    assert len(fallback_q_client.upsert_called) == 1
    assert fallback_q_client.upsert_called[0]["id"] == "scene_summary_02_summary"
    assert fallback_q_client.upsert_called[0]["vector"] == [1.0] * 384

    # Verify MemoryCommitEvent specifies fallback target
    conn = sqlite3.connect(temp_db_path)
    cur = conn.execute("SELECT targets_json FROM memory_commit_events WHERE embedding_id='scene_summary_02_summary'")
    row = cur.fetchone()
    assert row is not None
    targets_m = json.loads(row[0])
    assert "qdrant_fallback" in targets_m
    assert targets_m["qdrant_fallback"]["committed"] is True
    conn.close()
