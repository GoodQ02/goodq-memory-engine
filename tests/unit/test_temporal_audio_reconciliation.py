from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).parents[2] / "cli" / "temporal_audio_reconciliation.py"
SPEC = importlib.util.spec_from_file_location("temporal_audio_reconciliation", MODULE)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_token_bound_reconciliation_changes_only_target_temporal_audio_fields(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    manifest_path = processing / "video-a" / "video" / "scene_manifest.json"
    temporal_path = processing / "video-a" / "temporal_index.json"
    scene = {
        "scene_id": "scene-a", "duration": 10.0,
        "audio": {"path": "audio.wav", "full_text": "Recovered text", "segments": [{"text": "Recovered text"}], "speakers": ["SPEAKER_01"], "diarization_status": "success", "speaker_voice_signatures": [{"speaker": "SPEAKER_01"}], "speaker_voice_signature_meta": {"status": "ok"}},
    }
    untouched = {"scene_id": "scene-b", "full_transcript": "keep", "transcript_segments": ["keep"], "speaker_ids": ["SPEAKER_99"], "custom": "preserve"}
    _write(manifest_path, {"video_id": "video-a", "scenes": [scene]})
    _write(temporal_path, {"segments": [{"scene_id": "scene-a", "full_transcript": "old", "transcript_segments": [], "speaker_ids": [], "custom": "preserve"}, untouched]})
    receipt = tmp_path / "epoch" / "recovery_addenda" / "op" / "receipt.json"
    _write(receipt, {"status": "recovery_addendum_committed", "changed_scene_ids": ["scene-a"]})

    plan = reconcile.build_plan(processing, receipt)
    before_manifest = manifest_path.read_bytes()
    result = reconcile.execute_plan(plan, reconcile.plan_digest(plan))

    assert result["status"] == "temporal_audio_reconciliation_committed"
    assert manifest_path.read_bytes() == before_manifest
    temporal = json.loads(temporal_path.read_text())
    updated = temporal["segments"][0]
    assert updated["full_transcript"] == "Recovered text"
    assert updated["speaker_ids"] == ["SPEAKER_01"]
    assert updated["custom"] == "preserve"
    assert temporal["segments"][1] == untouched
    assert Path(result["backup_root"]).is_dir()


def test_direct_plan_requires_explicit_reason_and_preserves_untargeted_scenes(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    manifest_path = processing / "video-a" / "video" / "scene_manifest.json"
    temporal_path = processing / "video-a" / "temporal_index.json"
    _write(
        manifest_path,
        {"scenes": [{"scene_id": "scene-a", "audio": {"full_text": "Canonical text", "segments": []}}]},
    )
    _write(
        temporal_path,
        {"segments": [
            {"scene_id": "scene-a", "full_transcript": "", "custom": "preserve"},
            {"scene_id": "scene-b", "full_transcript": "untouched"},
        ]},
    )

    try:
        reconcile.build_direct_plan(processing, ["scene-a"], "")
    except reconcile.TemporalAudioReconciliationError as exc:
        assert "requires a reason" in str(exc)
    else:
        raise AssertionError("expected direct plan without reason to fail")

    plan = reconcile.build_direct_plan(processing, ["scene-a"], "canonical_full_text_projection")
    result = reconcile.execute_plan(plan, reconcile.plan_digest(plan))

    assert plan["kind"] == "historical_temporal_audio_reconciliation"
    assert plan["source"]["reason"] == "canonical_full_text_projection"
    assert result["status"] == "temporal_audio_reconciliation_committed"
    temporal = json.loads(temporal_path.read_text())
    assert temporal["segments"][0]["full_transcript"] == "Canonical text"
    assert temporal["segments"][0]["custom"] == "preserve"
    assert temporal["segments"][1] == {"scene_id": "scene-b", "full_transcript": "untouched"}
