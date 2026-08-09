"""Materialize one installer profile's sealed runtime model payload.

This is the only bridge from the immutable asset vault into an installer
staging tree.  It deliberately follows the cache layout consumed by
``model_provisioner`` so an offline install never turns a declared CPU
capability into a first-use network download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.ingestion_capability_contract import resolve_profile_assets
from scripts.assets.personal_asset_vault import evaluate_pack_admission, verify_snapshot


class ProfilePackStageError(RuntimeError):
    """Raised when a profile asset cannot be safely materialized."""


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ProfilePackStageError(f"expected YAML mapping: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_for(vault_root: Path, asset_id: str, revision: str) -> Path:
    candidates = sorted((vault_root / asset_id).glob(f"{revision}-*"))
    if len(candidates) != 1:
        raise ProfilePackStageError(
            f"{asset_id} requires exactly one sealed snapshot for {revision}"
        )
    return candidates[0]


def _registry_records(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for section in ("huggingface_models", "external_models", "lexicons", "system_tools"):
        values = registry.get(section)
        if isinstance(values, dict):
            records.update(
                {str(key): value for key, value in values.items() if isinstance(value, dict)}
            )
    return records


def _copy_source(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ProfilePackStageError(f"refusing to overlay staged payload: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _verify_copied_source(snapshot: Path, destination: Path, asset_id: str) -> None:
    """Prove the staged copy still matches the sealed source-member receipt."""

    manifest_path = snapshot / "source-manifest.json"
    try:
        members = json.loads(manifest_path.read_text(encoding="utf-8"))["members"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ProfilePackStageError(f"{asset_id} has an unreadable source-member receipt") from exc
    for member in members:
        relative = Path(str(member["path"]))
        staged_file = destination / relative
        if not staged_file.is_file():
            raise ProfilePackStageError(f"{asset_id} staged copy is missing {relative}")
        if staged_file.stat().st_size != int(member["size_bytes"]):
            raise ProfilePackStageError(f"{asset_id} staged copy size mismatch for {relative}")
        if _sha256(staged_file).casefold() != str(member["sha256"]).casefold():
            raise ProfilePackStageError(f"{asset_id} staged copy hash mismatch for {relative}")


def _external_source_file(source: Path, record: dict[str, Any], asset_id: str) -> Path:
    expected = str(record.get("sha256") or "").casefold()
    candidates = [path for path in source.rglob("*") if path.is_file()]
    if not expected:
        raise ProfilePackStageError(f"{asset_id} external registry entry lacks sha256")
    matches = [path for path in candidates if _sha256(path).casefold() == expected]
    if len(matches) != 1:
        raise ProfilePackStageError(
            f"{asset_id} sealed source must contain exactly one registry-hash-matching file"
        )
    return matches[0]


def _stage_asset(
    *,
    asset_id: str,
    catalog_record: dict[str, Any],
    registry_record: dict[str, Any] | None,
    snapshot: Path,
    models_root: Path,
) -> dict[str, Any]:
    source = snapshot / "source"
    if not source.is_dir():
        raise ProfilePackStageError(f"{asset_id} sealed snapshot has no source directory")

    if catalog_record.get("kind") == "lexicon":
        destination = models_root / "lexicons" / asset_id
        _copy_source(source, destination)
        _verify_copied_source(snapshot, destination, asset_id)
        return {
            "asset_id": asset_id,
            "delivery": "bundled_reference_lexicon",
            "runtime_path": str(destination.relative_to(models_root)).replace("\\", "/"),
        }

    if not registry_record:
        raise ProfilePackStageError(f"{asset_id} is a selected model without a runtime registry entry")
    if registry_record.get("local_path"):
        destination = models_root / str(registry_record["local_path"])
        source_file = _external_source_file(source, registry_record, asset_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        if _sha256(destination).casefold() != str(registry_record["sha256"]).casefold():
            raise ProfilePackStageError(f"{asset_id} staged external model hash mismatch")
        return {
            "asset_id": asset_id,
            "delivery": "external_model",
            "runtime_path": str(destination.relative_to(models_root)).replace("\\", "/"),
            "sha256": str(registry_record["sha256"]),
        }

    repo_id = str(registry_record.get("repo_id") or "")
    revision = str(registry_record.get("revision") or "")
    if not repo_id or not revision:
        raise ProfilePackStageError(f"{asset_id} registry entry lacks repo_id or revision")
    if repo_id == "snakers4/silero-vad":
        destination = models_root / "hub" / "snakers4_silero-vad_master"
    else:
        cache_name = repo_id.replace("/", "--")
        destination = models_root / "hub" / f"models--{cache_name}" / "snapshots" / revision
    _copy_source(source, destination)
    _verify_copied_source(snapshot, destination, asset_id)
    return {
        "asset_id": asset_id,
        "delivery": "huggingface_cache",
        "repo_id": repo_id,
        "revision": revision,
        "runtime_path": str(destination.relative_to(models_root)).replace("\\", "/"),
    }


def stage_profile(*, vault_root: Path, staging_root: Path, profile: str, check_only: bool = False) -> dict[str, Any]:
    """Verify and stage every profile-selected model/lexicon from sealed source."""

    catalog = _read_yaml(REPO_ROOT / "configs" / "offline_asset_catalog.yaml")
    profiles = _read_yaml(REPO_ROOT / "configs" / "installer_profile_contract.yaml")
    registry = _registry_records(_read_yaml(REPO_ROOT / "configs" / "model_registry.yaml"))
    catalog_assets = dict(catalog.get("assets") or {})
    profile_record = dict((profiles.get("profiles") or {}).get(profile) or {})
    distribution = str(profile_record.get("distribution") or "")
    if distribution not in {"public", "personal"}:
        raise ProfilePackStageError(f"unknown installer profile: {profile}")
    selected = resolve_profile_assets(catalog, profiles, profile)
    payload_ids = [
        asset_id
        for asset_id in selected
        if str((catalog_assets.get(asset_id) or {}).get("kind")) in {"model", "lexicon"}
    ]

    if not check_only:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_root.mkdir(parents=True, exist_ok=True)
    staged: list[dict[str, Any]] = []
    for asset_id in payload_ids:
        print(
            f"[PROFILE-PACK] verifying {asset_id} ({len(staged) + 1}/{len(payload_ids)})",
            flush=True,
        )
        record = dict(catalog_assets[asset_id])
        admission = evaluate_pack_admission(catalog, asset_id=asset_id, distribution=distribution)
        if not admission.allowed:
            raise ProfilePackStageError(f"{asset_id} cannot enter {profile}: {admission.reason}")
        revision = str(record.get("revision") or "")
        snapshot = _snapshot_for(vault_root, asset_id, revision)
        verified = verify_snapshot(snapshot)
        if verified.manifest_sha256 != record.get("sealed_manifest_sha256"):
            raise ProfilePackStageError(f"{asset_id} sealed source manifest does not match catalog")
        if check_only:
            staged.append({"asset_id": asset_id, "status": "sealed"})
            continue
        print(f"[PROFILE-PACK] staging {asset_id}", flush=True)
        staged_entry = _stage_asset(
            asset_id=asset_id,
            catalog_record=record,
            registry_record=registry.get(asset_id),
            snapshot=snapshot,
            models_root=staging_root,
        )
        staged_entry.update(
            {
                "pack_scope": record["pack_scope"],
                "source_revision": revision,
                "source_manifest_sha256": verified.manifest_sha256,
                "license_class": record["license_class"],
            }
        )
        staged.append(staged_entry)

    result = {
        "schema_version": 1,
        "profile": profile,
        "distribution": distribution,
        "selected_asset_ids": selected,
        "payload_asset_ids": payload_ids,
        "payloads": staged,
    }
    if not check_only:
        (staging_root / "selected_capabilities.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--check", action="store_true", help="verify vault admission without copying")
    parser.add_argument("--receipt-path", type=Path, help="write the resolved receipt for this audit or stage")
    args = parser.parse_args(argv)
    try:
        result = stage_profile(
            vault_root=args.vault_root,
            staging_root=args.staging_root,
            profile=args.profile,
            check_only=args.check,
        )
        if args.receipt_path:
            args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
            args.receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, ProfilePackStageError) as exc:
        print(f"profile model pack staging failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
