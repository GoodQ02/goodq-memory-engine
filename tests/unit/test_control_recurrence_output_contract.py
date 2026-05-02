from __future__ import annotations

import json
from pathlib import Path

from lib.control_recurrence_recommendations import build_recommendation_draft_from_report
from lib.control_recurrence_report import build_control_recurrence_comparison, build_control_recurrence_report
from lib.control_recurrence_trend import build_control_recurrence_trend


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, payloads: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item) for item in payloads) + "\n", encoding="utf-8")


def _write_fixture_run(
    tmp_path: Path,
    run_name: str,
    *,
    runtime_run_id: str,
    video_id: str,
    step_rows: list[dict],
) -> tuple[Path, Path]:
    reports_root = tmp_path / "reports" / "fresh_ingest_runs"
    run_root = reports_root / run_name
    epoch_root = tmp_path / "GoodQ_Data" / "epochs" / f"epoch_{run_name}"
    episode_name = "01x01 - Contract Witness.mp4"
    episode_dir = run_root / "01x01_contract_witness"
    processing_dir = epoch_root / "processing" / "01x01 - Contract Witness"
    output_path = episode_dir / "output" / "scene_ingest_results.json"
    scene_manifest_path = processing_dir / "video" / "scene_manifest.json"
    temporal_index_path = processing_dir / "temporal_index.json"
    scene_id = f"{run_name}-scene"

    scenes = [{"scene_id": scene_id, "index": 0, "qdrant_ok": True}]
    _write_json(
        output_path,
        [
            {
                "video_id": video_id,
                "video_hash": video_id,
                "video_name": episode_name,
                "phase6_complete": True,
                "qdrant_ok": True,
                "phase6_qdrant_ok": True,
                "scenes": scenes,
                "temporal_index_path": str(temporal_index_path),
            }
        ],
    )
    _write_json(
        scene_manifest_path,
        {
            "video_id": video_id,
            "phase6_complete": True,
            "phase6_harmonized": True,
            "phase6_vector_commit": {"qdrant_ok": True},
            "scenes": scenes,
        },
    )
    _write_json(
        temporal_index_path,
        {
            "video_id": video_id,
            "phase6_complete": True,
            "phase6_harmonized": True,
            "total_scenes": 1,
            "segments": [{"scene_id": scene_id, "index": 0}],
        },
    )
    _write_json(
        episode_dir / "workspace" / "_resolved_config.json",
        {
            "run": {"id": runtime_run_id, "pipeline": "scene_ingest_cli", "warnings": []},
            "paths": {"log_dir": str(epoch_root / "logs")},
        },
    )
    _write_json(
        episode_dir / "experiment_log.json",
        {
            "episode": episode_name,
            "status": "passed",
            "metrics": {
                "output_path": str(output_path),
                "scene_manifest_path": str(scene_manifest_path),
                "temporal_index_path": str(temporal_index_path),
            },
        },
    )
    _write_json(
        run_root / "experiment_log.json",
        {
            "epoch": f"epoch_{run_name}",
            "status": "completed",
            "plan": [{"episode": episode_name, "status": "passed", "run_dir": str(episode_dir)}],
        },
    )
    for row in step_rows:
        row.setdefault("run_id", runtime_run_id)
        row.setdefault("video_id", video_id)
        row.setdefault("scene_id", scene_id)
        row.setdefault("scene_index", 0)
    _write_jsonl(epoch_root / "logs" / "step_runs.jsonl", step_rows)
    return reports_root, run_root


def _assert_keys(value: dict, keys: set[str]) -> None:
    assert keys.issubset(value), sorted(keys - set(value))


def test_single_run_recurrence_report_contract_includes_observer_sections(tmp_path: Path) -> None:
    reports_root, run_root = _write_fixture_run(
        tmp_path,
        "contract_single",
        runtime_run_id="runtime-single",
        video_id="video-single",
        step_rows=[
            {
                "ts": "2026-05-02T00:00:00",
                "step": "image_caption",
                "status": "ok",
                "duration_ms": 1000.0,
            },
            {
                "ts": "2026-05-02T00:00:01",
                "step": "image_ocr",
                "status": "skipped",
                "duration_ms": 10.0,
                "extra": {
                    "reason": "image_ocr_pytesseract",
                    "result_meta": {"ocr_meta": {"status": "dependency_missing", "reason": "pytesseract"}},
                    "embedding_emitted": False,
                },
            },
        ],
    )

    report = build_control_recurrence_report(run_id=run_root.name, reports_root=reports_root)

    _assert_keys(
        report,
        {
            "report",
            "scope",
            "step_latency_summary",
            "recurrence_summary",
            "top_repeated_failure_families",
            "optional_enrichment_skips",
            "optional_enrichment_coverage",
            "recovered_vs_unrecovered_failures",
            "phase6_qdrant_truth",
            "recurrence_classification",
            "recommendation",
            "operator_hints",
            "inspection_targets",
            "evidence",
        },
    )
    _assert_keys(
        report["optional_enrichment_coverage"],
        {"mode", "source", "status", "total_rows", "step_count", "non_ok_rows", "steps", "warnings"},
    )
    coverage = {row["step_name"]: row for row in report["optional_enrichment_coverage"]["steps"]}
    _assert_keys(
        coverage["image_ocr"],
        {
            "step_name",
            "total_rows",
            "ok_count",
            "skipped_count",
            "error_count",
            "warning_count",
            "non_ok_count",
            "status_counts",
            "reason_counts",
            "meta_status_counts",
            "embedding_emitted_count",
            "scene_count",
            "episodes",
            "episode_count",
        },
    )
    assert report["report"]["control_agent"] == "not_activated"
    assert report["report"]["auto_healing"] == "not_enabled"


def test_comparison_recurrence_report_contract_includes_latency_and_coverage_delta(tmp_path: Path) -> None:
    reports_root, _ = _write_fixture_run(
        tmp_path,
        "contract_baseline",
        runtime_run_id="runtime-baseline",
        video_id="video-baseline",
        step_rows=[
            {"ts": "2026-05-02T00:00:00", "step": "image_caption", "status": "ok", "duration_ms": 1000.0},
            {"ts": "2026-05-02T00:00:01", "step": "image_ocr", "status": "ok", "duration_ms": 10.0},
        ],
    )
    _write_fixture_run(
        tmp_path,
        "contract_candidate",
        runtime_run_id="runtime-candidate",
        video_id="video-candidate",
        step_rows=[
            {"ts": "2026-05-02T01:00:00", "step": "image_caption", "status": "ok", "duration_ms": 1500.0},
            {
                "ts": "2026-05-02T01:00:01",
                "step": "image_ocr",
                "status": "skipped",
                "duration_ms": 12.0,
                "extra": {"reason": "image_ocr_pytesseract"},
            },
        ],
    )

    comparison = build_control_recurrence_comparison(
        baseline_run_id="contract_baseline",
        candidate_run_id="contract_candidate",
        reports_root=reports_root,
    )

    _assert_keys(comparison, {"report", "baseline", "candidate", "delta", "recommendation", "operator_hints", "inspection_targets", "evidence"})
    _assert_keys(
        comparison["delta"],
        {
            "total_recurrence_signals",
            "signals_by_error_family",
            "recovery_counts",
            "category_counts",
            "per_step_changes",
            "step_latency_delta",
            "optional_enrichment_coverage_delta",
            "phase6_health_delta",
            "qdrant_health_delta",
        },
    )
    assert comparison["delta"]["step_latency_delta"]["status"] == "available"
    assert comparison["delta"]["optional_enrichment_coverage_delta"]["status"] == "available"


def test_trend_and_recommendation_contracts_remain_read_only(tmp_path: Path) -> None:
    reports_root, run_root = _write_fixture_run(
        tmp_path,
        "contract_indexed",
        runtime_run_id="runtime-indexed",
        video_id="video-indexed",
        step_rows=[
            {"ts": "2026-05-02T00:00:00", "step": "image_caption", "status": "ok", "duration_ms": 1000.0},
        ],
    )
    report = build_control_recurrence_report(run_id=run_root.name, reports_root=reports_root)
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_json(report_dir / "contract_indexed.json", report)
    _write_json(
        report_dir / "index.json",
        {
            "reports": [
                {
                    "report_type": "single_run",
                    "report_id": "contract_indexed",
                    "run_id": "contract_indexed",
                    "json_path": "contract_indexed.json",
                    "recommendation_status": report["recommendation"]["status"],
                    "highest_category": report["recurrence_classification"]["highest_category"],
                    "total_signals": report["scope"]["signals"],
                    "blocking_signal_count": report["recurrence_classification"]["signal_counts"]["blocking"],
                    "created_or_updated_at": "2026-05-02T00:00:00+00:00",
                }
            ],
            "warnings": [],
        },
    )

    trend = build_control_recurrence_trend(base_dir=report_dir)
    recommendation = build_recommendation_draft_from_report("contract_indexed", report)

    _assert_keys(
        trend,
        {
            "trend_report",
            "report_window",
            "report_timeline",
            "family_trends",
            "category_trends",
            "recovery_trends",
            "health_trends",
            "latency_trends",
            "recommendation_history",
            "scope_warnings",
            "safety_boundary",
        },
    )
    _assert_keys(
        recommendation,
        {
            "status",
            "report_id",
            "report_type",
            "recommendation_status",
            "highest_category",
            "blocking_summary",
            "top_operator_priorities",
            "inspection_plan",
            "defer_mutation_reason",
            "safety_boundary",
        },
    )
    assert trend["safety_boundary"]["reports_generated"] == "not_triggered"
    assert recommendation["safety_boundary"]["auto_healing"] == "not_enabled"
