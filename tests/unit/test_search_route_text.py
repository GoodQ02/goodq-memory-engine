"""Direct Text and unified Text ranking parity through registered callers."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import search
from retrieval.multimodal_search import MultimodalSearchEngine


@pytest.mark.parametrize("top_k", [5, 50])
def test_direct_text_uses_unified_candidate_pool_and_ranking(tmp_path, monkeypatch, top_k):
    cfg = {"paths": {"data_root": str(tmp_path)}, "identity_search": {"enabled": False},
           "observability": {"retrieval_events": {"enabled": False, "jsonl_fallback": False}}}
    engine = MultimodalSearchEngine(cfg)
    query = "scheduled infant checkup"
    hits = [{"id": i, "score": 1 - i * .01,
             "payload": {"video_id": "fixture", "scene_id": i}}
            for i in range(8)]
    hits[7]["payload"].update(tags=["scheduled", "infant", "checkup"], text=query)
    calls = []

    def retained_text_candidates(query, top_k, **kwargs):
        calls.append((top_k, kwargs["retrieval_context"]))
        return deepcopy(hits[:top_k])

    monkeypatch.setattr(engine, "search_text", retained_text_candidates)
    monkeypatch.setattr(engine, "search_visual", lambda *a, **kw: pytest.fail("Text invoked visual"))
    monkeypatch.setattr(engine, "search_audio", lambda *a, **kw: pytest.fail("Text invoked audio"))
    monkeypatch.setattr(search, "_config", cfg)
    monkeypatch.setattr(search, "_search_engine", engine)
    monkeypatch.setattr(search, "_data_loader", SimpleNamespace(
        list_processed_videos=lambda: [], get_video_metadata=lambda key: {}))
    client = TestClient(app, client=("127.0.0.1", 50000))
    engine._set_search_diagnostic("visual", status="unavailable", label="stale", reason="stale")
    direct = client.get("/api/search/text", params={"q": query, "top_k": top_k})
    unified = client.post("/api/search/multimodal", json={"query": query, "modalities": ["text"], "top_k": top_k})
    assert direct.status_code == unified.status_code == 200
    direct_body, unified_body = direct.json(), unified.json()
    assert direct_body["results"][0]["scene_id"] == 7
    assert direct_body["results"] == unified_body["results"]
    assert len(direct_body["results"]) == min(top_k, 8)
    assert calls == [(max(top_k, 5) * 2, "human.ui.search")] * 2
    assert "visual" not in (direct_body.get("diagnostics") or {})
    assert direct_body["modalities_searched"] == ["text"]
