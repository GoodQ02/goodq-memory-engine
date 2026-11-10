"""Exercise action readiness through the production API using disposable stores."""
import json
import sqlite3

import pytest
import yaml
from fastapi.testclient import TestClient

from api.main import app
from api.routes import identity


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    epoch = tmp_path / "epochs" / "epoch_test"
    root = tmp_path / "identity"
    root.mkdir()
    (epoch / "ucf").mkdir(parents=True)
    cfg = {"epoch_id": epoch.name,
           "paths": {"db_path": str(epoch / "memory.db"), "knowledge_graph_db": str(epoch / "knowledge_graph.db")},
           "identity_search": {"roster_path": str(root / "family_roster.yaml")}}
    monkeypatch.setattr(identity, "_CFG", cfg)
    with sqlite3.connect(epoch / "ucf/ucf_ledger.db") as conn:
        conn.execute("CREATE TABLE context_frames (worker_name, promotion_status, epoch_id)")
        conn.execute("INSERT INTO context_frames VALUES ('face_embed','promoted',?)", (epoch.name,))
    with sqlite3.connect(epoch / "knowledge_graph.db") as conn:
        conn.execute("CREATE TABLE nodes (node_type)")
        conn.execute("INSERT INTO nodes VALUES ('speaker_pattern')")
    return TestClient(app, client=("127.0.0.1", 50000)), root, epoch


def test_missing_manifests_do_not_block_family_facts_preparation_or_voice_review(isolated):
    client, root, _ = isolated
    actions = client.get("/api/identity/readiness").json()["actions"]
    assert all(actions[key]["ready"] for key in ("family_facts", "face_prepare", "voice_review"))
    assert all(not actions[key]["ready"] for key in ("face_review", "speaker_review", "name_review"))
    assert list(root.iterdir()) == []  # Readiness must never manufacture prerequisites.


@pytest.mark.parametrize("payload,reason", [
    ("not json", "artifact_invalid"),
    ({"epoch_id": "other", "clusters": []}, "epoch_mismatch"),
    ({"epoch_id": "epoch_test", "clusters": [{}]}, "artifact_invalid"),
])
def test_invalid_face_artifact_blocks_only_its_actions(isolated, payload, reason):
    client, root, _ = isolated
    (root / "face_clusters.json").write_text(payload if isinstance(payload, str) else json.dumps(payload))
    actions = client.get("/api/identity/readiness").json()["actions"]
    assert actions["face_review"]["reason"] == actions["face_prepare"]["reason"] == reason
    assert actions["family_facts"]["ready"] and actions["voice_review"]["ready"]


def test_face_review_does_not_require_speaker_or_name_manifests(isolated):
    client, root, _ = isolated
    (root / "face_clusters.json").write_text(json.dumps({"epoch_id": "epoch_test", "clusters": []}))
    actions = client.get("/api/identity/readiness").json()["actions"]
    assert actions["face_review"]["ready"]
    assert not actions["speaker_review"]["ready"] and not actions["name_review"]["ready"]


def test_missing_evidence_and_invalid_roster_fail_visibly_without_store_creation(isolated):
    client, root, epoch = isolated
    (epoch / "knowledge_graph.db").unlink()
    (epoch / "ucf/ucf_ledger.db").unlink()
    (root / "family_roster.yaml").write_text("identities: broken")
    actions = client.get("/api/identity/readiness").json()["actions"]
    assert actions["family_facts"]["reason"] == "roster_invalid"
    assert actions["voice_review"]["reason"] == actions["face_prepare"]["reason"] == "store_missing"
    assert not (epoch / "knowledge_graph.db").exists()


@pytest.fixture
def authorized(monkeypatch):
    class Authority:
        def authorize_action(self, **kwargs):
            return {"request_id": "test", "status": "ok"}, 0
        def record_external_execution_outcome(self, **kwargs):
            pass
    monkeypatch.setattr(identity, "MiniAgentClient", lambda **kwargs: Authority())


def test_family_fact_save_and_export_preserve_existing_unavailable_bindings(isolated, authorized):
    client, root, _ = isolated
    person = {"id": "a", "display_name": "Alice", "face_cluster_ids": ["old_face"], "speaker_cluster_ids": ["old_voice"]}
    (root / "family_roster.yaml").write_text(yaml.safe_dump({"identities": [person]}))
    person["aliases"] = ["Al"]
    response = client.post("/api/identity/roster/save", json={"identity": person})
    assert response.status_code == 200, response.text
    assert client.get("/api/identity/roster").json()["identities"] == [person]
    response = client.post("/api/identity/roster/export", json={"identities": [person]})
    assert response.status_code == 200
    before = (root / "family_roster.yaml").read_bytes()
    response = client.post("/api/identity/roster/export", json={"identities": []})
    assert response.status_code == 409
    assert (root / "family_roster.yaml").read_bytes() == before


@pytest.mark.parametrize("field,filename", [("face_cluster_ids", "face_clusters.json"), ("speaker_cluster_ids", "speaker_clusters.json")])
@pytest.mark.parametrize("epoch", [None, "other"])
def test_assignment_cannot_bypass_missing_or_foreign_evidence(isolated, authorized, field, filename, epoch):
    client, root, _ = isolated
    if epoch:
        (root / filename).write_text(json.dumps({"epoch_id": epoch, "clusters": [{"cluster_id": "candidate"}]}))
    response = client.post("/api/identity/roster/save", json={"identity": {"id": "a", field: ["candidate"]}})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_evidence_not_ready"
    assert not (root / "family_roster.yaml").exists()


@pytest.mark.parametrize("endpoint,body", [
    ("face-clusters/label", {"cluster_id": "missing", "label": "Alice"}),
    ("speaker-clusters/confirm", {"cluster_id": "missing", "confirmed": True}),
])
def test_confirmation_alone_cannot_make_missing_evidence_ready(isolated, authorized, endpoint, body):
    client, _, _ = isolated
    response = client.post("/api/identity/"+endpoint, json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_evidence_not_ready"


def test_face_preparation_cannot_overwrite_foreign_epoch_evidence(isolated, authorized, monkeypatch):
    client, root, _ = isolated
    artifact = root / "face_clusters.json"
    artifact.write_text(json.dumps({"epoch_id": "other", "clusters": []}))
    before = artifact.read_bytes()
    monkeypatch.setattr(identity.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Preparation must not start"))
    response = client.post("/api/identity/rebuild-face-clusters", json={"eps": 0.4})
    assert response.status_code == 409
    assert artifact.read_bytes() == before
