"""Reconcile a committed recovery addendum into temporal-index audio fields only."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.atomic_io import atomic_write_json_for_concurrent_readers


class TemporalAudioReconciliationError(RuntimeError):
    """The requested temporal projection is not safe to apply."""


_FIELDS = (
    "full_transcript",
    "transcript_segments",
    "speaker_ids",
    "diarization_status",
    "diarization_error",
    "diarization_note",
    "speaker_voice_signature_count",
    "speaker_voice_signature_meta",
    "has_audio",
    "has_transcript",
    "has_speakers",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemporalAudioReconciliationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TemporalAudioReconciliationError(f"expected JSON object: {path}")
    return value


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _scene_id(scene: dict[str, Any]) -> str:
    value = scene.get("scene_id") or scene.get("id")
    return str(value) if value else ""


def _speaker_ids(scene: dict[str, Any]) -> list[str]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    inputs: list[Any] = [scene.get("speaker_ids"), audio.get("speakers")]
    inputs.extend(audio.get(key) for key in ("speaker_transcript", "speaker_segments", "diarization"))
    result: list[str] = []
    for candidates in inputs:
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            value = candidate if isinstance(candidate, str) else candidate.get("speaker", candidate.get("label")) if isinstance(candidate, dict) else None
            if isinstance(value, str) and value.strip() and value.strip() not in result:
                result.append(value.strip())
    return result


def _audio_projection(scene: dict[str, Any]) -> dict[str, Any]:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else None
    if not isinstance(audio, dict):
        raise TemporalAudioReconciliationError(f"scene {_scene_id(scene)} has no canonical audio projection")
    transcript = str(audio.get("full_text") or audio.get("transcript") or "").strip()
    segments = audio.get("segments") if isinstance(audio.get("segments"), list) else []
    transcript_segments = [
        str(segment.get("text") or "").strip()
        for segment in segments
        if isinstance(segment, dict) and str(segment.get("text") or "").strip()
    ]
    speakers = _speaker_ids(scene)
    signatures = audio.get("speaker_voice_signatures")
    signatures = signatures if isinstance(signatures, list) else []
    has_audio = bool(audio.get("path") or audio.get("audio_meta") or segments or transcript)
    return {
        "full_transcript": transcript,
        "transcript_segments": transcript_segments,
        "speaker_ids": speakers,
        "diarization_status": audio.get("diarization_status"),
        "diarization_error": audio.get("diarization_error"),
        "diarization_note": audio.get("diarization_note"),
        "speaker_voice_signature_count": len(signatures),
        "speaker_voice_signature_meta": audio.get("speaker_voice_signature_meta"),
        "has_audio": has_audio,
        "has_transcript": bool(transcript or transcript_segments),
        "has_speakers": bool(has_audio and speakers),
    }


def _receipt_scene_ids(receipt_path: Path) -> set[str]:
    receipt = _read_json(receipt_path)
    if receipt.get("status") != "recovery_addendum_committed":
        raise TemporalAudioReconciliationError("receipt is not a committed recovery addendum")
    ids = receipt.get("changed_scene_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(value, str) and value for value in ids):
        raise TemporalAudioReconciliationError("receipt has no valid changed_scene_ids")
    if len(set(ids)) != len(ids):
        raise TemporalAudioReconciliationError("receipt changed_scene_ids are not unique")
    return set(ids)


def _build_plan(
    processing_root: Path,
    targets: set[str],
    *,
    kind: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    """Build an exact no-mutation temporal audio projection plan."""
    remaining = set(targets)
    files: dict[Path, dict[str, Any]] = {}
    scene_entries: list[dict[str, Any]] = []
    for manifest_path in sorted(processing_root.glob("*/video/scene_manifest.json")):
        temporal_path = manifest_path.parent.parent / "temporal_index.json"
        if not temporal_path.is_file():
            continue
        manifest = _read_json(manifest_path)
        temporal = _read_json(temporal_path)
        temporal_segments = {
            _scene_id(segment): segment
            for segment in temporal.get("segments", [])
            if isinstance(segment, dict) and _scene_id(segment)
        }
        matches = [scene for scene in manifest.get("scenes", []) if isinstance(scene, dict) and _scene_id(scene) in targets]
        if not matches:
            continue
        files[temporal_path] = {
            "manifest_path": str(manifest_path),
            "temporal_sha256": hashlib.sha256(temporal_path.read_bytes()).hexdigest(),
        }
        for scene in matches:
            scene_id = _scene_id(scene)
            if scene_id not in remaining:
                raise TemporalAudioReconciliationError(f"scene is ambiguous across manifests: {scene_id}")
            segment = temporal_segments.get(scene_id)
            if segment is None:
                raise TemporalAudioReconciliationError(f"temporal segment missing for {scene_id}")
            projection = _audio_projection(scene)
            scene_entries.append(
                {
                    "scene_id": scene_id,
                    "manifest_path": str(manifest_path),
                    "temporal_path": str(temporal_path),
                    "projection_digest": _canonical_digest(projection),
                    "changed_fields": [field for field in _FIELDS if segment.get(field) != projection[field]],
                }
            )
            remaining.remove(scene_id)
    if remaining:
        raise TemporalAudioReconciliationError(f"receipt targets absent from canonical manifests: {sorted(remaining)}")
    if len(scene_entries) != len(targets):
        raise TemporalAudioReconciliationError("plan scope is incomplete")
    return {
        "status": "ready",
        "kind": kind,
        "source": source,
        "processing_root": str(processing_root),
        "operation_root": str(processing_root.parent),
        "scene_count": len(scene_entries),
        "temporal_file_count": len(files),
        "fields": list(_FIELDS),
        "files": [
            {"temporal_path": str(path), **details}
            for path, details in sorted(files.items(), key=lambda item: str(item[0]))
        ],
        "scenes": sorted(scene_entries, key=lambda item: item["scene_id"]),
        "provenance_policy": {
            "kind": "recovery_addendum",
            "retrieval_effect": "none",
            "ranking_effect": "none",
            "confidence_effect": "none",
        },
    }


def build_plan(processing_root: Path, receipt_path: Path) -> dict[str, Any]:
    """Build the exact no-mutation plan for one committed recovery addendum."""
    return _build_plan(
        processing_root,
        _receipt_scene_ids(receipt_path),
        kind="recovery_addendum_temporal_audio_reconciliation",
        source={"kind": "recovery_addendum", "receipt_path": str(receipt_path)},
    )


def build_direct_plan(processing_root: Path, scene_ids: list[str], reason: str) -> dict[str, Any]:
    """Plan an explicit historical projection repair without inventing a receipt."""
    targets = {scene_id.strip() for scene_id in scene_ids if scene_id.strip()}
    if not targets or len(targets) != len(scene_ids):
        raise TemporalAudioReconciliationError("scene ids must be non-empty and unique")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise TemporalAudioReconciliationError("direct reconciliation requires a reason")
    return _build_plan(
        processing_root,
        targets,
        kind="historical_temporal_audio_reconciliation",
        source={"kind": "explicit_scene_ids", "reason": normalized_reason, "scene_ids": sorted(targets)},
    )


def plan_digest(plan: dict[str, Any]) -> str:
    scope = {
        key: plan.get(key)
        for key in ("kind", "source", "processing_root", "operation_root", "scene_count", "temporal_file_count", "fields", "files", "scenes", "provenance_policy")
    }
    return _canonical_digest(scope)


def execute_plan(plan: dict[str, Any], confirmation_token: str) -> dict[str, Any]:
    """Apply only a token-bound temporal projection, with backup and rollback."""
    if plan.get("status") != "ready" or confirmation_token != plan_digest(plan):
        raise TemporalAudioReconciliationError("confirmation token does not match the inspected plan")
    files = plan.get("files")
    scenes = plan.get("scenes")
    if not isinstance(files, list) or not isinstance(scenes, list) or not scenes:
        raise TemporalAudioReconciliationError("plan is structurally incomplete")
    target_root = Path(str(plan["operation_root"])).resolve()
    operation_id = f"temporal_audio_reconciliation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{confirmation_token[:12]}"
    receipt_root = target_root / "temporal_reconciliations" / operation_id
    backup_root = receipt_root / "backup"
    backup_root.mkdir(parents=True, exist_ok=False)
    originals: dict[Path, bytes] = {}
    temporal_by_path: dict[Path, dict[str, Any]] = {}
    for index, detail in enumerate(files):
        path = Path(str(detail["temporal_path"])).resolve()
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != detail["temporal_sha256"]:
            raise TemporalAudioReconciliationError(f"temporal authority changed after planning: {path}")
        originals[path] = payload
        (backup_root / f"temporal_{index:02d}.json").write_bytes(payload)
        temporal_by_path[path] = _read_json(path)
    try:
        for entry in scenes:
            manifest = _read_json(Path(str(entry["manifest_path"])))
            matches = [scene for scene in manifest.get("scenes", []) if isinstance(scene, dict) and _scene_id(scene) == entry["scene_id"]]
            if len(matches) != 1:
                raise TemporalAudioReconciliationError(f"scene authority changed: {entry['scene_id']}")
            projection = _audio_projection(matches[0])
            if _canonical_digest(projection) != entry["projection_digest"]:
                raise TemporalAudioReconciliationError(f"audio projection changed after planning: {entry['scene_id']}")
            temporal = temporal_by_path[Path(str(entry["temporal_path"])).resolve()]
            targets = [segment for segment in temporal.get("segments", []) if isinstance(segment, dict) and _scene_id(segment) == entry["scene_id"]]
            if len(targets) != 1:
                raise TemporalAudioReconciliationError(f"temporal segment changed: {entry['scene_id']}")
            targets[0].update(projection)
        for temporal in temporal_by_path.values():
            segments = [segment for segment in temporal.get("segments", []) if isinstance(segment, dict)]
            temporal["has_audio"] = any(segment.get("has_audio") for segment in segments)
            temporal["has_transcripts"] = any(segment.get("has_transcript") for segment in segments)
            temporal["segments_with_speaker_voice_signatures"] = sum(
                1 for segment in segments if int(segment.get("speaker_voice_signature_count") or 0) > 0
            )
        for path, temporal in temporal_by_path.items():
            atomic_write_json_for_concurrent_readers(path, temporal)
    except Exception as exc:
        for path, payload in originals.items():
            path.write_bytes(payload)
        raise TemporalAudioReconciliationError(f"reconciliation rolled back: {exc}") from exc
    receipt = {
        "status": "temporal_audio_reconciliation_committed",
        "operation_id": operation_id,
        "plan_digest": confirmation_token,
        "scene_count": len(scenes),
        "temporal_file_count": len(files),
        "fields": plan["fields"],
        "backup_root": str(backup_root),
        "changed_scene_ids": [entry["scene_id"] for entry in scenes],
        "temporal_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in temporal_by_path},
        "provenance_policy": plan["provenance_policy"],
    }
    atomic_write_json_for_concurrent_readers(receipt_root / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--receipt", type=Path)
    source.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--reason", help="Required with --scene-id; stored as repair provenance.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation-token")
    args = parser.parse_args()
    try:
        plan = (
            build_plan(args.processing_root, args.receipt)
            if args.receipt is not None
            else build_direct_plan(args.processing_root, args.scene_id, str(args.reason or ""))
        )
        plan["plan_digest"] = plan_digest(plan)
        result: dict[str, Any] = plan
        if args.execute:
            result = execute_plan(plan, str(args.confirmation_token or ""))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except TemporalAudioReconciliationError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
