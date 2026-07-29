import json
from pathlib import Path

import pytest

from cli.diarization_outcome_reconciliation import (
    DiarizationOutcomeReconciliationError,
    NORMALIZED_NOTE,
    NORMALIZED_STATUS,
    build_plan,
    execute_plan,
    plan_digest,
)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _scene(scene_id: str, signature: dict) -> dict:
    return {
        "scene_id": scene_id,
        "diarization_status": "success",
        "keep": "scene",
        "audio": {
            "diarization_status": "success",
            "diarization_note": None,
            "diarization": [],
            "speaker_count": 0,
            "speakers": [],
            "speaker_voice_signature_meta": signature,
            "full_text": "keep transcript",
        },
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    processing = tmp_path / "epoch" / "processing"
    manifest = processing / "video-a" / "video" / "scene_manifest.json"
    temporal = processing / "video-a" / "temporal_index.json"
    target = _scene("target", {"status": "error", "reason": "embedding_step_failed"})
    excluded = _scene("excluded", {"status": "skipped", "reason": "diarization_unavailable"})
    _write(manifest, {"scenes": [target, excluded]})
    _write(temporal, {"segments": [{"scene_id": "target", "diarization_status": "success", "keep": "temporal"}, {"scene_id": "excluded", "diarization_status": "success"}]})
    return processing, manifest, temporal


def test_plan_targets_only_legacy_signature_failure_zero_tracks(tmp_path: Path) -> None:
    processing, manifest, temporal = _fixture(tmp_path)
    plan = build_plan(processing)

    assert plan["scene_count"] == 1
    assert plan["scenes"] == [{"scene_id": "target", "manifest_path": str(manifest), "temporal_path": str(temporal)}]
    assert plan["normalized_outcome"]["status"] == NORMALIZED_STATUS
    assert "no_wsl" in plan["non_effects"]


def test_token_bound_reconciliation_changes_only_diarization_metadata(tmp_path: Path) -> None:
    processing, manifest, temporal = _fixture(tmp_path)
    plan = build_plan(processing)
    receipt = execute_plan(plan, plan_digest(plan))

    output = json.loads(manifest.read_text(encoding="utf-8"))
    segment = json.loads(temporal.read_text(encoding="utf-8"))["segments"][0]
    target = output["scenes"][0]
    excluded = output["scenes"][1]
    assert receipt["status"] == "diarization_outcome_reconciliation_committed"
    assert Path(receipt["backup_root"]).is_dir()
    assert target["keep"] == "scene"
    assert target["audio"]["full_text"] == "keep transcript"
    assert target["diarization_status"] == NORMALIZED_STATUS
    assert target["audio"]["diarization_status"] == NORMALIZED_STATUS
    assert target["audio"]["diarization_note"] == NORMALIZED_NOTE
    assert segment["keep"] == "temporal"
    assert segment["diarization_status"] == NORMALIZED_STATUS
    assert excluded["diarization_status"] == "success"


def test_reconciliation_rejects_unbound_token_without_writing(tmp_path: Path) -> None:
    processing, manifest, _ = _fixture(tmp_path)
    plan = build_plan(processing)

    with pytest.raises(DiarizationOutcomeReconciliationError, match="confirmation token"):
        execute_plan(plan, "wrong-token")
    assert json.loads(manifest.read_text(encoding="utf-8"))["scenes"][0]["diarization_status"] == "success"
