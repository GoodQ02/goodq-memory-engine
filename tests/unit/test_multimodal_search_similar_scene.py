from __future__ import annotations

from retrieval.multimodal_search import MultimodalSearchEngine


def _engine() -> MultimodalSearchEngine:
    return MultimodalSearchEngine(
        {
            "qdrant": {
                "host": "http://127.0.0.1:6333",
                "collections": {
                    "text": "goodq_text",
                    "clip": "goodq_clip_scenes",
                },
            },
            "paths": {
                "processing": "processing",
            },
        }
    )


def test_build_scene_similarity_query_prefers_scene_memory_fields() -> None:
    engine = _engine()
    scene_context = {
        "primary_tags": ["clothing business"],
        "dialogue_topics": ["designer"],
        "keywords": ["fashion", "shirt"],
        "narrative_summary": "Table conversation about clothing business.",
        "audio_emotion": "surprise",
        "detected_objects": [{"label": "table"}],
    }

    query = engine.build_scene_similarity_query(scene_context)

    lowered = query.lower()
    assert "clothing business" in lowered
    assert "designer" in lowered
    assert "fashion" in lowered
    assert "shirt" in lowered
    assert "surprise" in lowered
    assert "table" in lowered


def test_search_similar_scene_excludes_source_scene_and_enriches_context(monkeypatch) -> None:
    engine = _engine()
    source_context = {
        "scene_id": 101,
        "primary_tags": ["business deal"],
        "keywords": ["negotiation"],
    }
    similar_context = {
        "scene_id": 202,
        "start": 3.5,
        "end": 7.0,
        "duration": 3.5,
        "full_transcript": "A second business deal scene.",
        "keywords": ["business", "deal"],
    }

    contexts = {
        ("video_001", 101): source_context,
        ("video_002", 202): similar_context,
    }

    def fake_retrieve_scene_context(video_id: str, scene_id: int):
        return contexts.get((video_id, scene_id))

    def fake_search_multimodal(query: str, top_k: int, modalities: list[str]):
        assert "business deal" in query.lower()
        assert modalities == ["text", "visual", "audio"]
        return [
            {
                "id": "video_001:101",
                "score": 0.99,
                "payload": {"video_id": "video_001", "scene_id": 101},
            },
            {
                "id": "video_002:202",
                "score": 0.88,
                "payload": {"video_id": "video_002", "scene_id": 202},
            },
        ]

    monkeypatch.setattr(engine, "retrieve_scene_context", fake_retrieve_scene_context)
    monkeypatch.setattr(engine, "search_multimodal", fake_search_multimodal)

    results = engine.search_similar_scene(video_id="video_001", scene_id=101, top_k=5)

    assert len(results) == 1
    assert results[0]["payload"] == {"video_id": "video_002", "scene_id": 202}
    assert results[0]["scene_context"] == similar_context


def test_search_similar_scene_accepts_string_scene_ids(monkeypatch) -> None:
    engine = _engine()
    source_context = {
        "scene_id": "scene_hash_source",
        "primary_tags": ["family couch"],
        "keywords": ["living room"],
    }
    similar_context = {
        "scene_id": "scene_hash_neighbor",
        "start": 12.0,
        "end": 18.0,
        "duration": 6.0,
        "full_transcript": "A related family scene.",
    }

    contexts = {
        ("video_hash", "scene_hash_source"): source_context,
        ("video_hash", "scene_hash_neighbor"): similar_context,
    }

    def fake_retrieve_scene_context(video_id: str, scene_id: int | str):
        return contexts.get((video_id, str(scene_id)))

    def fake_search_multimodal(query: str, top_k: int, modalities: list[str]):
        assert "family couch" in query.lower()
        assert modalities == ["text", "visual", "audio"]
        return [
            {
                "id": "video_hash:scene_hash_source",
                "score": 0.99,
                "payload": {"video_id": "video_hash", "scene_id": "scene_hash_source"},
            },
            {
                "id": "video_hash:scene_hash_neighbor",
                "score": 0.83,
                "payload": {"video_id": "video_hash", "scene_id": "scene_hash_neighbor"},
            },
        ]

    monkeypatch.setattr(engine, "retrieve_scene_context", fake_retrieve_scene_context)
    monkeypatch.setattr(engine, "search_multimodal", fake_search_multimodal)

    results = engine.search_similar_scene(video_id="video_hash", scene_id="scene_hash_source", top_k=5)

    assert len(results) == 1
    assert results[0]["payload"] == {"video_id": "video_hash", "scene_id": "scene_hash_neighbor"}
    assert results[0]["scene_context"] == similar_context
