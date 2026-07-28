"""Read-only planner for promoting verified recovery scenes into an active epoch.

Recovery epochs intentionally isolate their SQLite, FAISS, and Qdrant writes.
This module is the first gate for a later confirmation-bound promotion: it
proves that every selected scene has complete recovery evidence and a single
matching scene in the target authority.  It never mutates either epoch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any

from steps.common.atomic_io import atomic_write_json_for_concurrent_readers


class RecoveryPromotionPlanError(RuntimeError):
    """Raised when planner inputs are structurally invalid."""


class RecoveryPromotionExecutionError(RuntimeError):
    """Raised when a bounded recovery reconciliation cannot complete safely."""


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryPromotionPlanError(f"cannot read manifest {path}: {exc}") from exc
    # Historical scene-first receipts are JSON arrays containing exactly one
    # video projection.  Normalize only that unambiguous legacy envelope;
    # multi-result arrays remain blocked because they lack a single scope.
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise RecoveryPromotionPlanError(f"manifest is not one scoped object: {path}")
        value = value[0]
    if not isinstance(value, dict):
        raise RecoveryPromotionPlanError(f"manifest is not an object: {path}")
    return value


def _manifest_paths(processing_root: Path) -> list[Path]:
    paths = sorted(processing_root.glob("*/video/scene_manifest.json"))
    if not paths:
        raise RecoveryPromotionPlanError(f"no scene manifests under {processing_root}")
    return paths


def _scene_id(scene: dict[str, Any]) -> str:
    value = scene.get("scene_id") or scene.get("id")
    return str(value) if value else ""


def _recovery_failure(scene: dict[str, Any]) -> str | None:
    audio = scene.get("audio")
    if not isinstance(audio, dict):
        return "missing_audio_projection"
    if audio.get("status") != "success":
        return "audio_not_successful"
    if audio.get("transcript_outcome") != "transcript_available":
        return "transcript_not_available"
    if not isinstance(audio.get("full_text"), str) or not audio["full_text"].strip():
        return "empty_transcript"
    if audio.get("audio_backend_effective") != "wsl":
        return "audio_not_from_wsl"
    if audio.get("audio_backend_downgraded") is True:
        return "audio_backend_downgraded"
    clap_meta = audio.get("clap_meta")
    if not isinstance(clap_meta, dict):
        return "missing_clap_projection"
    if clap_meta.get("status") != "ok":
        return "clap_not_successful"
    if clap_meta.get("component") != "audio_embed_clap":
        return "clap_component_mismatch"
    if clap_meta.get("qdrant_committed") is not True:
        return "clap_qdrant_not_committed"
    if scene.get("qdrant_ok") is not True:
        return "recovery_vectors_not_committed"
    return None


def build_recovery_plan(
    active_processing_root: Path,
    recovery_processing_root: Path,
    recovery_receipt_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Build a scene-scoped, no-mutation recovery promotion plan.

    Matching is deliberately by both video hash and immutable scene ID.  The
    plan rejects ambiguity and incomplete recovery evidence rather than trying
    to infer a target or silently promote a partial projection.
    """
    active_by_video: dict[str, tuple[Path, dict[str, dict[str, Any]]]] = {}
    for path in _manifest_paths(active_processing_root):
        manifest = _read_manifest(path)
        video_hash = str(manifest.get("video_hash") or manifest.get("video_id") or "")
        if not video_hash or video_hash in active_by_video:
            raise RecoveryPromotionPlanError(f"ambiguous active video authority: {path}")
        scenes: dict[str, dict[str, Any]] = {}
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            scene_id = _scene_id(scene)
            if not scene_id or scene_id in scenes:
                raise RecoveryPromotionPlanError(f"ambiguous active scene authority: {path}")
            scenes[scene_id] = scene
        active_by_video[video_hash] = (path, scenes)

    planned: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen_recovery_scenes: set[tuple[str, str]] = set()
    for path in _manifest_paths(recovery_processing_root):
        manifest = _read_manifest(path)
        video_hash = str(manifest.get("video_hash") or manifest.get("video_id") or "")
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            scene_id = _scene_id(scene)
            identity = (video_hash, scene_id)
            failure = _recovery_failure(scene)
            if not video_hash or not scene_id:
                failure = failure or "missing_immutable_identity"
            elif identity in seen_recovery_scenes:
                failure = failure or "duplicate_recovery_scene"
            seen_recovery_scenes.add(identity)
            target = active_by_video.get(video_hash)
            if target is None:
                failure = failure or "target_video_not_found"
            elif scene_id not in target[1]:
                failure = failure or "target_scene_not_found"
            if failure:
                rejected.append({"video_hash": video_hash, "scene_id": scene_id, "reason": failure})
                continue
            planned.append(
                {
                    "video_hash": video_hash,
                    "scene_id": scene_id,
                    "recovery_manifest": str(path),
                    "target_manifest": str(target[0]),
                }
            )

    # A scene-first recovery receipt uses the same scene projection but predates
    # the grouped recovery epoch.  Admit it only through this identical
    # evidence gate; never treat a receipt as a shortcut around manifest checks.
    for path in recovery_receipt_paths:
        manifest = _read_manifest(path)
        video_hash = str(manifest.get("video_hash") or manifest.get("video_id") or "")
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            scene_id = _scene_id(scene)
            identity = (video_hash, scene_id)
            failure = _recovery_failure(scene)
            if not video_hash or not scene_id:
                failure = failure or "missing_immutable_identity"
            elif identity in seen_recovery_scenes:
                failure = failure or "duplicate_recovery_scene"
            seen_recovery_scenes.add(identity)
            target = active_by_video.get(video_hash)
            if target is None:
                failure = failure or "target_video_not_found"
            elif scene_id not in target[1]:
                failure = failure or "target_scene_not_found"
            if failure:
                rejected.append({"video_hash": video_hash, "scene_id": scene_id, "reason": failure})
                continue
            planned.append(
                {
                    "video_hash": video_hash,
                    "scene_id": scene_id,
                    "recovery_manifest": str(path),
                    "target_manifest": str(target[0]),
                }
            )

    return {
        "status": "ready" if planned and not rejected else "blocked",
        "planned_scene_count": len(planned),
        "rejected_scene_count": len(rejected),
        "provenance_policy": {
            "kind": "recovery_addendum",
            "retrieval_effect": "none",
            "ranking_effect": "none",
            "confidence_effect": "none",
            "purpose": "audit_and_relevant_context_only",
        },
        "scenes": planned,
        "rejections": rejected,
    }


_AUDIO_DERIVED_SCENE_FIELDS = (
    "transcript_outcome",
    "transcript_outcome_reason",
    "speaker_ids",
    "speaker_count",
)


def plan_digest(plan: dict[str, Any]) -> str:
    """Return a stable, scope-bound digest for a ready recovery plan."""
    scope = {
        "status": plan.get("status"),
        "provenance_policy": plan.get("provenance_policy"),
        "scenes": [
            {
                "video_hash": scene.get("video_hash"),
                "scene_id": scene.get("scene_id"),
                "recovery_manifest": scene.get("recovery_manifest"),
                "target_manifest": scene.get("target_manifest"),
            }
            for scene in plan.get("scenes", [])
        ],
    }
    encoded = json.dumps(scope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _epoch_root_from_manifest(path: Path) -> Path:
    path = Path(path).resolve()
    if path.name != "scene_manifest.json" or path.parent.name != "video":
        raise RecoveryPromotionExecutionError(f"not a canonical scene manifest: {path}")
    processing_root = path.parent.parent.parent
    if processing_root.name != "processing":
        raise RecoveryPromotionExecutionError(f"manifest is outside a processing root: {path}")
    return processing_root.parent


def _scene_from_manifest(path: Path, video_hash: str, scene_id: str) -> dict[str, Any]:
    manifest = _read_manifest(path)
    actual_hash = str(manifest.get("video_hash") or manifest.get("video_id") or "")
    if actual_hash != video_hash:
        raise RecoveryPromotionExecutionError(f"video identity changed for {path}")
    matches = [scene for scene in manifest.get("scenes", []) if isinstance(scene, dict) and _scene_id(scene) == scene_id]
    if len(matches) != 1:
        raise RecoveryPromotionExecutionError(f"scene authority is no longer singular for {scene_id}")
    return matches[0]


def _rehydrated_scene(target: dict[str, Any], recovery: dict[str, Any], source_path: Path) -> dict[str, Any]:
    if _recovery_failure(recovery):
        raise RecoveryPromotionExecutionError(f"recovery evidence no longer passes for {_scene_id(recovery)}")
    audio = recovery.get("audio")
    if not isinstance(audio, dict):  # guarded above; keeps the write boundary explicit
        raise RecoveryPromotionExecutionError("recovery audio projection is missing")
    result = dict(target)
    result["audio"] = audio
    for field in _AUDIO_DERIVED_SCENE_FIELDS:
        if field in recovery:
            result[field] = recovery[field]
    result["recovery_addendum"] = {
        "kind": "recovery_addendum",
        "source_manifest": str(source_path),
        "retrieval_effect": "none",
        "ranking_effect": "none",
        "confidence_effect": "none",
    }
    return result


def execute_recovery_plan(plan: dict[str, Any], confirmation_token: str) -> dict[str, Any]:
    """Rehydrate only approved audio projections, with backup and compensation.

    ``confirmation_token`` must equal the digest of the exact inspected plan.
    The caller therefore cannot substitute, expand, or reorder a scope between
    inspection and execution. This command never copies recovery vectors: the
    canonical epoch already owns its visual/vector authority.
    """
    if plan.get("status") != "ready" or plan.get("rejected_scene_count") != 0:
        raise RecoveryPromotionExecutionError("only a ready, rejection-free plan may execute")
    expected_token = plan_digest(plan)
    if confirmation_token != expected_token:
        raise RecoveryPromotionExecutionError("confirmation token does not match the inspected plan")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise RecoveryPromotionExecutionError("plan has no scenes")

    target_paths = {Path(item["target_manifest"]).resolve() for item in scenes}
    roots = {_epoch_root_from_manifest(path) for path in target_paths}
    if len(roots) != 1:
        raise RecoveryPromotionExecutionError("plan spans multiple target epochs")
    target_root = roots.pop()
    memory_db = target_root / "memory.db"
    if not memory_db.is_file():
        raise RecoveryPromotionExecutionError(f"target memory authority is absent: {memory_db}")

    operation_id = f"recovery_addendum_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{expected_token[:12]}"
    receipt_root = target_root / "recovery_addenda" / operation_id
    backup_root = receipt_root / "backup"
    backup_root.mkdir(parents=True, exist_ok=False)

    original_manifest_bytes = {path: path.read_bytes() for path in target_paths}
    for index, (path, payload) in enumerate(sorted(original_manifest_bytes.items(), key=lambda item: str(item[0]))):
        (backup_root / f"manifest_{index:02d}.json").write_bytes(payload)
    shutil.copy2(memory_db, backup_root / "memory.db")

    changed_by_path: dict[Path, dict[str, dict[str, Any]]] = {}
    scene_updates: list[tuple[str, str, dict[str, Any]]] = []
    for item in scenes:
        target_path = Path(item["target_manifest"]).resolve()
        source_path = Path(item["recovery_manifest"]).resolve()
        video_hash = str(item["video_hash"])
        scene_id = str(item["scene_id"])
        target_scene = _scene_from_manifest(target_path, video_hash, scene_id)
        recovery_scene = _scene_from_manifest(source_path, video_hash, scene_id)
        replacement = _rehydrated_scene(target_scene, recovery_scene, source_path)
        changed_by_path.setdefault(target_path, {})[scene_id] = replacement
        scene_updates.append((scene_id, video_hash, replacement))

    updated_manifests: dict[Path, dict[str, Any]] = {}
    for path, replacements in changed_by_path.items():
        manifest = _read_manifest(path)
        manifest["scenes"] = [
            replacements.get(_scene_id(scene), scene) if isinstance(scene, dict) else scene
            for scene in manifest.get("scenes", [])
        ]
        updated_manifests[path] = manifest

    try:
        for path, manifest in updated_manifests.items():
            atomic_write_json_for_concurrent_readers(path, manifest)
        connection = sqlite3.connect(memory_db)
        try:
            with connection:
                for scene_id, video_hash, replacement in scene_updates:
                    row = connection.execute(
                        "SELECT meta FROM scenes WHERE id = ? AND video_hash = ?", (scene_id, video_hash)
                    ).fetchone()
                    if row is None:
                        raise RecoveryPromotionExecutionError(f"target scene row disappeared: {scene_id}")
                    connection.execute(
                        "UPDATE scenes SET meta = ? WHERE id = ? AND video_hash = ?",
                        (json.dumps(replacement, ensure_ascii=False), scene_id, video_hash),
                    )
        finally:
            connection.close()
    except Exception as exc:
        for path, payload in original_manifest_bytes.items():
            path.write_bytes(payload)
        shutil.copy2(backup_root / "memory.db", memory_db)
        raise RecoveryPromotionExecutionError(f"recovery reconciliation rolled back: {exc}") from exc

    receipt = {
        "status": "recovery_addendum_committed",
        "operation_id": operation_id,
        "plan_digest": expected_token,
        "scene_count": len(scene_updates),
        "provenance_policy": plan["provenance_policy"],
        "backup_root": str(backup_root),
        "target_epoch": target_root.name,
        "changed_scene_ids": [scene_id for scene_id, _, _ in scene_updates],
        "memory_db_sha256": hashlib.sha256(memory_db.read_bytes()).hexdigest(),
        "manifest_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in updated_manifests
        },
    }
    atomic_write_json_for_concurrent_readers(receipt_root / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect recovery-to-active scene promotion readiness")
    parser.add_argument("--active-processing", type=Path, required=True)
    parser.add_argument("--recovery-processing", type=Path, required=True)
    parser.add_argument("--recovery-receipt", type=Path, action="append", default=[])
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Rehydrate the exact inspected audio scope after supplying its plan-bound token.",
    )
    parser.add_argument(
        "--confirmation-token",
        help="Required only with --execute; must equal the printed plan_digest.",
    )
    args = parser.parse_args()
    try:
        plan = build_recovery_plan(
            args.active_processing,
            args.recovery_processing,
            tuple(args.recovery_receipt),
        )
        plan["plan_digest"] = plan_digest(plan)
        if args.execute:
            if not args.confirmation_token:
                raise RecoveryPromotionExecutionError("--execute requires --confirmation-token")
            print(json.dumps(execute_recovery_plan(plan, args.confirmation_token), indent=2))
        else:
            print(json.dumps(plan, indent=2))
    except (RecoveryPromotionPlanError, RecoveryPromotionExecutionError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
