from __future__ import annotations

from scripts.seg_p5_promotion_envelope import build_envelope, render_envelope_markdown


def test_build_envelope_derives_stats_and_thresholds() -> None:
    report = {
        "report_path": "reports/segmentation_shadow_campaign.json",
        "campaign_id": "demo",
        "episodes": [
            {
                "status": "ok",
                "episode_name": "ep1",
                "scene_backend_match_ratio_live": 1.0,
                "scene_backend_duration_coverage": 0.50,
                "scene_backend_boundary_delta_mean_sec": 10.0,
                "scene_count_live": 33,
                "scene_count_shadow": 67,
                "scene_count_delta": 34,
            },
            {
                "status": "ok",
                "episode_name": "ep2",
                "scene_backend_match_ratio_live": 0.98,
                "scene_backend_duration_coverage": 0.54,
                "scene_backend_boundary_delta_mean_sec": 9.4,
                "scene_count_live": 31,
                "scene_count_shadow": 64,
                "scene_count_delta": 33,
            },
        ],
    }

    envelope = build_envelope(report)

    assert envelope["episode_count"] == 2
    assert envelope["metric_stats"]["scene_backend_match_ratio_live"]["min"] == 0.98
    assert envelope["thresholds"]["scene_backend_match_ratio_live_min"] <= 0.98
    assert envelope["thresholds"]["scene_backend_boundary_delta_mean_sec_max"] >= 10.0
    assert envelope["thresholds"]["scene_count_delta_expected_window"]["min"] <= 33


def test_render_envelope_markdown_contains_manual_gates() -> None:
    report = {
        "report_path": "reports/segmentation_shadow_campaign.json",
        "campaign_id": "demo",
        "episodes": [
            {
                "status": "ok",
                "episode_name": "ep1",
                "scene_backend_match_ratio_live": 1.0,
                "scene_backend_duration_coverage": 0.50,
                "scene_backend_boundary_delta_mean_sec": 10.0,
                "scene_count_live": 33,
                "scene_count_shadow": 67,
                "scene_count_delta": 34,
            }
        ],
    }
    envelope = build_envelope(report)
    rendered = render_envelope_markdown(report, envelope)

    assert "# SEG_P5 Promotion Envelope" in rendered
    assert "scene_backend_match_ratio_live" in rendered
    assert "manual review only" in rendered

