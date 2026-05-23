from __future__ import annotations

import asyncio
import importlib.util
import json
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
        self.calls: list[tuple[str, int | str, int]] = []

    def search_similar_scene(self, video_id: str, scene_id: int | str, top_k: int):
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
        "segments_with_scene_context_llm": 1,
        "segments_with_scene_context_epistemic": 1,
        "segments_with_scene_context_arbitration": 1,
        "top_candidate_visible_people": [{"entity": "anonymous_person_1", "type": "PERSON", "count": 1}],
        "top_interaction_dominance": [{"speaker_id": "SPEAKER_00", "count": 1}],
        "top_conversation_owners": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "top_speaker_aligned_mentions": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "top_scene_context_tags": [{"tag": "planning", "count": 1}],
        "top_scene_context_epistemic_states": [{"state": "supported", "count": 1}],
        "top_scene_context_epistemic_dominant_evidence": [{"evidence": "mixed", "count": 1}],
        "top_scene_context_arbitration_resolved_by": [{"resolved_by": "mixed", "count": 1}],
        "top_scene_context_arbitration_unresolved_axes": [{"axis": "identity", "count": 1}],
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
                "visual_caption": "a girl playing a trumpet in a room",
                "ocr_text": "DEC 16 2002",
                "ocr_date_candidates": ["DEC 16 2002"],
                "diarization_status": "success",
                "emotion_status": "success",
                "speaker_voice_signature_count": 1,
                "speaker_voice_signature_meta": {"status": "ok", "emitted": 1},
                "audio_emotion": "fear",
                "audio_emotion_scores": {"neutral": 0.48, "calm": 0.31, "sad": 0.21},
                "clap_meta": {
                    "status": "ok",
                    "faiss_id": 2602,
                    "model": "laion/clap-htsat-unfused",
                },
                "sentiment": {"label": "negative", "score": 0.82},
                "sentiment_label": "negative",
                "sentiment_score": 0.82,
                "time_hints": {"explicit_dates": [], "relative_phrases": ["next week"]},
                "tags": ["indoor", "music", "performance", "trumpet", "december"],
                "tag_details": [
                    {"label": "trumpet", "score": 3.5, "sources": ["caption"]},
                    {"label": "music", "score": 2.75, "sources": ["caption_inference"]},
                    {"label": "december", "score": 1.5, "sources": ["time_hint"]},
                ],
                "scene_present_entities": [
                    {"text": "trumpet", "type": "OBJECT", "source": "caption"},
                    {"text": "music", "type": "CONCEPT", "source": "tagger"},
                ],
                "scene_context_llm": {
                    "narrative_summary": "A young musician performs indoors during a dated family recording.",
                    "context_tags": ["performance", "music"],
                    "activity_description": "Trumpet performance",
                    "source": "scene_context_llm",
                },
                "scene_context_epistemic": {"state": "supported", "dominant_evidence": "mixed"},
                "scene_context_arbitration": {"resolved_by": "mixed", "unresolved_axes": ["identity"]},
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


def _model_payload(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def test_scene_and_timeline_frame_surfaces_do_not_expose_local_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    temporal_index = _sample_temporal_index()
    raw_frame = (
        r"L:\_DATA\GoodQ_Data\processing\video_001\video\frames"
        r"\scene_0101_frame_01.jpg"
    )
    temporal_index["segments"][0]["representative_frame"] = raw_frame
    temporal_index["segments"][0]["frame_paths"] = [raw_frame]
    loader = _FakeLoader(temporal_index)
    monkeypatch.setattr(scenes_module, "get_data_loader", lambda: loader)
    monkeypatch.setattr(timeline_module, "get_data_loader", lambda: loader)

    scene = asyncio.run(scenes_module.list_scenes(video_id="video_001"))[0]
    timeline_segment = asyncio.run(timeline_module.get_full_timeline(video_id="video_001")).segments[0]

    for item in (scene, timeline_segment):
        payload = _model_payload(item)
        serialized = json.dumps(payload)
        assert "L:" not in serialized
        assert "C:" not in serialized
        assert "_DATA" not in serialized
        assert item.representative_frame == "/api/media/video/video_001/frame/scene_0101_frame_01.jpg"
        assert getattr(item, "representative_frame_available", None) is True
        assert getattr(item, "representative_frame_endpoint", None) == (
            "/api/media/video/video_001/frame/scene_0101_frame_01.jpg"
        )
        assert getattr(item, "representative_frame_path_redacted", None) is True
        assert getattr(item, "frame_endpoints", None) == [
            "/api/media/video/video_001/frame/scene_0101_frame_01.jpg"
        ]
        assert getattr(item, "frame_path_count", None) == 1
        assert getattr(item, "frame_paths_redacted", None) is True


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
    assert scene.visual_caption == "a girl playing a trumpet in a room"
    assert scene.ocr_text == "DEC 16 2002"
    assert scene.ocr_date_candidates == ["DEC 16 2002"]
    assert scene.audio_emotion == "fear"
    assert scene.audio_emotion_scores == {"neutral": 0.48, "calm": 0.31, "sad": 0.21}
    assert scene.clap_meta == {
        "status": "ok",
        "faiss_id": 2602,
        "model": "laion/clap-htsat-unfused",
    }
    assert scene.sentiment == {"label": "negative", "score": 0.82}
    assert scene.sentiment_label == "negative"
    assert scene.sentiment_score == 0.82
    assert scene.time_hints == {"explicit_dates": [], "relative_phrases": ["next week"]}
    assert scene.tags == ["indoor", "music", "performance", "trumpet", "december"]
    assert scene.tag_details == [
        {"label": "trumpet", "score": 3.5, "sources": ["caption"]},
        {"label": "music", "score": 2.75, "sources": ["caption_inference"]},
        {"label": "december", "score": 1.5, "sources": ["time_hint"]},
    ]
    assert scene.scene_present_entities == [
        {"text": "trumpet", "type": "OBJECT", "source": "caption"},
        {"text": "music", "type": "CONCEPT", "source": "tagger"},
    ]
    assert scene.scene_context_llm == {
        "narrative_summary": "A young musician performs indoors during a dated family recording.",
        "context_tags": ["performance", "music"],
        "activity_description": "Trumpet performance",
        "source": "scene_context_llm",
    }
    assert scene.scene_context_epistemic == {"state": "supported", "dominant_evidence": "mixed"}
    assert scene.scene_context_arbitration == {"resolved_by": "mixed", "unresolved_axes": ["identity"]}
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
        "segments_with_scene_context_llm": 1,
        "segments_with_scene_context_epistemic": 1,
        "segments_with_scene_context_arbitration": 1,
        "top_candidate_visible_people": [{"entity": "anonymous_person_1", "type": "PERSON", "count": 1}],
        "top_interaction_dominance": [{"speaker_id": "SPEAKER_00", "count": 1}],
        "top_conversation_owners": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "top_speaker_aligned_mentions": [{"entity": "jerry", "type": "PERSON", "count": 1}],
        "top_scene_context_tags": [{"tag": "planning", "count": 1}],
        "top_scene_context_epistemic_states": [{"state": "supported", "count": 1}],
        "top_scene_context_epistemic_dominant_evidence": [{"evidence": "mixed", "count": 1}],
        "top_scene_context_arbitration_resolved_by": [{"resolved_by": "mixed", "count": 1}],
        "top_scene_context_arbitration_unresolved_axes": [{"axis": "identity", "count": 1}],
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
    assert segment.visual_caption == "a girl playing a trumpet in a room"
    assert segment.ocr_text == "DEC 16 2002"
    assert segment.ocr_date_candidates == ["DEC 16 2002"]
    assert segment.audio_emotion == "fear"
    assert segment.audio_emotion_scores == {"neutral": 0.48, "calm": 0.31, "sad": 0.21}
    assert segment.clap_meta == {
        "status": "ok",
        "faiss_id": 2602,
        "model": "laion/clap-htsat-unfused",
    }
    assert segment.sentiment == {"label": "negative", "score": 0.82}
    assert segment.sentiment_label == "negative"
    assert segment.sentiment_score == 0.82
    assert segment.time_hints == {"explicit_dates": [], "relative_phrases": ["next week"]}
    assert segment.tags == ["indoor", "music", "performance", "trumpet", "december"]
    assert segment.tag_details == [
        {"label": "trumpet", "score": 3.5, "sources": ["caption"]},
        {"label": "music", "score": 2.75, "sources": ["caption_inference"]},
        {"label": "december", "score": 1.5, "sources": ["time_hint"]},
    ]
    assert segment.scene_present_entities == [
        {"text": "trumpet", "type": "OBJECT", "source": "caption"},
        {"text": "music", "type": "CONCEPT", "source": "tagger"},
    ]
    assert segment.scene_context_llm == {
        "narrative_summary": "A young musician performs indoors during a dated family recording.",
        "context_tags": ["performance", "music"],
        "activity_description": "Trumpet performance",
        "source": "scene_context_llm",
    }
    assert segment.scene_context_epistemic == {"state": "supported", "dominant_evidence": "mixed"}
    assert segment.scene_context_arbitration == {"resolved_by": "mixed", "unresolved_axes": ["identity"]}
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
    assert scene.video_id == "video_002"
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


def test_similar_scene_route_accepts_string_scene_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    temporal_index = _sample_temporal_index()
    temporal_index["segments"][0]["scene_id"] = "scene_hash_source"
    neighbor_segment = dict(temporal_index["segments"][0])
    neighbor_segment.update(
        {
            "scene_id": "scene_hash_neighbor",
            "full_transcript": "A hydrated similar family memory scene.",
            "sentiment": "positive",
            "sentiment_label": None,
            "entities": ["Family"],
        }
    )
    temporal_index["segments"].append(neighbor_segment)
    loader = _FakeLoader(temporal_index)
    monkeypatch.setattr(scenes_module, "get_data_loader", lambda: loader)
    similar_context = {
        "scene_id": "scene_hash_neighbor",
        "start": 7.5,
        "end": 11.0,
        "duration": 3.5,
        "full_transcript": "A raw payload scene that should be timeline-hydrated.",
        "keywords": ["family", "living room"],
        "detected_objects": [{"label": "couch"}],
        "sentiment": "positive",
        "entities": ["Family"],
    }
    engine = _FakeSearchEngine(
        [
            {
                "id": "video_001:scene_hash_neighbor",
                "score": 0.82,
                "payload": {"video_id": "video_001", "scene_id": "scene_hash_neighbor"},
                "scene_context": similar_context,
            }
        ]
    )
    monkeypatch.setattr(scenes_module, "get_search_engine", lambda: engine, raising=False)

    result = asyncio.run(
        scenes_module.find_similar_scenes(video_id="video_001", scene_id="scene_hash_source", top_k=5)
    )

    assert engine.calls == [("video_001", "scene_hash_source", 5)]
    assert len(result) == 1
    assert result[0].video_id == "video_001"
    assert result[0].scene_id == "scene_hash_neighbor"
    assert result[0].transcript == "A hydrated similar family memory scene."
    assert result[0].sentiment is None
    assert result[0].sentiment_label == "positive"
    assert result[0].entities == [{"text": "Family"}]


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
