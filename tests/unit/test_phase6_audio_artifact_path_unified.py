from __future__ import annotations

import json
from pathlib import Path

from steps.video import cross_modal_harmonizer as harmonizer_module
from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_harmonizer_uses_explicit_audio_artifact_dir(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_001"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                }
            ],
        },
    )

    # Deliberately place conflicting transcript data at processing_dir/audio.
    _write_json(
        processing_dir / "audio" / "transcript.json",
        {"segments": [{"start": 0.0, "end": 1.0, "text": "WRONG_SOURCE"}]},
    )

    # Canonical source of truth for Phase 6b audio artifacts.
    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(
        audio_artifact_dir / "transcript.json",
        {"segments": [{"start": 0.0, "end": 1.0, "text": "RIGHT_SOURCE"}]},
    )
    _write_json(
        audio_artifact_dir / "diarization.json",
        {"speakers": []},
    )
    _write_json(
        audio_artifact_dir / "segmentation.json",
        {"segments": []},
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index_path = processing_dir / "temporal_index.json"
    temporal_index = json.loads(temporal_index_path.read_text(encoding="utf-8"))
    full_transcript = temporal_index["segments"][0]["full_transcript"]

    assert "RIGHT_SOURCE" in full_transcript
    assert "WRONG_SOURCE" not in full_transcript


def test_harmonizer_transcript_truth_uses_scene_payload_even_without_commits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_payload_truth"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 5.0,
                    "duration": 5.0,
                    "confidence": 0.9,
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "audio_meta": {"duration_sec": 5.0, "sample_rate": 16000},
                        "transcript": "PAYLOAD_TRANSCRIPT",
                        "segments": [{"start": 0.0, "end": 1.0, "text": "PAYLOAD_SEGMENT"}],
                    },
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    monkeypatch.setattr(
        harmonizer_module,
        "_load_commit_presence",
        lambda *_args, **_kwargs: {
            "available": True,
            "has_audio": False,
            "has_transcripts": False,
            "audio_scene_ids": set(),
            "transcript_scene_ids": set(),
        },
    )

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    segment = temporal_index["segments"][0]

    assert temporal_index["has_transcripts"] is True
    assert temporal_index["has_audio"] is True
    assert segment["has_transcript"] is True
    assert segment["has_audio"] is True
    assert "PAYLOAD_TRANSCRIPT" in segment["full_transcript"]
    assert temporal_index["committed_modalities"]["audio_transcript"] is False


def test_harmonizer_reports_no_transcript_truth_when_no_transcript_sources(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_no_transcript"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                }
            ],
        },
    )

    # Missing transcript.json should keep degraded warning behavior.
    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert result["harmonization_status"] == "degraded"
    assert temporal_index["has_transcripts"] is False
    assert temporal_index["phase6_warning"] == "missing_audio_artifacts"


def test_harmonizer_keeps_complete_for_empty_classified_scenes_without_processing_error(
    tmp_path: Path,
) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_empty_not_error"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 0.6,
                    "duration": 0.6,
                    "confidence": 0.9,
                    "content_state": "empty",
                    "audio": {
                        "path": "audio/scene_0000.wav",
                        "transcript_meta": {"status": "success", "duration": 0.0},
                        "transcript": "",
                        "segments": [],
                    },
                }
            ],
        },
    )

    # Missing required audio artifacts (no transcript/diarization) should not degrade
    # when all classified scenes are empty and none are processing_error.
    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))

    assert result["harmonization_status"] == "complete"
    assert "phase6_warning" not in temporal_index


def test_harmonizer_uses_scene_payload_objects_when_legacy_file_missing(tmp_path: Path) -> None:
    processing_root = tmp_path / "processing"
    video_id = "video_payload_objects"
    processing_dir = processing_root / video_id
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"

    expected_objects = [
        {"label": "person", "score": 0.98, "bbox": [10, 20, 100, 200]},
        {"label": "chair", "score": 0.87, "bbox": [120, 40, 200, 210]},
    ]

    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase5_complete": True,
            "phase6_complete": True,
            "scenes": [
                {
                    "scene_id": "scene_0000",
                    "start": 0.0,
                    "end": 2.0,
                    "duration": 2.0,
                    "confidence": 0.9,
                    "objects": expected_objects,
                }
            ],
        },
    )

    audio_artifact_dir = tmp_path / "canonical_audio_artifacts"
    _write_json(audio_artifact_dir / "transcript.json", {"segments": []})
    _write_json(audio_artifact_dir / "diarization.json", {"speakers": []})
    _write_json(audio_artifact_dir / "segmentation.json", {"segments": []})

    item = {
        "id": video_id,
        "source_path": str(tmp_path / "video.mp4"),
        "processing_dir": str(processing_dir),
        "scene_manifest_path": str(scene_manifest_path),
        "audio_artifact_dir": str(audio_artifact_dir),
    }
    cfg = {"paths": {"processing": str(processing_root)}}

    result = run_cross_modal_harmonization(item, cfg)
    assert result["harmonization_status"] == "complete"

    temporal_index = json.loads((processing_dir / "temporal_index.json").read_text(encoding="utf-8"))
    assert temporal_index["segments"][0]["detected_objects"] == expected_objects
