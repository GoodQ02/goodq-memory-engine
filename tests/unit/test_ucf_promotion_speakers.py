"""Governed promotion consumes retained voice evidence, without inference."""
import json
import sqlite3

from tests.unit.test_ucf_promotion_scene_identity import scene_promotion, stage_source, confirmed
from scripts.ucf.ucf_ledger import UCFLedgerClient


def stage_voice(root, cfg, client, name, labels=("speaker_01",), *, turns=True):
    video, scene = stage_source(root, cfg, name)
    path = root / "processing" / name / "video/scene_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["scenes"][0]["audio"] = {
        "speakers": list(labels),
        "diarization": [{"speaker": label, "start": 0., "end": 1.} for label in labels],
        "speaker_voice_signatures": [{"speaker": label, "embedding": [1., 0.],
                                      "voiced_seconds": 4., "segment_count": 2} for label in labels],
        "speaker_change_review": {"status": "unreviewed", "flags": [{"identity_claim": False}]},
        "entities": [{"name": "Kathy", "type": "PERSON"}],
    }
    path.write_text(json.dumps(manifest))
    if turns:
        ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
        for label in labels:
            ledger.log_frame(video_hash=video, epoch_id=root.name, run_id="voice-projection",
                t_start=0., t_end=1., modality="audio", worker_name="speaker_merge",
                model_tag="fixture", source_artifact_id=scene, payload={"speaker_id": label})
        ledger.close()
    scope = {"video_hash": video, "epoch_id": root.name}
    result, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, result
    return scope, scene, path


def prepare(fixture, name, **kwargs):
    root, cfg, client = fixture
    return stage_voice(root, cfg, client, name, **kwargs)


def graph(root):
    with sqlite3.connect(root / "knowledge_graph.db") as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                for table in ("nodes", "edges", "node_media", "media_nodes")}


def test_governed_promotion_recurrence_replay_and_review_boundary(scene_promotion):
    root, cfg, client = scene_promotion
    a, scene_a, _ = prepare(scene_promotion, "a", labels=("speaker_01", "speaker_02", "Kathy"))
    b, scene_b, _ = prepare(scene_promotion, "b", labels=("speaker_04",))
    for scope in (a, b):
        result, _ = confirmed(client, "promote_ucf_to_memory", scope)
        assert "materialization_report" in result["output"], result
    with sqlite3.connect(root / "knowledge_graph.db") as db:
        assert db.execute("SELECT count(*) FROM nodes WHERE node_type='speaker_pattern'").fetchone() == (2,)
        assert db.execute("SELECT count(*) FROM nodes WHERE node_type='person'").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM edges WHERE edge_type LIKE 'identity_%'").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM edges WHERE edge_type='voice_pattern_match'").fetchone() == (3,)
        before = db.execute("SELECT * FROM nodes WHERE node_type='speaker_pattern' ORDER BY id").fetchall()
        review = json.loads(db.execute("SELECT properties FROM nodes WHERE node_type='scene' AND name=?", (scene_a,)).fetchone()[0])
        assert review["speaker_change_review"]["flags"]
        assert review["ucf_provenance"]
    result, _ = confirmed(client, "promote_ucf_to_memory", a)
    with sqlite3.connect(root / "knowledge_graph.db") as db:
        assert db.execute("SELECT * FROM nodes WHERE node_type='speaker_pattern' ORDER BY id").fetchall() == before
        assert db.execute("SELECT count(*) FROM edges WHERE edge_type='voice_pattern_match'").fetchone() == (3,)


def test_manifest_voice_without_promoted_turns_is_not_projected(scene_promotion):
    root, _, client = scene_promotion
    scope, _, _ = prepare(scene_promotion, "a", turns=False)
    confirmed(client, "promote_ucf_to_memory", scope)
    with sqlite3.connect(root / "knowledge_graph.db") as db:
        assert db.execute("SELECT count(*) FROM nodes WHERE node_type IN ('speaker','speaker_pattern')").fetchone() == (0,)


def test_changed_replay_fails_before_existing_views_are_touched(scene_promotion):
    root, _, client = scene_promotion
    scope, _, path = prepare(scene_promotion, "a")
    confirmed(client, "promote_ucf_to_memory", scope)
    before = graph(root)
    data = json.loads(path.read_text())
    data["scenes"][0]["audio"]["speaker_voice_signatures"][0]["embedding"] = [0., 1.]
    path.write_text(json.dumps(data))
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "explicit reconciliation required" in json.dumps(result)
    assert graph(root) == before


def test_projection_failure_rolls_back_patterns_and_ledger(scene_promotion, monkeypatch):
    import lib.kg_realtime_integration as projection
    root, _, client = scene_promotion
    scope, _, _ = prepare(scene_promotion, "a", labels=("speaker_01", "speaker_02"))
    original = projection._upsert_speaker_pattern_node
    def fail_second(*args, **kwargs):
        if kwargs["speaker_label"].lower() == "speaker_02":
            raise RuntimeError("injected second-pattern failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(projection, "_upsert_speaker_pattern_node", fail_second)
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "injected second-pattern failure" in json.dumps(result)
    with sqlite3.connect(root / "knowledge_graph.db") as db:
        assert db.execute("SELECT count(*) FROM nodes WHERE node_type='speaker_pattern'").fetchone() == (0,)
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as db:
        assert db.execute("SELECT count(*) FROM context_frames WHERE promotion_status='promoted'").fetchone() == (0,)


def test_completed_delivery_replay_reuses_receipt_without_qdrant_writes(scene_promotion, monkeypatch):
    root, _, client = scene_promotion
    scope, _, _ = prepare(scene_promotion, "a")
    confirmed(client, "promote_ucf_to_memory", scope)
    # Model an already verified delivery receipt, independently of transport.
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as db:
        db.execute("UPDATE ucf_qdrant_sync_outbox SET delivery_state='complete'")
    def unexpected(**kwargs):
        raise AssertionError("Replay must not deliver an already completed obligation")
    monkeypatch.setattr(client, "_deliver_pending_promotion_qdrant_sync", unexpected)
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc == 0, result
    assert result["output"]["status"] == "promoted_complete"
    assert result["output"]["promoted_count"] == 0
    assert result["output"]["qdrant_sync"]["attempted"] is False


def test_stitch_preview_reads_committed_wal_without_checkpoint(tmp_path, monkeypatch):
    from lib.knowledge_graph import KnowledgeGraph
    from api.routes import system
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority
    db = tmp_path / "live.db"
    monkeypatch.setattr(system, "_get_kg_db_path", lambda: db)
    app = FastAPI()
    operation = ("POST", "/api/system/identity/stitch/preview")
    app.router.routes.extend(r for r in system.router.routes if r.path == operation[1])
    install_route_effect_authority(app, registry={operation: ROUTE_EFFECTS[operation]})
    with KnowledgeGraph(str(db)) as writer:
        writer.conn.execute("PRAGMA wal_autocheckpoint=0")
        writer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.add_node("speaker_pattern", "wal_pattern", {})
        with TestClient(app, client=("127.0.0.1", 50000)) as http:
            response = http.post(operation[1], json={"source_node_name": "wal_pattern", "target_person_name": "Kathy"})
        assert response.status_code == 200, response.text
        with KnowledgeGraph(str(db), read_only=True, read_live_wal=True) as reader:
            import pytest
            with pytest.raises(sqlite3.OperationalError):
                reader.conn.execute("DELETE FROM nodes")
