"""Audit every non-code dependency needed by a fresh offline Windows install.

This is an inventory and verification surface, not an installer builder.  It
reconciles the declarative installer manifest, model/asset catalog, staged
payload, and immutable asset vault into one JSON receipt.  A record is never
silently treated as complete merely because a similarly named cache exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from packaging.utils import canonicalize_name, parse_wheel_filename

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _sealed_snapshot(vault_root: Path, asset_id: str, revision: str) -> tuple[Path | None, str | None]:
    asset_root = vault_root / asset_id
    if not asset_root.is_dir():
        return None, None
    candidates = sorted(asset_root.glob(f"{revision}-*"), key=lambda item: item.name)
    if len(candidates) != 1:
        return None, None
    try:
        seal = _read_json(candidates[0] / "seal.json")
        manifest = _read_json(candidates[0] / "source-manifest.json")
    except (OSError, json.JSONDecodeError):
        return candidates[0], None
    digest = hashlib.sha256(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    if (
        seal.get("asset_id") != asset_id
        or str(seal.get("revision")) != revision
        or seal.get("source_manifest_sha256") != digest
    ):
        return candidates[0], None
    return candidates[0], digest


def _model_records(catalog: dict[str, Any], vault_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    assets = dict(catalog.get("assets", {}))
    for asset_id, item in sorted(assets.items()):
        if not isinstance(item, dict) or item.get("kind") not in {"model", "lexicon", "source_collection"}:
            continue
        status = str(item.get("status", ""))
        record: dict[str, Any] = {
            "asset_id": asset_id,
            "kind": item.get("kind"),
            "source": item.get("source"),
            "revision": str(item.get("revision")),
            "catalog_status": status,
            "vault_scope": item.get("vault_scope"),
            "pack_scope": item.get("pack_scope"),
        }
        if status == "eligible":
            seal_path, digest = _sealed_snapshot(vault_root, asset_id, str(item.get("revision")))
            expected = item.get("sealed_manifest_sha256")
            if digest and expected == digest and item.get("expected_terms"):
                state = "sealed_manifest_confirmed"
            elif seal_path and digest:
                state = "sealed_unrecorded"
            else:
                state = "missing_or_unverified"
            record.update(
                state=state,
                seal_path=str(seal_path) if seal_path else None,
                sealed_manifest_sha256=digest,
                expected_manifest_sha256=expected,
            )
        elif status == "agreement_gated":
            record["state"] = "held_by_acceptance"
        elif status == "personal_only":
            parent_id = item.get("source_snapshot_parent")
            parent = assets.get(str(parent_id)) if parent_id else None
            if isinstance(parent, dict):
                parent_revision = str(parent.get("revision"))
                seal_path, digest = _sealed_snapshot(vault_root, str(parent_id), parent_revision)
                expected = parent.get("sealed_manifest_sha256")
                if digest and expected == digest and parent.get("expected_terms"):
                    state = "personal_snapshot_via_parent"
                elif seal_path and digest:
                    state = "personal_parent_snapshot_unrecorded"
                else:
                    state = "personal_parent_snapshot_missing"
                record["source_snapshot_parent"] = str(parent_id)
            else:
                seal_path, digest = _sealed_snapshot(vault_root, asset_id, str(item.get("revision")))
                expected = item.get("sealed_manifest_sha256")
                if digest and expected == digest and item.get("expected_terms"):
                    state = "personal_snapshot_confirmed"
                elif seal_path and digest:
                    state = "personal_snapshot_unrecorded"
                else:
                    state = "personal_snapshot_missing"
            record.update(
                state=state,
                seal_path=str(seal_path) if seal_path else None,
                sealed_manifest_sha256=digest,
                expected_manifest_sha256=expected,
            )
        else:
            record["state"] = "excluded"
        records.append(record)
    return records


def _wheel_names(wheelhouse: Path) -> set[str]:
    if not wheelhouse.is_dir():
        return set()
    names: set[str] = set()
    for wheel in wheelhouse.glob("*.whl"):
        try:
            name, _, _, _ = parse_wheel_filename(wheel.name)
        except Exception:
            continue
        names.add(canonicalize_name(str(name)))
    return names


def _manifest_records(manifest: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for section in ("toolchains", "dependencies"):
        for asset_id, item in sorted(dict(manifest.get(section, {})).items()):
            if not isinstance(item, dict):
                continue
            target = repo_root / str(item.get("target_path", ""))
            cache = repo_root / "scripts" / "install" / str(item.get("cache_path", ""))
            state = (
                "staged_target_present"
                if target.exists()
                else "cached_source_present"
                if cache.exists()
                else "missing_from_stage_and_cache"
            )
            records.append(
                {
                    "asset_id": asset_id,
                    "class": section,
                    "required": bool(item.get("required")),
                    "source_url": item.get("source_url"),
                    "source_version": item.get("source_version"),
                    "sha256": item.get("sha256"),
                    "target_path": str(target),
                    "cache_path": str(cache),
                    "state": state,
                }
            )
    wheels = list(dict(manifest.get("wheels", {})).get("wheelhouse", []))
    wheel_names = _wheel_names(repo_root / "scripts" / "install" / "staged_cache" / "wheels")
    for item in wheels:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        present = canonicalize_name(name) in wheel_names
        required = bool(item.get("required"))
        records.append(
            {
                "asset_id": str(item.get("artifact_id", name)),
                "class": "wheelhouse",
                "required": required,
                "source_url": item.get("source_url"),
                "sha256": item.get("sha256"),
                "state": (
                    "cached_wheel_present"
                    if present
                    else "missing_cached_wheel"
                    if required
                    else "optional_wheel_not_cached"
                ),
            }
        )
    return records


def _wheelhouse_closure(repo_root: Path) -> dict[str, Any]:
    """Report the complete lock-resolved closure carried by the build cache."""

    cache = repo_root / "scripts" / "install" / "staged_cache" / "wheels"
    sbom_path = repo_root / "scripts" / "install" / "staged_cache" / "wheelhouse-sbom.json"
    if not sbom_path.is_file():
        return {"state": "missing_sbom", "package_count": 0, "missing_files": []}
    sbom = _read_json(sbom_path)
    packages = list(sbom.get("packages", []))
    missing = sorted(
        str(item.get("filename"))
        for item in packages
        if not (cache / str(item.get("filename", ""))).is_file()
    )
    return {
        "state": "closure_present" if not missing else "closure_files_missing",
        "package_count": len(packages),
        "wheelhouse_sha256": sbom.get("wheelhouse_sha256"),
        "missing_files": missing,
    }


def build_report(*, catalog_path: Path, manifest_path: Path, vault_root: Path, repo_root: Path) -> dict[str, Any]:
    """Build a deterministic closure receipt from the four authoritative inputs."""

    models = _model_records(_read_yaml(catalog_path), vault_root)
    installer = _manifest_records(_read_json(manifest_path), repo_root)
    model_counts: dict[str, int] = {}
    installer_counts: dict[str, int] = {}
    for item in models:
        model_counts[item["state"]] = model_counts.get(item["state"], 0) + 1
    for item in installer:
        installer_counts[item["state"]] = installer_counts.get(item["state"], 0) + 1
    return {
        "schema_version": 1,
        "purpose": "fresh_windows_offline_dependency_closure",
        "models_and_data": models,
        "installer_artifacts": installer,
        "wheelhouse_closure": _wheelhouse_closure(repo_root),
        "summary": {"models_and_data": model_counts, "installer_artifacts": installer_counts},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the GoodQ offline reproducibility closure")
    parser.add_argument("--catalog", type=Path, default=REPO_ROOT / "configs" / "offline_asset_catalog.yaml")
    parser.add_argument("--manifest", type=Path, default=REPO_ROOT / "configs" / "offline_dependencies_manifest.json")
    parser.add_argument("--vault-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(
        catalog_path=args.catalog,
        manifest_path=args.manifest,
        vault_root=args.vault_root,
        repo_root=REPO_ROOT,
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
