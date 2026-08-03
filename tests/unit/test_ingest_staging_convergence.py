from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.mini_agent_client import MiniAgentClient
from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority


def _load_ingest_module():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    module_path = repo_root / "api" / "routes" / "ingest.py"
    spec = importlib.util.spec_from_file_location(
        "tests.ingest_staging_convergence_route", module_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ingest_module = _load_ingest_module()

def _runtime_paths(
    tmp_path: Path,
    *,
    create: bool = True,
) -> dict[str, Path]:
    paths = {
        "ingest_requests": tmp_path / "ingest_requests",
        "import_inbox": tmp_path / "import_inbox",
        "processing": tmp_path / "processing",
        "processed": tmp_path / "processed",
        "failed": tmp_path / "failed",
        "watchdog_state_file": tmp_path / "logs" / "watchdog_state.json",
    }
    if create:
        for path in paths.values():
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                path.mkdir(parents=True, exist_ok=True)
    return paths


def _app_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    create_runtime_paths: bool = True,
) -> tuple[TestClient, dict[str, Path], MiniAgentClient]:
    runtime_paths = _runtime_paths(tmp_path, create=create_runtime_paths)
    authority = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    monkeypatch.setattr(
        ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths
    )
    monkeypatch.setattr(
        ingest_module,
        "get_ingest_authority",
        lambda: authority,
        raising=False,
    )
    app = FastAPI()
    app.include_router(ingest_module.router)
    install_route_effect_authority(
        app,
        registry={
            operation: ROUTE_EFFECTS[operation]
            for operation in (
                ("POST", "/api/ingest/submit"),
                ("GET", "/api/ingest/status/{request_id}"),
            )
        },
        client_is_loopback=lambda client: isinstance(client, (tuple, list))
        and client[0] == "127.0.0.1",
    )
    return (
        TestClient(app, client=("127.0.0.1", 50000)),
        runtime_paths,
        authority,
    )


def _prepare_upload(client: TestClient, content: bytes = b"browser-video"):
    return client.post(
        "/api/ingest/submit",
        files={"file": ("browser_clip.mp4", content, "video/mp4")},
        data={
            "action": "prepare",
            "policy_profile": "local_ingest_facade_v1",
        },
    )


def test_router_has_one_submit_authority_and_retires_token_and_upload_routes() -> None:
    mounted = {
        (method, route.path)
        for route in ingest_module.router.routes
        for method in route.methods
    }

    assert ("POST", "/api/ingest/submit") in mounted
    assert ("GET", "/api/ingest/token") not in mounted
    assert ("POST", "/api/ingest/upload") not in mounted


def test_multipart_prepare_requires_separate_exact_confirmation_before_watchdog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    content = b"browser-video"

    prepared = _prepare_upload(client, content)

    assert prepared.status_code == 201
    payload = prepared.json()
    assert payload["status"] == "pending_confirmation"
    assert payload["confirmation_required"] is True
    assert payload["confirmation_token"]
    assert payload["confirmation_expires_at"]
    assert payload["file_sha256"] == hashlib.sha256(content).hexdigest()
    assert payload["size_bytes"] == len(content)
    assert payload["original_name"] == "browser_clip.mp4"
    assert prepared.headers["location"].endswith(
        f"/api/ingest/status/{payload['request_id']}"
    )
    assert list(runtime_paths["import_inbox"].iterdir()) == []

    record = json.loads(
        (
            runtime_paths["ingest_requests"] / f"{payload['request_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert record["status"] == "pending_confirmation"
    assert "confirmation_token" not in record
    assert record["confirmation_expires_at"] == payload["confirmation_expires_at"]
    pending_path = Path(record["pending_path"])
    assert pending_path.read_bytes() == content

    confirmed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )

    assert confirmed.status_code == 202
    confirmed_payload = confirmed.json()
    assert confirmed_payload["status"] == "staged"
    assert confirmed_payload["confirmation_token"] is None
    assert confirmed_payload["queue_depth_snapshot"] == 1
    assert len(list(runtime_paths["import_inbox"].iterdir())) == 1
    assert not pending_path.exists()

    status_payload = client.get(
        f"/api/ingest/status/{payload['request_id']}"
    ).json()
    assert status_payload["status"] == "waiting_for_watchdog"
    assert "source_path" not in status_payload
    assert "partial_path" not in status_payload
    assert "pending_path" not in status_payload
    assert "staged_path" not in status_payload
    assert "confirmation_token" not in status_payload

    reused = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )
    assert reused.status_code == 409
    assert len(list(runtime_paths["import_inbox"].iterdir())) == 1


def test_cold_start_prepare_and_confirm_create_governed_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(
        tmp_path,
        monkeypatch,
        create_runtime_paths=False,
    )
    assert not runtime_paths["ingest_requests"].exists()
    assert not runtime_paths["import_inbox"].exists()

    prepared = _prepare_upload(client, b"cold-start-video")

    assert prepared.status_code == 201
    payload = prepared.json()
    record_path = (
        runtime_paths["ingest_requests"] / f"{payload['request_id']}.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    pending_path = Path(record["pending_path"])
    assert pending_path.is_file()

    confirmed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )

    assert confirmed.status_code == 202
    assert confirmed.json()["status"] == "staged"
    assert len(list(runtime_paths["import_inbox"].iterdir())) == 1
    assert not pending_path.exists()


def test_local_path_prepare_copies_source_then_uses_same_confirm_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    source = tmp_path / "local_clip.mp4"
    source.write_bytes(b"local-video")

    prepared = client.post(
        "/api/ingest/submit",
        json={
            "action": "prepare",
            "file_path": str(source),
            "policy_profile": "local_ingest_facade_v1",
        },
    )

    assert prepared.status_code == 201
    payload = prepared.json()
    assert payload["status"] == "pending_confirmation"
    assert source.read_bytes() == b"local-video"
    assert list(runtime_paths["import_inbox"].iterdir()) == []

    confirmed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )
    assert confirmed.status_code == 202
    assert confirmed.json()["status"] == "staged"
    assert source.exists()
    assert len(list(runtime_paths["import_inbox"].iterdir())) == 1


def test_cancel_revokes_exact_token_and_removes_only_pending_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client)
    payload = prepared.json()
    record_path = (
        runtime_paths["ingest_requests"] / f"{payload['request_id']}.json"
    )
    pending_path = Path(json.loads(record_path.read_text())["pending_path"])

    canceled = client.post(
        "/api/ingest/submit",
        json={
            "action": "cancel",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )

    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert not pending_path.exists()
    assert list(runtime_paths["import_inbox"].iterdir()) == []
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "canceled"

    token_store = Path(sys.modules[MiniAgentClient.__module__].os.environ[
        "GOODQ_MINI_AGENT_HOME"
    ]) / "confirmation_tokens.json"
    tokens = json.loads(token_store.read_text(encoding="utf-8"))
    assert payload["confirmation_token"] not in tokens

    repeated = client.post(
        "/api/ingest/submit",
        json={
            "action": "cancel",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "canceled"


def test_tampered_pending_file_never_reaches_watchdog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client)
    payload = prepared.json()
    record_path = (
        runtime_paths["ingest_requests"] / f"{payload['request_id']}.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    Path(record["pending_path"]).write_bytes(b"tampered")

    confirmed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )

    assert confirmed.status_code == 409
    assert list(runtime_paths["import_inbox"].iterdir()) == []
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == (
        "integrity_failed"
    )


def test_post_authorization_replacement_is_rejected_before_watchdog_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client).json()
    real_place = ingest_module._place_pending_for_verification

    def replace_after_hidden_move(source: Path, verification_path: Path) -> None:
        real_place(source, verification_path)
        verification_path.write_bytes(b"replacement-after-authorization")

    monkeypatch.setattr(
        ingest_module,
        "_place_pending_for_verification",
        replace_after_hidden_move,
    )

    response = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": prepared["request_id"],
            "confirmation_token": prepared["confirmation_token"],
        },
    )

    assert response.status_code == 409
    assert list(runtime_paths["import_inbox"].glob("*.mp4")) == []
    record = json.loads(
        (
            runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert record["status"] == "integrity_failed"


def test_oversized_upload_fails_before_pending_or_inbox_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ingest_module,
        "get_max_upload_size",
        lambda: 4,
        raising=False,
    )
    copy_after_parse = MagicMock(
        side_effect=AssertionError("oversized file reached pending-copy stage")
    )
    monkeypatch.setattr(
        ingest_module,
        "_copy_stream_with_budget",
        copy_after_parse,
    )

    response = _prepare_upload(client, b"12345")

    assert response.status_code == 413
    copy_after_parse.assert_not_called()
    assert list(runtime_paths["import_inbox"].iterdir()) == []
    pending_dir = runtime_paths["ingest_requests"] / ".pending"
    assert not pending_dir.exists() or list(pending_dir.iterdir()) == []


def test_new_prepare_expires_abandoned_pending_request_without_status_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    first = _prepare_upload(client, b"first").json()
    ledger = ingest_module.IngestRequestLedger(runtime_paths["ingest_requests"])
    ledger.update_record(
        first["request_id"],
        confirmation_expires_at="2000-01-01T00:00:00+00:00",
    )
    real_record_lock = ingest_module._record_lock
    locked_request_ids: list[str] = []

    def track_record_lock(active_ledger, request_id):
        locked_request_ids.append(request_id)
        return real_record_lock(active_ledger, request_id)

    monkeypatch.setattr(ingest_module, "_record_lock", track_record_lock)

    second = _prepare_upload(client, b"second")

    assert second.status_code == 201
    first_record = json.loads(
        (
            runtime_paths["ingest_requests"] / f"{first['request_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert first_record["status"] == "expired"
    assert first_record["pending_path"] is None
    assert first["request_id"] in locked_request_ids


def test_pending_storage_budget_rejects_second_abandoned_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    monkeypatch.setattr(ingest_module, "get_max_pending_bytes", lambda: 5)
    first = _prepare_upload(client, b"123").json()

    second = _prepare_upload(client, b"456")

    assert second.status_code == 413
    first_record = json.loads(
        (
            runtime_paths["ingest_requests"] / f"{first['request_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert Path(first_record["pending_path"]).is_file()
    assert len(list((runtime_paths["ingest_requests"] / ".pending").iterdir())) == 1


def test_pending_storage_budget_counts_in_progress_partial_files(tmp_path: Path) -> None:
    pending_dir = tmp_path / ".pending"
    pending_dir.mkdir()
    (pending_dir / ".receiving.part").write_bytes(b"1234")
    (pending_dir / "prepared.mp4").write_bytes(b"567")

    assert ingest_module._pending_storage_bytes(pending_dir) == 7


def test_cleanup_scans_beyond_terminal_history_and_expires_receiving_artifacts(
    tmp_path: Path,
) -> None:
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    ledger = ingest_module.IngestRequestLedger(requests_dir)
    terminal_record = {
        "status": "completed",
        "created_at": "2000-01-01T00:00:00+00:00",
        "last_updated_at": "2000-01-01T00:00:00+00:00",
    }
    for index in range(1000):
        request_id = f"ingest_20000101T000000Z_{index:08x}"
        record = {"request_id": request_id, **terminal_record}
        ledger.record_path(request_id).write_text(json.dumps(record), encoding="utf-8")

    request_id = "ingest_20990101T000000Z_deadbeef"
    pending_dir = requests_dir / ".pending"
    pending_dir.mkdir()
    partial_path = pending_dir / f".{request_id}.part"
    pending_path = pending_dir / f"{request_id}__clip.mp4"
    partial_path.write_bytes(b"partial")
    pending_path.write_bytes(b"pending")
    ledger.record_path(request_id).write_text(
        json.dumps(
            {
                "request_id": request_id,
                "status": "receiving",
                "partial_path": str(partial_path),
                "pending_path": str(pending_path),
                "created_at": "2000-01-01T00:00:00+00:00",
                "last_updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    runtime_paths = {
        "import_inbox": tmp_path / "inbox",
        "processing": tmp_path / "processing",
        "processed": tmp_path / "processed",
        "failed": tmp_path / "failed",
        "watchdog_state_file": tmp_path / "watchdog.json",
    }
    for key in ("import_inbox", "processing", "processed", "failed"):
        runtime_paths[key].mkdir()

    ingest_module._recover_or_expire_incomplete_requests(ledger, runtime_paths)

    cleaned = ledger.load(request_id)
    assert cleaned is not None
    assert cleaned["status"] == "expired"
    assert not partial_path.exists()
    assert not pending_path.exists()


def test_cleanup_recovers_authorized_hidden_verification_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client).json()
    ledger = ingest_module.IngestRequestLedger(runtime_paths["ingest_requests"])
    record = ledger.load(prepared["request_id"])
    assert record is not None
    staged_name = f"{prepared['request_id']}__{record['staged_basename']}"
    staged_path = runtime_paths["import_inbox"] / staged_name
    verification_path = runtime_paths["import_inbox"] / (
        f".{prepared['request_id']}.verification.part"
    )
    os.replace(Path(record["pending_path"]), verification_path)
    ledger.update_record(
        prepared["request_id"],
        status="staging",
        staged_name=staged_name,
        staged_path=str(staged_path),
        verification_path=str(verification_path),
        confirmation_token_present=False,
    )

    ingest_module._recover_or_expire_incomplete_requests(ledger, runtime_paths)

    recovered = ledger.load(prepared["request_id"])
    assert recovered is not None
    assert recovered["status"] == "staged"
    assert staged_path.is_file()
    assert not verification_path.exists()


def test_crash_after_inbox_move_reconciles_staging_record_from_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client)
    payload = prepared.json()
    real_update = ingest_module.IngestRequestLedger.update_record

    class SimulatedCrash(BaseException):
        pass

    def crash_after_move(self, request_id, **updates):
        if updates.get("status") == "staged":
            record = self.load(request_id)
            assert record is not None
            assert Path(record["staged_path"]).exists()
            raise SimulatedCrash()
        return real_update(self, request_id, **updates)

    monkeypatch.setattr(
        ingest_module.IngestRequestLedger,
        "update_record",
        crash_after_move,
    )

    with pytest.raises(SimulatedCrash):
        client.post(
            "/api/ingest/submit",
            json={
                "action": "confirm",
                "request_id": payload["request_id"],
                "confirmation_token": payload["confirmation_token"],
            },
        )

    record_path = (
        runtime_paths["ingest_requests"] / f"{payload['request_id']}.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "staging"
    assert Path(record["staged_path"]).exists()
    resolved = ingest_module.resolve_ingest_request_status(record, runtime_paths)
    assert resolved["status"] == "waiting_for_watchdog"

    runtime_paths["watchdog_state_file"].write_text(
        json.dumps(
            {
                record["file_sha256"]: {
                    "original_name": record["staged_name"],
                    "status": "success",
                    "run_id": "run-crash-recovered",
                    "timestamp": "2026-07-11T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )
    completed = ingest_module.resolve_ingest_request_status(record, runtime_paths)
    assert completed["status"] == "completed"
    assert completed["run_id"] == "run-crash-recovered"

    processed_copy = runtime_paths["processed"] / f"PROCESSED_{record['staged_name']}"
    os.replace(Path(record["staged_path"]), processed_copy)
    monkeypatch.setattr(
        ingest_module.IngestRequestLedger,
        "update_record",
        real_update,
    )
    resumed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": payload["request_id"],
            "confirmation_token": payload["confirmation_token"],
        },
    )
    assert resumed.status_code == 202
    assert resumed.json()["status"] == "completed"
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == (
        "completed"
    )


def test_watchdog_pickup_during_final_visible_verification_reconciles_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client).json()
    real_place = ingest_module._place_staged_file

    def place_then_watchdog_pickup(source: Path, destination: Path) -> None:
        real_place(source, destination)
        os.replace(destination, runtime_paths["processing"] / destination.name)

    monkeypatch.setattr(
        ingest_module,
        "_place_staged_file",
        place_then_watchdog_pickup,
    )
    confirmed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": prepared["request_id"],
            "confirmation_token": prepared["confirmation_token"],
        },
    )

    assert confirmed.status_code == 202
    assert confirmed.json()["status"] == "processing"
    record_path = (
        runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
    )
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == (
        "processing"
    )


def test_crash_after_token_claim_resumes_same_exact_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client).json()
    real_update = ingest_module.IngestRequestLedger.update_record
    crashed = False

    class SimulatedCrash(BaseException):
        pass

    def crash_before_staging(self, request_id, **updates):
        nonlocal crashed
        if updates.get("status") == "staging" and not crashed:
            crashed = True
            raise SimulatedCrash()
        return real_update(self, request_id, **updates)

    monkeypatch.setattr(
        ingest_module.IngestRequestLedger,
        "update_record",
        crash_before_staging,
    )
    transition = {
        "action": "confirm",
        "request_id": prepared["request_id"],
        "confirmation_token": prepared["confirmation_token"],
    }

    with pytest.raises(SimulatedCrash):
        client.post("/api/ingest/submit", json=transition)

    record_path = (
        runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
    )
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == (
        "authorizing"
    )

    resumed = client.post("/api/ingest/submit", json=transition)
    assert resumed.status_code == 202
    assert resumed.json()["status"] == "staged"
    assert len(list(runtime_paths["import_inbox"].iterdir())) == 1


def test_crash_after_token_revoke_resumes_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client).json()
    real_update = ingest_module.IngestRequestLedger.update_record
    crashed = False

    class SimulatedCrash(BaseException):
        pass

    def crash_before_canceled(self, request_id, **updates):
        nonlocal crashed
        if updates.get("status") == "canceled" and not crashed:
            crashed = True
            raise SimulatedCrash()
        return real_update(self, request_id, **updates)

    monkeypatch.setattr(
        ingest_module.IngestRequestLedger,
        "update_record",
        crash_before_canceled,
    )
    transition = {
        "action": "cancel",
        "request_id": prepared["request_id"],
        "confirmation_token": prepared["confirmation_token"],
    }

    with pytest.raises(SimulatedCrash):
        client.post("/api/ingest/submit", json=transition)
    record_path = (
        runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
    )
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == (
        "canceling"
    )

    resumed = client.post("/api/ingest/submit", json=transition)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "canceled"
    assert list(runtime_paths["import_inbox"].iterdir()) == []


def test_transient_pending_delete_failure_resumes_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _app_client(tmp_path, monkeypatch)
    prepared = _prepare_upload(client).json()
    record_path = (
        runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
    )
    pending_path = Path(
        json.loads(record_path.read_text(encoding="utf-8"))["pending_path"]
    )
    real_unlink = Path.unlink
    failed_once = False

    def fail_pending_unlink_once(path, *args, **kwargs):
        nonlocal failed_once
        if path == pending_path and not failed_once:
            failed_once = True
            raise OSError("transient delete failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_pending_unlink_once)
    transition = {
        "action": "cancel",
        "request_id": prepared["request_id"],
        "confirmation_token": prepared["confirmation_token"],
    }

    failed = client.post("/api/ingest/submit", json=transition)
    assert failed.status_code == 500
    assert json.loads(record_path.read_text(encoding="utf-8"))["status"] == (
        "cancel_failed"
    )
    assert pending_path.is_file()

    resumed = client.post("/api/ingest/submit", json=transition)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "canceled"
    assert not pending_path.exists()


def test_submit_openapi_documents_json_and_multipart_bodies() -> None:
    app = FastAPI()
    app.include_router(ingest_module.router)
    operation = app.openapi()["paths"]["/api/ingest/submit"]["post"]

    content = operation["requestBody"]["content"]
    assert {"application/json", "multipart/form-data"} <= set(content)
    assert content["application/json"]["schema"]["discriminator"]["propertyName"] == (
        "action"
    )
    confirm_schema = content["application/json"]["schema"]["oneOf"][1]
    assert confirm_schema["properties"]["request_id"]["pattern"]
    upload_schema = content["multipart/form-data"]["schema"]
    assert upload_schema["properties"]["file"]["format"] == "binary"
    assert set(operation["responses"]) >= {
        "200",
        "201",
        "202",
        "400",
        "403",
        "404",
        "409",
        "410",
        "413",
        "415",
        "422",
        "500",
    }


def test_retro_stage_media_requires_visible_confirmation_and_truthful_copy() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root / "ui" / "retro_console_v1" / "static" / "js" / "retro.js"
    ).read_text(encoding="utf-8")
    page = (repo_root / "ui" / "retro_console_v1" / "index.html").read_text(
        encoding="utf-8"
    )
    first_run = (repo_root / "docs" / "guides" / "FIRST_RUN.md").read_text(
        encoding="utf-8"
    )

    assert "/api/ingest/token" not in script
    assert "/api/ingest/upload" not in script
    assert 'formData.append("action", "prepare")' in script
    assert 'action: "confirm"' in script
    assert 'action: "cancel"' in script
    assert "window.confirm(" in script
    assert "Awaiting confirmation" in script
    assert "Request staged" in script
    assert "xhr.status !== 201 && xhr.status !== 200" in script
    assert 'prepared.status === "duplicate"' in script
    assert "Already processed" in script
    assert "Ingestion starting" not in script
    assert "Stage Media" in page
    assert "Stage Media" in first_run
    assert "confirm" in first_run.lower()
