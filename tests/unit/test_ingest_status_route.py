from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.utils.ingest_requests import IngestRequestLedger


def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ingest_module = _load_route_module("ingest")


def _runtime_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "ingest_requests": tmp_path / "ingest_requests",
        "import_inbox": tmp_path / "import_inbox",
        "processing": tmp_path / "processing",
        "processed": tmp_path / "processed",
        "failed": tmp_path / "failed",
        "watchdog_state_file": tmp_path / "logs" / "watchdog_state.json",
    }
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def test_get_ingest_status_returns_completed_run_details(tmp_path: Path, monkeypatch) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")
    staged_path = runtime_paths["import_inbox"] / "req_003__sample.mp4"
    ledger = IngestRequestLedger(runtime_paths["ingest_requests"])
    record = ledger.create_record(
        source_path=source_path,
        staged_path=staged_path,
        file_hash="abc123",
        confirmation_token_present=True,
        policy_profile="local_ingest_facade_v1",
        queue_depth_snapshot=1,
        watchdog_detection_window_seconds=5,
        budget_scope="single_local_file_handoff",
        budget_status="accepted",
    )
    runtime_paths["watchdog_state_file"].write_text(
        json.dumps(
            {
                "abc123": {
                    "original_name": staged_path.name,
                    "status": "success",
                    "run_id": "run-777",
                    "timestamp": "2026-04-22T12:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths)

    response = asyncio.run(ingest_module.get_ingest_status(record["request_id"]))

    assert response.request_id == record["request_id"]
    assert response.status == "completed"
    assert response.run_id == "run-777"
    assert response.original_name == "sample.mp4"
    assert response.policy_profile == "local_ingest_facade_v1"
    assert response.pickup_estimate == "best_effort"


def test_get_ingest_status_raises_404_for_unknown_request(tmp_path: Path, monkeypatch) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    monkeypatch.setattr(ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(ingest_module.get_ingest_status("missing-request"))

    assert exc_info.value.status_code == 404
