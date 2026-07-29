"""Run immediate-next signature backfill batches with an independent audit gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from cli.signature_backfill_batch_execute import (
    BatchExecutionError,
    build_execution_plan,
    execute_batch,
    plan_digest,
)
from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
from steps.common.config_loader import load_configs


class SerialRunError(RuntimeError):
    """A serial signature backfill run cannot safely continue."""


PlanBuilder = Callable[[Path], dict[str, Any]]
BatchExecutor = Callable[[dict[str, Any], str], dict[str, Any]]


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SerialRunError(f"expected object: {path}")
    return value


def audit_batch_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Verify a committed batch against its saved plan and per-scene backups."""
    if receipt.get("status") != "signature_backfill_batch_committed":
        raise SerialRunError("batch did not commit")
    batch_root = Path(str(receipt.get("batch_root") or ""))
    plan = _read(batch_root / "plan.json")
    entries = {str(entry["scene_id"]): entry for entry in plan.get("scenes", [])}
    scene_receipts = receipt.get("scene_receipts")
    completed = receipt.get("completed_scene_ids")
    if not isinstance(scene_receipts, list) or not isinstance(completed, list):
        raise SerialRunError("batch receipt lacks scene receipts")
    if len(completed) != int(plan.get("scene_count") or 0) or len(set(completed)) != len(completed):
        raise SerialRunError("batch receipt scene scope is incomplete or duplicated")

    audited: list[dict[str, Any]] = []
    for scene_receipt in scene_receipts:
        if not isinstance(scene_receipt, dict):
            raise SerialRunError("invalid scene receipt")
        scene_id = str(scene_receipt.get("scene_id") or "")
        entry = entries.get(scene_id)
        backup_root = Path(str(scene_receipt.get("backup_root") or ""))
        if not entry or not backup_root.is_dir():
            raise SerialRunError(f"scene backup authority is absent: {scene_id}")
        proof = _read(batch_root / "proofs" / f"{scene_id}.json")
        if proof.get("status") != "success" or proof.get("device") != "cuda":
            raise SerialRunError(f"scene proof is not CUDA-successful: {scene_id}")
        manifest_before = _read(next(backup_root.glob("*scene_manifest*.json")))
        temporal_before = _read(next(backup_root.glob("*temporal_index*.json")))
        manifest_path = Path(str(entry["manifest_path"]))
        manifest_after = _read(manifest_path)
        temporal_after = _read(manifest_path.parent.parent / "temporal_index.json")
        before_scene = next(scene for scene in manifest_before["scenes"] if scene.get("scene_id") == scene_id)
        after_scene = next(scene for scene in manifest_after["scenes"] if scene.get("scene_id") == scene_id)
        before_segment = next(segment for segment in temporal_before["segments"] if segment.get("scene_id") == scene_id)
        after_segment = next(segment for segment in temporal_after["segments"] if segment.get("scene_id") == scene_id)
        preserved_scene = json.loads(json.dumps(before_scene))
        current_scene = json.loads(json.dumps(after_scene))
        preserved_segment = json.loads(json.dumps(before_segment))
        current_segment = json.loads(json.dumps(after_segment))
        for key in ("speaker_voice_signatures", "speaker_voice_signature_meta"):
            preserved_scene.get("audio", {}).pop(key, None)
            current_scene.get("audio", {}).pop(key, None)
            preserved_segment.pop(key, None)
            current_segment.pop(key, None)
        preserved_segment.pop("speaker_voice_signature_count", None)
        current_segment.pop("speaker_voice_signature_count", None)
        signatures = after_scene.get("audio", {}).get("speaker_voice_signatures", [])
        projected = (
            isinstance(signatures, list)
            and bool(signatures)
            and after_segment.get("speaker_voice_signature_count") == len(signatures)
            and after_segment.get("speaker_voice_signature_meta")
            == after_scene.get("audio", {}).get("speaker_voice_signature_meta")
        )
        if preserved_scene != current_scene or preserved_segment != current_segment or not projected:
            raise SerialRunError(f"post-promotion audit failed: {scene_id}")
        audited.append({"scene_id": scene_id, "signature_count": len(signatures)})
    return {"status": "signature_backfill_batch_audited", "batch_root": str(batch_root), "scene_count": len(audited), "scenes": audited}


def run_serial(
    processing_root: Path,
    *,
    max_batches: int,
    plan_builder: PlanBuilder | None = None,
    batch_executor: BatchExecutor | None = None,
    auditor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run a bounded number of immediate-next batches; stop on any failed gate."""
    if max_batches <= 0:
        raise SerialRunError("max_batches must be positive")
    plan_builder = plan_builder or (lambda root: build_execution_plan(root, batch_index=1))
    batch_executor = batch_executor or execute_batch
    auditor = auditor or audit_batch_receipt
    operation = (
        "signature_backfill_serial_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:12]}"
    )
    run_root = processing_root.parent / "signature_backfill_serial_runs" / operation
    run_root.mkdir(parents=True, exist_ok=False)
    batches: list[dict[str, Any]] = []
    try:
        for number in range(1, max_batches + 1):
            plan = plan_builder(processing_root)
            token = plan_digest(plan)
            receipt = batch_executor(plan, token)
            audit = auditor(receipt)
            batches.append({"sequence": number, "plan_digest": token, "receipt": receipt, "audit": audit})
            atomic_write_json_for_concurrent_readers(run_root / "receipt.json", {
                "status": "running", "operation": operation, "completed_batches": batches,
            })
    except (BatchExecutionError, SerialRunError, OSError, ValueError, StopIteration) as exc:
        payload = {"status": "stopped", "operation": operation, "completed_batches": batches, "error": str(exc)}
        atomic_write_json_for_concurrent_readers(run_root / "receipt.json", payload)
        raise SerialRunError(f"serial run stopped after {len(batches)} audited batches") from exc
    payload = {"status": "committed", "operation": operation, "completed_batches": batches, "batch_count": len(batches), "run_root": str(run_root)}
    atomic_write_json_for_concurrent_readers(run_root / "receipt.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--max-batches", type=int, required=True)
    args = parser.parse_args()
    cfg = load_configs()
    root = args.processing_root or Path(cfg["paths"]["processing"])
    try:
        print(json.dumps(run_serial(root, max_batches=args.max_batches), indent=2))
        return 0
    except SerialRunError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
