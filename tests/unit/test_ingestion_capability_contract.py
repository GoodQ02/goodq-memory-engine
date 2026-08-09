from __future__ import annotations

import pytest

from lib.ingestion_capability_contract import (
    build_capability_matrix,
    build_capability_receipt,
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
