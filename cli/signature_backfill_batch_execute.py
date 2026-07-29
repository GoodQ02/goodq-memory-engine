"""Token-bound serial executor for an inspected signature-only backfill batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cli.signature_backfill_batches import DEFAULT_BATCH_SIZE, build_batch_plan
from cli.signature_backfill_execute import (
    SignatureBackfillError,
    build_plan as build_scene_plan,
    execute_plan as execute_scene_plan,
    plan_digest as scene_plan_digest,
)
from cli.signature_backfill_plan import build_signature_backfill_plan
from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
from steps.common.config_loader import load_configs


class BatchExecutionError(RuntimeError):
    """The serial signature batch cannot safely continue."""


ProofRunner = Callable[[dict[str, Any]], dict[str, Any]]


def _digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchExecutionError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BatchExecutionError(f"expected JSON object: {path}")
    return value


def _scene_id(scene: dict[str, Any]) -> str:
    value = scene.get("scene_id") or scene.get("id")
    return str(value) if value else ""


def _windows_to_wsl_path(path: Path) -> str:
    normalized = str(path.resolve()).replace("\\", "/")
    if len(normalized) >= 3 and normalized[1] == ":" and normalized[2] == "/":
        return f"/mnt/{normalized[0].lower()}/{normalized[3:]}"
    raise BatchExecutionError(f"path is not WSL-mountable: {path}")


def _runtime_contract() -> dict[str, str]:
    host = load_configs().get("host", {})
    host = host if isinstance(host, dict) else {}
    distro = str(host.get("wsl_distro") or "").strip()
    workspace = str(host.get("wsl_workspace") or "").strip()
    if not distro or not workspace:
        raise BatchExecutionError("configured WSL distro and workspace are required")
    return {"wsl_distro": distro, "wsl_workspace": workspace}


def build_execution_plan(processing_root: Path, *, batch_index: int, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    """Build only the immediate next serial batch from the current eligible ledger."""
    if batch_index != 1:
        raise BatchExecutionError(
            "serial executor accepts only batch_index=1; the eligible ledger rebases after every committed batch"
        )
    source = build_signature_backfill_plan(processing_root)
    batches = build_batch_plan(source, batch_size=batch_size)
    selected = next((batch for batch in batches["batches"] if batch["batch_index"] == batch_index), None)
    if not isinstance(selected, dict):
        raise BatchExecutionError(f"batch index is outside inspected plan: {batch_index}")
    by_id = {str(item["scene_id"]): item for item in source["eligible"]}
    selected_records = [by_id[scene_id] for scene_id in selected["scene_ids"]]
    return {
        "status": "ready",
        "kind": "signature_only_serial_batch_execution",
        "processing_root": str(processing_root),
        "batch_index": batch_index,
        "batch_size": batch_size,
        "batch_digest": selected["batch_digest"],
        "source_eligible_scene_ids_sha256": source["eligible_scene_ids_sha256"],
        "scene_count": len(selected_records),
        "scene_ids": selected["scene_ids"],
        "scenes": selected_records,
        "execution_policy": {
            "mode": "serial",
            "requires_cuda_signature_proof": True,
            "per_scene_receipt": True,
            "stop_on_first_error": True,
            "automatic_batch_rollback": False,
            "requires_fresh_batch_confirmation": True,
            "preserves": ["transcript", "diarization", "clap", "temporal", "visual"],
        },
    }


def plan_digest(plan: dict[str, Any]) -> str:
    return _digest({key: value for key, value in plan.items() if key != "status"})


def _scene_request(entry: dict[str, Any], proof_root: Path) -> dict[str, Any]:
    manifest_path = Path(str(entry["manifest_path"])).resolve()
    temporal_path = manifest_path.parent.parent / "temporal_index.json"
    manifest = _read(manifest_path)
    matches = [scene for scene in manifest.get("scenes", []) if isinstance(scene, dict) and _scene_id(scene) == entry["scene_id"]]
    if len(matches) != 1:
        raise BatchExecutionError(f"scene authority is ambiguous: {entry['scene_id']}")
    scene = matches[0]
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    signature = audio.get("speaker_voice_signature_meta")
    signature = signature if isinstance(signature, dict) else {}
    diarization = audio.get("diarization")
    if (
        signature.get("status"),
        signature.get("reason"),
    ) != ("error", "embedding_step_failed"):
        raise BatchExecutionError(f"scene is no longer an eligible signature failure: {entry['scene_id']}")
    if audio.get("diarization_status") != "success" or not isinstance(diarization, list) or not diarization:
        raise BatchExecutionError(f"scene lacks persisted diarization authority: {entry['scene_id']}")
    audio_path = Path(str(audio.get("path") or ""))
    if not audio_path.is_file():
        raise BatchExecutionError(f"scene audio artifact is absent: {entry['scene_id']}")
    proof_root.mkdir(parents=True, exist_ok=True)
    return {
        "scene_id": entry["scene_id"],
        "audio_path": str(audio_path),
        "diarization_segments": diarization,
        "manifest_path": str(manifest_path),
        "temporal_path": str(temporal_path),
        "proof_result_path": str(proof_root / f"{entry['scene_id']}.json"),
    }


def _run_wsl_signature_proof(request: dict[str, Any], runtime: dict[str, str]) -> dict[str, Any]:
    """Run the existing signature-only WSL worker; no full audio path is called."""
    proof_path = Path(str(request["proof_result_path"])).resolve()
    diarization_path = proof_path.with_suffix(".diarization.json")
    atomic_write_json_for_concurrent_readers(diarization_path, request["diarization_segments"])
    command = " && ".join(
        [
            f"cd {shlex.quote(runtime['wsl_workspace'])}",
            "source ./setup_cuda_env.sh >/dev/null",
            "python3 signature_only.py "
            + " ".join(
                shlex.quote(value)
                for value in (
                    _windows_to_wsl_path(Path(str(request["audio_path"]))),
                    _windows_to_wsl_path(diarization_path),
                    _windows_to_wsl_path(proof_path),
                )
            ),
        ]
    )
    completed = subprocess.run(
        ["wsl", "-d", runtime["wsl_distro"], "--", "bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if completed.returncode != 0 or not proof_path.is_file():
        raise BatchExecutionError(f"WSL signature proof failed for {request['scene_id']}")
    proof = _read(proof_path)
    if proof.get("status") != "success" or proof.get("device") != "cuda":
        raise BatchExecutionError(f"WSL signature proof is not a CUDA success: {request['scene_id']}")
    return proof


def _write_receipt(root: Path, payload: dict[str, Any]) -> None:
    atomic_write_json_for_concurrent_readers(root / "receipt.json", payload)


def execute_batch(plan: dict[str, Any], confirmation_token: str, *, proof_runner: ProofRunner | None = None) -> dict[str, Any]:
    """Execute a fresh, token-bound batch and stop after the first failed scene."""
    if plan.get("status") != "ready" or confirmation_token != plan_digest(plan):
        raise BatchExecutionError("confirmation token does not match inspected batch")
    processing_root = Path(str(plan["processing_root"])).resolve()
    fresh = build_execution_plan(processing_root, batch_index=int(plan["batch_index"]), batch_size=int(plan["batch_size"]))
    if plan_digest(fresh) != confirmation_token:
        raise BatchExecutionError("eligible ledger changed after planning")
    epoch_root = processing_root.parent
    operation_id = f"signature_backfill_batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{confirmation_token[:12]}"
    batch_root = epoch_root / "signature_backfill_batches" / operation_id
    proof_root = batch_root / "proofs"
    batch_root.mkdir(parents=True, exist_ok=False)
    atomic_write_json_for_concurrent_readers(batch_root / "plan.json", plan)
    runtime = _runtime_contract() if proof_runner is None else None
    completed: list[str] = []
    scene_receipts: list[dict[str, Any]] = []
    for entry in plan["scenes"]:
        scene_id = str(entry["scene_id"])
        try:
            request = _scene_request(entry, proof_root)
            proof = proof_runner(request) if proof_runner else _run_wsl_signature_proof(request, runtime or {})
            proof_path = Path(str(request["proof_result_path"])).resolve()
            atomic_write_json_for_concurrent_readers(proof_path, proof)
            scene_plan = build_scene_plan(
                Path(str(request["manifest_path"])),
                Path(str(request["temporal_path"])),
                scene_id,
                proof_path,
            )
            scene_receipt = execute_scene_plan(scene_plan, scene_plan_digest(scene_plan))
            completed.append(scene_id)
            scene_receipts.append(scene_receipt)
        except (BatchExecutionError, SignatureBackfillError, OSError, RuntimeError, ValueError) as exc:
            interrupted = {
                "status": "signature_backfill_batch_stopped",
                "operation_id": operation_id,
                "plan_digest": confirmation_token,
                "failed_scene_id": scene_id,
                "completed_scene_ids": completed,
                "scene_receipts": scene_receipts,
                "error": str(exc),
                "batch_root": str(batch_root),
            }
            _write_receipt(batch_root, interrupted)
            raise BatchExecutionError(f"batch stopped after scene failure: {scene_id}") from exc
    receipt = {
        "status": "signature_backfill_batch_committed",
        "operation_id": operation_id,
        "plan_digest": confirmation_token,
        "batch_index": plan["batch_index"],
        "scene_count": plan["scene_count"],
        "completed_scene_ids": completed,
        "scene_receipts": scene_receipts,
        "batch_root": str(batch_root),
        "execution_policy": plan["execution_policy"],
    }
    _write_receipt(batch_root, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation-token")
    args = parser.parse_args()
    cfg = load_configs()
    processing_root = args.processing_root or Path(cfg["paths"]["processing"])
    try:
        plan = build_execution_plan(processing_root, batch_index=args.batch_index, batch_size=args.batch_size)
        token = plan_digest(plan)
        if not args.execute:
            print(json.dumps({"plan": plan, "confirmation_token": token}, indent=2))
            return 0
        if not args.confirmation_token:
            raise BatchExecutionError("--confirmation-token is required with --execute")
        print(json.dumps(execute_batch(plan, args.confirmation_token), indent=2))
        return 0
    except BatchExecutionError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
