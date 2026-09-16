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


def test_staged_copy_reports_progress_for_large_source_members(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    payload = b"sealed-model" * 1024
    (source / "model.bin").write_bytes(payload)
    updates: list[str] = []

    stage_profile_model_packs._copy_source(
        source,
        destination,
        asset_id="large_model",
        progress=updates.append,
        chunk_bytes=128,
        heartbeat_seconds=0,
    )

    assert (destination / "model.bin").read_bytes() == payload
    assert any("copy plan: large_model" in update for update in updates)
    assert any("copy heartbeat: large_model" in update for update in updates)
    assert any("copy complete: large_model" in update for update in updates)


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


class _FakeTensor:
    shape = (2, 2)
    dtype = "float32"

    def detach(self):
        return self

    def cpu(self):
        return self

    def contiguous(self):
        return self

    def clone(self):
        return _FakeTensor()


def _fake_safetensors_tools(calls: list[dict[str, object]]):
    class FakeTorch:
        __version__ = "2.5.1+cu121"

        @staticmethod
        def load(path, **kwargs):
            calls.append({"operation": "load", "path": Path(path), **kwargs})
            return {"weight": _FakeTensor()}

    def save_file(state_dict, path):
        calls.append(
            {
                "operation": "save",
                "path": Path(path),
                "keys": sorted(state_dict),
            }
        )
        Path(path).write_bytes(b"safe-transformed-weights")

    def load_file(path, *, device):
        calls.append(
            {"operation": "verify", "path": Path(path), "device": device}
        )
        return {"weight": _FakeTensor()}

    return FakeTorch, save_file, load_file


def test_required_safetensors_transform_uses_safe_loading_and_records_provenance(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "blip"
    runtime_root.mkdir()
    source_bytes = b"sealed-pytorch-state-dict"
    (runtime_root / "pytorch_model.bin").write_bytes(source_bytes)
    calls: list[dict[str, object]] = []

    provenance = stage_profile_model_packs._transform_required_safetensors(
        "blip_caption",
        runtime_root,
        tool_loader=lambda: _fake_safetensors_tools(calls),
    )

    assert (runtime_root / "model.safetensors").read_bytes() == b"safe-transformed-weights"
    load_call = next(call for call in calls if call["operation"] == "load")
    assert load_call["weights_only"] is True
    assert load_call["map_location"] == "cpu"
    assert provenance == [
        {
            "type": "pytorch_state_dict_to_safetensors",
            "source_path": "pytorch_model.bin",
            "source_sha256": _sha256(source_bytes),
            "target_path": "model.safetensors",
            "target_sha256": _sha256(b"safe-transformed-weights"),
            "torch_version": "2.5.1+cu121",
            "safe_load": "weights_only_true",
        }
    ]


def test_required_safetensors_transform_fails_when_tooling_is_missing(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "clap"
    runtime_root.mkdir()
    (runtime_root / "pytorch_model.bin").write_bytes(b"sealed")

    def missing_tools():
        raise ImportError("safetensors unavailable")

    with pytest.raises(
        stage_profile_model_packs.ProfilePackStageError,
        match="required safetensors tooling is unavailable",
    ):
        stage_profile_model_packs._transform_required_safetensors(
            "clap_audio",
            runtime_root,
            tool_loader=missing_tools,
        )


def test_required_safetensors_transform_rejects_unsafe_or_failed_conversion(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "clip"
    runtime_root.mkdir()
    (runtime_root / "pytorch_model.bin").write_bytes(b"unsafe-pickle")

    class UnsafeTorch:
        __version__ = "2.5.1+cu121"

        @staticmethod
        def load(path, **kwargs):
            assert kwargs["weights_only"] is True
            raise RuntimeError("unsafe global in pickle")

    with pytest.raises(
        stage_profile_model_packs.ProfilePackStageError,
        match="required safetensors transformation failed",
    ):
        stage_profile_model_packs._transform_required_safetensors(
            "clip_vit",
            runtime_root,
            tool_loader=lambda: (UnsafeTorch, lambda *_: None, lambda *_: {}),
        )
    assert not (runtime_root / "model.safetensors").exists()


def test_required_safetensors_transform_rejects_missing_source_weight(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "caption"
    runtime_root.mkdir()

    with pytest.raises(
        stage_profile_model_packs.ProfilePackStageError,
        match="required transformation source is missing",
    ):
        stage_profile_model_packs._transform_required_safetensors(
            "vit_gpt2_caption",
            runtime_root,
            tool_loader=lambda: _fake_safetensors_tools([]),
        )


def test_required_safetensors_transform_set_is_exact() -> None:
    assert stage_profile_model_packs.REQUIRED_SAFETENSORS_TRANSFORMS == {
        "blip_caption": ("pytorch_model.bin", "model.safetensors"),
        "clap_audio": ("pytorch_model.bin", "model.safetensors"),
        "clip_vit": ("pytorch_model.bin", "model.safetensors"),
        "hubert_emotion": ("pytorch_model.bin", "model.safetensors"),
        "vit_gpt2_caption": ("pytorch_model.bin", "model.safetensors"),
    }


def test_model_member_manifest_binds_source_and_transformed_members(
    tmp_path: Path,
) -> None:
    staging_root = tmp_path / "models"
    runtime_root = staging_root / "hub" / "model"
    runtime_root.mkdir(parents=True)
    source_bytes = b"sealed-source"
    transformed_bytes = b"transformed-safe"
    (runtime_root / "config.json").write_bytes(source_bytes)
    (runtime_root / "model.safetensors").write_bytes(transformed_bytes)
    payloads = [
        {
            "asset_id": "blip_caption",
            "runtime_path": "hub/model",
            "source_manifest_sha256": "a" * 64,
        }
    ]
    source_members = {
        "blip_caption": {
            "config.json": {
                "path": "config.json",
                "size_bytes": len(source_bytes),
                "sha256": _sha256(source_bytes),
            },
            "pytorch_model.bin": {
                "path": "pytorch_model.bin",
                "size_bytes": 10,
                "sha256": "b" * 64,
            },
        }
    }
    transformations = {
        "blip_caption": [
            {
                "type": "pytorch_state_dict_to_safetensors",
                "source_path": "pytorch_model.bin",
                "source_sha256": "b" * 64,
                "target_path": "model.safetensors",
                "target_sha256": _sha256(transformed_bytes),
                "torch_version": "2.5.1+cu121",
                "safe_load": "weights_only_true",
            }
        ]
    }

    manifest = stage_profile_model_packs._build_model_member_manifest(
        staging_root=staging_root,
        profile="PUBLIC_GPU_ENHANCED",
        payloads=payloads,
        source_members_by_asset=source_members,
        transformations_by_asset=transformations,
    )

    assert manifest["schema_version"] == 2
    assert manifest["member_count"] == 2
    assert [member["path"] for member in manifest["members"]] == [
        "hub/model/config.json",
        "hub/model/model.safetensors",
    ]
    assert manifest["members"][0]["provenance"]["type"] == "sealed_source_copy"
    assert (
        manifest["members"][1]["provenance"]["type"]
        == "pytorch_state_dict_to_safetensors"
    )
    stage_profile_model_packs._verify_model_member_manifest(staging_root, manifest)

    (runtime_root / "config.json").write_bytes(b"drifted")
    with pytest.raises(
        stage_profile_model_packs.ProfilePackStageError,
        match="member (size|hash) mismatch",
    ):
        stage_profile_model_packs._verify_model_member_manifest(staging_root, manifest)


def test_model_member_manifest_rejects_orphan_staged_member(tmp_path: Path) -> None:
    staging_root = tmp_path / "models"
    runtime_root = staging_root / "hub" / "model"
    runtime_root.mkdir(parents=True)
    (runtime_root / "config.json").write_bytes(b"sealed-source")
    (runtime_root / "orphan.bin").write_bytes(b"orphan")

    with pytest.raises(
        stage_profile_model_packs.ProfilePackStageError,
        match="orphan staged member",
    ):
        stage_profile_model_packs._build_model_member_manifest(
            staging_root=staging_root,
            profile="PUBLIC_GPU_ENHANCED",
            payloads=[
                {
                    "asset_id": "blip_caption",
                    "runtime_path": "hub/model",
                    "source_manifest_sha256": "a" * 64,
                }
            ],
            source_members_by_asset={
                "blip_caption": {
                    "config.json": {
                        "path": "config.json",
                        "size_bytes": 13,
                        "sha256": _sha256(b"sealed-source"),
                    }
                }
            },
            transformations_by_asset={},
        )
