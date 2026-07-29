"""
R-08 seam 6: MiniAgent confirmation gate — identity process execution routes.
TDD contract: RED on missing gate, GREEN after gate is added.

Two routes under test:
  POST /api/identity/rebuild-face-clusters?eps=0.4
  POST /api/identity/roster/validate

Each route must:
  - Return 403 when no confirmation_token is present (or MiniAgent rejects)
  - Succeed and call record_external_execution_outcome(status="succeeded")
    when a valid confirmation_token is supplied
  - NOT call the subprocess when authority rejects
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app
from api.routes import identity as identity_route
from api.utils.action_jobs import ActionJobLedger


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    return TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture(autouse=True)
def isolate_cfg(monkeypatch):
    """Prevent _CFG module-level state leaks."""
    monkeypatch.setattr("api.routes.identity._CFG", {})


class _MockAuthority:
    """Minimal MiniAgentClient stub used across all tests in this module."""

    def __init__(
        self,
        *,
        authorized: bool = True,
        audit_error: Exception | None = None,
    ):
        self._authorized = authorized
        self._audit_error = audit_error
        self.authorize_calls: list[Dict[str, Any]] = []
        self.record_calls: list[Dict[str, Any]] = []

    def authorize_action(self, **kwargs) -> tuple[Dict[str, Any], int]:
        self.authorize_calls.append(kwargs)
        if self._authorized:
            envelope = {
                "status": "ok",
                "request_id": "req-" + "a" * 16,
                "result": {"allowed": True},
                "errors": [],
            }
            return envelope, 0
        else:
            envelope = {
                "status": "error",
                "request_id": "req-" + "b" * 16,
                "result": {"allowed": False},
                "errors": ["confirmation_required"],
            }
            return envelope, 1

    def record_external_execution_outcome(self, **kwargs) -> Dict[str, Any]:
        self.record_calls.append(kwargs)
        if self._audit_error is not None:
            raise self._audit_error
        return {"audit_status": "recorded", "error_codes": []}


def _make_authority_patch(authorized: bool = True) -> _MockAuthority:
    return _MockAuthority(authorized=authorized)


def _make_subprocess_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a mock subprocess.CompletedProcess-like object."""
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def _valid_rebuild_manifest(epoch_id: str, eps: float) -> dict[str, Any]:
    return {
        "epoch_id": epoch_id,
        "generated_at": "2026-07-20T12:00:00+00:00",
        "eps_used": eps,
        "note": "Candidate clusters for operator review",
        "cluster_count": 0,
        "unassigned_count": 0,
        "clusters": [],
        "unassigned_face_ids": [],
    }


class _GatedRebuildProcess:
    def __init__(
        self,
        *,
        identity_dir: Path,
        epoch_id: str,
        eps: float,
        returncode: int = 0,
        communicate_error: Exception | None = None,
    ) -> None:
        self.pid = 4321
        self.stdin: io.StringIO | None = io.StringIO()
        self.returncode: int | None = None
        self._final_returncode = returncode
        self._communicate_error = communicate_error
        self._identity_dir = identity_dir
        self._manifest = _valid_rebuild_manifest(epoch_id, eps)

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        if self._communicate_error is not None:
            error, self._communicate_error = self._communicate_error, None
            raise error
        if self._final_returncode == 0:
            (self._identity_dir / "face_clusters.json").write_text(
                json.dumps(self._manifest), encoding="utf-8"
            )
        self.returncode = self._final_returncode
        return "", ""

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = self._final_returncode or 1
        return self.returncode


def _install_gated_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    process: _GatedRebuildProcess,
) -> MagicMock:
    popen = MagicMock(return_value=process)
    monkeypatch.setattr(identity_route.subprocess, "Popen", popen)
    monkeypatch.setattr(
        identity_route,
        "_probe_process_start_token",
        lambda pid: ("live", "abc123") if pid == process.pid else ("unknown", None),
    )
    return popen


def _job_root(identity_dir: Path) -> Path:
    return identity_dir / "process_jobs"


def _only_job(identity_dir: Path) -> dict[str, Any]:
    records = ActionJobLedger(_job_root(identity_dir)).list_records()
    assert len(records) == 1
    return records[0]


class _TrackingLedger(ActionJobLedger):
    transitions: list[tuple[str, str]] = []

    def transition(
        self,
        job_id: str,
        *,
        expected_states: str | set[str] | frozenset[str],
        new_state: str,
        **updates: Any,
    ) -> dict[str, Any]:
        before = self.load(job_id)
        assert before is not None
        result = super().transition(
            job_id,
            expected_states=expected_states,
            new_state=new_state,
            **updates,
        )
        type(self).transitions.append((str(before["state"]), new_state))
        return result


# ═════════════════════════════════════════════════════════════════════════════
# rebuild_face_clusters  — POST /api/identity/rebuild-face-clusters
# ═════════════════════════════════════════════════════════════════════════════

def test_rebuild_face_clusters_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """Sending no confirmation_token must block the process and return 403."""
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(tmp_path / "identity"))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch("api.routes.identity.subprocess.Popen") as mock_run:
        response = client.post(
            "/api/identity/rebuild-face-clusters",
            json={
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text
    mock_run.assert_not_called()
    assert not (tmp_path / "identity").exists()


def test_rebuild_face_clusters_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid confirmation_token allows the subprocess; record_external_execution_outcome called."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=True)
    fake_proc = _GatedRebuildProcess(
        identity_dir=identity_dir,
        epoch_id="epoch_test_001",
        eps=0.4,
    )
    mock_popen = _install_gated_rebuild(monkeypatch, fake_proc)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch(
        "api.routes.identity._epoch_id", return_value="epoch_test_001"
    ):
        response = client.post(
            "/api/identity/rebuild-face-clusters",
            json={"confirmation_token": "tok-abc123"},
        )

    assert response.status_code == 200, response.text

    assert len(mock_authority.record_calls) == 1, (
        "record_external_execution_outcome must be called exactly once on success"
    )
    assert mock_authority.record_calls[0]["status"] == "succeeded"
    mock_popen.assert_called_once()


def test_rebuild_face_clusters_no_subprocess_on_403(
    client, tmp_path, monkeypatch
) -> None:
    """When authority rejects, subprocess must NOT be called."""
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(tmp_path / "identity"))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch("api.routes.identity.subprocess.Popen") as mock_run:
        response = client.post(
            "/api/identity/rebuild-face-clusters",
            json={"confirmation_token": "bad-tok"},
        )

    assert response.status_code == 403, response.text
    mock_run.assert_not_called()
    assert not (tmp_path / "identity").exists()


# ═════════════════════════════════════════════════════════════════════════════
# validate_roster  — POST /api/identity/roster/validate
# ═════════════════════════════════════════════════════════════════════════════

def test_validate_roster_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """Sending no confirmation_token must block the process and return 403."""
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(tmp_path / "identity"))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch("api.routes.identity.subprocess.run") as mock_run:
        response = client.post(
            "/api/identity/roster/validate",
            json={
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text
    mock_run.assert_not_called()
    assert not (tmp_path / "identity").exists()


def test_validate_roster_authorization_precedes_script_validation(
    client, tmp_path, monkeypatch
) -> None:
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch(
        "api.routes.identity.Path.exists", return_value=False
    ), patch("api.routes.identity.subprocess.run") as mock_run:
        response = client.post(
            "/api/identity/roster/validate",
            json={"confirmation_token": "bad-tok"},
        )

    assert response.status_code == 403, response.text
    assert len(mock_authority.authorize_calls) == 1
    mock_run.assert_not_called()
    assert not identity_dir.exists()


def test_validate_roster_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid confirmation_token allows subprocess; record_external_execution_outcome called."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=True)
    fake_proc = _make_subprocess_result(
        returncode=0,
        stdout=" ✓ roster valid\n",
        stderr="",
    )

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch(
        "api.routes.identity.subprocess.run", return_value=fake_proc
    ) as mock_run:
        response = client.post(
            "/api/identity/roster/validate",
            json={"confirmation_token": "tok-xyz789"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True

    assert len(mock_authority.record_calls) == 1, (
        "record_external_execution_outcome must be called exactly once on success"
    )
    assert mock_authority.record_calls[0]["status"] == "succeeded"


def test_validate_roster_no_subprocess_on_403(
    client, tmp_path, monkeypatch
) -> None:
    """When authority rejects, subprocess must NOT be called."""
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(tmp_path / "identity"))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ), patch("api.routes.identity.subprocess.run") as mock_run:
        response = client.post(
            "/api/identity/roster/validate",
            json={"confirmation_token": "bad-tok"},
        )

    assert response.status_code == 403, response.text
    mock_run.assert_not_called()
    assert not (tmp_path / "identity").exists()


@pytest.mark.parametrize(
    ("route", "payload", "operation", "scope", "epoch_id"),
    [
        (
            "/api/identity/rebuild-face-clusters",
            {"eps": 0.35, "confirmation_token": "tok-rebuild-success"},
            "identity.rebuild_face_clusters",
            {"epoch_id": "epoch_test_001", "eps": 0.35},
            "epoch_test_001",
        ),
        (
            "/api/identity/roster/validate",
            {"confirmation_token": "tok-validate-success"},
            "identity.validate_roster",
            {},
            None,
        ),
    ],
)
def test_authorized_identity_process_persists_exact_scope_owner_and_lifecycle(
    client,
    tmp_path,
    monkeypatch,
    route: str,
    payload: dict[str, Any],
    operation: str,
    scope: dict[str, Any],
    epoch_id: str | None,
) -> None:
    identity_dir = tmp_path / operation.replace(".", "_")
    identity_dir.mkdir(parents=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    authority = _make_authority_patch(authorized=True)
    fake_proc = _make_subprocess_result(
        returncode=0,
        stdout=" ✓ roster valid\n" if operation.endswith("validate_roster") else "done",
    )
    _TrackingLedger.transitions = []
    monkeypatch.setattr(identity_route, "ActionJobLedger", _TrackingLedger, raising=False)
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    if epoch_id is not None:
        monkeypatch.setattr(identity_route, "_epoch_id", lambda: epoch_id)
        _install_gated_rebuild(
            monkeypatch,
            _GatedRebuildProcess(
                identity_dir=identity_dir,
                epoch_id=epoch_id,
                eps=float(scope["eps"]),
            ),
        )
    else:
        monkeypatch.setattr(identity_route.subprocess, "run", lambda *_a, **_kw: fake_proc)

    response = client.post(route, json=payload)

    assert response.status_code == 200, response.text
    response_body = response.json()
    assert "job" in response_body
    job_projection = response_body["job"]
    assert set(job_projection) == {
        "job_id",
        "operation",
        "scope",
        "state",
        "created_at_utc",
        "updated_at_utc",
        "outcome",
        "audit_status",
    }
    assert job_projection["operation"] == operation
    assert job_projection["scope"] == scope
    assert job_projection["state"] == "succeeded"
    persisted = _only_job(identity_dir)
    assert persisted["owner_instance"] == identity_route._IDENTITY_PROCESS_OWNER_INSTANCE
    assert persisted["scope"] == scope
    assert persisted["token_fingerprint"] == hashlib.sha256(
        payload["confirmation_token"].encode("utf-8")
    ).hexdigest()
    assert persisted["authorization_request_id"] == "req-" + "a" * 16
    assert payload["confirmation_token"] not in json.dumps(persisted)
    assert _TrackingLedger.transitions == [
        ("pending_confirmation", "authorizing"),
        ("authorizing", "queued"),
        ("queued", "running"),
        ("running", "succeeded"),
    ]
    assert authority.record_calls[0]["arguments"] == (
        {"eps": 0.35} if operation == "identity.rebuild_face_clusters" else {}
    )


@pytest.mark.parametrize(
    ("route", "operation", "failure", "expected_status", "expected_detail"),
    [
        (
            "/api/identity/rebuild-face-clusters",
            "identity.rebuild_face_clusters",
            subprocess.TimeoutExpired(cmd="build", timeout=120),
            500,
            "face_cluster_rebuild_failed",
        ),
        (
            "/api/identity/roster/validate",
            "identity.validate_roster",
            OSError("sensitive path C:/private/roster"),
            500,
            "roster_validation_failed",
        ),
    ],
)
def test_identity_process_exception_is_terminal_and_opaque(
    client,
    tmp_path,
    monkeypatch,
    route: str,
    operation: str,
    failure: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    identity_dir = tmp_path / operation.replace(".", "_")
    identity_dir.mkdir(parents=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch_test")
    authority = _make_authority_patch(authorized=True)
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    if operation == "identity.rebuild_face_clusters":
        _install_gated_rebuild(
            monkeypatch,
            _GatedRebuildProcess(
                identity_dir=identity_dir,
                epoch_id="epoch_test",
                eps=0.4,
                communicate_error=failure,
            ),
        )
    else:
        monkeypatch.setattr(identity_route.subprocess, "run", MagicMock(side_effect=failure))

    response = client.post(route, json={"confirmation_token": "tok-failure"})

    assert response.status_code == expected_status, response.text
    assert response.json() == {"detail": expected_detail}
    assert "sensitive" not in response.text
    assert "C:/private" not in response.text
    persisted = _only_job(identity_dir)
    assert persisted["state"] == "failed"
    assert persisted["outcome"]["code"] == expected_detail
    assert persisted["audit_status"] == "recorded"
    assert authority.record_calls[0]["status"] == "failed"


@pytest.mark.parametrize(
    ("route", "operation", "returncode", "expected_http", "expected_ok", "error_code"),
    [
        (
            "/api/identity/rebuild-face-clusters",
            "identity.rebuild_face_clusters",
            7,
            500,
            None,
            "face_cluster_rebuild_failed",
        ),
        (
            "/api/identity/roster/validate",
            "identity.validate_roster",
            2,
            200,
            False,
            "roster_validation_failed",
        ),
    ],
)
def test_nonzero_identity_process_result_is_terminal_with_existing_http_contract(
    client,
    tmp_path,
    monkeypatch,
    route: str,
    operation: str,
    returncode: int,
    expected_http: int,
    expected_ok: bool | None,
    error_code: str,
) -> None:
    identity_dir = tmp_path / operation.replace(".", "_")
    identity_dir.mkdir(parents=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch_test")
    authority = _make_authority_patch(authorized=True)
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    fake_proc = _make_subprocess_result(
        returncode=returncode,
        stdout="SENSITIVE_STDOUT",
        stderr="SENSITIVE_STDERR C:/private/path",
    )
    if operation == "identity.rebuild_face_clusters":
        _install_gated_rebuild(
            monkeypatch,
            _GatedRebuildProcess(
                identity_dir=identity_dir,
                epoch_id="epoch_test",
                eps=0.4,
                returncode=returncode,
            ),
        )
    else:
        monkeypatch.setattr(identity_route.subprocess, "run", lambda *_a, **_kw: fake_proc)

    response = client.post(route, json={"confirmation_token": "tok-nonzero"})

    assert response.status_code == expected_http, response.text
    if expected_ok is not None:
        assert response.json()["ok"] is expected_ok
        assert "job" in response.json()
    assert "SENSITIVE" not in response.text
    assert "C:/private" not in response.text
    persisted = _only_job(identity_dir)
    assert persisted["state"] == "failed"
    assert persisted["outcome"]["code"] == error_code
    assert persisted["audit_status"] == "recorded"
    assert authority.record_calls[0]["status"] == "failed"


def test_audit_failure_is_visible_but_does_not_leave_success_running(
    client, tmp_path, monkeypatch
) -> None:
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch_test")
    authority = _MockAuthority(
        authorized=True,
        audit_error=RuntimeError("sensitive audit backend detail"),
    )
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    _install_gated_rebuild(
        monkeypatch,
        _GatedRebuildProcess(
            identity_dir=identity_dir,
            epoch_id="epoch_test",
            eps=0.4,
        ),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"confirmation_token": "tok-audit-failure"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["job"]["state"] == "succeeded"
    assert response.json()["job"]["audit_status"] == "failed"
    assert "sensitive" not in response.text
    persisted = _only_job(identity_dir)
    assert persisted["state"] == "succeeded"
    assert persisted["audit_status"] == "failed"
