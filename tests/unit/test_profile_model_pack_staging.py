"""Focused integrity contracts for the generic installer profile payload stager."""

from __future__ import annotations

import hashlib
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = spec_from_file_location(
    "stage_profile_model_packs",
    REPO_ROOT / "scripts" / "install" / "stage_profile_model_packs.py",
)
assert _SPEC and _SPEC.loader
stage_profile_model_packs = module_from_spec(_SPEC)
_SPEC.loader.exec_module(stage_profile_model_packs)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_staged_copy_must_match_every_sealed_source_member(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    source = snapshot / "source"
    staged = tmp_path / "staged"
    source.mkdir(parents=True)
    staged.mkdir()
    payload = b"sealed model bytes\n"
    (source / "model.bin").write_bytes(payload)
    (staged / "model.bin").write_bytes(payload)
    (snapshot / "source-manifest.json").write_text(
        json.dumps(
            {
                "members": [
                    {"path": "model.bin", "size_bytes": len(payload), "sha256": _sha256(payload)}
                ]
            }
        ),
        encoding="utf-8",
    )

    stage_profile_model_packs._verify_copied_source(snapshot, staged, "sample")

    (staged / "model.bin").write_bytes(b"tampered")
    with pytest.raises(stage_profile_model_packs.ProfilePackStageError, match="size mismatch"):
        stage_profile_model_packs._verify_copied_source(snapshot, staged, "sample")


def test_stage_receipt_records_cpu_profile_payload_membership() -> None:
    catalog = stage_profile_model_packs._read_yaml(REPO_ROOT / "configs" / "offline_asset_catalog.yaml")
    profiles = stage_profile_model_packs._read_yaml(REPO_ROOT / "configs" / "installer_profile_contract.yaml")

    selected = stage_profile_model_packs.resolve_profile_assets(
        catalog, profiles, "PUBLIC_CPU_BASELINE"
    )
    assert "faster_whisper_small" in selected
    assert "opencv_nanodet" in selected
    assert "vader_lexicon" in selected
