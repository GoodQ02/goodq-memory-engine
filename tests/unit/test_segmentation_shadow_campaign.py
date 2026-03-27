from __future__ import annotations

from pathlib import Path

from scripts.segmentation_shadow_campaign import (
    _build_campaign_overrides,
    _extract_episode_metrics,
)


def test_build_campaign_overrides_enables_shadow_and_isolates_runtime(tmp_path: Path) -> None:
    base_cfg = {
        "paths": {"models_cache": str(tmp_path / "models")},
        "qdrant": {"host": "http://127.0.0.1:6333"},
    }

    overrides = _build_campaign_overrides(
        campaign_root=tmp_path / "campaign",
        episode_slug="ep1",
        collection_prefix="segshadow_test_ep1",
        base_cfg=base_cfg,
    )

    assert overrides["segmentation"]["activation"] == "shadow"
    assert overrides["segmentation"]["metrics_output"] is True
    assert overrides["segmentation"]["shadow_audio_overlay"] is False
    assert overrides["paths"]["models_cache"] == str(tmp_path / "models")
    assert overrides["qdrant"]["host"] == "http://127.0.0.1:6333"
    assert overrides["qdrant"]["collections"]["clip"] == "segshadow_test_ep1_clip"
    assert "shadow_campaign" in overrides["paths"]["db_dir"]


def test_extract_episode_metrics_reads_shadow_payload() -> None:
    runtime = {
        "workspace": Path("workspace"),
        "output": Path("ingestion_results.json"),
    }
    result = {
        "orchestration": {
            "scene_backend_selected": "segmentation_phase5_shadow_compare",
            "scene_backend_effective": "legacy_scene_detect",
            "scene_backend_effective_reason": "segmentation_shadow_compare_legacy_authority",
        },
        "segmentation_shadow": {
            "status": "complete",
            "reason": "segmentation_shadow_complete",
            "summary_path": "shadow_summary.json",
            "scene_manifest_path": "scene_manifest.json",
            "segmentation_manifest_path": "segmentation.json",
            "metrics_path": "shadow_metrics.json",
            "metrics": {
                "scene_backend_match_ratio_live": 0.95,
                "scene_backend_duration_coverage": 0.91,
                "scene_backend_boundary_delta_mean_sec": 0.22,
                "scene_count_current": 40,
                "scene_count_shadow": 38,
                "scene_count_delta": -2,
            },
        },
    }

    episode = _extract_episode_metrics(
        result,
        episode_name="01x01 - Good News, Bad News",
        video_path=Path("episode.mp4"),
        runtime=runtime,
    )

    assert episode["status"] == "ok"
    assert episode["scene_backend_match_ratio_live"] == 0.95
    assert episode["scene_backend_duration_coverage"] == 0.91
    assert episode["scene_backend_boundary_delta_mean_sec"] == 0.22
    assert episode["scene_count_live"] == 40
    assert episode["scene_count_shadow"] == 38
    assert episode["orchestration"]["scene_backend_selected"] == "segmentation_phase5_shadow_compare"
