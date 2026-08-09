"""Canonical, pure capability outcome contract for ingestion evidence."""

from __future__ import annotations

from collections import Counter
from typing import Any


CAPABILITY_SCHEMA_VERSION = 1

RUNTIME_CAPABILITY_POLICIES: dict[str, dict[str, Any]] = {
    "audio_transcribe_local": {
        "classification": "core_required",
        "status_surface": "transcript_meta",
    },
    "image_ocr": {
        "classification": "enhancement_optional",
        "status_surface": "ocr_meta",
    },
    "object_detect": {
        "classification": "enhancement_optional",
        "status_surface": "object_meta",
    },
    "audio_embed_clap": {
        "classification": "enhancement_optional",
        "status_surface": "clap_meta",
    },
    "local_vlm": {
        "classification": "profile_optional",
        "status_surface": "local_vlm_meta",
    },
}

_NON_FAILURE_STATUSES = {"ok", "completed", "not_applicable"}


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
