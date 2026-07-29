from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app
from api.routes import identity as identity_route
from api.utils.action_jobs import (
    ActionJobLedger,
    ActionJobTransitionError,
    PassiveActionJobReader,
)


REBUILD_OPERATION = "identity.rebuild_face_clusters"
VALIDATE_OPERATION = "identity.validate_roster"
IDENTITY_OPERATIONS = {REBUILD_OPERATION, VALIDATE_OPERATION}


@pytest.fixture
def client() -> TestClient:
    return TestClient(
        app,
        raise_server_exceptions=False,
        client=("127.0.0.1", 50000),
    )


@pytest.fixture(autouse=True)
def isolate_identity_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_route, "_CFG", {})


class _Authority:
    def __init__(self, *, audit_error: Exception | None = None) -> None:
        self.audit_error = audit_error
        self.authorize_calls: list[dict[str, Any]] = []
        self.audit_calls: list[dict[str, Any]] = []

    def authorize_action(self, **kwargs: Any) -> tuple[dict[str, Any], int]:
        self.authorize_calls.append(kwargs)
        return (
            {
                "status": "ok",
                "request_id": "req-" + "a" * 16,
                "result": {"allowed": True},
                "errors": [],
            },
            0,
        )

    def record_external_execution_outcome(self, **kwargs: Any) -> dict[str, Any]:
        self.audit_calls.append(kwargs)
        if self.audit_error is not None:
            raise self.audit_error
        return {"audit_status": "recorded", "error_codes": []}


def _job_root(identity_root: Path) -> Path:
    return identity_root / "process_jobs"


def _rebuild_scope(*, eps: float = 0.4, epoch_id: str = "epoch-test") -> dict[str, Any]:
    return {"epoch_id": epoch_id, "eps": eps}


def _record_in_state(
    ledger: ActionJobLedger,
    state: str,
    *,
    operation: str = REBUILD_OPERATION,
    scope: dict[str, Any] | None = None,
    owner_instance: str = "identity-api:host-old:100:abc123:old-instance",
) -> dict[str, Any]:
    if scope is None:
        scope = _rebuild_scope()
    record = ledger.create_pending(
        operation=operation,
        scope=scope,
        owner_instance=owner_instance,
    )
    if state == "pending_confirmation":
        return record
    if state in {"failed", "expired"}:
        return ledger.transition(
            record["job_id"],
            expected_states="pending_confirmation",
            new_state=state,
            outcome={
                "code": "test_terminal",
                "message": "Test terminal record",
            },
        )
    record = ledger.transition(
        record["job_id"],
        expected_states="pending_confirmation",
        new_state="authorizing",
        token_fingerprint="0" * 64,
        authorization_request_id="req-" + "1" * 16,
    )
    if state == "authorizing":
        return record
    record = ledger.transition(
        record["job_id"],
        expected_states="authorizing",
        new_state="queued",
    )
    if state == "queued":
        return record
    record = ledger.transition(
        record["job_id"],
        expected_states="queued",
        new_state="running",
    )
    if state == "running":
        return record
    if state in {"succeeded", "interrupted"}:
        return ledger.transition(
            record["job_id"],
            expected_states="running",
            new_state=state,
            outcome={
                "code": "test_terminal",
                "message": "Test terminal record",
            },
            audit_status="recorded",
        )
    raise AssertionError(f"unsupported test state: {state}")


def _record_snapshot(ledger: ActionJobLedger, job_id: str) -> tuple[bytes, int]:
    path = ledger.record_path(job_id)
    return path.read_bytes(), path.stat().st_mtime_ns


def _inject_launch_metadata(
    ledger: ActionJobLedger,
    record: dict[str, Any],
    **metadata: Any,
) -> dict[str, Any]:
    path = ledger.record_path(record["job_id"])
    persisted = json.loads(path.read_text(encoding="utf-8"))
    persisted.update(metadata)
    path.write_text(json.dumps(persisted, sort_keys=True), encoding="utf-8")
    return persisted


def _root_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    if not root.exists():
        return {}
    return {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.iterdir())
        if path.is_file()
    }


def _public_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "job_id",
            "operation",
            "scope",
            "state",
            "created_at_utc",
            "updated_at_utc",
            "outcome",
            "audit_status",
        )
    }


def test_process_owner_binds_safe_host_pid_start_token_and_random_instance() -> None:
    owner = identity_route._IDENTITY_PROCESS_OWNER_INSTANCE
    parts = owner.split(":")

    assert len(parts) == 5
    prefix, host_fingerprint, pid, start_token, random_instance = parts
    assert prefix == "identity-api"
    assert re.fullmatch(r"[0-9a-f]{16}", host_fingerprint)
    assert pid == str(os.getpid())
    assert re.fullmatch(r"(?:[0-9a-f]{1,32}|unknown)", start_token)
    assert re.fullmatch(r"[0-9a-f]{32}", random_instance)
    assert re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", owner)

    expected = "live" if os.name == "nt" or Path("/proc").is_dir() else "unknown"
    assert identity_route._classify_identity_process_owner(owner) == expected


def test_pid_reuse_is_classified_dead_by_start_token_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = identity_route._IDENTITY_PROCESS_OWNER_INSTANCE
    persisted_start = owner.split(":")[3]
    replacement_start = "1" if persisted_start != "1" else "2"
    monkeypatch.setattr(
        identity_route,
        "_probe_process_start_token",
        lambda _pid: ("live", replacement_start),
        raising=False,
    )

    assert identity_route._classify_identity_process_owner(owner) == "dead"


@pytest.mark.skipif(os.name != "nt", reason="Windows process wait oracle")
def test_windows_process_probe_distinguishes_exited_259_from_live_sleeper() -> None:
    with subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(259)"],
        close_fds=True,
    ) as exited:
        assert exited.wait(timeout=10) == 259
        assert identity_route._windows_process_start_token(exited.pid) == (
            "dead",
            None,
        )

    with subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        close_fds=True,
    ) as sleeper:
        try:
            state, token = identity_route._windows_process_start_token(sleeper.pid)
            assert state == "live"
            assert isinstance(token, str) and re.fullmatch(r"[0-9a-f]{1,32}", token)
        finally:
            sleeper.terminate()
            sleeper.wait(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Windows process wait oracle")
def test_windows_process_probe_wait_failure_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes

    class _Function:
        def __init__(self, result: int) -> None:
            self.result = result
            self.calls: list[tuple[Any, ...]] = []
            self.argtypes: list[Any] = []
            self.restype: Any = None

        def __call__(self, *args: Any) -> int:
            self.calls.append(args)
            return self.result

    class _Kernel32:
        def __init__(self) -> None:
            self.OpenProcess = _Function(123)
            self.WaitForSingleObject = _Function(0xFFFFFFFF)
            self.GetProcessTimes = _Function(1)
            self.CloseHandle = _Function(1)

    kernel32 = _Kernel32()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_kw: kernel32)

    assert identity_route._windows_process_start_token(4321) == ("unknown", None)
    assert len(kernel32.WaitForSingleObject.calls) == 1
    assert kernel32.GetProcessTimes.calls == []
    assert len(kernel32.CloseHandle.calls) == 1


@pytest.mark.parametrize(
    ("owner", "probe_result"),
    [
        ("malformed-owner", ("live", "abc")),
        ("identity-api:ffffffffffffffff:123:abc:0123456789abcdef0123456789abcdef", ("live", "abc")),
        (None, ("live", "abc")),
    ],
)
def test_malformed_or_foreign_host_owner_is_unknown(
    owner: Any,
    probe_result: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        identity_route,
        "_probe_process_start_token",
        lambda _pid: probe_result,
        raising=False,
    )

    assert identity_route._classify_identity_process_owner(owner) == "unknown"


def test_passive_get_reads_safe_projection_without_mutating_filesystem(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    root = _job_root(identity_root)
    ledger = ActionJobLedger(root)
    record = _record_in_state(
        ledger,
        "succeeded",
        owner_instance="identity-api:host-old:100:abc123:old-instance",
    )
    before = _root_snapshot(root)
    reader_calls: list[str] = []

    class _TrackingReader(PassiveActionJobReader):
        def load(self, job_id: str) -> dict[str, Any] | None:
            reader_calls.append(job_id)
            return super().load(job_id)

    def _forbidden_writer(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("passive GET constructed ActionJobLedger")

    monkeypatch.setattr(
        identity_route,
        "PassiveActionJobReader",
        _TrackingReader,
        raising=False,
    )
    monkeypatch.setattr(
        identity_route,
        "ActionJobLedger",
        _forbidden_writer,
        raising=False,
    )
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("passive GET executed subprocess")
        ),
    )

    response = client.get(f"/api/identity/process-jobs/{record['job_id']}")

    assert response.status_code == 200, response.text
    assert response.json() == _public_projection(record)
    assert reader_calls == [record["job_id"]]
    assert _root_snapshot(root) == before
    serialized = response.text
    assert "owner_instance" not in serialized
    assert "token_fingerprint" not in serialized
    assert "authorization_request_id" not in serialized


def test_passive_get_missing_root_is_noncreating(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))

    response = client.get(
        "/api/identity/process-jobs/job_00000000000000000000000000000000"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "identity_process_job_not_found"}
    assert not identity_root.exists()


def test_passive_get_rejects_invalid_and_foreign_jobs(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))

    invalid = client.get("/api/identity/process-jobs/not-a-job")
    assert invalid.status_code == 404
    assert invalid.json() == {"detail": "identity_process_job_not_found"}

    ledger = ActionJobLedger(_job_root(identity_root))
    foreign = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": "a" * 32},
        owner_instance="summary-api:old",
    )
    before = _record_snapshot(ledger, foreign["job_id"])

    response = client.get(f"/api/identity/process-jobs/{foreign['job_id']}")

    assert response.status_code == 404
    assert response.json() == {"detail": "identity_process_job_not_found"}
    assert _record_snapshot(ledger, foreign["job_id"]) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_id", "job_" + "e" * 32),
        ("state", "invented_state"),
        ("created_at_utc", "not-a-canonical-timestamp"),
        (
            "outcome",
            {
                "code": "crafted",
                "message": "Recovered from C:/private/identity/job.json",
            },
        ),
    ],
)
def test_passive_get_rejects_semantically_malformed_persisted_job(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    identity_root = tmp_path / field
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    ledger = ActionJobLedger(_job_root(identity_root))
    record = _record_in_state(ledger, "succeeded")
    path = ledger.record_path(record["job_id"])
    corrupted = json.loads(path.read_text(encoding="utf-8"))
    corrupted[field] = value
    path.write_text(json.dumps(corrupted), encoding="utf-8")
    before = _root_snapshot(_job_root(identity_root))

    response = client.get(f"/api/identity/process-jobs/{record['job_id']}")

    assert response.status_code == 404
    assert response.json() == {"detail": "identity_process_job_not_found"}
    assert _root_snapshot(_job_root(identity_root)) == before


@pytest.mark.parametrize(
    ("owner_instance", "classification"),
    [
        ("identity-api:host-live:100:abc123:live-instance", "live"),
        ("identity-api:host-unknown:101:def456:unknown-instance", "unknown"),
    ],
)
def test_request_keeps_live_or_unknown_prior_owner_blocking_byte_for_byte(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_instance: str,
    classification: str,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    active = _record_in_state(
        ledger,
        "running",
        owner_instance=owner_instance,
    )
    before = _record_snapshot(ledger, active["job_id"])
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: classification if owner == owner_instance else "unknown",
        raising=False,
    )
    run = MagicMock(side_effect=AssertionError("duplicate subprocess launched"))
    monkeypatch.setattr(identity_route.subprocess, "run", run)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-active"},
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "identity_process_active"}
    assert len(authority.authorize_calls) == 1
    run.assert_not_called()
    assert _record_snapshot(ledger, active["job_id"]) == before


@pytest.mark.parametrize("child_classification", ["live", "unknown"])
def test_dead_parent_with_live_or_unknown_gated_child_blocks_byte_for_byte(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    child_classification: str,
) -> None:
    identity_root = tmp_path / child_classification
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:102:fedcba:dead-instance"
    active = _record_in_state(ledger, "running", owner_instance=prior_owner)
    active = _inject_launch_metadata(
        ledger,
        active,
        launch_protocol="stdin_gate_v1",
        child_pid=4321,
        child_start_token="abc123",
    )
    before = _record_snapshot(ledger, active["job_id"])
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
    )
    child_probe = MagicMock(return_value=child_classification)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        child_probe,
        raising=False,
    )
    monkeypatch.setattr(
        identity_route.subprocess,
        "Popen",
        MagicMock(side_effect=AssertionError("duplicate child launched")),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-child-active"},
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "identity_process_active"}
    child_probe.assert_called_once_with(4321, "abc123")
    assert _record_snapshot(ledger, active["job_id"]) == before
    assert authority.audit_calls == []


def test_dead_parent_with_dead_gated_child_recovers_once_without_boolean_audit(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "dead-child"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:103:fedcba:dead-instance"
    active = _record_in_state(ledger, "running", owner_instance=prior_owner)
    _inject_launch_metadata(
        ledger,
        active,
        launch_protocol="stdin_gate_v1",
        child_pid=4322,
        child_start_token="abc124",
    )
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
    )
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        lambda pid, token: "dead" if (pid, token) == (4322, "abc124") else "unknown",
        raising=False,
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-child-dead"},
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "identity_process_recovered_retry_required"}
    recovered = ledger.load(active["job_id"])
    assert recovered is not None
    assert recovered["state"] == "interrupted"
    assert recovered["audit_status"] == "not_recorded_mutation_unknown"
    assert authority.audit_calls == []


@pytest.mark.parametrize(
    ("metadata", "expected_status", "expected_audits"),
    [
        ({"launch_protocol": "stdin_gate_v1"}, "interrupted", 1),
        ({}, "running", 0),
    ],
)
def test_dead_parent_gated_no_pair_recovers_while_identical_legacy_record_blocks(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata: dict[str, Any],
    expected_status: str,
    expected_audits: int,
) -> None:
    identity_root = tmp_path / ("gated" if metadata else "legacy")
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:104:fedcba:dead-instance"
    active = _record_in_state(ledger, "running", owner_instance=prior_owner)
    if metadata:
        _inject_launch_metadata(ledger, active, **metadata)
    before = _record_snapshot(ledger, active["job_id"])
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
    )
    child_probe = MagicMock(side_effect=AssertionError("no child pair must not be probed"))
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        child_probe,
        raising=False,
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-no-pair"},
    )

    assert response.status_code == 409, response.text
    persisted = ledger.load(active["job_id"])
    assert persisted is not None
    assert persisted["state"] == expected_status
    if metadata:
        assert response.json() == {"detail": "identity_process_recovered_retry_required"}
        assert authority.audit_calls[0]["side_effect_report"]["mutated"] is False
    else:
        assert response.json() == {"detail": "identity_process_active"}
        assert _record_snapshot(ledger, active["job_id"]) == before
    assert len(authority.audit_calls) == expected_audits
    child_probe.assert_not_called()


@pytest.mark.parametrize(
    "metadata",
    [
        {"launch_protocol": "other_protocol"},
        {"launch_protocol": "stdin_gate_v1", "child_pid": 4321},
        {"launch_protocol": "stdin_gate_v1", "child_start_token": "abc123"},
        {
            "launch_protocol": "stdin_gate_v1",
            "child_pid": True,
            "child_start_token": "abc123",
        },
        {
            "launch_protocol": "stdin_gate_v1",
            "child_pid": 0,
            "child_start_token": "abc123",
        },
        {
            "launch_protocol": "stdin_gate_v1",
            "child_pid": 4321,
            "child_start_token": "not safe",
        },
        {"child_pid": 4321, "child_start_token": "abc123"},
    ],
)
def test_malformed_launch_metadata_fails_closed_on_all_surfaces_without_probe_or_write(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata: dict[str, Any],
) -> None:
    identity_root = tmp_path / str(len(metadata)) / str(abs(hash(repr(metadata))))
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:105:fedcba:dead-instance"
    active = _record_in_state(ledger, "running", owner_instance=prior_owner)
    _inject_launch_metadata(ledger, active, **metadata)
    before = _record_snapshot(ledger, active["job_id"])
    owner_probe = MagicMock(side_effect=AssertionError("malformed job owner probed"))
    child_probe = MagicMock(side_effect=AssertionError("malformed job child probed"))
    popen = MagicMock(side_effect=AssertionError("malformed job launched child"))
    monkeypatch.setattr(identity_route, "_classify_identity_process_owner", owner_probe)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        child_probe,
        raising=False,
    )
    monkeypatch.setattr(identity_route.subprocess, "Popen", popen)
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)

    passive = client.get(f"/api/identity/process-jobs/{active['job_id']}")
    assert passive.status_code == 404
    assert passive.json() == {"detail": "identity_process_job_not_found"}
    assert _record_snapshot(ledger, active["job_id"]) == before

    with pytest.raises(ValueError):
        identity_route._reconcile_identity_process_jobs()
    assert _record_snapshot(ledger, active["job_id"]) == before

    authorized = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-malformed"},
    )
    assert authorized.status_code == 500, authorized.text
    assert authorized.json() == {"detail": "identity_process_state_invalid"}
    assert _record_snapshot(ledger, active["job_id"]) == before
    owner_probe.assert_not_called()
    child_probe.assert_not_called()
    popen.assert_not_called()
    assert authority.audit_calls == []


@pytest.mark.parametrize(
    ("child_state", "expected_audits", "expected_audit_status"),
    [
        (None, 1, "recorded"),
        ("dead", 0, "not_recorded_mutation_unknown"),
    ],
)
def test_concurrent_gated_recovery_has_one_owner_cas_winner_and_exact_audit_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    child_state: str | None,
    expected_audits: int,
    expected_audit_status: str,
) -> None:
    identity_root = tmp_path / (child_state or "no-pair")
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    root = _job_root(identity_root)
    ledger = ActionJobLedger(root)
    prior_owner = "identity-api:host-dead:106:fedcba:dead-instance"
    running = _record_in_state(ledger, "running", owner_instance=prior_owner)
    metadata: dict[str, Any] = {"launch_protocol": "stdin_gate_v1"}
    if child_state is not None:
        metadata.update(child_pid=4321, child_start_token="abc123")
    running = _inject_launch_metadata(ledger, running, **metadata)
    authority = _Authority()
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
    )
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        lambda _pid, _token: child_state,
        raising=False,
    )

    def recover_once() -> str:
        try:
            identity_route._recover_dead_identity_process_job(
                ActionJobLedger(root),
                dict(running),
                authority=authority,
            )
            return "won"
        except ActionJobTransitionError:
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: recover_once(), range(2)))

    assert sorted(outcomes) == ["lost", "won"]
    persisted = ledger.load(running["job_id"])
    assert persisted is not None
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == expected_audit_status
    assert len(authority.audit_calls) == expected_audits
    if authority.audit_calls:
        assert authority.audit_calls[0]["side_effect_report"]["mutated"] is False


def test_current_owner_duplicate_is_blocking_without_liveness_probe(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    active = _record_in_state(
        ledger,
        "queued",
        owner_instance=identity_route._IDENTITY_PROCESS_OWNER_INSTANCE,
    )
    before = _record_snapshot(ledger, active["job_id"])
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda _owner: (_ for _ in ()).throw(
            AssertionError("current owner must not be probed as prior")
        ),
        raising=False,
    )
    run = MagicMock(side_effect=AssertionError("duplicate subprocess launched"))
    monkeypatch.setattr(identity_route.subprocess, "run", run)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-current"},
    )

    assert response.status_code == 409, response.text
    run.assert_not_called()
    assert _record_snapshot(ledger, active["job_id"]) == before


@pytest.mark.parametrize(
    ("state", "expected_terminal"),
    [
        ("pending_confirmation", "failed"),
        ("running", "interrupted"),
    ],
)
def test_request_recovers_dead_owner_but_conflicts_without_launch_or_replay(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    expected_terminal: str,
) -> None:
    identity_root = tmp_path / state
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:102:fedcba:dead-instance"
    active = _record_in_state(ledger, state, owner_instance=prior_owner)
    if state == "running":
        active = _inject_launch_metadata(
            ledger,
            active,
            launch_protocol="stdin_gate_v1",
            child_pid=4321,
            child_start_token="abc123",
        )
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
        raising=False,
    )
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        lambda _pid, _token: "dead",
        raising=False,
    )
    run = MagicMock(side_effect=AssertionError("recovery replayed subprocess"))
    monkeypatch.setattr(identity_route.subprocess, "run", run)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-recover"},
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "identity_process_recovered_retry_required"}
    run.assert_not_called()
    records = ledger.list_records(operation=REBUILD_OPERATION, scope=_rebuild_scope())
    assert [record["job_id"] for record in records] == [active["job_id"]]
    recovered = records[0]
    assert recovered["state"] == expected_terminal
    assert recovered["owner_instance"] == prior_owner
    assert recovered["state"] != "succeeded"
    if state == "running":
        assert recovered["audit_status"] == "not_recorded_mutation_unknown"
        assert authority.audit_calls == []
    else:
        assert authority.audit_calls == []


def test_startup_recovery_terminalizes_every_dead_nonterminal_state_by_owner_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:200:abc123:dead-instance"
    source_states = (
        "pending_confirmation",
        "authorizing",
        "queued",
        "running",
    )
    records = {
        state: _record_in_state(
            ledger,
            state,
            scope=_rebuild_scope(eps=0.20 + index / 100),
            owner_instance=prior_owner,
        )
        for index, state in enumerate(source_states)
    }
    records["running"] = _inject_launch_metadata(
        ledger,
        records["running"],
        launch_protocol="stdin_gate_v1",
        child_pid=4321,
        child_start_token="abc123",
    )
    validation_running = _record_in_state(
        ledger,
        "running",
        operation=VALIDATE_OPERATION,
        scope={},
        owner_instance=prior_owner,
    )
    authority = _Authority()
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
        raising=False,
    )
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_child",
        lambda _pid, _token: "dead",
        raising=False,
    )
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("startup recovery executed subprocess")
        ),
    )

    class _TrackingLedger(ActionJobLedger):
        owner_cas: list[tuple[str, str, str]] = []

        def adopt_and_transition(
            self,
            job_id: str,
            *,
            expected_state: str,
            expected_owner_instance: str,
            new_owner_instance: str,
            new_state: str,
            **updates: Any,
        ) -> dict[str, Any]:
            type(self).owner_cas.append(
                (job_id, expected_owner_instance, new_owner_instance)
            )
            return super().adopt_and_transition(
                job_id,
                expected_state=expected_state,
                expected_owner_instance=expected_owner_instance,
                new_owner_instance=new_owner_instance,
                new_state=new_state,
                **updates,
            )

    monkeypatch.setattr(identity_route, "ActionJobLedger", _TrackingLedger, raising=False)

    identity_route._reconcile_identity_process_jobs()

    expected = {
        "pending_confirmation": "failed",
        "authorizing": "failed",
        "queued": "interrupted",
        "running": "interrupted",
    }
    for source_state, source in records.items():
        persisted = ledger.load(source["job_id"])
        assert persisted is not None
        assert persisted["state"] == expected[source_state]
        assert persisted["owner_instance"] == prior_owner
        assert persisted["state"] != "succeeded"
    persisted_validation = ledger.load(validation_running["job_id"])
    assert persisted_validation is not None
    assert persisted_validation["state"] == "interrupted"
    assert persisted_validation["owner_instance"] == prior_owner
    assert all(expected_owner == replacement_owner == prior_owner for _, expected_owner, replacement_owner in _TrackingLedger.owner_cas)
    assert len(_TrackingLedger.owner_cas) == 5
    assert len(authority.audit_calls) == 2
    rebuild_audits = [
        call for call in authority.audit_calls if call["operation"] == REBUILD_OPERATION
    ]
    validation_audits = [
        call for call in authority.audit_calls if call["operation"] == VALIDATE_OPERATION
    ]
    assert len(rebuild_audits) == 1
    assert all(set(call["arguments"]) == {"eps"} for call in rebuild_audits)
    assert [call["arguments"] for call in validation_audits] == [{}]
    persisted_running_rebuild = ledger.load(records["running"]["job_id"])
    assert persisted_running_rebuild is not None
    assert (
        persisted_running_rebuild["audit_status"]
        == "not_recorded_mutation_unknown"
    )


def test_startup_recovery_preserves_live_unknown_current_terminal_and_foreign_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    ledger = ActionJobLedger(_job_root(identity_root))
    live_owner = "identity-api:host-live:300:abc123:live-instance"
    unknown_owner = "identity-api:host-unknown:301:def456:unknown-instance"
    live = _record_in_state(
        ledger,
        "running",
        scope=_rebuild_scope(eps=0.31),
        owner_instance=live_owner,
    )
    unknown = _record_in_state(
        ledger,
        "queued",
        scope=_rebuild_scope(eps=0.32),
        owner_instance=unknown_owner,
    )
    current = _record_in_state(
        ledger,
        "authorizing",
        scope=_rebuild_scope(eps=0.33),
        owner_instance=identity_route._IDENTITY_PROCESS_OWNER_INSTANCE,
    )
    terminal = _record_in_state(
        ledger,
        "failed",
        scope=_rebuild_scope(eps=0.34),
        owner_instance="identity-api:host-dead:302:aaa111:terminal-instance",
    )
    foreign = _record_in_state(
        ledger,
        "running",
        operation="video_summary.generate",
        scope={"video_hash": "b" * 32},
        owner_instance="summary-api:old",
    )
    protected = [live, unknown, current, terminal, foreign]
    before = {
        record["job_id"]: _record_snapshot(ledger, record["job_id"])
        for record in protected
    }
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: {
            live_owner: "live",
            unknown_owner: "unknown",
        }.get(owner, "dead"),
        raising=False,
    )
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("startup recovery executed subprocess")
        ),
    )

    identity_route._reconcile_identity_process_jobs()

    after = {
        record["job_id"]: _record_snapshot(ledger, record["job_id"])
        for record in protected
    }
    assert after == before


def test_startup_recovery_fails_visible_on_malformed_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    root = _job_root(identity_root)
    root.mkdir(parents=True)
    (root / ("job_" + "f" * 32 + ".json")).write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(json.JSONDecodeError):
        identity_route._reconcile_identity_process_jobs()


def test_startup_semantic_validation_prevents_job_id_cas_redirection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    ledger = ActionJobLedger(_job_root(identity_root))
    victim = _record_in_state(
        ledger,
        "running",
        scope=_rebuild_scope(eps=0.41),
        owner_instance=identity_route._IDENTITY_PROCESS_OWNER_INSTANCE,
    )
    attacker_owner = "identity-api:host-dead:999:abc123:redirection"
    attacker = _record_in_state(
        ledger,
        "running",
        scope=_rebuild_scope(eps=0.42),
        owner_instance=attacker_owner,
    )
    attacker_path = ledger.record_path(attacker["job_id"])
    redirected = json.loads(attacker_path.read_text(encoding="utf-8"))
    redirected["job_id"] = victim["job_id"]
    attacker_path.write_text(json.dumps(redirected), encoding="utf-8")
    before = {
        path.name: path.read_bytes()
        for path in _job_root(identity_root).glob("job_*.json")
    }
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == attacker_owner else "live",
    )
    run = MagicMock(side_effect=AssertionError("recovery executed subprocess"))
    monkeypatch.setattr(identity_route.subprocess, "run", run)

    with pytest.raises(ValueError, match="job"):
        identity_route._reconcile_identity_process_jobs()

    after = {
        path.name: path.read_bytes()
        for path in _job_root(identity_root).glob("job_*.json")
    }
    assert after == before
    run.assert_not_called()


def test_startup_missing_job_root_is_noncreating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))

    identity_route._reconcile_identity_process_jobs()

    assert not identity_root.exists()


def test_recovery_audit_failure_still_terminalizes_dead_running_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:400:abc123:audit-failure"
    running = _record_in_state(
        ledger,
        "running",
        operation=VALIDATE_OPERATION,
        scope={},
        owner_instance=prior_owner,
    )
    authority = _Authority(audit_error=RuntimeError("sensitive audit detail"))
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
        raising=False,
    )

    identity_route._reconcile_identity_process_jobs()

    persisted = ledger.load(running["job_id"])
    assert persisted is not None
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == "failed"
    assert "sensitive" not in json.dumps(persisted)


def test_recovery_authority_constructor_failure_still_terminalizes_dead_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    ledger = ActionJobLedger(_job_root(identity_root))
    prior_owner = "identity-api:host-dead:401:abc123:constructor-failure"
    running = _record_in_state(
        ledger,
        "running",
        operation=VALIDATE_OPERATION,
        scope={},
        owner_instance=prior_owner,
    )
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
    )
    monkeypatch.setattr(
        identity_route,
        "MiniAgentClient",
        MagicMock(side_effect=RuntimeError("sensitive constructor failure")),
    )
    run = MagicMock(side_effect=AssertionError("recovery executed subprocess"))
    monkeypatch.setattr(identity_route.subprocess, "run", run)

    identity_route._reconcile_identity_process_jobs()

    persisted = ledger.load(running["job_id"])
    assert persisted is not None
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == "failed"
    assert "sensitive" not in json.dumps(persisted)
    run.assert_not_called()


def test_concurrent_startup_recovery_audits_only_the_owner_cas_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_root = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_root))
    root = _job_root(identity_root)
    ledger = ActionJobLedger(root)
    prior_owner = "identity-api:host-dead:402:abc123:concurrent-recovery"
    running = _record_in_state(
        ledger,
        "running",
        operation=VALIDATE_OPERATION,
        scope={},
        owner_instance=prior_owner,
    )
    authority = _Authority()
    monkeypatch.setattr(
        identity_route,
        "_classify_identity_process_owner",
        lambda owner: "dead" if owner == prior_owner else "unknown",
    )

    def recover_once() -> str:
        try:
            identity_route._recover_dead_identity_process_job(
                ActionJobLedger(root),
                dict(running),
                authority=authority,
            )
            return "won"
        except ActionJobTransitionError:
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: recover_once(), range(2)))

    assert sorted(outcomes) == ["lost", "won"]
    assert len(authority.audit_calls) == 1
    persisted = ledger.load(running["job_id"])
    assert persisted is not None
    assert persisted["state"] == "interrupted"
    assert persisted["audit_status"] == "recorded"
