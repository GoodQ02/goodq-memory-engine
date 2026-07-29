from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).parents[2] / "cli" / "transcript_timestamp_reconciliation.py"
SPEC = importlib.util.spec_from_file_location("transcript_timestamp_reconciliation", MODULE)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_token_bound_reconciliation_bounds_only_the_requested_scene(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    manifest_path = processing / "video-a" / "video" / "scene_manifest.json"
    temporal_path = processing / "video-a" / "temporal_index.json"
    target = {
        "scene_id": "scene-a",
        "duration": 10.0,
        "audio": {
            "segments": [
                {"start": -1.0, "end": 2.0, "text": "opening"},
                {"start": 8.0, "end": 18.0, "text": "trailing"},
                {"start": 16.0, "end": 17.0, "text": "outside"},
            ],
            "word_timestamps": [{"start": 8.0, "end": 18.0, "text": "trailing"}],
            "speaker_transcript": [{"start": 16.0, "end": 17.0, "text": "outside"}],
            "full_text": "opening trailing outside",
            "transcript": "opening trailing outside",
        },
    }
    untouched = {"scene_id": "scene-b", "duration": 10.0, "audio": {"segments": [{"start": 0.0, "end": 1.0, "text": "keep"}]}}
    _write(manifest_path, {"scenes": [target, untouched]})
    _write(temporal_path, {"segments": [{"scene_id": "scene-a", "custom": "preserve"}, {"scene_id": "scene-b", "full_transcript": "keep"}]})

    plan = reconcile.build_plan(processing, {"scene-a"})
    receipt = reconcile.execute_plan(plan, reconcile.plan_digest(plan))

    assert receipt["status"] == "transcript_timestamp_reconciliation_committed"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audio = manifest["scenes"][0]["audio"]
    assert audio["segments"] == [
        {"start": 0.0, "end": 2.0, "text": "opening"},
        {"start": 8.0, "end": 10.0, "text": "trailing"},
    ]
    assert audio["word_timestamps"] == [{"start": 8.0, "end": 10.0, "text": "trailing"}]
    assert audio["speaker_transcript"] == []
    assert audio["full_text"] == "opening trailing"
    assert audio["transcription_timing"]["status"] == "reconciled_to_audio_bounds"
    temporal = json.loads(temporal_path.read_text(encoding="utf-8"))
    assert temporal["segments"][0]["full_transcript"] == "opening trailing"
    assert temporal["segments"][0]["custom"] == "preserve"
    assert manifest["scenes"][1] == untouched
    assert temporal["segments"][1] == {"scene_id": "scene-b", "full_transcript": "keep"}


def test_plan_rejects_requested_scene_without_material_overshoot(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    _write(
        processing / "video-a" / "video" / "scene_manifest.json",
        {"scenes": [{"scene_id": "scene-a", "duration": 10.0, "audio": {"segments": [{"start": 0.0, "end": 10.0, "text": "keep"}]}}]},
    )
    _write(processing / "video-a" / "temporal_index.json", {"segments": [{"scene_id": "scene-a"}]})

    try:
        reconcile.build_plan(processing, {"scene-a"})
    except reconcile.TranscriptTimestampReconciliationError as exc:
        assert "not timestamp targets" in str(exc)
    else:
        raise AssertionError("expected bounded scene to be rejected")
