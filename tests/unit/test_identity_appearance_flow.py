"""Saved observation -> governed API -> passive consumer, on synthetic media only."""
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest
import yaml

from api.utils import identity_appearance as appearance
from tests.unit.test_build_face_clusters_producer_contract import controlled_faces, face_pipeline
from tests.unit.test_promote_identity_layer import _create_kg


@pytest.fixture
def appearance_app(face_pipeline, monkeypatch):
    from api.main import app
    from api.routes import identity

    f = face_pipeline
    scenes, groups = [], [[], []]
    for i in range(2):
        scene, _, records = f["persist"](controlled_faces(), index=i, sampled=True)
        scenes.append((scene["scene_id"], [r[0] for r in records]))
        for j, (fid, payload, _) in enumerate(records):
            groups[j].append(f"{fid}_{payload['face_index']}")
    root = f["epoch"].parent.parent / "appearance-identities"
    root.mkdir()
    roster = {"identities": [
        {"id": "person-a", "display_name": "Avery (fixture)", "aliases": ["Mom"], "face_cluster_ids": ["fc-a"]},
        {"id": "person-b", "display_name": "Blair (fixture)", "aliases": ["Mom"], "face_cluster_ids": ["fc-b"], "speaker_cluster_ids": ["unavailable-voice"]},
    ]}
    (root / "family_roster.yaml").write_text(yaml.safe_dump(roster), encoding="utf-8")
    (root / "face_clusters.json").write_text(json.dumps({"epoch_id": f["epoch"].name, "clusters": [
        {"cluster_id": cid, "label": name, "face_ids": ids, "face_count": len(ids)}
        for cid, name, ids in zip(("fc-a", "fc-b"), ("Avery", "Blair"), groups)
    ]}), encoding="utf-8")
    kg = f["epoch"] / "knowledge_graph.db"
    _create_kg(kg, scenes)
    cfg = {"epoch_id": f["epoch"].name,
           "paths": {"db_path": str(f["epoch"] / "memory.db"), "knowledge_graph_db": str(kg)},
           "identity_search": {"roster_path": str(root / "family_roster.yaml"), "kg_db_path": str(kg)}}
    (root.parent / "appearance-config.json").write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(identity, "_CFG", cfg)
    return TestClient(app, client=("127.0.0.1", 50000)), cfg, kg, root


def _snapshot(kg):
    with sqlite3.connect(kg) as conn:
        return [conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in ("nodes", "edges")]


def _preview(client):
    response = client.get("/api/identity/appearances/preview")
    assert response.status_code == 200, response.text
    return response.json()


def _confirmed(client, action, payload):
    path = f"/api/identity/appearances/{action}"
    prepared = client.post(path, json=payload)
    assert prepared.status_code == 403, prepared.text
    token = prepared.json()["result"]["confirmation_token"]
    return client.post(path, json={**payload, "confirmation_token": token})


def test_preview_and_confirmation_preparation_never_write_graph(appearance_app):
    client, cfg, kg, root = appearance_app
    before = _snapshot(kg)
    files = {p.name: p.read_bytes() for p in root.iterdir()}
    plan = _preview(client)
    assert plan["summary"] == {"people": 2, "groups": 2, "appearances": 4, "scenes": 2,
                               "observations": 4, "new_nodes": 4, "new_edges": 6, "existing_edges": 0}
    assert plan["held"]["shared_aliases"] == [{"term": "mom", "people": ["Avery (fixture)", "Blair (fixture)"]}]
    assert plan["held"]["transcript_mentions"] == "all"
    assert all(e["edge_type"] in {"person_appears_in_scene", "person_has_face_cluster"} for e in plan["edges"])
    assert all(m["evidence_status"] == "available" for a in plan["appearances"] for m in a["evidence"])
    assert _preview(client)["plan_sha256"] == plan["plan_sha256"]
    response = client.post("/api/identity/appearances/apply", json={"plan_sha256": plan["plan_sha256"]})
    assert response.status_code == 403
    assert _snapshot(kg) == before
    assert {p.name: p.read_bytes() for p in root.iterdir()} == files
    assert not (kg.parent / "memory.db").exists()  # no transcript reads or implicit DB creation
    with sqlite3.connect(kg) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (appearance.TABLE,)).fetchone()


def test_apply_consumer_retry_and_scoped_undo(appearance_app):
    client, cfg, kg, root = appearance_app
    before = _snapshot(kg)
    files = {p.name: p.read_bytes() for p in root.iterdir()}
    plan = _preview(client)
    receipt_response = _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]})
    assert receipt_response.status_code == 200, receipt_response.text
    receipt = receipt_response.json()
    assert receipt["status"] == "applied" and receipt["mutated"]
    consumer = client.get("/api/identity/scene-evidence", params={"subjects": "Avery (fixture),Blair (fixture)"})
    assert consumer.status_code == 200
    assert len(consumer.json()["scene_refs"]) == 2
    assert all(p["evidence_types"] == ["appearance"] for s in consumer.json()["scene_refs"] for p in s["people"])
    applied = _snapshot(kg)
    retry = _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]})
    assert retry.json()["mutated"] is False
    assert _snapshot(kg) == applied
    assert _preview(client)["summary"]["new_edges"] == 0
    # Unrelated later work survives Undo.
    with sqlite3.connect(kg) as conn:
        conn.execute("INSERT INTO nodes (node_type,name) VALUES ('note','unrelated')")
    undo = _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]})
    assert undo.status_code == 200, undo.text
    assert undo.json()["status"] == "undone"
    after = _snapshot(kg)
    assert after[0][:-1] == before[0] and after[1] == before[1]
    assert client.get("/api/identity/scene-evidence", params={"subjects": "Avery (fixture)"}).json()["scene_refs"] == []
    assert client.get("/api/identity/appearances/history").json()["receipts"][0]["status"] == "undone"
    assert all((root / name).read_bytes() == value for name, value in files.items())


def test_saved_people_reads_applied_edges_not_pending_labels_or_mentions(appearance_app, monkeypatch):
    client, cfg, kg, root = appearance_app
    assert client.get("/api/identity/appearances/saved").json()["appearances"] == []
    plan = _preview(client)
    assert _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]}).status_code == 200
    with sqlite3.connect(kg) as conn:
        video = conn.execute("INSERT INTO nodes (node_type,name) VALUES ('video','controlled-source')").lastrowid
        scene_ids = [r[0] for r in conn.execute("SELECT id FROM nodes WHERE node_type='scene'")]
        person = conn.execute("SELECT id FROM nodes WHERE name='person-b'").fetchone()[0]
        for sid in scene_ids:
            conn.execute("INSERT INTO edges (source_id,target_id,edge_type) VALUES (?,?,'video_contains_scene')", (video, sid))
            conn.execute("INSERT INTO edges (source_id,target_id,edge_type) VALUES (?,?,'person_mentioned_in_scene')", (person, sid))
    # Saved browsing must survive incomplete new edits and must never plan them.
    (root / "family_roster.yaml").write_text("unfinished: edit", encoding="utf-8")
    (root / "face_clusters.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(appearance, "_build", lambda *_: pytest.fail("saved browsing must not preview"))
    before = _snapshot(kg)
    response = client.get("/api/identity/appearances/saved", params={"person_id": "person-a"})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["summary"] == {"people": 1, "appearances": 2, "scenes": 2}
    assert saved["people"][0]["display_name"] == "Avery (fixture)"
    assert saved["held"] == {"transcript_mentions": "all", "voice_links": "all"}
    assert {a["scene_id"] for a in saved["appearances"]} == {a["scene_id"] for a in plan["appearances"]}
    assert all(a["video_id"] == "controlled-source" and a["person_id"] == "person-a" for a in saved["appearances"])
    assert all(m["evidence_status"] == "available" for a in saved["appearances"] for m in a["evidence"])
    # An ambiguous alias is not an identity ID; no fuzzy/name-based assignment.
    assert client.get("/api/identity/appearances/saved?person_id=Mom").json()["people"] == []
    assert _snapshot(kg) == before


def test_saved_people_keeps_unavailable_evidence_and_refuses_ambiguous_source(appearance_app):
    client, cfg, kg, root = appearance_app
    plan = _preview(client)
    _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]})
    with sqlite3.connect(kg) as conn:
        sid = conn.execute("SELECT id FROM nodes WHERE node_type='scene' LIMIT 1").fetchone()[0]
        for name in ("source-one", "source-two"):
            vid = conn.execute("INSERT INTO nodes (node_type,name) VALUES ('video',?)", (name,)).lastrowid
            conn.execute("INSERT INTO edges (source_id,target_id,edge_type) VALUES (?,?,'video_contains_scene')", (vid, sid))
    for image in (kg.parent / "processing").rglob("*.jpg"):
        image.unlink()  # Generated fixture pixels only.
    before = _snapshot(kg)
    saved = client.get("/api/identity/appearances/saved").json()
    assert len(saved["appearances"]) == 4
    assert all(a["video_id"] is None for a in saved["appearances"])
    assert all(m["evidence_status"] == "unavailable" for a in saved["appearances"] for m in a["evidence"])
    assert _snapshot(kg) == before


@pytest.mark.parametrize("change", ["roster", "labels", "scene", "source"])
def test_changed_inputs_refuse_apply_without_partial_writes(appearance_app, change):
    client, cfg, kg, root = appearance_app
    plan = _preview(client)
    if change in {"roster", "labels"}:
        path = root / ("family_roster.yaml" if change == "roster" else "face_clusters.json")
        path.write_text(path.read_text() + "\n")
    elif change == "scene":
        with sqlite3.connect(kg) as conn:
            conn.execute("UPDATE nodes SET occurrence_count=7 WHERE id=1")
    else:
        image = next((kg.parent / "processing").rglob("*.jpg"))
        image.write_bytes(b"changed source")
    before = _snapshot(kg)
    response = _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]})
    assert response.status_code == 409, response.text
    assert _snapshot(kg) == before
    assert appearance.history(cfg) == []


def test_confirmation_token_cannot_apply_another_plan(appearance_app):
    client, _, kg, _ = appearance_app
    plan = _preview(client)
    before = _snapshot(kg)
    prepared = client.post("/api/identity/appearances/apply", json={"plan_sha256": plan["plan_sha256"]})
    response = client.post("/api/identity/appearances/apply", json={"plan_sha256": "b" * 64,
                           "confirmation_token": prepared.json()["result"]["confirmation_token"]})
    assert response.status_code == 403
    assert _snapshot(kg) == before


@pytest.mark.parametrize("change", ["edge_edit", "dependency"])
def test_undo_preserves_later_edits_and_dependencies(appearance_app, change):
    client, cfg, kg, _ = appearance_app
    receipt = _confirmed(client, "apply", {"plan_sha256": _preview(client)["plan_sha256"]}).json()
    with sqlite3.connect(kg) as conn:
        if change == "edge_edit":
            conn.execute("UPDATE edges SET weight=0.9 WHERE id=(SELECT MAX(id) FROM edges)")
        else:
            person = conn.execute("SELECT id FROM nodes WHERE node_type='Person' LIMIT 1").fetchone()[0]
            conn.execute("INSERT INTO edges (source_id,target_id,edge_type) VALUES (?,1,'later-evidence')", (person,))
    before = _snapshot(kg)
    response = _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]})
    assert response.status_code == 409, response.text
    assert _snapshot(kg) == before
    assert appearance.history(cfg)[0]["status"] == "applied"


def test_failed_receipt_write_rolls_back_graph(appearance_app, monkeypatch):
    client, cfg, kg, _ = appearance_app
    plan = _preview(client)
    before = _snapshot(kg)
    def fail(*args):
        raise sqlite3.OperationalError("controlled receipt failure")
    monkeypatch.setattr(appearance, "_persist", fail)
    with pytest.raises(sqlite3.OperationalError, match="controlled"):
        _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]})
    assert _snapshot(kg) == before


def test_conflicting_group_ownership_blocks_preview(appearance_app):
    client, cfg, kg, root = appearance_app
    path = root / "family_roster.yaml"
    roster = yaml.safe_load(path.read_text())
    roster["identities"][1]["face_cluster_ids"] = ["fc-a"]
    path.write_text(yaml.safe_dump(roster))
    response = client.get("/api/identity/appearances/preview")
    assert response.status_code == 409
    assert appearance.history(cfg) == []


def test_apply_and_undo_preserve_existing_person_and_appearance(appearance_app):
    client, cfg, kg, _ = appearance_app
    plan = _preview(client)
    person = next(n for n in plan["nodes"] if n["node_type"] == "Person")
    edge = next(e for e in plan["edges"] if e["source"][1] == person["name"] and e["edge_type"] == "person_appears_in_scene")
    with sqlite3.connect(kg) as conn:
        person_id = conn.execute("INSERT INTO nodes (node_type,name,properties) VALUES ('Person',?,?)",
                                 (person["name"], json.dumps(person["properties"]))).lastrowid
        target_id = conn.execute("SELECT id FROM nodes WHERE node_type='scene' AND name=?", (edge["target"][1],)).fetchone()[0]
        conn.execute("INSERT INTO edges (source_id,target_id,edge_type,weight,properties) VALUES (?,?,?,?,?)",
                     (person_id, target_id, edge["edge_type"], edge["weight"], json.dumps(edge["properties"])))
    before = _snapshot(kg)
    plan = _preview(client)
    assert plan["summary"]["existing_edges"] == 1
    assert plan["summary"]["new_nodes"] == 3
    receipt = _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"]}).json()
    response = _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]})
    assert response.status_code == 200, response.text
    assert _snapshot(kg) == before
