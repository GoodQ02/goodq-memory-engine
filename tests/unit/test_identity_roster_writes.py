from __future__ import annotations

import os
import sys
import yaml
import json
import threading
from concurrent.futures import ThreadPoolExecutor
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
    monkeypatch.setattr("api.routes.identity._CFG", {"epoch_id": "epoch_test"})

@pytest.fixture(autouse=True)
def bypass_miniagent_confirmation(monkeypatch):
    """Bypass MiniAgent confirmation gate so these tests exercise atomic-write behavior."""
    _ok_envelope = {
        "status": "ok",
        "request_id": "req-" + "a" * 16,
        "result": {"allowed": True},
        "errors": [],
    }

    recorded = []

    class _BypassAuthority:
        def authorize_action(self, **kwargs):
            return _ok_envelope, 0

        def record_external_execution_outcome(self, **kwargs):
            recorded.append(kwargs)
            return {"audit_status": "recorded", "error_codes": []}

    monkeypatch.setattr("api.routes.identity.MiniAgentClient", lambda **_kw: _BypassAuthority())
    return recorded

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


@pytest.mark.parametrize("route,filename,payload", [
    ("face-clusters/label", "face_clusters.json", {"cluster_id": "fixture", "label": "Changed", "operator_note": "Reviewed"}),
    ("speaker-clusters/confirm", "speaker_clusters.json", {"cluster_id": "fixture", "confirmed": True, "identity_label": "Changed"}),
])
def test_interrupted_json_edit_preserves_original_bytes(client, tmp_path, monkeypatch, route, filename, payload, bypass_miniagent_confirmation):
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    target = identity_dir / filename
    target.write_text(json.dumps({"epoch_id": "epoch_test", "clusters": [{"cluster_id": "fixture", "label": "Original", "confirmed": False}]}), encoding="utf-8")
    before = target.read_bytes()
    real_iterencode = json.JSONEncoder.iterencode

    def interrupted_encode(encoder, value, *args, **kwargs):
        if isinstance(value, dict) and "clusters" in value:
            yield '{"clusters": ['
            raise OSError("fixture interrupted JSON write")
        yield from real_iterencode(encoder, value, *args, **kwargs)

    monkeypatch.setattr(json.JSONEncoder, "iterencode", interrupted_encode)
    with TestClient(app, client=("127.0.0.1", 50000), raise_server_exceptions=False) as failing_client:
        response = failing_client.post("/api/identity/" + route, json=payload)
    assert response.status_code == 500
    assert target.read_bytes() == before, "failed edit must preserve the previous valid JSON"
    assert not list(identity_dir.glob("*.tmp"))
    assert not bypass_miniagent_confirmation


@pytest.mark.parametrize("same_cluster", [False, True])
def test_concurrent_roster_updates_are_one_transaction(tmp_path, monkeypatch, same_cluster):
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    roster = identity_dir / "family_roster.yaml"
    roster.write_text("identities: []\n", encoding="utf-8")
    (identity_dir / "face_clusters.json").write_text(json.dumps({
        "epoch_id": "epoch_test", "clusters": [{"cluster_id": "shared"}],
    }), encoding="utf-8")
    first_at_replace = threading.Event()
    second_finished = threading.Event()
    real_replace = os.replace

    def pause_first_writer(source, target):
        if Path(target) == roster and "fixture_first" in Path(source).read_text(encoding="utf-8") and not first_at_replace.is_set():
            first_at_replace.set()
            # The old unlocked path lets the second request finish here. A
            # serialized transaction holds it until the first commit completes.
            second_finished.wait(timeout=1)
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", pause_first_writer)

    def save(identity_id):
        with TestClient(app, client=("127.0.0.1", 50000)) as concurrent_client:
            return concurrent_client.post("/api/identity/roster/save", json={"identity": {
                "id": identity_id, "display_name": identity_id,
                "face_cluster_ids": ["shared"] if same_cluster else [],
            }})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(save, "fixture_first")
        assert first_at_replace.wait(timeout=5), "first request did not reach its commit"
        def second_save():
            try:
                return save("fixture_second")
            finally:
                second_finished.set()
        second = pool.submit(second_save)
        responses = [first.result(timeout=10), second.result(timeout=10)]

    identities = yaml.safe_load(roster.read_text(encoding="utf-8"))["identities"]
    if same_cluster:
        assert sorted(response.status_code for response in responses) == [200, 409]
        assert len(identities) == 1
    else:
        assert [response.status_code for response in responses] == [200, 200]
        assert {entry["id"] for entry in identities} == {"fixture_first", "fixture_second"}


@pytest.mark.parametrize("route,filename,payload", [
    ("face-clusters/label", "face_clusters.json", {"cluster_id": "fixture", "label": "Changed"}),
    ("speaker-clusters/confirm", "speaker_clusters.json", {"cluster_id": "fixture", "confirmed": True}),
    ("roster/save", "family_roster.yaml", {"identity": {"id": "fixture", "display_name": "Changed"}}),
    ("roster/export", "family_roster.yaml", {"identities": [{"id": "fixture", "display_name": "Changed"}]}),
])
def test_failed_identity_replace_preserves_data_and_allows_retry(
        tmp_path, monkeypatch, route, filename, payload, bypass_miniagent_confirmation):
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    target = identity_dir / filename
    target.write_text(
        'identities: [{id: fixture, display_name: Original}]\n' if filename.endswith("yaml")
        else json.dumps({"epoch_id": "epoch_test", "clusters": [{"cluster_id": "fixture", "label": "Original", "confirmed": False}]}),
        encoding="utf-8",
    )
    before = target.read_bytes()
    real_replace = os.replace

    def failed_replace(source, destination):
        if Path(destination) == target:
            raise PermissionError("fixture replacement denied")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", failed_replace)
    with TestClient(app, client=("127.0.0.1", 50000), raise_server_exceptions=False) as failing_client:
        assert failing_client.post("/api/identity/" + route, json=payload).status_code == 500
        assert target.read_bytes() == before
        assert not list(identity_dir.glob("*.tmp"))
        assert not bypass_miniagent_confirmation
        monkeypatch.setattr(os, "replace", real_replace)
        assert failing_client.post("/api/identity/" + route, json=payload).status_code == 200
    assert target.read_bytes() != before
    assert len(bypass_miniagent_confirmation) == 1
