from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


MODULE = Path(__file__).parents[2] / "cli" / "transcript_outcome_reconciliation.py"
SPEC = importlib.util.spec_from_file_location("transcript_outcome_reconciliation", MODULE)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_token_bound_reconciliation_labels_only_eligible_legacy_outcome(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")
    manifest_path = processing / "video" / "video" / "scene_manifest.json"
    temporal_path = processing / "video" / "temporal_index.json"
    scene = {"scene_id": "scene-a", "audio": {"path": str(audio_path), "full_text": "", "segments": [], "transcript_meta": {"status": "success"}}}
    _write(manifest_path, {"scenes": [scene, {"scene_id": "scene-b", "audio": {"path": str(audio_path), "full_text": "keep", "transcript_meta": {"status": "success"}}}]})
    _write(temporal_path, {"segments": [{"scene_id": "scene-a", "custom": "keep"}, {"scene_id": "scene-b", "custom": "untouched"}]})

    plan = reconcile.build_plan(processing, {"scene-a"})
    receipt = reconcile.execute_plan(plan, reconcile.plan_digest(plan))

    assert receipt["status"] == "transcript_outcome_reconciliation_committed"
    manifest = json.loads(manifest_path.read_text())
    temporal = json.loads(temporal_path.read_text())
    assert manifest["scenes"][0]["audio"]["transcript_outcome"] == "unclassified"
    assert manifest["scenes"][0]["transcript_outcome_reason"] == "no_explicit_speech_or_quality_outcome"
    assert temporal["segments"][0]["custom"] == "keep"
    assert temporal["segments"][1] == {"scene_id": "scene-b", "custom": "untouched"}


def test_plan_rejects_missing_audio_or_failed_metadata(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    manifest_path = processing / "video" / "video" / "scene_manifest.json"
    _write(manifest_path, {"scenes": [{"scene_id": "scene-a", "audio": {"path": "missing.wav", "transcript_meta": {"status": "success"}}}]})
    _write(processing / "video" / "temporal_index.json", {"segments": [{"scene_id": "scene-a"}]})
    try:
        reconcile.build_plan(processing)
    except reconcile.TranscriptOutcomeReconciliationError as exc:
        assert "no eligible" in str(exc)
    else:
        raise AssertionError("expected missing audio to be rejected")


def test_direct_cli_prefers_its_own_repository_root(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")
    _write(
        processing / "video" / "video" / "scene_manifest.json",
        {"scenes": [{"scene_id": "scene-a", "audio": {"path": str(audio_path), "transcript_meta": {"status": "success"}}}]},
    )
    _write(processing / "video" / "temporal_index.json", {"segments": [{"scene_id": "scene-a"}]})
    env = dict(os.environ)
    env["PYTHONPATH"] = str(MODULE.parents[3])
    result = subprocess.run(
        [sys.executable, str(MODULE), "--processing-root", str(processing)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["plan"]["scene_count"] == 1
