from __future__ import annotations

import os
import sys
import yaml
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app
from api.routes.identity import _identity_data_path

@pytest.fixture
def client() -> TestClient:
    return TestClient(app, client=("127.0.0.1", 50000))

@pytest.fixture(autouse=True)
def mock_global_cfg(monkeypatch):
    """Isolate _CFG state for all tests in this module to prevent leaks from other tests."""
    monkeypatch.setattr("api.routes.identity._CFG", {})

@pytest.fixture(autouse=True)
def bypass_miniagent_confirmation(monkeypatch):
    """Bypass MiniAgent confirmation gate so these tests exercise atomic-write behavior."""
    _ok_envelope = {
        "status": "ok",
        "request_id": "req-" + "a" * 16,
        "result": {"allowed": True},
        "errors": [],
    }

    class _BypassAuthority:
        def authorize_action(self, **kwargs):
            return _ok_envelope, 0

        def record_external_execution_outcome(self, **kwargs):
            return {"audit_status": "recorded", "error_codes": []}

    monkeypatch.setattr("api.routes.identity.MiniAgentClient", lambda **_kw: _BypassAuthority())

def test_save_roster_identity_atomic(client, tmp_path, monkeypatch) -> None:
    temp_identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_dir))

    # Save a new identity
    response = client.post("/api/identity/roster/save", json={
        "identity": {
            "id": "person_1",
            "name": "Joe User",
            "aliases": ["Joe", "Jdb"]
        }
    })
    assert response.status_code == 200
    assert response.json().get("ok") is True

    # Verify the file was created and contains the saved identity
    roster_file = temp_identity_dir / "family_roster.yaml"
    assert roster_file.exists()

    import yaml
    with open(roster_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data is not None
    assert "identities" in data
    assert len(data["identities"]) == 1
    assert data["identities"][0]["id"] == "person_1"

def test_export_roster_atomic(client, tmp_path, monkeypatch) -> None:
    temp_identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_dir))

    # Export list of identities
    response = client.post("/api/identity/roster/export", json={
        "identities": [
            {"id": "person_1", "name": "Joe User"},
            {"id": "person_2", "name": "Jane User"}
        ]
    })
    assert response.status_code == 200
    assert response.json().get("ok") is True

    # Verify the file exists and has both identities
    roster_file = temp_identity_dir / "family_roster.yaml"
    assert roster_file.exists()

    import yaml
    with open(roster_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert len(data["identities"]) == 2


def test_save_roster_rejects_face_cluster_owned_by_another_identity(
    client, tmp_path, monkeypatch
) -> None:
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    roster_file = identity_dir / "family_roster.yaml"
    roster_file.write_text(
        yaml.safe_dump(
            {
                "identities": [
                    {
                        "id": "grace",
                        "display_name": "Grace",
                        "face_cluster_ids": ["face_cluster_0"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    before = roster_file.read_bytes()

    response = client.post(
        "/api/identity/roster/save",
        json={
            "identity": {
                "id": "joe",
                "display_name": "Joe",
                "face_cluster_ids": ["face_cluster_0"],
            }
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "face_cluster_already_owned",
        "cluster_ids": ["face_cluster_0"],
        "owner_ids": ["grace"],
    }
    assert roster_file.read_bytes() == before

def test_write_failure_cleanup(client, tmp_path, monkeypatch) -> None:
    temp_identity_dir = tmp_path / "identity"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_identity_dir))

    # Step 1: Write an initial roster file
    temp_identity_dir.mkdir(parents=True, exist_ok=True)
    roster_file = temp_identity_dir / "family_roster.yaml"

    import yaml
    initial_data = {
        "identities": [{"id": "person_initial", "name": "Initial"}]
    }
    with open(roster_file, "w", encoding="utf-8") as f:
        yaml.dump(initial_data, f)

    # Step 2: Monkeypatch yaml.dump to raise an error during write
    def mock_dump(*args, **kwargs):
        raise IOError("Simulated disk full or write failure")

    monkeypatch.setattr(yaml, "dump", mock_dump)

    # Step 3: Try to save, expecting a 500 error response (HTTPException, not a raw raise)
    response = client.post("/api/identity/roster/save", json={
        "identity": {"id": "person_failed", "name": "Should Fail"}
    })
    assert response.status_code == 500
    assert "roster_save_failed" in response.text

    # Step 4: Verify original roster file is completely unchanged
    with open(roster_file, encoding="utf-8") as f:
        monkeypatch.undo()  # Undo monkeypatch to read YAML safely
        data = yaml.safe_load(f)
    assert len(data["identities"]) == 1
    assert data["identities"][0]["id"] == "person_initial"

    # Step 5: Verify no .tmp files are left in the directory
    tmp_files = list(temp_identity_dir.glob("*.tmp"))
    assert len(tmp_files) == 0, f"Leaked temporary files found: {tmp_files}"

def test_identity_path_precedence(monkeypatch, tmp_path) -> None:
    # Clear env
    monkeypatch.delenv("GOODQ_IDENTITY_PATH", raising=False)
    monkeypatch.setattr("api.routes.identity._CFG", {})

    # 1. Default path check
    path = _identity_data_path()
    assert "GoodQ_Data" in str(path)

    # 2. Env override check
    temp_env_path = tmp_path / "env_identity_dir"
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(temp_env_path))
    path = _identity_data_path()
    assert path == temp_env_path

    # 3. Config override check (explicit roster_path wins over env)
    temp_cfg_roster = tmp_path / "cfg_identity_dir" / "family_roster.yaml"
    monkeypatch.setattr("api.routes.identity._CFG", {
        "identity_search": {
            "roster_path": str(temp_cfg_roster)
        }
    })
    path = _identity_data_path()
    assert path == temp_cfg_roster.parent
