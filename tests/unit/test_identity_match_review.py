"""Review choices -> passive preview -> governed transaction, synthetic pixels only."""
import copy
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest
import yaml

from lib import identity_matching as matching
from api.utils import identity_appearance as appearance
from tests.unit.test_identity_matching import reference_source
from tests.unit.test_build_face_clusters_producer_contract import face_pipeline, controlled_faces
from tests.unit.test_identity_appearance_flow import _confirmed, _snapshot


@pytest.fixture
def reviewed_faces(reference_source, face_pipeline, monkeypatch):
    return _reviewed_faces(reference_source, face_pipeline, monkeypatch)


SECOND_PERSON = {"id": "second-family-id", "display_name": "Second Person"}


@pytest.fixture
def two_person_faces(reference_source, face_pipeline, monkeypatch):
    # A saved roster person without a reference image can still be the human
    # correction for a rejected pairing.
    roster = Path(reference_source["identity_path"]) / "family_roster.yaml"
    saved = yaml.safe_load(roster.read_text(encoding="utf-8"))
    saved["identities"].append(dict(SECOND_PERSON))
    roster.write_text(yaml.safe_dump(saved), encoding="utf-8")
    return _reviewed_faces(reference_source, face_pipeline, monkeypatch)


def _reviewed_faces(reference_source, face_pipeline, monkeypatch):
    from api.main import app
    from api.routes import identity
    f = face_pipeline
    catalog = matching.load_reference_catalog({"reference_sources": [reference_source]})
    frozen = {"catalog": catalog, "catalog_sha256": matching.digest(catalog), "run_id": "review-fixture",
              "policy": {"face_similarity": .6, "voice_similarity": .25, "minimum_margin": .05}}
    scenes = []
    kg = f["epoch"] / "knowledge_graph.db"
    with sqlite3.connect(kg) as conn:
        vid = conn.execute("INSERT INTO nodes(node_type,name) VALUES('video','second')").lastrowid
        for i in range(1, 4):
            # Two observations in a scene enable independent, incremental review.
            faces = controlled_faces()
            faces[0]["encoding"] = [.8, .6] + [0.0] * 126
            row, image, records = f["persist"](faces, index=i, sampled=True)
            sid = conn.execute("INSERT INTO nodes(node_type,name,properties) VALUES('scene',?,?)",
                               (row["scene_id"], json.dumps({"ucf_provenance": [r[0] for r in records]}))).lastrowid
            conn.execute("INSERT INTO edges(source_id,target_id,edge_type) VALUES(?,?,'video_contains_scene')", (vid, sid))
            # Only one of the two faces is a candidate in each sampled frame.
            row["keyframe"]["face_observations"] = [{"timestamp": row["keyframe"]["timestamp"], "source_path": str(image),
                                                    "faces": faces[:1]}]
            scenes.append(row)
    data = f["epoch"].parent / "destination-identity"
    data.mkdir()
    cfg = {"epoch_id": f["epoch"].name, "paths": {"db_path": str(f["epoch"] / "memory.db"), "knowledge_graph_db": str(kg)},
           "identity_search": {"roster_path": str(data / "family_roster.yaml"), "kg_db_path": str(kg)},
           "identity_matching": {"reference_sources": [reference_source]}}
    video = {"video_hash": f["video_hash"], "video_path": "second.mp4", "video_name": "second.mp4", "scenes": scenes}
    result = matching.write_video_matches(cfg, frozen, video)
    path = matching.report_root(cfg) / "reports" / (result["id"] + ".json")
    report = matching.read_json(path)
    # Human recognition must not depend on the automatic cutoff.
    report["records"][0]["status"] = "no_match"
    report["records"][0]["candidates"][0]["similarity"] = .45
    report["content_sha256"] = matching.digest({k: v for k, v in report.items() if k != "content_sha256"})
    path.write_text(json.dumps(report))
    monkeypatch.setattr(identity, "_CFG", cfg)
    body = {"report_id": report["id"], "report_sha256": report["content_sha256"], "accepted_ids": [report["records"][0]["id"]]}
    return TestClient(app, client=("127.0.0.1", 50000)), cfg, kg, report, body, f


def preview(client, body):
    response = client.post("/api/identity/matches/preview", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def apply(client, plan):
    return _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"], "match_review": plan["review"]})


def test_selected_below_threshold_face_only_preview_apply_undo(reviewed_faces):
    client, cfg, kg, report, body, _ = reviewed_faces
    before = _snapshot(kg)
    plan = preview(client, body)
    assert plan["summary"]["observations"] == plan["summary"]["appearances"] == 1
    assert plan["held"] == {"faces": 2, "voice_links": "all", "transcript_mentions": "all"}
    assert plan["appearances"][0]["evidence"][0]["machine_status"] == "no_match"
    assert _snapshot(kg) == before
    preparation = client.post("/api/identity/appearances/apply", json={"plan_sha256": plan["plan_sha256"], "match_review": body})
    assert preparation.status_code == 403 and _snapshot(kg) == before
    result = apply(client, plan)
    assert result.status_code == 200, result.text
    receipt = result.json()
    assert receipt["review"] == body and receipt["mutated"]
    assert apply(client, plan).json()["mutated"] is False
    saved = client.get("/api/identity/appearances/saved").json()
    assert saved["summary"]["appearances"] == 1
    assert saved["people"][0]["id"] == "stable-family-id"
    assert saved["appearances"][0]["evidence"][0]["evidence_status"] == "available"
    assert client.get(f"/api/identity/matches/{report['id']}").json()["content_sha256"] == report["content_sha256"]
    undo = _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]})
    assert undo.status_code == 200, undo.text
    assert _snapshot(kg) == before


@pytest.mark.parametrize("change", ["unknown", "duplicate", "digest", "media", "labels", "unpromoted", "scene", "video", "voice"])
def test_invalid_or_stale_choices_refuse_without_writes(reviewed_faces, change):
    client, cfg, kg, report, body, f = reviewed_faces
    plan = preview(client, body)
    if change == "unknown": body["accepted_ids"] = ["unknown"]
    elif change == "duplicate": body["accepted_ids"] *= 2
    elif change == "digest": body["report_sha256"] = "0" * 64
    elif change == "media": Path(report["records"][0]["media"]["path"]).write_bytes(b"changed fixture")
    elif change == "labels":
        path = Path(cfg["identity_matching"]["reference_sources"][0]["identity_path"]) / "family_roster.yaml"
        roster = yaml.safe_load(path.read_text(encoding="utf-8"))
        roster["identities"][0]["display_name"] = "Renamed Person"
        path.write_text(yaml.safe_dump(roster), encoding="utf-8")
    elif change == "unpromoted":
        with sqlite3.connect(f["ledger"]) as conn:
            conn.execute("UPDATE context_frames SET promotion_status='staged' WHERE source_artifact_id=?", (report["records"][0]["scene_id"],))
    elif change in {"scene", "video"}:
        with sqlite3.connect(kg) as conn:
            if change == "scene": conn.execute("UPDATE nodes SET properties='{}' WHERE name=?", (report["records"][0]["scene_id"],))
            else: conn.execute("DELETE FROM edges WHERE edge_type='video_contains_scene'")
    elif change == "voice":
        report["records"][0]["modality"] = "voice"
        report["content_sha256"] = matching.digest({k: v for k, v in report.items() if k != "content_sha256"})
        (matching.report_root(cfg) / "reports" / (report["id"] + ".json")).write_text(json.dumps(report))
        body["report_sha256"] = report["content_sha256"]
    before = _snapshot(kg)
    assert client.post("/api/identity/matches/preview", json=body).status_code == 409
    assert apply(client, {**plan, "review": body}).status_code == 409
    assert _snapshot(kg) == before and appearance.history(cfg) == []


def test_changed_selection_cannot_use_another_confirmation_token(reviewed_faces):
    client, _, kg, report, body, _ = reviewed_faces
    plan = preview(client, body)
    payload = {"plan_sha256": plan["plan_sha256"], "match_review": body}
    token = client.post("/api/identity/appearances/apply", json=payload).json()["result"]["confirmation_token"]
    changed = copy.deepcopy(payload)
    changed["match_review"]["accepted_ids"] = [report["records"][1]["id"]]
    changed["confirmation_token"] = token
    before = _snapshot(kg)
    assert client.post("/api/identity/appearances/apply", json=changed).status_code == 403
    assert _snapshot(kg) == before


def test_later_scene_review_and_undo_preserve_prior_receipt(reviewed_faces):
    client, _, kg, report, body, _ = reviewed_faces
    first = apply(client, preview(client, body)).json()
    first_state = _snapshot(kg)
    body["accepted_ids"].append(report["records"][1]["id"])
    second = apply(client, preview(client, body)).json()
    assert second["mutated"]
    assert _confirmed(client, "undo", {"receipt_id": first["id"], "receipt_sha256": first["receipt_sha256"]}).status_code == 409
    assert _confirmed(client, "undo", {"receipt_id": second["id"], "receipt_sha256": second["receipt_sha256"]}).status_code == 200
    assert _snapshot(kg) == first_state


@pytest.mark.parametrize("later_edit", [False, True])
def test_append_review_to_existing_scene_preserves_prior_evidence(reviewed_faces, later_edit):
    client, _, kg, report, body, _ = reviewed_faces
    with sqlite3.connect(kg) as conn:
        pid = conn.execute("INSERT INTO nodes(node_type,name,properties) VALUES('Person','stable-family-id',?)",
                           (json.dumps({"display_name": "Fixture Person", "existing_fact": "keep"}),)).lastrowid
        sid = conn.execute("SELECT id FROM nodes WHERE name=?", (report["records"][0]["scene_id"],)).fetchone()[0]
        conn.execute("INSERT INTO edges(source_id,target_id,edge_type,properties) VALUES(?,?,'person_appears_in_scene',?)",
                     (pid, sid, json.dumps({"confidence": "candidate", "evidence_face_ids": ["prior-evidence"], "existing_fact": "keep"})))
    before = _snapshot(kg)
    plan = preview(client, body)
    assert plan["summary"]["new_edges"] == 0 and plan["summary"]["updated_edges"] == 1
    result = apply(client, plan)
    assert result.status_code == 200, result.text
    receipt = result.json()
    with sqlite3.connect(kg) as conn:
        props = json.loads(conn.execute("SELECT properties FROM edges WHERE edge_type='person_appears_in_scene'").fetchone()[0])
        assert props["existing_fact"] == "keep" and "prior-evidence" in props["evidence_face_ids"]
        assert len(props["reviewed_matches"]) == 1
        if later_edit:
            conn.execute("UPDATE edges SET weight=.9 WHERE edge_type='person_appears_in_scene'")
    after = _snapshot(kg)
    result = _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]})
    assert result.status_code == (409 if later_edit else 200)
    assert _snapshot(kg) == (after if later_edit else before)


def three_way_body(report, body):
    result = copy.deepcopy(body)
    result.update(decisions={r["id"]: state for r, state in zip(report["records"], ("correct", "incorrect", "unsure"))},
                  completed_review=True, reuse_confirmed_faces=True)
    return result


def test_three_way_review_reuses_only_applied_correct_and_undo_revokes(reviewed_faces, tmp_path):
    client, cfg, kg, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    options = cfg["identity_matching"]
    baseline = _snapshot(kg)
    original = matching.load_reference_catalog(options)
    plan = preview(client, body)
    assert plan["summary"]["decisions"] == {"correct": 1, "incorrect": 1, "unsure": 1, "not_accepted": 0}
    assert plan["summary"]["unreviewed"] == 0 and plan["summary"]["reusable_faces"] == 1
    assert matching.load_reference_catalog(options) == original and _snapshot(kg) == baseline
    receipt = apply(client, plan).json()
    assert receipt["review"] == body
    assert client.get("/api/identity/appearances/history").json()["receipts"][0]["review"] == body
    next_cfg = {"paths": {"db_path": str(tmp_path / "next-film/memory.db")},
                "identity_matching": {**options, "enabled": True, "reviewed_face_sources": [str(kg.parent)]}}
    frozen = matching.prepare_matching(next_cfg, "next-film-run")
    faces = frozen["catalog"]["faces"]
    assert len(faces) == len(original["faces"]) + 1
    assert faces[-1]["review"]["evidence_id"] == body["accepted_ids"][0]
    assert faces[-1]["person_id"] == original["faces"][0]["person_id"]
    assert len({f["id"] for f in faces}) == len(faces)
    # The normal comparison writer and API can actually consume a reviewed
    # example. These synthetic vectors make it closer than the original sample.
    record = report["records"][0]
    video = {"video_hash": report["video_hash"], "video_path": "second.mp4", "video_name": "second.mp4", "scenes": [{
        "scene_id": record["scene_id"], "start": record["scene_start"], "end": record["scene_end"],
        "keyframe": {"face_observations": [{"timestamp": record["media"]["timestamp"], "source_path": record["media"]["path"],
            "faces": [{"bbox": record["media"]["bbox"], "encoding": [.8, .6] + [0.0] * 126, "engine": faces[-1]["space"]}]}]}}]}
    next_report = matching.write_video_matches(cfg, frozen, video)
    public = client.get(f"/api/identity/matches/{next_report['id']}").json()
    assert public["records"][0]["candidates"][0]["reference_id"] == faces[-1]["id"]
    assert client.get(next(r for r in public["references"] if r["id"] == faces[-1]["id"])["media"]["url"]).status_code == 200
    next_review = {"report_id": public["id"], "report_sha256": public["content_sha256"], "accepted_ids": [public["records"][0]["id"]]}
    preview(client, next_review)
    assert _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]}).status_code == 200
    assert client.post("/api/identity/matches/preview", json=next_review).status_code == 409
    assert matching.load_reference_catalog(options) == original
    assert matching.prepare_matching(next_cfg, "next-film-run") == frozen  # Frozen history is not rewritten.
    assert _snapshot(kg) == baseline


def test_legacy_completed_review_preserves_nonacceptance_without_inventing_negatives(reviewed_faces):
    client, cfg, kg, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    for key in body["decisions"]:
        if key not in body["accepted_ids"]:
            body["decisions"][key] = "not_accepted"
    plan = preview(client, body)
    assert plan["summary"]["decisions"] == {"correct": 1, "incorrect": 0, "unsure": 0, "not_accepted": 2}
    receipt = apply(client, plan).json()
    assert receipt["review"]["completed_review"] is True
    assert len(matching.load_reference_catalog(cfg["identity_matching"])["faces"]) == 2


def test_review_only_batch_persists_without_identity_links_or_reference_examples(reviewed_faces):
    client, cfg, kg, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    body["accepted_ids"] = []
    body["decisions"][report["records"][0]["id"]] = "incorrect"
    before = _snapshot(kg)
    catalog = matching.load_reference_catalog(cfg["identity_matching"])
    plan = preview(client, body)
    assert plan["summary"]["observations"] == plan["summary"]["new_edges"] == plan["summary"]["reusable_faces"] == 0
    result = apply(client, plan)
    assert result.status_code == 200, result.text
    assert _snapshot(kg) == before
    assert matching.load_reference_catalog(cfg["identity_matching"]) == catalog
    assert result.json()["review"]["decisions"] == body["decisions"]
    assert apply(client, plan).json()["mutated"] is False


@pytest.mark.parametrize("change", ["invalid_state", "wrong_correct_ids", "missing_completed_face", "legacy_without_completed", "voice_decision"])
def test_invalid_three_way_review_has_no_side_effects(reviewed_faces, change):
    client, cfg, kg, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    if change == "invalid_state": body["decisions"][report["records"][1]["id"]] = "maybe"
    elif change == "wrong_correct_ids": body["accepted_ids"] = []
    elif change == "missing_completed_face": body["decisions"].pop(report["records"][1]["id"])
    elif change == "legacy_without_completed":
        body["decisions"][report["records"][1]["id"]] = "not_accepted"
        body["completed_review"] = False
    elif change == "voice_decision": body["decisions"]["unknown-voice"] = "incorrect"
    before = _snapshot(kg)
    assert client.post("/api/identity/matches/preview", json=body).status_code == 409
    assert _snapshot(kg) == before and appearance.history(cfg) == []


def test_reuse_choice_is_bound_to_confirmation_token(reviewed_faces):
    client, _, kg, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    plan = preview(client, body)
    payload = {"plan_sha256": plan["plan_sha256"], "match_review": body}
    token = client.post("/api/identity/appearances/apply", json=payload).json()["result"]["confirmation_token"]
    payload["match_review"]["reuse_confirmed_faces"] = False
    payload["confirmation_token"] = token
    before = _snapshot(kg)
    assert client.post("/api/identity/appearances/apply", json=payload).status_code == 403
    assert _snapshot(kg) == before


@pytest.mark.parametrize("change", ["media", "edge", "receipt"])
def test_reusable_reference_refuses_changed_evidence(reviewed_faces, change):
    client, cfg, kg, report, body, _ = reviewed_faces
    apply(client, preview(client, three_way_body(report, body)))
    if change == "media": Path(report["records"][0]["media"]["path"]).write_bytes(b"changed")
    else:
        with sqlite3.connect(kg) as conn:
            if change == "edge": conn.execute("UPDATE edges SET properties='{}' WHERE edge_type='person_appears_in_scene'")
            else:
                raw = json.loads(conn.execute("SELECT receipt FROM identity_appearance_receipts").fetchone()[0])
                raw["review"]["decisions"][body["accepted_ids"][0]] = "incorrect"
                conn.execute("UPDATE identity_appearance_receipts SET receipt=?", (json.dumps(raw),))
    with pytest.raises(ValueError): matching.load_reference_catalog(cfg["identity_matching"])


def test_saved_correct_and_reuse_require_undo_before_changing(reviewed_faces):
    client, _, _, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    apply(client, preview(client, body))
    changed = copy.deepcopy(body)
    changed["decisions"][body["accepted_ids"][0]] = "incorrect"
    changed["accepted_ids"] = []
    assert client.post("/api/identity/matches/preview", json=changed).status_code == 409
    changed = {**body, "reuse_confirmed_faces": False}
    assert client.post("/api/identity/matches/preview", json=changed).status_code == 409


def corrected_body(report, body):
    result = three_way_body(report, body)
    result["corrections"] = {report["records"][1]["id"]: SECOND_PERSON["id"]}
    return result


def test_incorrect_face_assigned_to_chosen_person_is_reusable_and_undoable(two_person_faces, tmp_path):
    client, cfg, kg, report, body, _ = two_person_faces
    assert SECOND_PERSON in report["people"]
    body = corrected_body(report, body)
    corrected = report["records"][1]
    options = cfg["identity_matching"]
    baseline, original = _snapshot(kg), matching.load_reference_catalog(options)
    plan = preview(client, body)
    assert _snapshot(kg) == baseline
    assert plan["summary"]["decisions"] == {"correct": 1, "incorrect": 1, "unsure": 1, "not_accepted": 0}
    assert plan["summary"]["corrected"] == 1 and plan["summary"]["observations"] == 2
    assert plan["summary"]["reusable_faces"] == 2 and plan["held"]["faces"] == 1
    link = next(a for a in plan["appearances"] if a["person_id"] == SECOND_PERSON["id"])
    assert link["display_name"] == SECOND_PERSON["display_name"] and link["scene_id"] == corrected["scene_id"]
    evidence = link["evidence"][0]
    assert evidence["evidence_id"] == corrected["id"] and evidence["assignment"] == "human_corrected"
    assert evidence["rejected_person_id"] == corrected["candidates"][0]["person_id"]
    assert "similarity" not in evidence  # The score measured the rejected person.
    receipt = apply(client, plan).json()
    assert receipt["review"] == body and receipt["mutated"]
    saved = client.get("/api/identity/appearances/saved", params={"person_id": SECOND_PERSON["id"]}).json()
    assert saved["summary"]["appearances"] == 1
    assert saved["appearances"][0]["scene_id"] == corrected["scene_id"]
    # The other person's saved links never receive the rejected face.
    first = client.get("/api/identity/appearances/saved", params={"person_id": "stable-family-id"}).json()
    assert {a["scene_id"] for a in first["appearances"]} == {report["records"][0]["scene_id"]}
    next_cfg = {"paths": {"db_path": str(tmp_path / "next-film/memory.db")},
                "identity_matching": {**options, "enabled": True, "reviewed_face_sources": [str(kg.parent)]}}
    faces = matching.prepare_matching(next_cfg, "next-film-run")["catalog"]["faces"]
    assert len(faces) == len(original["faces"]) + 2
    reused = next(f for f in faces if f.get("review", {}).get("evidence_id") == corrected["id"])
    assert reused["person_id"] == SECOND_PERSON["id"] and reused["display_name"] == SECOND_PERSON["display_name"]
    undo = _confirmed(client, "undo", {"receipt_id": receipt["id"], "receipt_sha256": receipt["receipt_sha256"]})
    assert undo.status_code == 200, undo.text
    assert _snapshot(kg) == baseline and matching.load_reference_catalog(options) == original


@pytest.mark.parametrize("change", ["correct_face", "unsure_face", "same_person", "unknown_person",
                                    "unknown_face", "without_decisions"])
def test_invalid_correction_refuses_without_writes(two_person_faces, change):
    client, cfg, kg, report, body, _ = two_person_faces
    body = corrected_body(report, body)
    records = report["records"]
    if change == "correct_face": body["corrections"] = {records[0]["id"]: SECOND_PERSON["id"]}
    elif change == "unsure_face": body["corrections"] = {records[2]["id"]: SECOND_PERSON["id"]}
    elif change == "same_person": body["corrections"] = {records[1]["id"]: records[1]["candidates"][0]["person_id"]}
    elif change == "unknown_person": body["corrections"] = {records[1]["id"]: "nobody"}
    elif change == "unknown_face": body["corrections"] = {"unknown-face": SECOND_PERSON["id"]}
    else:
        body = {**body, "decisions": None, "completed_review": False, "reuse_confirmed_faces": False}
        body.pop("decisions")
    before = _snapshot(kg)
    response = client.post("/api/identity/matches/preview", json=body)
    assert response.status_code == 409, response.text
    assert _snapshot(kg) == before and appearance.history(cfg) == []


def test_saved_correction_requires_undo_before_changing(two_person_faces):
    client, _, _, report, body, _ = two_person_faces
    body = corrected_body(report, body)
    apply(client, preview(client, body))
    withdrawn = {k: v for k, v in body.items() if k != "corrections"}
    assert client.post("/api/identity/matches/preview", json=withdrawn).status_code == 409
    switched = copy.deepcopy(body)
    switched["decisions"][report["records"][1]["id"]] = "unsure"
    switched.pop("corrections")
    assert client.post("/api/identity/matches/preview", json=switched).status_code == 409
    # Repeating the identical review remains a no-op preview.
    assert preview(client, body)["review_changed"] is False


def test_reviews_without_corrections_keep_their_saved_shape(reviewed_faces):
    client, _, kg, report, body, _ = reviewed_faces
    body = three_way_body(report, body)
    plan = preview(client, body)
    assert plan["summary"]["corrected"] == 0
    receipt = apply(client, plan).json()
    assert "corrections" not in receipt["review"]
    with sqlite3.connect(kg) as conn:
        (raw,) = conn.execute("SELECT properties FROM edges WHERE edge_type='person_appears_in_scene'").fetchone()
    [match] = json.loads(raw)["reviewed_matches"]
    assert set(match) == {"report_id", "evidence_id", "reference_id", "target_face_id", "timestamp",
                          "machine_status", "similarity"}


def _edit_reference_labels(cfg, change):
    identity = Path(cfg["identity_matching"]["reference_sources"][0]["identity_path"])
    roster_path, groups_path = identity / "family_roster.yaml", identity / "face_clusters.json"
    roster = yaml.safe_load(roster_path.read_text(encoding="utf-8"))
    groups = json.loads(groups_path.read_text(encoding="utf-8"))
    if change == "alias":
        roster["identities"][0]["aliases"] = ["Fixture Nickname"]
    elif change == "group_label":
        groups["clusters"][0]["label"] = "Different nickname"  # Display text only.
    elif change == "rename":
        roster["identities"][0]["display_name"] = "Renamed Person"
    elif change == "move_group":
        roster["identities"][0]["face_cluster_ids"] = []
        roster["identities"][1]["face_cluster_ids"] = ["fc1"]
    elif change == "representative":
        groups["clusters"][0]["face_ids"] = groups["clusters"][0]["face_ids"][1:]
    roster_path.write_text(yaml.safe_dump(roster), encoding="utf-8")
    groups_path.write_text(json.dumps(groups), encoding="utf-8")


@pytest.mark.parametrize("change", ["alias", "group_label"])
def test_reference_edits_that_keep_identity_facts_still_allow_review(two_person_faces, change):
    client, cfg, kg, report, body, _ = two_person_faces
    body = corrected_body(report, body)
    _edit_reference_labels(cfg, change)
    plan = preview(client, body)
    assert plan["summary"]["corrected"] == 1
    result = apply(client, plan)
    assert result.status_code == 200, result.text


@pytest.mark.parametrize("change", ["rename", "move_group", "representative"])
def test_reference_edits_that_change_identity_facts_refuse_review(two_person_faces, change):
    client, cfg, kg, report, body, _ = two_person_faces
    _edit_reference_labels(cfg, change)
    before = _snapshot(kg)
    response = client.post("/api/identity/matches/preview", json=corrected_body(report, body))
    assert response.status_code == 409, response.text
    assert _snapshot(kg) == before and appearance.history(cfg) == []


def test_review_sources_survive_configuration_validation():
    from scripts.config_schema import IdentityMatchingConfig
    opts = IdentityMatchingConfig(reviewed_face_sources=["saved-epoch"])
    assert opts.model_dump()["reviewed_face_sources"] == ["saved-epoch"]
