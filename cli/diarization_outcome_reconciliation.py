"""Reconcile historical zero-track diarization labels without recomputing media."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
from steps.common.config_loader import load_configs


TARGET_STATUS = "success"
TARGET_SIGNATURE_STATUS = "error"
TARGET_SIGNATURE_REASON = "embedding_step_failed"
NORMALIZED_STATUS = "completed_no_speakers"
NORMALIZED_NOTE = "diarization completed without emitted speaker tracks"


class DiarizationOutcomeReconciliationError(RuntimeError):
    """The inspected metadata-only reconciliation is unsafe to apply."""


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiarizationOutcomeReconciliationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DiarizationOutcomeReconciliationError(f"expected JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _scene_id(value: dict[str, Any]) -> str:
    scene_id = value.get("scene_id") or value.get("id")
    return str(scene_id) if scene_id else ""


def _is_target(scene: dict[str, Any]) -> bool:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    signature = audio.get("speaker_voice_signature_meta")
    signature = signature if isinstance(signature, dict) else {}
    return (
        bool(_scene_id(scene))
        and scene.get("diarization_status") == TARGET_STATUS
        and audio.get("diarization_status") == TARGET_STATUS
        and isinstance(audio.get("diarization"), list)
        and not audio["diarization"]
        and int(audio.get("speaker_count") or 0) == 0
        and not audio.get("speakers")
        and signature.get("status") == TARGET_SIGNATURE_STATUS
        and signature.get("reason") == TARGET_SIGNATURE_REASON
    )


def build_plan(processing_root: Path) -> dict[str, Any]:
    """Inspect exactly the legacy signature-failure zero-track class."""
    files: dict[Path, dict[str, Any]] = {}
    scenes: list[dict[str, Any]] = []
    for manifest_path in sorted(processing_root.glob("*/video/scene_manifest.json")):
        temporal_path = manifest_path.parent.parent / "temporal_index.json"
        if not temporal_path.is_file():
            continue
        manifest = _read(manifest_path)
        temporal = _read(temporal_path)
        segments = {
            _scene_id(segment): segment
            for segment in temporal.get("segments", [])
            if isinstance(segment, dict) and _scene_id(segment)
        }
        selected = [scene for scene in manifest.get("scenes", []) if isinstance(scene, dict) and _is_target(scene)]
        if not selected:
            continue
        files[manifest_path] = {
            "manifest_path": str(manifest_path),
            "temporal_path": str(temporal_path),
            "manifest_sha256": _sha(manifest_path),
            "temporal_sha256": _sha(temporal_path),
        }
        for scene in selected:
            scene_id = _scene_id(scene)
            segment = segments.get(scene_id)
            if not isinstance(segment, dict):
                raise DiarizationOutcomeReconciliationError(f"temporal segment missing: {scene_id}")
            if segment.get("diarization_status") != TARGET_STATUS:
                raise DiarizationOutcomeReconciliationError(f"temporal status is not legacy success: {scene_id}")
            scenes.append({"scene_id": scene_id, "manifest_path": str(manifest_path), "temporal_path": str(temporal_path)})
    if not scenes:
        raise DiarizationOutcomeReconciliationError("no historical zero-track diarization targets found")
    return {
        "status": "ready",
        "kind": "historical_zero_track_diarization_metadata_reconciliation",
        "processing_root": str(processing_root),
        "scene_count": len(scenes),
        "file_count": len(files),
        "target_contract": {
            "audio_diarization_status": TARGET_STATUS,
            "scene_diarization_status": TARGET_STATUS,
            "speaker_count": 0,
            "diarization_segments": 0,
            "signature_status": TARGET_SIGNATURE_STATUS,
            "signature_reason": TARGET_SIGNATURE_REASON,
        },
        "normalized_outcome": {"status": NORMALIZED_STATUS, "note": NORMALIZED_NOTE},
        "files": [files[path] for path in sorted(files)],
        "scenes": sorted(scenes, key=lambda item: item["scene_id"]),
        "write_scope": [
            "scene.audio.diarization_status",
            "scene.audio.diarization_note",
            "scene.diarization_status",
            "scene.diarization_note",
            "temporal_index.segments[scene_id].diarization_status",
            "temporal_index.segments[scene_id].diarization_note",
        ],
        "non_effects": [
            "no_wsl", "no_media_processing", "no_transcription", "no_diarization",
            "no_signatures", "no_vectors", "no_sqlite", "no_graph", "no_reingestion",
        ],
    }


def plan_digest(plan: dict[str, Any]) -> str:
    return _digest({key: value for key, value in plan.items() if key != "status"})


def execute_plan(plan: dict[str, Any], confirmation_token: str) -> dict[str, Any]:
    """Apply only the inspected metadata fields with file-level rollback."""
    if plan.get("status") != "ready" or confirmation_token != plan_digest(plan):
        raise DiarizationOutcomeReconciliationError("confirmation token does not match inspected plan")
    files = plan.get("files")
    scenes = plan.get("scenes")
    if not isinstance(files, list) or not isinstance(scenes, list) or not scenes:
        raise DiarizationOutcomeReconciliationError("plan is structurally incomplete")
    file_by_manifest = {Path(str(item["manifest_path"])).resolve(): item for item in files}
    epoch_root = Path(str(plan["processing_root"])).resolve().parent
    operation_id = f"diarization_outcome_reconciliation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{confirmation_token[:12]}"
    receipt_root = epoch_root / "diarization_outcome_reconciliations" / operation_id
    backup_root = receipt_root / "backup"
    backup_root.mkdir(parents=True, exist_ok=False)
    originals: dict[Path, bytes] = {}
    manifests: dict[Path, dict[str, Any]] = {}
    temporals: dict[Path, dict[str, Any]] = {}
    for index, detail in enumerate(files):
        manifest_path = Path(str(detail["manifest_path"])).resolve()
        temporal_path = Path(str(detail["temporal_path"])).resolve()
        if _sha(manifest_path) != detail["manifest_sha256"] or _sha(temporal_path) != detail["temporal_sha256"]:
            raise DiarizationOutcomeReconciliationError("authority changed after planning")
        for label, path in (("manifest", manifest_path), ("temporal", temporal_path)):
            originals[path] = path.read_bytes()
            (backup_root / f"{index:02d}_{label}.json").write_bytes(originals[path])
        manifests[manifest_path] = _read(manifest_path)
        temporals[temporal_path] = _read(temporal_path)
    try:
        for entry in scenes:
            manifest_path = Path(str(entry["manifest_path"])).resolve()
            detail = file_by_manifest.get(manifest_path)
            if detail is None:
                raise DiarizationOutcomeReconciliationError("scene refers to an unplanned manifest")
            temporal_path = Path(str(detail["temporal_path"])).resolve()
            manifest = manifests[manifest_path]
            temporal = temporals[temporal_path]
            candidates = [scene for scene in manifest.get("scenes", []) if isinstance(scene, dict) and _scene_id(scene) == entry["scene_id"]]
            segments = [segment for segment in temporal.get("segments", []) if isinstance(segment, dict) and _scene_id(segment) == entry["scene_id"]]
            if len(candidates) != 1 or len(segments) != 1 or not _is_target(candidates[0]):
                raise DiarizationOutcomeReconciliationError(f"scene authority changed: {entry['scene_id']}")
            if segments[0].get("diarization_status") != TARGET_STATUS:
                raise DiarizationOutcomeReconciliationError(f"temporal authority changed: {entry['scene_id']}")
            scene = candidates[0]
            audio = scene["audio"]
            for target in (audio, scene, segments[0]):
                target["diarization_status"] = NORMALIZED_STATUS
                target["diarization_note"] = NORMALIZED_NOTE
        for path, payload in manifests.items():
            atomic_write_json_for_concurrent_readers(path, payload)
        for path, payload in temporals.items():
            atomic_write_json_for_concurrent_readers(path, payload)
    except Exception as exc:
        for path, raw in originals.items():
            path.write_bytes(raw)
        raise DiarizationOutcomeReconciliationError(f"reconciliation rolled back: {exc}") from exc
    receipt = {
        "status": "diarization_outcome_reconciliation_committed",
        "operation_id": operation_id,
        "plan_digest": confirmation_token,
        "scene_count": len(scenes),
        "file_count": len(files),
        "backup_root": str(backup_root),
        "changed_scene_ids": [entry["scene_id"] for entry in scenes],
        "normalized_outcome": plan["normalized_outcome"],
        "write_scope": plan["write_scope"],
        "non_effects": plan["non_effects"],
        "manifest_sha256": {str(path): _sha(path) for path in manifests},
        "temporal_sha256": {str(path): _sha(path) for path in temporals},
    }
    atomic_write_json_for_concurrent_readers(receipt_root / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation-token")
    args = parser.parse_args()
    processing_root = args.processing_root or Path(load_configs()["paths"]["processing"])
    try:
        plan = build_plan(processing_root)
        token = plan_digest(plan)
        if not args.execute:
            print(json.dumps({"plan": plan, "confirmation_token": token}, indent=2))
            return 0
        if not args.confirmation_token:
            raise DiarizationOutcomeReconciliationError("--confirmation-token is required with --execute")
        print(json.dumps(execute_plan(plan, args.confirmation_token), indent=2))
        return 0
    except DiarizationOutcomeReconciliationError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
