from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.install.prebuild_readiness import (
    LARGE_MODEL_ASSET_IDS,
    PERSONAL_ONLY_DELTA,
    REQUIRED_TRANSFORM_ASSET_IDS,
    PrebuildReadinessError,
    load_readiness_receipt,
    validate_readiness,
    write_readiness_receipt,
)


EXPECTED_VERSION = "3.0.1"


def _digest(character: str) -> str:
    return character * 64


def _valid_candidate() -> dict[str, object]:
    required_public = list(REQUIRED_TRANSFORM_ASSET_IDS)
    required_public.extend(f"public_asset_{index:02d}" for index in range(33 - len(required_public)))
    public = sorted(required_public)
    personal = sorted([*public, *PERSONAL_ONLY_DELTA])
    model_assets = sorted(required_public[:10])
    model_probe_records = [
        {
            "asset_id": asset_id,
            "probe": "fixture_loader",
            "status": "loader_contract_ready",
        }
        for asset_id in model_assets
    ]
    vault_assets = sorted([*model_assets, *LARGE_MODEL_ASSET_IDS])
    return {
        "schema": "goodq.prebuild-readiness.v1",
        "status": "candidate",
        "version": "3.0.1",
        "source": {
            "initial_commit": "a" * 40,
            "observed_commit": "a" * 40,
            "initial_tree": "b" * 40,
            "observed_tree": "b" * 40,
            "clean": True,
            "dedicated_worktree": True,
            "root_fingerprint": _digest("1"),
            "config_inventory_sha256": _digest("2"),
            "remote_alignment": {
                "behind_origin_dev": 0,
                "ahead_of_origin_dev": 15,
                "policy": "push_deferred_by_checkpoint",
            },
        },
        "profiles": {
            "PUBLIC_GPU_ENHANCED": {
                "asset_count": 33,
                "asset_ids": public,
                "selector_sha256": _digest("3"),
                "asset_inventory_sha256": _digest("4"),
            },
            "PERSONAL_AIR_GAP": {
                "asset_count": 36,
                "asset_ids": personal,
                "selector_sha256": _digest("5"),
                "asset_inventory_sha256": _digest("6"),
            },
            "personal_only_delta": list(PERSONAL_ONLY_DELTA),
            "forbidden_asset_ids": list(LARGE_MODEL_ASSET_IDS),
            "local_vlm_dispatch_present": False,
            "local_vlm_dispatch_paths": [],
            "local_vlm_status_writer_paths": [],
            "local_llm_serving_owner_present": False,
        },
        "vault": {
            "explicit": True,
            "status": "verified",
            "root_fingerprint": _digest("7"),
            "inventory_sha256": _digest("8"),
            "verified_asset_ids": vault_assets,
            "preserved_large_model_asset_ids": list(LARGE_MODEL_ASSET_IDS),
            "seals": [
                {
                    "asset_id": asset_id,
                    "status": "verified",
                    "manifest_sha256": _digest("9"),
                }
                for asset_id in vault_assets
            ],
        },
        "transformations": {
            "status": "feasible",
            "asset_ids": list(REQUIRED_TRANSFORM_ASSET_IDS),
            "records": [
                {"asset_id": asset_id, "status": "safe_load_feasible"}
                for asset_id in REQUIRED_TRANSFORM_ASSET_IDS
            ],
        },
        "model_load_probes": {
            "status": "prebuild_feasibility_passed",
            "installed_inference_status": "required_after_build",
            "expected_asset_ids": model_assets,
            "records": model_probe_records,
        },
        "wsl": {
            "status": "passed",
            "distro": "Ubuntu-22.04",
            "wsl_version": 2,
            "workspace_fingerprint": _digest("4"),
            "constraints_sha256": _digest("5"),
            "evidence_sha256": _digest("6"),
            "expected_versions": {
                "torch": "2.5.1+cu121",
                "torchvision": "0.20.1+cu121",
                "torchaudio": "2.5.1+cu121",
                "pyannote.audio": "3.3.2",
                "faster-whisper": "1.2.1",
                "transformers": "4.43.3",
                "tokenizers": "0.19.1",
                "safetensors": "0.7.0",
            },
            "detected_versions": {
                "torch": "2.5.1+cu121",
                "torchvision": "0.20.1+cu121",
                "torchaudio": "2.5.1+cu121",
                "pyannote.audio": "3.3.2",
                "faster-whisper": "1.2.1",
                "transformers": "4.43.3",
                "tokenizers": "0.19.1",
                "safetensors": "0.7.0",
            },
            "versions_match_constraints": True,
            "required_checks": {
                "workspace": True,
                "transcription": True,
                "process_import": True,
                "abi": True,
                "diarization": True,
                "wav2vec_enrichment": True,
                "clap_handoff": True,
                "gpu": True,
            },
            "allowed_warnings": ["torchcodec_unavailable"],
            "warnings": ["torchcodec_unavailable"],
        },
        "fixture_pack": {
            "status": "verified",
            "root_fingerprint": _digest("a"),
            "manifest_sha256": _digest("b"),
            "fixture_pack_sha256": _digest("c"),
            "members_sha256": _digest("d"),
            "member_count": 6,
        },
        "turboquant": {
            "evidence_sha256": _digest("7"),
            "release_configuration": {"active": False, "shadow": False},
            "witness_configuration": {"active": False, "shadow": False},
            "host_observation": {
                "active": False,
                "shadow": True,
                "policy": "superseded_existing_host_not_a_build_input",
                "runtime_config_root_fingerprint": _digest("8"),
                "runtime_config_inventory_sha256": _digest("9"),
                "local_config_present": True,
            },
            "runtime_config": {
                "root_fingerprint": _digest("8"),
                "inventory_sha256": _digest("9"),
                "local_config_present": True,
            },
            "database_sidecar_counts": {
                "tq_indices": 0,
                "tq_norm": 0,
                "tq_qjl_sign": 0,
                "tq_norm_residual": 0,
            },
        },
        "private_build_inputs": {
            "status": "verified",
            "root_fingerprint": _digest("0"),
            "cache_root_fingerprint": _digest("1"),
            "cache_size_bytes": 10_000,
            "inventory_sha256": _digest("2"),
            "signing_key_present": True,
            "signing_key_matches_launcher": True,
            "signing_public_key_sha256": _digest("3"),
            "dependency_gates": [
                {"profile": profile, "mode": mode, "status": "passed"}
                for profile in ("PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP")
                for mode in ("verify", "audit")
            ],
        },
        "disk": {
            "required_bytes": 100,
            "free_bytes": 1_000,
            "estimate_sha256": _digest("e"),
        },
        "future_output": {
            "root_fingerprint": _digest("f"),
            "exists": False,
            "empty": True,
        },
        "boundaries": {
            "installer_build_started": False,
            "installer_installed": False,
            "memory_reset": False,
            "reingestion_started": False,
            "push_tag_or_publication": False,
        },
    }


def _expect_failure(candidate: dict[str, object], message: str) -> None:
    with pytest.raises(PrebuildReadinessError, match=message):
        validate_readiness(candidate, expected_version=EXPECTED_VERSION)


def test_readiness_rejects_a_dirty_source() -> None:
    candidate = _valid_candidate()
    candidate["source"]["clean"] = False
    _expect_failure(candidate, "source tree is dirty")


@pytest.mark.parametrize("field", ["observed_commit", "observed_tree"])
def test_readiness_rejects_source_identity_drift(field: str) -> None:
    candidate = _valid_candidate()
    candidate["source"][field] = "0" * 40
    _expect_failure(candidate, "source identity drift")


def test_readiness_requires_a_dedicated_source_worktree() -> None:
    candidate = _valid_candidate()
    candidate["source"]["dedicated_worktree"] = False
    _expect_failure(candidate, "dedicated source worktree")


def test_readiness_rejects_a_missing_explicit_vault_root() -> None:
    candidate = _valid_candidate()
    candidate["vault"]["explicit"] = False
    _expect_failure(candidate, "explicit asset vault")


def test_readiness_rejects_vault_seal_drift() -> None:
    candidate = _valid_candidate()
    candidate["vault"]["seals"][0]["status"] = "drifted"
    _expect_failure(candidate, "vault seal verification")


def test_readiness_requires_all_five_preserved_large_model_seals() -> None:
    candidate = _valid_candidate()
    candidate["vault"]["preserved_large_model_asset_ids"].pop()
    _expect_failure(candidate, "preserved large-model seal set")


def test_readiness_rejects_wrong_profile_counts() -> None:
    candidate = _valid_candidate()
    candidate["profiles"]["PUBLIC_GPU_ENHANCED"]["asset_count"] = 32
    _expect_failure(candidate, "Public GPU profile must contain exactly 33")


def test_readiness_rejects_a_forbidden_large_model_selection() -> None:
    candidate = _valid_candidate()
    candidate["profiles"]["PUBLIC_GPU_ENHANCED"]["asset_ids"][0] = LARGE_MODEL_ASSET_IDS[0]
    candidate["profiles"]["PUBLIC_GPU_ENHANCED"]["asset_ids"].sort()
    _expect_failure(candidate, "forbidden large-model asset")


def test_readiness_rejects_a_local_vlm_dispatch() -> None:
    candidate = _valid_candidate()
    candidate["profiles"]["local_vlm_dispatch_present"] = True
    _expect_failure(candidate, "local VLM must remain policy-excluded")


def test_readiness_rejects_a_local_vlm_status_writer() -> None:
    candidate = _valid_candidate()
    candidate["profiles"]["local_vlm_status_writer_paths"] = ["steps/local_vlm.py"]
    _expect_failure(candidate, "local VLM runner or status writer")


def test_readiness_rejects_a_failed_wsl_prerequisite() -> None:
    candidate = _valid_candidate()
    candidate["wsl"]["required_checks"]["clap_handoff"] = False
    _expect_failure(candidate, "WSL prerequisite check failed")


def test_readiness_rejects_an_unclassified_wsl_warning() -> None:
    candidate = _valid_candidate()
    candidate["wsl"]["warnings"].append("unknown_warning")
    _expect_failure(candidate, "unapproved WSL warning")


def test_readiness_rejects_wsl_package_version_drift() -> None:
    candidate = _valid_candidate()
    candidate["wsl"]["detected_versions"]["transformers"] = "5.0.0"
    _expect_failure(candidate, "WSL package versions do not match")


def test_readiness_rejects_fixture_drift() -> None:
    candidate = _valid_candidate()
    candidate["fixture_pack"]["status"] = "drifted"
    _expect_failure(candidate, "fixture pack")


@pytest.mark.parametrize("field", ["active", "shadow"])
def test_readiness_rejects_enabled_turboquant_release_configuration(field: str) -> None:
    candidate = _valid_candidate()
    candidate["turboquant"]["release_configuration"][field] = True
    _expect_failure(candidate, "TurboQuant release configuration")


def test_readiness_rejects_nonzero_database_sidecars() -> None:
    candidate = _valid_candidate()
    candidate["turboquant"]["database_sidecar_counts"]["tq_norm"] = 1
    _expect_failure(candidate, "TurboQuant database sidecars")


def test_readiness_rejects_an_unbound_active_runtime_config() -> None:
    candidate = _valid_candidate()
    candidate["turboquant"]["host_observation"][
        "runtime_config_inventory_sha256"
    ] = _digest("0")
    _expect_failure(candidate, "current host TurboQuant state is not config-bound")


def test_readiness_rejects_an_incomplete_private_cache_gate() -> None:
    candidate = _valid_candidate()
    candidate["private_build_inputs"]["dependency_gates"].pop()
    _expect_failure(candidate, "private dependency cache gates are incomplete")


def test_readiness_rejects_a_signing_key_mismatch() -> None:
    candidate = _valid_candidate()
    candidate["private_build_inputs"]["signing_key_matches_launcher"] = False
    _expect_failure(candidate, "private signing key is not bound")


def test_readiness_rejects_a_missing_model_probe() -> None:
    candidate = _valid_candidate()
    candidate["model_load_probes"]["records"].pop()
    _expect_failure(candidate, "model-load probe coverage")


def test_readiness_rejects_an_infeasible_transformation() -> None:
    candidate = _valid_candidate()
    candidate["transformations"]["records"][0]["status"] = "failed"
    _expect_failure(candidate, "safetensors transformation")


def test_readiness_rejects_insufficient_disk() -> None:
    candidate = _valid_candidate()
    candidate["disk"]["free_bytes"] = 99
    _expect_failure(candidate, "insufficient disk space")


def test_readiness_rejects_a_reused_output_root() -> None:
    candidate = _valid_candidate()
    candidate["future_output"].update({"exists": True, "empty": False})
    _expect_failure(candidate, "future output root is not unused")


def test_readiness_rejects_a_version_mismatch() -> None:
    candidate = _valid_candidate()
    candidate["version"] = "3.0.0"
    _expect_failure(candidate, "release version must be 3.0.1")


def test_readiness_rejects_a_crossed_release_boundary() -> None:
    candidate = _valid_candidate()
    candidate["boundaries"]["installer_build_started"] = True
    _expect_failure(candidate, "crosses an unapproved release boundary")


def test_terminal_receipt_round_trip_is_external_and_hash_bound(tmp_path: Path) -> None:
    repo_root = tmp_path / "source"
    repo_root.mkdir()
    (repo_root / "goodq_version.py").write_text(
        f'GOODQ_VERSION = "{EXPECTED_VERSION}"\n', encoding="utf-8"
    )
    receipt_path = tmp_path / "evidence" / "prebuild-readiness.json"

    written = write_readiness_receipt(
        _valid_candidate(),
        receipt_path=receipt_path,
        repo_root=repo_root,
    )
    loaded = load_readiness_receipt(written, expected_version=EXPECTED_VERSION)

    assert loaded["status"] == "passed"
    assert loaded["schema"] == "goodq.prebuild-readiness.v1"
    assert loaded["version"] == "3.0.1"
    validate_readiness(loaded, expected_version=EXPECTED_VERSION)


def test_terminal_receipt_may_not_be_written_inside_source_control(tmp_path: Path) -> None:
    repo_root = tmp_path / "source"
    repo_root.mkdir()
    (repo_root / "goodq_version.py").write_text(
        f'GOODQ_VERSION = "{EXPECTED_VERSION}"\n', encoding="utf-8"
    )

    with pytest.raises(PrebuildReadinessError, match="external to source control"):
        write_readiness_receipt(
            _valid_candidate(),
            receipt_path=repo_root / "prebuild-readiness.json",
            repo_root=repo_root,
        )
