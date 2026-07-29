from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app
from api.routes import identity


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, client=("127.0.0.1", 50000))


def _use_temporary_identity_config(monkeypatch, roster_path: Path) -> None:
    cfg = dict(identity._CFG)
    cfg["identity_search"] = {
        **(cfg.get("identity_search") or {}),
        "roster_path": str(roster_path),
    }
    monkeypatch.setattr(identity, "_CFG", cfg)


def test_get_face_clusters_non_creating(client, tmp_path, monkeypatch) -> None:
    # Set GOODQ_IDENTITY_PATH to a temporary location
    temp_identity_path = tmp_path / "identity" / "family_roster.yaml"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_path))
    _use_temporary_identity_config(monkeypatch, temp_identity_path)

    parent_dir = temp_identity_path.parent
    assert not parent_dir.exists()

    response = client.get("/api/identity/face-clusters")
    assert response.status_code == 200

    payload = response.json()
    assert "clusters" in payload
    assert "not found" in payload.get("message", "")

    # This assertion will fail on RED run because _data_path() runs mkdir()
    assert not parent_dir.exists(), "Directory should not be created by GET /face-clusters"


def test_get_speaker_clusters_non_creating(client, tmp_path, monkeypatch) -> None:
    temp_identity_path = tmp_path / "identity" / "family_roster.yaml"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_path))
    _use_temporary_identity_config(monkeypatch, temp_identity_path)

    parent_dir = temp_identity_path.parent
    assert not parent_dir.exists()

    response = client.get("/api/identity/speaker-clusters")
    assert response.status_code == 200

    payload = response.json()
    assert "clusters" in payload
    assert "not found" in payload.get("message", "")

    # This assertion will fail on RED run because _data_path() runs mkdir()
    assert not parent_dir.exists(), "Directory should not be created by GET /speaker-clusters"


def test_get_name_mentions_non_creating(client, tmp_path, monkeypatch) -> None:
    temp_identity_path = tmp_path / "identity" / "family_roster.yaml"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_path))
    _use_temporary_identity_config(monkeypatch, temp_identity_path)

    parent_dir = temp_identity_path.parent
    assert not parent_dir.exists()

    response = client.get("/api/identity/name-mentions")
    assert response.status_code == 200

    payload = response.json()
    assert "mentions" in payload
    assert "not found" in payload.get("message", "")

    # This assertion will fail on RED run because _data_path() runs mkdir()
    assert not parent_dir.exists(), "Directory should not be created by GET /name-mentions"


def test_get_roster_non_creating(client, tmp_path, monkeypatch) -> None:
    temp_identity_path = tmp_path / "identity" / "family_roster.yaml"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_path))
    _use_temporary_identity_config(monkeypatch, temp_identity_path)

    parent_dir = temp_identity_path.parent
    assert not parent_dir.exists()

    response = client.get("/api/identity/roster")
    assert response.status_code == 200

    payload = response.json()
    assert "identities" in payload
    assert "not found" in payload.get("message", "")

    # This assertion will fail on RED run because _data_path() runs mkdir()
    assert not parent_dir.exists(), "Directory should not be created by GET /roster"


def test_get_identity_evidence_pack_non_creating(client, tmp_path, monkeypatch) -> None:
    temp_identity_path = tmp_path / "identity" / "family_roster.yaml"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_path))
    _use_temporary_identity_config(monkeypatch, temp_identity_path)

    parent_dir = temp_identity_path.parent
    assert not parent_dir.exists()

    response = client.get("/api/identity/evidence-pack", params={"subjects": "Maria"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["claim_status"] == "not_established"
    assert payload["identities"] == []
    assert not parent_dir.exists(), "Directory should not be created by GET /evidence-pack"
