"""
R-08 seam 4: MiniAgent confirmation gate — identity curated mutation routes.
TDD contract: RED on missing gate, GREEN after gate is added.

Four routes under test:
  POST /api/identity/face-clusters/label
  POST /api/identity/speaker-clusters/confirm
  POST /api/identity/roster/save
  POST /api/identity/roster/export

Each route must:
  - Return 403 when no confirmation_token is present (or MiniAgent rejects)
  - Succeed and call record_external_execution_outcome(status="succeeded")
    when a valid confirmation_token is supplied
"""
from __future__ import annotations

import json
import os
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

    def __init__(self, *, authorized: bool = True):
        self._authorized = authorized
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
        return {"audit_status": "recorded", "error_codes": []}


# ── Helper: patch MiniAgentClient in the identity module ─────────────────────

def _make_authority_patch(authorized: bool = True) -> _MockAuthority:
    return _MockAuthority(authorized=authorized)


# ═════════════════════════════════════════════════════════════════════════════
# label_face_cluster
# ═════════════════════════════════════════════════════════════════════════════

def test_label_face_cluster_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """Sending no confirmation_token must block the mutation and return 403."""
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/face-clusters/label",
            json={
                "cluster_id": "fc_001",
                "label": "Joe",
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text


def test_label_face_cluster_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid confirmation_token allows the mutation; record_external_execution_outcome called."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    # Seed data file
    face_file = identity_dir / "face_clusters.json"
    face_file.write_text(
        json.dumps({"clusters": [{"cluster_id": "fc_001", "label": ""}]})
    )

    mock_authority = _make_authority_patch(authorized=True)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/face-clusters/label",
            json={
                "cluster_id": "fc_001",
                "label": "Joe",
                "confirmation_token": "tok-abc123",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True

    assert len(mock_authority.record_calls) == 1, (
        "record_external_execution_outcome must be called exactly once on success"
    )
    assert mock_authority.record_calls[0]["status"] == "succeeded"


def test_label_face_cluster_no_file_mutation_on_403(
    client, tmp_path, monkeypatch
) -> None:
    """When authority rejects, face_clusters.json must not be mutated."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    face_file = identity_dir / "face_clusters.json"
    original_content = json.dumps({"clusters": [{"cluster_id": "fc_001", "label": "original"}]})
    face_file.write_text(original_content)

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/face-clusters/label",
            json={"cluster_id": "fc_001", "label": "hacked", "confirmation_token": "bad"},
        )

    assert response.status_code == 403

    # File must be unchanged
    assert face_file.read_text() == original_content


# ═════════════════════════════════════════════════════════════════════════════
# confirm_speaker_cluster
# ═════════════════════════════════════════════════════════════════════════════

def test_confirm_speaker_cluster_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """No confirmation_token → 403, no file mutation."""
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/speaker-clusters/confirm",
            json={
                "cluster_id": "sc_001",
                "confirmed": True,
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text


def test_confirm_speaker_cluster_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid token allows mutation; record called with status=succeeded."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    speaker_file = identity_dir / "speaker_clusters.json"
    speaker_file.write_text(
        json.dumps({"clusters": [{"cluster_id": "sc_001", "confirmed": False}]})
    )

    mock_authority = _make_authority_patch(authorized=True)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/speaker-clusters/confirm",
            json={
                "cluster_id": "sc_001",
                "confirmed": True,
                "confirmation_token": "tok-xyz789",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True

    assert len(mock_authority.record_calls) == 1
    assert mock_authority.record_calls[0]["status"] == "succeeded"


def test_confirm_speaker_cluster_no_file_mutation_on_403(
    client, tmp_path, monkeypatch
) -> None:
    """Authority rejects → speaker_clusters.json unchanged."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    speaker_file = identity_dir / "speaker_clusters.json"
    original = json.dumps({"clusters": [{"cluster_id": "sc_001", "confirmed": False}]})
    speaker_file.write_text(original)

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/speaker-clusters/confirm",
            json={"cluster_id": "sc_001", "confirmed": True, "confirmation_token": "bad"},
        )

    assert response.status_code == 403
    assert speaker_file.read_text() == original


# ═════════════════════════════════════════════════════════════════════════════
# save_roster_identity
# ═════════════════════════════════════════════════════════════════════════════

def test_save_roster_identity_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """No confirmation_token → 403, file not created."""
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/roster/save",
            json={
                "identity": {"id": "p1", "name": "Alice"},
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text
    assert not (identity_dir / "family_roster.yaml").exists()


def test_save_roster_identity_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid token → identity saved, record called with status=succeeded."""
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=True)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/roster/save",
            json={
                "identity": {"id": "p1", "name": "Alice"},
                "confirmation_token": "tok-roster-save",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True

    assert len(mock_authority.record_calls) == 1
    assert mock_authority.record_calls[0]["status"] == "succeeded"


# ═════════════════════════════════════════════════════════════════════════════
# export_roster
# ═════════════════════════════════════════════════════════════════════════════

def test_export_roster_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """No confirmation_token → 403, file not created."""
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/roster/export",
            json={
                "identities": [{"id": "p1", "name": "Alice"}],
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text
    assert not (identity_dir / "family_roster.yaml").exists()


def test_export_roster_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid token → roster exported, record called with status=succeeded."""
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _make_authority_patch(authorized=True)

    with patch(
        "api.routes.identity.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/identity/roster/export",
            json={
                "identities": [
                    {"id": "p1", "name": "Alice"},
                    {"id": "p2", "name": "Bob"},
                ],
                "confirmation_token": "tok-roster-export",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True
    assert body.get("count") == 2

    assert len(mock_authority.record_calls) == 1
    assert mock_authority.record_calls[0]["status"] == "succeeded"
