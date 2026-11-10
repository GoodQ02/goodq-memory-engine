from __future__ import annotations

import json
import sqlite3
import uuid

import numpy as np
import pytest


pytest.importorskip(
    "goodq_mini_agent",
    reason="goodq_mini_agent is an optional private policy-engine integration",
)

from agents.mini_agent_client import MiniAgentClient
from scripts.ucf.ucf_ledger import UCFLedgerClient
from steps.common.memory import _connect, to_faiss_id


@pytest.fixture
def promotion(tmp_path, monkeypatch):
    epoch_root = tmp_path / "epochs" / "epoch_faiss_mapping"
    ledger_path = epoch_root / "ucf" / "ucf_ledger.db"
    ledger_path.parent.mkdir(parents=True)
    config = {
        "paths": {
            "db_dir": str(epoch_root),
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
            "processing": str(epoch_root / "processing"),
        },
        "agent": {"execution_mode": "in_process"},
    }
    monkeypatch.setenv("GOODQ_AGENT_EXECUTION_MODE", "in_process")
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.register_media(
        video_hash="video_faiss_mapping",
        file_path="fixture.mp4",
        duration=1.0,
        fps=30.0,
        width=640,
        height=480,
    )
    client = MiniAgentClient(profile="safe", config=config)
    fetched = []

    def fetch_vector(collection, vector_key):
        fetched.append((collection, vector_key))
        if collection in {"fixture_clip", "fixture_dino"}:
            return [0.25] * (768 if collection == "fixture_clip" else 1024)
        return [0.25, 0.5, 0.75]

    monkeypatch.setattr(client, "_fetch_vector_from_qdrant", fetch_vector)
    monkeypatch.setattr(
        client,
        "_sync_ucf_status_to_qdrant",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "points_attempted": 1,
            "points_verified": 1,
            "collections_attempted": ["fixture_text"],
            "failed_collections": [],
        },
    )
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_kwargs: {
            "status": "ok",
            "points_verified": 1,
            "failed_collections": [],
        },
    )
    monkeypatch.setattr(
        client,
        "_execute_validate_ucf_epoch",
        lambda _args: {"success": True, "errors": []},
    )

    def dispatch(vector_key, payload, *, visual_frames=()):
        records = visual_frames or [(vector_key, payload, "text", "text_embed", "fixture_text", 3)]
        frame_ids = []
        for key, frame_payload, modality, worker, collection, dimension in records:
            frame_ids.append(ledger.log_frame(
                video_hash="video_faiss_mapping",
                epoch_id="epoch_faiss_mapping",
                run_id="run_faiss_mapping",
                t_start=0.0,
                t_end=1.0,
                modality=modality,
                worker_name=worker,
                model_tag="fixture/model",
                vector_key=key,
                vector_backend="qdrant",
                vector_collection=collection,
                vector_dim=dimension,
                source_artifact_id="scene_faiss_mapping",
                payload=frame_payload,
                promotion_status="validated",
            ))
        args = {
            "video_hash": "video_faiss_mapping",
            "epoch_id": "epoch_faiss_mapping",
        }
        envelope, rc = client.execute_tool(
            tool_name="promote_ucf_to_memory", tool_args=args
        )
        assert rc == 3, envelope
        envelope, rc = client.execute_tool(
            tool_name="promote_ucf_to_memory",
            tool_args=args,
            confirm=True,
            confirmation_token=envelope["result"]["confirmation_token"],
        )
        assert rc == 0, envelope
        assert envelope["output"]["status"] == "promoted_complete", envelope
        assert envelope["output"]["promoted_count"] == len(records)
        assert sorted(fetched) == sorted((record[4], record[0]) for record in records)
        with sqlite3.connect(ledger_path) as conn:
            for frame_id in frame_ids:
                assert conn.execute(
                    "SELECT promotion_status FROM context_frames WHERE frame_id = ?",
                    (frame_id,),
                ).fetchone() == ("promoted",)
        return frame_ids if visual_frames else frame_ids[0]

    yield config, dispatch
    ledger.close()


@pytest.mark.parametrize("id_kind", ["normalized_summary", "raw_frame", "legacy"])
def test_confirmed_promotion_maps_original_faiss_id(promotion, id_kind):
    config, dispatch = promotion
    embedding_id = "scene_faiss_mapping_summary"
    vector_key = embedding_id
    if id_kind == "normalized_summary":
        vector_key = str(
            uuid.uuid5(
                uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4"), embedding_id
            )
        )
        assert to_faiss_id(vector_key) != to_faiss_id(embedding_id)
    payload = {"embedding_id": embedding_id} if id_kind != "legacy" else {}
    frame_id = dispatch(vector_key, payload)

    with sqlite3.connect(config["paths"]["db_path"]) as conn:
        row = conn.execute(
            "SELECT hash, faiss_id, modality, scene_id, ucf_provenance "
            "FROM embeddings"
        ).fetchone()
        assert row[:4] == (
            vector_key,
            to_faiss_id(embedding_id),
            "text",
            "scene_faiss_mapping",
        )
        assert json.loads(row[4]) == [frame_id]
        assert conn.execute(
            "SELECT record_id, ucf_frame_id FROM ucf_provenance_mapping "
            "WHERE record_type = 'embedding'"
        ).fetchall() == [(vector_key, frame_id)]


def test_confirmed_promotion_keeps_clip_and_dino_for_the_same_image(promotion):
    config, dispatch = promotion
    records = [
        ("shared_image_hash", {}, "video", "image_embed_clip", "fixture_clip", 768),
        ("shared_image_hash", {}, "video", "image_embed_dino", "fixture_dino", 1024),
        ("pooled_clip", {"embedding_id": "clip_scene_0"}, "multimodal", "scene_visual_embeddings_clip", "fixture_clip", 768),
        ("pooled_dino", {"embedding_id": "dino_scene_0"}, "multimodal", "scene_visual_embeddings_dino", "fixture_dino", 1024),
    ]
    frame_ids = dispatch(None, {}, visual_frames=records)
    with sqlite3.connect(config["paths"]["db_path"]) as conn:
        rows = conn.execute(
            "SELECT hash,modality,faiss_id,vector,ucf_provenance FROM embeddings"
        ).fetchall()
        assert len(rows) == 4
        by_key = {(row[0], row[1]): row for row in rows}
        for record, frame_id in zip(records, frame_ids):
            key, payload, _, _, collection, dimension = record
            row = by_key[(key, collection.removeprefix("fixture_"))]
            assert row[2] == to_faiss_id(payload.get("embedding_id", key))
            np.testing.assert_array_equal(np.frombuffer(row[3], dtype=np.float32), [0.25] * dimension)
            assert json.loads(row[4]) == [frame_id]
        assert conn.execute(
            "SELECT count(*) FROM ucf_provenance_mapping WHERE record_type='embedding'"
        ).fetchone() == (4,)


def test_confirmed_promotion_preserves_existing_embedding_metadata(promotion):
    config, dispatch = promotion
    vector_key = "frame_embedding"
    conn = _connect(config["paths"]["db_path"])
    with conn:
        conn.execute(
            "INSERT INTO embeddings(hash, faiss_id, source_path, modality, "
            "scene_id, created_at, sentiment_label, sentiment_score, vector) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                vector_key,
                to_faiss_id(vector_key),
                "fixture/frame_001.jpg",
                "text",
                "scene_faiss_mapping",
                "2026-01-01T00:00:00",
                "positive",
                0.8,
                np.array([0.0, 0.0, 1.0], dtype=np.float32).tobytes(),
            ),
        )
        conn.execute(
            "INSERT INTO embeddings(hash, faiss_id, source_path, modality) "
            "VALUES (?, ?, ?, ?)",
            (vector_key, 123, "fixture/frame_001.png", "image"),
        )
    conn.close()

    frame_id = dispatch(vector_key, {"embedding_id": vector_key})

    with sqlite3.connect(config["paths"]["db_path"]) as conn:
        row = conn.execute(
            "SELECT source_path, created_at, sentiment_label, sentiment_score, "
            "vector, ucf_provenance FROM embeddings WHERE hash = ? AND modality = ?",
            (vector_key, "text"),
        ).fetchone()
        assert row[:4] == (
            "fixture/frame_001.jpg",
            "2026-01-01T00:00:00",
            "positive",
            0.8,
        )
        np.testing.assert_array_equal(
            np.frombuffer(row[4], dtype=np.float32), [0.25, 0.5, 0.75]
        )
        assert json.loads(row[5]) == [frame_id]
        assert conn.execute(
            "SELECT faiss_id, source_path FROM embeddings "
            "WHERE hash = ? AND modality = 'image'",
            (vector_key,),
        ).fetchone() == (123, "fixture/frame_001.png")
