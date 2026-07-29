from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).parents[2] / "cli" / "content_state_reconciliation.py"
SPEC = importlib.util.spec_from_file_location("content_state_reconciliation", MODULE)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(reconcile)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding="utf-8")


def test_token_bound_reconciliation_updates_only_stale_content_state(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"; manifest_path = processing / "video" / "video" / "scene_manifest.json"; temporal_path = processing / "video" / "temporal_index.json"
    scene = {"scene_id": "scene-a", "duration": 2.0, "content_state": "processing_error", "audio": {"full_text": "usable", "embeddings_error": "keep"}}
    _write(manifest_path, {"scenes": [scene, {"scene_id": "scene-b", "content_state": "processing_error", "audio_error": "real failure"}]})
    _write(temporal_path, {"segments": [{"scene_id": "scene-a", "content_state": "processing_error", "custom": "keep"}, {"scene_id": "scene-b", "content_state": "processing_error"}]})
    plan = reconcile.build_plan(processing, {"scene-a"}); receipt = reconcile.execute_plan(plan, reconcile.plan_digest(plan))
    manifest, temporal = json.loads(manifest_path.read_text()), json.loads(temporal_path.read_text())
    assert receipt["status"] == "content_state_reconciliation_committed"
    assert manifest["scenes"][0]["content_state"] == "signal"
    assert manifest["scenes"][0]["audio"]["embeddings_error"] == "keep"
    assert temporal["segments"][0] == {"scene_id": "scene-a", "content_state": "signal", "custom": "keep"}
    assert manifest["scenes"][1]["content_state"] == "processing_error"


def test_plan_rejects_a_real_processing_error(tmp_path: Path) -> None:
    processing = tmp_path / "epoch" / "processing"
    _write(processing / "video" / "video" / "scene_manifest.json", {"scenes": [{"scene_id": "scene-a", "content_state": "processing_error", "audio_error": "real failure"}]})
    _write(processing / "video" / "temporal_index.json", {"segments": [{"scene_id": "scene-a", "content_state": "processing_error"}]})
    try: reconcile.build_plan(processing)
    except reconcile.ContentStateReconciliationError as exc: assert "no stale" in str(exc)
    else: raise AssertionError("expected real error rejection")
