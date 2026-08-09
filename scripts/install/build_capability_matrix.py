"""Validate runtime capability declarations against the asset authorities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.ingestion_capability_contract import (
    RUNTIME_CAPABILITY_POLICIES,
    build_capability_matrix,
    resolve_profile_assets,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return payload


def _flatten_registry(payload: dict[str, Any]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for section in ("huggingface_models", "external_models", "lexicons", "system_tools"):
        values = payload.get(section)
        if isinstance(values, dict):
            records.update({str(key): value for key, value in values.items() if isinstance(value, dict)})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only; do not write an artifact")
    parser.add_argument(
        "--profile",
        help="validate this exact installer profile in addition to the complete contract",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "reports" / "capability_matrix.json",
        help="matrix path when not using --check",
    )
    args = parser.parse_args()

    registry = _flatten_registry(_load_yaml(REPO_ROOT / "configs" / "model_registry.yaml"))
    catalog = _load_yaml(REPO_ROOT / "configs" / "offline_asset_catalog.yaml")
    profile_contract = _load_yaml(REPO_ROOT / "configs" / "installer_profile_contract.yaml")
    matrix = build_capability_matrix(
        registry=registry,
        catalog=catalog,
        runtime_policies=RUNTIME_CAPABILITY_POLICIES,
    )
    profile_selections = {
        profile: resolve_profile_assets(catalog, profile_contract, profile)
        for profile in sorted(dict(profile_contract.get("profiles") or {}))
    }
    if args.profile and args.profile not in profile_selections:
        raise ValueError(f"unknown installer profile: {args.profile}")
    matrix["profile_selections"] = profile_selections
    if args.check:
        print(
            "capability matrix check passed: "
            f"runtime_steps={len(matrix['runtime_steps'])} profiles={len(profile_selections)}"
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote capability matrix: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
