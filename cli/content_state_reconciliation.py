"""Reconcile stale scene content-state labels from canonical persisted evidence."""
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

from cli.run_ingestion import _classify_scene_content
from steps.common.atomic_io import atomic_write_json_for_concurrent_readers
from steps.common.config_loader import load_configs


class ContentStateReconciliationError(RuntimeError):
    """The requested content-state reconciliation is unsafe to apply."""


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContentStateReconciliationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContentStateReconciliationError(f"expected JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scene_id(value: dict[str, Any]) -> str:
    return str(value.get("scene_id") or value.get("id") or "")


def _recomputed_state(scene: dict[str, Any]) -> str:
    return _classify_scene_content(scene, empty_duration_threshold_sec=1.0)


def _is_target(scene: dict[str, Any]) -> bool:
    return scene.get("content_state") == "processing_error" and _recomputed_state(scene) in {"signal", "empty"}


def build_plan(processing_root: Path, scene_ids: set[str] | None = None) -> dict[str, Any]:
    """Inspect stale labels only; never infer a target from an arbitrary scene."""
    requested, found = set(scene_ids or ()), set()
    files: dict[Path, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for manifest_path in sorted(processing_root.glob("*/video/scene_manifest.json")):
        temporal_path = manifest_path.parent.parent / "temporal_index.json"
        if not temporal_path.is_file():
            continue
        manifest, temporal = _read(manifest_path), _read(temporal_path)
        temporal_by_id = {_scene_id(item): item for item in temporal.get("segments", []) if isinstance(item, dict)}
        for scene in manifest.get("scenes", []):
            if not isinstance(scene, dict) or not _is_target(scene):
                continue
            scene_id = _scene_id(scene)
            if requested and scene_id not in requested:
                continue
            segment = temporal_by_id.get(scene_id)
            if not isinstance(segment, dict) or segment.get("content_state") != "processing_error":
                raise ContentStateReconciliationError(f"temporal state is not stale processing_error: {scene_id}")
            files.setdefault(manifest_path, {"manifest_path": str(manifest_path), "temporal_path": str(temporal_path), "manifest_sha256": _sha(manifest_path), "temporal_sha256": _sha(temporal_path)})
            entries.append({"scene_id": scene_id, "manifest_path": str(manifest_path), "temporal_path": str(temporal_path), "recomputed_content_state": _recomputed_state(scene)})
            found.add(scene_id)
    if requested - found:
        raise ContentStateReconciliationError(f"requested scenes are not eligible: {sorted(requested - found)}")
    if not entries:
        raise ContentStateReconciliationError("no stale content-state targets found")
    return {
        "status": "ready", "kind": "historical_content_state_metadata_reconciliation",
        "processing_root": str(processing_root), "scene_count": len(entries), "file_count": len(files),
        "files": [files[path] for path in sorted(files)], "scenes": sorted(entries, key=lambda item: item["scene_id"]),
        "write_scope": ["scene.content_state", "temporal_index.segments[scene_id].content_state"],
        "non_effects": ["preserve_error_fields", "no_wsl", "no_media_processing", "no_transcription", "no_diarization", "no_embeddings", "no_vectors", "no_sqlite", "no_graph", "no_reingestion"],
    }


def plan_digest(plan: dict[str, Any]) -> str:
    return _digest({key: value for key, value in plan.items() if key != "status"})


def execute_plan(plan: dict[str, Any], confirmation_token: str) -> dict[str, Any]:
    if plan.get("status") != "ready" or confirmation_token != plan_digest(plan):
        raise ContentStateReconciliationError("confirmation token does not match inspected plan")
    files, entries = plan.get("files"), plan.get("scenes")
    if not isinstance(files, list) or not isinstance(entries, list) or not entries:
        raise ContentStateReconciliationError("plan is structurally incomplete")
    root = Path(str(plan["processing_root"])).resolve().parent
    op = f"content_state_reconciliation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{confirmation_token[:12]}"
    receipt_root, backup_root = root / "content_state_reconciliations" / op, root / "content_state_reconciliations" / op / "backup"
    backup_root.mkdir(parents=True, exist_ok=False)
    originals: dict[Path, bytes] = {}
    payloads: dict[Path, dict[str, Any]] = {}
    try:
        for index, detail in enumerate(files):
            for label in ("manifest", "temporal"):
                path = Path(str(detail[f"{label}_path"])).resolve()
                if _sha(path) != detail[f"{label}_sha256"]:
                    raise ContentStateReconciliationError("authority changed after planning")
                originals[path] = path.read_bytes(); (backup_root / f"{index:02d}_{label}.json").write_bytes(originals[path]); payloads[path] = _read(path)
        for entry in entries:
            manifest = payloads[Path(str(entry["manifest_path"])).resolve()]
            temporal = payloads[Path(str(entry["temporal_path"])).resolve()]
            scenes = [item for item in manifest.get("scenes", []) if isinstance(item, dict) and _scene_id(item) == entry["scene_id"]]
            segments = [item for item in temporal.get("segments", []) if isinstance(item, dict) and _scene_id(item) == entry["scene_id"]]
            if len(scenes) != 1 or len(segments) != 1 or not _is_target(scenes[0]) or segments[0].get("content_state") != "processing_error":
                raise ContentStateReconciliationError(f"scene authority changed: {entry['scene_id']}")
            state = _recomputed_state(scenes[0])
            if state != entry["recomputed_content_state"]:
                raise ContentStateReconciliationError(f"canonical state changed: {entry['scene_id']}")
            scenes[0]["content_state"] = state; segments[0]["content_state"] = state
        for path, payload in payloads.items():
            atomic_write_json_for_concurrent_readers(path, payload)
    except Exception as exc:
        for path, raw in originals.items(): path.write_bytes(raw)
        raise ContentStateReconciliationError(f"reconciliation rolled back: {exc}") from exc
    receipt = {"status": "content_state_reconciliation_committed", "operation_id": op, "plan_digest": confirmation_token, "scene_count": len(entries), "file_count": len(files), "backup_root": str(backup_root), "changed_scene_ids": [item["scene_id"] for item in entries], "write_scope": plan["write_scope"], "non_effects": plan["non_effects"]}
    atomic_write_json_for_concurrent_readers(receipt_root / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path); parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true"); parser.add_argument("--confirmation-token")
    args = parser.parse_args(); root = args.processing_root or Path(load_configs()["paths"]["processing"])
    try:
        plan = build_plan(root, set(args.scene_id) if args.scene_id else None); token = plan_digest(plan)
        print(json.dumps(execute_plan(plan, args.confirmation_token) if args.execute else {"plan": plan, "confirmation_token": token}, indent=2)); return 0
    except ContentStateReconciliationError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)})); return 3


if __name__ == "__main__":
    raise SystemExit(main())
