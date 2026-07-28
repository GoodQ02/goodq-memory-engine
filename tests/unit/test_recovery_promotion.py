from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cli.recovery_promotion import (
    RecoveryPromotionExecutionError,
    build_recovery_plan,
    execute_recovery_plan,
    plan_digest,
)


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


def _create_target_db(root: Path, scene: dict) -> None:
    connection = sqlite3.connect(root / "memory.db")
    try:
        connection.execute("CREATE TABLE scenes (id TEXT PRIMARY KEY, video_hash TEXT, meta TEXT)")
        connection.execute(
            "INSERT INTO scenes (id, video_hash, meta) VALUES (?, ?, ?)",
            (scene["scene_id"], "video-a", json.dumps(scene)),
        )
        connection.commit()
    finally:
        connection.close()


def test_execute_rehydrates_only_audio_projection_with_a_receipt(tmp_path: Path) -> None:
    active = tmp_path / "active" / "processing"
    recovery = tmp_path / "recovery" / "processing"
    target = {"scene_id": "scene-a", "visual": {"caption": "keep"}}
    _write_manifest(active, "video-a", [target])
    _write_manifest(recovery, "video-a", [_recovered_scene("scene-a")])
    _create_target_db(active.parent, target)

    plan = build_recovery_plan(active, recovery)
    receipt = execute_recovery_plan(plan, plan_digest(plan))

    assert receipt["status"] == "recovery_addendum_committed"
    assert receipt["scene_count"] == 1
    manifest = json.loads((active / "video-a" / "video" / "scene_manifest.json").read_text())
    scene = manifest["scenes"][0]
    assert scene["visual"] == {"caption": "keep"}
    assert scene["audio"]["full_text"] == "verified transcript"
    assert scene["recovery_addendum"]["retrieval_effect"] == "none"
    connection = sqlite3.connect(active.parent / "memory.db")
    try:
        meta = json.loads(connection.execute("SELECT meta FROM scenes WHERE id = 'scene-a'").fetchone()[0])
    finally:
        connection.close()
    assert meta["audio"]["full_text"] == "verified transcript"


def test_execute_rejects_an_unbound_confirmation_token(tmp_path: Path) -> None:
    active, recovery = tmp_path / "active" / "processing", tmp_path / "recovery" / "processing"
    target = {"scene_id": "scene-a"}
    _write_manifest(active, "video-a", [target])
    _write_manifest(recovery, "video-a", [_recovered_scene("scene-a")])
    _create_target_db(active.parent, target)
    with pytest.raises(RecoveryPromotionExecutionError, match="confirmation token"):
        execute_recovery_plan(build_recovery_plan(active, recovery), "wrong-token")
