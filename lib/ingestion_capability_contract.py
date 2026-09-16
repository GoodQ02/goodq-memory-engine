"""Canonical, pure capability outcome contract for ingestion evidence."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any


CAPABILITY_RECEIPT_SCHEMA_VERSION = 2
CAPABILITY_MATRIX_SCHEMA_VERSION = 1
# Backwards-compatible import name for receipt consumers.
CAPABILITY_SCHEMA_VERSION = CAPABILITY_RECEIPT_SCHEMA_VERSION

RUNTIME_CAPABILITY_POLICIES: dict[str, dict[str, Any]] = {
    "audio_transcribe_local": {"classification": "core_required", "status_surface": "transcript_meta", "asset_ids": ["faster_whisper_medium"]},
    "image_ocr": {"classification": "enhancement_optional", "status_surface": "ocr_meta", "asset_ids": ["tesseract"]},
    "image_caption": {"classification": "enhancement_optional", "status_surface": "caption_meta", "asset_ids": ["blip_caption", "vit_gpt2_caption"]},
    "object_detect": {"classification": "enhancement_optional", "status_surface": "object_meta", "asset_ids": ["opencv_nanodet", "opencv_yolox"]},
    "face_embed": {"classification": "enhancement_optional", "status_surface": "face_meta", "asset_ids": ["opencv_yunet", "opencv_sface"]},
    "image_embed_dino": {"classification": "enhancement_optional", "status_surface": "dino_meta", "asset_ids": ["dinov2"]},
    "image_embed_clip": {"classification": "enhancement_optional", "status_surface": "clip_meta", "asset_ids": ["clip_vit"]},
    "tagger": {"classification": "enhancement_optional", "status_surface": "tagger_meta", "asset_ids": ["bert_ner"]},
    "audio_metadata": {"classification": "enhancement_optional", "status_surface": "audio_meta", "asset_ids": []},
    "audio_speaker_merge": {"classification": "profile_optional", "status_surface": "speaker_meta", "asset_ids": ["pyannote_diarization", "pyannote_segmentation", "pyannote_wespeaker"]},
    "audio_music_events": {"classification": "enhancement_optional", "status_surface": "music_meta", "asset_ids": []},
    "audio_time_hints": {"classification": "enhancement_optional", "status_surface": "time_hints", "asset_ids": []},
    "audio_emotion": {"classification": "enhancement_optional", "status_surface": "audio_emotion_meta", "asset_ids": ["hubert_emotion", "wav2vec2_emotion"]},
    "audio_wav2vec2_enrichment": {"classification": "profile_optional", "status_surface": "wsl_capability_outcomes.wav2vec2", "asset_ids": ["wav2vec2_base_960h"]},
    "audio_clap_handoff": {"classification": "profile_optional", "status_surface": "wsl_capability_outcomes.clap_handoff", "asset_ids": []},
    "sentiment": {"classification": "enhancement_optional", "status_surface": "sentiment_meta", "asset_ids": ["sentiment_model", "vader_lexicon"]},
    "emotion_classify": {"classification": "enhancement_optional", "status_surface": "emotion_meta", "asset_ids": ["emotion_classify_model"]},
    "audio_embed_clap": {"classification": "enhancement_optional", "status_surface": "clap_meta", "asset_ids": ["clap_audio"]},
    "local_vlm": {"classification": "profile_optional", "status_surface": "local_vlm_meta", "asset_ids": ["qwen2_5_vl_7b", "qwen2_5_vl_3b"]},
}

_NON_FAILURE_STATUSES = {"ok", "completed", "not_applicable"}
_RUNTIME_CLASSIFICATIONS = {"core_required", "enhancement_optional", "profile_optional", "gated_personal", "excluded"}
_CAPABILITY_PROFILE_FIELDS = {
    "runtime_owner",
    "implementation",
    "status_surface",
    "asset_ids",
    "content_applicability",
    "fallback_policy",
}
_ASSET_DISPOSITIONS = {
    "ingest_runtime",
    "infrastructure_runtime",
    "alternate_model",
    "external_serving_capability",
    "personal_overlay",
    "build_only",
    "excluded",
}


def build_capability_receipt(
    *,
    run_id: str,
    profile: str,
    terminal_status: str,
    step_rows: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    evidence_paths: dict[str, str],
    expected_capabilities: dict[str, dict[str, Any]] | None = None,
    malformed_row_count: int = 0,
    input_count: int | None = None,
    full_coverage: bool = False,
    content_truth_by_scene: dict[str, dict[str, bool]] | None = None,
) -> dict[str, Any]:
    """Build a receipt solely from already-structured runtime evidence."""

    observations = [_normalize_capability(row) for row in step_rows]
    for capability in observations:
        capability["closure_status"] = _closure_status(capability)
    capabilities = _aggregate_capabilities(observations)
    if evidence_paths.get("step_runs"):
        for capability in capabilities:
            if not capability.get("evidence_references"):
                capability["evidence_references"] = ["step_runs"]
    capabilities_by_step = {row["step"]: row for row in capabilities}
    observed_steps = set(capabilities_by_step)
    expected = expected_capabilities or {}
    content_truth = content_truth_by_scene or {}
    missing_expected = 0
    if full_coverage:
        for step, policy in sorted(expected.items()):
            if step in capabilities_by_step:
                capability = capabilities_by_step[step]
                capability.update(
                    {
                        key: value
                        for key, value in policy.items()
                        if key
                        in {
                            "runtime_owner",
                            "implementation",
                            "asset_ids",
                            "content_applicability",
                            "fallback_policy",
                        }
                    }
                )
                if str(policy.get("disposition") or "runtime") == "policy_excluded":
                    capability["closure_status"] = "policy_exclusion_violated"
                    capability["reason"] = str(
                        policy.get("reason") or "policy_exclusion_violated"
                    )
                    continue
                if capability["closure_status"] == "ran_content_appropriate_empty":
                    truth_key = str(policy.get("content_applicability") or "")
                    scene_ids = capability.get("affected_scene_ids") or []
                    if not truth_key or not scene_ids or not all(
                        isinstance(content_truth.get(scene_id), dict)
                        and content_truth[scene_id].get(truth_key) is False
                        for scene_id in scene_ids
                    ):
                        capability["closure_status"] = "content_truth_mismatch"
                fallback_policy = policy.get("fallback_policy")
                if isinstance(fallback_policy, list):
                    allowed_fallbacks = {
                        str(item) for item in fallback_policy if str(item).strip()
                    }
                elif isinstance(fallback_policy, str) and fallback_policy not in {
                    "",
                    "none",
                }:
                    allowed_fallbacks = {fallback_policy}
                else:
                    allowed_fallbacks = set()
                fallback_chain = set(capability.get("fallback_chain") or [])
                if fallback_chain - allowed_fallbacks:
                    capability["closure_status"] = "unapproved_fallback"
                elif (
                    fallback_chain
                    and capability["closure_status"] == "ran_with_output"
                ):
                    capability["closure_status"] = "ran_with_approved_fallback"
                continue
            disposition = str(policy.get("disposition") or "runtime")
            closure_status = (
                "policy_excluded"
                if disposition == "policy_excluded"
                else "not_observed"
            )
            missing = {
                "step": step,
                "classification": str(
                    (RUNTIME_CAPABILITY_POLICIES.get(step) or {}).get(
                        "classification", "profile_optional"
                    )
                ),
                "status_surface": str(policy.get("status_surface") or ""),
                "status": (
                    "not_applicable"
                    if closure_status == "policy_excluded"
                    else "missing"
                ),
                "closure_status": closure_status,
                "reason": str(policy.get("reason") or closure_status),
                "requested_implementation": str(policy.get("implementation") or step),
                "effective_implementation": "",
                "fallback_chain": [],
                "affected_scene_ids": [],
                "error": "",
                "runtime_owner": str(policy.get("runtime_owner") or ""),
                "implementation": str(policy.get("implementation") or ""),
                "asset_ids": [str(item) for item in policy.get("asset_ids") or []],
                "content_applicability": str(policy.get("content_applicability") or ""),
                "fallback_policy": policy.get("fallback_policy", "none"),
                "evidence_references": [
                    reference
                    for reference in (
                        "capability_profile_contract",
                        "step_runs" if closure_status == "not_observed" else "",
                    )
                    if reference and evidence_paths.get(reference)
                ],
            }
            capabilities.append(missing)
            capabilities_by_step[step] = missing
            if closure_status == "not_observed":
                missing_expected += 1
    summary = _summarize(capabilities)
    summary.update(
        {
            "missing_expected": missing_expected,
            "malformed_rows": max(0, int(malformed_row_count)),
            "input_count": input_count,
            "unexpected_capabilities": (
                sorted(observed_steps - set(expected)) if full_coverage else []
            ),
        }
    )
    coverage_failures = (
        missing_expected
        + summary["malformed_rows"]
        + len(summary["unexpected_capabilities"])
    )
    if full_coverage:
        coverage_failures += sum(
            1
            for step in observed_steps & set(expected)
            if capabilities_by_step[step]["closure_status"]
            not in {
                "ran_with_output",
                "ran_with_approved_fallback",
                "ran_content_appropriate_empty",
                "policy_excluded",
            }
        )
    if full_coverage and (
        not isinstance(input_count, int)
        or isinstance(input_count, bool)
        or input_count <= 0
    ):
        coverage_failures += 1
    summary["coverage_failures"] = coverage_failures
    outcome = _resolve_outcome(
        terminal_status,
        summary,
        full_coverage=full_coverage,
    )
    return {
        "schema_version": CAPABILITY_RECEIPT_SCHEMA_VERSION,
        "run_id": str(run_id),
        "profile": str(profile),
        "terminal_status": str(terminal_status),
        "outcome": outcome,
        "summary": summary,
        "capabilities": capabilities,
        "capabilities_by_step": capabilities_by_step,
        "warnings": list(warnings),
        "scene_count": len(scenes),
        "full_coverage": bool(full_coverage),
        "evidence": dict(evidence_paths),
    }


def render_capability_receipt(receipt: dict[str, Any]) -> str:
    """Render the receipt without reclassifying its evidence."""

    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    return (
        "[CAPABILITY] outcome={outcome} core_failures={core} "
        "optional_skips={skips} optional_errors={errors} "
        "recovered_fallbacks={fallbacks}".format(
            outcome=receipt.get("outcome", "unknown"),
            core=summary.get("required_core_failures", 0),
            skips=summary.get("optional_skips", 0),
            errors=summary.get("optional_errors", 0),
            fallbacks=summary.get("recovered_fallbacks", 0),
        )
    )


def build_capability_matrix(
    *,
    registry: dict[str, Any],
    catalog: dict[str, Any],
    runtime_policies: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Reconcile declared runtime paths with registry and catalog evidence."""

    catalog_assets = catalog.get("assets") if isinstance(catalog.get("assets"), dict) else catalog
    if not isinstance(catalog_assets, dict):
        raise ValueError("catalog assets must be a mapping")
    runtime_steps: dict[str, dict[str, Any]] = {}
    for step, policy in sorted(runtime_policies.items()):
        classification = str(policy.get("classification") or "")
        status_surface = policy.get("status_surface")
        if classification not in _RUNTIME_CLASSIFICATIONS:
            raise ValueError(f"invalid runtime classification for {step}: {classification or 'missing'}")
        if not isinstance(status_surface, str) or not status_surface.strip():
            raise ValueError(f"runtime status surface missing for {step}")
        asset_ids = [str(asset_id) for asset_id in policy.get("asset_ids") or []]
        registry_record = registry.get(step)
        if isinstance(registry_record, dict) and str(registry_record.get("classification") or "") == "REQUIRED_FIRST_LAUNCH":
            if classification != "core_required":
                raise ValueError(f"runtime classification conflict for {step}")
        for asset_id in asset_ids:
            catalog_record = catalog_assets.get(asset_id)
            if not isinstance(catalog_record, dict):
                raise ValueError(f"runtime asset absent from catalog: {step}:{asset_id}")
            registry_asset = registry.get(asset_id)
            if isinstance(registry_asset, dict):
                expected_source = registry_asset.get("repo_id")
                if expected_source:
                    if catalog_record.get("source") != expected_source:
                        raise ValueError(f"registry/catalog source mismatch for {asset_id}")
                    if registry_asset.get("revision") and catalog_record.get("revision") != registry_asset.get("revision"):
                        raise ValueError(f"registry/catalog revision mismatch for {asset_id}")
        runtime_steps[step] = {
            "classification": classification,
            "status_surface": status_surface,
            "asset_ids": asset_ids,
        }
    return {
        "schema_version": CAPABILITY_MATRIX_SCHEMA_VERSION,
        "runtime_steps": runtime_steps,
        "assets": {str(key): dict(value) for key, value in sorted(catalog_assets.items()) if isinstance(value, dict)},
        "profile_selections": {},
    }


def validate_profile_selection(matrix: dict[str, Any], profile: str) -> list[str]:
    """Reject explicit public selections that contain non-distributable assets."""

    selected = (matrix.get("profile_selections") or {}).get(profile) or []
    assets = matrix.get("assets") if isinstance(matrix.get("assets"), dict) else {}
    selected_ids = [str(asset_id) for asset_id in selected]
    if str(profile).startswith("PUBLIC_"):
        for asset_id in selected_ids:
            record = assets.get(asset_id)
            if not isinstance(record, dict):
                raise ValueError(f"profile selects absent asset: {profile}:{asset_id}")
            if record.get("status") != "eligible" or record.get("vault_scope") != "personal_and_distributable":
                raise ValueError(f"public profile selects non-distributable asset: {profile}:{asset_id}")
    return selected_ids


def resolve_capability_profile(
    contract: dict[str, Any],
    profile: str,
) -> dict[str, dict[str, Any]]:
    """Expand one capability profile into complete per-capability records."""

    if contract.get("schema_version") != 2:
        raise ValueError("capability profile contract must use schema_version 2")
    definitions = contract.get("capabilities")
    profiles = contract.get("profiles")
    if not isinstance(definitions, dict) or not isinstance(profiles, dict):
        raise ValueError("capability profile contract requires mappings")

    def _resolve_policy(name: str, seen: set[str]) -> dict[str, Any]:
        if name in seen:
            raise ValueError(f"capability profile inheritance cycle: {name}")
        record = profiles.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"unknown capability profile: {name}")
        parent = record.get("extends")
        resolved = _resolve_policy(str(parent), seen | {name}) if parent else {
            "default_disposition": "runtime",
            "capability_dispositions": {},
        }
        resolved = {
            "default_disposition": str(
                record.get("default_disposition")
                or resolved.get("default_disposition")
                or "runtime"
            ),
            "capability_dispositions": dict(
                resolved.get("capability_dispositions") or {}
            ),
        }
        overrides = record.get("capability_dispositions") or {}
        if not isinstance(overrides, dict):
            raise ValueError(
                f"capability profile {name} dispositions must be a mapping"
            )
        for step, override in overrides.items():
            if step not in definitions:
                raise ValueError(
                    f"capability profile {name} overrides unknown capability: {step}"
                )
            if not isinstance(override, dict):
                raise ValueError(
                    f"capability profile {name} has invalid disposition: {step}"
                )
            resolved["capability_dispositions"][str(step)] = dict(override)
        return resolved

    policy = _resolve_policy(profile, set())
    expanded: dict[str, dict[str, Any]] = {}
    for step, definition in sorted(definitions.items()):
        if not isinstance(definition, dict) or not _CAPABILITY_PROFILE_FIELDS <= set(
            definition
        ):
            raise ValueError(f"incomplete capability definition: {step}")
        override = policy["capability_dispositions"].get(step) or {}
        disposition = str(
            override.get("disposition") or policy["default_disposition"]
        )
        if disposition not in {"runtime", "policy_excluded"}:
            raise ValueError(
                f"invalid capability disposition for {profile}:{step}: {disposition}"
            )
        record = dict(definition)
        record.update(override)
        record["disposition"] = disposition
        if disposition == "runtime" and str(record.get("runtime_owner")) == "none":
            raise ValueError(f"runtime capability lacks owner: {profile}:{step}")
        expanded[str(step)] = record
    return expanded


def resolve_installer_profile(
    profile_contract: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    """Resolve inherited packs and explicit capability/component policy."""

    profiles = profile_contract.get("profiles") if isinstance(profile_contract.get("profiles"), dict) else {}
    if not isinstance(profiles, dict):
        raise ValueError("profile contract must contain a profiles mapping")

    def _resolve(name: str, seen: set[str]) -> dict[str, Any]:
        if name in seen:
            raise ValueError(f"profile inheritance cycle: {name}")
        record = profiles.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"unknown installer profile: {name}")

        parent = record.get("extends")
        resolved = _resolve(str(parent), seen | {name}) if parent else {
            "include_packs": [],
            "exclude_assets": [],
            "forbidden_assets": [],
            "capability_dispositions": {},
            "component_dispositions": {},
        }
        resolved = {
            **resolved,
            "include_packs": list(resolved.get("include_packs") or []),
            "exclude_assets": list(resolved.get("exclude_assets") or []),
            "forbidden_assets": list(resolved.get("forbidden_assets") or []),
            "capability_dispositions": dict(resolved.get("capability_dispositions") or {}),
            "component_dispositions": dict(resolved.get("component_dispositions") or {}),
        }
        for key in ("distribution", "acceptance_required", "expected_asset_count"):
            if key in record:
                resolved[key] = record[key]
        for pack in record.get("include_packs") or []:
            pack_name = str(pack)
            if pack_name not in resolved["include_packs"]:
                resolved["include_packs"].append(pack_name)
        for asset_id in record.get("exclude_assets") or []:
            asset_name = str(asset_id)
            if asset_name not in resolved["exclude_assets"]:
                resolved["exclude_assets"].append(asset_name)
        for asset_id in record.get("forbidden_assets") or []:
            asset_name = str(asset_id)
            if asset_name not in resolved["forbidden_assets"]:
                resolved["forbidden_assets"].append(asset_name)
        for key in ("capability_dispositions", "component_dispositions"):
            values = record.get(key) or {}
            if not isinstance(values, dict):
                raise ValueError(f"profile {name} {key} must be a mapping")
            for item_name, disposition in values.items():
                if not isinstance(disposition, dict) or not disposition.get("status"):
                    raise ValueError(f"profile {name} has invalid {key}: {item_name}")
                resolved[key][str(item_name)] = dict(disposition)
        return resolved

    return _resolve(profile, set())


def resolve_profile_assets(
    catalog: dict[str, Any],
    profile_contract: dict[str, Any],
    profile: str,
) -> list[str]:
    """Resolve one profile's sealed, policy-permitted catalog asset IDs."""

    assets = catalog.get("assets") if isinstance(catalog.get("assets"), dict) else catalog
    profiles = profile_contract.get("profiles") if isinstance(profile_contract.get("profiles"), dict) else {}
    if not isinstance(assets, dict) or not isinstance(profiles, dict):
        raise ValueError("catalog and profile contract must contain mappings")

    profile_record = profiles.get(profile)
    if not isinstance(profile_record, dict):
        raise ValueError(f"unknown installer profile: {profile}")
    resolved_profile = resolve_installer_profile(profile_contract, profile)
    distribution = str(resolved_profile.get("distribution") or "")
    pack_scopes = set(resolved_profile.get("include_packs") or [])
    excluded_assets = {str(asset_id) for asset_id in resolved_profile.get("exclude_assets") or []}
    selected: list[str] = []
    for asset_id, record in sorted(assets.items()):
        if (
            not isinstance(record, dict)
            or str(asset_id) in excluded_assets
            or str(record.get("pack_scope") or "") not in pack_scopes
        ):
            continue
        manifest_seal = record.get("sealed_manifest_sha256")
        source_seal = record.get("source_artifact_sha256")
        build_time_seal = record.get("seal_mode") == "build_time_sbom"
        if not (
            isinstance(manifest_seal, str)
            and len(manifest_seal) == 64
            or isinstance(source_seal, str)
            and len(source_seal) == 64
            or build_time_seal
        ):
            raise ValueError(f"profile selects unsealed asset: {profile}:{asset_id}")
        if distribution == "public" and (
            record.get("status") != "eligible"
            or record.get("vault_scope") != "personal_and_distributable"
        ):
            raise ValueError(f"public profile selects non-distributable asset: {profile}:{asset_id}")
        selected.append(str(asset_id))
    return selected


def build_profile_asset_closure(
    *,
    catalog: dict[str, Any],
    profile_contract: dict[str, Any],
    registry: dict[str, Any],
    capability_profile: dict[str, dict[str, Any]],
    profile: str,
) -> dict[str, Any]:
    """Resolve one complete, hash-bound asset-to-runtime disposition ledger."""

    catalog_assets = (
        catalog.get("assets")
        if isinstance(catalog.get("assets"), dict)
        else catalog
    )
    asset_contracts = profile_contract.get("asset_contracts")
    if not isinstance(catalog_assets, dict) or not isinstance(asset_contracts, dict):
        raise ValueError("asset closure requires catalog assets and asset_contracts")
    selected = resolve_profile_assets(catalog, profile_contract, profile)
    resolved_profile = resolve_installer_profile(profile_contract, profile)
    expected_count = resolved_profile.get("expected_asset_count")
    if expected_count is not None and len(selected) != int(expected_count):
        raise ValueError(
            f"profile asset count mismatch: {profile}: {len(selected)} != {expected_count}"
        )
    forbidden = {
        str(asset_id) for asset_id in resolved_profile.get("forbidden_assets") or []
    }
    forbidden_selected = sorted(set(selected) & forbidden)
    if forbidden_selected:
        raise ValueError(
            f"profile selects forbidden assets: {profile}: {forbidden_selected}"
        )

    runtime_capability_assets: dict[str, list[str]] = {}
    excluded_capability_assets: dict[str, list[str]] = {}
    for capability, record in sorted(capability_profile.items()):
        if not isinstance(record, dict):
            raise ValueError(f"invalid capability record: {profile}:{capability}")
        target = (
            runtime_capability_assets
            if record.get("disposition") == "runtime"
            else excluded_capability_assets
        )
        for asset_id in record.get("asset_ids") or []:
            target.setdefault(str(asset_id), []).append(str(capability))
    missing_runtime_capabilities = sorted(
        capability
        for capability, record in capability_profile.items()
        if record.get("disposition") == "runtime"
        and record.get("asset_ids")
        and not set(str(asset_id) for asset_id in record.get("asset_ids") or [])
        & set(selected)
    )
    if missing_runtime_capabilities:
        raise ValueError(
            f"runtime capability has no selected asset: {profile}: "
            f"{missing_runtime_capabilities}"
        )

    assets: list[dict[str, Any]] = []
    for asset_id in selected:
        catalog_record = catalog_assets.get(asset_id)
        contract = asset_contracts.get(asset_id)
        if not isinstance(catalog_record, dict):
            raise ValueError(f"profile selects absent asset: {profile}:{asset_id}")
        if not isinstance(contract, dict):
            raise ValueError(f"selected asset lacks disposition: {profile}:{asset_id}")
        disposition = str(contract.get("disposition") or "")
        runtime_owner = str(contract.get("runtime_owner") or "").strip()
        probe = str(contract.get("probe") or "").strip()
        if disposition not in _ASSET_DISPOSITIONS:
            raise ValueError(
                f"invalid selected asset disposition: {profile}:{asset_id}:{disposition}"
            )
        if disposition == "excluded":
            raise ValueError(f"selected asset cannot be excluded: {profile}:{asset_id}")
        if not runtime_owner or runtime_owner == "none":
            raise ValueError(f"selected asset lacks runtime owner: {profile}:{asset_id}")
        kind = str(catalog_record.get("kind") or "")
        registry_bound = asset_id in registry
        if kind in {"model", "lexicon"} and not registry_bound:
            raise ValueError(f"selected model lacks runtime registry: {profile}:{asset_id}")
        if kind == "model" and (not probe or probe == "none"):
            raise ValueError(f"selected model lacks load probe: {profile}:{asset_id}")
        if not probe or probe == "none":
            raise ValueError(f"selected asset lacks probe: {profile}:{asset_id}")
        assets.append(
            {
                "asset_id": asset_id,
                "kind": kind,
                "source": str(catalog_record.get("source") or ""),
                "revision": str(catalog_record.get("revision") or ""),
                "pack_scope": str(catalog_record.get("pack_scope") or ""),
                "hardware_profile": str(
                    catalog_record.get("hardware_profile") or ""
                ),
                "sealed_manifest_sha256": str(
                    catalog_record.get("sealed_manifest_sha256") or ""
                ),
                "disposition": disposition,
                "runtime_owner": runtime_owner,
                "probe": probe,
                "registry_bound": registry_bound,
                "runtime_capabilities": sorted(
                    runtime_capability_assets.get(asset_id) or []
                ),
                "policy_excluded_capabilities": sorted(
                    excluded_capability_assets.get(asset_id) or []
                ),
            }
        )

    components = dict(resolved_profile.get("component_dispositions") or {})
    for component, disposition in components.items():
        status = str((disposition or {}).get("status") or "")
        if status == "host_prerequisite" and bool((disposition or {}).get("packaged")):
            raise ValueError(
                f"host prerequisite cannot also be packaged: {profile}:{component}"
            )
    selector_bytes = json.dumps(selected, separators=(",", ":")).encode("utf-8")
    ledger_bytes = json.dumps(
        assets, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": 2,
        "profile": profile,
        "distribution": str(resolved_profile.get("distribution") or ""),
        "asset_count": len(selected),
        "selected_asset_ids": selected,
        "selector_sha256": hashlib.sha256(selector_bytes).hexdigest(),
        "asset_inventory_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "assets": assets,
        "assets_by_id": {record["asset_id"]: record for record in assets},
        "capability_dispositions": dict(
            resolved_profile.get("capability_dispositions") or {}
        ),
        "component_dispositions": components,
    }


def _normalize_capability(row: dict[str, Any]) -> dict[str, Any]:
    step = str(row.get("step") or "").strip()
    policy = RUNTIME_CAPABILITY_POLICIES.get(step)
    if policy is None:
        raise ValueError(f"unclassified runtime step: {step or '<missing>'}")

    extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
    status = str(row.get("status") or "unknown").strip().lower()
    requested = str(extra.get("requested_implementation") or step)
    effective = str(extra.get("effective_implementation") or requested)
    fallback_chain = _fallback_chain(extra)
    reason = str(extra.get("reason") or row.get("error") or status or "unknown")
    scene_id = row.get("scene_id")
    scene_ids = [str(scene_id)] if scene_id not in (None, "") else []
    raw_references = row.get("evidence_references") or extra.get(
        "evidence_references"
    )
    if isinstance(raw_references, str):
        evidence_references = [raw_references] if raw_references.strip() else []
    elif isinstance(raw_references, list):
        evidence_references = [
            str(item) for item in raw_references if str(item).strip()
        ]
    else:
        evidence_references = []
    return {
        "step": step,
        "classification": str(policy["classification"]),
        "status_surface": str(policy["status_surface"]),
        "status": status,
        "reason": reason,
        "requested_implementation": requested,
        "effective_implementation": effective,
        "fallback_chain": fallback_chain,
        "affected_scene_ids": scene_ids,
        "error": str(row.get("error") or ""),
        "evidence_references": evidence_references,
    }


def _fallback_chain(extra: dict[str, Any]) -> list[str]:
    native_retry = extra.get("native_retry_mode")
    if isinstance(native_retry, str) and native_retry.strip():
        return [native_retry.strip()]
    explicit = extra.get("fallback_chain")
    if isinstance(explicit, list):
        return [str(item) for item in explicit if str(item).strip()]
    return []


def _aggregate_capabilities(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        grouped.setdefault(str(observation["step"]), []).append(observation)

    aggregates: list[dict[str, Any]] = []
    failure_precedence = ("error", "skipped", "missing", "unknown")
    for step, rows in grouped.items():
        aggregate = dict(rows[0])
        statuses = Counter(str(row["status"]) for row in rows)
        aggregate["status_counts"] = dict(sorted(statuses.items()))
        aggregate["affected_scene_ids"] = sorted(
            {
                scene_id
                for row in rows
                for scene_id in row.get("affected_scene_ids") or []
            }
        )
        aggregate["fallback_chain"] = list(
            dict.fromkeys(
                fallback
                for row in rows
                for fallback in row.get("fallback_chain") or []
            )
        )
        aggregate["evidence_references"] = list(
            dict.fromkeys(
                reference
                for row in rows
                for reference in row.get("evidence_references") or []
            )
        )
        aggregate["observations"] = rows
        failure = next(
            (status for status in failure_precedence if statuses.get(status)),
            None,
        )
        if failure:
            aggregate["status"] = failure
            aggregate["closure_status"] = failure
            failing_row = next(row for row in rows if row["status"] == failure)
            aggregate["reason"] = failing_row["reason"]
            aggregate["error"] = failing_row["error"]
        elif any(row["closure_status"] == "ran_with_output" for row in rows):
            aggregate["status"] = "ok"
            aggregate["closure_status"] = "ran_with_output"
        elif all(
            row["closure_status"] == "ran_content_appropriate_empty" for row in rows
        ):
            aggregate["status"] = "not_applicable"
            aggregate["closure_status"] = "ran_content_appropriate_empty"
        aggregates.append(aggregate)
    return aggregates


def _closure_status(capability: dict[str, Any]) -> str:
    status = str(capability.get("status") or "unknown")
    if status in {"ok", "completed"}:
        return "ran_with_output"
    if status == "not_applicable" and capability.get("reason") in {
        "content_appropriate_empty",
        "no_text",
        "silence",
        "no_face",
        "no_ocr_text",
        "no_detected_object",
    }:
        return "ran_content_appropriate_empty"
    return status


def _summarize(capabilities: list[dict[str, Any]]) -> dict[str, int]:
    status_counts = Counter(str(row["status"]) for row in capabilities)
    required_core_failures = sum(
        1
        for row in capabilities
        if row["classification"] == "core_required" and row["status"] not in _NON_FAILURE_STATUSES
    )
    optional_rows = [
        row
        for row in capabilities
        if row["classification"]
        in {"enhancement_optional", "profile_optional", "gated_personal"}
    ]
    return {
        "capability_count": len(capabilities),
        "required_core_failures": required_core_failures,
        "optional_skips": sum(1 for row in optional_rows if row["status"] == "skipped"),
        "optional_errors": sum(1 for row in optional_rows if row["status"] == "error"),
        "recovered_fallbacks": sum(1 for row in capabilities if row["fallback_chain"]),
        "approved_fallbacks": sum(
            1
            for row in capabilities
            if row.get("closure_status") == "ran_with_approved_fallback"
        ),
        "unapproved_fallbacks": sum(
            1
            for row in capabilities
            if row.get("closure_status") == "unapproved_fallback"
        ),
        "not_applicable": int(status_counts.get("not_applicable", 0)),
    }


def _resolve_outcome(
    terminal_status: str,
    summary: dict[str, Any],
    *,
    full_coverage: bool = False,
) -> str:
    normalized = str(terminal_status).strip().lower()
    if (
        summary["required_core_failures"] > 0
        or normalized in {"failed", "blocked"}
        or full_coverage
        and int(summary.get("coverage_failures") or 0) > 0
    ):
        return "failed"
    if (
        summary["optional_skips"] > 0
        or summary["optional_errors"] > 0
        or summary["recovered_fallbacks"] > summary.get("approved_fallbacks", 0)
    ):
        return "degraded"
    return "completed"
