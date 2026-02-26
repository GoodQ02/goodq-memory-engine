from __future__ import annotations

import json
from pathlib import Path

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
