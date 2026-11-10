"""Scene retirement through the governed caller and real persistence boundaries."""
import json
import sqlite3
import uuid

import pytest
import requests

pytest.importorskip("goodq_mini_agent")

from agents.mini_agent_client import MiniAgentClient
from scripts.ucf.ucf_ledger import UCFLedgerClient, read_scene_retirements
from steps.common.memory import _make_id
from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
from steps.video_scene_detect import step as scene_step
from tests.unit.test_ucf_promotion_scene_identity import confirmed, scene_promotion, stage_source


def prepare(scene_promotion, monkeypatch, *, shared=False, legacy=False):
    root, config, client = scene_promotion
    monkeypatch.setattr(scene_step, "_detect_with_scenedetect", lambda *_: {
        "duration": 3.0, "scenes": [
            {"index": i, "start": float(i), "end": float(i + 1), "duration": 1.0, "confidence": 1.0}
            for i in range(3)]})
    monkeypatch.setattr(scene_step, "_get_video_dimensions", lambda _: (3.0, 10.0, 64, 48))
    vh, _ = stage_source(root, config, "three_windows")
    ids = [_make_id("scene", [vh, f"{i:.3f}", f"{i + 1:.3f}"]) for i in range(3)]
    scenes = [{"scene_id": sid, "video_id": vh, "index": i,
               "start": float(i), "end": float(i + 1), "duration": 1.0,
               "keyframe": {"caption": f"Window {i}", "ocr_text": f"Evidence {i}"}}
              for i, sid in enumerate(ids)]
    if shared:
        for scene in scenes[:2]:
            scene["audio"] = {"speaker_transcript": [
                {"start": 0.5, "end": 1.5, "speaker": "speaker_01", "text": "Shared utterance"}]}
    manifest = root / "processing/three_windows/video/scene_manifest.json"
    manifest.write_text(json.dumps({"video_hash": vh, "scenes": scenes}), encoding="utf-8")
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    for i, sid in enumerate(ids[1:], 1):
        ledger.log_frame(video_hash=vh, epoch_id=root.name, run_id="scene-retirement",
                         t_start=float(i), t_end=float(i + 1), modality="video", worker_name="image_caption",
                         model_tag="fixture", source_artifact_id=sid, payload={"caption": f"Window {i}"})
    ledger.close()
    if legacy:
        with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
            for i, sid in enumerate(ids):
                conn.execute("UPDATE context_frames SET source_artifact_id=? WHERE source_artifact_id=? AND worker_name='video_scene_detect'", (f"scene_{i:04d}", sid))
    scope = {"video_hash": vh, "epoch_id": root.name}
    result, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, result
    result, _ = confirmed(client, "promote_ucf_to_memory", scope)
    assert result["output"]["status"] == "promotion_committed_sync_pending", result
    with sqlite3.connect(root / "memory.db") as conn:
        assert set(conn.execute("SELECT id FROM scenes").fetchall()) == {(sid,) for sid in ids}
    return root, config, client, scope, ids


@pytest.mark.parametrize("legacy", [False, True])
def test_caller_retires_middle_scene_and_repeat_preserves_neighbors(scene_promotion, monkeypatch, legacy):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch, legacy=legacy)
    manifest = root / "processing/three_windows/video/scene_manifest.json"
    before_bytes = manifest.read_bytes()
    for attempt in range(2):
        result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
        assert rc == 0 and result["output"]["status"] == "superseded_complete", result
        with sqlite3.connect(root / "memory.db") as conn:
            assert set(conn.execute("SELECT id FROM scenes").fetchall()) == {(ids[0],), (ids[2],)}
            assert set(conn.execute("SELECT scene_id FROM scene_text_fts").fetchall()) == {(ids[0],), (ids[2],)}
        with sqlite3.connect(root / "knowledge_graph.db") as conn:
            assert {r[0] for r in conn.execute("SELECT scene_id FROM media_nodes")} == {ids[0], ids[2]}
            assert conn.execute("SELECT COUNT(*) FROM nodes WHERE node_type='video'").fetchone() == (1,)
        with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='promoted'").fetchone() == (4,)
            assert conn.execute("SELECT COUNT(*) FROM ucf_status_transitions WHERE scope LIKE 'scene_retirement:%'").fetchone() == (1,)
            assert conn.execute("SELECT attempt_count FROM ucf_qdrant_sync_outbox WHERE operation LIKE 'scene_retirement:%'").fetchone() == (1,)
            assert conn.execute("SELECT delivery_state FROM ucf_qdrant_sync_outbox WHERE operation='promotion'").fetchone() == ("pending",)
        assert manifest.read_bytes() == before_bytes
    assert read_scene_retirements(root / "ucf/ucf_ledger.db", **scope)[0]["scene_id"] == ids[1]


@pytest.mark.parametrize("change", [{"scene_id": "foreign"}, {"scene_id": ""}, {"scene_index": 1},
                                    {"scene_ids": ["anything"]}, {"video_id": "alias"}, {"epoch_id": "other-epoch"}])
def test_invalid_scope_never_issues_confirmation_or_writes(scene_promotion, monkeypatch, change):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    request, rc = client.execute_tool("supersede_ucf_frames", {**scope, "scene_id": ids[1], **change})
    assert rc == 1 and request["status"] == "error", request
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes").fetchone() == (3,)


def test_committed_exclusion_survives_failed_delivery_and_new_client_retry(scene_promotion, monkeypatch):
    root, config, client, scope, ids = prepare(scene_promotion, monkeypatch)
    monkeypatch.setattr(client, "_dematerialize_scene_views", lambda _: (_ for _ in ()).throw(RuntimeError("interrupted after ledger commit")))
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 1 and result["output"]["ledger_retirement_committed"], result
    assert result["output"]["delivery_state"] == "pending"
    denied, denied_rc = client.execute_tool("reconcile_ucf_qdrant", {**scope, "scene_id": ids[1]})
    assert denied_rc == 1 and "invalid_tool_arguments" in json.dumps(denied)
    evidence = read_scene_retirements(root / "ucf/ucf_ledger.db", **scope)
    assert evidence[0]["scene_id"] == ids[1]
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes").fetchone() == (3,)
    replacement = MiniAgentClient(profile="safe", config=config)
    monkeypatch.setattr(replacement, "_sync_ucf_status_to_qdrant", client._sync_ucf_status_to_qdrant)
    monkeypatch.setattr(replacement, "_sync_qdrant_by_scope", client._sync_qdrant_by_scope)
    result, rc = confirmed(replacement, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    assert read_scene_retirements(root / "ucf/ucf_ledger.db", **scope) == evidence
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT attempt_count,delivery_state FROM ucf_qdrant_sync_outbox WHERE operation LIKE 'scene_retirement:%'").fetchone() == (2, "complete")


def test_failed_audit_rolls_back_ledger_and_outbox_together(scene_promotion, monkeypatch):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    monkeypatch.setattr(UCFLedgerClient, "insert_status_transition", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 1 and "audit unavailable" in json.dumps(result)
    assert read_scene_retirements(root / "ucf/ucf_ledger.db", **scope) == []
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='promoted'").fetchone() == (6,)
        assert conn.execute("SELECT COUNT(*) FROM ucf_qdrant_sync_outbox WHERE operation LIKE 'scene_retirement:%'").fetchone() == (0,)


def test_shared_entity_keeps_neighbor_occurrence(scene_promotion, monkeypatch):
    from lib.knowledge_graph import KnowledgeGraph
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    with KnowledgeGraph(str(root / "knowledge_graph.db")) as kg:
        shared = kg.add_node("person", "Confirmed shared person")
        target_only = kg.add_node("object", "Target-only object")
        for sid in ids[:2]:
            media = kg.conn.execute("SELECT id FROM media_nodes WHERE scene_id=?", (sid,)).fetchone()[0]
            kg.link_node_to_media(shared, media)
            if sid == ids[1]:
                kg.link_node_to_media(target_only, media)
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    with sqlite3.connect(root / "knowledge_graph.db") as conn:
        assert conn.execute("SELECT m.scene_id FROM node_media nm JOIN media_nodes m ON m.id=nm.media_id WHERE nm.node_id=?", (shared,)).fetchall() == [(ids[0],)]
        assert conn.execute("SELECT id FROM nodes WHERE id=?", (shared,)).fetchone() == (shared,)
        assert conn.execute("SELECT id FROM nodes WHERE id=?", (target_only,)).fetchone() is None


@pytest.mark.parametrize("alias", [False, True])
def test_producer_replay_refuses_retired_scene_without_mutating_evidence(scene_promotion, monkeypatch, alias):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch, legacy=alias)
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    db = root / "ucf/ucf_ledger.db"
    with sqlite3.connect(db) as conn:
        before = conn.execute("SELECT * FROM context_frames").fetchall()
    ledger = UCFLedgerClient(str(db))
    with pytest.raises(ValueError, match="replay is not restoration"):
        ledger.log_frame(**scope, run_id="retry", t_start=1.0, t_end=2.0, modality="video",
                         worker_name="new_worker", model_tag="fixture",
                         source_artifact_id="scene_0001" if alias else ids[1])
    ledger.close()
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT * FROM context_frames").fetchall() == before


@pytest.mark.parametrize("remove_alias", [False, True])
def test_promoter_refuses_reintroduced_retired_evidence(scene_promotion, monkeypatch, remove_alias):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        conn.execute("UPDATE context_frames SET promotion_status='validated' WHERE source_artifact_id=?", (ids[1],))
        if remove_alias:
            conn.execute("UPDATE context_frames SET source_artifact_id=NULL WHERE source_artifact_id=?", (ids[1],))
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc == 1 and "cannot be promoted" in json.dumps(result), result
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes").fetchone() == (2,)


@pytest.mark.parametrize("artifact", [None, "unrelated-alias"])
def test_replayed_retired_frame_cannot_hide_its_identity(scene_promotion, monkeypatch, artifact):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    with pytest.raises(ValueError, match="replay is not restoration"):
        ledger.log_frame(**scope, run_id="retry-without-label", t_start=1.0, t_end=2.0,
                         modality="video", worker_name="image_caption", model_tag="fixture",
                         source_artifact_id=artifact)
    ledger.close()


def test_shared_segment_survives_first_scene_retirement(scene_promotion, monkeypatch):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch, shared=True)
    with sqlite3.connect(root / "memory.db") as conn:
        segment = conn.execute("SELECT id FROM segments").fetchone()[0]
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[0]})
    assert rc == 0, result
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT id FROM segments").fetchall() == [(segment,)]
        assert conn.execute("SELECT parent_hash FROM links WHERE child_hash=? AND relation='overlaps'", (segment,)).fetchall() == [(ids[1],)]
        assert conn.execute("SELECT COUNT(*) FROM ucf_provenance_mapping WHERE record_type='segment'").fetchone()[0] > 0
    with sqlite3.connect(root / "knowledge_graph.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM nodes WHERE node_type='segment' AND name=?", (segment,)).fetchone() == (1,)
        assert conn.execute("SELECT s.name FROM edges e JOIN nodes s ON s.id=e.source_id JOIN nodes t ON t.id=e.target_id WHERE e.edge_type='scene_has_segment' AND t.name=?", (segment,)).fetchall() == [(ids[1],)]


@pytest.mark.parametrize("corruption", ["json", "scope", "frames", "vectors"])
def test_corrupt_relevant_evidence_is_visible_on_read_and_retry(scene_promotion, monkeypatch, corruption):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    db = root / "ucf/ucf_ledger.db"
    with sqlite3.connect(db) as conn:
        raw = conn.execute("SELECT evidence FROM ucf_status_transitions WHERE scope LIKE 'scene_retirement:%'").fetchone()[0]
        value = json.loads(raw)
        if corruption == "scope":
            value["scene_id"] = ids[0]
        elif corruption == "frames":
            value["frame_ids"] = [999]
        elif corruption == "vectors":
            value["vectors"] = [{}]
        conn.execute("UPDATE ucf_status_transitions SET evidence=? WHERE scope LIKE 'scene_retirement:%'", ("broken" if corruption == "json" else json.dumps(value),))
    with pytest.raises(ValueError, match="Corrupt scene retirement"):
        read_scene_retirements(db, **scope)
    request, rc = client.execute_tool("supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 1 and "Corrupt scene retirement" in json.dumps(request)


def test_read_missing_ledger_does_not_create_it(tmp_path):
    missing = tmp_path / "absent/ledger.db"
    assert read_scene_retirements(missing, video_hash="source") == []
    assert not missing.parent.exists()


def test_faiss_only_frame_does_not_require_qdrant_collection(scene_promotion, monkeypatch):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    fid = ledger.log_frame(**scope, run_id="faiss", t_start=1.0, t_end=2.0, modality="video",
                           worker_name="image_embed_clip", model_tag="fixture", source_artifact_id=ids[1],
                           vector_key="a" * 64, vector_backend="faiss", promotion_status="promoted")
    ledger.close()
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    evidence = read_scene_retirements(root / "ucf/ucf_ledger.db", **scope)[0]
    assert fid in evidence["frame_ids"] and evidence["vectors"][0]["collection"] is None


def test_real_vector_transport_changes_only_target_across_four_families(scene_promotion, monkeypatch):
    root, _, client, scope, ids = prepare(scene_promotion, monkeypatch)
    points = {}
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    for family in ("text", "audio", "clip", "dino"):
        collection = f"goodq_{family}_{root.name}"
        points[collection] = {}
        for i, sid in enumerate(ids):
            key = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, family + sid))
            ledger.log_frame(**scope, run_id="fixture-vectors", t_start=float(i), t_end=float(i + 1),
                             modality="audio" if family == "audio" else "text" if family == "text" else "video",
                             worker_name=f"fixture_{family}", model_tag="fixture", source_artifact_id=sid,
                             vector_key=key, vector_backend="qdrant", vector_collection=collection,
                             promotion_status="promoted")
            points[collection][key] = {"id": key, "payload": {**scope, "scene_id": sid, "ucf_promotion_status": "promoted"}}
    ledger.close()

    def response(value):
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps({"result": value}).encode()
        return result

    def matches(point, filter_):
        def condition(rule):
            if "has_id" in rule:
                return point["id"] in rule["has_id"]
            value = point["payload"].get(rule["key"])
            return value in rule["match"]["any"] if "any" in rule["match"] else value == rule["match"]["value"]
        return all(condition(c) for c in filter_.get("must", [])) and not any(condition(c) for c in filter_.get("must_not", []))

    def post(url, *, json, **kwargs):
        collection = url.split("/collections/")[1].split("/")[0]
        selected = [p for p in points[collection].values()
                    if (p["id"] in json["ids"] if "ids" in json else
                        p["id"] in json["points"] if "points" in json else matches(p, json.get("filter", {})))]
        if "/payload" in url:
            for point in selected:
                point["payload"].update(json["payload"])
            return response({"status": "completed"})
        return response({"points": selected, "next_page_offset": None} if "/scroll" in url else selected)

    monkeypatch.setattr(requests, "get", lambda *a, **k: response({"collections": [{"name": name} for name in points]}))
    monkeypatch.setattr(requests, "post", post)
    for name in ("_sync_ucf_status_to_qdrant", "_sync_qdrant_by_scope"):
        monkeypatch.setattr(client, name, getattr(MiniAgentClient, name).__get__(client))
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 0, result
    for collection in points.values():
        assert {p["payload"]["scene_id"]: p["payload"]["ucf_promotion_status"] for p in collection.values()} == {
            ids[0]: "promoted", ids[1]: "superseded", ids[2]: "promoted"}
    # A late vector write cannot be swept back into promoted visibility on retry.
    for collection in points.values():
        for point in collection.values():
            if point["payload"]["scene_id"] == ids[1]:
                point["payload"]["ucf_promotion_status"] = "staged"
    sync = client._sync_qdrant_by_scope(epoch_id=scope["epoch_id"], video_hash=scope["video_hash"], status_val="promoted")
    assert sync["status"] == "ok", sync
    assert all(p["payload"]["ucf_promotion_status"] == "staged" for c in points.values() for p in c.values() if p["payload"]["scene_id"] == ids[1])


@pytest.mark.parametrize("cross_video", [False, True])
@pytest.mark.parametrize("missing_artifact", [False, True])
def test_shared_content_point_rebinds_exact_survivor_without_retired_context(scene_promotion, monkeypatch, cross_video, missing_artifact):
    import hashlib
    from steps.common.memory import to_faiss_id
    root, config, client, scope, ids = prepare(scene_promotion, monkeypatch)
    survivor_video, survivor_id = scope["video_hash"], ids[0]
    if cross_video:
        monkeypatch.setattr(scene_step, "_detect_with_scenedetect", lambda *_: {
            "duration": 1.0, "scenes": [{"index": 0, "start": 0.0, "end": 1.0, "duration": 1.0, "confidence": 1.0}]})
        monkeypatch.setattr(scene_step, "_get_video_dimensions", lambda _: (1.0, 10.0, 64, 48))
        survivor_video, survivor_id = stage_source(root, config, "other_movie")
        other_scope = {**scope, "video_hash": survivor_video}
        result, rc = confirmed(client, "validate_ucf_frames", other_scope)
        assert rc == 0, result
        result, _ = confirmed(client, "promote_ucf_to_memory", other_scope)
        assert result["output"]["status"] == "promotion_committed_sync_pending"
    artifact = root / "processing/survivor_frame.png"
    artifact.write_bytes(b"identical decoded frame source bytes")
    key = hashlib.sha256(artifact.read_bytes()).hexdigest()
    point_id = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, key))
    collection = f"goodq_clip_{root.name}"
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    fid = ledger.log_frame(video_hash=survivor_video, epoch_id=root.name, run_id="survivor",
                           t_start=0.0, t_end=1.0, modality="video", worker_name="image_embed_clip",
                           model_tag="ViT-B-32", vector_model_tag="ViT-B-32", source_artifact_id=survivor_id,
                           vector_key=key, vector_backend="qdrant", vector_collection=collection, promotion_status="promoted")
    target_fid = ledger.log_frame(**scope, run_id="retiring-owner", t_start=1.0, t_end=2.0, modality="video",
                                 worker_name="image_embed_clip", model_tag="ViT-B-32", source_artifact_id=ids[1],
                                 vector_key=key, vector_backend="qdrant", vector_collection=collection, promotion_status="promoted")
    ledger.close()
    with sqlite3.connect(root / "memory.db") as conn:
        meta = json.loads(conn.execute("SELECT meta FROM scenes WHERE id=?", (survivor_id,)).fetchone()[0])
        meta["keyframe"]["path"] = str(artifact)
        conn.execute("UPDATE scenes SET meta=? WHERE id=?", (json.dumps(meta), survivor_id))
        conn.execute("INSERT INTO ucf_provenance_mapping VALUES('scene',?,?)", (survivor_id, fid))
        conn.execute("INSERT INTO ucf_provenance_mapping VALUES('scene',?,?)", (ids[1], target_fid))
        conn.execute("INSERT INTO embeddings(hash,faiss_id,source_path,modality,scene_id,created_at,ucf_provenance) VALUES(?,?,?,'clip',?,'fixture',?)",
                     (key, to_faiss_id(key), str(artifact), ids[1], json.dumps([fid, target_fid])))
        for support in (fid, target_fid):
            conn.execute("INSERT INTO ucf_provenance_mapping VALUES('embedding',?,?)", (key, support))
    config["paths"]["clip_id_map_db"] = str(root / "clip-map.db")
    with sqlite3.connect(root / "clip-map.db") as conn:
        conn.execute("CREATE TABLE clip_id_map(hash TEXT,video_hash TEXT,epoch_id TEXT,scene_id TEXT,source_path TEXT,ucf_frame_id INTEGER)")
        conn.execute("INSERT INTO clip_id_map VALUES(?,?,?,?,?,?)", (key, scope["video_hash"], root.name, ids[1], "retired-frame.png", target_fid))
    point = {"id": point_id, "payload": {**scope, "scene_id": ids[1], "ucf_promotion_status": "promoted",
             "transcript": "Retired words", "caption": "Retired action", "people": ["retired identity"],
             "source_path": "retired-frame.png", "start": 1.0, "end": 2.0}}
    before_payload = dict(point["payload"])
    writes = []

    def response(value):
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps({"result": value}).encode()
        return result

    def post(url, *, json, **kwargs):
        if "/scroll" in url:
            # The actual scene sweep must exclude this shared ID and must bind
            # the retiring scene, even after ownership moves to another video.
            filter_ = json["filter"]
            assert {"key": "scene_id", "match": {"any": [ids[1]]}} in filter_["must"]
            assert {"has_id": [point_id]} in filter_["must_not"]
            return response({"points": [], "next_page_offset": None})
        assert url.endswith("/points") and json["ids"] == [point_id], (url, json)
        return response([point])

    def put(url, *, json, **kwargs):
        assert url.endswith("/points/payload?wait=true") and json["points"] == [point_id]
        writes.append(dict(json["payload"]))
        point["payload"] = dict(json["payload"])
        return response({"status": "completed"})

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "put", put)
    monkeypatch.setattr(requests, "get", lambda *a, **k: response({"collections": [{"name": collection}]}))
    for name in ("_sync_ucf_status_to_qdrant", "_sync_qdrant_by_scope"):
        monkeypatch.setattr(client, name, getattr(MiniAgentClient, name).__get__(client))
    if missing_artifact:
        artifact.unlink()
    result, rc = confirmed(client, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    if missing_artifact:
        assert rc == 1 and result["output"]["delivery_state"] == "pending", result
        assert "artifact is missing" in json.dumps(result)
        assert not writes and point["payload"] == before_payload
        return
    assert rc == 0, result
    assert len(writes) == 1
    assert point["payload"]["scene_id"] == survivor_id
    assert point["payload"]["video_hash"] == survivor_video
    assert point["payload"]["epoch_id"] == root.name
    assert (point["payload"]["start"], point["payload"]["end"]) == (0.0, 1.0)
    assert point["payload"]["source_path"] == str(artifact.resolve())
    assert not {"transcript", "caption", "people"}.intersection(point["payload"])
    assert point["payload"]["ucf_promotion_status"] == "promoted"
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT scene_id FROM embeddings WHERE hash=?", (key,)).fetchone() == (survivor_id,)
    with sqlite3.connect(root / "clip-map.db") as conn:
        assert conn.execute("SELECT video_hash,scene_id,ucf_frame_id FROM clip_id_map WHERE hash=?", (key,)).fetchone() == (survivor_video, survivor_id, fid)
