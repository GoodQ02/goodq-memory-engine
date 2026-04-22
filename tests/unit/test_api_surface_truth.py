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


def _sample_temporal_index() -> dict:
    return {
        "duration": 12.0,
        "phase6_complete": True,
        "phase6_harmonized": True,
        "version": 7,
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
                "time_hints": {"explicit_dates": [], "relative_phrases": ["next week"]},
                "content_state": "signal",
                "candidate_visible_people": [{"name": "anonymous_person_1"}],
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
    assert scene.time_hints == {"explicit_dates": [], "relative_phrases": ["next week"]}
    assert scene.content_state == "signal"
    assert scene.candidate_visible_people == [{"name": "anonymous_person_1"}]


def test_full_timeline_surfaces_persisted_audio_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _FakeLoader(_sample_temporal_index())
    monkeypatch.setattr(timeline_module, "get_data_loader", lambda: loader)

    response = asyncio.run(timeline_module.get_full_timeline(video_id="video_001"))

    assert response.video_id == "video_001"
    assert response.metadata == {
        "phase6_complete": True,
        "phase6_harmonized": True,
        "version": 7,
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
    assert segment.time_hints == {"explicit_dates": [], "relative_phrases": ["next week"]}
    assert segment.content_state == "signal"
    assert segment.candidate_visible_people == [{"name": "anonymous_person_1"}]


def test_similar_scene_route_returns_honest_not_implemented(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _FakeLoader(_sample_temporal_index())
    monkeypatch.setattr(scenes_module, "get_data_loader", lambda: loader)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            scenes_module.find_similar_scenes(video_id="video_001", scene_id=101, top_k=5)
        )

    assert exc_info.value.status_code == 501
    assert "not wired yet" in str(exc_info.value.detail)
