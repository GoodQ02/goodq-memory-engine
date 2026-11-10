from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

pytest.importorskip("goodq_mini_agent")

from agents.mini_agent_client import MiniAgentClient
from scripts.ucf.ucf_ledger import UCFLedgerClient
from steps.common.memory import _make_id
from steps.video_scene_detect import step as scene_step


@pytest.fixture
def scene_promotion(tmp_path, monkeypatch):
    root = tmp_path / "epoch_scene_identity"
    config = {
        "paths": {
            "db_dir": str(root),
            "db_path": str(root / "memory.db"),
            "knowledge_graph_db": str(root / "knowledge_graph.db"),
            "processing": str(root / "processing"),
        },
        "agent": {"execution_mode": "in_process"},
    }
    monkeypatch.setenv("GOODQ_AGENT_EXECUTION_MODE", "in_process")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr("steps.common.progress_tracker.get_tracker", lambda: None)
    # Codec/scene detector are separate native dependencies. Exercise the real
    # scene worker, ledger and governed promotion caller below.
    monkeypatch.setattr(scene_step, "_detect_with_scenedetect", lambda *_: {
        "duration": 1.0,
        "scenes": [{"index": 0, "start": 0.0, "end": 1.0, "duration": 1.0, "confidence": 1.0}],
    })
    monkeypatch.setattr(scene_step, "_get_video_dimensions", lambda _: (1.0, 10.0, 64, 48))
    client = MiniAgentClient(profile="safe", config=config)
    # This fixture has no vectors; there is no external Qdrant delivery to test.
    monkeypatch.setattr(client, "_sync_ucf_status_to_qdrant", lambda *_args, **_kwargs: {
        "status": "ok", "points_attempted": 0, "points_verified": 0,
        "collections_attempted": [], "failed_collections": [],
    })
    monkeypatch.setattr(client, "_sync_qdrant_by_scope", lambda **_kwargs: {
        "status": "ok", "points_verified": 0, "failed_collections": [],
    })
    monkeypatch.setattr(client, "_execute_validate_ucf_epoch", lambda _: {"success": True, "errors": []})
    return root, config, client


def confirmed(client, name, scope):
    request, rc = client.execute_tool(name, scope)
    assert rc == 3, request
    result, rc = client.execute_tool(
        name, scope, confirm=True,
        confirmation_token=request["result"]["confirmation_token"],
    )
    return result, rc


def stage_source(root, config, name, *, legacy_alias=False, manifest=True):
    source = root.parent / f"{name}.mp4"
    source.write_bytes(name.encode())
    video_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    scene_id = _make_id("scene", [video_hash, "0.000", "1.000"])
    output = scene_step.video_scene_detect({"source_path": str(source), "video_hash": video_hash}, config)
    assert output["scene_meta"]["status"] == "ok"
    ledger_path = root / "ucf/ucf_ledger.db"
    if legacy_alias:
        with sqlite3.connect(ledger_path) as conn:
            conn.execute("UPDATE context_frames SET source_artifact_id='scene_0000' WHERE video_hash=?", (video_hash,))
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.log_frame(
        video_hash=video_hash, epoch_id=root.name, run_id="scene-identity-test",
        t_start=0.0, t_end=1.0, modality="video", worker_name="image_caption",
        model_tag="fixture", source_artifact_id=scene_id, payload={"caption": name},
    )
    ledger.close()
    if manifest:
        folder = root / "processing" / name / "video"
        folder.mkdir(parents=True)
        (folder / "scene_manifest.json").write_text(json.dumps({
            "video_hash": video_hash,
            "scenes": [{"scene_id": scene_id, "video_id": video_hash, "index": 0,
                        "start": 0.0, "end": 1.0, "duration": 1.0,
                        "keyframe": {"caption": name}, "fixture_identity": name}],
        }), encoding="utf-8")
    return video_hash, scene_id


def test_scene_worker_logs_canonical_scene_identity(scene_promotion):
    root, config, _ = scene_promotion
    video_hash, scene_id = stage_source(root, config, "video_a")
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute(
            "SELECT source_artifact_id FROM context_frames WHERE video_hash=? AND worker_name='video_scene_detect'",
            (video_hash,),
        ).fetchone() == (scene_id,)


@pytest.mark.parametrize("legacy_alias", [False, True], ids=["new-worker", "historical-alias"])
def test_two_video_worker_ledgers_promote_to_two_unique_full_scenes(scene_promotion, legacy_alias):
    root, config, client = scene_promotion
    expected = [stage_source(root, config, name, legacy_alias=legacy_alias) for name in ("video_a", "video_b")]
    for video_hash, _ in expected:
        scope = {"video_hash": video_hash, "epoch_id": root.name}
        validated, rc = confirmed(client, "validate_ucf_frames", scope)
        assert rc == 0, validated
        promoted, rc = confirmed(client, "promote_ucf_to_memory", scope)
        # This vector-free fixture deliberately cannot satisfy Qdrant delivery;
        # assess the committed local materialization without fabricating vectors.
        assert rc == 1, promoted
        assert promoted["output"]["status"] == "promotion_committed_sync_pending", promoted

    with sqlite3.connect(root / "memory.db") as conn:
        rows = conn.execute("SELECT id, video_hash, meta FROM scenes ORDER BY video_hash").fetchall()
        assert {(sid, vh) for sid, vh, _ in rows} == {(sid, vh) for vh, sid in expected}
        assert len(rows) == 2
        for sid, video_hash, raw_meta in rows:
            meta = json.loads(raw_meta)
            assert meta["scene_id"] == sid
            assert meta["video_id"] == video_hash
            assert meta["fixture_identity"] in {"video_a", "video_b"}
            assert meta["keyframe"]["caption"] == meta["fixture_identity"]
            assert len(meta["ucf_provenance"]) == 2
        assert conn.execute("SELECT COUNT(*) FROM links WHERE parent_hash='scene_0000' OR child_hash='scene_0000'").fetchone() == (0,)
        assert set(conn.execute("SELECT parent_hash, child_hash FROM links WHERE relation='scene_of'").fetchall()) == set(expected)
        assert conn.execute("SELECT COUNT(*) FROM ucf_provenance_mapping WHERE record_id='scene_0000'").fetchone() == (0,)
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='promoted'").fetchone() == (4,)
        detection_ids = {row[0] for row in conn.execute("SELECT source_artifact_id FROM context_frames WHERE worker_name='video_scene_detect'")}
        assert detection_ids == ({"scene_0000"} if legacy_alias else {sid for _, sid in expected})
    with sqlite3.connect(root / "knowledge_graph.db") as conn:
        assert {row[0] for row in conn.execute("SELECT DISTINCT scene_id FROM media_nodes WHERE scene_id IS NOT NULL")} == {sid for _, sid in expected}


@pytest.mark.parametrize("bad_manifest", ["missing", "ambiguous", "wrong_video"])
def test_unresolved_historical_alias_fails_before_materialization(scene_promotion, bad_manifest):
    root, config, client = scene_promotion
    video_hash, _ = stage_source(root, config, "video_unresolved", legacy_alias=True, manifest=bad_manifest != "missing")
    if bad_manifest != "missing":
        path = root / "processing/video_unresolved/video/scene_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if bad_manifest == "ambiguous":
            manifest["scenes"].append(dict(manifest["scenes"][0]))
        else:
            manifest["video_hash"] = "another-video"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    scope = {"video_hash": video_hash, "epoch_id": root.name}
    validated, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, validated
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0, result
    assert "scene_0000" in json.dumps(result)
    assert not (root / "memory.db").exists()
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='validated'").fetchone() == (2,)
