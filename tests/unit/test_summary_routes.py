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
from api.utils.action_jobs import ActionJobLedger, ActionJobTransitionError
from lib import summary_aggregator


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


def _collection_payload(*, name: str = "Private family highlights") -> dict:
    return {
        "name": name,
        "description": "Private operator description",
        "collection_type": "manual_playlist",
        "query_params": {"person": "Joe"},
        "scene_refs": [{"video_id": "video-1", "scene_id": "scene-1"}],
        "operator_note": "Private operator note",
    }


def _prepare_collection(client: TestClient, payload: dict) -> dict:
    response = client.post(
        "/api/summary/collections",
        json={"action": "prepare", "collection": payload},
    )
    assert response.status_code == 200
    return response.json()


def _confirm_collection_body(prepared: dict, payload: dict) -> dict:
    return {
        "action": "confirm",
        "action_id": prepared["action_id"],
        "epoch_id": prepared["epoch_id"],
        "payload_sha256": prepared["payload_sha256"],
        "confirmation_token": prepared["confirmation_token"],
        "collection": payload,
    }


def _create_collection_for_delete(db_path: Path) -> dict:
    return summary_aggregator.add_collection(
        db_path,
        {
            "name": "Delete target",
            "description": "Preserved after soft delete",
            "collection_type": "manual_playlist",
            "query_params": {},
            "scene_refs": [],
            "operator_note": "Created for delete test",
        },
    )


def _prepare_collection_delete(client: TestClient, collection_id: str) -> dict:
    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection_id}",
        json={"action": "prepare"},
    )
    assert response.status_code == 200
    return response.json()


def _confirm_collection_delete_body(prepared: dict) -> dict:
    return {
        "action": "confirm",
        "job_id": prepared["job"]["job_id"],
        "epoch_id": prepared["job"]["scope"]["epoch_id"],
        "expected_record_sha256": prepared["job"]["scope"][
            "expected_record_sha256"
        ],
        "confirmation_token": prepared["confirmation_token"],
    }


def test_collection_prepare_is_write_free_and_uses_digest_only_scope(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()

    response = client.post(
        "/api/summary/collections",
        json={"action": "prepare", "collection": payload},
    )

    assert response.status_code == 200
    prepared = response.json()
    assert prepared["success"] is True
    assert re.fullmatch(r"action_[0-9a-f]{32}", prepared["action_id"])
    assert prepared["epoch_id"] == mock_db_paths[0].parent.name
    assert re.fullmatch(r"[0-9a-f]{64}", prepared["payload_sha256"])
    assert prepared["confirmation_token"] == "confirmation-token-1"
    assert "Private family highlights" not in response.text
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()
    assert authority.authorize_calls == [
        {
            "prompt": "Prepare one exact summary collection create",
            "mode": "ops",
            "tool_name": "create_summary_collection",
            "tool_args": {
                "action_id": prepared["action_id"],
                "epoch_id": prepared["epoch_id"],
                "payload_sha256": prepared["payload_sha256"],
            },
        }
    ]


def test_collection_prepare_requires_authoritative_epoch_database(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    mock_db_paths[0].unlink()

    response = client.post(
        "/api/summary/collections",
        json={"action": "prepare", "collection": _collection_payload()},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection epoch database not initialized"
    assert authority.authorize_calls == []
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


@pytest.mark.parametrize(
    "body",
    [
        {"action": "prepare", "collection": _collection_payload(), "extra": True},
        {
            "action": "prepare",
            "collection": {**_collection_payload(), "unsupported": "private"},
        },
    ],
)
def test_collection_prepare_rejects_extra_fields_before_authority_or_write(
    body, client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    response = client.post("/api/summary/collections", json=body)

    assert response.status_code == 422
    assert authority.authorize_calls == []
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_payload_canonicalization_equates_omitted_and_explicit_defaults(
    client, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    minimal = _prepare_collection(client, {"name": "Canonical collection"})
    explicit = _prepare_collection(
        client,
        {
            "name": "Canonical collection",
            "description": None,
            "collection_type": "manual_playlist",
            "query_params": {},
            "scene_refs": [],
            "operator_note": None,
        },
    )

    assert minimal["payload_sha256"] == explicit["payload_sha256"]


@pytest.mark.parametrize(
    "collection",
    [
        {"name": "   "},
        {"name": "Noncanonical", "query_params": {"score": float("nan")}},
    ],
)
def test_collection_prepare_rejects_noncanonical_payload_before_authority(
    collection, client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    encoded = json.dumps(
        {"action": "prepare", "collection": collection},
        allow_nan=True,
    )

    response = client.post(
        "/api/summary/collections",
        content=encoded,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert authority.authorize_calls == []
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_prepare_revokes_token_when_authority_evidence_is_invalid(
    client, mock_db_paths, monkeypatch
) -> None:
    class InvalidEvidenceAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "private\\invalid-request",
                    "status": "needs_confirmation",
                    "result": {"confirmation_token": "confirmation-token-private"},
                    "errors": [],
                },
                3,
            )

    authority = InvalidEvidenceAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    response = client.post(
        "/api/summary/collections",
        json={"action": "prepare", "collection": _collection_payload()},
    )

    assert response.status_code == 503
    assert "confirmation-token-private" not in response.text
    assert authority.revoke_calls == [
        {
            "prompt": "Revoke unreturned summary collection authorization",
            "mode": "ops",
            "tool_name": "create_summary_collection",
            "tool_args": authority.authorize_calls[0]["tool_args"],
            "confirmation_token": "confirmation-token-private",
        }
    ]
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_confirm_rederives_scope_persists_receipt_and_audits(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["action_id"] == prepared["action_id"]
    assert result["audit_status"] == "recorded"
    assert "confirmation-token-1" not in response.text
    assert "authorization-request-1" not in response.text
    assert set(result["collection"]["history"][0]) == {
        "action",
        "timestamp_utc",
        "operator_note",
    }
    stored = summary_aggregator.load_collections(mock_db_paths[0])["collections"]
    assert len(stored) == 1
    assert stored[0]["history"][0] == {
        "action": "create",
        "timestamp_utc": stored[0]["history"][0]["timestamp_utc"],
        "operator_note": payload["operator_note"],
        "action_id": prepared["action_id"],
        "payload_sha256": prepared["payload_sha256"],
        "authorization_request_id": "authorization-request-1",
    }
    exact_scope = {
        "action_id": prepared["action_id"],
        "epoch_id": prepared["epoch_id"],
        "payload_sha256": prepared["payload_sha256"],
    }
    assert authority.authorize_calls[1] == {
        "prompt": "Confirm one exact summary collection create",
        "mode": "ops",
        "tool_name": "create_summary_collection",
        "tool_args": exact_scope,
        "confirm": True,
        "confirmation_token": "confirmation-token-1",
    }
    assert authority.external_calls == [
        {
            "operation": "create_summary_collection",
            "arguments": exact_scope,
            "request_id": "authorization-request-1",
            "mode": "ops",
            "status": "succeeded",
            "return_code": 0,
            "duration_ms": authority.external_calls[0]["duration_ms"],
            "side_effect_report": {
                "mutated": True,
                "targets": [f"summary-collection:create:{prepared['action_id']}"],
            },
            "error_codes": [],
        }
    ]


def test_collection_confirm_rechecks_authoritative_epoch_database(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)
    mock_db_paths[0].unlink()

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection epoch database not initialized"
    assert len(authority.authorize_calls) == 1
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_confirm_rejects_changed_payload_before_authority_or_write(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)
    changed = _collection_payload(name="Changed after prepare")

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, changed),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Collection confirmation scope mismatch"
    assert len(authority.authorize_calls) == 1
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


@pytest.mark.parametrize(
    ("field", "replacement", "expected_status"),
    [
        ("epoch_id", "epoch_other", 409),
        ("payload_sha256", "b" * 64, 409),
        ("action_id", "../private", 422),
    ],
)
def test_collection_confirm_rejects_tampered_scope_before_authority(
    field, replacement, expected_status, client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)
    body = _confirm_collection_body(prepared, payload)
    body[field] = replacement

    response = client.post("/api/summary/collections", json=body)

    assert response.status_code == expected_status
    assert len(authority.authorize_calls) == 1
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


@pytest.mark.parametrize(
    ("error_code", "expected_detail"),
    [
        ("token_expired", "Collection authorization expired"),
        ("wrong_operation", "Collection authorization failed"),
        ("token_already_used", "Collection authorization recovery failed"),
    ],
)
def test_collection_confirm_authority_failure_is_write_free_and_sanitized(
    error_code, expected_detail, client, mock_db_paths, monkeypatch
) -> None:
    class RejectingAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-2",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [
                        {
                            "code": error_code,
                            "message": "confirmation-token-private private\\path",
                        }
                    ],
                },
                1,
            )

    authority = RejectingAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == expected_detail
    assert "confirmation-token-private" not in response.text
    assert "private\\path" not in response.text
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_confirm_rejects_malformed_authority_envelope_safely(
    client, mock_db_paths, monkeypatch
) -> None:
    class MalformedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return None, 0

    authority = MalformedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Collection authorization unavailable"
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_confirm_recovers_only_from_exact_persisted_receipt(
    client, mock_db_paths, monkeypatch
) -> None:
    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-retry",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_already_used", "message": "Used"}],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)
    summary_aggregator.add_collection(
        mock_db_paths[0],
        payload,
        mutation_evidence={
            "action_id": prepared["action_id"],
            "payload_sha256": prepared["payload_sha256"],
            "authorization_request_id": "authorization-request-original",
        },
    )

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 200
    assert response.json()["recovered"] is True
    assert len(summary_aggregator.load_collections(mock_db_paths[0])["collections"]) == 1
    assert authority.external_calls[0]["request_id"] == "authorization-request-original"


@pytest.mark.parametrize("wrong_evidence", ["action", "digest", "epoch"])
def test_collection_confirm_recovery_rejects_wrong_persisted_receipt(
    wrong_evidence, client, mock_db_paths, monkeypatch
) -> None:
    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-retry",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_already_used", "message": "Used"}],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)
    persisted = summary_aggregator.add_collection(
        mock_db_paths[0],
        payload,
        mutation_evidence={
            "action_id": (
                "action_00000000000000000000000000000000"
                if wrong_evidence == "action"
                else prepared["action_id"]
            ),
            "payload_sha256": (
                "b" * 64
                if wrong_evidence == "digest"
                else prepared["payload_sha256"]
            ),
            "authorization_request_id": "authorization-request-original",
        },
    )
    if wrong_evidence == "epoch":
        collections_file = mock_db_paths[0].parent / "saved_collections.json"
        data = json.loads(collections_file.read_text(encoding="utf-8"))
        data["collections"][0]["source_epoch"] = "epoch_other"
        collections_file.write_text(json.dumps(data), encoding="utf-8")

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Collection authorization recovery failed"
    loaded = summary_aggregator.load_collections(mock_db_paths[0])["collections"]
    assert [item["collection_id"] for item in loaded] == [persisted["collection_id"]]
    assert authority.external_calls == []


def test_collection_post_effect_audit_failure_preserves_success(
    client, mock_db_paths, monkeypatch
) -> None:
    class FailingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            self.external_calls.append(kwargs)
            return {"audit_status": "failed", "error_codes": ["audit_log_error"]}

    authority = FailingAuditAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 200
    assert response.json()["audit_status"] == "failed"
    assert len(summary_aggregator.load_collections(mock_db_paths[0])["collections"]) == 1


def test_collection_post_effect_audit_exception_preserves_success(
    client, mock_db_paths, monkeypatch
) -> None:
    class RaisingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            self.external_calls.append(kwargs)
            raise RuntimeError("confirmation-token-private private\\audit.json")

    authority = RaisingAuditAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)

    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 200
    assert response.json()["audit_status"] == "failed"
    assert "confirmation-token-private" not in response.text
    assert len(summary_aggregator.load_collections(mock_db_paths[0])["collections"]) == 1


def test_concurrent_collection_confirms_create_at_most_one_receipt(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)
    body = _confirm_collection_body(prepared, payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _unused: client.post("/api/summary/collections", json=body),
                range(2),
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 500]
    stored = summary_aggregator.load_collections(mock_db_paths[0])["collections"]
    assert len(stored) == 1
    assert stored[0]["history"][0]["action_id"] == prepared["action_id"]


def test_collection_store_failure_is_sanitized_and_audited_without_mutation(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    payload = _collection_payload()
    prepared = _prepare_collection(client, payload)

    def fail_store(*_args, **_kwargs):
        raise RuntimeError("confirmation-token-private private\\saved_collections.json")

    monkeypatch.setattr(summary_aggregator, "add_collection", fail_store)
    response = client.post(
        "/api/summary/collections",
        json=_confirm_collection_body(prepared, payload),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Collection mutation failed"
    assert "confirmation-token-private" not in response.text
    assert "saved_collections.json" not in response.text
    assert authority.external_calls[0]["status"] == "failed"
    assert authority.external_calls[0]["side_effect_report"]["mutated"] is False
    assert not (mock_db_paths[0].parent / "saved_collections.json").exists()


def test_collection_delete_prepare_is_write_free_and_persists_exact_job_scope(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    collections_file = mock_db_paths[0].parent / "saved_collections.json"
    before = collections_file.read_bytes()

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json={"action": "prepare"},
    )

    assert response.status_code == 200
    prepared = response.json()
    assert prepared["success"] is True
    assert prepared["confirmation_token"] == "confirmation-token-1"
    assert prepared["job"]["state"] == "pending_confirmation"
    assert prepared["job"]["operation"] == "summary_collection.delete"
    expected_scope = {
        "epoch_id": mock_db_paths[0].parent.name,
        "collection_id": collection["collection_id"],
        "expected_record_sha256": summary_aggregator.collection_record_sha256(
            collection
        ),
    }
    assert prepared["job"]["scope"] == expected_scope
    assert "token_fingerprint" not in prepared["job"]
    assert "authorization_request_id" not in prepared["job"]
    assert collections_file.read_bytes() == before
    assert authority.authorize_calls == [
        {
            "prompt": "Prepare one exact summary collection delete",
            "mode": "ops",
            "tool_name": "delete_summary_collection",
            "tool_args": {
                "job_id": prepared["job"]["job_id"],
                **expected_scope,
            },
        }
    ]
    persisted = _job_ledger(mock_db_paths[0].parent).load(
        prepared["job"]["job_id"]
    )
    assert persisted["token_fingerprint"] == hashlib.sha256(
        b"confirmation-token-1"
    ).hexdigest()
    assert persisted["authorization_request_id"] == "authorization-request-1"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"action": "prepare", "extra": True},
        {"action": "confirm", "job_id": "job_invalid"},
    ],
)
def test_collection_delete_rejects_invalid_body_before_authority_or_job(
    body, client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=body,
    )

    assert response.status_code == 422
    assert authority.authorize_calls == []
    assert not (
        mock_db_paths[0].parent / "GoodQ_Data" / "control" / "action_jobs"
    ).exists()


def test_collection_delete_prepare_requires_active_collection_without_job(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    response = client.request(
        "DELETE",
        "/api/summary/collections/col_missing",
        json={"action": "prepare"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Active collection not found"
    assert authority.authorize_calls == []
    assert not (
        mock_db_paths[0].parent / "GoodQ_Data" / "control" / "action_jobs"
    ).exists()


def test_collection_delete_prepare_rejects_collection_from_wrong_epoch(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    data = summary_aggregator.load_collections(mock_db_paths[0])
    data["collections"][0]["source_epoch"] = "epoch_other"
    summary_aggregator.save_collections(mock_db_paths[0], data)

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json={"action": "prepare"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Collection epoch mismatch"
    assert authority.authorize_calls == []
    assert not (
        mock_db_paths[0].parent / "GoodQ_Data" / "control" / "action_jobs"
    ).exists()


def test_collection_delete_prepare_conflicts_with_active_job_without_new_token(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])

    first = _prepare_collection_delete(client, collection["collection_id"])
    second = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json={"action": "prepare"},
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "active_job_exists"
    assert second.json()["detail"]["job"]["job_id"] == first["job"]["job_id"]
    assert "confirmation_token" not in second.text
    assert len(authority.authorize_calls) == 1


def test_collection_delete_confirm_claims_exact_scope_and_terminalizes(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["recovered"] is False
    assert result["job"]["state"] == "succeeded"
    assert result["job"]["outcome"]["code"] == "collection_deleted"
    assert result["job"]["audit_status"] == "recorded"
    assert "confirmation-token-1" not in response.text
    assert "authorization-request-1" not in response.text
    persisted_collection = summary_aggregator.load_collections(mock_db_paths[0])[
        "collections"
    ][0]
    assert persisted_collection["status"] == "deleted"
    expected_scope = prepared["job"]["scope"]
    assert persisted_collection["history"][-1] == {
        "action": "delete",
        "timestamp_utc": persisted_collection["history"][-1]["timestamp_utc"],
        "operator_note": "Soft-deleted by operator",
        "job_id": prepared["job"]["job_id"],
        "expected_record_sha256": expected_scope["expected_record_sha256"],
        "authorization_request_id": "authorization-request-1",
    }
    exact_args = {"job_id": prepared["job"]["job_id"], **expected_scope}
    assert authority.authorize_calls[1] == {
        "prompt": "Confirm one exact summary collection delete",
        "mode": "ops",
        "tool_name": "delete_summary_collection",
        "tool_args": exact_args,
        "confirm": True,
        "confirmation_token": "confirmation-token-1",
    }
    assert authority.external_calls == [
        {
            "operation": "delete_summary_collection",
            "arguments": exact_args,
            "request_id": "authorization-request-1",
            "mode": "ops",
            "status": "succeeded",
            "return_code": 0,
            "duration_ms": authority.external_calls[0]["duration_ms"],
            "side_effect_report": {
                "mutated": True,
                "targets": [
                    f"summary-collection:delete:{prepared['job']['job_id']}"
                ],
            },
            "error_codes": [],
        }
    ]


def test_collection_delete_persists_confirm_request_id_across_all_evidence(
    client, mock_db_paths, monkeypatch
) -> None:
    class DistinctRequestAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            envelope, code = super().authorize_action(**kwargs)
            envelope["request_id"] = (
                "authorization-confirm-request"
                if kwargs.get("confirm")
                else "authorization-prepare-request"
            )
            return envelope, code

    authority = DistinctRequestAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 200
    job = _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])
    assert job["authorization_request_id"] == "authorization-confirm-request"
    history = summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "history"
    ]
    assert history[-1]["authorization_request_id"] == "authorization-confirm-request"
    assert authority.external_calls[0]["request_id"] == "authorization-confirm-request"


def test_collection_delete_wrong_token_preserves_pending_job_and_collection(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    body = _confirm_collection_delete_body(prepared)
    body["confirmation_token"] = "wrong-token"

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=body,
    )

    assert response.status_code == 403
    record = _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])
    assert record["state"] == "pending_confirmation"
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "active"
    assert len(authority.authorize_calls) == 1


def test_collection_delete_changed_record_fails_without_mutation(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    data = summary_aggregator.load_collections(mock_db_paths[0])
    data["collections"][0]["description"] = "Changed after authorization"
    summary_aggregator.save_collections(mock_db_paths[0], data)

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "collection_changed"
    assert detail["job"]["state"] == "failed"
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "active"
    assert authority.external_calls[0]["status"] == "failed"
    assert authority.external_calls[0]["side_effect_report"]["mutated"] is False


def test_collection_delete_token_already_used_recovers_exact_receipt(
    client, mock_db_paths, monkeypatch
) -> None:
    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-retry",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_already_used", "message": "Used"}],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    scope = prepared["job"]["scope"]
    summary_aggregator.soft_delete_collection(
        mock_db_paths[0],
        collection["collection_id"],
        mutation_evidence={
            "job_id": prepared["job"]["job_id"],
            "expected_record_sha256": scope["expected_record_sha256"],
            "authorization_request_id": "authorization-request-original",
        },
    )

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 200
    assert response.json()["recovered"] is True
    assert response.json()["job"]["state"] == "succeeded"
    assert authority.external_calls[0]["request_id"] == "authorization-request-original"
    assert len(
        summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
            "history"
        ]
    ) == 2


def test_collection_delete_token_already_used_without_receipt_fails_closed(
    client, mock_db_paths, monkeypatch
) -> None:
    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-retry",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_already_used", "message": "Used"}],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "authorization_recovery_failed"
    assert response.json()["detail"]["job"]["state"] == "failed"
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "active"


@pytest.mark.parametrize("invalid_receipt", ["wrong_target", "active", "epoch"])
def test_collection_delete_recovery_rejects_misbound_receipt(
    invalid_receipt, client, mock_db_paths, monkeypatch
) -> None:
    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-retry",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_already_used", "message": "Used"}],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    target = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, target["collection_id"])
    data = summary_aggregator.load_collections(mock_db_paths[0])
    receipt_target = data["collections"][0]
    if invalid_receipt == "wrong_target":
        other = summary_aggregator.add_collection(
            mock_db_paths[0],
            {"name": "Wrong receipt target"},
        )
        data = summary_aggregator.load_collections(mock_db_paths[0])
        receipt_target = next(
            item for item in data["collections"] if item["collection_id"] == other["collection_id"]
        )
    receipt_target["history"].append(
        {
            "action": "delete",
            "timestamp_utc": "2026-07-12T23:00:00Z",
            "operator_note": "Injected invalid receipt",
            "job_id": prepared["job"]["job_id"],
            "expected_record_sha256": prepared["job"]["scope"][
                "expected_record_sha256"
            ],
            "authorization_request_id": "authorization-request-original",
        }
    )
    if invalid_receipt != "active":
        receipt_target["status"] = "deleted"
        receipt_target["deleted_at_utc"] = "2026-07-12T23:00:00Z"
    if invalid_receipt == "epoch":
        receipt_target["source_epoch"] = "epoch_other"
    summary_aggregator.save_collections(mock_db_paths[0], data)

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{target['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "authorization_recovery_failed"
    assert response.json()["detail"]["job"]["state"] == "failed"
    assert authority.external_calls == []


def test_collection_delete_post_effect_audit_failure_preserves_success(
    client, mock_db_paths, monkeypatch
) -> None:
    class FailingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            self.external_calls.append(kwargs)
            return {"audit_status": "failed", "error_codes": ["audit_log_error"]}

    authority = FailingAuditAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 200
    assert response.json()["job"]["state"] == "succeeded"
    assert response.json()["job"]["audit_status"] == "failed"
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "deleted"


def test_concurrent_collection_delete_confirms_mutate_once(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    body = _confirm_collection_delete_body(prepared)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _unused: client.request(
                    "DELETE",
                    f"/api/summary/collections/{collection['collection_id']}",
                    json=body,
                ),
                range(2),
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    stored = summary_aggregator.load_collections(mock_db_paths[0])["collections"][0]
    assert stored["status"] == "deleted"
    assert len([entry for entry in stored["history"] if entry["action"] == "delete"]) == 1


def test_collection_delete_prepare_revokes_unpersisted_authorization(
    client, mock_db_paths, monkeypatch
) -> None:
    class InvalidEvidenceAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "private\\invalid-request",
                    "status": "needs_confirmation",
                    "result": {"confirmation_token": "confirmation-token-private"},
                    "errors": [],
                },
                3,
            )

    authority = InvalidEvidenceAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json={"action": "prepare"},
    )

    assert response.status_code == 503
    assert "confirmation-token-private" not in response.text
    assert authority.revoke_calls == [
        {
            "prompt": "Revoke unpersisted summary collection delete authorization",
            "mode": "ops",
            "tool_name": "delete_summary_collection",
            "tool_args": authority.authorize_calls[0]["tool_args"],
            "confirmation_token": "confirmation-token-private",
        }
    ]
    record = _job_ledger(mock_db_paths[0].parent).list_records(
        operation="summary_collection.delete"
    )[0]
    assert record["state"] == "failed"
    assert record["outcome"]["code"] == "authorization_prepare_failed"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("epoch_id", "epoch_other"),
        ("expected_record_sha256", "b" * 64),
    ],
)
def test_collection_delete_confirm_rejects_tampered_scope_before_authority(
    field, replacement, client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    body = _confirm_collection_delete_body(prepared)
    body[field] = replacement

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=body,
    )

    assert response.status_code == 404
    assert len(authority.authorize_calls) == 1
    assert _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])[
        "state"
    ] == "pending_confirmation"
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "active"


def test_collection_delete_expired_authorization_is_terminal_and_write_free(
    client, mock_db_paths, monkeypatch
) -> None:
    class ExpiredAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            if not kwargs.get("confirm"):
                return super().authorize_action(**kwargs)
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-2",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_expired", "message": "Expired"}],
                },
                1,
            )

    authority = ExpiredAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "authorization_expired"
    assert response.json()["detail"]["job"]["state"] == "expired"
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "active"


def test_collection_delete_audit_exception_preserves_committed_success(
    client, mock_db_paths, monkeypatch
) -> None:
    class RaisingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            self.external_calls.append(kwargs)
            raise RuntimeError("confirmation-token-private private\\audit.json")

    authority = RaisingAuditAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 200
    assert response.json()["job"]["state"] == "succeeded"
    assert response.json()["job"]["audit_status"] == "failed"
    assert "confirmation-token-private" not in response.text
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "deleted"


def test_collection_delete_store_exception_is_sanitized_and_terminal(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])

    def fail_store(*_args, **_kwargs):
        raise RuntimeError("confirmation-token-private private\\saved_collections.json")

    monkeypatch.setattr(summary_aggregator, "soft_delete_collection", fail_store)
    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "collection_mutation_failed"
    assert detail["job"]["state"] == "failed"
    assert "confirmation-token-private" not in response.text
    assert "saved_collections.json" not in response.text
    assert summary_aggregator.load_collections(mock_db_paths[0])["collections"][0][
        "status"
    ] == "active"


@pytest.mark.parametrize(
    "failure_exception",
    [
        ActionJobTransitionError("private\\terminal.json"),
        OSError("private\\terminal.json"),
    ],
)
def test_collection_delete_terminal_ledger_failure_reports_pending_truth(
    failure_exception, client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    ledger = _job_ledger(mock_db_paths[0].parent)
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    original_transition = ledger.transition

    def fail_terminal(job_id, *, expected_states, new_state, **updates):
        if new_state == "succeeded":
            raise failure_exception
        return original_transition(
            job_id,
            expected_states=expected_states,
            new_state=new_state,
            **updates,
        )

    monkeypatch.setattr(ledger, "transition", fail_terminal)
    response = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "collection_finalization_pending"
    assert response.json()["detail"]["job"]["state"] == "running"
    assert "terminal.json" not in response.text
    assert ledger.load(prepared["job"]["job_id"])["state"] == "running"
    persisted = summary_aggregator.find_collection_by_delete_job(
        mock_db_paths[0],
        job_id=prepared["job"]["job_id"],
        expected_record_sha256=prepared["job"]["scope"]["expected_record_sha256"],
    )
    assert persisted["status"] == "deleted"


def test_collection_delete_prepare_and_confirm_require_epoch_database(
    client, mock_db_paths, monkeypatch
) -> None:
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    collection = _create_collection_for_delete(mock_db_paths[0])
    prepared = _prepare_collection_delete(client, collection["collection_id"])
    mock_db_paths[0].unlink()

    confirm = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json=_confirm_collection_delete_body(prepared),
    )
    new_prepare = client.request(
        "DELETE",
        f"/api/summary/collections/{collection['collection_id']}",
        json={"action": "prepare"},
    )

    assert confirm.status_code == 404
    assert new_prepare.status_code == 404
    assert len(authority.authorize_calls) == 1
    assert _job_ledger(mock_db_paths[0].parent).load(prepared["job"]["job_id"])[
        "state"
    ] == "pending_confirmation"


def _summary_job_in_state(
    ledger: ActionJobLedger,
    state: str,
    *,
    owner_instance: str = "summary-api-prior",
    complete_evidence: bool = True,
) -> dict:
    record = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance=owner_instance,
    )
    if complete_evidence:
        record = ledger.compare_and_update(
            record["job_id"],
            expected_state="pending_confirmation",
            token_fingerprint=hashlib.sha256(b"confirmation-token-1").hexdigest(),
            authorization_request_id="authorization-request-1",
        )
    transitions = {
        "pending_confirmation": [],
        "authorizing": ["authorizing"],
        "queued": ["authorizing", "queued"],
        "running": ["authorizing", "queued", "running"],
    }[state]
    current = "pending_confirmation"
    for next_state in transitions:
        record = ledger.transition(
            record["job_id"],
            expected_states=current,
            new_state=next_state,
        )
        current = next_state
    return record


def _delete_job_in_state(
    tmp_path: Path,
    state: str,
    *,
    owner_instance: str = "summary-api-prior",
    complete_evidence: bool = True,
    persist_receipt: bool = False,
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "knowledge_graph.db"
    db_path.write_text("", encoding="utf-8")
    collection = _create_collection_for_delete(db_path)
    scope = {
        "epoch_id": tmp_path.name,
        "collection_id": collection["collection_id"],
        "expected_record_sha256": summary_aggregator.collection_record_sha256(
            collection
        ),
    }
    ledger = _job_ledger(tmp_path)
    record = ledger.create_pending(
        operation="summary_collection.delete",
        scope=scope,
        owner_instance=owner_instance,
    )
    if complete_evidence:
        record = ledger.compare_and_update(
            record["job_id"],
            expected_state="pending_confirmation",
            token_fingerprint=hashlib.sha256(b"confirmation-token-1").hexdigest(),
            authorization_request_id="authorization-delete-original",
        )
    transitions = {
        "pending_confirmation": [],
        "authorizing": ["authorizing"],
        "queued": ["authorizing", "queued"],
        "running": ["authorizing", "queued", "running"],
    }[state]
    current = "pending_confirmation"
    for next_state in transitions:
        record = ledger.transition(
            record["job_id"],
            expected_states=current,
            new_state=next_state,
        )
        current = next_state
    if persist_receipt:
        summary_aggregator.soft_delete_collection(
            db_path,
            collection["collection_id"],
            mutation_evidence={
                "job_id": record["job_id"],
                "expected_record_sha256": scope["expected_record_sha256"],
                "authorization_request_id": "authorization-delete-original",
            },
        )
    return {
        "db_path": db_path,
        "collection": collection,
        "scope": scope,
        "ledger": ledger,
        "record": record,
        "cfg": {
            "paths": {
                "data_root": str(tmp_path / "GoodQ_Data"),
                "knowledge_graph_db": str(db_path),
            }
        },
    }


def test_summary_router_registers_reconciliation_startup_handler() -> None:
    handlers = [
        handler
        for handler in summary_route.router.on_startup
        if handler is summary_route._reconcile_summary_jobs_on_startup
    ]

    assert handlers == [summary_route._reconcile_summary_jobs_on_startup]


def test_summary_reconciliation_absent_job_root_is_not_created(tmp_path) -> None:
    data_root = tmp_path / "GoodQ_Data"
    job_root = data_root / "control" / "action_jobs"

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(data_root)}}
    )

    assert not job_root.exists()


@pytest.mark.parametrize("state", ["pending_confirmation", "authorizing"])
def test_summary_reconciliation_preserves_complete_authorization_evidence(
    state, tmp_path
) -> None:
    ledger = _job_ledger(tmp_path)
    record = _summary_job_in_state(ledger, state)
    path = ledger.record_path(record["job_id"])
    before = (path.read_bytes(), path.stat().st_mtime_ns)

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
    )

    assert ledger.load(record["job_id"]) == record
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("state", ["pending_confirmation", "authorizing"])
def test_summary_reconciliation_fails_incomplete_authorization_evidence(
    state, tmp_path
) -> None:
    ledger = _job_ledger(tmp_path)
    record = _summary_job_in_state(
        ledger,
        state,
        complete_evidence=False,
    )

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
    )

    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "failed"
    assert persisted["outcome"] == {
        "code": "authorization_interrupted",
        "message": "Video summary authorization was interrupted by restart",
    }


@pytest.mark.parametrize("state", ["queued", "running"])
def test_summary_reconciliation_audits_before_interrupting_execution(
    state, tmp_path, monkeypatch
) -> None:
    ledger = _job_ledger(tmp_path)
    record = _summary_job_in_state(ledger, state)

    class InspectingAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            assert ledger.load(record["job_id"])["state"] == state
            return super().record_external_execution_outcome(**kwargs)

    authority = InspectingAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
    )

    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == "recorded"
    assert persisted["outcome"] == {
        "code": "execution_interrupted",
        "message": "Video summary generation was interrupted by restart",
    }
    assert authority.external_calls == [
        {
            "operation": "generate_video_summary",
            "arguments": {"job_id": record["job_id"], "video_hash": VALID_HASH},
            "request_id": "authorization-request-1",
            "mode": "ops",
            "status": "interrupted",
            "return_code": 1,
            "duration_ms": 0,
            "side_effect_report": {
                "mutated": False,
                "targets": [f"video-summary:{record['job_id']}"],
            },
            "error_codes": ["execution_interrupted"],
        }
    ]


@pytest.mark.parametrize("failure_mode", ["constructor", "write"])
def test_summary_reconciliation_audit_failure_still_interrupts_safely(
    failure_mode, tmp_path, monkeypatch, caplog
) -> None:
    ledger = _job_ledger(tmp_path)
    record = _summary_job_in_state(ledger, "running")

    class FailingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            raise RuntimeError("confirmation-token-private C:\\private\\audit.json")

    if failure_mode == "constructor":
        def fail_authority(_cfg):
            raise RuntimeError("confirmation-token-private C:\\private\\authority")

        monkeypatch.setattr(summary_route, "_get_summary_authority", fail_authority)
    else:
        monkeypatch.setattr(
            summary_route,
            "_get_summary_authority",
            lambda _cfg: FailingAuditAuthority(),
        )

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
    )

    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == "failed"
    assert "confirmation-token-private" not in caplog.text
    assert "private\\" not in caplog.text


def test_summary_reconciliation_leaves_current_terminal_and_unrelated_jobs_unchanged(
    tmp_path, monkeypatch
) -> None:
    ledger = _job_ledger(tmp_path)
    current = _summary_job_in_state(
        ledger,
        "queued",
        owner_instance=summary_route._SUMMARY_OWNER_INSTANCE,
    )
    terminal_source = _summary_job_in_state(ledger, "pending_confirmation")
    terminal = ledger.transition(
        terminal_source["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
    )
    unrelated = ledger.create_pending(
        operation="identity.rebuild",
        scope={"target": "faces"},
        owner_instance="summary-api-prior",
    )
    unrelated = ledger.transition(
        unrelated["job_id"],
        expected_states="pending_confirmation",
        new_state="authorizing",
    )
    before = {
        record["job_id"]: ledger.record_path(record["job_id"]).read_bytes()
        for record in (current, terminal, unrelated)
    }
    monkeypatch.setattr(
        summary_route,
        "_get_summary_authority",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("unexpected audit")),
    )

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
    )

    assert {
        job_id: ledger.record_path(job_id).read_bytes() for job_id in before
    } == before


def test_summary_reconciliation_never_runs_worker_or_model(
    tmp_path, monkeypatch
) -> None:
    ledger = _job_ledger(tmp_path)
    _summary_job_in_state(ledger, "queued")
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(
        summary_route,
        "_generate_summary_worker",
        lambda *_args: (_ for _ in ()).throw(AssertionError("worker ran")),
    )
    monkeypatch.setattr(
        "steps.video_summarizer.step.run_step",
        lambda *_args: (_ for _ in ()).throw(AssertionError("model ran")),
    )

    summary_route._reconcile_summary_jobs(
        {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
    )

    assert authority.authorize_calls == []
    assert len(authority.external_calls) == 1


def test_summary_reconciliation_surfaces_corrupt_ledger(tmp_path) -> None:
    root = tmp_path / "GoodQ_Data" / "control" / "action_jobs"
    root.mkdir(parents=True)
    (root / f"job_{'a' * 32}.json").write_text("{corrupt", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        summary_route._reconcile_summary_jobs(
            {"paths": {"data_root": str(tmp_path / "GoodQ_Data")}}
        )


@pytest.mark.parametrize("state", ["pending_confirmation", "authorizing"])
def test_collection_delete_reconciliation_preserves_complete_authorization(
    state, tmp_path
) -> None:
    job = _delete_job_in_state(tmp_path, state)
    path = job["ledger"].record_path(job["record"]["job_id"])
    before = (path.read_bytes(), path.stat().st_mtime_ns)

    summary_route._reconcile_summary_jobs(job["cfg"])

    assert job["ledger"].load(job["record"]["job_id"]) == job["record"]
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("state", ["pending_confirmation", "authorizing"])
def test_collection_delete_reconciliation_fails_incomplete_authorization(
    state, tmp_path
) -> None:
    job = _delete_job_in_state(
        tmp_path,
        state,
        complete_evidence=False,
    )

    summary_route._reconcile_summary_jobs(job["cfg"])

    persisted = job["ledger"].load(job["record"]["job_id"])
    assert persisted["state"] == "failed"
    assert persisted["outcome"] == {
        "code": "authorization_interrupted",
        "message": "Collection delete authorization was interrupted by restart",
    }


@pytest.mark.parametrize("state", ["authorizing", "queued", "running"])
def test_collection_delete_reconciliation_completes_exact_receipt_without_replay(
    state, tmp_path, monkeypatch
) -> None:
    job = _delete_job_in_state(tmp_path, state, persist_receipt=True)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(
        summary_aggregator,
        "soft_delete_collection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("delete replayed")
        ),
    )

    summary_route._reconcile_summary_jobs(job["cfg"])

    persisted = job["ledger"].load(job["record"]["job_id"])
    assert persisted["state"] == "succeeded"
    assert persisted["outcome"] == {
        "code": "collection_deleted",
        "message": "Collection delete was recovered from durable evidence",
    }
    assert persisted["audit_status"] == "recorded"
    assert authority.authorize_calls == []
    assert authority.external_calls == [
        {
            "operation": "delete_summary_collection",
            "arguments": {"job_id": job["record"]["job_id"], **job["scope"]},
            "request_id": "authorization-delete-original",
            "mode": "ops",
            "status": "succeeded",
            "return_code": 0,
            "duration_ms": 0,
            "side_effect_report": {
                "mutated": True,
                "targets": [
                    f"summary-collection:delete:{job['record']['job_id']}"
                ],
            },
            "error_codes": [],
        }
    ]


@pytest.mark.parametrize("state", ["queued", "running"])
def test_collection_delete_reconciliation_interrupts_without_receipt_or_replay(
    state, tmp_path, monkeypatch
) -> None:
    job = _delete_job_in_state(tmp_path, state)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(
        summary_aggregator,
        "soft_delete_collection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("delete replayed")
        ),
    )

    summary_route._reconcile_summary_jobs(job["cfg"])

    persisted = job["ledger"].load(job["record"]["job_id"])
    assert persisted["state"] == "interrupted"
    assert persisted["outcome"] == {
        "code": "execution_interrupted",
        "message": "Collection delete was interrupted before durable mutation",
    }
    assert persisted["audit_status"] == "recorded"
    assert authority.authorize_calls == []
    assert authority.external_calls[0]["status"] == "interrupted"
    assert authority.external_calls[0]["side_effect_report"]["mutated"] is False
    assert authority.external_calls[0]["error_codes"] == ["execution_interrupted"]
    assert summary_aggregator.load_collections(job["db_path"])["collections"][0][
        "status"
    ] == "active"


@pytest.mark.parametrize("persist_receipt", [False, True])
def test_collection_delete_reconciliation_audit_failure_keeps_state_truth(
    persist_receipt, tmp_path, monkeypatch
) -> None:
    job = _delete_job_in_state(
        tmp_path,
        "running",
        persist_receipt=persist_receipt,
    )

    class RaisingAuditAuthority(StubSummaryAuthority):
        def record_external_execution_outcome(self, **kwargs):
            raise RuntimeError("confirmation-token-private private\\audit.json")

    monkeypatch.setattr(
        summary_route,
        "_get_summary_authority",
        lambda _cfg: RaisingAuditAuthority(),
    )

    summary_route._reconcile_summary_jobs(job["cfg"])

    persisted = job["ledger"].load(job["record"]["job_id"])
    assert persisted["state"] == (
        "succeeded" if persist_receipt else "interrupted"
    )
    assert persisted["audit_status"] == "failed"


def test_collection_delete_reconciliation_is_idempotent(tmp_path, monkeypatch) -> None:
    job = _delete_job_in_state(tmp_path, "running", persist_receipt=True)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    summary_route._reconcile_summary_jobs(job["cfg"])
    first = job["ledger"].load(job["record"]["job_id"])
    summary_route._reconcile_summary_jobs(job["cfg"])

    assert job["ledger"].load(job["record"]["job_id"]) == first
    assert len(authority.external_calls) == 1


def test_collection_delete_reconciliation_leaves_current_and_terminal_unchanged(
    tmp_path, monkeypatch
) -> None:
    current = _delete_job_in_state(
        tmp_path / "current",
        "running",
        owner_instance=summary_route._SUMMARY_OWNER_INSTANCE,
    )
    terminal = _delete_job_in_state(tmp_path / "terminal", "running")
    terminal_record = terminal["ledger"].transition(
        terminal["record"]["job_id"],
        expected_states="running",
        new_state="interrupted",
        outcome={"code": "already_terminal", "message": "Already terminal"},
    )
    before_current = current["ledger"].record_path(
        current["record"]["job_id"]
    ).read_bytes()
    before_terminal = terminal["ledger"].record_path(
        terminal_record["job_id"]
    ).read_bytes()
    monkeypatch.setattr(
        summary_route,
        "_get_summary_authority",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("unexpected audit")),
    )

    summary_route._reconcile_summary_jobs(current["cfg"])
    summary_route._reconcile_summary_jobs(terminal["cfg"])

    assert current["ledger"].record_path(
        current["record"]["job_id"]
    ).read_bytes() == before_current
    assert terminal["ledger"].record_path(
        terminal_record["job_id"]
    ).read_bytes() == before_terminal


def test_collection_delete_reconciliation_surfaces_corrupt_store(
    tmp_path
) -> None:
    job = _delete_job_in_state(tmp_path, "running")
    (tmp_path / "saved_collections.json").write_text("{corrupt", encoding="utf-8")

    with pytest.raises(RuntimeError, match="saved collections store"):
        summary_route._reconcile_summary_jobs(job["cfg"])

    assert job["ledger"].load(job["record"]["job_id"])["state"] == "running"


@pytest.mark.parametrize("invalid_receipt", ["wrong_target", "active", "epoch"])
def test_collection_delete_reconciliation_never_accepts_misbound_receipt(
    invalid_receipt, tmp_path, monkeypatch
) -> None:
    job = _delete_job_in_state(tmp_path, "running")
    data = summary_aggregator.load_collections(job["db_path"])
    receipt_target = data["collections"][0]
    if invalid_receipt == "wrong_target":
        other = summary_aggregator.add_collection(
            job["db_path"],
            {"name": "Wrong restart receipt target"},
        )
        data = summary_aggregator.load_collections(job["db_path"])
        receipt_target = next(
            item for item in data["collections"] if item["collection_id"] == other["collection_id"]
        )
    receipt_target["history"].append(
        {
            "action": "delete",
            "timestamp_utc": "2026-07-12T23:00:00Z",
            "operator_note": "Injected invalid restart receipt",
            "job_id": job["record"]["job_id"],
            "expected_record_sha256": job["scope"]["expected_record_sha256"],
            "authorization_request_id": "authorization-delete-original",
        }
    )
    if invalid_receipt != "active":
        receipt_target["status"] = "deleted"
        receipt_target["deleted_at_utc"] = "2026-07-12T23:00:00Z"
    if invalid_receipt == "epoch":
        receipt_target["source_epoch"] = "epoch_other"
    summary_aggregator.save_collections(job["db_path"], data)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    summary_route._reconcile_summary_jobs(job["cfg"])

    persisted = job["ledger"].load(job["record"]["job_id"])
    assert persisted["state"] == "interrupted"
    assert authority.external_calls[0]["status"] == "interrupted"
    assert authority.external_calls[0]["side_effect_report"]["mutated"] is False


def test_collection_delete_reconciliation_missing_epoch_db_interrupts_without_guess(
    tmp_path, monkeypatch
) -> None:
    job = _delete_job_in_state(tmp_path, "running")
    job["db_path"].unlink()
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)

    summary_route._reconcile_summary_jobs(job["cfg"])

    persisted = job["ledger"].load(job["record"]["job_id"])
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == "recorded"


def test_collection_delete_reconciliation_surfaces_invalid_persisted_scope(
    tmp_path
) -> None:
    job = _delete_job_in_state(tmp_path, "running")
    record_path = job["ledger"].record_path(job["record"]["job_id"])
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["scope"]["unexpected"] = "not-authoritative"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    before = record_path.read_bytes()

    with pytest.raises(ValueError, match="scope is invalid"):
        summary_route._reconcile_summary_jobs(job["cfg"])

    assert record_path.read_bytes() == before


def test_collection_delete_reconciliation_surfaces_request_id_mismatch(
    tmp_path, monkeypatch
) -> None:
    job = _delete_job_in_state(tmp_path, "running", persist_receipt=True)
    data = summary_aggregator.load_collections(job["db_path"])
    data["collections"][0]["history"][-1][
        "authorization_request_id"
    ] = "authorization-delete-conflict"
    summary_aggregator.save_collections(job["db_path"], data)
    record_path = job["ledger"].record_path(job["record"]["job_id"])
    before = record_path.read_bytes()
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(
        summary_aggregator,
        "soft_delete_collection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("delete replayed")
        ),
    )

    with pytest.raises(ValueError, match="authorization request ID"):
        summary_route._reconcile_summary_jobs(job["cfg"])

    assert record_path.read_bytes() == before
    assert authority.authorize_calls == []
    assert authority.external_calls == []


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

    def readonly_execute(statement, *_args):
        result = MagicMock()
        result.fetchone.return_value = (1,) if statement == "PRAGMA query_only" else None
        return result

    mock_conn.execute.side_effect = readonly_execute
    
    # Mock scenes check: returns None (video not in KG DB)
    mock_cursor.execute.return_value.fetchone.return_value = None

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


def test_confirm_recovers_prior_pending_owner_and_queues_once(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    authority = StubSummaryAuthority()
    ledger = _job_ledger(mock_db_paths[0].parent)
    worker_calls = []
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)
    async def worker(*args):
        worker_calls.append(args)

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)
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

    assert response.status_code == 202
    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "queued"
    assert persisted["owner_instance"] == summary_route._SUMMARY_OWNER_INSTANCE
    assert len(worker_calls) == 1
    assert worker_calls[0][:2] == (record["job_id"], VALID_HASH)
    assert authority.authorize_calls == [
        {
            "prompt": "Confirm one exact video summary",
            "mode": "ops",
            "tool_name": "generate_video_summary",
            "tool_args": {"job_id": record["job_id"], "video_hash": VALID_HASH},
            "confirm": True,
            "confirmation_token": "confirmation-token-1",
        }
    ]


def test_confirm_recovers_prior_authorizing_token_already_used(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    ledger = _job_ledger(mock_db_paths[0].parent)
    record = _summary_job_in_state(ledger, "authorizing")
    worker_calls = []

    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-1",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [
                        {"code": "token_already_used", "message": "Already used"}
                    ],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)

    async def worker(*args):
        worker_calls.append(args)

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": record["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 202
    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "queued"
    assert persisted["owner_instance"] == summary_route._SUMMARY_OWNER_INSTANCE
    assert len(worker_calls) == 1


def test_confirm_does_not_accept_token_already_used_for_recovered_pending(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    ledger = _job_ledger(mock_db_paths[0].parent)
    record = _summary_job_in_state(ledger, "pending_confirmation")

    class AlreadyUsedAuthority(StubSummaryAuthority):
        def authorize_action(self, **kwargs):
            self.authorize_calls.append(kwargs)
            return (
                {
                    "request_id": "authorization-request-1",
                    "status": "error",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_already_used", "message": "Used"}],
                },
                1,
            )

    authority = AlreadyUsedAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": record["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 409
    assert ledger.load(record["job_id"])["state"] == "failed"


def test_confirm_same_owner_authorizing_remains_conflict(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    ledger = _job_ledger(mock_db_paths[0].parent)
    record = _summary_job_in_state(
        ledger,
        "authorizing",
        owner_instance=summary_route._SUMMARY_OWNER_INSTANCE,
    )
    authority = StubSummaryAuthority()
    worker_calls = []
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)

    async def worker(*args):
        worker_calls.append(args)

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": record["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 409
    assert ledger.load(record["job_id"]) == record
    assert authority.authorize_calls == []
    assert worker_calls == []


def test_confirm_prior_owner_checks_token_before_adoption(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    ledger = _job_ledger(mock_db_paths[0].parent)
    record = _summary_job_in_state(ledger, "pending_confirmation")
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": record["job_id"],
            "confirmation_token": "wrong-token",
        },
    )

    assert response.status_code == 403
    assert ledger.load(record["job_id"])["owner_instance"] == "summary-api-prior"


def test_confirm_prior_owner_requires_complete_authorization_evidence(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    ledger = _job_ledger(mock_db_paths[0].parent)
    record = _summary_job_in_state(
        ledger,
        "pending_confirmation",
        complete_evidence=False,
    )
    record = ledger.compare_and_update(
        record["job_id"],
        expected_state="pending_confirmation",
        token_fingerprint=hashlib.sha256(b"confirmation-token-1").hexdigest(),
    )
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)

    response = client.post(
        f"/api/summary/video/{VALID_HASH}/generate",
        json={
            "action": "confirm",
            "job_id": record["job_id"],
            "confirmation_token": "confirmation-token-1",
        },
    )

    assert response.status_code == 409
    assert ledger.load(record["job_id"])["owner_instance"] == "summary-api-prior"


def test_concurrent_prior_owner_confirmation_queues_exactly_once(
    client, mock_db_paths, monkeypatch
) -> None:
    _mock_existing_video(monkeypatch)
    ledger = _job_ledger(mock_db_paths[0].parent)
    record = _summary_job_in_state(ledger, "pending_confirmation")
    authority = StubSummaryAuthority()
    worker_calls = []
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    monkeypatch.setattr(summary_route, "_get_summary_job_ledger", lambda _cfg: ledger)

    async def worker(*args):
        worker_calls.append(args)

    monkeypatch.setattr(summary_route, "_generate_summary_worker", worker)

    def confirm():
        return client.post(
            f"/api/summary/video/{VALID_HASH}/generate",
            json={
                "action": "confirm",
                "job_id": record["job_id"],
                "confirmation_token": "confirmation-token-1",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _unused: confirm(), range(2)))

    assert sorted(response.status_code for response in responses) == [202, 409]
    assert ledger.load(record["job_id"])["state"] == "queued"
    assert len(authority.authorize_calls) == 1
    assert len(worker_calls) == 1


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


def test_summary_status_absent_root_stays_absent(client, mock_db_paths) -> None:
    job_root = (
        mock_db_paths[0].parent / "GoodQ_Data" / "control" / "action_jobs"
    )
    job_id = "job_" + "a" * 32

    assert not job_root.exists()
    latest = client.get(f"/api/summary/video/{VALID_HASH}/status")
    exact = client.get(
        f"/api/summary/video/{VALID_HASH}/status", params={"job_id": job_id}
    )

    assert latest.status_code == 200
    assert latest.json() == {"status": "not_started", "job": None}
    assert exact.status_code == 404
    assert not job_root.exists()


def test_summary_status_latest_and_exact_never_enter_writer_lock(
    client, mock_db_paths, monkeypatch
) -> None:
    ledger = _job_ledger(mock_db_paths[0].parent)
    older = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance="api-owner",
    )
    latest = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": VALID_HASH},
        owner_instance="api-owner",
    )

    def forbidden_writer_ledger(_cfg):
        raise AssertionError("summary status must not construct the writer ledger")

    monkeypatch.setattr(
        summary_route,
        "_get_summary_job_ledger",
        forbidden_writer_ledger,
    )

    latest_response = client.get(f"/api/summary/video/{VALID_HASH}/status")
    exact_response = client.get(
        f"/api/summary/video/{VALID_HASH}/status", params={"job_id": older["job_id"]}
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["job"]["job_id"] == latest["job_id"]
    assert exact_response.status_code == 200
    assert exact_response.json()["job"]["job_id"] == older["job_id"]
    assert not (ledger.root_dir / ".action-jobs.lock").exists()


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

    def readonly_execute(statement, *_args):
        result = MagicMock()
        result.fetchone.return_value = (1,) if statement == "PRAGMA query_only" else None
        return result

    mock_conn.execute.side_effect = readonly_execute
    
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
