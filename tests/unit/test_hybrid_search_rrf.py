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
    orig_compute_file_hash = mem.compute_file_hash
    mem.compute_file_hash = lambda path: "dummy_hash_" + Path(path).name if path else None

    try:
        register_scene_bundle(
            cfg,
            video_hash=bundle["video_hash"],
            scene=bundle["scene"],
            scene_id=bundle["scene_id"],
            frame=bundle["frame"],
            audio=bundle["audio"]
        )
    finally:
        mem.compute_file_hash = orig_compute_file_hash

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


def test_rrf_combines_artifacts_with_fts_once_per_scene():
    engine = MultimodalSearchEngine({"paths": {"db_path": ":memory:"}})
    def hit(point, scene, video="v", **extra):
        return {"id": point, "payload": {"scene_id": scene, "video_hash": video, **extra}}
    semantic = [hit("point-1", "a"), hit("point-2", "a"), hit("point-3", "b")]
    lexical = [hit("b", "b", text="exact transcript"), hit("b", "b"), hit("a", "a")]
    result = engine.reciprocal_rank_fusion([semantic, lexical], top_k=10)
    assert len(result) == 2
    assert {r["payload"]["scene_id"] for r in result} == {"a", "b"}
    assert all(r["score"] == pytest.approx((1/61 + 1/62)/(2/61)) for r in result)
    assert next(r for r in result if r["payload"]["scene_id"] == "b")["payload"]["text"] == "exact transcript"
    separate = engine.reciprocal_rank_fusion([[hit("p", "0", "v1"), hit("q", "0", "v2")]])
    assert len(separate) == 2


def test_search_text_hybrid_blend(monkeypatch: pytest.MonkeyPatch, temp_db_path: str) -> None:
    engine = MultimodalSearchEngine({"paths": {"db_path": temp_db_path}})

    # Mock Qdrant client query to return semantic matches
    class FakeQdrantClient:
        def query(self, vector, top_k, **kwargs):
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
    fused_results = engine.search_text(
        "Tony",
        top_k=5,
        retrieval_context="system.healthcheck",
    )

    # RRF fuses both semantic (scene_01) and lexical (scene_02)
    assert len(fused_results) == 2
    assert {r["id"] for r in fused_results} == {"scene_01", "scene_02"}


def test_document_chunks_preserve_best_passage_and_distinct_sources_through_search(monkeypatch):
    engine = MultimodalSearchEngine({"paths": {"db_path": ":memory:"}})
    passage = {"chunk_index": 25, "char_start": 900, "char_end": 911,
               "text": "late answer", "token_count": 2}
    hits = [{"id": f"point-{i}", "score": 0.95 - i / 1000,
             "payload": {"scene_id": "long-scene", "video_id": "long-pdf",
                         "source_kind": "document", "document_chunk": {**passage, "chunk_index": i}}}
            for i in range(80)]
    hits.append({"id": "other-point", "score": 0.8,
                 "payload": {"scene_id": "other-scene", "video_id": "other-pdf",
                             "source_kind": "document", "document_chunk": passage}})
    pulls = []
    class Client:
        def query(self, vector, top_k, **kwargs):
            pulls.append((top_k, kwargs))
            return hits[:top_k]
    monkeypatch.setattr(engine, "_get_qdrant_client", lambda collection: Client())
    monkeypatch.setattr(engine, "encode_text_query", lambda query: np.ones(384))
    monkeypatch.setattr(engine, "search_fts", lambda query, top_k: [
        {"id": "long-scene", "payload": {"video_id": "long-pdf", "scene_id": "long-scene",
                                              "text": "complete document lexical text"}}])
    results = engine.search_multimodal("late answer", top_k=2, modalities=["text"],
                                      retrieval_context="human.ui.search")
    assert {item["payload"]["video_id"] for item in results} == {"long-pdf", "other-pdf"}
    matched = next(item for item in results if item["payload"]["video_id"] == "long-pdf")
    assert matched["payload"]["document_chunk"] == {**passage, "chunk_index": 0}
    assert len(pulls) > 1
    assert max(limit for limit, _ in pulls) <= 4096
    assert all(options["retrieval_context"] == "human.ui.search" for _, options in pulls)
    assert all(options["payload_filter"]["must"] == [
        {"key": "ucf_promotion_status", "match": {"value": "promoted"}}] for _, options in pulls)


def test_multimodal_fusion_retains_text_passage_when_other_modality_wins(monkeypatch):
    engine = MultimodalSearchEngine({"paths": {"db_path": ":memory:"}})
    passage = {"chunk_index": 3, "char_start": 50, "char_end": 56,
               "text": "answer", "token_count": 1}
    payload = {"video_id": "pdf", "scene_id": "scene", "source_kind": "document"}
    monkeypatch.setattr(engine, "search_text", lambda *args, **kwargs: [
        {"score": 0.1, "payload": {**payload, "document_chunk": passage}}])
    monkeypatch.setattr(engine, "search_visual", lambda *args, **kwargs: [
        {"score": 1.0, "payload": payload}])
    result = engine.search_multimodal("answer", top_k=1, modalities=["text", "visual"],
                                     retrieval_context="human.ui.search")[0]
    assert result["payload"]["document_chunk"] == passage


def test_literal_document_search_uses_matching_retained_passage_not_semantic_sibling(monkeypatch, temp_db_path):
    text = "General relaxation. Controlled breathing and palliative\nimagination reduce tension."
    conn = _connect(temp_db_path)
    conn.execute("INSERT INTO scenes(id,video_hash,start,end,meta,created_at) VALUES (?,?,?,?,?,?)",
                 ("document-scene", "pdf", 0, 0, '{"source_kind":"document"}', "2026-10-15"))
    conn.execute("INSERT INTO scene_text_fts(scene_id,video_hash,content_type,text) VALUES (?,?,?,?)",
                 ("document-scene", "pdf", "document_text", text))
    conn.commit()
    conn.close()
    engine = MultimodalSearchEngine({"paths": {"db_path": temp_db_path}})
    def hit(index, start, end, score):
        return {"id": f"point-{index}", "score": score, "payload": {
            "video_id": "pdf", "scene_id": "document-scene", "source_kind": "document",
            "document_chunk": {"chunk_index": index, "char_start": start, "char_end": end,
                               "text": text[start:end], "token_count": 10}}}
    semantic = [hit(0, 0, 20, .8), hit(1, 20, len(text), .4)]
    class Client:
        def query(self, *args, **kwargs):
            return semantic
    monkeypatch.setattr(engine, "_get_qdrant_client", lambda collection: Client())
    monkeypatch.setattr(engine, "encode_text_query", lambda query: np.ones(384))
    result = engine.search_multimodal("PALLIATIVE imagination", top_k=1, modalities=["text"],
                                     retrieval_context="human.ui.search")[0]
    assert result["id"] == "point-1"
    assert result["payload"]["document_chunk"] == semantic[1]["payload"]["document_chunk"]
    assert "palliative\nimagination" in result["payload"]["document_chunk"]["text"]
    assert len(engine.search_multimodal("PALLIATIVE imagination", top_k=1, modalities=["text"],
                                       retrieval_context="human.ui.search")) == 1
    # A paraphrase retains model order; exact-match projection must not become a
    # source-specific relevance heuristic or invent a span from the full text.
    assert engine.search_multimodal("How do people relax?", top_k=1, modalities=["text"],
                                    retrieval_context="human.ui.search")[0]["id"] == "point-0"


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


class _PassageTokenizer:
    def __call__(self, text, **kwargs):
        import re
        offsets = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        return {"input_ids": list(range(len(offsets))), "offset_mapping": offsets}


class _PassageEncoder:
    tokenizer = _PassageTokenizer()

    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        if self.failure == "raise":
            raise RuntimeError("encoder failed")
        scores = [.99 if "bibliography" in t else .95 if "unreported" in t else .5 for t in texts]
        vectors = np.array([[v, np.sqrt(1-v*v)] for v in scores])
        if self.failure == "nan":
            vectors[0, 0] = np.nan
        elif self.failure == "shape":
            vectors = vectors[:, :1]
        elif self.failure == "zero":
            vectors[:] = 0
        elif self.failure == "overflow":
            vectors[:] = 1e300
        return vectors


def _passage_hit(index, text, source="a", **metadata):
    return {"id": f"{source}-{index}", "score": .9-index/1000, "payload": {
        "scene_id": f"scene-{source}", "video_id": source, "source_kind": "document",
        "document_chunk": {"chunk_index": index, "char_start": index*10000,
                           "char_end": index*10000+len(text), "text": text,
                           "token_count": len(text.split())}, **metadata}}


def _passage_engine(monkeypatch, hits, failure=None):
    engine = MultimodalSearchEngine({"paths": {"db_path": ":memory:"}})
    model = _PassageEncoder(failure)
    engine._text_model = model
    class Client:
        def query(self, vector, top_k, **kwargs):
            return hits[:top_k]
    monkeypatch.setattr(engine, "_get_qdrant_client", lambda collection: Client())
    monkeypatch.setattr(engine, "encode_text_query", lambda query: np.array([1., 0.]))
    monkeypatch.setattr(engine, "search_fts", lambda query, top_k: [])
    return engine, model


def test_combined_passage_ranking_preserves_source_order_metadata_and_exact_evidence(monkeypatch):
    hits = [_passage_hit(0, "table of intervention results"),
            _passage_hit(0, "unrelated source", source="b", text_preview="unreported persistence"),
            _passage_hit(1, "bibliography of effects"),
            _passage_hit(2, "effect size and persistence remain unreported", entities=["unreported", "persistence"])]
    engine, model = _passage_engine(monkeypatch, hits)
    result = engine.search_multimodal("unreported persistence", top_k=2, modalities=["text"],
                                      retrieval_context="human.ui.search")
    # Document preview metadata must not overturn the evidence-based source rank.
    assert [r["payload"]["video_id"] for r in result] == ["a", "b"]
    selected = result[0]
    assert selected["payload"]["document_chunk"] == hits[3]["payload"]["document_chunk"]
    assert selected["id"] == "a-0"
    assert "entities" not in selected["payload"]
    assert selected["score"] == pytest.approx(.5)
    assert model.calls and all(len(t.split()) <= 96 for t in model.calls[0][0])


def test_document_lexical_windows_match_terminal_s_variants(monkeypatch):
    hits = [_passage_hit(0, "configuration guidance and model recovery"),
            _passage_hit(1, "No downloads or configuration rewrites are authorized.")]
    engine, _ = _passage_engine(monkeypatch, hits)
    results = engine.search_multimodal("download and rewrite configuration", top_k=1,
        modalities=["text"], retrieval_context="human.ui.search")
    assert results[0]["payload"]["document_chunk"] == hits[0]["payload"]["document_chunk"]
    assert results[0]["payload"]["document_lexical_chunk"] == hits[1]["payload"]["document_chunk"]


def test_document_metadata_does_not_override_retrieval_but_video_keeps_bonus(monkeypatch):
    engine, _ = _passage_engine(monkeypatch, [])
    payload = {"entities": ["database"], "text_preview": "database database"}
    assert engine._metadata_bonus("database", {**payload, "source_kind": "document"}) == 0
    assert engine._metadata_bonus("database", {**payload, "content_type": "document_text"}) == 0
    assert engine._metadata_bonus("database", {**payload, "source_kind": "video"}) > 0


@pytest.mark.parametrize("failure", ["raise", "nan", "shape", "zero", "overflow"])
def test_passage_encoder_failure_keeps_original_search_and_reports_fallback(monkeypatch, failure):
    hits = [_passage_hit(0, "table results"), _passage_hit(1, "unreported persistence")]
    engine, _ = _passage_engine(monkeypatch, hits, failure)
    result = engine.search_multimodal("unreported persistence", top_k=1, modalities=["text"],
                                      retrieval_context="human.ui.search")
    assert result[0]["payload"]["document_chunk"] == hits[0]["payload"]["document_chunk"]
    assert engine.last_search_diagnostics()["text_passages"]["status"] == "fallback"


def test_passage_ranking_budget_is_global_across_documents(monkeypatch):
    hits = [_passage_hit(i, " ".join([f"word{i}"]*254), source=str(i//2)) for i in range(40)]
    engine, model = _passage_engine(monkeypatch, hits)
    result = engine.search_multimodal("unreported persistence", top_k=20, modalities=["text"],
                                      retrieval_context="human.ui.search")
    assert len(result) == 20
    windows = [t for texts, _ in model.calls for t in texts]
    assert windows and len(windows) <= 192
    assert all(len(t.split()) <= 96 for t in windows)
    assert not any("word32" in t for t in windows)
    assert engine.last_search_diagnostics()["text_passages"]["status"] == "limited"


def test_literal_passage_override_wins_combined_ranking(monkeypatch):
    hits = [_passage_hit(0, "table results"), _passage_hit(1, "bibliography unreported persistence"),
            _passage_hit(2, "unreported persistence remains unknown")]
    engine, _ = _passage_engine(monkeypatch, hits)
    monkeypatch.setattr(engine, "search_fts", lambda query, top_k: [{"id": "scene-a", "payload": {
        "scene_id": "scene-a", "video_id": "a", "content_type": "document_text", "text": "full document"}}])
    result = engine.search_multimodal("remains unknown", top_k=1, modalities=["text"],
                                      retrieval_context="human.ui.search")
    assert result[0]["payload"]["document_chunk"] == hits[2]["payload"]["document_chunk"]
    assert result[0]["id"] == "a-2"


def test_scalar_text_search_does_not_encode_passage_windows(monkeypatch):
    hits = [{"id": "scalar", "score": .9, "payload": {"scene_id": "scene", "text": "transcript"}}]
    engine, model = _passage_engine(monkeypatch, hits)
    result = engine.search_multimodal("unreported persistence", top_k=1, modalities=["text"],
                                      retrieval_context="human.ui.search")
    assert result[0]["id"] == "scalar"
    assert not model.calls
    assert "text_passages" not in engine.last_search_diagnostics()


def test_direct_text_search_clears_previous_passage_diagnostic(monkeypatch):
    hits = [_passage_hit(0, "table results"), _passage_hit(1, "unreported persistence")]
    engine, _ = _passage_engine(monkeypatch, hits, "raise")
    engine.search_text("unreported persistence", retrieval_context="human.ui.search")
    assert engine.last_search_diagnostics()["text_passages"]["status"] == "fallback"
    hits[:] = [{"id": "scalar", "payload": {"scene_id": "scalar", "text": "transcript"}}]
    result = engine.search_text("unrelated query", retrieval_context="human.ui.search")
    assert result[0]["id"] == "scalar"
    assert "text_passages" not in engine.last_search_diagnostics()


@pytest.mark.parametrize("fault,reason", [
    ("query", "document_passage_input_limit"),
    ("characters", "document_passage_input_limit"),
    ("total_characters", "document_passage_input_limit"),
    ("offset", "invalid_document_chunk"),
    ("windows", "document_passage_window_limit"),
])
def test_passage_input_and_window_limits_fall_back_before_encoding(monkeypatch, fault, reason):
    hits = [_passage_hit(0, "table results"), _passage_hit(1, "unreported persistence")]
    query = "unreported persistence"
    if fault == "query":
        query = "x"*4097
    elif fault == "characters":
        hits[1] = _passage_hit(1, "x"*32769)
    elif fault == "total_characters":
        hits = [_passage_hit(i, "x"*32000) for i in range(9)]
    elif fault == "offset":
        hits[1]["payload"]["document_chunk"]["char_start"] = True
    else:
        hits = [_passage_hit(i, "word "*512) for i in range(32)]
    engine, model = _passage_engine(monkeypatch, hits)
    result = engine.search_multimodal(query, top_k=1, modalities=["text"],
                                      retrieval_context="human.ui.search")
    assert result[0]["payload"]["document_chunk"] == hits[0]["payload"]["document_chunk"]
    assert not model.calls
    diagnostic = engine.last_search_diagnostics()["text_passages"]
    assert diagnostic["status"] == "fallback"
    assert diagnostic["reason"] == reason
