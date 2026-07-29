"""Reconcile legacy successful-but-empty transcript outcomes without reprocessing media."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
from steps.common.config_loader import load_configs


OUTCOME = "unclassified"
REASON = "no_explicit_speech_or_quality_outcome"


class TranscriptOutcomeReconciliationError(RuntimeError):
    """The requested metadata-only reconciliation is unsafe to apply."""


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TranscriptOutcomeReconciliationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TranscriptOutcomeReconciliationError(f"expected JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scene_id(value: dict[str, Any]) -> str:
    return str(value.get("scene_id") or value.get("id") or "")


def _is_target(scene: dict[str, Any]) -> bool:
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    meta = audio.get("transcript_meta") if isinstance(audio.get("transcript_meta"), dict) else {}
    text = str(audio.get("full_text") or audio.get("transcript") or "").strip()
    segments = audio.get("segments") if isinstance(audio.get("segments"), list) else []
    has_segment_text = any(isinstance(item, dict) and str(item.get("text") or "").strip() for item in segments)
    audio_path = str(audio.get("path") or "").strip()
    return (
        bool(_scene_id(scene))
        and bool(audio_path and Path(audio_path).is_file())
        and not text and not has_segment_text
        and str(meta.get("status") or "").lower() == "success"
        and not meta.get("error")
        and not scene.get("audio_error")
        and not audio.get("transcript_outcome") and not audio.get("transcript_outcome_reason")
        and not scene.get("transcript_outcome") and not scene.get("transcript_outcome_reason")
    )


def build_plan(processing_root: Path, scene_ids: set[str] | None = None) -> dict[str, Any]:
    """Inspect the bounded legacy outcome class; no mutation occurs here."""
    files: dict[Path, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    requested = set(scene_ids or ())
    found: set[str] = set()
    for manifest_path in sorted(processing_root.glob("*/video/scene_manifest.json")):
        temporal_path = manifest_path.parent.parent / "temporal_index.json"
        if not temporal_path.is_file():
            continue
        manifest, temporal = _read(manifest_path), _read(temporal_path)
        temporal_by_id = {_scene_id(value): value for value in temporal.get("segments", []) if isinstance(value, dict)}
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict) or not _is_target(scene):
                continue
            scene_id = _scene_id(scene)
            if requested and scene_id not in requested:
                continue
            segment = temporal_by_id.get(scene_id)
            if not isinstance(segment, dict):
                raise TranscriptOutcomeReconciliationError(f"temporal segment missing: {scene_id}")
            files.setdefault(manifest_path, {
                "manifest_path": str(manifest_path), "temporal_path": str(temporal_path),
                "manifest_sha256": _sha(manifest_path), "temporal_sha256": _sha(temporal_path),
            })
            entries.append({"scene_id": scene_id, "manifest_path": str(manifest_path), "temporal_path": str(temporal_path)})
            found.add(scene_id)
    if requested - found:
        raise TranscriptOutcomeReconciliationError(f"requested scenes are not eligible: {sorted(requested - found)}")
    if not entries:
        raise TranscriptOutcomeReconciliationError("no eligible legacy transcript outcomes found")
    return {
        "status": "ready", "kind": "historical_transcript_outcome_metadata_reconciliation",
        "processing_root": str(processing_root), "scene_count": len(entries), "file_count": len(files),
        "normalized_outcome": {"outcome": OUTCOME, "reason": REASON},
        "files": [files[path] for path in sorted(files)], "scenes": sorted(entries, key=lambda item: item["scene_id"]),
        "write_scope": [
            "scene.audio.transcript_outcome", "scene.audio.transcript_outcome_reason",
            "scene.transcript_outcome", "scene.transcript_outcome_reason",
            "temporal_index.segments[scene_id].transcript_outcome",
            "temporal_index.segments[scene_id].transcript_outcome_reason",
        ],
        "non_effects": ["no_wsl", "no_media_processing", "no_transcription", "no_diarization", "no_embeddings", "no_vectors", "no_sqlite", "no_graph", "no_reingestion"],
    }


def plan_digest(plan: dict[str, Any]) -> str:
    return _digest({key: value for key, value in plan.items() if key != "status"})


def execute_plan(plan: dict[str, Any], confirmation_token: str) -> dict[str, Any]:
    if plan.get("status") != "ready" or confirmation_token != plan_digest(plan):
        raise TranscriptOutcomeReconciliationError("confirmation token does not match inspected plan")
    files, entries = plan.get("files"), plan.get("scenes")
    if not isinstance(files, list) or not isinstance(entries, list) or not entries:
        raise TranscriptOutcomeReconciliationError("plan is structurally incomplete")
    epoch_root = Path(str(plan["processing_root"])).resolve().parent
    operation_id = f"transcript_outcome_reconciliation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{confirmation_token[:12]}"
    receipt_root, backup_root = epoch_root / "transcript_outcome_reconciliations" / operation_id, epoch_root / "transcript_outcome_reconciliations" / operation_id / "backup"
    backup_root.mkdir(parents=True, exist_ok=False)
    originals: dict[Path, bytes] = {}
    payloads: dict[Path, dict[str, Any]] = {}
    try:
        for index, detail in enumerate(files):
            for label in ("manifest", "temporal"):
                path = Path(str(detail[f"{label}_path"])).resolve()
                if _sha(path) != detail[f"{label}_sha256"]:
                    raise TranscriptOutcomeReconciliationError("authority changed after planning")
                originals[path] = path.read_bytes()
                (backup_root / f"{index:02d}_{label}.json").write_bytes(originals[path])
                payloads[path] = _read(path)
        for entry in entries:
            manifest = payloads[Path(str(entry["manifest_path"])).resolve()]
            temporal = payloads[Path(str(entry["temporal_path"])).resolve()]
            scenes = [value for value in manifest.get("scenes", []) if isinstance(value, dict) and _scene_id(value) == entry["scene_id"]]
            segments = [value for value in temporal.get("segments", []) if isinstance(value, dict) and _scene_id(value) == entry["scene_id"]]
            if len(scenes) != 1 or len(segments) != 1 or not _is_target(scenes[0]):
                raise TranscriptOutcomeReconciliationError(f"scene authority changed: {entry['scene_id']}")
            for target in (scenes[0]["audio"], scenes[0], segments[0]):
                target["transcript_outcome"] = OUTCOME
                target["transcript_outcome_reason"] = REASON
        for path, payload in payloads.items():
            atomic_write_json_for_concurrent_readers(path, payload)
    except Exception as exc:
        for path, raw in originals.items():
            path.write_bytes(raw)
        raise TranscriptOutcomeReconciliationError(f"reconciliation rolled back: {exc}") from exc
    receipt = {"status": "transcript_outcome_reconciliation_committed", "operation_id": operation_id, "plan_digest": confirmation_token, "scene_count": len(entries), "file_count": len(files), "backup_root": str(backup_root), "changed_scene_ids": [item["scene_id"] for item in entries], "normalized_outcome": plan["normalized_outcome"], "write_scope": plan["write_scope"], "non_effects": plan["non_effects"]}
    atomic_write_json_for_concurrent_readers(receipt_root / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation-token")
    args = parser.parse_args()
    root = args.processing_root or Path(load_configs()["paths"]["processing"])
    try:
        plan = build_plan(root, set(args.scene_id) if args.scene_id else None)
        token = plan_digest(plan)
        print(json.dumps(execute_plan(plan, args.confirmation_token) if args.execute else {"plan": plan, "confirmation_token": token}, indent=2))
        return 0
    except TranscriptOutcomeReconciliationError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
