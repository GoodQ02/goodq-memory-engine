from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


RUNTIME_PROFILES = {"isolated", "live", "golden"}
RUNTIME_EVIDENCE_MANIFEST = Path(__file__).with_name("runtime_evidence_manifest.json")


def require_live_profile(profile: str, purpose: str) -> None:
    """Skips intentional live tests unless a live evidence profile was selected."""
    if profile not in RUNTIME_PROFILES:
        pytest.fail(f"Unknown GoodQ test profile: {profile!r}", pytrace=False)
    if profile == "isolated":
        pytest.skip(f"{purpose} requires --goodq-test-profile=live or golden")


def require_runtime_evidence(profile: str, available: bool, reason: str) -> None:
    """Missing required evidence is a failure in live and golden profiles."""
    if available:
        return
    if profile in {"live", "golden"}:
        pytest.fail(f"[{profile}] required runtime evidence unavailable: {reason}", pytrace=False)
    pytest.skip(reason)


def load_runtime_evidence_manifest() -> dict:
    """Load the checked-in golden runtime evidence authority."""
    try:
        manifest = json.loads(RUNTIME_EVIDENCE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(
            f"Runtime evidence manifest is unavailable or malformed: {type(exc).__name__}",
            pytrace=False,
        )
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("golden"), dict):
        pytest.fail("Runtime evidence manifest has an unsupported schema", pytrace=False)
    return manifest


def selected_runtime_epoch(profile: str, explicit_epoch: str | None = None) -> str:
    """Resolve the requested epoch and enforce the pinned golden authority."""
    require_live_profile(profile, "runtime epoch selection")
    epoch_id = (explicit_epoch or os.environ.get("GOODQ_TEST_EPOCH", "")).strip()
    require_runtime_evidence(profile, bool(epoch_id), "GOODQ_TEST_EPOCH is not set")
    if profile == "golden":
        expected = load_runtime_evidence_manifest()["golden"].get("epoch_id", "")
        require_runtime_evidence(
            profile,
            epoch_id == expected,
            f"golden epoch mismatch: expected {expected!r}, got {epoch_id!r}",
        )
    return epoch_id


def expected_epoch_collections(profile: str, epoch_id: str | None = None) -> dict[str, str]:
    """Return exact modality-to-collection names for the selected epoch."""
    selected = selected_runtime_epoch(profile, epoch_id)
    if profile == "golden":
        collections = load_runtime_evidence_manifest()["golden"].get("qdrant_collections")
        require_runtime_evidence(
            profile,
            isinstance(collections, dict) and bool(collections),
            "golden Qdrant collection authority is missing",
        )
        return dict(collections)
    return {
        modality: f"goodq_{modality}_{selected}"
        for modality in ("audio", "clip", "dino", "text")
    }
