from __future__ import annotations

import hashlib
import json
from pathlib import Path

from api.utils.ingest_requests import IngestRequestLedger, resolve_ingest_request_status


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


def test_request_ledger_persists_round_trip_record(tmp_path: Path) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    ledger = IngestRequestLedger(runtime_paths["ingest_requests"])
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")
    file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    record = ledger.create_record(
        source_path=source_path,
        staged_path=runtime_paths["import_inbox"] / "req_001__sample.mp4",
        file_hash=file_hash,
        confirmation_token_present=True,
        policy_profile="local_ingest_facade_v1",
        queue_depth_snapshot=1,
        watchdog_detection_window_seconds=5,
        budget_scope="single_local_file_handoff",
        budget_status="accepted",
    )

    loaded = ledger.load(record["request_id"])

    assert loaded is not None
    assert loaded["request_id"] == record["request_id"]
    assert loaded["source_path"] == str(source_path)
    assert loaded["staged_path"].endswith("req_001__sample.mp4")
    assert loaded["file_hash"] == file_hash
    assert loaded["status"] == "staged"
    assert loaded["policy_profile"] == "local_ingest_facade_v1"
    assert loaded["confirmation_token_present"] is True
    assert loaded["budget_scope"] == "single_local_file_handoff"
    assert loaded["budget_status"] == "accepted"


def test_resolve_request_status_tracks_waiting_processing_and_completed(tmp_path: Path) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    ledger = IngestRequestLedger(runtime_paths["ingest_requests"])
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")
    file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    staged_path = runtime_paths["import_inbox"] / "req_002__sample.mp4"

    record = ledger.create_record(
        source_path=source_path,
        staged_path=staged_path,
        file_hash=file_hash,
        confirmation_token_present=True,
        policy_profile="local_ingest_facade_v1",
        queue_depth_snapshot=1,
        watchdog_detection_window_seconds=5,
        budget_scope="single_local_file_handoff",
        budget_status="accepted",
    )

    staged_path.write_bytes(source_path.read_bytes())
    waiting = resolve_ingest_request_status(record, runtime_paths)
    assert waiting["status"] == "waiting_for_watchdog"

    processing_copy = runtime_paths["processing"] / staged_path.name
    processing_copy.write_bytes(source_path.read_bytes())
    processing = resolve_ingest_request_status(record, runtime_paths)
    assert processing["status"] == "processing"

    runtime_paths["watchdog_state_file"].write_text(
        json.dumps(
            {
                file_hash: {
                    "original_name": staged_path.name,
                    "status": "success",
                    "run_id": "run-123",
                    "timestamp": "2026-04-22T12:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )
    completed = resolve_ingest_request_status(record, runtime_paths)
    assert completed["status"] == "completed"
    assert completed["run_id"] == "run-123"

