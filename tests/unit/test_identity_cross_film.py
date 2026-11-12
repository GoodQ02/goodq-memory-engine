"""Production-caller verification for active-epoch roster quick-add, visual grouping, and cross-film face discovery."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest
import yaml

from lib import identity_matching as matching
from tests.unit.test_build_face_clusters_producer_contract import controlled_faces, face_pipeline
from tests.unit.test_identity_appearance_flow import _confirmed, _snapshot
from tests.unit.test_identity_matching import reference_source
from tests.unit.test_promote_identity_layer import _create_kg


def _make_movie_epoch(tmp_path: Path, epoch_name: str, video_name: str, scene_vectors: list[list[float]]) -> dict:
    """Create a realistic promoted movie epoch using the production visual UCF writer."""
    from cli.run_ingestion import _log_visual_to_ucf_ledger
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch = tmp_path / "epochs" / epoch_name
    frames = epoch / "processing" / video_name / "video" / "frames"
    frames.mkdir(parents=True)
    (epoch / "ucf").mkdir()
    ledger_path = epoch / "ucf" / "ucf_ledger.db"
    video_hash = hashlib.sha256(f"{epoch_name}:{video_name}".encode("utf-8")).hexdigest()
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.register_media(video_hash, video_name, 60, 25, 128, 100)
    ledger.close()

    config = tmp_path / f"{epoch_name}_cfg.json"
    config.write_text(json.dumps({"paths": {"db_dir": str(epoch)}}), encoding="utf-8")
    manifest = {"epoch_id": epoch.name, "video_hash": video_hash, "scenes": []}
    manifest_path = frames.parent / "scene_manifest.json"
    kg_path = epoch / "knowledge_graph.db"

    scene_rows = []
    provenance_pairs = []
    for index, vec in enumerate(scene_vectors, start=1):
        start = index * 10.0
        duration = 8.0
        sid = hashlib.sha256(f"{video_hash}|{start:.3f}".encode("utf-8")).hexdigest()
        image = frames / f"scene_{index:04d}.jpg"
        pixels = np.zeros((100, 128, 3), dtype=np.uint8)
        pixels[:, :64] = (30 * index % 255, 120, 200)
        Image.fromarray(pixels).save(image)

        faces = controlled_faces()[:1]
        faces[0]["encoding"] = list(vec)
        row = {
            "scene_id": sid,
            "start": start,
            "end": start + duration,
            "duration": duration,
            "keyframe": {
                "path": str(image),
                "timestamp": start + duration / 2,
                "face_observations": [
                    {"timestamp": start + duration / 2, "source_path": str(image), "faces": faces}
                ],
            },
        }
        manifest["scenes"].append({
            "scene_id": sid,
            "start": start,
            "end": start + duration,
            "duration": duration,
            "keyframe": {"path": str(image), "timestamp": start + duration / 2},
        })
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        item = {
            "path": str(image),
            "faces": faces,
            "faces_meta": {"engine": "opencv-yunet-sface"},
            "_face_observation_index": 0,
            "source_path": str(image),
            "timestamp": start + duration / 2,
        }
        _log_visual_to_ucf_ledger(config, video_hash, sid, row, frames, item, strict=True)
        with closing(sqlite3.connect(ledger_path)) as db, db:
            fids = [
                r[0]
                for r in db.execute(
                    "SELECT frame_id FROM context_frames WHERE worker_name='face_embed' AND source_artifact_id=? ORDER BY frame_id",
                    (sid,),
                ).fetchall()
            ]
            db.execute(
                "UPDATE context_frames SET promotion_status='promoted' WHERE source_artifact_id=?",
                (sid,),
            )
        scene_rows.append(row)
        provenance_pairs.append((sid, fids))

    _create_kg(kg_path, provenance_pairs)
    with closing(sqlite3.connect(kg_path)) as conn, conn:
        vid = conn.execute(
            "INSERT INTO nodes(node_type,name,properties) VALUES('video',?,?)",
            (Path(video_name).stem, json.dumps({"video_name": video_name})),
        ).lastrowid
        for s_row in scene_rows:
            conn.execute(
                "UPDATE nodes SET properties=? WHERE node_type='scene' AND name=?",
                (
                    json.dumps({
                        "start_time": s_row["start"],
                        "end_time": s_row["end"],
                        "ucf_provenance": dict(provenance_pairs)[s_row["scene_id"]],
                    }),
                    s_row["scene_id"],
                ),
            )
            sid_pk = conn.execute(
                "SELECT id FROM nodes WHERE node_type='scene' AND name=?",
                (s_row["scene_id"],),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO edges(source_id,target_id,edge_type) VALUES(?,?,'video_contains_scene')",
                (vid, sid_pk),
            )
    results_path = epoch / "results.json"
    results_path.write_text("[]", encoding="utf-8")
    return {
        "epoch": epoch,
        "kg": kg_path,
        "ledger": ledger_path,
        "video_hash": video_hash,
        "video_name": video_name,
        "scenes": scene_rows,
        "provenance": provenance_pairs,
        "results_path": results_path,
    }


@pytest.fixture
def two_movie_workbench(reference_source, face_pipeline, tmp_path, monkeypatch):
    """Movie 1 = reference_source; Movie 2 = active epoch with recurring & novel faces."""
    from api.main import app
    from api.routes import identity

    # Distinct vectors in 128-d space:
    # - vec_new_person: Uncle Frank (appears twice in Movie 2 AND had 1 unlabeled cameo in Movie 1!)
    # - vec_other: unrelated bystander in Movie 2
    vec_new_person = [0.0, 1.0] + [0.0] * 126
    vec_other = [0.0, 0.0, 1.0] + [0.0] * 125

    # Add an unlabeled cameo of Uncle Frank into Movie 1 (reference_source) so cross-film scan spots him!
    m1_faces = controlled_faces()[:1]
    m1_faces[0]["encoding"] = list(vec_new_person)
    cameo_scene, _, cameo_rows = face_pipeline["persist"](m1_faces, index=5, sampled=True)
    with closing(sqlite3.connect(face_pipeline["epoch"] / "knowledge_graph.db")) as conn, conn:
        conn.execute(
            "INSERT INTO nodes(node_type,name,properties) VALUES('scene',?,?)",
            (
                cameo_scene["scene_id"],
                json.dumps({
                    "start_time": cameo_scene["start"],
                    "end_time": cameo_scene["end"],
                    "ucf_provenance": [r[0] for r in cameo_rows],
                }),
            ),
        )

    movie2 = _make_movie_epoch(
        tmp_path,
        "epoch-movie-02",
        "02. 1988 Reunion.mp4",
        [vec_new_person, vec_new_person, vec_other],
    )
    active_ident_dir = tmp_path / "movie2-identity"
    active_ident_dir.mkdir()

    cfg = {
        "epoch_id": movie2["epoch"].name,
        "paths": {
            "db_path": str(movie2["epoch"] / "memory.db"),
            "knowledge_graph_db": str(movie2["kg"]),
            "identity_data_dir": str(active_ident_dir),
        },
        "identity_search": {
            "roster_path": str(active_ident_dir / "family_roster.yaml"),
            "kg_db_path": str(movie2["kg"]),
        },
        "identity_matching": {
            "enabled": True,
            "reference_sources": [reference_source],
        },
    }
    frozen = matching.prepare_matching(cfg, "movie2-ingest")
    video_payload = {
        "video_hash": movie2["video_hash"],
        "video_path": movie2["video_name"],
        "video_name": movie2["video_name"],
        "scenes": movie2["scenes"],
    }
    written = matching.write_video_matches(cfg, frozen, video_payload)
    monkeypatch.setattr(identity, "_CFG", cfg)
    client = TestClient(app, client=("127.0.0.1", 50000))
    return {
        "client": client,
        "cfg": cfg,
        "movie1": face_pipeline,
        "movie2": movie2,
        "active_ident_dir": active_ident_dir,
        "report_id": written["id"],
        "cameo_scene": cameo_scene,
        "cameo_frame_ids": [r[0] for r in cameo_rows],
        "cameo_detection_id": f"{cameo_rows[0][0]}_{cameo_rows[0][1]['face_index']}",
    }


def test_inline_new_roster_person_assigns_in_match_review_and_carries_forward_to_next_film(
    two_movie_workbench, tmp_path
):
    client = two_movie_workbench["client"]
    cfg = two_movie_workbench["cfg"]
    report_id = two_movie_workbench["report_id"]
    movie2 = two_movie_workbench["movie2"]

    initial_report = client.get(f"/api/identity/matches/{report_id}").json()
    assert [p["id"] for p in initial_report["people"]] == ["stable-family-id"]

    # Create a brand-new person inline via the governed /api/identity/roster/save endpoint.
    new_identity = {
        "id": "uncle_frank",
        "display_name": "Uncle Frank",
        "aliases": [],
        "face_cluster_ids": [],
        "speaker_cluster_ids": [],
        "name_mention_keys": ["Uncle Frank"],
        "role": "Uncle",
        "notes": "Added inline from Match Review.",
        "confirmed": False,
    }
    prep = client.post("/api/identity/roster/save", json={"identity": new_identity})
    assert prep.status_code == 403
    token = prep.json()["result"]["confirmation_token"]
    saved_resp = client.post(
        "/api/identity/roster/save",
        json={"identity": new_identity, "confirmation_token": token},
    )
    assert saved_resp.status_code == 200, saved_resp.text

    # Public match report immediately includes Uncle Frank without mutating frozen content_sha256!
    refreshed_report = client.get(f"/api/identity/matches/{report_id}").json()
    assert refreshed_report["content_sha256"] == initial_report["content_sha256"]
    assert {p["id"]: p["display_name"] for p in refreshed_report["people"]} == {
        "stable-family-id": "Fixture Person",
        "uncle_frank": "Uncle Frank",
    }

    # Reassign the two Uncle Frank observations in Movie 2 via Match Review preview + apply.
    rec_ids = [r["id"] for r in refreshed_report["records"]]
    review_body = {
        "report_id": report_id,
        "report_sha256": refreshed_report["content_sha256"],
        "accepted_ids": [],
        "decisions": {
            rec_ids[0]: "incorrect",
            rec_ids[1]: "incorrect",
            rec_ids[2]: "unsure",
        },
        "corrections": {
            rec_ids[0]: "uncle_frank",
            rec_ids[1]: "uncle_frank",
        },
        "completed_review": True,
        "reuse_confirmed_faces": True,
    }
    prev_resp = client.post("/api/identity/matches/preview", json=review_body)
    assert prev_resp.status_code == 200, prev_resp.text
    plan = prev_resp.json()
    assert plan["summary"]["corrected"] == 2
    assert plan["summary"]["reusable_faces"] == 2

    applied_resp = _confirmed(
        client,
        "apply",
        {"plan_sha256": plan["plan_sha256"], "match_review": plan["review"]},
    )
    assert applied_resp.status_code == 200, applied_resp.text

    # Verify Movie 3 / next-film ingestion carries Uncle Frank + his 2 confirmed faces forward!
    # Works BOTH via reviewed_face_sources AND when Movie 2 (with no face_clusters.json!) is in reference_sources.
    movie2_ref_source = {
        "epoch_root": str(movie2["epoch"]),
        "identity_path": str(two_movie_workbench["active_ident_dir"]),
        "results_path": str(movie2["results_path"]),
    }
    next_cfg = {
        "paths": {"db_path": str(tmp_path / "movie-03" / "memory.db")},
        "identity_matching": {
            "enabled": True,
            "reference_sources": [cfg["identity_matching"]["reference_sources"][0], movie2_ref_source],
            "reviewed_face_sources": [str(movie2["epoch"])],
        },
    }
    frozen_next = matching.prepare_matching(next_cfg, "movie-03-ingest")
    people_map = {p["id"]: p["display_name"] for p in frozen_next["catalog"]["people"]}
    assert people_map["uncle_frank"] == "Uncle Frank"
    frank_faces = [f for f in frozen_next["catalog"]["faces"] if f["person_id"] == "uncle_frank"]
    assert len(frank_faces) == 2


def test_visual_groups_endpoint_clusters_similar_faces_without_mutation(two_movie_workbench):
    client = two_movie_workbench["client"]
    report_id = two_movie_workbench["report_id"]
    kg = two_movie_workbench["movie2"]["kg"]
    before = _snapshot(kg)

    resp = client.get(f"/api/identity/matches/{report_id}/visual-groups?min_similarity=0.58")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["multi_face_group_count"] == 1
    assert payload["singleton_count"] == 1
    assert payload["groups"][0]["member_count"] == 2
    assert payload["groups"][1]["member_count"] == 1
    assert _snapshot(kg) == before


def test_cross_film_scan_and_media_spot_missed_cameos_and_respect_retirement(two_movie_workbench):
    client = two_movie_workbench["client"]
    report_id = two_movie_workbench["report_id"]
    cameo_det_id = two_movie_workbench["cameo_detection_id"]
    cameo_scene = two_movie_workbench["cameo_scene"]
    cameo_frame_ids = two_movie_workbench["cameo_frame_ids"]
    movie1_epoch = two_movie_workbench["movie1"]["epoch"]

    report = client.get(f"/api/identity/matches/{report_id}").json()
    first_evidence_id = report["records"][0]["id"]

    # Scan Movie 2's first face across Movie 2 AND Movie 1:
    scan_resp = client.get(
        f"/api/identity/cross-film-scan?report_id={report_id}&evidence_id={first_evidence_id}&min_similarity=0.50"
    )
    assert scan_resp.status_code == 200, scan_resp.text
    scan = scan_resp.json()

    # Should find the 2nd matching shot in Movie 2 AND the unlabeled cameo in Movie 1!
    assert scan["summary"]["current_movie_matches"] == 1
    assert scan["current_movie"]["matches"][0]["evidence_id"] == report["records"][1]["id"]
    assert scan["summary"]["other_movies_with_matches"] == 1
    assert scan["summary"]["missed_unlabeled_in_other_movies"] == 1

    other_hit = scan["other_movies"][0]["matches"][0]
    assert other_hit["epoch_id"] == movie1_epoch.name
    assert other_hit["detection_id"] == cameo_det_id
    assert other_hit["curation_status"] == "missed_unlabeled"
    assert other_hit["missed"] is True
    assert isinstance(other_hit["bbox"], list) and len(other_hit["bbox"]) == 4

    # Verified media endpoint serves the exact keyframe for configured epochs and rejects unconfigured epochs.
    media_ok = client.get(other_hit["media_url"])
    assert media_ok.status_code == 200
    assert media_ok.headers["content-type"] == "image/jpeg"

    media_denied = client.get("/api/identity/cross-film-media/unconfigured_private_epoch/1_0")
    assert media_denied.status_code == 404

    # Retiring the Movie 1 cameo scene in UCF immediately excludes it from both cross-film-scan and cross-film-media!
    retirement_evidence = {
        "kind": "scene_retirement",
        "version": 1,
        "video_hash": two_movie_workbench["movie1"]["video_hash"],
        "epoch_id": movie1_epoch.name,
        "scene_id": cameo_scene["scene_id"],
        "aliases": [cameo_scene["scene_id"]],
        "frame_ids": cameo_frame_ids,
        "start": cameo_scene["start"],
        "end": cameo_scene["end"],
        "vectors": [],
    }
    with closing(sqlite3.connect(movie1_epoch / "ucf" / "ucf_ledger.db")) as db, db:
        db.execute(
            "INSERT INTO ucf_status_transitions(frame_ids,video_hash,epoch_id,old_status,new_status,tool_name,reason,scope,evidence,transitioned_at) "
            "VALUES(?,?,?,'promoted','superseded','retire_scene','operator test',?,?, '2026-11-11T00:00:00Z')",
            (
                json.dumps(cameo_frame_ids),
                two_movie_workbench["movie1"]["video_hash"],
                movie1_epoch.name,
                f"scene_retirement:{cameo_scene['scene_id']}",
                json.dumps(retirement_evidence),
            ),
        )

    post_retire_scan = client.get(
        f"/api/identity/cross-film-scan?report_id={report_id}&evidence_id={first_evidence_id}&min_similarity=0.50"
    ).json()
    assert post_retire_scan["summary"]["other_movie_matches"] == 0
    assert client.get(other_hit["media_url"]).status_code == 404


def test_cross_film_scan_by_person_and_cluster_id(two_movie_workbench):
    client = two_movie_workbench["client"]
    movie2 = two_movie_workbench["movie2"]
    active_ident_dir = two_movie_workbench["active_ident_dir"]

    # Build a synthetic face_clusters.json in the active movie's identity directory
    first_frame_id = movie2["provenance"][0][1][0]
    (active_ident_dir / "face_clusters.json").write_text(
        json.dumps({
            "epoch_id": movie2["epoch"].name,
            "clusters": [
                {
                    "cluster_id": "fc_000",
                    "label": "Uncle Frank",
                    "face_ids": [f"{first_frame_id}_0"],
                }
            ],
        }),
        encoding="utf-8",
    )
    (active_ident_dir / "family_roster.yaml").write_text(
        yaml.safe_dump({
            "identities": [
                {
                    "id": "uncle_frank",
                    "display_name": "Uncle Frank",
                    "face_cluster_ids": ["fc_000"],
                }
            ]
        }),
        encoding="utf-8",
    )

    by_cluster = client.get("/api/identity/cross-film-scan?cluster_id=fc_000&min_similarity=0.50")
    assert by_cluster.status_code == 200, by_cluster.text
    assert by_cluster.json()["summary"]["other_movies_with_matches"] == 1
    assert by_cluster.json()["summary"]["missed_unlabeled_in_other_movies"] == 1

    by_person = client.get("/api/identity/cross-film-scan?person_id=uncle_frank&min_similarity=0.50")
    assert by_person.status_code == 200, by_person.text
    assert by_person.json()["target"] == {
        "kind": "person",
        "person_id": "uncle_frank",
        "display_name": "Uncle Frank",
    }
    assert by_person.json()["summary"]["other_movies_with_matches"] == 1
    assert by_person.json()["summary"]["missed_unlabeled_in_other_movies"] == 1


def test_refresh_matches_picks_up_newly_confirmed_prior_film_faces_without_reingestion(
    two_movie_workbench, tmp_path, monkeypatch
):
    """Ingesting Movie 3 while Movie 2 is still unreviewed can refresh comparisons in <1s once Movie 2 is applied."""
    import api.routes.identity as identity_routes

    client = two_movie_workbench["client"]
    cfg2 = two_movie_workbench["cfg"]
    movie2 = two_movie_workbench["movie2"]
    report2_id = two_movie_workbench["report_id"]

    # Build Movie 3 with Uncle Frank's same face vector BEFORE Movie 2 has been reviewed/applied.
    frank_vec = [0.02, 0.99] + [0.0] * 126
    movie3 = _make_movie_epoch(tmp_path, "epoch_movie_03", "family_movie_03.mp4", [frank_vec])
    movie3_out = movie3["epoch"] / "output"
    movie3_out.mkdir(parents=True, exist_ok=True)
    video3_entry = {
        "video_hash": movie3["video_hash"],
        "video_path": str(tmp_path / movie3["video_name"]),
        "video_name": movie3["video_name"],
        "scenes": movie3["scenes"],
    }
    (movie3_out / "scene_ingest_results.json").write_text(json.dumps([video3_entry]), encoding="utf-8")
    movie3_ident = tmp_path / "movie3_identity"
    movie3_ident.mkdir(parents=True)
    cfg3 = {
        "epoch_id": movie3["epoch"].name,
        "paths": {
            "db_path": str(movie3["epoch"] / "memory.db"),
            "knowledge_graph_db": str(movie3["kg"]),
            "output_directory": str(movie3_out),
        },
        "identity_search": {
            "roster_path": str(movie3_ident / "family_roster.yaml"),
            "kg_db_path": str(movie3["kg"]),
        },
        "identity_matching": {
            "enabled": True,
            "reference_sources": cfg2["identity_matching"]["reference_sources"],
            "reviewed_face_sources": [str(movie2["epoch"])],
            "face_min_similarity": 0.60,
            "voice_min_similarity": 0.25,
            "minimum_margin": 0.05,
        },
    }
    frozen_initial = matching.prepare_matching(cfg3, "movie03_initial")
    initial_summary = matching.write_video_matches(cfg3, frozen_initial, video3_entry)
    assert initial_summary["summary"]["face"].get("proposed", 0) == 0

    # Now review & apply Uncle Frank on Movie 2!
    new_identity = {
        "id": "uncle_frank",
        "display_name": "Uncle Frank",
        "aliases": [],
        "face_cluster_ids": [],
        "speaker_cluster_ids": [],
        "name_mention_keys": [],
        "role": "Uncle",
        "notes": "",
        "confirmed": False,
    }
    t0 = client.post("/api/identity/roster/save", json={"identity": new_identity}).json()["result"]["confirmation_token"]
    assert client.post("/api/identity/roster/save", json={"identity": new_identity, "confirmation_token": t0}).status_code == 200
    rep2 = client.get(f"/api/identity/matches/{report2_id}").json()
    rec_ids = [r["id"] for r in rep2["records"]]
    plan = client.post(
        "/api/identity/matches/preview",
        json={
            "report_id": report2_id,
            "report_sha256": rep2["content_sha256"],
            "accepted_ids": [],
            "decisions": {rec_ids[0]: "incorrect", rec_ids[1]: "unsure", rec_ids[2]: "unsure"},
            "corrections": {rec_ids[0]: "uncle_frank"},
            "completed_review": True,
            "reuse_confirmed_faces": True,
        },
    ).json()
    assert _confirmed(client, "apply", {"plan_sha256": plan["plan_sha256"], "match_review": plan["review"]}).status_code == 200

    # Switch active API config to Movie 3 and call governed POST /api/identity/matches/refresh!
    monkeypatch.setattr(identity_routes, "_CFG", cfg3)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(movie3_ident))

    unconfirmed = client.post("/api/identity/matches/refresh", json={})
    assert unconfirmed.status_code == 403
    refresh_token = unconfirmed.json()["result"]["confirmation_token"]

    refreshed = client.post("/api/identity/matches/refresh", json={"confirmation_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["refreshed"] is True
    assert body["mutated"] is True
    assert body["people_count"] == 2

    new_rep = client.get(f"/api/identity/matches/{body['latest_report_id']}").json()
    assert new_rep["summary"]["face"]["proposed"] == 1
    assert new_rep["records"][0]["candidates"][0]["person_id"] == "uncle_frank"

    # Calling refresh again with no new prior-film changes is a clean non-mutating no-op.
    t2 = client.post("/api/identity/matches/refresh", json={}).json()["result"]["confirmation_token"]
    noop = client.post("/api/identity/matches/refresh", json={"confirmation_token": t2}).json()
    assert noop["refreshed"] is False
    assert noop["mutated"] is False
    assert noop["latest_report_id"] == body["latest_report_id"]


def test_roster_known_people_and_cluster_suggested_matches_populate_from_prior_films(
    two_movie_workbench, tmp_path, monkeypatch
):
    import api.routes.identity as identity_routes

    client = two_movie_workbench["client"]
    active_ident_dir = two_movie_workbench["active_ident_dir"]
    cfg2 = two_movie_workbench["cfg"]
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(active_ident_dir))

    # Before Movie 2 has a local family_roster.yaml, GET /api/identity/roster stays non-creating
    # and still populates known_people from Movie 1's reference_sources.
    roster_file = active_ident_dir / "family_roster.yaml"
    assert not roster_file.exists()
    roster_resp = client.get("/api/identity/roster")
    assert roster_resp.status_code == 200
    roster_data = roster_resp.json()
    assert roster_data["identities"] == []
    assert not roster_file.exists()
    known_by_id = {p["id"]: p for p in roster_data["known_people"]}
    assert "stable-family-id" in known_by_id
    assert known_by_id["stable-family-id"]["in_active_roster"] is False

    # Build a clean epoch containing Movie 1's saved reference face and verify
    # GET /api/identity/face-clusters attaches suggested_matches from reference_sources.
    ref_vec = list(controlled_faces()[0]["encoding"])
    movie_suggest = _make_movie_epoch(tmp_path, "epoch-movie-suggest", "03. 1989.mp4", [ref_vec])
    suggest_ident_dir = tmp_path / "suggest-identity"
    suggest_ident_dir.mkdir()
    first_fid = movie_suggest["provenance"][0][1][0]
    (suggest_ident_dir / "face_clusters.json").write_text(
        json.dumps(
            {
                "epoch_id": movie_suggest["epoch"].name,
                "clusters": [
                    {
                        "cluster_id": "fc_ref_000",
                        "label": None,
                        "face_count": 1,
                        "face_ids": [f"{first_fid}_0"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cfg_suggest = {
        "epoch_id": movie_suggest["epoch"].name,
        "paths": {
            "db_path": str(movie_suggest["epoch"] / "memory.db"),
            "knowledge_graph_db": str(movie_suggest["kg"]),
        },
        "identity_search": {
            "roster_path": str(suggest_ident_dir / "family_roster.yaml"),
            "kg_db_path": str(movie_suggest["kg"]),
        },
        "identity_matching": {
            "enabled": True,
            "reference_sources": cfg2["identity_matching"]["reference_sources"],
        },
    }
    monkeypatch.setattr(identity_routes, "_CFG", cfg_suggest)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(suggest_ident_dir))

    clusters_resp = client.get("/api/identity/face-clusters")
    assert clusters_resp.status_code == 200
    clusters = clusters_resp.json()["clusters"]
    suggested_clusters = [c for c in clusters if c.get("suggested_matches")]
    assert suggested_clusters, "Expected cluster to carry suggested_matches from Movie 1 references"
    top_match = suggested_clusters[0]["suggested_matches"][0]
    assert top_match["person_id"] == "stable-family-id"
    assert top_match["similarity"] >= 0.99
    assert top_match["above_threshold"] is True
