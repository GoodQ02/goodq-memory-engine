"""Read-only planner for promoting verified recovery scenes into an active epoch.

Recovery epochs intentionally isolate their SQLite, FAISS, and Qdrant writes.
This module is the first gate for a later confirmation-bound promotion: it
proves that every selected scene has complete recovery evidence and a single
matching scene in the target authority.  It never mutates either epoch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class RecoveryPromotionPlanError(RuntimeError):
    """Raised when planner inputs are structurally invalid."""


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect recovery-to-active scene promotion readiness")
    parser.add_argument("--active-processing", type=Path, required=True)
    parser.add_argument("--recovery-processing", type=Path, required=True)
    parser.add_argument("--recovery-receipt", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        print(json.dumps(
            build_recovery_plan(
                args.active_processing,
                args.recovery_processing,
                tuple(args.recovery_receipt),
            ),
            indent=2,
        ))
    except RecoveryPromotionPlanError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
