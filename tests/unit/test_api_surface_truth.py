from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scenes_module = _load_route_module("scenes")
timeline_module = _load_route_module("timeline")


class _FakeLoader:
    def __init__(self, temporal_index: dict):
        self._temporal_index = temporal_index

    def load_temporal_index(self, video_id: str):
        return self._temporal_index if video_id == "video_001" else None


class _FakeSearchEngine:
    def __init__(self, similar_results: list[dict]):
        self.similar_results = similar_results
        self.calls: list[tuple[str, int, int]] = []

    def search_similar_scene(self, video_id: str, scene_id: int, top_k: int):
        self.calls.append((video_id, scene_id, top_k))
        return self.similar_results[:top_k]


def _sample_temporal_index() -> dict:
    return {
        "duration": 12.0,
        "phase6_complete": True,
        "phase6_harmonized": True,
        "version": 7,
        "segments_with_candidate_visible_people": 1,
        "segments_with_interaction_dominance": 1,
        "segments_with_conversation_owner": 1,
        "segments_with_speaker_aligned_mentions": 1,
        "top_candidate_visible_people": [{"entity": "anonymous_person_1", "type": "PERSON", "count": 1}],
        "top_interaction_dominance": [{"speaker_id": "SPEAKER_00", "count": 1}],
        "top_conversation_owners": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "top_speaker_aligned_mentions": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "speaker_aligned_mention_variant_groups": [
            {
                "group_key": "person::jerry seinfeld",
                "type": "PERSON",
                "reason": "single_token_full_name_overlap",
                "total_count": 2,
                "variants": [
                    {"entity": "jerry", "count": 1},
                    {"entity": "jerry seinfeld", "count": 1},
                ],
            }
        ],
        "segments_with_transcript_entity_disagreements": 2,
        "segments_with_full_name_partial_entity_disagreements": 1,
        "transcript_entity_disagreement_category_counts": [
            {"category": "transcript_full_name_reduced_to_partial_entity", "count": 1},
            {"category": "title_bearing_transcript_name_not_resolved", "count": 1},
        ],
        "top_transcript_full_name_partial_entity_families": [
            {
                "family_key": "partial::jerry",
                "count": 1,
                "example": {
                    "scene_id": 101,
                    "transcript_candidate": "Jerry Seinfeld",
                    "entity_names": ["Jerry"],
                    "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
                    "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
                    "reason": "transcript full-name surface reduced to partial local person identity",
                },
            }
        ],
        "top_transcript_entity_disagreement_families": [
            {
                "category": "transcript_full_name_reduced_to_partial_entity",
                "family_key": "partial::jerry",
                "count": 1,
                "example": {
                    "scene_id": 101,
                    "transcript_candidate": "Jerry Seinfeld",
                    "entity_names": ["Jerry"],
                    "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
                    "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
                    "reason": "transcript full-name surface reduced to partial local person identity",
                },
            },
            {
                "category": "title_bearing_transcript_name_not_resolved",
                "family_key": "title_unresolved::mrs swedler",
                "count": 1,
                "example": {
                    "scene_id": 102,
                    "transcript_candidate": "Mrs. Swedler",
                    "entity_names": [],
                    "mentioned_people": [],
                    "speaker_aligned_mentions": [],
                    "reason": "title-bearing transcript person reference is not represented in local person truth surfaces",
                },
            },
        ],
        "segments": [
            {
                "segment_id": 1,
                "scene_id": 101,
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "audio_chunks": [0],
                "speaker_ids": ["SPEAKER_00"],
                "speaker_count": 1,
                "dominant_speaker_id": "SPEAKER_00",
                "continuity_key": "SPEAKER_00",
                "full_transcript": "A full transcript for the opening scene.",
                "keywords": ["opening", "scene", "dialogue"],
                "detected_objects": [
                    {"label": "person", "score": 0.99},
                    {"label": "tie", "score": 0.41},
                ],
                "clip_id": "clip_001",
                "dino_id": "dino_001",
                "representative_frame": "frame_0001.jpg",
                "diarization_status": "success",
                "emotion_status": "success",
                "speaker_voice_signature_count": 1,
                "speaker_voice_signature_meta": {"status": "ok", "emitted": 1},
                "audio_emotion": "fear",
                "sentiment": {"label": "negative", "score": 0.82},
                "sentiment_label": "negative",
                "sentiment_score": 0.82,
                "time_hints": {"explicit_dates": [], "relative_phrases": ["next week"]},
                "content_state": "signal",
                "candidate_visible_people": [{"name": "anonymous_person_1"}],
                "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
                "transcript_entity_disagreements": [
                    {
                        "category": "transcript_full_name_reduced_to_partial_entity",
                        "family_key": "partial::jerry",
                        "scene_id": 101,
                        "transcript_candidate": "Jerry Seinfeld",
                        "entity_names": ["Jerry"],
                        "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
                        "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
                        "reason": "transcript full-name surface reduced to partial local person identity",
                    }
                ],
                "interaction_dominance": {
                    "speaker_id": "SPEAKER_00",
                    "dominant_share": 0.8,
                    "segments": 1,
                    "stability": 1.0,
                    "confidence": "strong",
                    "continuity_key": "SPEAKER_00",
                },
                "conversation_owner": {
                    "text": "Jerry",
                    "type": "PERSON",
                    "confidence": "candidate",
                    "source": "interaction_chain",
                    "continuity_key": "SPEAKER_00",
                },
            }
        ],
    }


def test_list_scenes_surfaces_persisted_audio_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _FakeLoader(_sample_temporal_index())
    monkeypatch.setattr(scenes_module, "get_data_loader", lambda: loader)

    result = asyncio.run(scenes_module.list_scenes(video_id="video_001"))

    assert len(result) == 1
    scene = result[0]
    assert scene.scene_id == 101
    assert scene.objects == ["person", "tie"]
    assert scene.speaker_count == 1
    assert scene.dominant_speaker_id == "SPEAKER_00"
    assert scene.continuity_key == "SPEAKER_00"
    assert scene.diarization_status == "success"
    assert scene.emotion_status == "success"
    assert scene.speaker_voice_signature_count == 1
    assert scene.speaker_voice_signature_meta == {"status": "ok", "emitted": 1}
    assert scene.audio_emotion == "fear"
    assert scene.sentiment == {"label": "negative", "score": 0.82}
    assert scene.sentiment_label == "negative"
    assert scene.sentiment_score == 0.82
    assert scene.time_hints == {"explicit_dates": [], "relative_phrases": ["next week"]}
    assert scene.content_state == "signal"
    assert scene.candidate_visible_people == [{"name": "anonymous_person_1"}]
    assert scene.speaker_aligned_mentions == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert scene.transcript_entity_disagreements == [
        {
            "category": "transcript_full_name_reduced_to_partial_entity",
            "family_key": "partial::jerry",
            "scene_id": 101,
            "transcript_candidate": "Jerry Seinfeld",
            "entity_names": ["Jerry"],
            "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
            "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
            "reason": "transcript full-name surface reduced to partial local person identity",
        }
    ]
    assert scene.interaction_dominance == {
        "speaker_id": "SPEAKER_00",
        "dominant_share": 0.8,
        "segments": 1,
        "stability": 1.0,
        "confidence": "strong",
        "continuity_key": "SPEAKER_00",
    }
    assert scene.conversation_owner == {
        "text": "Jerry",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "SPEAKER_00",
    }


def test_full_timeline_surfaces_persisted_audio_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _FakeLoader(_sample_temporal_index())
    monkeypatch.setattr(timeline_module, "get_data_loader", lambda: loader)

    response = asyncio.run(timeline_module.get_full_timeline(video_id="video_001"))

    assert response.video_id == "video_001"
    assert response.metadata == {
        "phase6_complete": True,
        "phase6_harmonized": True,
        "version": 7,
        "segments_with_candidate_visible_people": 1,
        "segments_with_interaction_dominance": 1,
        "segments_with_conversation_owner": 1,
        "segments_with_speaker_aligned_mentions": 1,
        "top_candidate_visible_people": [{"entity": "anonymous_person_1", "type": "PERSON", "count": 1}],
        "top_interaction_dominance": [{"speaker_id": "SPEAKER_00", "count": 1}],
        "top_conversation_owners": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "top_speaker_aligned_mentions": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "speaker_aligned_mention_variant_groups": [
            {
                "group_key": "person::jerry seinfeld",
                "type": "PERSON",
                "reason": "single_token_full_name_overlap",
                "total_count": 2,
                "variants": [
                    {"entity": "jerry", "count": 1},
                    {"entity": "jerry seinfeld", "count": 1},
                ],
            }
        ],
        "segments_with_transcript_entity_disagreements": 2,
        "segments_with_full_name_partial_entity_disagreements": 1,
        "transcript_entity_disagreement_category_counts": [
            {"category": "transcript_full_name_reduced_to_partial_entity", "count": 1},
            {"category": "title_bearing_transcript_name_not_resolved", "count": 1},
        ],
        "top_transcript_full_name_partial_entity_families": [
            {
                "family_key": "partial::jerry",
                "count": 1,
                "example": {
                    "scene_id": 101,
                    "transcript_candidate": "Jerry Seinfeld",
                    "entity_names": ["Jerry"],
                    "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
                    "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
                    "reason": "transcript full-name surface reduced to partial local person identity",
                },
            }
        ],
        "top_transcript_entity_disagreement_families": [
            {
                "category": "transcript_full_name_reduced_to_partial_entity",
                "family_key": "partial::jerry",
                "count": 1,
                "example": {
                    "scene_id": 101,
                    "transcript_candidate": "Jerry Seinfeld",
                    "entity_names": ["Jerry"],
                    "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
                    "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
                    "reason": "transcript full-name surface reduced to partial local person identity",
                },
            },
            {
                "category": "title_bearing_transcript_name_not_resolved",
                "family_key": "title_unresolved::mrs swedler",
                "count": 1,
                "example": {
                    "scene_id": 102,
                    "transcript_candidate": "Mrs. Swedler",
                    "entity_names": [],
                    "mentioned_people": [],
                    "speaker_aligned_mentions": [],
                    "reason": "title-bearing transcript person reference is not represented in local person truth surfaces",
                },
            },
        ],
    }
    assert len(response.segments) == 1
    segment = response.segments[0]
    assert segment.objects == ["person", "tie"]
    assert segment.speaker_count == 1
    assert segment.dominant_speaker_id == "SPEAKER_00"
    assert segment.continuity_key == "SPEAKER_00"
    assert segment.diarization_status == "success"
    assert segment.emotion_status == "success"
    assert segment.speaker_voice_signature_count == 1
    assert segment.speaker_voice_signature_meta == {"status": "ok", "emitted": 1}
    assert segment.audio_emotion == "fear"
    assert segment.sentiment == {"label": "negative", "score": 0.82}
    assert segment.sentiment_label == "negative"
    assert segment.sentiment_score == 0.82
    assert segment.time_hints == {"explicit_dates": [], "relative_phrases": ["next week"]}
    assert segment.content_state == "signal"
    assert segment.candidate_visible_people == [{"name": "anonymous_person_1"}]
    assert segment.speaker_aligned_mentions == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert segment.transcript_entity_disagreements == [
        {
            "category": "transcript_full_name_reduced_to_partial_entity",
            "family_key": "partial::jerry",
            "scene_id": 101,
            "transcript_candidate": "Jerry Seinfeld",
            "entity_names": ["Jerry"],
            "mentioned_people": [{"text": "Jerry", "type": "PERSON"}],
            "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
            "reason": "transcript full-name surface reduced to partial local person identity",
        }
    ]
    assert segment.interaction_dominance == {
        "speaker_id": "SPEAKER_00",
        "dominant_share": 0.8,
        "segments": 1,
        "stability": 1.0,
        "confidence": "strong",
        "continuity_key": "SPEAKER_00",
    }
    assert segment.conversation_owner == {
        "text": "Jerry",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "SPEAKER_00",
    }


def test_full_timeline_accepts_string_scene_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    temporal_index = _sample_temporal_index()
    temporal_index["segments"][0]["scene_id"] = "scene_0001_hash"
    temporal_index["top_transcript_entity_disagreement_families"][0]["example"]["scene_id"] = "scene_0001_hash"
    temporal_index["top_transcript_entity_disagreement_families"][1]["example"]["scene_id"] = "scene_0002_hash"

    loader = _FakeLoader(temporal_index)
    monkeypatch.setattr(timeline_module, "get_data_loader", lambda: loader)

    response = asyncio.run(timeline_module.get_full_timeline(video_id="video_001"))

    assert len(response.segments) == 1
    assert response.segments[0].scene_id == "scene_0001_hash"
    assert response.metadata["top_transcript_entity_disagreement_families"][0]["example"]["scene_id"] == "scene_0001_hash"


def test_similar_scene_route_returns_real_neighbors(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _FakeLoader(_sample_temporal_index())
    monkeypatch.setattr(scenes_module, "get_data_loader", lambda: loader)
    similar_context = {
        "scene_id": 202,
        "start": 7.5,
        "end": 11.0,
        "duration": 3.5,
        "full_transcript": "A similar business discussion scene.",
        "keywords": ["business", "deal"],
        "detected_objects": [{"label": "person"}, {"label": "desk"}],
        "speaker_ids": ["SPEAKER_01"],
        "audio_chunks": [4],
        "speaker_count": 1,
        "dominant_speaker_id": "SPEAKER_01",
        "continuity_key": "SPEAKER_01",
        "diarization_status": "success",
        "emotion_status": "success",
        "speaker_voice_signature_count": 1,
        "speaker_voice_signature_meta": {"status": "ok", "emitted": 1},
        "audio_emotion": "neutral",
        "sentiment": {"label": "neutral", "score": 0.51},
        "sentiment_label": "neutral",
        "sentiment_score": 0.51,
        "time_hints": {"explicit_dates": [], "relative_phrases": []},
        "content_state": "signal",
        "candidate_visible_people": [{"name": "anonymous_person_2"}],
        "speaker_aligned_mentions": [{"text": "Jerry", "type": "PERSON", "count": 1}],
        "interaction_dominance": {
            "speaker_id": "SPEAKER_01",
            "dominant_share": 0.75,
            "segments": 1,
            "stability": 1.0,
            "confidence": "strong",
            "continuity_key": "SPEAKER_01",
        },
        "conversation_owner": {
            "text": "Jerry",
            "type": "PERSON",
            "confidence": "candidate",
            "source": "interaction_chain",
            "continuity_key": "SPEAKER_01",
        },
    }
    engine = _FakeSearchEngine(
        [
            {
                "id": "video_002:202",
                "score": 0.91,
                "payload": {"video_id": "video_002", "scene_id": 202},
                "scene_context": similar_context,
            }
        ]
    )
    monkeypatch.setattr(scenes_module, "get_search_engine", lambda: engine, raising=False)

    result = asyncio.run(
        scenes_module.find_similar_scenes(video_id="video_001", scene_id=101, top_k=5)
    )

    assert engine.calls == [("video_001", 101, 5)]
    assert len(result) == 1
    scene = result[0]
    assert scene.scene_id == 202
    assert scene.transcript == "A similar business discussion scene."
    assert scene.objects == ["person", "desk"]
    assert scene.speaker_count == 1
    assert scene.dominant_speaker_id == "SPEAKER_01"
    assert scene.continuity_key == "SPEAKER_01"
    assert scene.sentiment == {"label": "neutral", "score": 0.51}
    assert scene.sentiment_label == "neutral"
    assert scene.sentiment_score == 0.51
    assert scene.speaker_aligned_mentions == [{"text": "Jerry", "type": "PERSON", "count": 1}]
    assert scene.interaction_dominance == {
        "speaker_id": "SPEAKER_01",
        "dominant_share": 0.75,
        "segments": 1,
        "stability": 1.0,
        "confidence": "strong",
        "continuity_key": "SPEAKER_01",
    }
    assert scene.conversation_owner == {
        "text": "Jerry",
        "type": "PERSON",
        "confidence": "candidate",
        "source": "interaction_chain",
        "continuity_key": "SPEAKER_01",
    }


def test_scene_and_timeline_routes_surface_normalization_instrumentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temporal_index = _sample_temporal_index()
    temporal_index["segments"][0]["normalization_applied"] = True
    temporal_index["segments"][0]["normalization_source"] = "exact_pair_allowlist"

    loader = _FakeLoader(temporal_index)
    monkeypatch.setattr(scenes_module, "get_data_loader", lambda: loader)
    monkeypatch.setattr(timeline_module, "get_data_loader", lambda: loader)

    scene = asyncio.run(scenes_module.get_scene(video_id="video_001", scene_id=101))
    timeline = asyncio.run(timeline_module.get_full_timeline(video_id="video_001"))

    assert scene.normalization_applied is True
    assert scene.normalization_source == "exact_pair_allowlist"
    assert timeline.segments[0].normalization_applied is True
    assert timeline.segments[0].normalization_source == "exact_pair_allowlist"
