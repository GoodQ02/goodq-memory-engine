from __future__ import annotations

import json
from pathlib import Path

from cli.recovery_promotion import build_recovery_plan


def _write_manifest(root: Path, video_hash: str, scenes: list[dict]) -> None:
    path = root / video_hash / "video" / "scene_manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"video_hash": video_hash, "scenes": scenes}), encoding="utf-8")


def _recovered_scene(scene_id: str) -> dict:
    return {
        "scene_id": scene_id,
        "qdrant_ok": True,
        "audio": {
            "status": "success",
            "transcript_outcome": "transcript_available",
            "full_text": "verified transcript",
            "audio_backend_effective": "wsl",
            "audio_backend_downgraded": False,
            "clap_meta": {
                "status": "ok",
                "component": "audio_embed_clap",
                "qdrant_committed": True,
            },
        },
    }


def test_plan_accepts_exact_recovered_scene_with_matching_target(tmp_path: Path) -> None:
    active, recovery = tmp_path / "active", tmp_path / "recovery"
    _write_manifest(active, "video-a", [{"scene_id": "scene-a"}])
    _write_manifest(recovery, "video-a", [_recovered_scene("scene-a")])

    plan = build_recovery_plan(active, recovery)

    assert plan["status"] == "ready"
    assert plan["planned_scene_count"] == 1
    assert plan["rejections"] == []
    assert plan["provenance_policy"] == {
        "kind": "recovery_addendum",
        "retrieval_effect": "none",
        "ranking_effect": "none",
        "confidence_effect": "none",
        "purpose": "audit_and_relevant_context_only",
    }


def test_plan_blocks_partial_or_ambiguous_recovery_evidence(tmp_path: Path) -> None:
    active, recovery = tmp_path / "active", tmp_path / "recovery"
    _write_manifest(active, "video-a", [{"scene_id": "scene-a"}])
    incomplete = _recovered_scene("scene-a")
    incomplete["audio"]["full_text"] = ""
    _write_manifest(recovery, "video-a", [incomplete])

    plan = build_recovery_plan(active, recovery)

    assert plan["status"] == "blocked"
    assert plan["rejected_scene_count"] == 1
    assert plan["rejections"][0]["reason"] == "empty_transcript"


def test_plan_blocks_legacy_audio_without_persisted_clap(tmp_path: Path) -> None:
    active, recovery = tmp_path / "active", tmp_path / "recovery"
    _write_manifest(active, "video-a", [{"scene_id": "scene-a"}])
    incomplete = _recovered_scene("scene-a")
    incomplete["audio"]["clap_meta"] = {"status": "skipped"}
    _write_manifest(recovery, "video-a", [incomplete])

    plan = build_recovery_plan(active, recovery)

    assert plan["status"] == "blocked"
    assert plan["rejected_scene_count"] == 1
    assert plan["rejections"][0]["reason"] == "clap_not_successful"


def test_plan_admits_scene_first_receipt_through_the_same_gate(tmp_path: Path) -> None:
    active, recovery = tmp_path / "active", tmp_path / "recovery"
    _write_manifest(active, "video-a", [{"scene_id": "scene-a"}])
    _write_manifest(recovery, "video-a", [])
    receipt = tmp_path / "scene_first_receipt.json"
    receipt.write_text(
        json.dumps([{"video_hash": "video-a", "scenes": [_recovered_scene("scene-a")]}]),
        encoding="utf-8",
    )

    plan = build_recovery_plan(active, recovery, (receipt,))

    assert plan["status"] == "ready"
    assert plan["planned_scene_count"] == 1
