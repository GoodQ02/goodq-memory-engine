from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import summary as summary_route
from api.utils.action_jobs import ActionJobLedger


VALID_HASH = "1234567890abcdef1234567890abcdef"


class StubSummaryAuthority:
    def __init__(self):
        self.authorize_calls = []
        self.revoke_calls = []
        self.external_calls = []
        self._lock = Lock()

    def authorize_action(self, **kwargs):
        with self._lock:
            self.authorize_calls.append(kwargs)
        if kwargs.get("confirm"):
            return (
                {
                    "schema": "goodq.tool-envelope.v1",
                    "request_id": "authorization-request-1",
                    "status": "ok",
                    "result": {"allowed": True},
                    "errors": [],
                },
                0,
            )
        return (
            {
                "schema": "goodq.tool-envelope.v1",
                "request_id": "authorization-request-1",
                "status": "needs_confirmation",
                "result": {
                    "confirmation_token": "confirmation-token-1",
                    "confirmation_expires_at": "2026-07-12T23:59:59Z",
                },
                "errors": [],
            },
            3,
        )

    def revoke_action_authorization(self, **kwargs):
        self.revoke_calls.append(kwargs)
        return ({"status": "ok", "errors": []}, 0)

    def record_external_execution_outcome(self, **kwargs):
        self.external_calls.append(kwargs)
        return {"audit_status": "recorded", "error_codes": []}

@pytest.fixture
def client() -> TestClient:
    return TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture(autouse=True)
def mock_db_paths(tmp_path):
    """Create temporary DB files and patch paths config to prevent using real databases."""
    kg_db = tmp_path / "knowledge_graph.db"
    kg_db.write_text("")  # ensure kg_db.exists() is True
    
    mem_db = tmp_path / "memory.db"
    mem_db.write_text("")  # ensure mem_db.exists() is True
    
    # Setup patch for _get_kg_db_path and config loader
    with patch("api.routes.summary._get_kg_db_path", return_value=kg_db), \
         patch("steps.common.config_loader.load_configs") as mock_load:
        
        mock_load.return_value = {
            "paths": {
                "data_root": str(tmp_path / "GoodQ_Data"),
                "db_path": str(mem_db),
                "knowledge_graph_db": str(kg_db)
            },
            "llm": {
                "features": {
                    "video_summarization": True
                },
                "api_url": "http://localhost:1234/v1/chat/completions",
                "model": "test-model"
            }
        }
        yield kg_db, mem_db


def _mock_existing_video(monkeypatch):
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    monkeypatch.setattr("sqlite3.connect", lambda *_args, **_kwargs: mock_conn)
    return mock_conn


def _job_ledger(tmp_path) -> ActionJobLedger:
    return ActionJobLedger(tmp_path / "GoodQ_Data" / "control" / "action_jobs")


def test_capabilities_endpoint(client) -> None:
    """Verify the summary capabilities endpoint returns correct LLM feature flags."""
    resp = client.get("/api/summary/capabilities")
    assert resp.status_code == 200
    assert resp.json() == {"video_summarization_enabled": True}


def test_invalid_hash_validation(client) -> None:
    """Verify endpoints validate hash patterns and return 400 Bad Request on malformed inputs."""
    # GET endpoint
    resp_get = client.get("/api/summary/video/not-a-hash")
    assert resp_get.status_code == 400
    assert "Invalid video hash format" in resp_get.json()["detail"]

    # Status endpoint
    resp_status = client.get("/api/summary/video/not-a-hash/status")
    assert resp_status.status_code == 400
    assert "Invalid video hash format" in resp_status.json()["detail"]

    # POST generate endpoint
    resp_post = client.post(
        "/api/summary/video/not-a-hash/generate", json={"action": "prepare"}
    )
    assert resp_post.status_code == 400
    assert "Invalid video hash format" in resp_post.json()["detail"]


@patch("sqlite3.connect")
def test_missing_video_checks(mock_connect, client) -> None:
    """Verify endpoints return 404 Not Found if video hash does not exist in the database."""
    # Mock database to return no matching video row
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock scenes check: returns None (video not in KG DB)
    mock_cursor.execute.return_value.fetchone.return_value = None
    mock_conn.execute.return_value.fetchone.return_value = None

    valid_missing_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"

    # POST Generate missing video
    resp_post = client.post(
        f"/api/summary/video/{valid_missing_hash}/generate",
        json={"action": "prepare"},
    )
    assert resp_post.status_code == 404
    assert "not found in database" in resp_post.json()["detail"]

    # GET missing video summary
    resp_get = client.get(f"/api/summary/video/{valid_missing_hash}")
    assert resp_get.status_code == 404
    assert "Video summary not found" in resp_get.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        [],
        {"action": ""},
        {"action": "prepare", "job_id": "job-extra"},
        {"action": "confirm"},
        {
            "action": "confirm",
            "job_id": "",
            "confirmation_token": "confirmation-token-1",
        },
        {
            "action": "confirm",
            "job_id": "job_" + "a" * 32,
            "confirmation_token": "   ",
        },
        {
            "action": "confirm",
            "job_id": "job_" + "a" * 32,
            "confirmation_token": "confirmation-token-1",
            "extra": True,
        },
    ],
)
def test_generate_rejects_non_exact_action_bodies(
    body, client, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    monkeypatch.setattr(
        "requests.get", lambda *_args, **_kwargs: MagicMock(status_code=200)
    )
    monkeypatch.setattr(
        "steps.video_summarizer.step.run_step",
        lambda *_args, **_kwargs: {"success": True},
    )

    kwargs = {} if body is None else {"json": body}
    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        **kwargs,
    )

    assert response.status_code == 422


def test_prepare_returns_token_once_and_persists_only_fingerprint(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(
        summary_route,
        "_get_summary_authority",
        lambda _cfg: authority,
        raising=False,
    )

    def reject_network(*_args, **_kwargs):
        raise AssertionError("prepare attempted an LLM/network preflight")

    def reject_worker(*_args, **_kwargs):
        raise AssertionError("prepare attempted to execute the summarizer")

    monkeypatch.setattr("requests.get", reject_network)
    monkeypatch.setattr("steps.video_summarizer.step.run_step", reject_worker)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmation_token"] == "confirmation-token-1"
    assert payload["job"]["state"] == "pending_confirmation"
    assert "owner_instance" not in payload["job"]
    assert authority.authorize_calls == [
        {
            "prompt": "Prepare one exact video summary",
            "mode": "ops",
            "tool_name": "generate_video_summary",
            "tool_args": {
                "job_id": payload["job"]["job_id"],
                "video_hash": VALID_HASH,
            },
        }
    ]

    ledger = _job_ledger(mock_db_paths[0].parent)
    persisted = ledger.load(payload["job"]["job_id"])
    assert persisted["token_fingerprint"] == hashlib.sha256(
        b"confirmation-token-1"
    ).hexdigest()
    assert persisted["authorization_request_id"] == "authorization-request-1"
    serialized = ledger.record_path(persisted["job_id"]).read_text(encoding="utf-8")
    assert "confirmation-token-1" not in serialized


def test_prepare_existing_active_job_conflicts_without_reissuing_token(
    client, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    first = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )
    second = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "active_job_exists"
    assert detail["job"]["job_id"] == first.json()["job"]["job_id"]
    assert "confirmation_token" not in detail
    assert "token_fingerprint" not in detail["job"]
    assert "authorization_request_id" not in detail["job"]
    assert len(authority.authorize_calls) == 1


def test_concurrent_prepare_has_one_token_issuer(client, monkeypatch) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    def prepare():
        return client.post(
            f"/api/summary/video/{VALID_HASH}/generate",
            json={"action": "prepare"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _unused: prepare(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert len(authority.authorize_calls) == 1


def test_prepare_authorization_failure_is_terminal(client, mock_db_paths, monkeypatch) -> None:
    _mock_existing_video(monkeypatch)

    class DenyingAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-denied",
                    "status": "denied",
                    "result": {"allowed": False},
                    "errors": [{"code": "policy_denied", "message": "Denied"}],
                },
                2,
            )

    authority = DenyingAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )

    assert response.status_code == 503
    records = _job_ledger(mock_db_paths[0].parent).list_records(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
    )
    assert len(records) == 1
    assert records[0]["state"] == "failed"
    assert records[0]["outcome"]["code"] == "authorization_prepare_failed"


def test_prepare_authority_initialization_failure_is_terminal_and_retryable(
    client, mock_db_paths, monkeypatch, caplog
) -> None:
    _mock_existing_video(monkeypatch)

    def fail_authority(_cfg):
        raise RuntimeError("confirmation-token-private C:\\private\\authority")

    monkeypatch.setattr(summary_route, "_get_summary_authority", fail_authority)

    failed = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )

    assert failed.status_code == 503
    ledger = _job_ledger(mock_db_paths[0].parent)
    failed_record = ledger.latest(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
    )
    assert failed_record["state"] == "failed"
    assert failed_record["outcome"]["code"] == "authorization_prepare_failed"
    assert "confirmation-token-private" not in caplog.text
    assert "private\\authority" not in caplog.text

    monkeypatch.setattr(
        summary_route, "_get_summary_authority", lambda _cfg: StubSummaryAuthority()
    )
    retried = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )

    assert retried.status_code == 200
    assert retried.json()["job"]["job_id"] != failed_record["job_id"]


def test_prepare_evidence_failure_revokes_issued_token(
    client, mock_db_paths, monkeypatch, caplog
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    ledger = _job_ledger(mock_db_paths[0].parent)
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)
    monkeypatch.setattr(
        ledger,
        "compare_and_update",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("confirmation-token-1 C:\\private\\job.json")
        ),
    )

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )

    assert response.status_code == 503
    record = ledger.latest(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
    )
    assert record["state"] == "failed"
    assert authority.revoke_calls == [
        {
            "prompt": "Revoke unpersisted video summary authorization",
            "mode": "ops",
            "tool_name": "generate_video_summary",
            "tool_args": {"job_id": record["job_id"], "video_hash": VALID_HASH},
            "confirmation_token": "confirmation-token-1",
        }
    ]
    assert "confirmation-token-1" not in caplog.text
    assert "private\\job.json" not in caplog.text


def _prepare_summary(client):
    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={"action": "prepare"},
    )
    assert response.status_code == 200
    return response.json()


def test_wrong_confirmation_token_leaves_pending_job_unchanged(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    prepared = _prepare_summary(client)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": prepared["job"]["job_id"],
            "confirmation_token": "wrong-token",
        },
    )

    assert response.status_code == 403
    persisted = _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])
    assert persisted["state"] == "pending_confirmation"
    assert len(authority.authorize_calls) == 1


@pytest.mark.parametrize("padded_field", ["job_id", "confirmation_token"])
def test_confirmation_values_are_not_whitespace_normalized(
    padded_field, client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    async def worker(*_args):
        return None

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)
    prepared = _prepare_summary(client)
    body = {
        "action": "confirm",
        "job_id": prepared["job"]["job_id"],
        "confirmation_token": "confirmation-token-1",
    }
    body[padded_field] = f" {body[padded_field]} "

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json=body,
    )

    assert response.status_code in {403, 404}
    persisted = _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])
    assert persisted["state"] == "pending_confirmation"
    assert len(authority.authorize_calls) == 1


def test_confirm_claims_exact_scope_and_queues_once(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    worker_calls = []
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    async def worker(*args):
        worker_calls.append(args)

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)
    prepared = _prepare_summary(client)
    job_id = prepared["job"]["job_id"]

    first = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": job_id,
            "confirmation_token": "confirmation-token-1",
        },
    )
    second = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": job_id,
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert first.status_code == 202
    assert first.json()["job"]["state"] == "queued"
    assert second.status_code == 409
    assert len(worker_calls) == 1
    assert worker_calls[0][:2] == (job_id, VALID_HASH)
    assert worker_calls[0][2]["paths"]["data_root"] == str(
        mock_db_paths[0].parent / "GoodQ_Data"
    )
    assert authority.authorize_calls[1] == {
        "prompt": "Confirm one exact video summary",
        "mode": "ops",
        "tool_name": "generate_video_summary",
        "tool_args": {"job_id": job_id, "video_hash": VALID_HASH},
        "confirm": True,
        "confirmation_token": "confirmation-token-1",
    }


def test_confirm_requires_current_api_owner(client, mock_db_paths, monkeypatch) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    ledger = _job_ledger(mock_db_paths[0].parent)
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)
    record = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance="prior-api-owner",
    )
    ledger.compare_and_update(
        record["job_id"],
        expected_state="pending_confirmation",
        token_fingerprint=hashlib.sha256(b"confirmation-token-1").hexdigest(),
        authorization_request_id="authorization-request-1",
    )

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": record["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 409
    assert ledger.load(record["job_id"])["state"] == "pending_confirmation"
    assert authority.authorize_calls == []


def test_expired_confirmation_becomes_terminal(client, mock_db_paths, monkeypatch) -> None:
    _mock_existing_video(monkeypatch)

    class ExpiringAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-1",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [
                        {"code": "token_expired", "message": "Confirmation expired"}
                    ],
                },
                1,
            )

    authority = ExpiringAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    prepared = _prepare_summary(client)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": prepared["job"]["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 409
    persisted = _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])
    assert persisted["state"] == "expired"
    assert persisted["outcome"] == {
        "code": "authorization_expired",
        "message": "Video summary authorization expired",
    }


def test_confirm_authority_initialization_failure_is_terminal_without_worker(
    client, mock_db_paths, monkeypatch, caplog
) -> None:
    _mock_existing_video(monkeypatch)
    monkeypatch.setattr(
        summary_route, "_get_summary_authority", lambda _cfg: StubSummaryAuthority()
    )
    prepared = _prepare_summary(client)
    worker_calls = []

    async def worker(*args):
        worker_calls.append(args)

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)

    def fail_authority(_cfg):
        raise RuntimeError("confirmation-token-private C:\\private\\authority")

    monkeypatch.setattr(summary_route, "_get_summary_authority", fail_authority)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": prepared["job"]["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 409
    persisted = _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])
    assert persisted["state"] == "failed"
    assert persisted["outcome"] == {
        "code": "authorization_failed",
        "message": "Video summary authorization failed",
    }
    assert worker_calls == []
    assert "confirmation-token-private" not in caplog.text
    assert "private\\authority" not in caplog.text


def _queued_summary_job(ledger: ActionJobLedger):
    record = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance=summary_route._SUMMARY_OWNER_INSTANCE,
    )
    ledger.compare_and_update(
        record["job_id"],
        expected_state="pending_confirmation",
        token_fingerprint=hashlib.sha256(b"confirmation-token-1").hexdigest(),
        authorization_request_id="authorization-request-1",
    )
    ledger.transition(
        record["job_id"],
        expected_states="pending_confirmation",
        new_state="authorizing",
    )
    return ledger.transition(
        record["job_id"],
        expected_states="authorizing",
        new_state="queued",
    )


@pytest.mark.parametrize(
    ("worker_result", "expected_state", "expected_code", "audit_status"),
    [
        (
            {"success": True, "summary": "private model output"},
            "succeeded",
            "summary_generated",
            "succeeded",
        ),
        (
            {"success": False, "error": "private backend detail"},
            "failed",
            "summary_generation_failed",
            "failed",
        ),
        (
            {"success": 1},
            "failed",
            "summary_generation_failed",
            "failed",
        ),
    ],
)
def test_summary_worker_records_truthful_returned_outcome(
    worker_result,
    expected_state,
    expected_code,
    audit_status,
    mock_db_paths,
    monkeypatch,
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    job = _queued_summary_job(ledger)

    class InspectingAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            assert ledger.load(job["job_id"])["state"] == "running"
            return super().record_external_execution_outcome(**kwargs)

    authority = InspectingAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(
        "steps.video_summarizer.step.run_step", lambda _cfg, _hash: worker_result
    )
    cfg = {
        "paths": {"data_root": str(mock_db_paths[0].parent / "GoodQ_Data")}
    }

    asyncio.run(summary_route._generate_summary_worker(job["job_id"], VALID_HASH, cfg))

    persisted = ledger.load(job["job_id"])
    assert persisted["state"] == expected_state
    assert persisted["outcome"]["code"] == expected_code
    assert persisted["audit_status"] == "recorded"
    assert "private" not in json.dumps(persisted)
    assert authority.external_calls == [
        {
            "operation": "generate_video_summary",
            "arguments": {"job_id": job["job_id"], "video_hash": VALID_HASH},
            "request_id": "authorization-request-1",
            "mode": "ops",
            "status": audit_status,
            "return_code": 0 if audit_status == "succeeded" else 1,
            "duration_ms": authority.external_calls[0]["duration_ms"],
            "side_effect_report": {
                "mutated": audit_status == "succeeded",
                "targets": [f"video-summary:{job['job_id']}"],
            },
            "error_codes": [] if audit_status == "succeeded" else [expected_code],
        }
    ]
    assert isinstance(authority.external_calls[0]["duration_ms"], int)
    assert authority.external_calls[0]["duration_ms"] >= 0


def test_summary_worker_exception_is_failed_and_sanitized(
    mock_db_paths, monkeypatch
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    job = _queued_summary_job(ledger)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    def fail_worker(*_args):
        raise RuntimeError("private path and backend response")

    monkeypatch.setattr("steps.video_summarizer.step.run_step", fail_worker)
    cfg = {
        "paths": {"data_root": str(mock_db_paths[0].parent / "GoodQ_Data")}
    }

    asyncio.run(summary_route._generate_summary_worker(job["job_id"], VALID_HASH, cfg))

    persisted = ledger.load(job["job_id"])
    assert persisted["state"] == "failed"
    assert persisted["outcome"] == {
        "code": "summary_generation_error",
        "message": "Video summary generation raised an error",
    }
    assert "private" not in json.dumps(persisted)
    assert authority.external_calls[0]["status"] == "failed"


def test_summary_worker_audit_failure_preserves_success(
    mock_db_paths, monkeypatch
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    job = _queued_summary_job(ledger)

    class FailingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            self.external_calls.append(kwargs)
            return {"audit_status": "failed", "error_codes": ["audit_log_error"]}

    authority = FailingAuditAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(
        "steps.video_summarizer.step.run_step",
        lambda *_args: {"success": True, "summary": "private model output"},
    )
    cfg = {
        "paths": {"data_root": str(mock_db_paths[0].parent / "GoodQ_Data")}
    }

    asyncio.run(summary_route._generate_summary_worker(job["job_id"], VALID_HASH, cfg))

    persisted = ledger.load(job["job_id"])
    assert persisted["state"] == "succeeded"
    assert persisted["audit_status"] == "failed"
    assert persisted["outcome"]["code"] == "summary_generated"


def test_summary_status_returns_not_started_without_creating_job(
    client, mock_db_paths
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    before = list(ledger.root_dir.glob("job_*.json"))

    response = client.get(f"/api/summary/video/{VALID_HASH}/status")

    assert response.status_code == 200
    assert response.json() == {"status": "not_started", "job": None}
    assert list(ledger.root_dir.glob("job_*.json")) == before


def test_summary_status_returns_latest_or_exact_scoped_job_passively(
    client, mock_db_paths, monkeypatch
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)
    older = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance="api-owner",
    )
    older = ledger.transition(
        older["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
        outcome={"code": "old_failure", "message": "Older summary job failed"},
    )
    latest = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance="api-owner",
    )
    latest_path = ledger.record_path(latest["job_id"])
    exact_before = latest_path.read_bytes()

    latest_response = client.get(f"/api/summary/video/{VALID_HASH}/status")
    exact_response = client.get(
        f"/api/summary/video/{VALID_HASH}/status", params={"job_id": older["job_id"]}
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["status"] == "pending_confirmation"
    assert latest_response.json()["job"]["job_id"] == latest["job_id"]
    assert exact_response.status_code == 200
    assert exact_response.json()["status"] == "failed"
    assert exact_response.json()["job"]["job_id"] == older["job_id"]
    for response in (latest_response, exact_response):
        serialized = json.dumps(response.json())
        assert "owner_instance" not in serialized
        assert "token_fingerprint" not in serialized
        assert "authorization_request_id" not in serialized
    assert latest_path.read_bytes() == exact_before


def test_summary_status_rejects_job_from_other_scope(
    client, mock_db_paths, monkeypatch
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)
    other = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": "abcdefabcdefabcdefabcdefabcdef12"},
        owner_instance="api-owner",
    )

    response = client.get(
        f"/api/summary/video/{VALID_HASH}/status", params={"job_id": other["job_id"]}
    )

    assert response.status_code == 404


@patch("sqlite3.connect")
def test_get_video_summary_success(mock_connect, client) -> None:
    """Verify that GET /video/{video_hash} parses and returns the persisted summary & provenance."""
    valid_hash = "abcdefabcdefabcdefabcdefabcdef12"
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock master table check: summaries table exists
    mock_cursor.fetchone.side_effect = [("summaries",)]
    
    # Mock summaries row payload
    payload = json.dumps({
        "video_hash": valid_hash,
        "summary": "This is a great test summary.",
        "method": "llm",
        "provenance": {
            "model_backend": "test-model (http://localhost:1234/v1/chat/completions)",
            "prompt_version": "v1.0.0",
            "timestamp": "2026-06-13T00:00:00Z"
        }
    })
    
    mock_cursor.fetchall.return_value = [(payload, "2026-06-13 00:00:00")]
    
    resp = client.get(f"/api/summary/video/{valid_hash}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_hash"] == valid_hash
    assert data["summary"] == "This is a great test summary."
    assert data["method"] == "llm"
    assert data["provenance"]["model_backend"] == "test-model (http://localhost:1234/v1/chat/completions)"
