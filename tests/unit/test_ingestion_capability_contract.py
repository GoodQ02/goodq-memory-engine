from __future__ import annotations

import pytest

from lib.ingestion_capability_contract import build_capability_receipt


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
