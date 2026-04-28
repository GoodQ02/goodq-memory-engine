from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import control_recurrence
from lib import control_recurrence_index


def _client(monkeypatch, report_dir: Path) -> TestClient:
    monkeypatch.setattr(control_recurrence_index, "DEFAULT_REPORT_DIR", report_dir)
    app = FastAPI()
    app.include_router(control_recurrence.router)
    return TestClient(app)


def _write_index(report_dir: Path, reports: list[dict]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "index.json").write_text(
        json.dumps(
            {
                "index": {
                    "name": "control_recurrence_index",
                    "version": "0.2.0",
                    "generated_at_utc": "2026-04-27T00:00:00+00:00",
                    "output_dir": "reports/control_recurrence",
                },
                "reports": reports,
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_control_recurrence_api_missing_index_returns_empty(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path / "reports" / "control_recurrence")

    payload = client.get("/api/control-recurrence/reports").json()

    assert payload == {"status": "empty", "reports": [], "reason": "index_missing"}


def test_control_recurrence_api_lists_reports(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "run_a",
                "run_id": "run_a",
                "json_path": "run_a.json",
                "markdown_path": "run_a.md",
                "recommendation_status": "PASS",
                "highest_category": "informational",
                "total_signals": 2,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            }
        ],
    )
    client = _client(monkeypatch, report_dir)

    payload = client.get("/api/control-recurrence/reports").json()

    assert payload["index"]["name"] == "control_recurrence_index"
    assert payload["reports"][0]["report_id"] == "run_a"
    assert payload["reports"][0]["json_path"] == "run_a.json"


def test_control_recurrence_api_latest_selects_newest(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "old_run",
                "run_id": "old_run",
                "json_path": "old_run.json",
                "recommendation_status": "PASS",
                "highest_category": "informational",
                "total_signals": 1,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            },
            {
                "report_type": "single_run",
                "report_id": "new_run",
                "run_id": "new_run",
                "json_path": "new_run.json",
                "recommendation_status": "WARN",
                "highest_category": "watch",
                "total_signals": 3,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T01:00:00+00:00",
            },
        ],
    )
    client = _client(monkeypatch, report_dir)

    payload = client.get("/api/control-recurrence/reports/latest").json()

    assert payload["status"] == "ok"
    assert payload["report"]["report_id"] == "new_run"
    assert payload["report"]["recommendation_status"] == "WARN"


def test_control_recurrence_api_fetches_report_json(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "run_a",
                "run_id": "run_a",
                "json_path": "run_a.json",
                "recommendation_status": "PASS",
                "highest_category": "informational",
                "total_signals": 1,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            }
        ],
    )
    (report_dir / "run_a.json").write_text(
        json.dumps(
            {
                "report": {"name": "control_recurrence_report"},
                "scope": {"run_roots": [str(report_dir / "run_a")]},
                "recommendation": {"status": "PASS"},
            }
        ),
        encoding="utf-8",
    )
    client = _client(monkeypatch, report_dir)

    payload = client.get("/api/control-recurrence/reports/run_a").json()

    assert payload["report"]["name"] == "control_recurrence_report"
    assert payload["scope"]["run_roots"] == ["run_a"]
    assert ":\\" not in json.dumps(payload)


def test_control_recurrence_api_fetches_markdown(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "run_a",
                "run_id": "run_a",
                "markdown_path": "run_a.md",
                "recommendation_status": "PASS",
                "highest_category": "informational",
                "total_signals": 1,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            }
        ],
    )
    (report_dir / "run_a.md").write_text("# Report\n\nPath: " + str(report_dir / "run_a"), encoding="utf-8")
    client = _client(monkeypatch, report_dir)

    response = client.get("/api/control-recurrence/reports/run_a/markdown")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# Report" in response.text
    assert ":\\" not in response.text


def test_control_recurrence_api_rejects_path_traversal(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "bad_run",
                "run_id": "bad_run",
                "json_path": "../outside.json",
                "recommendation_status": "FAIL",
                "highest_category": "blocking",
                "total_signals": 1,
                "blocking_signal_count": 1,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            }
        ],
    )
    client = _client(monkeypatch, report_dir)

    response = client.get("/api/control-recurrence/reports/bad_run")

    assert response.status_code == 400
    assert response.json()["status"] == "rejected"
    assert response.json()["reason"] == "artifact_path_traversal_rejected"


def test_control_recurrence_api_malformed_artifact_returns_warning(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "control_recurrence"
    _write_index(
        report_dir,
        [
            {
                "report_type": "single_run",
                "report_id": "bad_json",
                "run_id": "bad_json",
                "json_path": "bad_json.json",
                "recommendation_status": "WARN",
                "highest_category": "watch",
                "total_signals": 1,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            },
            {
                "report_type": "single_run",
                "report_id": "missing_json",
                "run_id": "missing_json",
                "json_path": "missing_json.json",
                "recommendation_status": "WARN",
                "highest_category": "watch",
                "total_signals": 1,
                "blocking_signal_count": 0,
                "created_or_updated_at": "2026-04-27T00:00:00+00:00",
            },
        ],
    )
    (report_dir / "bad_json.json").write_text("{not json", encoding="utf-8")
    client = _client(monkeypatch, report_dir)

    malformed = client.get("/api/control-recurrence/reports/bad_json").json()
    missing = client.get("/api/control-recurrence/reports/missing_json").json()

    assert malformed["status"] == "warning"
    assert malformed["reason"] == "json_artifact_malformed"
    assert missing["status"] == "not_available"
    assert missing["reason"] == "json_artifact_missing"
