from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from lib import ingestion_capability_contract as capability_contract

from lib.ingestion_capability_contract import (
    build_capability_matrix,
    build_capability_receipt,
    resolve_profile_assets,
    validate_profile_selection,
)


def test_optional_skip_is_degraded_not_core_failure() -> None:
    receipt = build_capability_receipt(
        run_id="run-1",
        profile="PUBLIC_CPU_BASELINE",
        terminal_status="completed",
        step_rows=[
            {
                "step": "image_ocr",
                "status": "skipped",
                "extra": {"optional": True, "reason": "dependency_missing"},
            },
            {"step": "audio_transcribe_local", "status": "ok"},
        ],
        warnings=[],
        scenes=[],
        evidence_paths={},
    )

    assert receipt["outcome"] == "degraded"
    assert receipt["summary"]["required_core_failures"] == 0
    assert receipt["capabilities_by_step"]["image_ocr"]["classification"] == "enhancement_optional"


def test_profile_optional_error_is_degraded_outside_release_mode() -> None:
    receipt = build_capability_receipt(
        run_id="run-profile-optional",
        profile="PERSONAL_AIR_GAP",
        terminal_status="completed",
        step_rows=[
            {
                "step": "audio_wav2vec2_enrichment",
                "status": "error",
                "error": "embedding missing",
            }
        ],
        warnings=[],
        scenes=[],
        evidence_paths={},
    )

    assert receipt["outcome"] == "degraded"
    assert receipt["summary"]["optional_errors"] == 1


def test_core_transcription_failure_is_failed() -> None:
    receipt = build_capability_receipt(
        run_id="run-2",
        profile="PUBLIC_CPU_BASELINE",
        terminal_status="failed",
        step_rows=[
            {
                "step": "audio_transcribe_local",
                "status": "error",
                "error": "engine unavailable",
            }
        ],
        warnings=[],
        scenes=[],
        evidence_paths={},
    )

    assert receipt["outcome"] == "failed"
    assert receipt["summary"]["required_core_failures"] == 1


def test_gpu_cpu_fallback_preserves_both_implementations() -> None:
    receipt = build_capability_receipt(
        run_id="run-3",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[
            {
                "step": "object_detect",
                "status": "ok",
                "extra": {
                    "native_retry_mode": "cpu_fallback",
                    "requested_implementation": "opencv_yolox_gpu",
                    "effective_implementation": "opencv_nanodet_cpu",
                    "reason": "gpu_native_crash",
                },
            }
        ],
        warnings=[],
        scenes=[],
        evidence_paths={},
    )

    capability = receipt["capabilities_by_step"]["object_detect"]
    assert receipt["outcome"] == "degraded"
    assert capability["requested_implementation"] == "opencv_yolox_gpu"
    assert capability["effective_implementation"] == "opencv_nanodet_cpu"
    assert capability["fallback_chain"] == ["cpu_fallback"]


def test_profile_exclusion_is_not_applicable_not_skipped() -> None:
    receipt = build_capability_receipt(
        run_id="run-4",
        profile="PUBLIC_CPU_BASELINE",
        terminal_status="completed",
        step_rows=[
            {
                "step": "local_vlm",
                "status": "not_applicable",
                "extra": {"reason": "profile_excluded"},
            }
        ],
        warnings=[],
        scenes=[],
        evidence_paths={},
    )

    capability = receipt["capabilities_by_step"]["local_vlm"]
    assert receipt["outcome"] == "completed"
    assert capability["status"] == "not_applicable"
    assert capability["classification"] == "profile_optional"


def test_unknown_runtime_step_is_rejected() -> None:
    with pytest.raises(ValueError, match="unclassified runtime step"):
        build_capability_receipt(
            run_id="run-5",
            profile="PUBLIC_CPU_BASELINE",
            terminal_status="completed",
            step_rows=[{"step": "unknown_step", "status": "ok"}],
            warnings=[],
            scenes=[],
            evidence_paths={},
        )


def test_full_coverage_missing_expected_capability_is_not_observed_and_failed() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-1",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={"step_runs": "step_runs.jsonl"},
        expected_capabilities={
            "audio_transcribe_local": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "faster_whisper_medium",
                "status_surface": "transcript_meta",
                "asset_ids": ["faster_whisper_medium"],
                "content_applicability": "audio_present",
                "fallback_policy": "none",
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    assert receipt["schema_version"] == 2
    assert receipt["outcome"] == "failed"
    assert receipt["summary"]["missing_expected"] == 1
    assert receipt["capabilities_by_step"]["audio_transcribe_local"]["closure_status"] == "not_observed"


def test_full_coverage_aggregates_all_scene_rows_instead_of_last_row_wins() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-2",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[
            {
                "step": "object_detect",
                "scene_id": "scene-error",
                "status": "error",
                "error": "model failed",
            },
            {
                "step": "object_detect",
                "scene_id": "scene-ok",
                "status": "ok",
            },
        ],
        warnings=[],
        scenes=[{"scene_id": "scene-error"}, {"scene_id": "scene-ok"}],
        evidence_paths={},
        expected_capabilities={
            "object_detect": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "opencv",
                "status_surface": "object_meta",
                "asset_ids": ["opencv_nanodet", "opencv_yolox"],
                "content_applicability": "video_present",
                "fallback_policy": "none",
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    capability = receipt["capabilities_by_step"]["object_detect"]
    assert capability["status_counts"] == {"error": 1, "ok": 1}
    assert capability["affected_scene_ids"] == ["scene-error", "scene-ok"]
    assert capability["closure_status"] == "error"
    assert receipt["outcome"] == "failed"


def test_full_coverage_malformed_current_run_evidence_fails_closure() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-3",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[{"step": "audio_transcribe_local", "status": "ok"}],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={"step_runs": "step_runs.jsonl"},
        expected_capabilities={
            "audio_transcribe_local": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "faster_whisper_medium",
                "status_surface": "transcript_meta",
                "asset_ids": ["faster_whisper_medium"],
                "content_applicability": "audio_present",
                "fallback_policy": "none",
            }
        },
        malformed_row_count=1,
        input_count=1,
        full_coverage=True,
    )

    assert receipt["summary"]["malformed_rows"] == 1
    assert receipt["summary"]["coverage_failures"] == 1
    assert receipt["outcome"] == "failed"


def test_full_coverage_zero_input_run_cannot_complete() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-4",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[],
        warnings=[],
        scenes=[],
        evidence_paths={},
        expected_capabilities={},
        malformed_row_count=0,
        input_count=0,
        full_coverage=True,
    )

    assert receipt["summary"]["input_count"] == 0
    assert receipt["summary"]["coverage_failures"] == 1
    assert receipt["outcome"] == "failed"


def test_full_coverage_synthesizes_only_declared_policy_exclusions() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-5",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={},
        expected_capabilities={
            "local_vlm": {
                "disposition": "policy_excluded",
                "runtime_owner": "none",
                "implementation": "none",
                "status_surface": "local_vlm_meta",
                "asset_ids": [],
                "content_applicability": "profile_excluded",
                "fallback_policy": "none",
                "reason": "deferred_for_v3_0_1",
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    capability = receipt["capabilities_by_step"]["local_vlm"]
    assert capability["status"] == "not_applicable"
    assert capability["closure_status"] == "policy_excluded"
    assert receipt["summary"]["missing_expected"] == 0
    assert receipt["outcome"] == "completed"


def test_capability_rows_bind_their_evidence_references() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-5a",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[{"step": "image_ocr", "status": "ok"}],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={
            "step_runs": "step_runs.jsonl",
            "capability_profile_contract": "ingestion_capability_profiles.yaml",
        },
        expected_capabilities={
            "image_ocr": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "steps.image_ocr.step.image_ocr",
                "status_surface": "ocr_meta",
                "asset_ids": ["tesseract"],
                "content_applicability": "ocr_text",
                "fallback_policy": "none",
            },
            "local_vlm": {
                "disposition": "policy_excluded",
                "runtime_owner": "none",
                "implementation": "none",
                "status_surface": "local_vlm_meta",
                "asset_ids": ["qwen2_5_vl_7b", "qwen2_5_vl_3b"],
                "content_applicability": "profile_excluded",
                "fallback_policy": "none",
                "reason": "deferred_for_v3_0_1",
            },
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    assert receipt["capabilities_by_step"]["image_ocr"][
        "evidence_references"
    ] == ["step_runs"]
    assert receipt["capabilities_by_step"]["local_vlm"][
        "evidence_references"
    ] == ["capability_profile_contract"]


def test_full_coverage_rejects_observed_policy_excluded_capability() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-5b",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[{"step": "local_vlm", "status": "ok"}],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={"step_runs": "step_runs.jsonl"},
        expected_capabilities={
            "local_vlm": {
                "disposition": "policy_excluded",
                "runtime_owner": "none",
                "implementation": "none",
                "status_surface": "local_vlm_meta",
                "asset_ids": ["qwen2_5_vl_7b", "qwen2_5_vl_3b"],
                "content_applicability": "profile_excluded",
                "fallback_policy": "none",
                "reason": "deferred_for_v3_0_1",
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    capability = receipt["capabilities_by_step"]["local_vlm"]
    assert capability["closure_status"] == "policy_exclusion_violated"
    assert receipt["outcome"] == "failed"


def test_full_coverage_requires_explicit_positive_input_count() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-5c",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[],
        warnings=[],
        scenes=[],
        evidence_paths={},
        expected_capabilities={},
        malformed_row_count=0,
        input_count=None,
        full_coverage=True,
    )

    assert receipt["summary"]["coverage_failures"] == 1
    assert receipt["outcome"] == "failed"


def test_content_appropriate_empty_requires_matching_fixture_truth() -> None:
    kwargs = {
        "run_id": "release-run-6",
        "profile": "PUBLIC_GPU_ENHANCED",
        "terminal_status": "completed",
        "step_rows": [
            {
                "step": "image_ocr",
                "scene_id": "scene-1",
                "status": "not_applicable",
                "extra": {"reason": "no_ocr_text"},
            }
        ],
        "warnings": [],
        "scenes": [{"scene_id": "scene-1"}],
        "evidence_paths": {},
        "expected_capabilities": {
            "image_ocr": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "tesseract",
                "status_surface": "ocr_meta",
                "asset_ids": ["tesseract"],
                "content_applicability": "ocr_text",
                "fallback_policy": "none",
            }
        },
        "malformed_row_count": 0,
        "input_count": 1,
        "full_coverage": True,
    }

    supported = build_capability_receipt(
        **kwargs,
        content_truth_by_scene={"scene-1": {"ocr_text": False}},
    )
    contradicted = build_capability_receipt(
        **kwargs,
        content_truth_by_scene={"scene-1": {"ocr_text": True}},
    )

    assert supported["capabilities_by_step"]["image_ocr"]["closure_status"] == "ran_content_appropriate_empty"
    assert supported["outcome"] == "completed"
    assert contradicted["capabilities_by_step"]["image_ocr"]["closure_status"] == "content_truth_mismatch"
    assert contradicted["outcome"] == "failed"


def test_full_coverage_unapproved_fallback_fails_closure() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-7",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[
            {
                "step": "object_detect",
                "scene_id": "scene-1",
                "status": "ok",
                "extra": {
                    "native_retry_mode": "cpu_fallback",
                    "requested_implementation": "opencv_yolox_gpu",
                    "effective_implementation": "opencv_nanodet_cpu",
                },
            }
        ],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={},
        expected_capabilities={
            "object_detect": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "opencv_yolox_gpu",
                "status_surface": "object_meta",
                "asset_ids": ["opencv_nanodet", "opencv_yolox"],
                "content_applicability": "object",
                "fallback_policy": "none",
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    capability = receipt["capabilities_by_step"]["object_detect"]
    assert capability["fallback_chain"] == ["cpu_fallback"]
    assert capability["closure_status"] == "unapproved_fallback"
    assert receipt["outcome"] == "failed"


def test_full_coverage_policy_approved_cpu_fallback_passes_with_receipt_evidence() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-approved-fallback",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[
            {
                "step": "emotion_classify",
                "scene_id": "scene-1",
                "status": "ok",
                "extra": {
                    "fallback_chain": ["cpu_fallback"],
                    "requested_implementation": "cardiffnlp_cuda",
                    "effective_implementation": "cardiffnlp_cpu",
                },
            }
        ],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={},
        expected_capabilities={
            "emotion_classify": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "steps.emotion_classify.step.emotion_classify",
                "status_surface": "emotion_meta",
                "asset_ids": ["emotion_classify_model"],
                "content_applicability": "text",
                "fallback_policy": ["cpu_fallback"],
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    capability = receipt["capabilities_by_step"]["emotion_classify"]
    assert capability["fallback_chain"] == ["cpu_fallback"]
    assert capability["closure_status"] == "ran_with_approved_fallback"
    assert receipt["summary"]["approved_fallbacks"] == 1
    assert receipt["outcome"] == "completed"


def test_full_coverage_rejects_nrc_when_only_cpu_fallback_is_approved() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-unapproved-nrc",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[
            {
                "step": "emotion_classify",
                "scene_id": "scene-1",
                "status": "ok",
                "extra": {
                    "fallback_chain": ["nrc_lexicon"],
                    "requested_implementation": "cardiffnlp_cuda",
                    "effective_implementation": "nrc_lexicon",
                },
            }
        ],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={},
        expected_capabilities={
            "emotion_classify": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "steps.emotion_classify.step.emotion_classify",
                "status_surface": "emotion_meta",
                "asset_ids": ["emotion_classify_model"],
                "content_applicability": "text",
                "fallback_policy": ["cpu_fallback"],
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    capability = receipt["capabilities_by_step"]["emotion_classify"]
    assert capability["closure_status"] == "unapproved_fallback"
    assert receipt["outcome"] == "failed"


def test_full_coverage_unexpected_known_capability_fails_closure() -> None:
    receipt = build_capability_receipt(
        run_id="release-run-8",
        profile="PUBLIC_GPU_ENHANCED",
        terminal_status="completed",
        step_rows=[
            {"step": "audio_transcribe_local", "status": "ok"},
            {"step": "image_ocr", "status": "ok"},
        ],
        warnings=[],
        scenes=[{"scene_id": "scene-1"}],
        evidence_paths={},
        expected_capabilities={
            "audio_transcribe_local": {
                "disposition": "runtime",
                "runtime_owner": "cli.run_ingestion",
                "implementation": "faster_whisper_medium",
                "status_surface": "transcript_meta",
                "asset_ids": ["faster_whisper_medium"],
                "content_applicability": "audio_present",
                "fallback_policy": "none",
            }
        },
        malformed_row_count=0,
        input_count=1,
        full_coverage=True,
    )

    assert receipt["summary"]["unexpected_capabilities"] == ["image_ocr"]
    assert receipt["outcome"] == "failed"


def _eligible_asset(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "source": "example/asset",
        "revision": "revision-1",
        "status": "eligible",
        "vault_scope": "personal_and_distributable",
        "hardware_profile": "cpu_gpu",
        "sealed_manifest_sha256": "a" * 64,
    }
    record.update(overrides)
    return record


def test_matrix_rejects_required_registry_as_optional_runtime_path() -> None:
    with pytest.raises(ValueError, match="runtime classification conflict"):
        build_capability_matrix(
            registry={"caption": {"classification": "REQUIRED_FIRST_LAUNCH"}},
            catalog={"caption": _eligible_asset()},
            runtime_policies={
                "caption": {
                    "classification": "enhancement_optional",
                    "status_surface": "caption_meta",
                    "asset_ids": ["caption"],
                }
            },
        )


def test_capability_matrix_preserves_its_v1_schema_identity() -> None:
    matrix = build_capability_matrix(
        registry={},
        catalog={},
        runtime_policies={},
    )

    assert matrix["schema_version"] == 1


def test_matrix_rejects_runtime_asset_absent_from_catalog() -> None:
    with pytest.raises(ValueError, match="runtime asset absent from catalog"):
        build_capability_matrix(
            registry={},
            catalog={},
            runtime_policies={
                "audio_transcribe_local": {
                    "classification": "core_required",
                    "status_surface": "transcript_meta",
                    "asset_ids": ["missing_transcriber"],
                }
            },
        )


def test_public_profile_rejects_explicit_personal_asset_selection() -> None:
    matrix = {
        "assets": {
            "private_model": {
                "status": "personal_only",
                "vault_scope": "personal",
                "hardware_profile": "gpu",
            }
        },
        "profile_selections": {"PUBLIC_GPU_ENHANCED": ["private_model"]},
    }

    with pytest.raises(ValueError, match="public profile selects non-distributable asset"):
        validate_profile_selection(matrix, "PUBLIC_GPU_ENHANCED")


def test_public_gpu_profile_is_a_cpu_superset_and_requires_sealed_assets() -> None:
    catalog = {
        "assets": {
            "core": _eligible_asset(pack_scope="core_cpu"),
            "cpu_vision": _eligible_asset(pack_scope="vision_cpu"),
            "gpu_vision": _eligible_asset(pack_scope="vision_gpu", hardware_profile="gpu"),
        }
    }
    profiles = {
        "profiles": {
            "PUBLIC_CPU_BASELINE": {
                "distribution": "public",
                "include_packs": ["core_cpu", "vision_cpu"],
            },
            "PUBLIC_GPU_ENHANCED": {
                "distribution": "public",
                "extends": "PUBLIC_CPU_BASELINE",
                "include_packs": ["vision_gpu"],
            },
        }
    }

    cpu_assets = resolve_profile_assets(catalog, profiles, "PUBLIC_CPU_BASELINE")
    gpu_assets = resolve_profile_assets(catalog, profiles, "PUBLIC_GPU_ENHANCED")

    assert set(cpu_assets) <= set(gpu_assets)
    assert gpu_assets == ["core", "cpu_vision", "gpu_vision"]


def test_capability_profile_resolution_applies_inherited_disposition_overrides() -> None:
    contract = {
        "schema_version": 2,
        "capabilities": {
            "image_ocr": {
                "runtime_owner": "cli.run_ingestion",
                "implementation": "steps.image_ocr.step.image_ocr",
                "status_surface": "ocr_meta",
                "asset_ids": ["tesseract"],
                "content_applicability": "ocr_text",
                "fallback_policy": "none",
            },
            "local_vlm": {
                "runtime_owner": "none",
                "implementation": "none",
                "status_surface": "local_vlm_meta",
                "asset_ids": ["qwen2_5_vl_7b", "qwen2_5_vl_3b"],
                "content_applicability": "profile_excluded",
                "fallback_policy": "none",
            },
        },
        "profiles": {
            "PUBLIC_CPU_BASELINE": {
                "default_disposition": "runtime",
                "capability_dispositions": {
                    "local_vlm": {
                        "disposition": "policy_excluded",
                        "reason": "deferred_for_v3_0_1",
                    }
                },
            },
            "PUBLIC_GPU_ENHANCED": {"extends": "PUBLIC_CPU_BASELINE"},
        },
    }

    resolved = capability_contract.resolve_capability_profile(
        contract, "PUBLIC_GPU_ENHANCED"
    )

    assert resolved["image_ocr"]["disposition"] == "runtime"
    assert resolved["local_vlm"]["disposition"] == "policy_excluded"
    assert resolved["local_vlm"]["reason"] == "deferred_for_v3_0_1"


def test_repository_gpu_capability_profiles_expand_to_complete_records() -> None:
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "ingestion_capability_profiles.yaml"
    )
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    required_fields = {
        "runtime_owner",
        "implementation",
        "status_surface",
        "asset_ids",
        "content_applicability",
        "fallback_policy",
        "disposition",
    }

    public = capability_contract.resolve_capability_profile(
        contract, "PUBLIC_GPU_ENHANCED"
    )
    personal = capability_contract.resolve_capability_profile(
        contract, "PERSONAL_AIR_GAP"
    )

    assert all(required_fields <= set(record) for record in public.values())
    assert all(required_fields <= set(record) for record in personal.values())
    for resolved in (public, personal):
        assert resolved["local_vlm"]["disposition"] == "policy_excluded"
        assert resolved["local_llm_serving"]["disposition"] == "policy_excluded"
    assert public["audio_speaker_merge"]["disposition"] == "policy_excluded"
    assert personal["audio_speaker_merge"]["disposition"] == "runtime"
    for step in ("audio_wav2vec2_enrichment", "audio_clap_handoff"):
        assert public[step]["disposition"] == "policy_excluded"
        assert personal[step]["disposition"] == "runtime"
    assert public["audio_emotion"]["status_surface"] == "audio_emotion_meta"
    assert public["emotion_classify"]["status_surface"] == "emotion_meta"
    assert public["emotion_classify"]["fallback_policy"] == ["cpu_fallback"]


def test_runtime_matrix_metadata_matches_capability_profile_contract() -> None:
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "ingestion_capability_profiles.yaml"
    )
    definitions = yaml.safe_load(contract_path.read_text(encoding="utf-8"))[
        "capabilities"
    ]

    for step, runtime_policy in capability_contract.RUNTIME_CAPABILITY_POLICIES.items():
        assert definitions[step]["status_surface"] == runtime_policy["status_surface"]
        assert definitions[step]["asset_ids"] == runtime_policy["asset_ids"]


def _repository_asset_closure(profile: str) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    catalog = yaml.safe_load(
        (repo_root / "configs" / "offline_asset_catalog.yaml").read_text(
            encoding="utf-8"
        )
    )
    installer_contract = yaml.safe_load(
        (repo_root / "configs" / "installer_profile_contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    capability_contract_payload = yaml.safe_load(
        (repo_root / "configs" / "ingestion_capability_profiles.yaml").read_text(
            encoding="utf-8"
        )
    )
    registry_payload = yaml.safe_load(
        (repo_root / "configs" / "model_registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    registry: dict[str, object] = {}
    for section in (
        "huggingface_models",
        "external_models",
        "lexicons",
        "system_tools",
    ):
        registry.update(dict(registry_payload.get(section) or {}))
    resolved_capabilities = capability_contract.resolve_capability_profile(
        capability_contract_payload,
        profile,
    )
    return capability_contract.build_profile_asset_closure(
        catalog=catalog,
        profile_contract=installer_contract,
        registry=registry,
        capability_profile=resolved_capabilities,
        profile=profile,
    )


def test_gpu_profiles_have_complete_asset_owner_and_probe_closure() -> None:
    public = _repository_asset_closure("PUBLIC_GPU_ENHANCED")
    personal = _repository_asset_closure("PERSONAL_AIR_GAP")

    assert public["schema_version"] == 2
    assert public["asset_count"] == 33
    assert personal["asset_count"] == 36
    assert set(personal["assets_by_id"]) - set(public["assets_by_id"]) == {
        "pyannote_diarization",
        "pyannote_segmentation",
        "pyannote_wespeaker",
    }
    for closure in (public, personal):
        assert len(closure["assets"]) == closure["asset_count"]
        assert all(record["runtime_owner"] != "none" for record in closure["assets"])
        for record in closure["assets"]:
            if record["kind"] == "model":
                assert record["probe"] != "none"
                assert record["registry_bound"] is True
    assert public["component_dispositions"]["wsl_audio"]["status"] == "excluded"
    assert personal["component_dispositions"]["wsl_audio"]["status"] == "host_prerequisite"


def test_asset_closure_rejects_missing_disposition() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog = yaml.safe_load(
        (repo_root / "configs" / "offline_asset_catalog.yaml").read_text(
            encoding="utf-8"
        )
    )
    installer_contract = yaml.safe_load(
        (repo_root / "configs" / "installer_profile_contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    installer_contract["asset_contracts"].pop("emotion_classify_model")
    capabilities = capability_contract.resolve_capability_profile(
        yaml.safe_load(
            (repo_root / "configs" / "ingestion_capability_profiles.yaml").read_text(
                encoding="utf-8"
            )
        ),
        "PUBLIC_GPU_ENHANCED",
    )
    registry_payload = yaml.safe_load(
        (repo_root / "configs" / "model_registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    registry = {
        key: value
        for section in (
            "huggingface_models",
            "external_models",
            "lexicons",
            "system_tools",
        )
        for key, value in dict(registry_payload.get(section) or {}).items()
    }

    with pytest.raises(ValueError, match="selected asset lacks disposition"):
        capability_contract.build_profile_asset_closure(
            catalog=catalog,
            profile_contract=installer_contract,
            registry=registry,
            capability_profile=capabilities,
            profile="PUBLIC_GPU_ENHANCED",
        )


def test_asset_closure_rejects_model_without_probe() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog = yaml.safe_load(
        (repo_root / "configs" / "offline_asset_catalog.yaml").read_text(
            encoding="utf-8"
        )
    )
    installer_contract = yaml.safe_load(
        (repo_root / "configs" / "installer_profile_contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    installer_contract["asset_contracts"]["emotion_classify_model"]["probe"] = "none"
    capabilities = capability_contract.resolve_capability_profile(
        yaml.safe_load(
            (repo_root / "configs" / "ingestion_capability_profiles.yaml").read_text(
                encoding="utf-8"
            )
        ),
        "PUBLIC_GPU_ENHANCED",
    )
    registry_payload = yaml.safe_load(
        (repo_root / "configs" / "model_registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    registry = {
        key: value
        for section in (
            "huggingface_models",
            "external_models",
            "lexicons",
            "system_tools",
        )
        for key, value in dict(registry_payload.get(section) or {}).items()
    }

    with pytest.raises(ValueError, match="selected model lacks load probe"):
        capability_contract.build_profile_asset_closure(
            catalog=catalog,
            profile_contract=installer_contract,
            registry=registry,
            capability_profile=capabilities,
            profile="PUBLIC_GPU_ENHANCED",
        )
