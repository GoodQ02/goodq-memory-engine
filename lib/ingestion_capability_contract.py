"""Canonical, pure capability outcome contract for ingestion evidence."""

from __future__ import annotations

from collections import Counter
from typing import Any


CAPABILITY_SCHEMA_VERSION = 1

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
    "audio_emotion": {"classification": "enhancement_optional", "status_surface": "emotion_meta", "asset_ids": ["hubert_emotion", "wav2vec2_emotion"]},
    "sentiment": {"classification": "enhancement_optional", "status_surface": "sentiment_meta", "asset_ids": ["sentiment_model", "vader_lexicon"]},
    "emotion_classify": {"classification": "enhancement_optional", "status_surface": "emotion_classify_meta", "asset_ids": ["emotion_classify_model"]},
    "audio_embed_clap": {"classification": "enhancement_optional", "status_surface": "clap_meta", "asset_ids": ["clap_audio"]},
    "local_vlm": {"classification": "profile_optional", "status_surface": "local_vlm_meta", "asset_ids": ["qwen2_5_vl_7b", "qwen2_5_vl_3b"]},
}

_NON_FAILURE_STATUSES = {"ok", "completed", "not_applicable"}
_RUNTIME_CLASSIFICATIONS = {"core_required", "enhancement_optional", "profile_optional", "gated_personal", "excluded"}


def build_capability_receipt(
    *,
    run_id: str,
    profile: str,
    terminal_status: str,
    step_rows: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    evidence_paths: dict[str, str],
) -> dict[str, Any]:
    """Build a receipt solely from already-structured runtime evidence."""

    capabilities = [_normalize_capability(row) for row in step_rows]
    capabilities_by_step = {row["step"]: row for row in capabilities}
    summary = _summarize(capabilities)
    outcome = _resolve_outcome(terminal_status, summary)
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "run_id": str(run_id),
        "profile": str(profile),
        "terminal_status": str(terminal_status),
        "outcome": outcome,
        "summary": summary,
        "capabilities": capabilities,
        "capabilities_by_step": capabilities_by_step,
        "warnings": list(warnings),
        "scene_count": len(scenes),
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
        "schema_version": CAPABILITY_SCHEMA_VERSION,
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

    def _packs(name: str, seen: set[str]) -> list[str]:
        if name in seen:
            raise ValueError(f"profile inheritance cycle: {name}")
        record = profiles.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"unknown installer profile: {name}")
        parent = record.get("extends")
        inherited = _packs(str(parent), seen | {name}) if parent else []
        return inherited + [str(pack) for pack in record.get("include_packs") or []]

    profile_record = profiles.get(profile)
    if not isinstance(profile_record, dict):
        raise ValueError(f"unknown installer profile: {profile}")
    distribution = str(profile_record.get("distribution") or "")
    pack_scopes = set(_packs(profile, set()))
    excluded_assets = {str(asset_id) for asset_id in profile_record.get("exclude_assets") or []}
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
    }


def _fallback_chain(extra: dict[str, Any]) -> list[str]:
    native_retry = extra.get("native_retry_mode")
    if isinstance(native_retry, str) and native_retry.strip():
        return [native_retry.strip()]
    explicit = extra.get("fallback_chain")
    if isinstance(explicit, list):
        return [str(item) for item in explicit if str(item).strip()]
    return []


def _summarize(capabilities: list[dict[str, Any]]) -> dict[str, int]:
    status_counts = Counter(str(row["status"]) for row in capabilities)
    required_core_failures = sum(
        1
        for row in capabilities
        if row["classification"] == "core_required" and row["status"] not in _NON_FAILURE_STATUSES
    )
    optional_rows = [row for row in capabilities if row["classification"] == "enhancement_optional"]
    return {
        "capability_count": len(capabilities),
        "required_core_failures": required_core_failures,
        "optional_skips": sum(1 for row in optional_rows if row["status"] == "skipped"),
        "optional_errors": sum(1 for row in optional_rows if row["status"] == "error"),
        "recovered_fallbacks": sum(1 for row in capabilities if row["fallback_chain"]),
        "not_applicable": int(status_counts.get("not_applicable", 0)),
    }


def _resolve_outcome(terminal_status: str, summary: dict[str, int]) -> str:
    normalized = str(terminal_status).strip().lower()
    if summary["required_core_failures"] > 0 or normalized in {"failed", "blocked"}:
        return "failed"
    if (
        summary["optional_skips"] > 0
        or summary["optional_errors"] > 0
        or summary["recovered_fallbacks"] > 0
    ):
        return "degraded"
    return "completed"
