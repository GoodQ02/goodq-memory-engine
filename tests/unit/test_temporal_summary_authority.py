from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import search as search_route
from api.utils.action_jobs import ActionJobLedger
from api.utils.temporal_summary_results import TemporalSummaryResultStore


class StubTemporalAuthority:
    def __init__(self) -> None:
        self.authorize_calls: list[dict] = []
        self.revoke_calls: list[dict] = []
        self.external_calls: list[dict] = []
        self.confirm_envelope = (
            {
                "request_id": "temporal-authorization-1",
                "status": "ok",
                "result": {"allowed": True},
                "errors": [],
            },
            0,
        )
        self._lock = Lock()

    def authorize_action(self, **kwargs):
        with self._lock:
            self.authorize_calls.append(kwargs)
        if kwargs.get("confirm"):
            return self.confirm_envelope
        return (
            {
                "request_id": "temporal-authorization-1",
                "status": "needs_confirmation",
                "result": {
                    "confirmation_token": "temporal-confirmation-token",
                    "confirmation_expires_at": "2026-07-14T00:00:00Z",
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
def temporal_runtime(tmp_path, monkeypatch):
    data_root = tmp_path / "GoodQ_Data"
    epoch_dir = data_root / "epochs" / "epoch_current"
    epoch_dir.mkdir(parents=True)
    cfg = {
        "paths": {
            "data_root": str(data_root),
            "db_path": str(epoch_dir / "memory.db"),
            "knowledge_graph_db": str(epoch_dir / "knowledge_graph.db"),
        },
        "host": {"profile": "BASELINE"},
        "llm": {
            "vllm_url": "http://127.0.0.1:38005/v1",
            "vllm_model": "test-vllm-model",
            "ollama_url": "http://127.0.0.1:31434/v1",
            "ollama_model": "test-ollama-model",
            "temporal_summary": {"allow_service_activation": False},
        },
    }
    authority = StubTemporalAuthority()
    load_configs = MagicMock(side_effect=lambda _overrides: copy.deepcopy(cfg))
    monkeypatch.setattr(search_route, "load_configs", load_configs)
    monkeypatch.setattr(
        search_route,
        "_get_temporal_summary_authority",
        lambda _cfg: authority,
    )
    monkeypatch.delenv("GOODQ_HOST_PROFILE", raising=False)
    monkeypatch.delenv("GOODQ_WSL_MODEL_PATH", raising=False)
    monkeypatch.delenv("GOODQ_OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    return cfg, authority, load_configs


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, client=("127.0.0.1", 50000))


def _request(**updates) -> dict:
    value = {
        "entities": ["Jay"],
        "start_date": None,
        "end_date": None,
        "time_hint": "summer 2026",
        "source_file": None,
        "modality": None,
        "max_results": 25,
        "grouping": "semantic_episode",
        "summary_style": "narrative",
    }
    value.update(updates)
    return value


def _prepare(client: TestClient, request: dict | None = None) -> dict:
    response = client.post(
        "/api/search/temporal/summarize",
        json={"action": "prepare", "request": request or _request()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _confirm_body(prepared: dict, request: dict | None = None) -> dict:
    scope = prepared["job"]["scope"]
    return {
        "action": "confirm",
        "job_id": prepared["job"]["job_id"],
        "epoch_id": scope["epoch_id"],
        "request_sha256": scope["request_sha256"],
        "execution_policy_sha256": scope["execution_policy_sha256"],
        "confirmation_token": prepared["confirmation_token"],
        "request": request or _request(),
    }


def _queued_job(cfg: dict, request: dict | None = None, *, owner: str | None = None):
    normalized = search_route.TemporalSummarizeRequest.model_validate(
        request or _request()
    ).model_dump(mode="json", exclude_none=False)
    request_bytes = search_route._canonical_json_bytes(normalized)
    snapshot = search_route._resolve_temporal_execution_snapshot(copy.deepcopy(cfg))
    scope = search_route._temporal_summary_scope(
        epoch_id=snapshot.epoch_id,
        request_sha256=hashlib.sha256(request_bytes).hexdigest(),
        execution_policy_sha256=snapshot.execution_policy_sha256,
    )
    job_root = search_route._temporal_summary_job_root(cfg)
    ledger = ActionJobLedger(job_root)
    record = ledger.create_pending(
        operation=search_route._TEMPORAL_SUMMARY_JOB_OPERATION,
        scope=scope,
        owner_instance=owner or search_route._TEMPORAL_SUMMARY_OWNER_INSTANCE,
    )
    record = ledger.compare_and_update(
        record["job_id"],
        expected_state="pending_confirmation",
        token_fingerprint=hashlib.sha256(b"temporal-confirmation-token").hexdigest(),
        authorization_request_id="temporal-authorization-1",
    )
    record = ledger.transition(
        record["job_id"],
        expected_states="pending_confirmation",
        new_state="authorizing",
    )
    record = ledger.transition(
        record["job_id"],
        expected_states="authorizing",
        new_state="queued",
    )
    return ledger, record, request_bytes, snapshot


def _success_result(snapshot) -> dict:
    return {
        "status": "success",
        "summary": "A grounded private narrative.",
        "segments": [
            {
                "scene_index": 1,
                "scene_id": "scene_0001",
                "text": "A grounded segment.",
                "start_time": 0.0,
                "end_time": 5.0,
            }
        ],
        "model_used": snapshot.models[0].name,
        "source_scene_ids": ["scene_0001"],
        "source_count": 1,
        "truncated": False,
        "warnings": [],
    }


@pytest.mark.parametrize(
    "body",
    [
        {"action": "prepare", "request": _request(), "extra": True},
        {"action": "prepare", "request": {**_request(), "extra": True}},
        {"action": "prepare", "request": _request(max_results=0)},
        {"action": "prepare", "request": _request(source_file="private/path.mp4")},
        {"action": "prepare", "request": _request(entities=["x" * 129])},
    ],
)
def test_prepare_rejects_noncanonical_request_before_authority(
    temporal_runtime,
    client,
    body,
) -> None:
    _cfg, authority, load_configs = temporal_runtime

    response = client.post("/api/search/temporal/summarize", json=body)

    assert response.status_code == 422
    assert authority.authorize_calls == []
    load_configs.assert_not_called()


def test_request_defaults_have_one_deterministic_digest() -> None:
    minimal = {"entities": ["Jay"]}
    _, normalized_minimal, bytes_minimal, digest_minimal = (
        search_route._parse_temporal_summary_action_body(
            {"action": "prepare", "request": minimal}
        )
    )
    _, normalized_explicit, bytes_explicit, digest_explicit = (
        search_route._parse_temporal_summary_action_body(
            {"action": "prepare", "request": _request(time_hint=None)}
        )
    )

    assert normalized_minimal == normalized_explicit
    assert bytes_minimal == bytes_explicit
    assert digest_minimal == digest_explicit


def test_execution_snapshot_freezes_loopback_endpoint_and_activation_policy(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    snapshot = search_route._resolve_temporal_execution_snapshot(copy.deepcopy(cfg))

    monkeypatch.setenv("GOODQ_OLLAMA_URL", "http://203.0.113.10:9999/v1")

    assert snapshot.allow_service_activation is False
    assert all("127.0.0.1" in model.endpoint for model in snapshot.models)
    assert all("203.0.113.10" not in model.endpoint for model in snapshot.models)


def test_prepare_persists_only_exact_digests_and_token_fingerprint(
    temporal_runtime,
    client,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    result_root = search_route._temporal_summary_result_root(cfg)

    prepared = _prepare(client)

    assert prepared["job"]["state"] == "pending_confirmation"
    assert set(prepared["job"]["scope"]) == {
        "epoch_id",
        "request_sha256",
        "execution_policy_sha256",
    }
    ledger = ActionJobLedger(search_route._temporal_summary_job_root(cfg))
    stored = ledger.load(prepared["job"]["job_id"])
    assert stored is not None
    serialized = json.dumps(stored)
    assert "Jay" not in serialized
    assert "summer 2026" not in serialized
    assert "temporal-confirmation-token" not in serialized
    assert stored["token_fingerprint"] == hashlib.sha256(
        b"temporal-confirmation-token"
    ).hexdigest()
    assert stored["authorization_request_id"] == "temporal-authorization-1"
    assert not result_root.exists()
    assert len(authority.authorize_calls) == 1
    assert authority.authorize_calls[0]["tool_args"] == {
        "job_id": stored["job_id"],
        **stored["scope"],
    }


def test_concurrent_prepare_issues_one_token(
    temporal_runtime,
    client,
) -> None:
    _cfg, authority, _load_configs = temporal_runtime

    def prepare_once() -> int:
        return client.post(
            "/api/search/temporal/summarize",
            json={"action": "prepare", "request": _request()},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _item: prepare_once(), range(2)))

    assert statuses == [200, 409]
    assert len(authority.authorize_calls) == 1


def test_prepare_evidence_failure_revokes_unreturned_token(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime

    def fail_evidence(*_args, **_kwargs):
        raise OSError("private persistence failure")

    monkeypatch.setattr(
        search_route.ActionJobLedger,
        "compare_and_update",
        fail_evidence,
    )

    response = client.post(
        "/api/search/temporal/summarize",
        json={"action": "prepare", "request": _request()},
    )

    assert response.status_code == 503
    assert len(authority.revoke_calls) == 1
    assert authority.revoke_calls[0]["confirmation_token"] == (
        "temporal-confirmation-token"
    )
    records = ActionJobLedger(
        search_route._temporal_summary_job_root(cfg)
    ).list_records(operation=search_route._TEMPORAL_SUMMARY_JOB_OPERATION)
    assert len(records) == 1
    assert records[0]["state"] == "failed"


def test_confirm_resubmits_exact_request_claims_once_and_queues(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    worker = MagicMock()

    async def no_op_worker(*args):
        worker(*args)

    monkeypatch.setattr(search_route, "_temporal_summary_worker", no_op_worker)
    prepared = _prepare(client)

    response = client.post(
        "/api/search/temporal/summarize",
        json=_confirm_body(prepared),
    )

    assert response.status_code == 202, response.text
    persisted = ActionJobLedger(search_route._temporal_summary_job_root(cfg)).load(
        prepared["job"]["job_id"]
    )
    assert persisted["state"] == "queued"
    assert len(authority.authorize_calls) == 2
    assert authority.authorize_calls[-1]["confirm"] is True
    assert authority.authorize_calls[-1]["tool_args"] == {
        "job_id": persisted["job_id"],
        **persisted["scope"],
    }
    worker.assert_called_once()
    worker_args = worker.call_args.args
    assert worker_args[0] == persisted["job_id"]
    assert isinstance(worker_args[1], bytes)
    assert json.loads(worker_args[1]) == _request()


def test_confirm_changed_request_fails_before_authority_or_worker(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    _cfg, authority, _load_configs = temporal_runtime
    worker = MagicMock()
    monkeypatch.setattr(search_route, "_temporal_summary_worker", worker)
    prepared = _prepare(client)

    response = client.post(
        "/api/search/temporal/summarize",
        json=_confirm_body(prepared, _request(time_hint="changed private request")),
    )

    assert response.status_code == 409
    assert len(authority.authorize_calls) == 1
    worker.assert_not_called()


def test_wrong_confirmation_token_leaves_pending_job_unchanged(
    temporal_runtime,
    client,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    prepared = _prepare(client)
    body = _confirm_body(prepared)
    body["confirmation_token"] = "wrong-token"

    response = client.post("/api/search/temporal/summarize", json=body)

    assert response.status_code == 403
    record = ActionJobLedger(search_route._temporal_summary_job_root(cfg)).load(
        prepared["job"]["job_id"]
    )
    assert record["state"] == "pending_confirmation"
    assert len(authority.authorize_calls) == 1


def test_expired_confirmation_terminalizes_without_worker(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    worker = MagicMock()
    monkeypatch.setattr(search_route, "_temporal_summary_worker", worker)
    prepared = _prepare(client)
    authority.confirm_envelope = (
        {
            "request_id": "temporal-authorization-1",
            "status": "error",
            "result": None,
            "errors": [{"code": "token_expired"}],
        },
        1,
    )

    response = client.post(
        "/api/search/temporal/summarize",
        json=_confirm_body(prepared),
    )

    assert response.status_code == 409
    record = ActionJobLedger(search_route._temporal_summary_job_root(cfg)).load(
        prepared["job"]["job_id"]
    )
    assert record["state"] == "expired"
    worker.assert_not_called()


def test_confirmation_request_id_mismatch_fails_before_worker(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    worker = MagicMock()
    monkeypatch.setattr(search_route, "_temporal_summary_worker", worker)
    prepared = _prepare(client)
    authority.confirm_envelope = (
        {
            "request_id": "different-authorization-request",
            "status": "ok",
            "result": {"allowed": True},
            "errors": [],
        },
        0,
    )

    response = client.post(
        "/api/search/temporal/summarize",
        json=_confirm_body(prepared),
    )

    assert response.status_code == 409
    record = ActionJobLedger(search_route._temporal_summary_job_root(cfg)).load(
        prepared["job"]["job_id"]
    )
    assert record["state"] == "failed"
    worker.assert_not_called()


def test_prior_owner_authorizing_claim_recovers_token_already_used(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, _snapshot = _queued_job(
        cfg,
        owner="prior-temporal-owner",
    )
    raw = ledger.load(record["job_id"])
    raw["state"] = "authorizing"
    ledger.record_path(record["job_id"]).write_text(
        json.dumps(raw),
        encoding="utf-8",
    )
    authority.confirm_envelope = (
        {
            "request_id": "temporal-authorization-1",
            "status": "error",
            "result": None,
            "errors": [{"code": "token_already_used"}],
        },
        1,
    )
    worker = MagicMock()

    async def no_op_worker(*args):
        worker(*args)

    monkeypatch.setattr(search_route, "_temporal_summary_worker", no_op_worker)
    prepared = {
        "confirmation_token": "temporal-confirmation-token",
        "job": {"job_id": record["job_id"], "scope": record["scope"]},
    }

    response = client.post(
        "/api/search/temporal/summarize",
        json=_confirm_body(prepared),
    )

    assert response.status_code == 202, response.text
    recovered = ledger.load(record["job_id"])
    assert recovered["state"] == "queued"
    assert recovered["owner_instance"] == search_route._TEMPORAL_SUMMARY_OWNER_INSTANCE
    worker.assert_called_once()


def test_concurrent_confirm_claims_token_and_queues_once(
    temporal_runtime,
    client,
    monkeypatch,
) -> None:
    _cfg, authority, _load_configs = temporal_runtime
    worker = MagicMock()

    async def no_op_worker(*args):
        worker(*args)

    monkeypatch.setattr(search_route, "_temporal_summary_worker", no_op_worker)
    prepared = _prepare(client)
    body = _confirm_body(prepared)

    def confirm_once() -> int:
        return client.post("/api/search/temporal/summarize", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _item: confirm_once(), range(2)))

    assert statuses == [202, 409]
    assert len([call for call in authority.authorize_calls if call.get("confirm")]) == 1
    worker.assert_called_once()


def test_worker_uses_one_snapshot_and_persists_receipt_before_audit(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, authority, load_configs = temporal_runtime
    ledger, record, request_bytes, snapshot = _queued_job(cfg)
    synthesize = MagicMock(return_value=_success_result(snapshot))
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        synthesize,
    )
    result_store = TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    )
    original_external = authority.record_external_execution_outcome

    def assert_receipt_then_audit(**kwargs):
        assert result_store.load_exact(job_id=record["job_id"], **record["scope"])
        assert ledger.load(record["job_id"])["state"] == "running"
        return original_external(**kwargs)

    authority.record_external_execution_outcome = assert_receipt_then_audit
    load_configs.reset_mock()

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    load_configs.assert_called_once_with({})
    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "succeeded"
    assert persisted["audit_status"] == "recorded"
    assert synthesize.call_count == 1
    kwargs = synthesize.call_args.kwargs
    assert kwargs["expected_epoch_id"] == "epoch_current"
    assert kwargs["allow_model_activation"] is False
    assert kwargs["allow_environment_proxies"] is False
    assert kwargs["models"][0].endpoint.startswith("http://127.0.0.1:")
    receipt = result_store.load_exact(job_id=record["job_id"], **record["scope"])
    assert receipt["terminal_state"] == "succeeded"
    assert receipt["result"]["summary"] == "A grounded private narrative."


def test_worker_policy_drift_writes_failure_without_inference(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, request_bytes, _snapshot = _queued_job(cfg)
    changed_cfg = copy.deepcopy(cfg)
    changed_cfg["llm"]["ollama_model"] = "changed-model"
    monkeypatch.setattr(
        search_route,
        "load_configs",
        MagicMock(return_value=changed_cfg),
    )
    synthesize = MagicMock()
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        synthesize,
    )

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    synthesize.assert_not_called()
    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "failed"
    receipt = TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    ).load_exact(job_id=record["job_id"], **record["scope"])
    assert receipt["terminal_state"] == "failed"
    assert receipt["error_code"] == "execution_scope_changed"


def test_worker_rejects_incomplete_authorization_before_running_or_inference(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, request_bytes, _snapshot = _queued_job(cfg)
    raw = ledger.load(record["job_id"])
    raw["authorization_request_id"] = None
    ledger.record_path(record["job_id"]).write_text(json.dumps(raw), encoding="utf-8")
    synthesize = MagicMock()
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        synthesize,
    )

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    synthesize.assert_not_called()
    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "failed"
    assert persisted["outcome"]["code"] == "authorization_evidence_invalid"
    assert not search_route._temporal_summary_result_root(cfg).exists()


def test_worker_converts_invalid_private_projection_to_failure_receipt(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, request_bytes, snapshot = _queued_job(cfg)
    invalid = _success_result(snapshot)
    invalid["segments"][0]["scene_id"] = None
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        MagicMock(return_value=invalid),
    )

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    persisted = ledger.load(record["job_id"])
    receipt = TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    ).load_exact(job_id=record["job_id"], **record["scope"])
    assert persisted["state"] == "failed"
    assert receipt["terminal_state"] == "failed"
    assert receipt["error_code"] == "result_projection_invalid"


def test_worker_runtime_value_error_is_not_misreported_as_scope_drift(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, request_bytes, _snapshot = _queued_job(cfg)
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        MagicMock(side_effect=ValueError("private runtime detail")),
    )

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    receipt = TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    ).load_exact(job_id=record["job_id"], **record["scope"])
    assert ledger.load(record["job_id"])["state"] == "failed"
    assert receipt["error_code"] == "temporal_summary_error"
    assert "private runtime detail" not in json.dumps(receipt)


def test_worker_audit_failure_preserves_success_receipt_and_terminal_truth(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    ledger, record, request_bytes, snapshot = _queued_job(cfg)
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        MagicMock(return_value=_success_result(snapshot)),
    )

    def fail_audit(**_kwargs):
        raise RuntimeError("private audit failure")

    authority.record_external_execution_outcome = fail_audit

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    persisted = ledger.load(record["job_id"])
    receipt = TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    ).load_exact(job_id=record["job_id"], **record["scope"])
    assert persisted["state"] == "succeeded"
    assert persisted["audit_status"] == "failed"
    assert receipt["terminal_state"] == "succeeded"


def test_worker_receipt_persistence_failure_stays_running_without_audit(
    temporal_runtime,
    monkeypatch,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    ledger, record, request_bytes, snapshot = _queued_job(cfg)
    monkeypatch.setattr(
        "retrieval.narrative_summarizer.synthesize_narrative",
        MagicMock(return_value=_success_result(snapshot)),
    )
    monkeypatch.setattr(
        search_route.TemporalSummaryResultStore,
        "write_success",
        MagicMock(side_effect=OSError("private persistence failure")),
    )

    asyncio.run(
        search_route._temporal_summary_worker(
            record["job_id"],
            request_bytes,
            search_route._temporal_summary_job_root(cfg),
        )
    )

    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "running"
    assert persisted["outcome"] is None
    assert persisted["audit_status"] is None
    assert authority.external_calls == []


def test_passive_get_absent_job_creates_nothing(temporal_runtime, client) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    job_root = search_route._temporal_summary_job_root(cfg)
    result_root = search_route._temporal_summary_result_root(cfg)

    response = client.get(
        "/api/search/temporal/summarize/job_00000000000000000000000000000000"
    )

    assert response.status_code == 404
    assert not job_root.exists()
    assert not result_root.exists()


def test_passive_get_returns_exact_receipt_without_changing_job(
    temporal_runtime,
    client,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, snapshot = _queued_job(cfg)
    running = ledger.transition(
        record["job_id"], expected_states="queued", new_state="running"
    )
    receipt = TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    ).write_success(
        job_id=record["job_id"],
        **record["scope"],
        started_at_utc=running["updated_at_utc"],
        result={
            "summary": "A grounded private narrative.",
            "segments": [],
            "source_scene_ids": ["scene_0001"],
            "source_count": 1,
            "truncated": False,
            "warning_codes": [],
        },
        model_evidence={
            "model_id": snapshot.models[0].model_id,
            "provider": snapshot.models[0].backend,
        },
    )
    terminal = ledger.transition(
        record["job_id"],
        expected_states="running",
        new_state="succeeded",
        outcome={"code": "temporal_summary_generated", "message": "Temporal summary generation succeeded"},
        audit_status="recorded",
    )
    before_bytes = ledger.record_path(record["job_id"]).read_bytes()

    response = client.get(f"/api/search/temporal/summarize/{record['job_id']}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["receipt"] == receipt
    assert set(payload["job"]) == {
        "job_id",
        "operation",
        "scope",
        "state",
        "created_at_utc",
        "updated_at_utc",
        "outcome",
        "audit_status",
    }
    assert payload["job"]["state"] == terminal["state"]
    assert ledger.record_path(record["job_id"]).read_bytes() == before_bytes


def test_passive_get_allows_preexecution_failure_without_receipt(
    temporal_runtime,
    client,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    snapshot = search_route._resolve_temporal_execution_snapshot(copy.deepcopy(cfg))
    ledger = ActionJobLedger(search_route._temporal_summary_job_root(cfg))
    record = ledger.create_pending(
        operation=search_route._TEMPORAL_SUMMARY_JOB_OPERATION,
        scope=search_route._temporal_summary_scope(
            epoch_id=snapshot.epoch_id,
            request_sha256="a" * 64,
            execution_policy_sha256=snapshot.execution_policy_sha256,
        ),
        owner_instance=search_route._TEMPORAL_SUMMARY_OWNER_INSTANCE,
    )
    failed = ledger.transition(
        record["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
        outcome={
            "code": "authorization_prepare_failed",
            "message": "Temporal summary authorization could not be prepared",
        },
    )

    response = client.get(f"/api/search/temporal/summarize/{record['job_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["receipt"] is None
    assert response.json()["job"]["outcome"] == failed["outcome"]


def test_passive_get_fails_closed_on_missing_or_malformed_success_receipt(
    temporal_runtime,
    client,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, _snapshot = _queued_job(cfg)
    ledger.transition(record["job_id"], expected_states="queued", new_state="running")
    ledger.transition(
        record["job_id"],
        expected_states="running",
        new_state="succeeded",
        outcome={
            "code": "temporal_summary_generated",
            "message": "Temporal summary generation succeeded",
        },
        audit_status="recorded",
    )
    before = ledger.record_path(record["job_id"]).read_bytes()

    missing = client.get(f"/api/search/temporal/summarize/{record['job_id']}")
    assert missing.status_code == 409

    result_root = search_route._temporal_summary_result_root(cfg)
    result_root.mkdir(parents=True)
    (result_root / f"{record['job_id']}.json").write_text("{malformed", encoding="utf-8")
    malformed = client.get(f"/api/search/temporal/summarize/{record['job_id']}")

    assert malformed.status_code == 409
    assert ledger.record_path(record["job_id"]).read_bytes() == before


def test_passive_get_rejects_receiptless_postexecution_failure(
    temporal_runtime,
    client,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, _snapshot = _queued_job(cfg)
    ledger.transition(record["job_id"], expected_states="queued", new_state="running")
    ledger.transition(
        record["job_id"],
        expected_states="running",
        new_state="failed",
        outcome={
            "code": "result_persistence_failed",
            "message": "Temporal summary result persistence failed",
        },
        audit_status="failed",
    )

    response = client.get(f"/api/search/temporal/summarize/{record['job_id']}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "result_invalid"


def test_recovery_uses_exact_receipt_without_replaying_inference(
    temporal_runtime,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, snapshot = _queued_job(
        cfg,
        owner="prior-temporal-owner",
    )
    TemporalSummaryResultStore(
        search_route._temporal_summary_result_root(cfg)
    ).write_success(
        job_id=record["job_id"],
        **record["scope"],
        started_at_utc=record["updated_at_utc"],
        result={
            "summary": "Recovered grounded narrative.",
            "segments": [],
            "source_scene_ids": ["scene_0001"],
            "source_count": 1,
            "truncated": False,
            "warning_codes": [],
        },
        model_evidence={
            "model_id": snapshot.models[0].model_id,
            "provider": snapshot.models[0].backend,
        },
    )

    search_route._reconcile_temporal_summary_jobs(copy.deepcopy(cfg))

    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "succeeded"
    assert persisted["audit_status"] == "recorded"
    assert authority.external_calls[-1]["status"] == "succeeded"


def test_recovery_interrupts_prior_queued_job_without_receipt(
    temporal_runtime,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, _snapshot = _queued_job(
        cfg,
        owner="prior-temporal-owner",
    )

    search_route._reconcile_temporal_summary_jobs(copy.deepcopy(cfg))

    persisted = ledger.load(record["job_id"])
    assert persisted["state"] == "interrupted"
    assert authority.external_calls[-1]["status"] == "interrupted"
    assert authority.external_calls[-1]["side_effect_report"]["mutated"] is False


def test_recovery_preserves_complete_pending_authorization_byte_for_byte(
    temporal_runtime,
) -> None:
    cfg, authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, _snapshot = _queued_job(
        cfg,
        owner="prior-temporal-owner",
    )
    raw = ledger.load(record["job_id"])
    raw["state"] = "pending_confirmation"
    ledger.record_path(record["job_id"]).write_text(
        json.dumps(raw, indent=2),
        encoding="utf-8",
    )
    before = ledger.record_path(record["job_id"]).read_bytes()

    search_route._reconcile_temporal_summary_jobs(copy.deepcopy(cfg))

    assert ledger.record_path(record["job_id"]).read_bytes() == before
    assert authority.external_calls == []


def test_recovery_fails_closed_on_malformed_receipt_without_state_change(
    temporal_runtime,
) -> None:
    cfg, _authority, _load_configs = temporal_runtime
    ledger, record, _request_bytes, _snapshot = _queued_job(
        cfg,
        owner="prior-temporal-owner",
    )
    before = ledger.record_path(record["job_id"]).read_bytes()
    result_root = search_route._temporal_summary_result_root(cfg)
    result_root.mkdir(parents=True)
    (result_root / f"{record['job_id']}.json").write_text("{malformed", encoding="utf-8")

    with pytest.raises(RuntimeError, match="malformed"):
        search_route._reconcile_temporal_summary_jobs(copy.deepcopy(cfg))

    assert ledger.record_path(record["job_id"]).read_bytes() == before
