"""Issue and revalidate the terminal v3.0.1 offline prebuild readiness receipt.

This command is deliberately preflight-only.  It may read and hash source,
vault, fixture, database, WSL, and disk evidence and may write one external
JSON receipt.  It never invokes NSIS, creates payload ZIPs, stages models,
changes the asset vault, installs software, or contacts the network.
"""

from __future__ import annotations

import argparse
import ast
import copy
import gc
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.ingestion_capability_contract import (
    build_profile_asset_closure,
    resolve_capability_profile,
    resolve_profile_assets,
)
from scripts.assets.personal_asset_vault import sha256_file, verify_snapshot
from scripts.install.generate_release_fixture_pack import verify_fixture_pack
from scripts.install.installer_contract import RELEASE_BUILD_PROFILES
from scripts.install.stage_profile_model_packs import REQUIRED_SAFETENSORS_TRANSFORMS
from scripts.install.verify_profile_model_payload import DEFAULT_PROBE_LOADERS
from scripts.wsl_audio_preflight import probe_wsl_audio_runtime


SCHEMA = "goodq.prebuild-readiness.v1"
PUBLIC_PROFILE, PERSONAL_PROFILE = RELEASE_BUILD_PROFILES
PUBLIC_ASSET_COUNT = 33
PERSONAL_ASSET_COUNT = 36
PERSONAL_ONLY_DELTA = (
    "pyannote_diarization",
    "pyannote_segmentation",
    "pyannote_wespeaker",
)
LARGE_MODEL_ASSET_IDS = (
    "deepseek_r1_distill_qwen_14b",
    "deepseek_r1_distill_qwen_7b",
    "gemma_4_12b_unified",
    "qwen2_5_vl_3b",
    "qwen2_5_vl_7b",
)
REQUIRED_TRANSFORM_ASSET_IDS = tuple(sorted(REQUIRED_SAFETENSORS_TRANSFORMS))
SIDECAR_COLUMNS = ("tq_indices", "tq_norm", "tq_qjl_sign", "tq_norm_residual")
WSL_CHECK_KEYS = (
    "workspace",
    "transcription",
    "process_import",
    "abi",
    "diarization",
    "wav2vec_enrichment",
    "clap_handoff",
    "gpu",
)
ALLOWED_WSL_WARNINGS = ("torchcodec_unavailable",)
WSL_PINNED_VERSION_KEYS = (
    "torch",
    "torchvision",
    "torchaudio",
    "pyannote.audio",
    "faster-whisper",
    "transformers",
    "tokenizers",
    "safetensors",
)
CONFIG_BINDING_PATHS = (
    "goodq_version.py",
    "configs/offline_asset_catalog.yaml",
    "configs/installer_profile_contract.yaml",
    "configs/ingestion_capability_profiles.yaml",
    "configs/model_registry.yaml",
    "scripts/config_schema.py",
    "steps/common/memory_stores.py",
    "cli/golden_witness.py",
    "scripts/wsl_audio_preflight.py",
    "scripts/install/generate_release_fixture_pack.py",
    "scripts/install/prebuild_readiness.py",
    "scripts/install/stage_profile_model_packs.py",
    "scripts/install/verify_profile_model_payload.py",
)


class PrebuildReadinessError(RuntimeError):
    """Raised when any prebuild release invariant is unproven or drifted."""


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _expect_sha256(value: object, label: str) -> str:
    digest = str(value or "").casefold()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise PrebuildReadinessError(f"{label} is not a SHA256 digest")
    return digest


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PrebuildReadinessError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PrebuildReadinessError(f"{label} must be a list")
    return value


def _path_fingerprint(path: Path) -> str:
    normalized = os.path.normcase(str(path.resolve())).replace("\\", "/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _text_fingerprint(namespace: str, value: str) -> str:
    normalized = f"{namespace}:{value.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise PrebuildReadinessError(f"YAML release input is unreadable: {path.name}") from exc
    if not isinstance(payload, dict):
        raise PrebuildReadinessError(f"YAML release input must be a mapping: {path.name}")
    return payload


def _run_git(repo_root: Path, *arguments: str, allow_failure: bool = False) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 and not allow_failure:
        detail = (completed.stderr or completed.stdout or "unknown Git error").strip()
        raise PrebuildReadinessError(f"Git identity check failed: {detail}")
    return (completed.stdout or "").strip()


def _canonical_version(repo_root: Path) -> str:
    source = (repo_root / "goodq_version.py").read_text(encoding="utf-8")
    match = re.search(r'GOODQ_VERSION\s*=\s*"([^"]+)"', source)
    if match is None:
        raise PrebuildReadinessError("canonical release version is unreadable")
    return match.group(1)


def _config_inventory(repo_root: Path) -> tuple[list[dict[str, object]], str]:
    records: list[dict[str, object]] = []
    for relative in CONFIG_BINDING_PATHS:
        path = repo_root / relative
        if not path.is_file():
            raise PrebuildReadinessError(f"release input is missing: {relative}")
        records.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records, _canonical_sha256(records)


def _dedicated_worktree(repo_root: Path) -> bool:
    git_dir_text = _run_git(repo_root, "rev-parse", "--git-dir")
    common_dir_text = _run_git(repo_root, "rev-parse", "--git-common-dir")
    git_dir = Path(git_dir_text)
    common_dir = Path(common_dir_text)
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    if not common_dir.is_absolute():
        common_dir = repo_root / common_dir
    return git_dir.resolve() != common_dir.resolve()


def _remote_alignment(repo_root: Path) -> dict[str, object]:
    value = _run_git(
        repo_root,
        "rev-list",
        "--left-right",
        "--count",
        "origin/dev...HEAD",
        allow_failure=True,
    )
    try:
        behind_text, ahead_text = value.split()
        behind = int(behind_text)
        ahead = int(ahead_text)
    except (ValueError, TypeError):
        behind = -1
        ahead = -1
    return {
        "behind_origin_dev": behind,
        "ahead_of_origin_dev": ahead,
        "policy": "push_deferred_by_checkpoint",
    }


def _capture_source_identity(repo_root: Path) -> dict[str, Any]:
    config_records, config_digest = _config_inventory(repo_root)
    branch = _run_git(repo_root, "symbolic-ref", "--short", "-q", "HEAD", allow_failure=True)
    return {
        "commit": _run_git(repo_root, "rev-parse", "HEAD"),
        "tree": _run_git(repo_root, "rev-parse", "HEAD^{tree}"),
        "clean": not bool(_run_git(repo_root, "status", "--porcelain", "--untracked-files=all")),
        "branch": branch or "HEAD",
        "dedicated_worktree": _dedicated_worktree(repo_root),
        "root_fingerprint": _path_fingerprint(repo_root),
        "config_inventory": config_records,
        "config_inventory_sha256": config_digest,
        "remote_alignment": _remote_alignment(repo_root),
    }


def _registry_records(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for section in ("huggingface_models", "external_models", "lexicons", "system_tools"):
        values = registry.get(section)
        if isinstance(values, dict):
            records.update(
                {str(key): dict(value) for key, value in values.items() if isinstance(value, dict)}
            )
    return records


def _runtime_symbol_paths(repo_root: Path, symbol: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    matches: list[str] = []
    for relative_root in ("cli", "steps", "pipelines", "api", "agents"):
        root = repo_root / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            try:
                source = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise PrebuildReadinessError(
                    f"runtime dispatch source is unreadable: {path.relative_to(repo_root).as_posix()}"
                ) from exc
            if pattern.search(source):
                matches.append(path.relative_to(repo_root).as_posix())
    return sorted(matches)


def _collect_profiles(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = _read_yaml(repo_root / "configs" / "offline_asset_catalog.yaml")
    contract = _read_yaml(repo_root / "configs" / "installer_profile_contract.yaml")
    capability_contract = _read_yaml(
        repo_root / "configs" / "ingestion_capability_profiles.yaml"
    )
    registry = _registry_records(_read_yaml(repo_root / "configs" / "model_registry.yaml"))
    selections = {
        profile: resolve_profile_assets(catalog, contract, profile)
        for profile in (PUBLIC_PROFILE, PERSONAL_PROFILE)
    }
    closures = {
        profile: build_profile_asset_closure(
            catalog=catalog,
            profile_contract=contract,
            registry=registry,
            capability_profile=resolve_capability_profile(capability_contract, profile),
            profile=profile,
        )
        for profile in (PUBLIC_PROFILE, PERSONAL_PROFILE)
    }
    profiles: dict[str, Any] = {}
    for profile in (PUBLIC_PROFILE, PERSONAL_PROFILE):
        closure = closures[profile]
        profiles[profile] = {
            "asset_count": len(selections[profile]),
            "asset_ids": selections[profile],
            "selector_sha256": closure["selector_sha256"],
            "asset_inventory_sha256": closure["asset_inventory_sha256"],
        }
    profiles["personal_only_delta"] = sorted(
        set(selections[PERSONAL_PROFILE]) - set(selections[PUBLIC_PROFILE])
    )
    profiles["forbidden_asset_ids"] = list(LARGE_MODEL_ASSET_IDS)
    local_vlm_dispatch_paths = _runtime_symbol_paths(repo_root, "local_vlm")
    local_vlm_status_writer_paths = _runtime_symbol_paths(repo_root, "local_vlm_meta")
    profiles["local_vlm_dispatch_paths"] = local_vlm_dispatch_paths
    profiles["local_vlm_status_writer_paths"] = local_vlm_status_writer_paths
    profiles["local_vlm_dispatch_present"] = bool(
        local_vlm_dispatch_paths or local_vlm_status_writer_paths
    )
    asset_contracts = _mapping(contract.get("asset_contracts"), "installer asset contracts")
    profiles["local_llm_serving_owner_present"] = any(
        asset_id in asset_contracts for asset_id in LARGE_MODEL_ASSET_IDS
    )
    context = {
        "catalog": catalog,
        "contract": contract,
        "registry": registry,
        "selections": selections,
        "closures": closures,
    }
    return profiles, context


def _snapshot_for(vault_root: Path, asset_id: str, revision: str) -> Path:
    candidates = sorted((vault_root / asset_id).glob(f"{revision}-*"))
    if len(candidates) != 1:
        raise PrebuildReadinessError(
            f"{asset_id} requires exactly one sealed vault snapshot for {revision}"
        )
    return candidates[0]


def _source_manifest(snapshot: Path) -> dict[str, Any]:
    try:
        payload = json.loads((snapshot / "source-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrebuildReadinessError(f"sealed source manifest is unreadable: {snapshot.name}") from exc
    if not isinstance(payload, dict):
        raise PrebuildReadinessError(f"sealed source manifest is malformed: {snapshot.name}")
    return payload


def _collect_vault(
    *,
    vault_root: Path,
    profile_context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    catalog_assets = _mapping(
        profile_context["catalog"].get("assets"), "offline asset catalog"
    )
    selected = sorted(
        set(profile_context["selections"][PUBLIC_PROFILE])
        | set(profile_context["selections"][PERSONAL_PROFILE])
    )
    payload_ids = [
        asset_id
        for asset_id in selected
        if str(_mapping(catalog_assets.get(asset_id), f"catalog asset {asset_id}").get("kind"))
        in {"model", "lexicon"}
    ]
    verification_ids = sorted(set(payload_ids) | set(LARGE_MODEL_ASSET_IDS))
    seals: list[dict[str, Any]] = []
    evidence_by_asset: dict[str, dict[str, Any]] = {}
    for asset_id in verification_ids:
        record = _mapping(catalog_assets.get(asset_id), f"catalog asset {asset_id}")
        revision = str(record.get("revision") or "")
        snapshot = _snapshot_for(vault_root, asset_id, revision)
        verified = verify_snapshot(snapshot)
        if verified.manifest_sha256 != record.get("sealed_manifest_sha256"):
            raise PrebuildReadinessError(f"vault seal drift: {asset_id}")
        manifest = _source_manifest(snapshot)
        members = _list(manifest.get("members"), f"{asset_id} source members")
        source_bytes = sum(int(_mapping(member, "source member").get("size_bytes") or 0) for member in members)
        seal = {
            "asset_id": asset_id,
            "revision": revision,
            "snapshot_id": snapshot.name,
            "manifest_sha256": verified.manifest_sha256,
            "source_bytes": source_bytes,
            "status": "verified",
            "disposition": (
                "preserved_excluded_candidate"
                if asset_id in LARGE_MODEL_ASSET_IDS
                else "selected_payload"
            ),
        }
        seals.append(seal)
        evidence_by_asset[asset_id] = {
            "snapshot": snapshot,
            "manifest": manifest,
            "seal": seal,
        }
    seals.sort(key=lambda item: str(item["asset_id"]))
    vault = {
        "explicit": True,
        "status": "verified",
        "root_fingerprint": _path_fingerprint(vault_root),
        "inventory_sha256": _canonical_sha256(seals),
        "verified_asset_ids": [str(item["asset_id"]) for item in seals],
        "selected_payload_asset_ids": payload_ids,
        "preserved_large_model_asset_ids": list(LARGE_MODEL_ASSET_IDS),
        "seals": seals,
    }
    return vault, evidence_by_asset


def _collect_transformations(
    evidence_by_asset: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    try:
        import importlib.metadata as metadata
        import torch
        import safetensors  # noqa: F401
    except ImportError as exc:
        raise PrebuildReadinessError("required safetensors transformation tooling is unavailable") from exc
    records: list[dict[str, Any]] = []
    for asset_id in REQUIRED_TRANSFORM_ASSET_IDS:
        evidence = _mapping(evidence_by_asset.get(asset_id), f"vault evidence {asset_id}")
        snapshot = Path(evidence["snapshot"])
        source_name, target_name = REQUIRED_SAFETENSORS_TRANSFORMS[asset_id]
        source = snapshot / "source" / source_name
        target = snapshot / "source" / target_name
        if not source.is_file() or target.exists():
            raise PrebuildReadinessError(
                f"required safetensors transformation input is not fresh: {asset_id}"
            )
        try:
            state_dict = torch.load(source, map_location="meta", weights_only=True)
            if not isinstance(state_dict, dict) or not state_dict:
                raise TypeError("safe weight payload is not a non-empty state dictionary")
            if any(
                not isinstance(key, str)
                or not all(hasattr(tensor, method) for method in ("detach", "cpu", "contiguous", "clone"))
                for key, tensor in state_dict.items()
            ):
                raise TypeError("safe weight payload contains a non-tensor member")
            tensor_count = len(state_dict)
        except Exception as exc:
            raise PrebuildReadinessError(
                f"safetensors transformation feasibility failed: {asset_id}: {exc}"
            ) from exc
        del state_dict
        gc.collect()
        manifest_members = _list(evidence["manifest"].get("members"), "source members")
        source_member = next(
            (
                member
                for member in manifest_members
                if isinstance(member, dict) and member.get("path") == source_name
            ),
            None,
        )
        if not isinstance(source_member, dict):
            raise PrebuildReadinessError(f"transformation source is absent from seal: {asset_id}")
        records.append(
            {
                "asset_id": asset_id,
                "status": "safe_load_feasible",
                "source_path": source_name,
                "source_size_bytes": source.stat().st_size,
                "source_sha256": source_member["sha256"],
                "target_path": target_name,
                "tensor_count": tensor_count,
                "safe_load": "weights_only_true_map_location_meta",
                "torch_version": str(getattr(torch, "__version__", "unknown")),
                "safetensors_version": metadata.version("safetensors"),
            }
        )
    return {
        "status": "feasible",
        "asset_ids": list(REQUIRED_TRANSFORM_ASSET_IDS),
        "inventory_sha256": _canonical_sha256(records),
        "records": records,
    }


def _collect_model_probe_coverage(
    *,
    profile_context: dict[str, Any],
    vault: dict[str, Any],
) -> dict[str, Any]:
    catalog_assets = _mapping(profile_context["catalog"].get("assets"), "asset catalog")
    assets_by_id = _mapping(
        profile_context["closures"][PERSONAL_PROFILE].get("assets_by_id"),
        "Personal asset closure",
    )
    payload_ids = list(vault["selected_payload_asset_ids"])
    records: list[dict[str, Any]] = []
    for asset_id in sorted(payload_ids):
        closure = _mapping(assets_by_id.get(asset_id), f"asset closure {asset_id}")
        catalog_record = _mapping(catalog_assets.get(asset_id), f"catalog asset {asset_id}")
        probe = str(closure.get("probe") or "")
        if probe not in DEFAULT_PROBE_LOADERS:
            raise PrebuildReadinessError(f"missing model-load probe: {asset_id}:{probe or 'unset'}")
        if not str(closure.get("runtime_owner") or ""):
            raise PrebuildReadinessError(f"missing model runtime owner: {asset_id}")
        records.append(
            {
                "asset_id": asset_id,
                "kind": catalog_record.get("kind"),
                "probe": probe,
                "runtime_owner": closure["runtime_owner"],
                "status": (
                    "safe_transform_and_loader_ready"
                    if asset_id in REQUIRED_TRANSFORM_ASSET_IDS
                    else "sealed_source_and_loader_ready"
                ),
                "installed_inference_gate": "required_after_build",
            }
        )
    return {
        "status": "prebuild_feasibility_passed",
        "installed_inference_status": "required_after_build",
        "expected_asset_ids": sorted(payload_ids),
        "inventory_sha256": _canonical_sha256(records),
        "records": records,
    }


def _wsl_version(distro: str) -> int:
    completed = subprocess.run(
        ["wsl", "--list", "--verbose"],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return 0
    output = completed.stdout
    text = output.decode("utf-16le", errors="replace") if b"\x00" in output else output.decode(errors="replace")
    for line in text.splitlines():
        normalized = line.replace("*", " ").strip()
        if normalized.casefold().startswith(distro.casefold()):
            parts = normalized.split()
            try:
                return int(parts[-1])
            except (IndexError, ValueError):
                return 0
    return 0


def _wsl_expected_versions(repo_root: Path) -> tuple[dict[str, str], str]:
    constraints_path = repo_root / "wsl2_audio" / "requirements-bootstrap-constraints.txt"
    try:
        constraints = constraints_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PrebuildReadinessError("WSL bootstrap constraints are unavailable") from exc
    versions: dict[str, str] = {}
    for line in constraints:
        candidate = line.strip()
        if not candidate or candidate.startswith("#") or "==" not in candidate:
            continue
        package, version = candidate.split("==", 1)
        if package in WSL_PINNED_VERSION_KEYS:
            versions[package] = version
    if set(versions) != set(WSL_PINNED_VERSION_KEYS):
        raise PrebuildReadinessError("WSL bootstrap constraints omit a required runtime pin")
    return versions, sha256_file(constraints_path)


def _collect_wsl(*, repo_root: Path, distro: str, workspace: str) -> dict[str, Any]:
    observed = probe_wsl_audio_runtime(distro, workspace)
    expected_versions, constraints_sha256 = _wsl_expected_versions(repo_root)
    checks = {
        "workspace": bool(observed.get("workspace_ready")),
        "transcription": bool(observed.get("transcription_ready")),
        "process_import": bool(observed.get("process_import_ready")),
        "abi": bool(observed.get("abi_ready")),
        "diarization": bool(observed.get("diarization_ready")),
        "wav2vec_enrichment": bool(observed.get("wav2vec_enrichment_ready")),
        "clap_handoff": bool(observed.get("clap_handoff_ready")),
        "gpu": bool(observed.get("gpu_ready")),
    }
    raw_warnings = set(str(item) for item in observed.get("runtime_warnings") or [])
    normalized_warnings: list[str] = []
    torchcodec_warnings = {
        "torchcodec_decoder_unavailable",
        "pyannote_warned_torchcodec_decoder_unavailable",
    }
    if raw_warnings & torchcodec_warnings:
        normalized_warnings.append("torchcodec_unavailable")
        raw_warnings -= torchcodec_warnings
    normalized_warnings.extend(sorted(raw_warnings))
    wsl_version = _wsl_version(distro)
    detected_versions = observed.get("detected_versions") or {}
    versions_match = all(
        str(detected_versions.get(package) or "") == version
        for package, version in expected_versions.items()
    )
    evidence = {
        "status": (
            "passed"
            if bool(observed.get("ready"))
            and all(checks.values())
            and wsl_version == 2
            and versions_match
            else "failed"
        ),
        "distro": distro,
        "wsl_version": wsl_version,
        "workspace_fingerprint": _text_fingerprint("wsl-workspace", workspace),
        "required_checks": checks,
        "allowed_warnings": list(ALLOWED_WSL_WARNINGS),
        "warnings": normalized_warnings,
        "torchcodec_status": (
            "allowed_unavailable" if observed.get("torchcodec_ready") is False else "ready"
        ),
        "torch_lane_status": observed.get("torch_lane_status"),
        "constraints_sha256": constraints_sha256,
        "expected_versions": expected_versions,
        "detected_versions": detected_versions,
        "versions_match_constraints": versions_match,
        "clap_handoff": observed.get("clap_handoff") or {},
    }
    evidence["evidence_sha256"] = _canonical_sha256(evidence)
    return evidence


def _collect_fixture(*, repo_root: Path, fixture_root: Path) -> dict[str, Any]:
    verified = verify_fixture_pack(fixture_root)
    manifest_path = fixture_root / "fixture-pack-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for source in _list(manifest.get("sources"), "fixture sources"):
        source_record = _mapping(source, "fixture source")
        path = repo_root / str(source_record.get("path") or "")
        if not path.is_file() or sha256_file(path) != source_record.get("sha256"):
            raise PrebuildReadinessError(
                f"fixture source drift: {source_record.get('id') or 'unknown'}"
            )
    return {
        "status": "verified",
        "root_fingerprint": _path_fingerprint(fixture_root),
        "manifest_sha256": verified["manifest_sha256"],
        "fixture_pack_sha256": verified["fixture_pack_sha256"],
        "members_sha256": verified["members_sha256"],
        "member_count": verified["member_count"],
    }


def _bool_from_environment(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _load_runtime_config(runtime_config_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    from steps.common.config_loader import (
        _deep_merge,
        _ensure_runtime_path_defaults,
        _normalize_paths,
        validate_config_mapping,
    )

    config_root = runtime_config_root / "configs"
    base_path = config_root / "config.yaml"
    local_path = config_root / "config.local.yaml"
    if not base_path.is_file():
        raise PrebuildReadinessError("active runtime config root has no canonical config")
    raw_config = _normalize_paths(_read_yaml(base_path))
    inventory = [
        {
            "path": "configs/config.yaml",
            "size_bytes": base_path.stat().st_size,
            "sha256": sha256_file(base_path),
        }
    ]
    if local_path.is_file():
        local_config = _normalize_paths(_read_yaml(local_path))
        _deep_merge(raw_config, local_config)
        inventory.append(
            {
                "path": "configs/config.local.yaml",
                "size_bytes": local_path.stat().st_size,
                "sha256": sha256_file(local_path),
            }
        )
    try:
        resolved = validate_config_mapping(_ensure_runtime_path_defaults(raw_config))
    except Exception as exc:
        raise PrebuildReadinessError("active runtime configuration is invalid") from exc
    return resolved, {
        "root_fingerprint": _path_fingerprint(runtime_config_root),
        "local_config_present": local_path.is_file(),
        "inventory": inventory,
        "inventory_sha256": _canonical_sha256(inventory),
    }


def _collect_turboquant(
    repo_root: Path,
    *,
    runtime_config_root: Path,
) -> dict[str, Any]:
    from scripts.config_schema import MemoryRoutingConfig
    from steps.common.sqlite_read_authority import open_sqlite_read_connection

    defaults = MemoryRoutingConfig()
    memory_source = (repo_root / "steps" / "common" / "memory_stores.py").read_text(
        encoding="utf-8"
    )
    witness_source = (repo_root / "cli" / "golden_witness.py").read_text(encoding="utf-8")
    release_active = bool(defaults.quantization_enabled) or _bool_from_environment(
        "GOODQ_QUANTIZATION_ENABLED"
    )
    release_shadow = bool(defaults.quantization_shadow_mode)
    if 'get("quantization_shadow_mode", False)' not in memory_source:
        release_shadow = True
    witness_active = '"quantization_enabled": False' not in witness_source
    witness_shadow = '"quantization_shadow_mode": False' not in witness_source
    cfg, runtime_config_evidence = _load_runtime_config(runtime_config_root)
    host_routing = ((cfg.get("memory") or {}).get("routing") or {}) if isinstance(cfg, dict) else {}
    host_active = bool(host_routing.get("quantization_enabled", False))
    host_shadow = bool(host_routing.get("quantization_shadow_mode", False))
    db_path = Path(str((cfg.get("paths") or {}).get("db_path") or ""))
    if not db_path.is_file():
        raise PrebuildReadinessError("active memory database is unavailable for sidecar census")
    try:
        connection = open_sqlite_read_connection(
            db_path,
            unavailable_message="active memory database is unavailable for sidecar census",
        )
    except (FileNotFoundError, OSError, sqlite3.Error) as exc:
        raise PrebuildReadinessError(
            f"TurboQuant sidecar database could not be opened read-only: {exc}"
        ) from exc
    try:
        row = connection.execute(
            "SELECT "
            + ", ".join(
                f"SUM(CASE WHEN {column} IS NOT NULL THEN 1 ELSE 0 END)"
                for column in SIDECAR_COLUMNS
            )
            + " FROM embeddings"
        ).fetchone()
    except sqlite3.Error as exc:
        raise PrebuildReadinessError(f"TurboQuant sidecar census failed: {exc}") from exc
    finally:
        connection.close()
    counts = {
        column: int((row or (0,) * len(SIDECAR_COLUMNS))[index] or 0)
        for index, column in enumerate(SIDECAR_COLUMNS)
    }
    evidence = {
        "release_configuration": {"active": release_active, "shadow": release_shadow},
        "witness_configuration": {"active": witness_active, "shadow": witness_shadow},
        "host_observation": {
            "active": host_active,
            "shadow": host_shadow,
            "policy": "superseded_existing_host_not_a_build_input",
            "runtime_config_root_fingerprint": runtime_config_evidence[
                "root_fingerprint"
            ],
            "runtime_config_inventory_sha256": runtime_config_evidence[
                "inventory_sha256"
            ],
            "local_config_present": runtime_config_evidence["local_config_present"],
        },
        "runtime_config": runtime_config_evidence,
        "database_fingerprint": _path_fingerprint(db_path),
        "database_sidecar_counts": counts,
    }
    evidence["evidence_sha256"] = _canonical_sha256(evidence)
    return evidence


def _tree_size(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _run_dependency_gate(
    *,
    repo_root: Path,
    cache_root: Path,
    profile: str,
    mode: str,
) -> None:
    powershell = (
        shutil.which("pwsh.exe")
        or shutil.which("pwsh")
        or shutil.which("powershell.exe")
        or shutil.which("powershell")
    )
    if powershell is None:
        raise PrebuildReadinessError("PowerShell is unavailable for private cache verification")
    environment = os.environ.copy()
    environment.update(
        {
            "PIP_NO_INDEX": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "GOODQ_OFFLINE_BUILD": "1",
            "NETWORK_POLICY": "blocked",
        }
    )
    if Path(powershell).name.casefold() == "powershell.exe":
        environment.pop("PSModulePath", None)
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "install" / "stage_dependencies.ps1"),
            "-Mode",
            mode,
            "-CacheDir",
            str(cache_root),
            "-ManifestPath",
            str(repo_root / "configs" / "offline_dependencies_manifest.json"),
            "-Profile",
            profile,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        output = "\n".join(
            line.strip()
            for line in (completed.stderr or completed.stdout or "").splitlines()
            if line.strip()
        )
        detail = output.splitlines()[-1] if output else "no diagnostic"
        raise PrebuildReadinessError(
            f"private cache {mode.casefold()} failed for {profile}: {detail}"
        )


def _collect_private_build_inputs(
    *,
    repo_root: Path,
    private_build_root: Path,
) -> dict[str, Any]:
    if not private_build_root.is_dir():
        raise PrebuildReadinessError("explicit private build root is unavailable")
    if private_build_root == repo_root or repo_root in private_build_root.parents:
        raise PrebuildReadinessError("private build inputs must remain outside source control")

    cache_root = private_build_root / "staged_cache"
    tool_paths = {
        "go": private_build_root / "go_compiler" / "go" / "bin" / "go.exe",
        "nsis": private_build_root / "nsis_compiler" / "nsis-3.09" / "makensis.exe",
    }
    signing_key = private_build_root / "dev_private_key.hex"
    if not cache_root.is_dir():
        raise PrebuildReadinessError("private staged dependency cache is unavailable")
    if any(not path.is_file() for path in tool_paths.values()):
        raise PrebuildReadinessError("private compiler input is unavailable")
    if not signing_key.is_file():
        raise PrebuildReadinessError("private signing key input is unavailable")

    try:
        private_key = bytes.fromhex(signing_key.read_text(encoding="ascii").strip())
    except (OSError, ValueError) as exc:
        raise PrebuildReadinessError("private signing key input is malformed") from exc
    if len(private_key) != 64:
        raise PrebuildReadinessError("private signing key input is malformed")
    launcher_source = (repo_root / "scripts" / "install" / "LAUNCH_GOODQ.go").read_text(
        encoding="utf-8"
    )
    embedded_match = re.search(r'EmbeddedPublicKeyHex\s*=\s*"([0-9a-fA-F]{64})"', launcher_source)
    if embedded_match is None or private_key[-32:].hex() != embedded_match.group(1).casefold():
        raise PrebuildReadinessError("private signing key does not match the bound launcher")
    embedded_public_key_sha256 = hashlib.sha256(private_key[-32:]).hexdigest()
    del private_key

    tool_records = [
        {
            "id": tool_id,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for tool_id, path in sorted(tool_paths.items())
    ]
    contract_paths = (
        "configs/offline_dependencies_manifest.json",
        "requirements-gpu-enhanced-lock.txt",
        "scripts/install/stage_dependencies.ps1",
    )
    contract_records = [
        {
            "path": relative,
            "sha256": sha256_file(repo_root / relative),
            "size_bytes": (repo_root / relative).stat().st_size,
        }
        for relative in contract_paths
    ]
    dependency_gates: list[dict[str, str]] = []
    for profile in (PUBLIC_PROFILE, PERSONAL_PROFILE):
        for mode in ("Verify", "Audit"):
            _run_dependency_gate(
                repo_root=repo_root,
                cache_root=cache_root,
                profile=profile,
                mode=mode,
            )
            dependency_gates.append(
                {"profile": profile, "mode": mode.casefold(), "status": "passed"}
            )
    inventory_binding = {
        "tools": tool_records,
        "contracts": contract_records,
        "dependency_gates": dependency_gates,
        "signing_public_key_sha256": embedded_public_key_sha256,
    }
    return {
        "status": "verified",
        "root_fingerprint": _path_fingerprint(private_build_root),
        "cache_root_fingerprint": _path_fingerprint(cache_root),
        "cache_size_bytes": _tree_size(cache_root),
        "tools": tool_records,
        "contracts": contract_records,
        "dependency_gates": dependency_gates,
        "signing_key_present": True,
        "signing_key_matches_launcher": True,
        "signing_public_key_sha256": embedded_public_key_sha256,
        "inventory_sha256": _canonical_sha256(inventory_binding),
    }


def _existing_ancestor(path: Path) -> Path:
    candidate = path.resolve()
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _collect_disk(
    *,
    private_build_inputs: Mapping[str, Any],
    future_output_root: Path,
    profile_context: dict[str, Any],
    evidence_by_asset: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    exists = future_output_root.exists()
    empty = not exists or not any(future_output_root.iterdir())
    cache_bytes = int(private_build_inputs.get("cache_size_bytes") or 0)
    catalog_assets = _mapping(profile_context["catalog"].get("assets"), "asset catalog")
    estimates: dict[str, dict[str, int]] = {}
    for profile in (PUBLIC_PROFILE, PERSONAL_PROFILE):
        payload_ids = [
            asset_id
            for asset_id in profile_context["selections"][profile]
            if str(_mapping(catalog_assets.get(asset_id), "catalog asset").get("kind"))
            in {"model", "lexicon"}
        ]
        model_bytes = sum(
            int(_mapping(evidence_by_asset[asset_id], "vault evidence")["seal"]["source_bytes"])
            for asset_id in payload_ids
        )
        transform_bytes = sum(
            int(_mapping(evidence_by_asset[asset_id], "vault evidence")["seal"]["source_bytes"])
            for asset_id in REQUIRED_TRANSFORM_ASSET_IDS
        )
        required = (model_bytes + cache_bytes) * 2 + transform_bytes + 10 * 1024**3
        estimates[profile] = {
            "selected_model_bytes": model_bytes,
            "private_cache_bytes": cache_bytes,
            "transformation_headroom_bytes": transform_bytes,
            "required_bytes": required,
        }
    required_bytes = max(item["required_bytes"] for item in estimates.values())
    free_bytes = shutil.disk_usage(_existing_ancestor(future_output_root)).free
    estimate_binding = {
        "profiles": estimates,
        "required_bytes": required_bytes,
    }
    return (
        {
            "required_bytes": required_bytes,
            "free_bytes": free_bytes,
            "profiles": estimates,
            "estimate_sha256": _canonical_sha256(estimate_binding),
        },
        {
            "root_fingerprint": _path_fingerprint(future_output_root),
            "exists": exists,
            "empty": empty,
        },
    )


def validate_readiness(
    candidate: Mapping[str, Any], *, expected_version: str
) -> None:
    if candidate.get("schema") != SCHEMA:
        raise PrebuildReadinessError("prebuild readiness schema is unsupported")
    if candidate.get("version") != expected_version:
        raise PrebuildReadinessError(f"release version must be {expected_version}")
    source = _mapping(candidate.get("source"), "source evidence")
    if source.get("clean") is not True:
        raise PrebuildReadinessError("source tree is dirty")
    if source.get("initial_commit") != source.get("observed_commit") or source.get(
        "initial_tree"
    ) != source.get("observed_tree"):
        raise PrebuildReadinessError("source identity drift occurred during preflight")
    if source.get("dedicated_worktree") is not True:
        raise PrebuildReadinessError("release requires a dedicated source worktree")
    _expect_sha256(source.get("root_fingerprint"), "source root fingerprint")
    _expect_sha256(source.get("config_inventory_sha256"), "source config inventory")
    remote = _mapping(source.get("remote_alignment"), "remote alignment")
    if int(remote.get("behind_origin_dev", -1)) != 0:
        raise PrebuildReadinessError("release source is behind origin/dev")
    if remote.get("policy") != "push_deferred_by_checkpoint":
        raise PrebuildReadinessError("remote alignment has no approved no-push policy")

    profiles = _mapping(candidate.get("profiles"), "profile evidence")
    public = _mapping(profiles.get(PUBLIC_PROFILE), "Public GPU profile")
    personal = _mapping(profiles.get(PERSONAL_PROFILE), "Personal profile")
    public_ids = _list(public.get("asset_ids"), "Public GPU assets")
    personal_ids = _list(personal.get("asset_ids"), "Personal assets")
    if int(public.get("asset_count", -1)) != PUBLIC_ASSET_COUNT or len(public_ids) != PUBLIC_ASSET_COUNT:
        raise PrebuildReadinessError("Public GPU profile must contain exactly 33 assets")
    if int(personal.get("asset_count", -1)) != PERSONAL_ASSET_COUNT or len(personal_ids) != PERSONAL_ASSET_COUNT:
        raise PrebuildReadinessError("Personal profile must contain exactly 36 assets")
    if public_ids != sorted(set(public_ids)) or personal_ids != sorted(set(personal_ids)):
        raise PrebuildReadinessError("profile asset lists must be unique and sorted")
    if set(public_ids) & set(LARGE_MODEL_ASSET_IDS) or set(personal_ids) & set(LARGE_MODEL_ASSET_IDS):
        raise PrebuildReadinessError("profile selected a forbidden large-model asset")
    if sorted(set(personal_ids) - set(public_ids)) != list(PERSONAL_ONLY_DELTA):
        raise PrebuildReadinessError("Personal profile delta is not the exact three Pyannote assets")
    if sorted(profiles.get("personal_only_delta") or []) != list(PERSONAL_ONLY_DELTA):
        raise PrebuildReadinessError("declared Personal profile delta is incorrect")
    if sorted(profiles.get("forbidden_asset_ids") or []) != list(LARGE_MODEL_ASSET_IDS):
        raise PrebuildReadinessError("declared forbidden large-model set is incomplete")
    for profile in (public, personal):
        _expect_sha256(profile.get("selector_sha256"), "profile selector")
        _expect_sha256(profile.get("asset_inventory_sha256"), "profile asset inventory")
    if profiles.get("local_vlm_dispatch_present") is not False:
        raise PrebuildReadinessError("local VLM must remain policy-excluded")
    if profiles.get("local_vlm_dispatch_paths") != [] or profiles.get(
        "local_vlm_status_writer_paths"
    ) != []:
        raise PrebuildReadinessError("local VLM runner or status writer is present")
    if profiles.get("local_llm_serving_owner_present") is not False:
        raise PrebuildReadinessError("local LLM serving must remain policy-excluded")

    vault = _mapping(candidate.get("vault"), "vault evidence")
    if vault.get("explicit") is not True:
        raise PrebuildReadinessError("an explicit asset vault root is required")
    if vault.get("status") != "verified":
        raise PrebuildReadinessError("vault seal verification did not pass")
    _expect_sha256(vault.get("root_fingerprint"), "vault root fingerprint")
    _expect_sha256(vault.get("inventory_sha256"), "vault inventory")
    if sorted(vault.get("preserved_large_model_asset_ids") or []) != list(LARGE_MODEL_ASSET_IDS):
        raise PrebuildReadinessError("preserved large-model seal set is incomplete")
    seals = _list(vault.get("seals"), "vault seals")
    if not seals or any(
        not isinstance(seal, dict) or seal.get("status") != "verified" for seal in seals
    ):
        raise PrebuildReadinessError("vault seal verification did not pass")
    seal_ids = {
        str(seal.get("asset_id")) for seal in seals if isinstance(seal, dict)
    }
    if not set(LARGE_MODEL_ASSET_IDS).issubset(seal_ids):
        raise PrebuildReadinessError("preserved large-model seal rows are incomplete")

    transformations = _mapping(candidate.get("transformations"), "transformation evidence")
    if transformations.get("status") != "feasible" or sorted(
        transformations.get("asset_ids") or []
    ) != list(REQUIRED_TRANSFORM_ASSET_IDS):
        raise PrebuildReadinessError("required safetensors transformation set is incomplete")
    transformation_records = _list(transformations.get("records"), "transformation records")
    if len(transformation_records) != len(REQUIRED_TRANSFORM_ASSET_IDS) or any(
        not isinstance(record, dict) or record.get("status") != "safe_load_feasible"
        for record in transformation_records
    ):
        raise PrebuildReadinessError("safetensors transformation feasibility did not pass")
    if sorted(
        str(record.get("asset_id"))
        for record in transformation_records
        if isinstance(record, dict)
    ) != list(REQUIRED_TRANSFORM_ASSET_IDS):
        raise PrebuildReadinessError("safetensors transformation evidence rows are incomplete")

    probes = _mapping(candidate.get("model_load_probes"), "model-load probes")
    if probes.get("status") != "prebuild_feasibility_passed" or probes.get(
        "installed_inference_status"
    ) != "required_after_build":
        raise PrebuildReadinessError("model-load probe feasibility did not pass")
    expected_probe_ids = sorted(probes.get("expected_asset_ids") or [])
    probe_records = _list(probes.get("records"), "model-load probe records")
    observed_probe_ids = sorted(
        str(record.get("asset_id") or "") for record in probe_records if isinstance(record, dict)
    )
    if observed_probe_ids != expected_probe_ids or len(probe_records) != len(expected_probe_ids):
        raise PrebuildReadinessError("model-load probe coverage is incomplete")
    allowed_probe_statuses = {
        "loader_contract_ready",
        "safe_transform_and_loader_ready",
        "sealed_source_and_loader_ready",
    }
    if any(
        not isinstance(record, dict) or record.get("status") not in allowed_probe_statuses
        for record in probe_records
    ):
        raise PrebuildReadinessError("model-load probe feasibility did not pass")

    wsl = _mapping(candidate.get("wsl"), "WSL prerequisite")
    if wsl.get("status") != "passed" or wsl.get("distro") != "Ubuntu-22.04" or int(
        wsl.get("wsl_version") or 0
    ) != 2:
        raise PrebuildReadinessError("WSL prerequisite did not pass")
    checks = _mapping(wsl.get("required_checks"), "WSL required checks")
    if any(checks.get(key) is not True for key in WSL_CHECK_KEYS):
        raise PrebuildReadinessError("WSL prerequisite check failed")
    warnings = set(wsl.get("warnings") or [])
    allowed_warnings = set(wsl.get("allowed_warnings") or [])
    if warnings - allowed_warnings or allowed_warnings != set(ALLOWED_WSL_WARNINGS):
        raise PrebuildReadinessError("unapproved WSL warning is present")
    for field in ("workspace_fingerprint", "constraints_sha256", "evidence_sha256"):
        _expect_sha256(wsl.get(field), f"WSL {field}")
    expected_versions = _mapping(wsl.get("expected_versions"), "WSL expected versions")
    detected_versions = _mapping(wsl.get("detected_versions"), "WSL detected versions")
    if set(expected_versions) != set(WSL_PINNED_VERSION_KEYS) or any(
        str(detected_versions.get(package) or "") != str(expected_versions.get(package) or "")
        for package in WSL_PINNED_VERSION_KEYS
    ) or wsl.get("versions_match_constraints") is not True:
        raise PrebuildReadinessError("WSL package versions do not match bootstrap constraints")

    fixture = _mapping(candidate.get("fixture_pack"), "fixture pack")
    if fixture.get("status") != "verified" or int(fixture.get("member_count") or 0) != 6:
        raise PrebuildReadinessError("fixture pack verification did not pass")
    for field in ("root_fingerprint", "manifest_sha256", "fixture_pack_sha256", "members_sha256"):
        _expect_sha256(fixture.get(field), f"fixture {field}")

    turboquant = _mapping(candidate.get("turboquant"), "TurboQuant evidence")
    _expect_sha256(turboquant.get("evidence_sha256"), "TurboQuant evidence")
    for name in ("release_configuration", "witness_configuration"):
        configuration = _mapping(turboquant.get(name), f"TurboQuant {name}")
        if configuration.get("active") is not False or configuration.get("shadow") is not False:
            raise PrebuildReadinessError("TurboQuant release configuration must keep both modes false")
    host = _mapping(turboquant.get("host_observation"), "TurboQuant host observation")
    if host.get("active") is not False or host.get("policy") != "superseded_existing_host_not_a_build_input":
        raise PrebuildReadinessError("current host TurboQuant state has no approved boundary")
    runtime_config = _mapping(turboquant.get("runtime_config"), "active runtime config evidence")
    for field in ("root_fingerprint", "inventory_sha256"):
        _expect_sha256(runtime_config.get(field), f"active runtime config {field}")
    if runtime_config.get("local_config_present") not in {True, False}:
        raise PrebuildReadinessError("active runtime config local-file status is invalid")
    if host.get("runtime_config_root_fingerprint") != runtime_config.get(
        "root_fingerprint"
    ) or host.get("runtime_config_inventory_sha256") != runtime_config.get(
        "inventory_sha256"
    ) or host.get("local_config_present") != runtime_config.get("local_config_present"):
        raise PrebuildReadinessError("current host TurboQuant state is not config-bound")
    counts = _mapping(turboquant.get("database_sidecar_counts"), "TurboQuant sidecar census")
    if set(counts) != set(SIDECAR_COLUMNS) or any(int(counts.get(column) or 0) != 0 for column in SIDECAR_COLUMNS):
        raise PrebuildReadinessError("TurboQuant database sidecars are not all zero")

    private_inputs = _mapping(candidate.get("private_build_inputs"), "private build inputs")
    if private_inputs.get("status") != "verified":
        raise PrebuildReadinessError("private build inputs did not pass verification")
    for field in (
        "root_fingerprint",
        "cache_root_fingerprint",
        "inventory_sha256",
        "signing_public_key_sha256",
    ):
        _expect_sha256(private_inputs.get(field), f"private build {field}")
    if int(private_inputs.get("cache_size_bytes") or 0) <= 0:
        raise PrebuildReadinessError("private staged dependency cache is empty")
    if private_inputs.get("signing_key_present") is not True or private_inputs.get(
        "signing_key_matches_launcher"
    ) is not True:
        raise PrebuildReadinessError("private signing key is not bound to the launcher")
    gates = _list(private_inputs.get("dependency_gates"), "private dependency gates")
    expected_gates = {
        (profile, mode)
        for profile in (PUBLIC_PROFILE, PERSONAL_PROFILE)
        for mode in ("verify", "audit")
    }
    observed_gates = {
        (str(gate.get("profile")), str(gate.get("mode")))
        for gate in gates
        if isinstance(gate, dict) and gate.get("status") == "passed"
    }
    if observed_gates != expected_gates:
        raise PrebuildReadinessError("private dependency cache gates are incomplete")

    disk = _mapping(candidate.get("disk"), "disk estimate")
    required_bytes = int(disk.get("required_bytes") or 0)
    free_bytes = int(disk.get("free_bytes") or 0)
    if required_bytes <= 0 or free_bytes < required_bytes:
        raise PrebuildReadinessError("insufficient disk space for both release profiles")
    _expect_sha256(disk.get("estimate_sha256"), "disk estimate")
    future_output = _mapping(candidate.get("future_output"), "future output")
    _expect_sha256(future_output.get("root_fingerprint"), "future output root")
    if future_output.get("empty") is not True:
        raise PrebuildReadinessError("future output root is not unused")
    boundaries = _mapping(candidate.get("boundaries"), "release boundaries")
    if set(boundaries) != {
        "installer_build_started",
        "installer_installed",
        "memory_reset",
        "reingestion_started",
        "push_tag_or_publication",
    } or any(value is not False for value in boundaries.values()):
        raise PrebuildReadinessError("prebuild receipt crosses an unapproved release boundary")


def collect_readiness(
    *,
    repo_root: Path,
    runtime_config_root: Path,
    private_build_root: Path,
    vault_root: Path,
    fixture_root: Path,
    future_output_root: Path,
    wsl_distro: str,
    wsl_workspace: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    runtime_config_root = runtime_config_root.resolve()
    private_build_root = private_build_root.resolve()
    vault_root = vault_root.resolve()
    fixture_root = fixture_root.resolve()
    future_output_root = future_output_root.resolve()
    if not vault_root.is_dir():
        raise PrebuildReadinessError("explicit asset vault root is unavailable")
    if runtime_config_root == repo_root or repo_root in runtime_config_root.parents:
        raise PrebuildReadinessError(
            "active runtime config root must remain distinct from the release worktree"
        )
    initial = _capture_source_identity(repo_root)
    version = _canonical_version(repo_root)
    if initial["clean"] is not True:
        raise PrebuildReadinessError("source tree is dirty")
    if initial["dedicated_worktree"] is not True:
        raise PrebuildReadinessError("release requires a dedicated source worktree")
    if int(initial["remote_alignment"].get("behind_origin_dev", -1)) != 0:
        raise PrebuildReadinessError("release source is behind origin/dev")
    profiles, profile_context = _collect_profiles(repo_root)
    private_build_inputs = _collect_private_build_inputs(
        repo_root=repo_root,
        private_build_root=private_build_root,
    )
    vault, evidence_by_asset = _collect_vault(
        vault_root=vault_root,
        profile_context=profile_context,
    )
    transformations = _collect_transformations(evidence_by_asset)
    model_probes = _collect_model_probe_coverage(
        profile_context=profile_context,
        vault=vault,
    )
    wsl = _collect_wsl(
        repo_root=repo_root,
        distro=wsl_distro,
        workspace=wsl_workspace,
    )
    fixture = _collect_fixture(repo_root=repo_root, fixture_root=fixture_root)
    turboquant = _collect_turboquant(
        repo_root,
        runtime_config_root=runtime_config_root,
    )
    disk, future_output = _collect_disk(
        private_build_inputs=private_build_inputs,
        future_output_root=future_output_root,
        profile_context=profile_context,
        evidence_by_asset=evidence_by_asset,
    )
    observed = _capture_source_identity(repo_root)
    source = {
        "initial_commit": initial["commit"],
        "observed_commit": observed["commit"],
        "initial_tree": initial["tree"],
        "observed_tree": observed["tree"],
        "clean": bool(initial["clean"] and observed["clean"]),
        "branch": observed["branch"],
        "dedicated_worktree": observed["dedicated_worktree"],
        "root_fingerprint": observed["root_fingerprint"],
        "config_inventory": observed["config_inventory"],
        "config_inventory_sha256": observed["config_inventory_sha256"],
        "remote_alignment": observed["remote_alignment"],
    }
    candidate = {
        "schema": SCHEMA,
        "status": "candidate",
        "version": version,
        "source": source,
        "profiles": profiles,
        "vault": vault,
        "transformations": transformations,
        "model_load_probes": model_probes,
        "wsl": wsl,
        "fixture_pack": fixture,
        "turboquant": turboquant,
        "private_build_inputs": private_build_inputs,
        "disk": disk,
        "future_output": future_output,
        "boundaries": {
            "installer_build_started": False,
            "installer_installed": False,
            "memory_reset": False,
            "reingestion_started": False,
            "push_tag_or_publication": False,
        },
    }
    validate_readiness(candidate, expected_version=version)
    return candidate


def write_readiness_receipt(
    candidate: Mapping[str, Any],
    *,
    receipt_path: Path,
    repo_root: Path,
) -> Path:
    validate_readiness(candidate, expected_version=_canonical_version(repo_root))
    receipt_path = receipt_path.resolve()
    repo_root = repo_root.resolve()
    if receipt_path == repo_root or repo_root in receipt_path.parents:
        raise PrebuildReadinessError("prebuild receipt must remain external to source control")
    if receipt_path.exists():
        raise PrebuildReadinessError("refusing to overwrite an existing prebuild receipt")
    receipt = copy.deepcopy(dict(candidate))
    receipt["status"] = "passed"
    receipt["created_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.parent / f".{receipt_path.name}.tmp"
    if temporary.exists():
        raise PrebuildReadinessError("prebuild receipt temporary path is not fresh")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(receipt_path)
    return receipt_path


def load_readiness_receipt(
    receipt_path: Path, *, expected_version: str
) -> dict[str, Any]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrebuildReadinessError("prebuild readiness receipt is unreadable") from exc
    if not isinstance(receipt, dict):
        raise PrebuildReadinessError("prebuild readiness receipt must be a JSON object")
    validate_readiness(receipt, expected_version=expected_version)
    if receipt.get("status") != "passed":
        raise PrebuildReadinessError("prebuild readiness receipt is not terminal passing evidence")
    return receipt


def _verify_source_binding(receipt: Mapping[str, Any], repo_root: Path) -> None:
    source = _mapping(receipt.get("source"), "receipt source")
    current = _capture_source_identity(repo_root)
    if (
        current["commit"] != source.get("initial_commit")
        or current["tree"] != source.get("initial_tree")
        or current["clean"] is not True
        or current["dedicated_worktree"] is not True
        or current["root_fingerprint"] != source.get("root_fingerprint")
        or current["config_inventory_sha256"] != source.get("config_inventory_sha256")
        or _canonical_version(repo_root) != receipt.get("version")
    ):
        raise PrebuildReadinessError("source commit/tree/config/version no longer matches receipt")


def verify_readiness_receipt(
    *,
    receipt_path: Path,
    repo_root: Path,
    phase: str,
    runtime_config_root: Path | None = None,
    private_build_root: Path | None = None,
    vault_root: Path | None = None,
    fixture_root: Path | None = None,
    future_output_root: Path | None = None,
    wsl_distro: str = "Ubuntu-22.04",
    wsl_workspace: str = "",
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    receipt = load_readiness_receipt(
        receipt_path,
        expected_version=_canonical_version(repo_root),
    )
    _verify_source_binding(receipt, repo_root)
    if phase == "source":
        return {
            "schema": SCHEMA,
            "status": "verified",
            "phase": phase,
            "source_commit": receipt["source"]["initial_commit"],
        }
    if phase != "prebuild":
        raise PrebuildReadinessError(f"unsupported readiness verification phase: {phase}")
    if (
        runtime_config_root is None
        or private_build_root is None
        or vault_root is None
        or fixture_root is None
        or future_output_root is None
        or not wsl_workspace
    ):
        raise PrebuildReadinessError("full prebuild verification requires explicit bound inputs")
    current = collect_readiness(
        repo_root=repo_root,
        runtime_config_root=runtime_config_root,
        private_build_root=private_build_root,
        vault_root=vault_root,
        fixture_root=fixture_root,
        future_output_root=future_output_root,
        wsl_distro=wsl_distro,
        wsl_workspace=wsl_workspace,
    )
    comparisons = (
        ("version", receipt["version"], current["version"]),
        ("source commit", receipt["source"]["initial_commit"], current["source"]["initial_commit"]),
        ("source tree", receipt["source"]["initial_tree"], current["source"]["initial_tree"]),
        ("Public selector", receipt["profiles"][PUBLIC_PROFILE]["selector_sha256"], current["profiles"][PUBLIC_PROFILE]["selector_sha256"]),
        ("Public asset inventory", receipt["profiles"][PUBLIC_PROFILE]["asset_inventory_sha256"], current["profiles"][PUBLIC_PROFILE]["asset_inventory_sha256"]),
        ("Personal selector", receipt["profiles"][PERSONAL_PROFILE]["selector_sha256"], current["profiles"][PERSONAL_PROFILE]["selector_sha256"]),
        ("Personal asset inventory", receipt["profiles"][PERSONAL_PROFILE]["asset_inventory_sha256"], current["profiles"][PERSONAL_PROFILE]["asset_inventory_sha256"]),
        ("vault inventory", receipt["vault"]["inventory_sha256"], current["vault"]["inventory_sha256"]),
        ("transformation inventory", receipt["transformations"].get("inventory_sha256"), current["transformations"].get("inventory_sha256")),
        ("model probe inventory", receipt["model_load_probes"].get("inventory_sha256"), current["model_load_probes"].get("inventory_sha256")),
        ("fixture manifest", receipt["fixture_pack"]["manifest_sha256"], current["fixture_pack"]["manifest_sha256"]),
        ("fixture pack", receipt["fixture_pack"]["fixture_pack_sha256"], current["fixture_pack"]["fixture_pack_sha256"]),
        ("WSL prerequisite", receipt["wsl"]["evidence_sha256"], current["wsl"]["evidence_sha256"]),
        ("TurboQuant evidence", receipt["turboquant"]["evidence_sha256"], current["turboquant"]["evidence_sha256"]),
        ("private build root", receipt["private_build_inputs"]["root_fingerprint"], current["private_build_inputs"]["root_fingerprint"]),
        ("private build inventory", receipt["private_build_inputs"]["inventory_sha256"], current["private_build_inputs"]["inventory_sha256"]),
        ("disk estimate", receipt["disk"]["estimate_sha256"], current["disk"]["estimate_sha256"]),
        ("future output", receipt["future_output"]["root_fingerprint"], current["future_output"]["root_fingerprint"]),
    )
    for label, expected, observed in comparisons:
        if expected != observed:
            raise PrebuildReadinessError(f"{label} no longer matches prebuild receipt")
    return {
        "schema": SCHEMA,
        "status": "verified",
        "phase": phase,
        "source_commit": receipt["source"]["initial_commit"],
        "vault_inventory_sha256": receipt["vault"]["inventory_sha256"],
        "fixture_pack_sha256": receipt["fixture_pack"]["fixture_pack_sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--repo-root", type=Path, required=True)
    preflight.add_argument("--runtime-config-root", type=Path, required=True)
    preflight.add_argument("--private-build-root", type=Path, required=True)
    preflight.add_argument("--vault-root", type=Path, required=True)
    preflight.add_argument("--fixture-root", type=Path, required=True)
    preflight.add_argument("--future-output-root", type=Path, required=True)
    preflight.add_argument("--receipt-path", type=Path, required=True)
    preflight.add_argument("--wsl-distro", required=True)
    preflight.add_argument("--wsl-workspace", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--repo-root", type=Path, required=True)
    verify.add_argument("--phase", choices=("source", "prebuild"), required=True)
    verify.add_argument("--vault-root", type=Path)
    verify.add_argument("--runtime-config-root", type=Path)
    verify.add_argument("--private-build-root", type=Path)
    verify.add_argument("--fixture-root", type=Path)
    verify.add_argument("--future-output-root", type=Path)
    verify.add_argument("--wsl-distro", default="Ubuntu-22.04")
    verify.add_argument("--wsl-workspace", default="")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            candidate = collect_readiness(
                repo_root=args.repo_root,
                runtime_config_root=args.runtime_config_root,
                private_build_root=args.private_build_root,
                vault_root=args.vault_root,
                fixture_root=args.fixture_root,
                future_output_root=args.future_output_root,
                wsl_distro=args.wsl_distro,
                wsl_workspace=args.wsl_workspace,
            )
            receipt = write_readiness_receipt(
                candidate,
                receipt_path=args.receipt_path,
                repo_root=args.repo_root,
            )
            print(receipt)
        else:
            result = verify_readiness_receipt(
                receipt_path=args.receipt,
                repo_root=args.repo_root,
                phase=args.phase,
                runtime_config_root=args.runtime_config_root,
                private_build_root=args.private_build_root,
                vault_root=args.vault_root,
                fixture_root=args.fixture_root,
                future_output_root=args.future_output_root,
                wsl_distro=args.wsl_distro,
                wsl_workspace=args.wsl_workspace,
            )
            print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, PrebuildReadinessError) as exc:
        print(f"prebuild readiness failure: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
