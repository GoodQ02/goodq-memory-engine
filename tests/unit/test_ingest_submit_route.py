from __future__ import annotations

import asyncio
import importlib.util
import hashlib
import json
import sys
from pathlib import Path


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


def test_submit_ingest_stages_file_and_returns_request_handle(tmp_path: Path, monkeypatch) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")

    monkeypatch.setattr(ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths)

    request = ingest_module.IngestSubmitRequest(
        file_path=str(source_path),
        confirmation_token="confirm-123",
        policy_profile="local_ingest_facade_v1",
    )

    response = asyncio.run(ingest_module.submit_ingest(request))

    staged_path = Path(response.staged_path)
    assert response.status == "staged"
    assert response.request_id
    assert response.original_name == "sample.mp4"
    assert response.policy_profile == "local_ingest_facade_v1"
    assert response.pickup_estimate == "best_effort"
    assert response.watchdog_detection_window_seconds == 5
    assert response.queue_depth_snapshot == 1
    assert staged_path.exists()
    assert staged_path.parent == runtime_paths["import_inbox"]

    record_path = runtime_paths["ingest_requests"] / f"{response.request_id}.json"
    assert record_path.exists()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "staged"
    assert record["staged_path"] == str(staged_path)


def test_submit_ingest_returns_duplicate_without_restaging(tmp_path: Path, monkeypatch) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")
    file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    runtime_paths["watchdog_state_file"].write_text(
        json.dumps(
            {
                file_hash: {
                    "original_name": "sample.mp4",
                    "status": "success",
                    "run_id": "run-321",
                    "timestamp": "2026-04-22T12:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths)

    request = ingest_module.IngestSubmitRequest(
        file_path=str(source_path),
        confirmation_token="confirm-123",
        policy_profile="local_ingest_facade_v1",
    )

    response = asyncio.run(ingest_module.submit_ingest(request))

    assert response.status == "duplicate"
    assert response.duplicate_of_run_id == "run-321"
    assert response.staged_path is None
    assert list(runtime_paths["import_inbox"].iterdir()) == []


def test_submit_ingest_rejects_invalid_token(tmp_path: Path, monkeypatch) -> None:
    from fastapi import HTTPException
    import pytest

    runtime_paths = _runtime_paths(tmp_path)
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")

    monkeypatch.setattr(ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths)

    request = ingest_module.IngestSubmitRequest(
        file_path=str(source_path),
        confirmation_token="invalid-token",
        policy_profile="local_ingest_facade_v1",
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ingest_module.submit_ingest(request))

    assert exc.value.status_code == 403
    assert "Invalid or expired confirmation_token" in exc.value.detail


def test_submit_ingest_accepts_server_generated_token(tmp_path: Path, monkeypatch) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    source_path = tmp_path / "sample.mp4"
    source_path.write_bytes(b"video-bytes")

    monkeypatch.setattr(ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths)

    # Generate token
    res = asyncio.run(ingest_module.generate_confirmation_token())
    token = res["confirmation_token"]

    request = ingest_module.IngestSubmitRequest(
        file_path=str(source_path),
        confirmation_token=token,
        policy_profile="local_ingest_facade_v1",
    )

    response = asyncio.run(ingest_module.submit_ingest(request))
    assert response.status == "staged"

    # Verifying one-time consumption: using the same token again should be rejected
    request_retry = ingest_module.IngestSubmitRequest(
        file_path=str(source_path),
        confirmation_token=token,
        policy_profile="local_ingest_facade_v1",
    )

    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ingest_module.submit_ingest(request_retry))
    assert exc.value.status_code == 403


