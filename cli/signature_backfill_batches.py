"""Create deterministic, inspect-only batches from the signature backfill ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from cli.signature_backfill_plan import build_signature_backfill_plan
from steps.common.config_loader import load_configs


DEFAULT_BATCH_SIZE = 10


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_batch_plan(backfill_plan: dict[str, Any], *, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    if backfill_plan.get("status") != "inspect_only":
        raise ValueError("backfill plan is not inspect-only")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    eligible = backfill_plan.get("eligible")
    if not isinstance(eligible, list):
        raise ValueError("backfill plan has no eligible ledger")
    batches = []
    for offset in range(0, len(eligible), batch_size):
        scenes = eligible[offset : offset + batch_size]
        scene_ids = [str(item["scene_id"]) for item in scenes]
        batches.append({
            "batch_index": len(batches) + 1,
            "scene_count": len(scenes),
            "scene_ids": scene_ids,
            "batch_digest": _digest(scenes),
            "execution": "not_started",
        })
    return {
        "status": "inspect_only",
        "kind": "signature_only_serial_batch_plan",
        "source_eligible_scene_ids_sha256": backfill_plan["eligible_scene_ids_sha256"],
        "eligible_count": len(eligible),
        "blocked_count": backfill_plan["blocked_count"],
        "batch_size": batch_size,
        "batch_count": len(batches),
        "batches": batches,
        "execution_policy": {
            "mode": "serial",
            "per_scene_receipt": True,
            "stop_on_first_error": True,
            "requires_fresh_batch_confirmation": True,
            "writes": "none_in_this_planner",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-root", type=Path)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cfg = load_configs()
    source = build_signature_backfill_plan(args.processing_root or Path(cfg["paths"]["processing"]))
    plan = build_batch_plan(source, batch_size=args.batch_size)
    rendered = json.dumps(plan, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
