from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest

from retrieval.multimodal_search import MultimodalSearchEngine


def _engine() -> MultimodalSearchEngine:
    return MultimodalSearchEngine(
        {
            "qdrant": {
                "host": "http://127.0.0.1:6333",
                "collections": {
                    "text": "goodq_text",
                    "clip": "goodq_clip_scenes",
                    "audio": "goodq_audio",
                },
                "embedding_dims": {
                    "text": 384,
                    "clip": 512,
                    "audio": 512,
                },
            },
            "paths": {
                "processing": "processing",
            },
            "phase6": {
                "retrieval": {
                    "fusion_weights": {
                        "text": 0.5,
                        "visual": 0.4,
                        "audio": 0.1,
                    }
                }
            },
        }
    )


def test_search_audio_uses_audio_collection_and_clap_text_encoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine()
    observed: dict[str, object] = {}

    class _FakeClient:
        def query(self, vector: list[float], top_k: int = 5, **kwargs):
            observed["vector"] = vector
            observed["top_k"] = top_k
            return [
                {
                    "id": "video_001:303",
                    "score": 0.82,
                    "payload": {"video_id": "video_001", "scene_id": 303},
                }
            ]

    monkeypatch.setattr(
        engine,
        "encode_text_for_audio_search",
        lambda query: np.ones(512, dtype=np.float32),
    )

    def _fake_get_qdrant_client(collection: str):
        observed["collection"] = collection
        return _FakeClient()

    monkeypatch.setattr(engine, "_get_qdrant_client", _fake_get_qdrant_client)

    results = engine.search_audio(
        "crowd laughter",
        top_k=4,
        retrieval_context="system.healthcheck",
    )

    assert observed["collection"] == "goodq_audio"
    assert observed["top_k"] == 4
    assert len(observed["vector"]) == 512
    assert results == [
        {
            "id": "video_001:303",
            "score": 0.82,
            "payload": {"video_id": "video_001", "scene_id": 303},
        }
    ]


def test_search_multimodal_includes_audio_results_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine()

    monkeypatch.setattr(engine, "_metadata_bonus", lambda query, payload: 0.0)
    monkeypatch.setattr(
        engine,
        "search_text",
        lambda query, top_k, *, retrieval_context: [
            {
                "id": "video_001:101",
                "score": 0.8,
                "payload": {"video_id": "video_001", "scene_id": 101},
            }
        ],
    )
    monkeypatch.setattr(
        engine,
        "search_audio",
        lambda query, top_k, *, retrieval_context: [
            {
                "id": "video_001:101",
                "score": 0.6,
                "payload": {"video_id": "video_001", "scene_id": 101},
            },
            {
                "id": "video_002:202",
                "score": 0.7,
                "payload": {"video_id": "video_002", "scene_id": 202},
            },
        ],
    )

    results = engine.search_multimodal(
        "awkward phone call",
        top_k=3,
        modalities=["text", "audio"],
        retrieval_context="system.healthcheck",
    )

    assert [result["payload"]["scene_id"] for result in results] == [101, 202]
    fused = results[0]
    assert fused["payload"] == {"video_id": "video_001", "scene_id": 101}
    assert fused["modalities"] == ["audio", "text"]
    assert fused["modality_scores"]["text"] == pytest.approx(0.4)
    assert fused["modality_scores"]["audio"] == pytest.approx(0.06)
    assert fused["score"] == pytest.approx(0.46)


def test_search_multimodal_defaults_stay_text_and_visual_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine()
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(engine, "_metadata_bonus", lambda query, payload: 0.0)
    monkeypatch.setattr(
        engine,
        "search_text",
        lambda query, top_k, *, retrieval_context: calls.append(("text", top_k)) or [],
    )
    monkeypatch.setattr(
        engine,
        "search_visual",
        lambda query, top_k, *, retrieval_context: calls.append(("visual", top_k)) or [],
    )
    monkeypatch.setattr(
        engine,
        "search_audio",
        lambda query, top_k, *, retrieval_context: (_ for _ in ()).throw(
            AssertionError("audio should not be called")
        ),
    )

    results = engine.search_multimodal(
        "office banter",
        top_k=4,
        retrieval_context="system.healthcheck",
    )

    assert results == []
    assert calls == [("text", 10), ("visual", 10)]


def test_search_multimodal_records_audio_encoder_unavailable_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine()

    monkeypatch.setattr(
        engine,
        "search_text",
        lambda query, top_k, *, retrieval_context: [],
    )
    monkeypatch.setattr(
        engine,
        "search_visual",
        lambda query, top_k, *, retrieval_context: [],
    )
    monkeypatch.setattr(
        engine,
        "encode_text_for_audio_search",
        lambda query: np.zeros(512, dtype=np.float32),
    )
    engine._audio_text_model_error_reason = "torch_safetensors_required"

    results = engine.search_multimodal(
        "couch",
        top_k=3,
        modalities=["audio"],
        retrieval_context="system.healthcheck",
    )

    assert results == []
    assert engine.last_search_diagnostics()["audio"] == {
        "status": "unavailable",
        "label": "Audio text-query encoder unavailable",
        "reason": "torch_safetensors_required",
    }


def test_visual_query_loader_uses_safetensors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _engine()
    calls: list[dict[str, object]] = []
    snapshot = (tmp_path / "pinned-clip-snapshot").resolve()
    search_module = sys.modules["retrieval.multimodal_search"]
    monkeypatch.setattr(
        search_module,
        "resolve_pinned_model_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )

    class _FakeProcessor:
        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs):
            assert model_id == str(snapshot)
            assert kwargs == {"local_files_only": True}
            return cls()

    class _FakeModel:
        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs):
            assert model_id == str(snapshot)
            calls.append(kwargs)
            return cls()

        def eval(self):
            return self

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.CLIPModel = _FakeModel
    fake_transformers.CLIPProcessor = _FakeProcessor
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    engine._load_clip_model()

    assert calls == [{"use_safetensors": True, "local_files_only": True}]


def test_visual_query_encoder_accepts_pooled_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()

    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    class _FakeTensor:
        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            values = np.zeros((1, 512), dtype=np.float32)
            values[0, 0] = 3.0
            values[0, 1] = 4.0
            return values

    class _FakeOutput:
        pooler_output = _FakeTensor()

    class _FakeModel:
        def get_text_features(self, **_inputs):
            return _FakeOutput()

    class _FakeProcessor:
        def __call__(self, **_kwargs):
            return {"input_ids": object()}

    fake_torch = types.ModuleType("torch")
    fake_torch.no_grad = lambda: _NoGrad()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    engine._clip_model = {"model": _FakeModel(), "processor": _FakeProcessor()}

    embedding = engine.encode_text_for_visual_search("woman at table")

    assert embedding.shape == (512,)
    assert embedding[0] == pytest.approx(0.6)
    assert embedding[1] == pytest.approx(0.8)
    assert np.linalg.norm(embedding) == pytest.approx(1.0)


def test_audio_query_encoder_accepts_pooled_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()

    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    class _FakeTensor:
        def to(self, _device):
            return self

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            values = np.zeros((1, 512), dtype=np.float32)
            values[0, 0] = 5.0
            values[0, 1] = 12.0
            return values

    class _FakeOutput:
        pooler_output = _FakeTensor()

    class _FakeModel:
        def get_text_features(self, **_inputs):
            return _FakeOutput()

    class _FakeProcessor:
        def __call__(self, **_kwargs):
            return {"input_ids": _FakeTensor()}

    fake_torch = types.ModuleType("torch")
    fake_torch.no_grad = lambda: _NoGrad()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    engine._audio_text_model = {
        "model": _FakeModel(),
        "processor": _FakeProcessor(),
        "device": "cpu",
    }

    embedding = engine.encode_text_for_audio_search("family laughing")

    assert embedding.shape == (512,)
    assert embedding[0] == pytest.approx(5.0 / 13.0)
    assert embedding[1] == pytest.approx(12.0 / 13.0)
    assert np.linalg.norm(embedding) == pytest.approx(1.0)
