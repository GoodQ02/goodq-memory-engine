"""Prediction isolation, source-bound review, and cross-film reference reuse."""
import copy
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest
import yaml

from lib import identity_matching as matching
from api.utils import identity_matching as projection
from tests.unit.test_build_face_clusters_producer_contract import controlled_faces, face_pipeline
from tests.unit.test_promote_identity_layer import _create_kg
from wsl2_audio import speaker_signature


@pytest.fixture
def reference_source(face_pipeline):
    f = face_pipeline
    scene, _, rows = f["persist"](controlled_faces(), sampled=True)
    root = f["epoch"].parent / "family"
    root.mkdir()
    (root / "family_roster.yaml").write_text(yaml.safe_dump({"identities": [
        {"id": "stable-family-id", "display_name": "Fixture Person", "face_cluster_ids": ["fc1"]}
    ]}), encoding="utf-8")
    (root / "face_clusters.json").write_text(json.dumps({"epoch_id": f["epoch"].name, "clusters": [
        {"cluster_id": "fc1", "label": "Fixture Person", "face_ids": [f"{r[0]}_{r[1]['face_index']}" for r in rows]}
    ]}), encoding="utf-8")
    _create_kg(f["epoch"] / "knowledge_graph.db", [(scene["scene_id"], [r[0] for r in rows])])
    output = f["epoch"] / "results.json"
    output.write_text("[]")
    return {"epoch_root": str(f["epoch"]), "identity_path": str(root), "results_path": str(output)}


def test_reference_loader_uses_only_named_representative_and_preserves_labels(reference_source):
    root = Path(reference_source["identity_path"])
    before = {p: p.read_bytes() for p in root.iterdir()}
    catalog = matching.load_reference_catalog({"reference_sources": [reference_source]})
    assert catalog["people"] == [{"id": "stable-family-id", "display_name": "Fixture Person"}]
    assert len(catalog["faces"]) == 1  # Labeling a group does not verify every member.
    assert catalog["faces"][0]["person_id"] == "stable-family-id"
    assert catalog["voices"] == []
    assert before == {p: p.read_bytes() for p in root.iterdir()}


def test_frozen_references_do_not_change_when_source_labels_change(reference_source, tmp_path):
    cfg = {"paths": {"db_path": str(tmp_path / "movie-two/memory.db")},
           "identity_matching": {"enabled": True, "reference_sources": [reference_source]}}
    first = matching.prepare_matching(cfg, "run-one")
    roster = Path(reference_source["identity_path"]) / "family_roster.yaml"
    roster.write_text("identities: []")
    assert matching.prepare_matching(cfg, "run-one") == first
    assert matching.prepare_matching({}, "anything") is None


def test_explicit_roster_assignment_preserves_a_different_group_nickname(reference_source):
    path = Path(reference_source["identity_path"]) / "face_clusters.json"
    groups = json.loads(path.read_text())
    groups["clusters"][0]["label"] = "Fixture nickname"
    path.write_text(json.dumps(groups))
    before = path.read_bytes()
    catalog = matching.load_reference_catalog({"reference_sources": [reference_source]})
    assert catalog["faces"][0]["person_id"] == "stable-family-id"
    assert catalog["faces"][0]["display_name"] == "Fixture Person"
    assert path.read_bytes() == before


def test_voice_references_bind_normalized_graph_label_and_require_saved_review(reference_source):
    epoch = Path(reference_source["epoch_root"])
    audio_path = epoch / "processing/controlled-source/voice.wav"
    audio_path.write_bytes(b"synthetic audio fixture")
    sig = {**speaker_signature.metadata(), "embedding_dim": 192, "embedding": [1] + [0] * 191,
           "speaker": "SPEAKER_01", "voiced_seconds": 4,
           "selected_segments": [{"speaker": "SPEAKER_01", "start": 1, "end": 5}]}
    with sqlite3.connect(epoch / "knowledge_graph.db") as conn:
        sid = conn.execute("SELECT name FROM nodes WHERE node_type='scene'").fetchone()[0]
        pattern = conn.execute("INSERT INTO nodes(node_type,name,properties) VALUES('speaker_pattern','pattern',?)",
                               (json.dumps(sig),)).lastrowid
        conn.execute("INSERT INTO edges(source_id,target_id,edge_type,properties) VALUES(1,?,'voice_pattern_match',?)",
                     (pattern, json.dumps({"scene_id": sid, "speaker_label": "Speaker_01"})))
    Path(reference_source["results_path"]).write_text(json.dumps([{"video_hash": "fixture", "video_name": "old.mp4", "scenes": [
        {"scene_id": sid, "start": 10, "end": 20, "audio": {"path": str(audio_path), "speaker_voice_signatures": [sig]}}
    ]}]))
    catalog = matching.load_reference_catalog({"reference_sources": [reference_source]})
    assert len(catalog["voices"]) == 1 and catalog["voices"][0]["person_id"] is None
    mapping = {"mapping_id": "review1", "source_node_type": "speaker_pattern", "source_node_name": "pattern",
               "status": "active", "target_person_name": "Fixture Person"}
    (epoch / "manual_identity_mappings.json").write_text(json.dumps({"mappings": [mapping]}))
    assert matching.load_reference_catalog({"reference_sources": [reference_source]})["voices"][0]["person_id"] is None
    with sqlite3.connect(epoch / "knowledge_graph.db") as conn:
        person = conn.execute("INSERT INTO nodes(node_type,name,properties) VALUES('person','Fixture Person','{}')").lastrowid
        conn.execute("INSERT INTO edges(source_id,target_id,edge_type,properties) VALUES(?,?,'identity_evidence',?)",
                     (pattern, person, json.dumps({"source": "operator_manual_override", "mapping_id": "review1"})))
    assert matching.load_reference_catalog({"reference_sources": [reference_source]})["voices"][0]["person_id"] == "stable-family-id"
    mapping["status"] = "revoked"
    (epoch / "manual_identity_mappings.json").write_text(json.dumps({"mappings": [mapping]}))
    assert matching.load_reference_catalog({"reference_sources": [reference_source]})["voices"][0]["person_id"] is None


@pytest.mark.parametrize("vector", [[0, 0], [float("nan"), 1], [True, 1], [], "bad"])
def test_invalid_vectors_never_produce_matches(vector):
    with pytest.raises(ValueError):
        matching.compare(vector, "space", [], .6, .05)


def ref(ident, vector, person=None, space="sface"):
    return {"id": ident, "space": space, "embedding": matching.unit(vector),
            "person_id": person, "display_name": person}


def test_scoring_distinguishes_identity_margin_from_multiple_examples():
    references = [ref("a", [1, 0], "person1"), ref("b", [.99, .01], "person1"),
                  ref("c", [0, 1], "person2")]
    result = matching.compare([1, 0], "sface", references, .6, .05)
    assert result["status"] == "proposed" and result["margin"] == 1
    assert [r["person_id"] for r in result["candidates"]] == ["person1", "person2"]
    assert matching.compare([1, 1], "sface", references, .6, .05)["status"] == "ambiguous"
    assert matching.compare([-1, -1], "sface", references, .6, .05)["status"] == "no_match"
    assert matching.compare([1, 0], "different-model", references, .6, .05)["status"] == "no_reference"
    assert matching.compare([1, 0, 0], "sface", references, .6, .05)["status"] == "no_reference"


@pytest.fixture
def comparison(tmp_path):
    epoch = tmp_path / "epoch-two"
    media = epoch / "processing/second"
    media.mkdir(parents=True)
    image = media / "frame.jpg"
    from PIL import Image
    Image.new("RGB", (100, 100), "red").save(image)
    wav = media / "scene.wav"
    import wave
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 16000 * 10)
    cfg = {"paths": {"db_path": str(epoch / "memory.db")}}
    face = ref("face-ref", [1, 0], "person1")
    face["media"] = matching._media(image, epoch, kind="image", bbox=[0, 0, 50, 50], timestamp=1)
    voice = ref("voice-ref", [1] + [0] * 191, space=speaker_signature.SPACE)
    voice["media"] = matching._media(wav, epoch, kind="audio", start=1, end=5, timestamp=11)
    catalog = {"people": [{"id": "person1", "display_name": "Fixture Person"}],
               "faces": [face], "voices": [voice], "sources": []}
    frozen = {"catalog": catalog, "catalog_sha256": matching.digest(catalog), "run_id": "test-run",
              "policy": {"face_similarity": .6, "voice_similarity": .25, "minimum_margin": .05}}
    signature = {**speaker_signature.metadata(), "embedding_dim": 192,
                 "speaker": "SPEAKER_01", "embedding": [1] + [0] * 191,
                 "selected_segments": [{"speaker": "SPEAKER_01", "start": 1, "end": 5}]}
    scene = {"scene_id": "scene-two", "start": 10, "end": 20,
             "audio": {"path": str(wav), "speaker_voice_signatures": [signature]},
             "keyframe": {"face_observations": [{"timestamp": 12, "source_path": str(image),
                         "faces": [{"encoding": [1, 0], "engine": "sface", "bbox": [0, 0, 50, 50]}]}]}}
    video = {"video_hash": "a" * 64, "video_path": "second.mp4", "video_name": "second.mp4", "scenes": [scene]}
    return cfg, frozen, video


def test_report_is_repeatable_separate_from_identities_and_holds_anonymous_voice(comparison):
    cfg, frozen, video = comparison
    result = matching.write_video_matches(cfg, frozen, video)
    assert matching.write_video_matches(cfg, frozen, video) == result
    report = projection.public_report(cfg, result["id"])
    assert not report["applied"] and report["status"] == "ready_for_review"
    assert report["records"][0]["candidates"][0]["person_id"] == "person1"
    assert report["records"][1]["candidates"][0]["person_id"] is None
    assert report["records"][1]["media"]["timestamp"] == 11
    assert "embedding" not in json.dumps(report) and "sha256" not in report["records"][0]["media"]
    assert not Path(cfg["paths"]["db_path"]).exists()
    assert not list(Path(cfg["paths"]["db_path"]).parent.glob("*mappings*"))
    for record in report["records"]:
        assert projection.media_file(cfg, result["id"], record["id"])[0].is_file()


def test_conflicting_simultaneous_faces_are_held(comparison):
    cfg, frozen, video = comparison
    faces = video["scenes"][0]["keyframe"]["face_observations"][0]["faces"]
    faces.append(copy.deepcopy(faces[0]))
    result = matching.write_video_matches(cfg, frozen, video)
    records = projection.public_report(cfg, result["id"])["records"]
    assert all(r["status"] == "ambiguous" for r in records if r["modality"] == "face")


def test_changed_media_or_report_refused(comparison):
    cfg, frozen, video = comparison
    result = matching.write_video_matches(cfg, frozen, video)
    report = projection.read_report(cfg, result["id"])
    image = Path(report["records"][0]["media"]["path"])
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        projection.media_file(cfg, result["id"], report["records"][0]["id"])
    path = matching.report_root(cfg) / "reports" / f"{result['id']}.json"
    report["applied"] = True
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        projection.read_report(cfg, result["id"])


def test_invalid_voice_space_is_visible_partial_not_guessed_identity(comparison):
    cfg, frozen, video = comparison
    video["scenes"][0]["audio"]["speaker_voice_signatures"][0]["embedding_space"] = "incompatible"
    result = matching.write_video_matches(cfg, frozen, video)
    report = projection.public_report(cfg, result["id"])
    assert report["status"] == "partial" and report["errors"][0]["modality"] == "voice"
    assert all(r["modality"] == "face" for r in report["records"])


def test_actual_api_returns_read_only_matches_and_bound_media(comparison, monkeypatch):
    from api.main import app
    from api.routes import identity
    cfg, frozen, video = comparison
    result = matching.write_video_matches(cfg, frozen, video)
    monkeypatch.setattr(identity, "_CFG", cfg)
    client = TestClient(app, client=("127.0.0.1", 50000))
    listing = client.get("/api/identity/matches")
    assert listing.status_code == 200 and listing.json()["reports"][0]["id"] == result["id"]
    response = client.get("/api/identity/matches/" + result["id"])
    assert response.status_code == 200
    record = response.json()["records"][0]
    assert client.get(record["media"]["url"]).status_code == 200
    assert client.get("/api/identity/matches/bad-id").status_code == 409
    assert client.post("/api/identity/matches/" + result["id"]).status_code in (403, 405)


def test_reference_loader_excludes_retired_scenes_from_ucf_ledger(reference_source):
    import hashlib
    epoch = Path(reference_source["epoch_root"])
    ucf_db = epoch / "ucf/ucf_ledger.db"
    with sqlite3.connect(ucf_db) as conn:
        vh, t_start, t_end, sid = conn.execute(
            "SELECT video_hash, t_start, t_end, source_artifact_id FROM context_frames LIMIT 1"
        ).fetchone()
        frame_ids = [r[0] for r in conn.execute("SELECT frame_id FROM context_frames WHERE source_artifact_id=?", (sid,))]
        expected_sid = hashlib.sha256(f"scene{vh}|{t_start:.3f}|{t_end:.3f}|".encode()).hexdigest()
        aliases = sorted({sid, expected_sid})
        evidence = {
            "kind": "scene_retirement",
            "version": 1,
            "video_hash": vh,
            "epoch_id": epoch.name,
            "scene_id": expected_sid,
            "aliases": aliases,
            "frame_ids": frame_ids,
            "start": float(t_start),
            "end": float(t_end),
            "vectors": [],
        }
        conn.execute(
            "INSERT INTO ucf_status_transitions(frame_ids,video_hash,epoch_id,old_status,new_status,tool_name,reason,scope,evidence,transitioned_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (json.dumps(frame_ids), vh, epoch.name, "promoted", "retired", "retire_scene", "test", f"scene_retirement:{expected_sid}", json.dumps(evidence), "2026-11-10T00:00:00Z"),
        )
    catalog = matching.load_reference_catalog({"reference_sources": [reference_source]})
    assert catalog["faces"] == []


def test_canonical_ingestion_freezes_then_records_proposals():
    # The real end-to-end witness exercises this same production caller. This
    # guard prevents a future refactor from leaving the feature as an ad hoc CLI.
    source = Path("cli/run_ingestion.py").read_text(encoding="utf-8")
    assert source.index("identity_matching_frozen = prepare_matching(cfg, run_id)") < source.index("knowledge_graph_status = asyncio.run(process_video_scenes_async())")
    assert "write_video_matches(cfg, identity_matching_frozen, video_result)" in source
    assert "if identity_matching_failed:" in source
