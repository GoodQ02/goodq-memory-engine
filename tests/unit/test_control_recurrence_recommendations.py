from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import control_recurrence
from cli.control_recurrence_report import main as recurrence_cli_main
from lib import control_recurrence_index
from lib.control_recurrence_recommendations import build_recommendation_draft


def _write_artifact(report_dir: Path, report_id: str, report: dict) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{report_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    reports = []
    if (report_dir / "index.json").is_file():
        reports = json.loads((report_dir / "index.json").read_text(encoding="utf-8")).get("reports", [])
    reports = [entry for entry in reports if entry.get("report_id") != report_id]
    reports.append(
        {
            "report_type": "single_run",
            "report_id": report_id,
            "run_id": report_id,
            "json_path": f"{report_id}.json",
            "recommendation_status": report["recommendation"]["status"],
            "highest_category": report["recommendation"]["highest_category"],
            "total_signals": report["scope"]["signals"],
            "blocking_signal_count": report["recurrence_classification"]["signal_counts"].get("blocking", 0),
            "created_or_updated_at": "2026-04-27T00:00:00+00:00",
        }
    )
    (report_dir / "index.json").write_text(
        json.dumps(
            {
                "index": {"name": "control_recurrence_index", "version": "0.2.0"},
                "reports": sorted(reports, key=lambda entry: entry["report_id"]),
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _report(
    *,
    category: str,
    family: str,
    status: str,
    count: int = 1,
    healthy: bool = True,
    step_name: str = "image_embed_dino",
    recovery_counts: dict | None = None,
) -> dict:
    signal_counts = {"informational": 0, "watch": 0, "actionable": 0, "blocking": 0}
    signal_counts[category] = count
    recovery_counts = recovery_counts or {}
    return {
        "report": {"name": "control_recurrence_report"},
        "scope": {"signals": count},
        "recommendation": {"status": status, "highest_category": category},
        "recurrence_classification": {
            "highest_category": category,
            "highest_category_level": {"informational": 0, "watch": 1, "actionable": 2, "blocking": 3}[category],
            "signal_counts": signal_counts,
            "families": [
                {
                    "error_family": family,
                    "category": category,
                    "count": count,
                    "operator_hints": [f"Inspect {family} metadata."],
                    "inspection_targets": [f"{family} target"],
                }
            ],
        },
        "top_repeated_failure_families": [
            {
                "error_family": family,
                "category": category,
                "count": count,
                "step_names": [step_name],
                "recovery_outcomes": recovery_counts,
            }
        ],
        "recovered_vs_unrecovered_failures": recovery_counts,
        "phase6_qdrant_truth": {
            "healthy": healthy,
            "status": "healthy" if healthy else "degraded",
            "episodes_total": 1,
            "episodes_healthy": 1 if healthy else 0,
            "episodes": [{"episode": "demo.mp4", "qdrant_ok": healthy}],
        },
    }


def _client(monkeypatch, report_dir: Path) -> TestClient:
    monkeypatch.setattr(control_recurrence_index, "DEFAULT_REPORT_DIR", report_dir)
    app = FastAPI()
    app.include_router(control_recurrence.router)
    return TestClient(app)


def test_recommendation_draft_informational_only_pass(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_artifact(report_dir, "info_run", _report(category="informational", family="no_text", status="pass"))

    draft, status_code = build_recommendation_draft("info_run", base_dir=report_dir)

    assert status_code == 200
    assert draft["recommendation_status"] == "pass"
    assert draft["highest_category"] == "informational"
    assert "No immediate action" in draft["top_operator_priorities"][0]
    assert "No mutation indicated" in draft["defer_mutation_reason"]
    assert draft["safety_boundary"]["control_agent"] == "not_activated"


def test_recommendation_draft_watch_only_warn(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_artifact(
        report_dir,
        "watch_run",
        _report(category="watch", family="diarization_unavailable", status="warn", count=3),
    )

    draft, status_code = build_recommendation_draft("watch_run", base_dir=report_dir)

    assert status_code == 200
    assert draft["recommendation_status"] == "warn"
    assert draft["highest_category"] == "watch"
    assert any("Trend watch recurrence family" in item for item in draft["top_operator_priorities"])
    assert any("targeted status/meta fields" in item for item in draft["inspection_plan"])


def test_recommendation_draft_actionable_recovered_warn(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_artifact(
        report_dir,
        "action_run",
        _report(
            category="actionable",
            family="native_crash_retry:0xC0000409",
            status="warn",
            count=2,
            recovery_counts={"recovered_retry": 2},
        ),
    )

    draft, status_code = build_recommendation_draft("action_run", base_dir=report_dir)

    assert status_code == 200
    assert draft["highest_category"] == "actionable"
    assert any("stderr/error tails" in item for item in draft["top_operator_priorities"])
    assert any("final scene output survived" in item for item in draft["inspection_plan"])
    assert "unrecovered count is zero" in draft["defer_mutation_reason"]


def test_recommendation_draft_blocking_fail(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_artifact(
        report_dir,
        "blocking_run",
        _report(
            category="blocking",
            family="missing temporal_index.json",
            status="fail",
            healthy=False,
            recovery_counts={"unrecovered_processing_error": 1},
        ),
    )

    draft, status_code = build_recommendation_draft("blocking_run", base_dir=report_dir)

    assert status_code == 200
    assert draft["recommendation_status"] == "fail"
    assert draft["blocking_summary"]["blocking_signal_count"] == 1
    assert draft["blocking_summary"]["canonical_artifact_missing_families"] == ["missing temporal_index.json"]
    assert any("canonical processing paths" in item for item in draft["inspection_plan"])
    assert any("Do not start with a broad rerun" in item for item in draft["inspection_plan"])


def test_recommendation_draft_cli_json_shape(tmp_path: Path, capsys) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_artifact(
        report_dir,
        "action_run",
        _report(category="actionable", family="native_crash_retry:0xC0000409", status="warn"),
    )

    assert recurrence_cli_main(["--recommendations-for", "action_run", "--output-dir", str(report_dir), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["report_id"] == "action_run"
    assert payload["recommendation_status"] == "warn"
    assert payload["safety_boundary"]["report_generation"] == "not_triggered"
    assert payload["safety_boundary"]["command_execution"] == "not_attempted"


def test_recommendation_draft_api_shape_and_path_rejection(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_artifact(report_dir, "info_run", _report(category="informational", family="no_text", status="pass"))
    client = _client(monkeypatch, report_dir)

    payload = client.get("/api/control-recurrence/reports/info_run/recommendations").json()
    rejected = client.get("/api/control-recurrence/reports/..%5Csecret/recommendations")

    assert payload["status"] == "ok"
    assert payload["report_id"] == "info_run"
    assert payload["safety_boundary"]["ingestion"] == "not_triggered"
    assert rejected.status_code == 400
    assert rejected.json()["reason"] == "report_id_path_traversal_rejected"
