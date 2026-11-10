"""Real governed promotion/retirement with only native compute and transport faked."""

import json
import sqlite3
import uuid

import pytest
import requests

pytest.importorskip("goodq_mini_agent")

from scripts.ucf.ucf_ledger import UCFLedgerClient
from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
from steps.video_summarizer.step import _load_target_scene_summary_records
from tests.unit.test_ucf_promotion_scene_identity import (
    confirmed,
    scene_promotion,
    stage_source,
)


@pytest.fixture
def points(monkeypatch):
    stored = {}

    def point_request(url, *, json, **kwargs):
        assert url.endswith("/points"), url
        response = requests.Response()
        response.status_code = 200
        response._content = __import__("json").dumps({
            "result": [stored[key] for key in json["ids"] if key in stored],
        }).encode()
        return response

    monkeypatch.setattr(requests, "post", point_request)
    return stored


def stage_summary(root, video_hash, scene_id, text, points):
    key = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, f"{scene_id}_summary"))
    collection = f"goodq_text_{root.name}"
    raw = root / f"{scene_id}_raw_summary.json"
    # Current production raw refs contain vector identity, not summary text.
    raw.write_text(json.dumps({
        "embedding_id": f"{scene_id}_summary", "embedding_source": "scene_summary",
        "engine": "all-MiniLM-L6-v2", "qdrant_collection": collection,
    }), encoding="utf-8")
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    frame_id = ledger.log_frame(
        video_hash=video_hash, epoch_id=root.name, run_id="summary-probe",
        t_start=0.0, t_end=1.0, modality="text", worker_name="scene_summary_embed",
        model_tag="sentence-transformers/all-MiniLM-L6-v2", source_artifact_id=scene_id,
        raw_ref=str(raw), payload={"embedding_id": f"{scene_id}_summary",
                                  "embedding_source": "scene_summary", "origin_modality": "scene_summary"},
        vector_key=key, vector_backend="qdrant", vector_dim=384,
        vector_model_tag="sentence-transformers/all-MiniLM-L6-v2", vector_collection=collection,
    )
    ledger.close()
    points[key] = {"id": key, "vector": [0.5] * 384, "payload": {
        "video_hash": video_hash, "video_id": video_hash, "scene_id": scene_id,
        "scene_hash": key, "start": 0.0, "end": 1.0, "text": text,
        "embedding_source": "scene_summary", "worker_name": "scene_summary_embed",
        "modality": "text", "ucf_frame_id": frame_id, "ucf_promotion_status": "staged",
    }}
    return key, frame_id


def promote(client, root, video_hash):
    scope = {"video_hash": video_hash, "epoch_id": root.name}
    result, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, result
    result, _ = confirmed(client, "promote_ucf_to_memory", scope)
    assert result["output"]["status"] in {"promotion_committed_sync_pending", "promoted_complete"}, result
    return result


def test_promotion_materializes_exact_summary_once_for_video_consumer(scene_promotion, points):
    root, config, client = scene_promotion
    config["ingestion_isolation"] = True
    target = stage_source(root, config, "summary_a")
    other = stage_source(root, config, "summary_b")
    text = " Exact source A summary.\n"
    _, fid = stage_summary(root, *target, text, points)
    stage_summary(root, *other, "Different source B summary.", points)

    promote(client, root, target[0])
    with sqlite3.connect(root / "memory.db") as conn:
        original_id, created_at = conn.execute("SELECT id,created_at FROM summaries").fetchone()
        conn.execute("INSERT INTO summaries(summary_type,category,content,created_at) VALUES('long_term','scene_summary',?,'duplicate')",
                     (json.dumps({"scene_id": target[1], "summary": "old duplicate"}),))
    promote(client, root, target[0])
    with sqlite3.connect(root / "memory.db") as conn:
        rows = conn.execute("SELECT id, summary_type, category, content FROM summaries").fetchall()
        provenance = conn.execute(
            "SELECT record_id,ucf_frame_id FROM ucf_provenance_mapping WHERE record_type='summary'",
        ).fetchall()
        assert conn.execute("SELECT created_at FROM summaries").fetchone() == (created_at,)
    assert len(rows) == 1
    assert rows[0][:3] == (original_id, "long_term", "scene_summary")
    assert json.loads(rows[0][3]) == {
        "scene_id": target[1], "summary": text, "index": 0,
        "start": 0.0, "end": 1.0, "duration": 1.0,
    }
    assert provenance == [(str(original_id), fid)]
    records = _load_target_scene_summary_records(str(root / "memory.db"), target[0])
    assert len(records) == 1 and records[0]["summary"] == text
    assert _load_target_scene_summary_records(str(root / "memory.db"), other[0]) == []


def test_supersede_removes_only_target_active_scene_summary(scene_promotion, points):
    root, config, client = scene_promotion
    target = stage_source(root, config, "retire_a")
    other = stage_source(root, config, "retain_b")
    for video_hash, scene_id in (target, other):
        stage_summary(root, video_hash, scene_id, scene_id, points)
        promote(client, root, video_hash)
    with sqlite3.connect(root / "memory.db") as conn:
        retained_id = conn.execute("SELECT id FROM summaries ORDER BY id DESC LIMIT 1").fetchone()[0]
        # Existing rows without provenance must retire too; unrelated/malformed
        # historical summaries must not prevent the scoped lifecycle action.
        for category, content in [
            ("scene_summary", json.dumps({"scene_id": target[1], "summary": "legacy duplicate"})),
            ("daily", "{}"), ("scene_summary", "not json"),
            ("scene_summary", '{"scene_id": null}'),
        ]:
            conn.execute("INSERT INTO summaries(summary_type,category,content,created_at) VALUES('long_term',?,?,'fixture')",
                         (category, content))
    result, rc = confirmed(client, "supersede_ucf_frames", {"video_hash": target[0], "epoch_id": root.name})
    assert rc == 0, result
    with sqlite3.connect(root / "memory.db") as conn:
        rows = conn.execute("SELECT category,content FROM summaries").fetchall()
        provenance = conn.execute("SELECT record_id FROM ucf_provenance_mapping WHERE record_type='summary'").fetchall()
    assert len(rows) == 4
    assert all(target[1] not in content for _, content in rows)
    assert provenance == [(str(retained_id),)]
    assert _load_target_scene_summary_records(str(root / "memory.db"), target[0]) == []
    assert _load_target_scene_summary_records(str(root / "memory.db"), other[0])[0]["summary"] == other[1]


def test_failed_retry_preserves_already_promoted_summary(scene_promotion, points):
    root, config, client = scene_promotion
    target = stage_source(root, config, "retry_summary")
    key, _ = stage_summary(root, *target, "Original promoted text", points)
    promote(client, root, target[0])
    with sqlite3.connect(root / "memory.db") as conn:
        before = conn.execute("SELECT * FROM summaries").fetchall()
    points[key]["payload"]["video_hash"] = "wrong-source"
    result, rc = confirmed(client, "promote_ucf_to_memory", {"video_hash": target[0], "epoch_id": root.name})
    assert rc != 0 and "Scene summary payload identity mismatch" in json.dumps(result)
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT * FROM summaries").fetchall() == before
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='promoted'").fetchone() == (3,)


def test_supersede_retires_exact_source_video_summary_projection(scene_promotion):
    root, config, client = scene_promotion
    target = stage_source(root, config, "retire_video_summary")
    other = stage_source(root, config, "retain_video_summary")
    for video_hash, _ in (target, other):
        promote(client, root, video_hash)
    with sqlite3.connect(root / "memory.db") as conn:
        for video_hash, _ in (target, other):
            content = json.dumps({"video_hash": video_hash, "summary": "Stored video summary",
                                  "method": "template", "provenance": {"scene_ids": []}})
            conn.execute("INSERT INTO summaries(summary_type,category,content,created_at) VALUES('video','video_summary',?,'fixture')",
                         (content,))
        conn.execute("INSERT INTO summaries(summary_type,category,content,created_at) VALUES('long_term','daily',?,'fixture')",
                     (json.dumps({"video_hash": target[0], "summary": "Unrelated category"}),))
    result, rc = confirmed(client, "supersede_ucf_frames", {"video_hash": target[0], "epoch_id": root.name})
    assert rc == 0, result
    with sqlite3.connect(root / "memory.db") as conn:
        rows = conn.execute("SELECT category,content FROM summaries").fetchall()
    assert {(category, json.loads(content)["video_hash"]) for category, content in rows} == {
        ("video_summary", other[0]), ("daily", target[0]),
    }


def test_post_write_failure_rolls_back_summary_and_ucf_promotion(scene_promotion, points, monkeypatch):
    root, config, client = scene_promotion
    target = stage_source(root, config, "rollback_summary")
    stage_summary(root, *target, "Must not remain active", points)
    scope = {"video_hash": target[0], "epoch_id": root.name}
    result, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, result

    class FailingKnowledgeGraph:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("forced post-write materialization failure")

    monkeypatch.setattr("lib.knowledge_graph.KnowledgeGraph", FailingKnowledgeGraph)
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "forced post-write materialization failure" in json.dumps(result)
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM summaries").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM scenes").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM ucf_provenance_mapping WHERE record_type='summary'").fetchone() == (0,)
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='validated'").fetchone() == (3,)


@pytest.mark.parametrize("field,value", [
    ("video_hash", "another-source"), ("video_id", "another-source"),
    ("scene_id", "another-scene"), ("scene_hash", "another-point"),
    ("epoch_id", "another-epoch"), ("worker_name", "ocr"),
    ("embedding_source", "ocr"), ("ucf_frame_id", -1),
    ("ucf_promotion_status", "superseded"), ("ucf_promotion_status", None),
    ("start", -1.0), ("end", 2.0), ("end", True), ("end", float("nan")),
    ("text", ""), ("text", None),
])
def test_wrong_summary_evidence_refuses_before_materialization(scene_promotion, points, field, value):
    root, config, client = scene_promotion
    target = stage_source(root, config, "wrong_summary")
    key, _ = stage_summary(root, *target, "Exact text", points)
    points[key]["payload"][field] = value
    assert_refused_without_active_writes(client, root, target)


@pytest.mark.parametrize("bad_point", ["absent", "wrong_id", "missing_payload", "manifest_bounds"])
def test_missing_or_incompatible_summary_refuses_before_materialization(scene_promotion, points, bad_point):
    root, config, client = scene_promotion
    target = stage_source(root, config, "missing_summary")
    key, _ = stage_summary(root, *target, "Exact text", points)
    if bad_point == "absent":
        points.clear()
    elif bad_point == "wrong_id":
        points[key]["id"] = "another-point"
    elif bad_point == "missing_payload":
        points[key].pop("payload")
    else:
        path = root / "processing/missing_summary/video/scene_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["scenes"][0]["end"] = 2.0
        path.write_text(json.dumps(manifest), encoding="utf-8")
    assert_refused_without_active_writes(client, root, target)


def assert_refused_without_active_writes(client, root, target):
    scope = {"video_hash": target[0], "epoch_id": root.name}
    validated, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, validated
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "Scene summary" in json.dumps(result), result
    assert not (root / "memory.db").exists()
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='validated'").fetchone() == (3,)
        assert conn.execute("SELECT COUNT(*) FROM context_frames WHERE promotion_status='promoted'").fetchone() == (0,)
