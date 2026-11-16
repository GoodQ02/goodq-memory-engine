"""Regression coverage for Phase 1 Area 4 identity and cache authority repairs (IC-01..IC-05)."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
import yaml

from api.routes import system as system_module
from lib import identity_matching as matching
from lib.identity_ledger import load_manual_mappings, save_manual_mappings
from lib.knowledge_graph import KnowledgeGraph
from scripts.identity.build_face_clusters import load_face_ucf_provenance
from scripts.identity.promote_identity_layer import promote
from tests.unit.test_build_face_clusters_producer_contract import controlled_faces, face_pipeline
from tests.unit.test_hitl_stitching import create_test_db
from tests.unit.test_identity_appearance_flow import _confirmed, _snapshot
from tests.unit.test_identity_cross_film import _make_movie_epoch
from tests.unit.test_identity_match_review import apply as apply_match_plan, preview as preview_match_plan, three_way_body
from tests.unit.test_identity_matching import reference_source


REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_JS = REPO_ROOT / "ui" / "identity_workbench" / "static" / "js" / "identity.js"
MATCHES_JS = REPO_ROOT / "ui" / "identity_workbench" / "static" / "js" / "matches.js"


def _retire_scene_in_ucf(ledger_path: Path, epoch_name: str, scene_id: str) -> str:
    """Insert a canonical scene_retirement transition while leaving KG delivery pending."""
    with sqlite3.connect(ledger_path) as conn:
        row = conn.execute(
            "SELECT video_hash, t_start, t_end FROM context_frames WHERE source_artifact_id=? LIMIT 1",
            (scene_id,),
        ).fetchone()
        assert row is not None
        vh, t_start, t_end = row[0], float(row[1]), float(row[2] if row[2] is not None else row[1] + 8.0)
        frame_ids = [
            r[0]
            for r in conn.execute(
                "SELECT frame_id FROM context_frames WHERE source_artifact_id=? ORDER BY frame_id",
                (scene_id,),
            ).fetchall()
        ]
        expected_sid = hashlib.sha256(f"scene{vh}|{t_start:.3f}|{t_end:.3f}|".encode()).hexdigest()
        aliases = sorted({scene_id, expected_sid})
        evidence = {
            "kind": "scene_retirement",
            "version": 1,
            "video_hash": vh,
            "epoch_id": epoch_name,
            "scene_id": expected_sid,
            "aliases": aliases,
            "frame_ids": frame_ids,
            "start": t_start,
            "end": t_end,
            "vectors": [],
        }
        conn.execute(
            "INSERT INTO ucf_status_transitions("
            "frame_ids,video_hash,epoch_id,old_status,new_status,tool_name,reason,scope,evidence,transitioned_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                json.dumps(frame_ids),
                vh,
                epoch_name,
                "promoted",
                "retired",
                "retire_scene",
                "audit_test",
                f"scene_retirement:{expected_sid}",
                json.dumps(evidence),
                "2026-11-15T00:00:00Z",
            ),
        )
    return expected_sid


# ── IC-01: Manual mappings & stitch/revoke atomicity + history preservation ───


def test_ic01_corrupt_manual_mappings_logs_warning_without_name_error(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    mappings_file = tmp_path / "manual_identity_mappings.json"
    mappings_file.write_text("{corrupt json", encoding="utf-8")

    loaded = load_manual_mappings(db_path)
    assert loaded == {"version": 1, "mappings": []}


def test_ic01_save_manual_mappings_atomic_replace_preserves_file_on_failure(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    initial = {
        "version": 1,
        "mappings": [{"mapping_id": "map_1", "source_node_name": "spk_1", "target_person_name": "Person A", "status": "active"}],
    }
    save_manual_mappings(db_path, initial)
    mappings_file = tmp_path / "manual_identity_mappings.json"
    original_bytes = mappings_file.read_bytes()

    def _boom_replace(_src, _dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("lib.identity_ledger.os.replace", _boom_replace)
    with pytest.raises(RuntimeError):
        save_manual_mappings(db_path, {"version": 1, "mappings": []})

    assert mappings_file.read_bytes() == original_bytes
    leftover_tmps = list(tmp_path.glob(".manual_identity_mappings.*.tmp"))
    assert leftover_tmps == []


def test_ic01_execute_and_revoke_stitch_rollback_and_history_preservation(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db(db_path)
    monkeypatch.setattr(system_module, "_get_kg_db_path", lambda: db_path)

    recorded_outcomes: list[dict] = []

    class _AuditAuthority:
        def authorize_action(self, **_kwargs):
            return {"status": "ok", "request_id": "req-" + "a" * 16, "result": {"allowed": True}, "errors": []}, 0

        def record_external_execution_outcome(self, **kwargs):
            recorded_outcomes.append(kwargs)
            return {"audit_status": "recorded", "error_codes": []}

    monkeypatch.setattr(system_module, "MiniAgentClient", lambda **_kw: _AuditAuthority())

    # 1. Stitch to Person A
    res_a = asyncio.run(
        system_module.execute_stitch(
            system_module.StitchRequest(
                source_node_name="voice_pattern_test_speaker_1",
                target_person_name="Person A",
                confirm=True,
                confirmation_token="tok-a",
                operator_note="Initial stitch to Person A",
            )
        )
    )
    assert res_a.success is True
    targets_a = recorded_outcomes[-1]["side_effect_report"]["targets"]
    assert {"manual_identity_mappings.json", "identity_ledger.json", "identity_ledger.md"}.issubset(set(targets_a))
    assert str(db_path) in targets_a

    # 2. Re-stitch same pattern to Person B -> Person A history preserved as revoked, distinct mapping_id
    res_b = asyncio.run(
        system_module.execute_stitch(
            system_module.StitchRequest(
                source_node_name="voice_pattern_test_speaker_1",
                target_person_name="Person B",
                confirm=True,
                confirmation_token="tok-b",
                operator_note="Re-stitch to Person B",
            )
        )
    )
    assert res_b.mapping_id != res_a.mapping_id
    mappings = load_manual_mappings(db_path)["mappings"]
    assert len(mappings) == 2
    by_target = {m["target_person_name"]: m for m in mappings}
    assert by_target["Person A"]["status"] == "revoked"
    assert by_target["Person A"]["mapping_id"] == res_a.mapping_id
    assert by_target["Person B"]["status"] == "active"
    assert by_target["Person B"]["mapping_id"] == res_b.mapping_id

    # 3. Simulated KG failure during execute_stitch rolls back BOTH SQLite and JSON
    mappings_file = tmp_path / "manual_identity_mappings.json"
    before_json = mappings_file.read_bytes()
    before_kg = _snapshot(db_path)

    orig_add_edge = KnowledgeGraph.add_edge

    def _fail_add_edge(self, *args, **kwargs):
        raise RuntimeError("simulated edge failure")

    monkeypatch.setattr(KnowledgeGraph, "add_edge", _fail_add_edge)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            system_module.execute_stitch(
                system_module.StitchRequest(
                    source_node_name="voice_pattern_test_speaker_1",
                    target_person_name="Person C",
                    confirm=True,
                    confirmation_token="tok-c",
                )
            )
        )
    assert exc_info.value.status_code == 500
    monkeypatch.setattr(KnowledgeGraph, "add_edge", orig_add_edge)
    assert mappings_file.read_bytes() == before_json
    assert _snapshot(db_path) == before_kg

    # 4. Simulated save_manual_mappings failure during revoke_stitch rolls back SQLite edge deletion
    monkeypatch.setattr(
        system_module,
        "save_manual_mappings",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("simulated save failure")),
    )
    with pytest.raises(HTTPException) as rev_exc:
        asyncio.run(
            system_module.revoke_stitch(
                system_module.StitchRevokeRequest(
                    mapping_id=res_b.mapping_id,
                    confirmation_token="tok-rev-fail",
                )
            )
        )
    assert rev_exc.value.status_code == 500
    assert mappings_file.read_bytes() == before_json
    assert _snapshot(db_path) == before_kg

    # 5. Clean revoke reports all mutated targets
    monkeypatch.setattr(system_module, "save_manual_mappings", save_manual_mappings)
    rev_ok = asyncio.run(
        system_module.revoke_stitch(
            system_module.StitchRevokeRequest(
                mapping_id=res_b.mapping_id,
                confirmation_token="tok-rev-ok",
            )
        )
    )
    assert rev_ok.success is True
    rev_targets = recorded_outcomes[-1]["side_effect_report"]["targets"]
    assert {"manual_identity_mappings.json", "identity_ledger.json", "identity_ledger.md"}.issubset(set(rev_targets))
    assert str(db_path) in rev_targets


# ── IC-02 (+ AS-01 Gap 3): Pending scene_retirement & promotion gating ────────


def test_ic02_pending_scene_retirement_excluded_across_clusters_projection_appearances_and_promote(
    tmp_path: Path, monkeypatch
) -> None:
    from api.main import app
    from api.routes import identity

    vec_1 = [1.0, 0.0] + [0.0] * 126
    vec_2 = [0.0, 1.0] + [0.0] * 126
    movie = _make_movie_epoch(tmp_path, "epoch_movie_1", "movie_1.mp4", [vec_1, vec_2])
    epoch = movie["epoch"]
    ledger_path = movie["ledger"]
    kg_path = movie["kg"]
    scene_1 = movie["scenes"][0]["scene_id"]
    scene_2 = movie["scenes"][1]["scene_id"]

    prov_before = load_face_ucf_provenance(ledger_path)
    all_rows_before = [r for rows in prov_before.values() for r in rows]
    assert len(all_rows_before) == 2
    fid_1 = next(r["frame_id"] for r in all_rows_before if r["source_artifact_id"] == scene_1)
    fid_2 = next(r["frame_id"] for r in all_rows_before if r["source_artifact_id"] == scene_2)

    # Record pending UCF scene_retirement for scene_1 while KG scene node remains present.
    _retire_scene_in_ucf(ledger_path, epoch.name, scene_1)

    prov_after = load_face_ucf_provenance(ledger_path)
    assert [r["frame_id"] for rows in prov_after.values() for r in rows] == [fid_2]
    prov_with_retired = load_face_ucf_provenance(ledger_path, include_retired=True)
    assert sorted(r["frame_id"] for rows in prov_with_retired.values() for r in rows) == sorted([fid_1, fid_2])

    # Also test legacy unpromoted row without observation_timestamp in payload on a synthetic frame.
    with sqlite3.connect(ledger_path) as conn:
        row2 = conn.execute(
            "SELECT video_hash, ucf_schema_version, run_id, modality, model_tag, raw_ref, t_start, t_end, payload "
            "FROM context_frames WHERE frame_id=?",
            (fid_2,),
        ).fetchone()
        legacy_payload = json.loads(row2[8])
        legacy_payload.pop("observation_timestamp", None)
        legacy_json = json.dumps(legacy_payload, sort_keys=True)
        legacy_hash = hashlib.sha256(legacy_json.encode()).hexdigest()
        legacy_fid = conn.execute(
            "INSERT INTO context_frames("
            "video_hash,ucf_schema_version,epoch_id,run_id,modality,worker_name,model_tag,raw_ref,"
            "t_start,t_end,payload,payload_hash,promotion_status,source_artifact_id,occurrence_id"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                row2[0],
                row2[1],
                epoch.name,
                row2[2],
                row2[3],
                "face_embed",
                row2[4],
                row2[5],
                row2[6],
                row2[7],
                legacy_json,
                legacy_hash,
                "staged",
                scene_2,
                "legacy_staged_test",
            ),
        ).lastrowid

    ident_dir = tmp_path / "identity_movie_1"
    ident_dir.mkdir()
    clusters_doc = {
        "epoch_id": epoch.name,
        "clusters": [
            {"cluster_id": "fc_retired", "label": "Person A", "face_count": 1, "face_ids": [f"{fid_1}_0"]},
            {"cluster_id": "fc_staged", "label": "Person A", "face_count": 1, "face_ids": [f"{legacy_fid}_0"]},
            {"cluster_id": "fc_active", "label": "Person B", "face_count": 1, "face_ids": [f"{fid_2}_0"]},
        ],
    }
    (ident_dir / "face_clusters.json").write_text(json.dumps(clusters_doc), encoding="utf-8")
    roster_doc = {
        "identities": [
            {"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_retired"]},
            {"id": "person-b", "display_name": "Person B", "face_cluster_ids": ["fc_active"]},
        ]
    }
    (ident_dir / "family_roster.yaml").write_text(yaml.safe_dump(roster_doc), encoding="utf-8")

    cfg = {
        "epoch_id": epoch.name,
        "paths": {"db_path": str(epoch / "memory.db"), "knowledge_graph_db": str(kg_path)},
        "identity_search": {"roster_path": str(ident_dir / "family_roster.yaml"), "kg_db_path": str(kg_path)},
    }
    monkeypatch.setattr(identity, "_CFG", cfg)
    client = TestClient(app, client=("127.0.0.1", 50000))

    fc_resp = client.get("/api/identity/face-clusters")
    assert fc_resp.status_code == 200, fc_resp.text
    by_cid = {c["cluster_id"]: c for c in fc_resp.json()["clusters"]}
    assert by_cid["fc_retired"]["members"][0]["evidence_status"] == "unavailable"
    assert by_cid["fc_staged"]["members"][0]["evidence_status"] == "unavailable"
    assert by_cid["fc_active"]["members"][0]["evidence_status"] == "available"

    # Appearances preview refuses when a selected group references the retired scene.
    app_prev = client.get("/api/identity/appearances/preview")
    assert app_prev.status_code == 409

    # promote_identity_layer skips retired scenes and retired transcript segments.
    mem_db = epoch / "memory.db"
    with sqlite3.connect(mem_db) as mconn:
        mconn.execute("CREATE TABLE segments (video_hash TEXT, speaker TEXT, meta TEXT)")
        mconn.execute(
            "INSERT INTO segments VALUES (?, ?, ?)",
            (movie["video_hash"], "SPK_0", json.dumps({"scene_id": scene_1, "text": "Hello Person B"})),
        )
        mconn.execute(
            "INSERT INTO segments VALUES (?, ?, ?)",
            (movie["video_hash"], "SPK_0", json.dumps({"scene_id": scene_2, "text": "Hello Person B"})),
        )
    (ident_dir / "family_roster.yaml").write_text(
        yaml.safe_dump({"identities": [{"id": "person-b", "display_name": "Person B", "face_cluster_ids": ["fc_active"]}]}),
        encoding="utf-8",
    )
    plan = promote(epoch.name, kg_path, ident_dir, mem_db, dry_run=True)
    assert plan["errors"] == []
    scene_targets = {e["to"] for e in plan["edges_created"] if e["edge"] in {"person_appears_in_scene", "person_mentioned_in_scene"}}
    assert scene_targets == {scene_2}


def test_ic02_speaker_reviews_and_stitch_preview_exclude_retired_scenes(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch = tmp_path / "epoch_audio_1"
    (epoch / "ucf").mkdir(parents=True)
    ledger_path = epoch / "ucf" / "ucf_ledger.db"
    db_path = epoch / "knowledge_graph.db"
    vh = hashlib.sha256(b"movie_audio_1").hexdigest()
    sid_1 = hashlib.sha256(f"scene{vh}|0.000|10.000|".encode()).hexdigest()
    sid_2 = hashlib.sha256(f"scene{vh}|10.000|20.000|".encode()).hexdigest()

    ucf = UCFLedgerClient(str(ledger_path))
    ucf.init_schema()
    ucf.register_media(vh, "movie_1.mp4", 30.0, 25.0, 128, 100)
    ucf.close()
    with sqlite3.connect(ledger_path) as conn:
        fid_1 = conn.execute(
            "INSERT INTO context_frames("
            "video_hash,ucf_schema_version,epoch_id,run_id,modality,worker_name,model_tag,raw_ref,"
            "t_start,t_end,payload,payload_hash,promotion_status,source_artifact_id,occurrence_id"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vh, "ucf.v0.1", epoch.name, "run_1", "audio", "audio_asr", "whisper", "raw1.json", 0.0, 10.0, "{}", "", "promoted", sid_1, "occ_1"),
        ).lastrowid
    _retire_scene_in_ucf(ledger_path, epoch.name, sid_1)
    assert fid_1 > 0

    with KnowledgeGraph(str(db_path)) as kg:
        pat_id = kg.add_node("speaker_pattern", "voice_pattern_1", {"total_voiced_seconds": 12.0})
        kg.add_node("scene", sid_1, {"scene_id": sid_1, "video_id": vh, "speaker_change_review": {"status": "review_retired"}})
        kg.add_node("scene", sid_2, {"scene_id": sid_2, "video_id": vh, "speaker_change_review": {"status": "review_active"}})
        m1 = kg.add_media_node("video_scene", "movie_1.mp4", sid_1, 0.0, 10.0, {"video_id": vh, "video_hash": vh})
        m2 = kg.add_media_node("video_scene", "movie_1.mp4", sid_2, 10.0, 20.0, {"video_id": vh, "video_hash": vh})
        kg.link_node_to_media(pat_id, m1, 0.9, {})
        kg.link_node_to_media(pat_id, m2, 0.9, {})

    monkeypatch.setattr(system_module, "_get_kg_db_path", lambda: db_path)
    reviews = asyncio.run(system_module.get_speaker_change_reviews())
    assert [r["scene_id"] for r in reviews] == [sid_2]

    preview = asyncio.run(
        system_module.preview_stitch(
            system_module.StitchPreviewRequest(
                source_node_name="voice_pattern_1",
                target_person_name="Person A",
            )
        )
    )
    assert preview.scenes_affected == 1
    assert preview.episodes_affected == 1


# ── IC-03: Reference facts symmetry with reviewed_faces + deleted person guard ─


def test_ic03_same_reference_facts_allows_alias_with_reviewed_faces_and_blocks_deleted_person(
    reference_source, face_pipeline, tmp_path: Path, monkeypatch
) -> None:
    from api.main import app
    from api.routes import identity

    # Add roster-only Person B to reference_source before freezing.
    roster_path = Path(reference_source["identity_path"]) / "family_roster.yaml"
    groups_path = Path(reference_source["identity_path"]) / "face_clusters.json"
    saved_roster = yaml.safe_load(roster_path.read_text(encoding="utf-8"))
    saved_roster["identities"].append({"id": "person-b", "display_name": "Person B"})
    roster_path.write_text(yaml.safe_dump(saved_roster), encoding="utf-8")

    # Seed Movie 1 (reference_source epoch) with an applied reusable face review so it has reviewed_faces too!
    f = face_pipeline
    kg = f["epoch"] / "knowledge_graph.db"
    catalog_initial = matching.load_reference_catalog({"reference_sources": [reference_source]})
    frozen_initial = {
        "catalog": catalog_initial,
        "catalog_sha256": matching.digest(catalog_initial),
        "run_id": "seed-review",
        "policy": {"face_similarity": 0.6, "voice_similarity": 0.25, "minimum_margin": 0.05},
    }
    scenes = []
    with sqlite3.connect(kg) as conn:
        vid = conn.execute("INSERT INTO nodes(node_type,name) VALUES('video','movie_2')").lastrowid
        for idx in range(1, 4):
            faces = controlled_faces()
            faces[0]["encoding"] = [0.8, 0.6] + [0.0] * 126
            row, image, records = f["persist"](faces, index=idx, sampled=True)
            sid = conn.execute(
                "INSERT INTO nodes(node_type,name,properties) VALUES('scene',?,?)",
                (row["scene_id"], json.dumps({"ucf_provenance": [r[0] for r in records]})),
            ).lastrowid
            conn.execute("INSERT INTO edges(source_id,target_id,edge_type) VALUES(?,?,'video_contains_scene')", (vid, sid))
            row["keyframe"]["face_observations"] = [
                {"timestamp": row["keyframe"]["timestamp"], "source_path": str(image), "faces": faces[:1]}
            ]
            scenes.append(row)

    dest_ident = f["epoch"].parent / "dest-identity-ic03"
    dest_ident.mkdir()
    cfg = {
        "epoch_id": f["epoch"].name,
        "paths": {"db_path": str(f["epoch"] / "memory.db"), "knowledge_graph_db": str(kg)},
        "identity_search": {"roster_path": str(dest_ident / "family_roster.yaml"), "kg_db_path": str(kg)},
        "identity_matching": {"reference_sources": [reference_source]},
    }
    monkeypatch.setattr(identity, "_CFG", cfg)
    client = TestClient(app, client=("127.0.0.1", 50000))

    seed_video = {"video_hash": f["video_hash"], "video_path": "movie_2.mp4", "video_name": "movie_2.mp4", "scenes": scenes}
    seed_summary = matching.write_video_matches(cfg, frozen_initial, seed_video)
    seed_report = matching.read_json(matching.report_root(cfg) / "reports" / f"{seed_summary['id']}.json")
    seed_body = three_way_body(
        seed_report,
        {"report_id": seed_report["id"], "report_sha256": seed_report["content_sha256"], "accepted_ids": [seed_report["records"][0]["id"]]},
    )
    seed_receipt = apply_match_plan(client, preview_match_plan(client, seed_body)).json()

    # Now freeze a new report that includes BOTH group_id refs AND reviewed_faces for f["epoch"].
    catalog_with_reviewed = matching.load_reference_catalog(cfg["identity_matching"])
    assert any("review" in r for r in catalog_with_reviewed["faces"])
    frozen_next = {
        "catalog": catalog_with_reviewed,
        "catalog_sha256": matching.digest(catalog_with_reviewed),
        "run_id": "with-reviewed-refs",
        "policy": {"face_similarity": 0.6, "voice_similarity": 0.25, "minimum_margin": 0.05},
    }
    next_summary = matching.write_video_matches(cfg, frozen_next, seed_video)
    next_report = matching.read_json(matching.report_root(cfg) / "reports" / f"{next_summary['id']}.json")

    # Undo seed_receipt only after we verify alias edit on next_report? Wait: keep seed_receipt applied so reviewed_faces stay active,
    # and preview selecting record[1] (which wasn't accepted in seed_receipt).
    assert seed_receipt["status"] == "applied"
    review_body = {
        "report_id": next_report["id"],
        "report_sha256": next_report["content_sha256"],
        "accepted_ids": [next_report["records"][1]["id"]],
    }

    # Edit alias + display-only group label while reviewed_faces exist -> MUST SUCCEED (200)!
    edited_roster = yaml.safe_load(roster_path.read_text(encoding="utf-8"))
    edited_roster["identities"][0]["aliases"] = ["Alias A"]
    roster_path.write_text(yaml.safe_dump(edited_roster), encoding="utf-8")
    edited_groups = json.loads(groups_path.read_text(encoding="utf-8"))
    edited_groups["clusters"][0]["label"] = "Updated Group Label"
    groups_path.write_text(json.dumps(edited_groups), encoding="utf-8")

    ok_resp = client.post("/api/identity/matches/preview", json=review_body)
    assert ok_resp.status_code == 200, ok_resp.text

    # Delete roster-only Person B from family_roster.yaml -> public report drops Person B and preview refuses (409)!
    edited_roster["identities"] = [p for p in edited_roster["identities"] if p["id"] != "person-b"]
    roster_path.write_text(yaml.safe_dump(edited_roster), encoding="utf-8")

    pub = client.get(f"/api/identity/matches/{next_report['id']}").json()
    assert "person-b" not in {p["id"] for p in pub["people"]}

    stale_resp = client.post("/api/identity/matches/preview", json=review_body)
    assert stale_resp.status_code == 409


# ── IC-04: Multi-report scan, live KG cluster suggestions, A->B->A refresh ────


def test_ic04_multi_report_person_scan_and_live_kg_cluster_suggestions_and_aba_refresh(
    tmp_path: Path, monkeypatch
) -> None:
    from api.main import app
    from api.routes import identity

    vec_a = [1.0, 0.0, 0.0] + [0.0] * 125
    vec_b = [0.0, 1.0, 0.0] + [0.0] * 125
    movie_1 = _make_movie_epoch(tmp_path, "epoch_m1", "movie_1.mp4", [vec_a, vec_b])
    movie_2 = _make_movie_epoch(tmp_path, "epoch_m2", "movie_2.mp4", [vec_a, vec_b])

    m1_epoch, m2_epoch = movie_1["epoch"], movie_2["epoch"]
    m1_ident = tmp_path / "ident_m1"
    m1_ident.mkdir()
    m2_ident = tmp_path / "ident_m2"
    m2_ident.mkdir()

    m1_prov = load_face_ucf_provenance(movie_1["ledger"])
    m1_frames = sorted(r["frame_id"] for rows in m1_prov.values() for r in rows)
    m2_prov = load_face_ucf_provenance(movie_2["ledger"])
    m2_frames = sorted(r["frame_id"] for rows in m2_prov.values() for r in rows)

    # Movie 1 has Person A via cluster fc_m1_a, AND Person B via live KG person_appears_in_scene edge!
    (m1_ident / "face_clusters.json").write_text(
        json.dumps(
            {
                "epoch_id": m1_epoch.name,
                "clusters": [{"cluster_id": "fc_m1_a", "label": "Person A", "face_count": 1, "face_ids": [f"{m1_frames[0]}_0"]}],
            }
        ),
        encoding="utf-8",
    )
    (m1_ident / "family_roster.yaml").write_text(
        yaml.safe_dump({"identities": [{"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_m1_a"]}]}),
        encoding="utf-8",
    )
    m1_results = m1_epoch / "scene_ingest_results.json"
    m1_results.write_text(json.dumps([{"video_hash": movie_1["video_hash"], "video_name": "movie_1.mp4", "scenes": movie_1["scenes"]}]), encoding="utf-8")

    # Movie 2 output/scene_ingest_results.json for refresh_epoch_matches
    m2_out = m2_epoch / "output"
    m2_out.mkdir()
    (m2_out / "scene_ingest_results.json").write_text(
        json.dumps([{"video_hash": movie_2["video_hash"], "video_path": "movie_2.mp4", "video_name": "movie_2.mp4", "scenes": movie_2["scenes"]}]),
        encoding="utf-8",
    )
    (m2_ident / "face_clusters.json").write_text(
        json.dumps(
            {
                "epoch_id": m2_epoch.name,
                "clusters": [
                    {"cluster_id": "fc_m2_a", "label": None, "face_count": 1, "face_ids": [f"{m2_frames[0]}_0"]},
                    {"cluster_id": "fc_m2_b", "label": None, "face_count": 1, "face_ids": [f"{m2_frames[1]}_0"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    ref_src = {
        "epoch_root": str(m1_epoch),
        "identity_path": str(m1_ident),
        "results_path": str(m1_results),
    }
    cfg = {
        "epoch_id": m2_epoch.name,
        "paths": {
            "db_path": str(m2_epoch / "memory.db"),
            "knowledge_graph_db": str(movie_2["kg"]),
            "output_directory": str(m2_out),
        },
        "identity_search": {"roster_path": str(m2_ident / "family_roster.yaml"), "kg_db_path": str(movie_2["kg"])},
        "identity_matching": {"enabled": True, "reference_sources": [ref_src]},
    }
    monkeypatch.setattr(identity, "_CFG", cfg)
    client = TestClient(app, client=("127.0.0.1", 50000))

    # 1. Initial refresh (Catalog A: Person A only) -> creates Report R1
    r1 = matching.refresh_epoch_matches(cfg)
    assert r1["refreshed"] is True

    # 2. Add Person B into Movie 1's live KG (person_appears_in_scene) WITHOUT refreshing reports yet!
    with sqlite3.connect(movie_1["kg"]) as conn:
        pb_id = conn.execute(
            "INSERT INTO nodes(node_type,name,properties) VALUES('Person','person-b',?)",
            (json.dumps({"display_name": "Person B"}),),
        ).lastrowid
        s2_id = conn.execute(
            "SELECT id FROM nodes WHERE node_type='scene' AND name=?",
            (movie_1["scenes"][1]["scene_id"],),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO edges(source_id,target_id,edge_type,weight,properties) VALUES(?,?,'person_appears_in_scene',0.7,?)",
            (pb_id, s2_id, json.dumps({"confidence": "candidate", "evidence_face_ids": [f"{m1_frames[1]}_0"]})),
        )

    # Even though R1 exists (had_report_refs == True) and m1_epoch is in reference_sources,
    # Movie 2's face-clusters MUST surface Person B in suggested_matches for fc_m2_b AND cross-film-scan?person_id=person-b MUST succeed!
    fc = client.get("/api/identity/face-clusters").json()
    m2_b_suggestions = next(c for c in fc["clusters"] if c["cluster_id"] == "fc_m2_b")["suggested_matches"]
    assert any(s["person_id"] == "person-b" for s in m2_b_suggestions)

    scan_live_kg = client.get("/api/identity/cross-film-scan", params={"person_id": "person-b", "min_similarity": 0.5})
    assert scan_live_kg.status_code == 200, scan_live_kg.text
    assert scan_live_kg.json()["current_movie"]["epoch_id"] == m2_epoch.name
    assert scan_live_kg.json()["current_movie"]["total_matches"] >= 1

    # 3. Also verify multi-report scan when Person C exists only in a second report file in reports_dir
    rep1_path = matching.report_root(cfg) / "reports" / f"{r1['latest_report_id']}.json"
    rep2 = copy.deepcopy(matching.read_json(rep1_path))
    rep2_id = "f" * 64
    rep2["id"] = rep2_id
    rep2["run_id"] = "second_video_report"
    rep2["people"].append({"id": "person-c", "display_name": "Person C"})
    rep2["references"].append(
        {
            "id": "c" * 64,
            "person_id": "person-c",
            "display_name": "Person C",
            "epoch_id": "external_prior_epoch",
            "observation_id": "999_0",
            "space": "opencv-yunet-sface",
            "embedding": matching.unit(vec_b),
            "media": dict(rep2["references"][0]["media"]),
        }
    )
    rep2["content_sha256"] = matching.digest({k: v for k, v in rep2.items() if k != "content_sha256"})
    rep2_path = matching.report_root(cfg) / "reports" / f"{rep2_id}.json"
    rep2_path.write_text(json.dumps(rep2), encoding="utf-8")
    # Make rep1 newer than rep2 so rep2 is the SECOND report in mtime order!
    newer_ns = rep2_path.stat().st_mtime_ns + 5_000_000
    os.utime(rep1_path, ns=(newer_ns, newer_ns))

    scan_c = client.get("/api/identity/cross-film-scan", params={"person_id": "person-c", "min_similarity": 0.5})
    assert scan_c.status_code == 200, scan_c.text
    assert scan_c.json()["target"]["person_id"] == "person-c"
    assert scan_c.json()["current_movie"]["total_matches"] >= 1
    rep2_path.unlink()

    # 4. Verify A -> B -> A catalog revert in refresh_epoch_matches writes a fresh latest report
    (m1_ident / "family_roster.yaml").write_text(
        yaml.safe_dump(
            {
                "identities": [
                    {"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_m1_a"]},
                    {"id": "person-extra", "display_name": "Person Extra"},
                ]
            }
        ),
        encoding="utf-8",
    )
    r2 = matching.refresh_epoch_matches(cfg)
    assert r2["refreshed"] is True and r2["latest_report_id"] != r1["latest_report_id"]

    # Revert Movie 1 roster back to Catalog A!
    (m1_ident / "family_roster.yaml").write_text(
        yaml.safe_dump({"identities": [{"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_m1_a"]}]}),
        encoding="utf-8",
    )
    r3 = matching.refresh_epoch_matches(cfg)
    assert r3["refreshed"] is True and r3["mutated"] is True
    listed = client.get("/api/identity/matches").json()["reports"]
    assert listed[0]["id"] == r3["latest_report_id"]


# ── IC-05: Roster delete persistence, export duplicate guards, JS scanCache ───


def test_ic05_roster_delete_persists_and_export_rejects_duplicates(
    tmp_path: Path, monkeypatch
) -> None:
    from api.main import app
    from api.routes import identity

    epoch = tmp_path / "epoch_ic05"
    epoch.mkdir()
    ident_dir = tmp_path / "ident_ic05"
    ident_dir.mkdir()
    (ident_dir / "face_clusters.json").write_text(
        json.dumps(
            {
                "epoch_id": epoch.name,
                "clusters": [{"cluster_id": "fc_1", "label": "Person A", "face_count": 1, "face_ids": ["1_0"]}],
            }
        ),
        encoding="utf-8",
    )
    cfg = {
        "epoch_id": epoch.name,
        "paths": {"db_path": str(epoch / "memory.db"), "knowledge_graph_db": str(epoch / "knowledge_graph.db")},
        "identity_search": {"roster_path": str(ident_dir / "family_roster.yaml")},
    }
    monkeypatch.setattr(identity, "_CFG", cfg)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = TestClient(app, client=("127.0.0.1", 50000))

    def _confirmed_post(url: str, payload: dict):
        prep = client.post(url, json=payload)
        assert prep.status_code == 403, prep.text
        tok = prep.json()["result"]["confirmation_token"]
        return client.post(url, json={**payload, "confirmation_token": tok})

    # Save Person A and Person B
    r_a = _confirmed_post(
        "/api/identity/roster/save",
        {"identity": {"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_1"]}},
    )
    assert r_a.status_code == 200, r_a.text
    r_b = _confirmed_post(
        "/api/identity/roster/save",
        {"identity": {"id": "person-b", "display_name": "Person B", "face_cluster_ids": []}},
    )
    assert r_b.status_code == 200, r_b.text

    # Token for non-delete save CANNOT be reused for delete=True
    prep_save = client.post(
        "/api/identity/roster/save",
        json={"identity": {"id": "person-b", "display_name": "Person B"}},
    )
    save_tok = prep_save.json()["result"]["confirmation_token"]
    forged_del = client.post(
        "/api/identity/roster/save",
        json={"identity": {"id": "person-b", "display_name": "Person B"}, "delete": True, "confirmation_token": save_tok},
    )
    assert forged_del.status_code == 403

    # Confirmed delete removes Person B from family_roster.yaml on disk
    del_b = _confirmed_post(
        "/api/identity/roster/save",
        {"identity": {"id": "person-b", "display_name": "Person B"}, "delete": True},
    )
    assert del_b.status_code == 200 and del_b.json()["deleted"] is True
    loaded_ids = [i["id"] for i in client.get("/api/identity/roster").json()["identities"]]
    assert loaded_ids == ["person-a"]

    # Export rejects duplicate identity IDs with 409 without mutating disk
    dup_id_resp = _confirmed_post(
        "/api/identity/roster/export",
        {
            "identities": [
                {"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_1"]},
                {"id": "person-a", "display_name": "Person A Duplicate", "face_cluster_ids": []},
            ]
        },
    )
    assert dup_id_resp.status_code == 409
    assert dup_id_resp.json()["detail"]["code"] == "duplicate_identity_id"

    # Export rejects duplicate face_cluster_ids across identities with 409 without mutating disk
    dup_fc_resp = _confirmed_post(
        "/api/identity/roster/export",
        {
            "identities": [
                {"id": "person-a", "display_name": "Person A", "face_cluster_ids": ["fc_1"]},
                {"id": "person-c", "display_name": "Person C", "face_cluster_ids": ["fc_1"]},
            ]
        },
    )
    assert dup_fc_resp.status_code == 409
    assert dup_fc_resp.json()["detail"]["code"] == "face_cluster_already_owned"
    assert [i["id"] for i in client.get("/api/identity/roster").json()["identities"]] == ["person-a"]


def test_ic05_workbench_js_delete_identity_and_matches_scan_cache_reset() -> None:
    # 1. Verify matches.js clears scanCache inside loadReport(id)
    matches_src = MATCHES_JS.read_text(encoding="utf-8")
    load_idx = matches_src.index("async function loadReport(id)")
    try_idx = matches_src.index("try {", load_idx)
    header_block = matches_src[load_idx:try_idx]
    assert "openScanIds.clear();" in header_block
    assert "scanCache.clear();" in header_block

    # 2. Verify identity.js delete button persists via confirmedIdentityRequest("/api/identity/roster/save", {..., delete: true})
    script = r"""
const fs = require("fs");
class ClassList { add() {} remove() {} toggle() {} }
class Element {
  constructor(id = "") {
    this.id = id;
    this.children = [];
    this.classList = new ClassList();
    this.dataset = {};
    this.hidden = false;
    this.innerHTML = "";
    this.open = false;
    this.style = {};
    this.textContent = "";
    this.value = "";
    this.listeners = {};
  }
  addEventListener(ev, fn) { this.listeners[ev] = fn; }
  appendChild(c) { this.children.push(c); return c; }
  insertAdjacentHTML(_p, h) { this.innerHTML += h; }
  close() { this.open = false; }
  remove() {}
  querySelector() { return new Element(); }
  querySelectorAll() { return []; }
  setAttribute() {}
  showModal() { this.open = true; }
}
const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, new Element(id));
  return elements.get(id);
};
global.document = {
  addEventListener() {},
  createElement() { return new Element(); },
  getElementById: element,
  querySelectorAll() { return []; },
};
global.window = { confirm: () => false };
global.setTimeout = (cb) => { cb(); return 0; };

let source = fs.readFileSync(process.env.IDENTITY_JS, "utf8");
source = source.replace(
  /\s*init\(\);\s*\}\)\(\);\s*$/,
  "\n  globalThis.__wb = { state, ui, renderRosterDetail, deleteIdentity };\n})();\n"
);
eval(source);
const wb = globalThis.__wb;

function response(status, payload) {
  return { ok: status >= 200 && status < 300, status, statusText: "ERR", json: async () => payload };
}

async function main() {
  wb.state.actions = { family_facts: { ready: true } };
  wb.state.roster = [{ id: "person-a", display_name: "Person A", aliases: [], face_cluster_ids: [], speaker_cluster_ids: [], name_mention_keys: [] }];
  wb.renderRosterDetail(0);

  // Cancelled confirmation must NOT splice state.roster in memory!
  let calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, body: JSON.parse(opts.body) });
    return response(403, { result: { confirmation_token: "del-tok-1" } });
  };
  await element("delete-identity-0").listeners.click();
  if (wb.state.roster.length !== 1) throw new Error("Cancelled delete mutated state.roster");
  if (calls.length !== 1 || calls[0].body.delete !== true) throw new Error("Delete did not send delete:true");

  // Confirmed 200 persists then removes from state.roster
  calls = [];
  global.window.confirm = () => true;
  global.fetch = async (url, opts) => {
    const body = JSON.parse(opts.body);
    calls.push({ url, body });
    if (calls.length === 1) return response(403, { result: { confirmation_token: "del-tok-2" } });
    return response(200, { ok: true, id: "person-a", deleted: true });
  };
  await wb.deleteIdentity(0);
  if (calls.length !== 2 || calls[1].body.confirmation_token !== "del-tok-2" || calls[1].body.delete !== true) {
    throw new Error("Confirmed delete did not send scoped retry");
  }
  if (wb.state.roster.length !== 0) throw new Error("Confirmed delete did not remove roster item");
}
main().catch((err) => { console.error(err); process.exit(1); });
"""
    proc = subprocess.run(
        ["node", "-e", script],
        env={**os.environ, "IDENTITY_JS": str(IDENTITY_JS)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
