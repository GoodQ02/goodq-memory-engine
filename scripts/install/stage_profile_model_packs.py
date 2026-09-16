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
import time
from pathlib import Path
from typing import Any, Callable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.ingestion_capability_contract import (
    build_profile_asset_closure,
    resolve_capability_profile,
    resolve_profile_assets,
)
from scripts.assets.personal_asset_vault import evaluate_pack_admission, verify_snapshot
from scripts.install.installer_contract import (
    MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
    MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
    MODEL_MEMBER_REQUIRED_FIELDS,
    SELECTED_CAPABILITIES_REQUIRED_FIELDS,
    SELECTED_CAPABILITIES_SCHEMA_VERSION,
)


class ProfilePackStageError(RuntimeError):
    """Raised when a profile asset cannot be safely materialized."""


def _require_fields(
    value: dict[str, Any], required_fields: frozenset[str], label: str
) -> None:
    missing = sorted(required_fields - set(value))
    if missing:
        raise ProfilePackStageError(f"{label} is missing required field: {missing[0]}")


COPY_CHUNK_BYTES = 16 * 1024 * 1024
COPY_HEARTBEAT_SECONDS = 30.0
MODEL_MEMBER_MANIFEST_NAME = "model_member_manifest.json"
SELECTED_CAPABILITIES_NAME = "selected_capabilities.json"
REQUIRED_SAFETENSORS_TRANSFORMS = {
    "blip_caption": ("pytorch_model.bin", "model.safetensors"),
    "clap_audio": ("pytorch_model.bin", "model.safetensors"),
    "clip_vit": ("pytorch_model.bin", "model.safetensors"),
    "hubert_emotion": ("pytorch_model.bin", "model.safetensors"),
    "vit_gpt2_caption": ("pytorch_model.bin", "model.safetensors"),
}


def _format_bytes(value: int) -> str:
    return f"{value / 1024**3:.2f} GiB"


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


def _copy_source(
    source: Path,
    destination: Path,
    *,
    asset_id: str,
    progress: Callable[[str], None],
    chunk_bytes: int = COPY_CHUNK_BYTES,
    heartbeat_seconds: float = COPY_HEARTBEAT_SECONDS,
) -> None:
    """Copy a sealed source tree with bounded, operator-visible progress."""

    if destination.exists():
        raise ProfilePackStageError(f"refusing to overlay staged payload: {destination}")
    if chunk_bytes <= 0:
        raise ValueError("copy chunk size must be positive")
    if heartbeat_seconds < 0:
        raise ValueError("copy heartbeat interval must not be negative")
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in sorted(source.rglob("*")) if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    copied_bytes = 0
    last_heartbeat = time.monotonic()
    progress(
        f"[PROFILE-PACK] copy plan: {asset_id}: "
        f"{len(files)} file(s), {_format_bytes(total_bytes)}"
    )
    for source_file in files:
        relative = source_file.relative_to(source)
        destination_file = destination / relative
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        file_size = source_file.stat().st_size
        progress(
            f"[PROFILE-PACK] copying {asset_id}: {relative.as_posix()} "
            f"({_format_bytes(file_size)})"
        )
        with source_file.open("rb") as source_handle, destination_file.open("wb") as destination_handle:
            for chunk in iter(lambda: source_handle.read(chunk_bytes), b""):
                destination_handle.write(chunk)
                copied_bytes += len(chunk)
                if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                    progress(
                        f"[PROFILE-PACK] copy heartbeat: {asset_id}: "
                        f"{_format_bytes(copied_bytes)} / {_format_bytes(total_bytes)}"
                    )
                    last_heartbeat = time.monotonic()
        shutil.copystat(source_file, destination_file)
    progress(
        f"[PROFILE-PACK] copy complete: {asset_id}: "
        f"{_format_bytes(copied_bytes)}"
    )


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


def _source_member_receipts(snapshot: Path, asset_id: str) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(
            (snapshot / "source-manifest.json").read_text(encoding="utf-8")
        )
        members = payload["members"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ProfilePackStageError(
            f"{asset_id} has an unreadable source-member receipt"
        ) from exc
    if not isinstance(members, list):
        raise ProfilePackStageError(
            f"{asset_id} source-member receipt must contain a member list"
        )
    receipts: dict[str, dict[str, Any]] = {}
    for member in members:
        if not isinstance(member, dict):
            raise ProfilePackStageError(
                f"{asset_id} source-member receipt contains an invalid row"
            )
        path = Path(str(member.get("path") or ""))
        normalized = path.as_posix()
        if path.is_absolute() or ".." in path.parts or not normalized:
            raise ProfilePackStageError(
                f"{asset_id} source-member receipt contains an unsafe path"
            )
        if normalized in receipts:
            raise ProfilePackStageError(
                f"{asset_id} source-member receipt contains a duplicate path"
            )
        receipts[normalized] = dict(member)
    return receipts


def _load_safetensors_tools():
    import torch
    from safetensors.torch import load_file, save_file

    return torch, save_file, load_file


def _transform_required_safetensors(
    asset_id: str,
    runtime_root: Path,
    *,
    tool_loader: Callable[[], tuple[Any, Callable[..., Any], Callable[..., Any]]]
    | None = None,
) -> list[dict[str, Any]]:
    """Apply one declared, safe, fatal state-dict transformation."""

    plan = REQUIRED_SAFETENSORS_TRANSFORMS.get(asset_id)
    if plan is None:
        return []
    source_name, target_name = plan
    source = runtime_root / source_name
    target = runtime_root / target_name
    temporary = runtime_root / f".{target_name}.tmp"
    if not source.is_file():
        raise ProfilePackStageError(
            f"{asset_id} required transformation source is missing: {source_name}"
        )
    if target.exists() or temporary.exists():
        raise ProfilePackStageError(
            f"{asset_id} required transformation target is not fresh: {target_name}"
        )
    try:
        torch, save_file, load_file = (tool_loader or _load_safetensors_tools)()
    except ImportError as exc:
        raise ProfilePackStageError(
            f"{asset_id} required safetensors tooling is unavailable"
        ) from exc

    source_sha256 = _sha256(source)
    try:
        state_dict = torch.load(source, map_location="cpu", weights_only=True)
        if not isinstance(state_dict, dict) or not state_dict:
            raise TypeError("safe weight payload is not a non-empty state dictionary")
        normalized: dict[str, Any] = {}
        for key, tensor in state_dict.items():
            if not isinstance(key, str) or not all(
                hasattr(tensor, method)
                for method in ("detach", "cpu", "contiguous", "clone")
            ):
                raise TypeError("safe weight payload contains a non-tensor member")
            normalized[key] = tensor.detach().cpu().contiguous().clone()
        save_file(normalized, temporary)
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise OSError("safetensors writer did not produce a non-empty file")
        verified = load_file(temporary, device="cpu")
        if set(verified) != set(normalized):
            raise ValueError("safetensors round-trip key mismatch")
        for key, tensor in normalized.items():
            restored = verified[key]
            if tuple(getattr(restored, "shape", ())) != tuple(
                getattr(tensor, "shape", ())
            ) or str(getattr(restored, "dtype", "")) != str(
                getattr(tensor, "dtype", "")
            ):
                raise ValueError(
                    f"safetensors round-trip tensor metadata mismatch: {key}"
                )
        temporary.replace(target)
    except Exception as exc:
        if temporary.exists():
            temporary.unlink()
        if target.exists():
            target.unlink()
        raise ProfilePackStageError(
            f"{asset_id} required safetensors transformation failed: {exc}"
        ) from exc
    return [
        {
            "type": "pytorch_state_dict_to_safetensors",
            "source_path": source_name,
            "source_sha256": source_sha256,
            "target_path": target_name,
            "target_sha256": _sha256(target),
            "torch_version": str(getattr(torch, "__version__", "unknown")),
            "safe_load": "weights_only_true",
        }
    ]


def _build_model_member_manifest(
    *,
    staging_root: Path,
    profile: str,
    payloads: list[dict[str, Any]],
    source_members_by_asset: dict[str, dict[str, dict[str, Any]]],
    transformations_by_asset: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Bind every staged model member to source or transform provenance."""

    members: list[dict[str, Any]] = []
    declared_paths: set[str] = set()
    for payload in sorted(payloads, key=lambda item: str(item.get("asset_id"))):
        asset_id = str(payload.get("asset_id") or "")
        runtime_relative = Path(str(payload.get("runtime_path") or ""))
        if runtime_relative.is_absolute() or ".." in runtime_relative.parts:
            raise ProfilePackStageError(f"{asset_id} declares an unsafe runtime path")
        runtime_root = staging_root / runtime_relative
        files = [runtime_root] if runtime_root.is_file() else [
            path for path in sorted(runtime_root.rglob("*")) if path.is_file()
        ]
        if not files:
            raise ProfilePackStageError(f"{asset_id} staged runtime has no members")
        source_receipts = source_members_by_asset.get(asset_id) or {}
        transform_records = {
            str(record.get("target_path")): dict(record)
            for record in transformations_by_asset.get(asset_id) or []
        }
        for path in files:
            local_path = (
                path.name if runtime_root.is_file() else path.relative_to(runtime_root).as_posix()
            )
            member_path = path.relative_to(staging_root).as_posix()
            if member_path in declared_paths:
                raise ProfilePackStageError(f"duplicate staged member: {member_path}")
            declared_paths.add(member_path)
            if local_path in transform_records:
                provenance = transform_records[local_path]
                if _sha256(path).casefold() != str(
                    provenance.get("target_sha256") or ""
                ).casefold():
                    raise ProfilePackStageError(
                        f"{asset_id} post-transform hash drift: {local_path}"
                    )
            else:
                source_receipt = source_receipts.get(local_path)
                if not isinstance(source_receipt, dict):
                    raise ProfilePackStageError(
                        f"{asset_id} orphan staged member: {local_path}"
                    )
                if path.stat().st_size != int(source_receipt.get("size_bytes") or -1):
                    raise ProfilePackStageError(
                        f"{asset_id} source member size drift: {local_path}"
                    )
                if _sha256(path).casefold() != str(
                    source_receipt.get("sha256") or ""
                ).casefold():
                    raise ProfilePackStageError(
                        f"{asset_id} source member hash drift: {local_path}"
                    )
                provenance = {
                    "type": "sealed_source_copy",
                    "source_path": local_path,
                    "source_sha256": str(source_receipt["sha256"]),
                }
            members.append(
                {
                    "path": member_path,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                    "asset_id": asset_id,
                    "source_manifest_sha256": str(
                        payload.get("source_manifest_sha256") or ""
                    ),
                    "provenance": provenance,
                }
            )
    members.sort(key=lambda item: str(item["path"]))
    actual_paths = {
        path.relative_to(staging_root).as_posix()
        for path in staging_root.rglob("*")
        if path.is_file()
        and path.name not in {MODEL_MEMBER_MANIFEST_NAME, SELECTED_CAPABILITIES_NAME}
    }
    orphans = sorted(actual_paths - declared_paths)
    if orphans:
        raise ProfilePackStageError(f"orphan staged member: {orphans[0]}")
    missing = sorted(declared_paths - actual_paths)
    if missing:
        raise ProfilePackStageError(f"missing staged member: {missing[0]}")
    inventory_bytes = json.dumps(
        members, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        "profile": profile,
        "member_count": len(members),
        "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "members": members,
    }


def _verify_model_member_manifest(
    staging_root: Path, manifest: dict[str, Any]
) -> None:
    _require_fields(
        manifest,
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        "model member manifest",
    )
    if manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION:
        raise ProfilePackStageError("model member manifest schema is unsupported")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise ProfilePackStageError("model member manifest has no members")
    if any(not isinstance(member, dict) for member in members):
        raise ProfilePackStageError("model member manifest contains an invalid member")
    for member in members:
        _require_fields(member, MODEL_MEMBER_REQUIRED_FIELDS, "model member")
    paths = [str(member.get("path") or "") for member in members]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ProfilePackStageError("model member manifest paths are not unique and sorted")
    actual_paths = {
        path.relative_to(staging_root).as_posix()
        for path in staging_root.rglob("*")
        if path.is_file()
        and path.name not in {MODEL_MEMBER_MANIFEST_NAME, SELECTED_CAPABILITIES_NAME}
    }
    if actual_paths != set(paths):
        raise ProfilePackStageError("model member manifest membership mismatch")
    for member in members:
        path = staging_root / Path(str(member["path"]))
        if path.stat().st_size != int(member.get("size_bytes") or -1):
            raise ProfilePackStageError(f"member size mismatch: {member['path']}")
        if _sha256(path).casefold() != str(member.get("sha256") or "").casefold():
            raise ProfilePackStageError(f"member hash mismatch: {member['path']}")
    inventory_bytes = json.dumps(
        members, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(inventory_bytes).hexdigest() != manifest.get("inventory_sha256"):
        raise ProfilePackStageError("model member manifest inventory digest mismatch")


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
        _copy_source(source, destination, asset_id=asset_id, progress=print)
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
    _copy_source(source, destination, asset_id=asset_id, progress=print)
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
    capability_profiles = _read_yaml(
        REPO_ROOT / "configs" / "ingestion_capability_profiles.yaml"
    )
    registry = _registry_records(_read_yaml(REPO_ROOT / "configs" / "model_registry.yaml"))
    catalog_assets = dict(catalog.get("assets") or {})
    profile_record = dict((profiles.get("profiles") or {}).get(profile) or {})
    distribution = str(profile_record.get("distribution") or "")
    if distribution not in {"public", "personal"}:
        raise ProfilePackStageError(f"unknown installer profile: {profile}")
    selected = resolve_profile_assets(catalog, profiles, profile)
    asset_closure = build_profile_asset_closure(
        catalog=catalog,
        profile_contract=profiles,
        registry=registry,
        capability_profile=resolve_capability_profile(capability_profiles, profile),
        profile=profile,
    )
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
    source_members_by_asset: dict[str, dict[str, dict[str, Any]]] = {}
    transformations_by_asset: dict[str, list[dict[str, Any]]] = {}
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
        source_members = _source_member_receipts(snapshot, asset_id)
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
        runtime_root = staging_root / Path(str(staged_entry["runtime_path"]))
        transformations = _transform_required_safetensors(asset_id, runtime_root)
        staged_entry["transformations"] = transformations
        source_members_by_asset[asset_id] = source_members
        transformations_by_asset[asset_id] = transformations
        staged.append(staged_entry)

    member_manifest: dict[str, Any] | None = None
    member_manifest_sha256: str | None = None
    if not check_only:
        member_manifest = _build_model_member_manifest(
            staging_root=staging_root,
            profile=profile,
            payloads=staged,
            source_members_by_asset=source_members_by_asset,
            transformations_by_asset=transformations_by_asset,
        )
        _verify_model_member_manifest(staging_root, member_manifest)
        member_manifest_path = staging_root / MODEL_MEMBER_MANIFEST_NAME
        member_manifest_path.write_text(
            json.dumps(member_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        member_manifest_sha256 = _sha256(member_manifest_path)

    result = {
        "schema_version": SELECTED_CAPABILITIES_SCHEMA_VERSION,
        "profile": profile,
        "distribution": distribution,
        "selected_asset_ids": selected,
        "selector_sha256": asset_closure["selector_sha256"],
        "asset_inventory_sha256": asset_closure["asset_inventory_sha256"],
        "asset_closure": asset_closure,
        "payload_asset_ids": payload_ids,
        "payloads": staged,
        "model_member_manifest": (
            {
                "path": MODEL_MEMBER_MANIFEST_NAME,
                "sha256": member_manifest_sha256,
                "inventory_sha256": member_manifest["inventory_sha256"],
                "member_count": member_manifest["member_count"],
            }
            if member_manifest is not None
            else None
        ),
    }
    _require_fields(
        result,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        "selected capability receipt",
    )
    if not check_only:
        (staging_root / SELECTED_CAPABILITIES_NAME).write_text(
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
