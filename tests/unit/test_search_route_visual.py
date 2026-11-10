"""Visual search contract through registered API routes and the real engine."""
from contextlib import nullcontext
from pathlib import Path
import sys
import types

import numpy as np
import pytest
import requests
from fastapi.testclient import TestClient

from api.main import app
from api.routes import search
from api.utils.loaders import DataLoader
from retrieval.multimodal_search import MultimodalSearchEngine
from steps.common import qdrant_client


@pytest.fixture
def visual_api(tmp_path, monkeypatch):
    models = tmp_path / "models"
    snapshot = models / "hub/models--laion--CLIP-ViT-L-14-DataComp.XL-s13B-b90K/snapshots/84c9828e63dc9a9351d1fe637c346d4c1c4db341"
    snapshot.mkdir(parents=True)
    for name in ("config.json", "preprocessor_config.json", "pytorch_model.bin"):
        (snapshot / name).write_text("deterministic model fixture")
    state = {"error": None, "inference_error": False, "embedding": [1., 0., 0.],
             "status": 200, "result": [], "posts": [], "loads": [], "collection_status": 200}

    class Tensor:
        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.array([state["embedding"]], dtype=np.float32)

    class Model:
        @classmethod
        def from_pretrained(cls, source, **kwargs):
            state["loads"].append((source, kwargs))
            assert source == str(snapshot.resolve())
            assert kwargs["local_files_only"] is True
            if state["error"]:
                raise state["error"]
            if kwargs.get("use_safetensors") is True and not (snapshot / "model.safetensors").exists():
                raise OSError("No model.safetensors in pinned snapshot")
            return cls()

        def eval(self):
            return self

        def get_text_features(self, **kwargs):
            if state["inference_error"]:
                raise RuntimeError("private inference detail")
            return Tensor()

    class Processor:
        @classmethod
        def from_pretrained(cls, source, **kwargs):
            assert source == str(snapshot.resolve())
            assert kwargs == {"local_files_only": True}
            return cls()

        def __call__(self, **kwargs):
            return {"input_ids": [1]}

    class Response:
        def __init__(self, status, result):
            self.status_code = status
            self.result = result
            self.text = "fixture backend"

        def json(self):
            return {"result": self.result}

    class Session:
        def get(self, url, **kwargs):
            return Response(state["collection_status"], {})

        def post(self, url, *, json, **kwargs):
            state["posts"].append((url, json))
            if state["status"] == "offline":
                raise requests.ConnectionError("private connection detail")
            result = state["result"]
            if "fixture_text" in url:
                result = [{"id": 21, "score": .8, "payload": {"scene_id": 4, "video_id": "fixture", "text": "retained text match"}}]
            if isinstance(result, list):
                result = result[:json["limit"]]
            return Response(state["status"], result)

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(CLIPModel=Model, CLIPProcessor=Processor))
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(no_grad=nullcontext))
    monkeypatch.setattr(qdrant_client, "build_qdrant_session", lambda host: Session())
    monkeypatch.setattr(qdrant_client.time, "sleep", lambda seconds: None)
    cfg = {"paths": {"data_root": str(tmp_path), "processing": str(tmp_path / "processing"), "models_cache": str(models)},
           "qdrant": {"collections": {"clip": "fixture_clip", "text": "fixture_text"}, "embedding_dims": {"clip": 3, "text": 3}},
           "observability": {"retrieval_events": {"enabled": False, "jsonl_fallback": False}},
           "identity_search": {"enabled": False}}
    engine = MultimodalSearchEngine(cfg)
    monkeypatch.setattr(search, "_config", cfg)
    monkeypatch.setattr(search, "_search_engine", engine)
    monkeypatch.setattr(search, "_data_loader", DataLoader(processing_root=str(tmp_path / "processing")))
    return TestClient(app, client=("127.0.0.1", 50000)), engine, state, snapshot


def call_visual(client, method):
    if method == "GET":
        return client.get("/api/search/visual", params={"q": "red truck"})
    return client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["visual"]})


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("weights", ["pytorch_model.bin", "model.safetensors"])
def test_visual_api_loads_pinned_local_format_and_distinguishes_empty(visual_api, method, weights):
    client, engine, state, snapshot = visual_api
    (snapshot / weights).write_text("deterministic model fixture")
    response = call_visual(client, method)
    assert response.status_code == 200
    assert len(state["posts"]) == 1
    assert response.json()["diagnostics"]["visual"]["status"] == "no_results"
    assert response.json()["results"] == []
    assert state["posts"][0][1]["filter"] == {"must": [{"key": "ucf_promotion_status", "match": {"value": "promoted"}}]}


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("error,reason", [
    (OSError("private local model path"), "clip_model_load_failed"),
    (ValueError("torch.load requires torch version to at least v2.6 even with weights_only=True"), "torch_version_unsupported"),
])
def test_visual_api_reports_loader_failure_without_backend_call(visual_api, method, error, reason):
    client, engine, state, snapshot = visual_api
    state["error"] = error
    response = call_visual(client, method)
    assert response.status_code == 200
    diagnostic = response.json()["diagnostics"]["visual"]
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["reason"] == reason
    assert state["posts"] == []
    assert "private" not in response.text


def test_visual_api_missing_cache_and_prewarm_are_unavailable(visual_api, monkeypatch):
    client, engine, state, snapshot = visual_api
    (snapshot / "config.json").unlink()
    response = call_visual(client, "POST")
    assert response.json()["diagnostics"]["visual"]["reason"] == "model_not_cached"
    assert state["loads"] == state["posts"] == []
    monkeypatch.setattr(engine, "encode_text_query", lambda query: np.ones(3))
    monkeypatch.setattr(engine, "encode_text_for_audio_search", lambda query: np.ones(3))
    assert search.prewarm_search_engine() == {"text": True, "visual": False, "audio": True}


@pytest.mark.parametrize("fault", ["exception", "zero", "nan", "dimension"])
def test_visual_api_encoding_failure_never_queries_backend(visual_api, fault):
    client, engine, state, snapshot = visual_api
    (snapshot / "model.safetensors").write_text("fixture")
    state["inference_error"] = fault == "exception"
    state["embedding"] = {"zero": [0., 0., 0.], "nan": [float("nan"), 0., 0.], "dimension": [1., 0.]}.get(fault, [1., 0., 0.])
    response = call_visual(client, "POST")
    assert response.status_code == 200
    assert response.json()["diagnostics"]["visual"]["status"] == "error"
    assert state["posts"] == []
    assert "private" not in response.text


@pytest.mark.parametrize("fault", [503, "offline", "missing", "malformed"])
def test_visual_api_distinguishes_backend_failure_from_empty(visual_api, fault):
    client, engine, state, snapshot = visual_api
    (snapshot / "model.safetensors").write_text("fixture")
    if fault == "missing":
        state["collection_status"] = 404
    elif fault == "malformed":
        state["result"] = {"unexpected": "response"}
    else:
        state["status"] = fault
    response = call_visual(client, "POST")
    assert response.status_code == 200
    diagnostic = response.json()["diagnostics"]["visual"]
    assert diagnostic["status"] in {"error", "unavailable"}
    assert diagnostic["reason"] != "qdrant_visual_search_empty"


def test_visual_api_success_clears_previous_failure_and_get_has_only_visual_diagnostics(visual_api):
    client, engine, state, snapshot = visual_api
    state["error"] = OSError("transient load failure")
    assert call_visual(client, "POST").json()["diagnostics"]["visual"]["status"] == "unavailable"
    state["error"] = None
    state["result"] = [{"id": 19, "score": .9, "payload": {"scene_id": 4, "video_id": "fixture"}}]
    engine._set_search_diagnostic("audio", status="unavailable", label="old", reason="old")
    result = call_visual(client, "GET").json()
    assert result["total_results"] == 1
    assert result["results"][0]["scene_id"] == 4
    assert set(result["diagnostics"]) == {"visual", "visual_captions"}
    assert result["diagnostics"]["visual_captions"]["status"] == "fallback"
    assert result["diagnostics"]["visual"]["status"] == "ready"


def test_mixed_search_retains_text_matches_when_visual_loader_fails(visual_api, monkeypatch):
    client, engine, state, snapshot = visual_api
    state["error"] = OSError("private failed model path")
    monkeypatch.setattr(engine, "encode_text_query", lambda query: np.array([1., 0., 0.]))
    result = client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["text", "visual"]}).json()
    assert result["total_results"] == 1
    assert result["results"][0]["modality"] == "text"
    assert result["diagnostics"]["visual"]["status"] == "unavailable"


def test_requested_visual_with_zero_weight_reports_disabled(visual_api):
    client, engine, state, snapshot = visual_api
    engine.weight_visual = 0
    result = call_visual(client, "POST").json()
    assert result["diagnostics"]["visual"]["status"] == "disabled"
    assert state["loads"] == state["posts"] == []


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_visual_limit_counts_scenes_and_preserves_best_hit(visual_api, monkeypatch, method):
    client, engine, state, _ = visual_api
    monkeypatch.setattr(search, "_data_loader", types.SimpleNamespace())
    # More than two points per scene requires expanding the candidate request.
    state["result"] = [
        {"id": i, "score": 1 - i / 100, "payload": {"scene_id": 0, "video_id": "first"}}
        for i in range(12)
    ] + [
        {"id": 12, "score": .8, "payload": {"scene_id": 0, "video_id": "second"}},
        {"id": 13, "score": .7, "payload": {"scene_id": 1, "video_id": "first"}},
        {"id": 14, "score": .6, "payload": {"scene_id": 2, "video_id": "first"}},
        {"id": 15, "score": .5, "payload": {"scene_id": 3, "video_id": "first"}},
    ]
    if method == "GET":
        response = client.get("/api/search/visual", params={"q": "red truck", "top_k": 5})
    else:
        response = client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["visual"], "top_k": 5})
    assert response.status_code == 200
    results = response.json()["results"]
    assert [(r["video_id"], r["scene_id"]) for r in results] == [
        ("first", 0), ("second", 0), ("first", 1), ("first", 2), ("first", 3),
    ]
    weight = 1 if method == "GET" else engine.weight_visual
    assert [r["score"] for r in results] == pytest.approx([s * weight for s in [1, .8, .7, .6, .5]])
    assert all(body["filter"] == {"must": [{"key": "ucf_promotion_status", "match": {"value": "promoted"}}]}
               for _, body in state["posts"])
    assert [body["limit"] for _, body in state["posts"]] == ([100] if method == "GET" else [200])


def test_visual_duplicate_budget_reports_partial_results(visual_api, monkeypatch):
    client, engine, state, _ = visual_api
    monkeypatch.setattr(search, "_data_loader", types.SimpleNamespace())
    state["result"] = [
        {"id": i, "score": 1 - i / 1000, "payload": {"scene_id": "same", "video_id": "first"}}
        for i in range(500)
    ]
    response = client.get("/api/search/visual", params={"q": "red truck", "top_k": 5})
    assert response.status_code == 200
    assert response.json()["total_results"] == 1
    assert response.json()["diagnostics"]["visual"]["reason"] == "visual_scene_candidate_limit"
    assert response.json()["diagnostics"]["visual"]["status"] == "limited"
    assert [body["limit"] for _, body in state["posts"]] == [100, 200, 400]


@pytest.fixture
def caption_api(visual_api, monkeypatch):
    client, engine, state, snapshot = visual_api
    # Scene zero and identical scene IDs in other sources must stay distinct.
    segments = [{"scene_id": i, "visual_caption": f"caption {i}",
                 "caption_meta": {"status": "ok", "sample_timestamp": i + .5, "is_midpoint_sample": True}}
                for i in range(55)]
    timeline = {"video_id": "fixture", "segments": segments}
    loader = search.get_data_loader()
    monkeypatch.setattr(loader, "list_processed_videos", lambda: ["fixture"])
    monkeypatch.setattr(loader, "load_temporal_index", lambda key: timeline)
    monkeypatch.setattr(loader, "get_video_metadata", lambda key: {})
    monkeypatch.setattr(loader, "is_search_result_active", lambda payload: payload.get("scene_id") != 54)
    state["result"] = [{"id": i, "score": .9 - i / 1000,
                        "payload": {"video_id": "fixture", "scene_id": i}} for i in range(55)]
    state["encoded"] = []

    class Encoder:
        def encode(self, texts, **kwargs):
            state["encoded"].append(texts)
            # Scene 5 is a real miss at CLIP rank 6, caption rank 1.
            return np.array([[1., 0.] if text in {"red truck", "caption 5"} else [0., 1.]
                             for text in texts])

    engine._text_model = Encoder()
    return client, engine, state, timeline


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_midpoint_ranking_through_api_recovers_clip_miss_and_retains_provenance(caption_api, method):
    client, engine, state, timeline = caption_api
    if method == "GET":
        response = client.get("/api/search/visual", params={"q": "red truck", "top_k": 5})
    else:
        response = client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["visual"], "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"]["visual_captions"]["candidates"] == 50
    assert len(body["results"]) == 5
    recovered = next(r for r in body["results"] if r["scene_id"] == 5)
    proof = recovered["visual_ranking"]
    assert proof["clip_rank"] == 6 and proof["caption_rank"] == 1
    assert proof["clip_score"] == pytest.approx(.895)
    assert proof["sample_timestamp"] == 5.5
    assert proof["qualification"] == "unverified_model_observation"
    assert recovered["score"] == pytest.approx((1/66 + 1/61)/(2/61))
    assert len(state["encoded"][0]) == 51
    assert "caption 50" not in state["encoded"][0]
    assert all(p[1]["filter"]["must"] == [{"key": "ucf_promotion_status", "match": {"value": "promoted"}}]
               for p in state["posts"])


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_caption_disagreement_retains_strongest_clip_match_through_api(caption_api, method):
    client, engine, state, timeline = caption_api

    class DisagreeingEncoder:
        def encode(self, texts, **kwargs):
            # The strongest image match has the least relevant saved caption.
            vectors = [[1., 0.]]
            for text in texts[1:]:
                index = int(text.split()[-1])
                cosine = 0. if index == 0 else 1. - index / 100.
                vectors.append([cosine, np.sqrt(1. - cosine ** 2)])
            return np.array(vectors)

    engine._text_model = DisagreeingEncoder()
    if method == "GET":
        response = client.get("/api/search/visual", params={"q": "red truck", "top_k": 50})
    else:
        response = client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["visual"], "top_k": 50})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["scene_id"] == 0
    assert [r["scene_id"] for r in results[1:]] == list(range(1, 50))
    assert results[0]["score"] < results[1]["score"]  # Preserve honest RRF evidence.
    assert results[0]["visual_ranking"]["caption_rank"] == 50
    assert results[0]["visual_ranking"]["is_clip_anchor"] is True
    assert all(r["visual_ranking"]["is_clip_anchor"] is False for r in results[1:])
    assert all(r["visual_ranking"]["ordering"] == "clip_anchor_then_rrf" for r in results)


@pytest.mark.parametrize("fault", ["missing", "failed", "not_midpoint", "wrong_source", "ambiguous_source", "ambiguous_scene", "encoder", "nan", "exception"])
def test_midpoint_ranking_falls_back_without_losing_clip_matches(caption_api, monkeypatch, fault):
    client, engine, state, timeline = caption_api
    if fault == "missing":
        timeline["segments"][0]["visual_caption"] = ""
    elif fault == "failed":
        timeline["segments"][0]["caption_meta"]["status"] = "failed"
    elif fault == "not_midpoint":
        timeline["segments"][0]["caption_meta"]["is_midpoint_sample"] = False
    elif fault == "wrong_source":
        timeline["video_id"] = "different source"
    elif fault == "ambiguous_source":
        monkeypatch.setattr(search.get_data_loader(), "list_processed_videos", lambda: ["one", "two"])
    elif fault == "ambiguous_scene":
        timeline["segments"].append(dict(timeline["segments"][0]))
    elif fault == "encoder":
        engine._text_model = None
        monkeypatch.setattr(engine, "_load_text_model", lambda: None)
    else:
        def fail(*args, **kwargs):
            if fault == "exception":
                raise RuntimeError("private encoder detail")
            return np.full((51, 2), np.nan)
        monkeypatch.setattr(engine._text_model, "encode", fail)
    body = client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["visual"], "top_k": 5}).json()
    assert [r["scene_id"] for r in body["results"]] == list(range(5))
    assert body["results"][0]["score"] == pytest.approx(.9 * engine.weight_visual)
    assert all(r["visual_ranking"] is None for r in body["results"])
    assert body["diagnostics"]["visual_captions"]["status"] == "fallback"
    assert "private" not in str(body)


def test_caption_ranking_skips_retired_candidates_and_does_not_change_mixed_modes(caption_api, monkeypatch):
    client, engine, state, timeline = caption_api
    monkeypatch.setattr(search.get_data_loader(), "is_search_result_active", lambda payload: payload.get("scene_id") != 5)
    body = client.get("/api/search/visual", params={"q": "red truck", "top_k": 5}).json()
    assert all(r["scene_id"] != 5 for r in body["results"])
    assert "caption 5" not in state["encoded"][0]
    state["encoded"].clear()
    monkeypatch.setattr(engine, "search_text", lambda *args, **kwargs: [])
    body = client.post("/api/search/multimodal", json={"query": "red truck", "modalities": ["text", "visual"], "top_k": 5}).json()
    assert "visual_captions" not in body["diagnostics"]
    assert not state["encoded"]


def test_caption_ranking_large_request_keeps_clip_and_clears_old_diagnostic(caption_api):
    client, engine, state, timeline = caption_api
    client.get("/api/search/visual", params={"q": "red truck", "top_k": 5})
    state["encoded"].clear()
    body = client.get("/api/search/visual", params={"q": "red truck", "top_k": 100}).json()
    assert "visual_captions" not in body["diagnostics"]
    assert not state["encoded"]


def test_visual_duplicate_exhaustion_is_not_a_budget_failure(visual_api, monkeypatch):
    client, engine, state, _ = visual_api
    monkeypatch.setattr(search, "_data_loader", types.SimpleNamespace())
    state["result"] = [
        {"id": i, "score": .9 - i / 10, "payload": {"scene_id": "same", "video_id": "first"}}
        for i in range(2)
    ]
    response = client.get("/api/search/visual", params={"q": "red truck", "top_k": 5})
    assert response.status_code == 200
    assert response.json()["total_results"] == 1
    assert response.json()["results"][0]["score"] == .9
    assert response.json()["diagnostics"]["visual"]["status"] == "ready"
