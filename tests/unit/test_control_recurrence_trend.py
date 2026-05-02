from __future__ import annotations

import json
from pathlib import Path

from cli.control_recurrence_report import main as recurrence_cli_main
from lib.control_recurrence_trend import build_control_recurrence_trend


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_index(report_dir: Path, reports: list[dict]) -> None:
    _write_json(
        report_dir / "index.json",
        {
            "index": {
                "name": "control_recurrence_index",
                "version": "0.2.0",
                "generated_at_utc": "2026-04-29T00:00:00+00:00",
                "output_dir": ".",
            },
            "reports": reports,
            "warnings": [],
        },
    )


def _index_entry(report_id: str, *, created: str, report_type: str = "single_run") -> dict:
    return {
        "report_type": report_type,
        "report_id": report_id,
        "run_id": report_id,
        "json_path": f"{report_id}.json",
        "artifact_status": "json_only",
        "recommendation_status": "warn",
        "highest_category": "watch",
        "total_signals": 1,
        "blocking_signal_count": 0,
        "phase6_health_summary": {"status": "healthy", "episodes_healthy": 1, "episodes_total": 1},
        "qdrant_health_summary": {"status": "healthy", "episodes_healthy": 1, "episodes_total": 1},
        "created_or_updated_at": created,
    }


def _report(
    *,
    videos: list[str],
    family_counts: dict[str, int],
    category_counts: dict[str, int] | None = None,
    recovery_counts: dict[str, int] | None = None,
    latency_steps: list[dict] | None = None,
    recommendation_status: str = "warn",
    highest_category: str = "watch",
    phase6_healthy: int = 1,
    qdrant_ok: bool = True,
    run_root: str = "missing/raw/run/root",
) -> dict:
    category_counts = category_counts or {
        "informational": 0,
        "watch": sum(family_counts.values()),
        "actionable": 0,
        "blocking": 0,
    }
    recovery_counts = recovery_counts or {"recovered": 0, "unrecovered": 0, "skipped": sum(family_counts.values()), "unknown": 0}
    family_rows = [
        {
            "error_family": family,
            "category": highest_category,
            "count": count,
            "recovery_outcomes": recovery_counts,
            "inspection_targets": ["temporal_index.json"],
        }
        for family, count in family_counts.items()
    ]
    return {
        "report": {
            "name": "control_recurrence_report",
            "version": "test-schema-v1",
            "mode": "read_only_observability",
        },
        "scope": {
            "run_roots": [run_root],
            "videos": videos,
            "signals": sum(family_counts.values()),
        },
        "top_repeated_failure_families": family_rows,
        "recurrence_classification": {
            "highest_category": highest_category,
            "signal_counts": category_counts,
            "families": family_rows,
        },
        "recovered_vs_unrecovered_failures": recovery_counts,
        "phase6_qdrant_truth": {
            "healthy": phase6_healthy > 0,
            "status": "healthy" if phase6_healthy > 0 else "degraded",
            "episodes_total": 1,
            "episodes_healthy": phase6_healthy,
            "episodes": [{"episode": videos[0] if videos else "unknown", "qdrant_ok": qdrant_ok}],
        },
        "recommendation": {
            "status": recommendation_status,
            "highest_category": highest_category,
            "reasons": [f"highest recurrence category is {highest_category}"],
        },
        "step_latency_summary": {
            "mode": "read_only_latency_observability",
            "source": "step_runs.jsonl duration_ms",
            "status": "available" if latency_steps else "empty",
            "duration_row_count": sum(int(row.get("count") or 0) for row in latency_steps or []),
            "step_count": len(latency_steps or []),
            "slow_outlier_count": sum(int(row.get("slow_outlier_count") or 0) for row in latency_steps or []),
            "timeout_boundary_exceedance_count": sum(
                int(row.get("timeout_boundary_exceedance_count") or 0) for row in latency_steps or []
            ),
            "steps": latency_steps or [],
            "warnings": [] if latency_steps else ["no_step_duration_rows"],
        },
    }


def test_control_recurrence_trend_computes_json_backed_trends(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_json(
        report_dir / "run_a.json",
        _report(
            videos=["episode-a.mp4"],
            family_counts={"emotion_classify_unavailable": 2},
            recovery_counts={"recovered": 0, "unrecovered": 0, "skipped": 2, "unknown": 0},
        ),
    )
    _write_json(
        report_dir / "run_b.json",
        _report(
            videos=["episode-a.mp4"],
            family_counts={"emotion_classify_unavailable": 5, "native_crash_retry:0xC0000409": 1},
            category_counts={"informational": 0, "watch": 5, "actionable": 1, "blocking": 0},
            recovery_counts={"recovered": 1, "unrecovered": 0, "skipped": 5, "unknown": 0},
            highest_category="actionable",
        ),
    )
    _write_index(
        report_dir,
        [
            _index_entry("run_a", created="2026-04-29T00:00:00+00:00"),
            _index_entry("run_b", created="2026-04-29T01:00:00+00:00"),
        ],
    )

    trend = build_control_recurrence_trend(base_dir=report_dir)

    assert trend["report_window"]["json_backed_reports"] == 2
    assert trend["report_window"]["comparable_scope_groups"] == 1
    family_by_name = {row["error_family"]: row for row in trend["family_trends"]}
    assert family_by_name["emotion_classify_unavailable"]["trend_status"] == "increased"
    assert family_by_name["emotion_classify_unavailable"]["delta"] == 3
    assert family_by_name["native_crash_retry:0xC0000409"]["trend_status"] == "new"
    recovered = [row for row in trend["recovery_trends"] if row["recovery_key"] == "recovered"][0]
    assert recovered["trend_status"] == "new"
    phase6 = [row for row in trend["health_trends"] if row["health_key"] == "phase6"][0]
    assert phase6["trend_status"] == "stable"
    assert trend["safety_boundary"]["raw_run_roots_scanned"] == "not_attempted"


def test_control_recurrence_trend_derives_latency_from_json_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_json(
        report_dir / "run_a.json",
        _report(
            videos=["episode-a.mp4"],
            family_counts={"no_text": 1},
            latency_steps=[
                {
                    "step_name": "image_caption",
                    "count": 2,
                    "p50_ms": 1000.0,
                    "p95_ms": 1200.0,
                    "max_ms": 1300.0,
                    "slow_outlier_count": 0,
                    "timeout_boundary_exceedance_count": 0,
                },
                {
                    "step_name": "audio_unified_wsl2",
                    "count": 2,
                    "p50_ms": 25000.0,
                    "p95_ms": 30000.0,
                    "max_ms": 31000.0,
                    "slow_outlier_count": 0,
                    "timeout_boundary_exceedance_count": 0,
                },
            ],
        ),
    )
    _write_json(
        report_dir / "run_b.json",
        _report(
            videos=["episode-a.mp4"],
            family_counts={"no_text": 1},
            latency_steps=[
                {
                    "step_name": "image_caption",
                    "count": 2,
                    "p50_ms": 1000.0,
                    "p95_ms": 1500.0,
                    "max_ms": 2500.0,
                    "slow_outlier_count": 1,
                    "timeout_boundary_exceedance_count": 0,
                },
                {
                    "step_name": "audio_unified_wsl2",
                    "count": 2,
                    "p50_ms": 23000.0,
                    "p95_ms": 29000.0,
                    "max_ms": 30000.0,
                    "slow_outlier_count": 0,
                    "timeout_boundary_exceedance_count": 0,
                },
            ],
        ),
    )
    _write_index(
        report_dir,
        [
            _index_entry("run_a", created="2026-04-29T00:00:00+00:00"),
            _index_entry("run_b", created="2026-04-29T01:00:00+00:00"),
        ],
    )

    trend = build_control_recurrence_trend(base_dir=report_dir)
    by_step = {row["step_name"]: row for row in trend["latency_trends"]}

    assert trend["report_timeline"][0]["latency_summary"]["duration_row_count"] == 4
    assert by_step["image_caption"]["trend_status"] == "increased"
    assert by_step["image_caption"]["p95_delta_ms"] == 300.0
    assert by_step["image_caption"]["slow_outlier_delta"] == 1
    assert by_step["audio_unified_wsl2"]["trend_status"] == "decreased"
    assert by_step["audio_unified_wsl2"]["source"] == "existing recurrence JSON step_latency_summary"
    rendered = json.dumps(trend)
    for forbidden in ("improved", "regressed", "fixed", "healed", "safer"):
        assert forbidden not in rendered


def test_control_recurrence_trend_marks_markdown_only_metadata(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "legacy_markdown",
                "run_id": "legacy_markdown",
                "markdown_path": "legacy_markdown.md",
                "artifact_status": "markdown_only",
                "recommendation_status": "unknown",
                "highest_category": "unknown",
                "total_signals": 0,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-29T00:00:00+00:00",
            }
        ],
    )

    trend = build_control_recurrence_trend(base_dir=report_dir)

    assert trend["report_timeline"][0]["json_backed"] is False
    assert "json_missing" in trend["report_timeline"][0]["warning_flags"]
    assert "limited_trendability" in trend["report_timeline"][0]["warning_flags"]
    assert any(row["warning"] == "markdown_only_entry" for row in trend["scope_warnings"])


def test_control_recurrence_trend_keeps_incomparable_scopes_timeline_only(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_json(report_dir / "run_a.json", _report(videos=["episode-a.mp4"], family_counts={"no_text": 1}))
    _write_json(report_dir / "run_b.json", _report(videos=["episode-b.mp4"], family_counts={"no_text": 3}))
    _write_index(
        report_dir,
        [
            _index_entry("run_a", created="2026-04-29T00:00:00+00:00"),
            _index_entry("run_b", created="2026-04-29T01:00:00+00:00"),
        ],
    )

    trend = build_control_recurrence_trend(base_dir=report_dir)
    rendered = json.dumps(trend)

    assert trend["report_window"]["scope_group_count"] == 2
    assert any(row["warning"] == "incomparable_scope_groups" for row in trend["scope_warnings"])
    assert {row["trend_status"] for row in trend["family_trends"]} == {"insufficient_comparable_data"}
    for forbidden in ("improved", "regressed", "fixed", "healed", "safer"):
        assert forbidden not in rendered


def test_control_recurrence_trend_warns_on_malformed_json(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    report_dir.mkdir(parents=True)
    (report_dir / "bad.json").write_text("{not json", encoding="utf-8")
    _write_index(report_dir, [_index_entry("bad", created="2026-04-29T00:00:00+00:00")])

    trend = build_control_recurrence_trend(base_dir=report_dir)

    assert trend["trend_report"]["status"] == "warning"
    assert trend["report_window"]["json_backed_reports"] == 0
    assert any(row["warning"] == "json_artifact_malformed" for row in trend["scope_warnings"])


def test_control_recurrence_trend_does_not_require_raw_run_roots(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    missing_raw_root = tmp_path / "missing_raw_run_root"
    _write_json(
        report_dir / "run_a.json",
        _report(videos=[], family_counts={"no_text": 1}, run_root=str(missing_raw_root)),
    )
    _write_index(report_dir, [_index_entry("run_a", created="2026-04-29T00:00:00+00:00")])

    trend = build_control_recurrence_trend(base_dir=report_dir)

    assert trend["report_window"]["json_backed_reports"] == 1
    assert trend["report_timeline"][0]["scope_signature"]["scope_basis"] == "run_roots"
    assert missing_raw_root.exists() is False


def test_control_recurrence_trend_does_not_generate_reports_or_mutate_index(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_json(report_dir / "run_a.json", _report(videos=["episode-a.mp4"], family_counts={"no_text": 1}))
    _write_index(report_dir, [_index_entry("run_a", created="2026-04-29T00:00:00+00:00")])
    before_files = sorted(path.name for path in report_dir.iterdir())
    before_index = (report_dir / "index.json").read_text(encoding="utf-8")

    build_control_recurrence_trend(base_dir=report_dir)

    assert sorted(path.name for path in report_dir.iterdir()) == before_files
    assert (report_dir / "index.json").read_text(encoding="utf-8") == before_index


def test_control_recurrence_trend_has_no_control_agent_import() -> None:
    source = Path("lib/control_recurrence_trend.py").read_text(encoding="utf-8")

    assert "agents.control_agent" not in source
    assert "ControlAgent" not in source
    assert "self_healing" not in source
    assert "config_healer" not in source


def test_control_recurrence_trend_cli_json_shape(tmp_path: Path, capsys) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_json(report_dir / "run_a.json", _report(videos=["episode-a.mp4"], family_counts={"no_text": 1}))
    _write_index(report_dir, [_index_entry("run_a", created="2026-04-29T00:00:00+00:00")])

    assert recurrence_cli_main(["--trend", "--output-dir", str(report_dir), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["trend_report"]["name"] == "control_recurrence_trend"
    assert payload["report_window"]["json_backed_reports"] == 1
    assert payload["safety_boundary"]["reports_generated"] == "not_triggered"
    assert payload["safety_boundary"]["control_agent"] == "not_imported_or_activated"
