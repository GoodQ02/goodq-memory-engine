"""Scene speaker summaries must describe tracks, not the ASR sentence subset."""
from __future__ import annotations

import copy
import json

import pytest

from steps.audio_speaker_merge.step import audio_speaker_merge
from steps.video import cross_modal_harmonizer as harmonizer


def _harmonize(tmp_path, monkeypatch, audio, *, start=100.0, end=110.0, fallback=None):
    monkeypatch.setattr(harmonizer, "ENTITY_EXTRACTION_AVAILABLE", False)
    processing = tmp_path / "processing"
    folder = processing / "sample"
    (folder / "video").mkdir(parents=True)
    audio_dir = folder / "audio"
    audio_dir.mkdir()
    for name, data in {
        "transcript": {"segments": []},
        "segmentation": {"segments": []},
        "diarization": {"speakers": fallback or []},
    }.items():
        (audio_dir / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    scene = {"scene_id": "scene", "start": start, "end": end,
             "content_state": "signal", "audio": {"path": "scene.wav", **audio}}
    manifest = folder / "video" / "scene_manifest.json"
    manifest.write_text(json.dumps({"video_id": "sample", "scenes": [scene]}), encoding="utf-8")
    result = harmonizer.run_cross_modal_harmonization(
        {"id": "sample", "processing_dir": str(folder), "scene_manifest_path": str(manifest),
         "audio_artifact_dir": str(audio_dir)}, {"paths": {"processing": str(processing)}})
    assert result["harmonization_status"] == "complete"
    saved = json.loads(manifest.read_text(encoding="utf-8"))["scenes"][0]
    temporal = json.loads((folder / "temporal_index.json").read_text(encoding="utf-8"))["segments"][0]
    assert saved["audio"] == scene["audio"]  # Raw speaker and review evidence is immutable.
    for field in ("speaker_count", "speaker_ids", "dominant_speaker_id", "dominant_speaker_share"):
        assert saved[field] == temporal[field]
    return temporal


@pytest.mark.parametrize("raw_key", ["diarization", "speaker_segments"])
@pytest.mark.parametrize("transcript", [
    [{"start": 0.0, "end": 10.0, "text": "A single long sentence."}],
    [{"start": 0.0, "end": 1.0, "text": "Only the quiet speaker was transcribed."}],
    [],
])
def test_tracks_survive_sentence_assignment(tmp_path, monkeypatch, raw_key, transcript):
    turns = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
             {"start": 2.0, "end": 10.0, "speaker": "SPEAKER_01"}]
    merged = audio_speaker_merge({"diarization": turns, "segments": transcript}, {})
    audio = {raw_key: turns, "speakers": ["SPEAKER_00", "SPEAKER_01"], "speaker_count": 2,
             "speaker_transcript": merged["speaker_transcript"],
             "speaker_change_review": {"status": "ok", "flags": [], "identity_claim": False}}
    seg = _harmonize(tmp_path, monkeypatch, audio)
    assert seg["speaker_count"] == 2
    assert set(seg["speaker_ids"]) == {"SPEAKER_00", "SPEAKER_01"}
    assert seg["dominant_speaker_id"] == "SPEAKER_01"
    assert seg["dominant_speaker_share"] == 0.8


def test_overlapping_turns_are_not_replaced_by_sentence_duration(tmp_path, monkeypatch):
    turns = [{"start": 0, "end": 10, "speaker": "A"},
             {"start": 2, "end": 7, "speaker": "B"}]
    seg = _harmonize(tmp_path, monkeypatch, {"diarization": turns, "speakers": ["A", "B"],
        "speaker_transcript": [{"start": 0, "end": 10, "speaker": "A", "text": "Recognized speech."}]})
    assert seg["speaker_count"] == 2
    assert seg["dominant_speaker_share"] == 0.6667  # Share of attributed track time, including overlap.


def test_absolute_artifact_turns_are_clipped_not_shifted(tmp_path, monkeypatch):
    seg = _harmonize(tmp_path, monkeypatch, {}, start=4, end=14, fallback=[
        {"start": 1, "end": 4, "speaker": "OUTSIDE"},
        {"start": 2, "end": 6, "speaker": "A"},
        {"start": 6, "end": 10, "speaker": "B"},
    ])
    assert set(seg["speaker_ids"]) == {"A", "B"}
    assert seg["speaker_count"] == 2
    assert seg["dominant_speaker_id"] == "B"
    assert seg["dominant_speaker_share"] == 0.6667


@pytest.mark.parametrize("audio,expected", [
    ({"speakers": [], "speaker_count": 0, "diarization": [],
      "diarization_status": "not_applicable", "diarization_note": "no_speech_detected"}, []),
    ({"speaker_transcript": [{"start": 0, "end": 5, "speaker": "A", "text": "Legacy words."}]}, ["A"]),
    ({"speakers": ["A", "A", "B"]}, ["A", "B"]),
])
def test_silence_and_legacy_evidence(tmp_path, monkeypatch, audio, expected):
    seg = _harmonize(tmp_path, monkeypatch, audio)
    assert sorted(seg["speaker_ids"]) == expected
    assert seg["speaker_count"] == len(expected)


def test_text_alignment_is_retained_for_mentions(monkeypatch):
    audio = {"diarization": [{"start": 0, "end": 8, "speaker": "A"},
                             {"start": 8, "end": 10, "speaker": "B"}],
             "speaker_transcript": [{"start": 1, "end": 2, "speaker": "A", "text": "Where is Jane?"}]}
    before = copy.deepcopy(audio)
    result = harmonizer._derive_candidate_visible_people(
        entity_channels={"mentioned_people": [{"text": "Jane"}]}, scene={}, scene_objects=[],
        scene_audio_payload=audio, fallback_speakers=[], scene_start=100, scene_end=110,
        speaker_ids=["A", "B"])
    assert result["speaker_count"] == 2
    assert result["speaker_aligned_mentions"] == [{"text": "Jane", "type": "PERSON", "count": 1}]
    assert audio == before
