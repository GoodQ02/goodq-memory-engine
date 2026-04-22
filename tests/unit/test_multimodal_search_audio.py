from __future__ import annotations

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
        def query(self, vector: list[float], top_k: int = 5):
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

    results = engine.search_audio("crowd laughter", top_k=4)

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
        lambda query, top_k: [
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
        lambda query, top_k: [
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
        lambda query, top_k: calls.append(("text", top_k)) or [],
    )
    monkeypatch.setattr(
        engine,
        "search_visual",
        lambda query, top_k: calls.append(("visual", top_k)) or [],
    )
    monkeypatch.setattr(
        engine,
        "search_audio",
        lambda query, top_k: (_ for _ in ()).throw(AssertionError("audio should not be called")),
    )

    results = engine.search_multimodal("office banter", top_k=4)

    assert results == []
    assert calls == [("text", 10), ("visual", 10)]
