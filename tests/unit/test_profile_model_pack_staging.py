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

_MATRIX_SPEC = spec_from_file_location(
    "build_capability_matrix",
    REPO_ROOT / "scripts" / "install" / "build_capability_matrix.py",
)
assert _MATRIX_SPEC and _MATRIX_SPEC.loader
build_capability_matrix_script = module_from_spec(_MATRIX_SPEC)
_MATRIX_SPEC.loader.exec_module(build_capability_matrix_script)


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


def test_cpu_profile_selects_only_runtime_registered_models() -> None:
    catalog = stage_profile_model_packs._read_yaml(REPO_ROOT / "configs" / "offline_asset_catalog.yaml")
    profiles = stage_profile_model_packs._read_yaml(REPO_ROOT / "configs" / "installer_profile_contract.yaml")
    registry = stage_profile_model_packs._registry_records(
        stage_profile_model_packs._read_yaml(REPO_ROOT / "configs" / "model_registry.yaml")
    )

    selected = stage_profile_model_packs.resolve_profile_assets(
        catalog, profiles, "PUBLIC_CPU_BASELINE"
    )
    assert "faster_whisper_small" in selected
    assert "opencv_nanodet" in selected
    assert "vader_lexicon" in selected
    assert "dinov2" in selected
    assert "dinov2_base" not in selected
    selected_models = {
        asset_id
        for asset_id in selected
        if (catalog.get("assets") or {}).get(asset_id, {}).get("kind") == "model"
    }
    assert selected_models <= set(registry)


def test_profile_preflight_rejects_selected_model_without_runtime_registry() -> None:
    with pytest.raises(ValueError, match="selected model lacks runtime registry"):
        build_capability_matrix_script._validate_profile_model_bindings(
            catalog={"assets": {"orphan": {"kind": "model"}}},
            profile_selections={"PUBLIC_CPU_BASELINE": ["orphan"]},
            registry={},
        )
