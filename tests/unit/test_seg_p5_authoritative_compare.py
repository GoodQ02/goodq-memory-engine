from __future__ import annotations

from pathlib import Path

from scripts.seg_p5_authoritative_compare import (
    _compare_scene_lists,
    _extract_run_summary,
)


def test_compare_scene_lists_reports_overlap_metrics() -> None:
    live = [
        {"start": 0.0, "end": 10.0},
        {"start": 10.0, "end": 20.0},
    ]
    candidate = [
        {"start": 0.0, "end": 9.5},
        {"start": 10.0, "end": 21.0},
        {"start": 30.0, "end": 35.0},
    ]

    comparison = _compare_scene_lists(live, candidate)

    assert comparison["matched_scene_count"] == 2
    assert comparison["matched_scene_ratio_live"] == 1.0
    assert comparison["matched_scene_ratio_candidate"] == 2 / 3
    assert comparison["duration_coverage"] > 0.9
    assert comparison["boundary_delta_mean_sec"] >= 0.0


def test_extract_run_summary_uses_scene_meta_and_orchestration(tmp_path: Path) -> None:
    result = {
        "phase6_complete": True,
        "qdrant_ok": True,
        "faiss_ok": True,
        "orchestration": {
            "scene_backend_selected": "segmentation_phase5",
            "scene_backend_effective": "segmentation_phase5",
            "scene_backend_effective_reason": "segmentation_authoritative_env_override",
        },
        "scenes": [
            {"start": 0.0, "end": 12.0},
            {"start": 12.0, "end": 20.0},
        ],
    }

    summary = _extract_run_summary(
        result,
        mode="authoritative",
        runtime={"output": tmp_path / "out.json", "workspace": tmp_path / "ws"},
    )

    assert summary["scene_count"] == 2
    assert summary["phase6_complete"] is True
    assert summary["orchestration"]["scene_backend_effective"] == "segmentation_phase5"
