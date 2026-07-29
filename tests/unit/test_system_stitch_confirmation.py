"""
R-08 seam 5: MiniAgent confirmation gate — system identity stitch routes.
TDD contract: RED on missing gate, GREEN after gate is added.

Two routes under test:
  POST /api/system/identity/stitch
  POST /api/system/identity/stitch/revoke

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


def _make_authority_patch(authorized: bool = True) -> _MockAuthority:
    return _MockAuthority(authorized=authorized)


# ── Helpers for DB seeding ────────────────────────────────────────────────────

def _seed_kg_db(tmp_path: Path) -> Path:
    """Create a minimal KG SQLite DB with one speaker_pattern node using KnowledgeGraph."""
    from lib.knowledge_graph import KnowledgeGraph
    db_path = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(db_path)) as kg:
        kg.add_node(
            node_type="speaker_pattern",
            name="SPEAKER_00",
            properties={},
            timestamp=None,
        )
    return db_path


def _seed_manual_mappings(db_path: Path, mapping_id: str = "map_test_001") -> Path:
    """Create a minimal manual_identity_mappings.json adjacent to the DB."""
    mappings_path = db_path.parent / "manual_identity_mappings.json"
    mappings_path.write_text(
        json.dumps({
            "version": 1,
            "mappings": [
                {
                    "mapping_id": mapping_id,
                    "source_node_type": "speaker_pattern",
                    "source_node_name": "SPEAKER_00",
                    "target_person_name": "Alice",
                    "status": "active",
                    "history": [],
                }
            ],
        }),
        encoding="utf-8",
    )
    return mappings_path


# ═════════════════════════════════════════════════════════════════════════════
# execute_stitch  — POST /api/system/identity/stitch
# ═════════════════════════════════════════════════════════════════════════════

def test_execute_stitch_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """Sending no confirmation_token must block the mutation and return 403."""
    db_path = _seed_kg_db(tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.system._get_kg_db_path", lambda: db_path
    )

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.system.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/system/identity/stitch",
            json={
                "source_node_name": "SPEAKER_00",
                "target_person_name": "Alice",
                "confirm": True,
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text


def test_execute_stitch_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid confirmation_token allows the mutation; record_external_execution_outcome called."""
    db_path = _seed_kg_db(tmp_path)
    _seed_manual_mappings(db_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.system._get_kg_db_path", lambda: db_path
    )

    mock_authority = _make_authority_patch(authorized=True)

    # Stub out identity_ledger functions to avoid heavy I/O
    monkeypatch.setattr(
        "api.routes.system.build_identity_ledger",
        lambda **_kwargs: {"persons": [], "patterns": []},
    )
    monkeypatch.setattr(
        "api.routes.system.write_identity_ledger_markdown",
        lambda *_args: None,
    )

    with patch(
        "api.routes.system.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/system/identity/stitch",
            json={
                "source_node_name": "SPEAKER_00",
                "target_person_name": "Alice",
                "confirm": True,
                "confirmation_token": "tok-stitch-001",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("success") is True

    assert len(mock_authority.record_calls) == 1, (
        "record_external_execution_outcome must be called exactly once on success"
    )
    assert mock_authority.record_calls[0]["status"] == "succeeded"


def test_execute_stitch_no_db_mutation_on_403(
    client, tmp_path, monkeypatch
) -> None:
    """When authority rejects, manual_identity_mappings.json must not be mutated."""
    db_path = _seed_kg_db(tmp_path)
    mappings_path = _seed_manual_mappings(db_path)
    original_content = mappings_path.read_text(encoding="utf-8")

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.system._get_kg_db_path", lambda: db_path
    )

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.system.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/system/identity/stitch",
            json={
                "source_node_name": "SPEAKER_00",
                "target_person_name": "HACKED",
                "confirm": True,
                "confirmation_token": "bad-tok",
            },
        )

    assert response.status_code == 403
    # Mappings file must be unchanged
    assert mappings_path.read_text(encoding="utf-8") == original_content


# ═════════════════════════════════════════════════════════════════════════════
# revoke_stitch  — POST /api/system/identity/stitch/revoke
# ═════════════════════════════════════════════════════════════════════════════

def test_revoke_stitch_missing_token_returns_403(
    client, tmp_path, monkeypatch
) -> None:
    """Sending no confirmation_token must block the revocation and return 403."""
    db_path = _seed_kg_db(tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.system._get_kg_db_path", lambda: db_path
    )

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.system.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/system/identity/stitch/revoke",
            json={
                "mapping_id": "map_test_001",
                # no confirmation_token
            },
        )

    assert response.status_code == 403, response.text


def test_revoke_stitch_with_token_succeeds(
    client, tmp_path, monkeypatch
) -> None:
    """Valid confirmation_token allows the revocation; record_external_execution_outcome called."""
    db_path = _seed_kg_db(tmp_path)
    _seed_manual_mappings(db_path, mapping_id="map_test_001")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.system._get_kg_db_path", lambda: db_path
    )

    mock_authority = _make_authority_patch(authorized=True)

    monkeypatch.setattr(
        "api.routes.system.build_identity_ledger",
        lambda **_kwargs: {"persons": [], "patterns": []},
    )
    monkeypatch.setattr(
        "api.routes.system.write_identity_ledger_markdown",
        lambda *_args: None,
    )

    with patch(
        "api.routes.system.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/system/identity/stitch/revoke",
            json={
                "mapping_id": "map_test_001",
                "confirmation_token": "tok-revoke-001",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("success") is True

    assert len(mock_authority.record_calls) == 1, (
        "record_external_execution_outcome must be called exactly once on success"
    )
    assert mock_authority.record_calls[0]["status"] == "succeeded"


def test_revoke_stitch_no_file_mutation_on_403(
    client, tmp_path, monkeypatch
) -> None:
    """When authority rejects, manual_identity_mappings.json must not be mutated."""
    db_path = _seed_kg_db(tmp_path)
    mappings_path = _seed_manual_mappings(db_path, mapping_id="map_test_001")
    original_content = mappings_path.read_text(encoding="utf-8")

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.system._get_kg_db_path", lambda: db_path
    )

    mock_authority = _make_authority_patch(authorized=False)

    with patch(
        "api.routes.system.MiniAgentClient", return_value=mock_authority
    ):
        response = client.post(
            "/api/system/identity/stitch/revoke",
            json={
                "mapping_id": "map_test_001",
                "confirmation_token": "bad-tok",
            },
        )

    assert response.status_code == 403
    # Mappings file must be unchanged
    assert mappings_path.read_text(encoding="utf-8") == original_content
