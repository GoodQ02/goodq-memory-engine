import sqlite3
import pytest
from pathlib import Path
from steps.common import memory
from steps.common import memory_commit_events
from steps.video import scene_visual_embeddings
from steps.video_summarizer import step as video_summarizer_step

def test_upsert_embedding_isolation(tmp_path):
    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}, "ingestion_isolation": True}
    
    # Initialize schema
    conn = memory._connect(str(db_path))
    conn.close()

    # Call upsert_embedding
    memory.upsert_embedding(cfg, "hash1", 1, "source_path", "video")

    # Assert no records exist
    conn = sqlite3.connect(str(db_path))
    try:
        # Check if embeddings table is empty or does not exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'")
        row = cursor.fetchone()
        if row:
            assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
    finally:
        conn.close()

def test_upsert_scene_and_segment_isolation(tmp_path):
    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}, "ingestion_isolation": True}
    
    conn = memory._connect(str(db_path))
    conn.close()

    # Call ID generating helpers
    scene_id = memory.upsert_scene(cfg, "video_hash", 0.0, 10.0, {"index": 1})
    segment_id = memory.upsert_segment(cfg, "video_hash", 0.0, 10.0, "speaker1")

    # Verify ID computed successfully
    assert scene_id != ""
    assert segment_id != ""

    # Assert no records written to database
    conn = sqlite3.connect(str(db_path))
    try:
        for table in ["scenes", "segments"]:
            cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone():
                assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        conn.close()

def test_register_scene_bundle_isolation(tmp_path):
    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}, "ingestion_isolation": True}
    
    conn = memory._connect(str(db_path))
    conn.close()

    res = memory.register_scene_bundle(
        cfg,
        video_hash="video_hash_1",
        scene={"start": 0.0, "end": 1.0, "index": 0},
        scene_id="scene_0000",
        audio={"path": "audio.wav", "start": 0.0, "end": 1.0, "data": {"speaker_transcript": [{"start": 0.0, "end": 1.0, "speaker": "A", "text": "hello"}]}},
    )

    # Check return values are constructed
    assert res["scene_id"] == "scene_0000"
    assert len(res["segments"]) == 1

    # Assert no database records
    conn = sqlite3.connect(str(db_path))
    try:
        for table in ["scenes", "links", "segments"]:
            cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone():
                assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        conn.close()

def test_emit_memory_commit_events_isolation(tmp_path):
    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}, "ingestion_isolation": True}
    
    conn = memory._connect(str(db_path))
    conn.close()

    event = memory_commit_events.MemoryCommitEvent(
        ts_utc="2026-06-17T12:00:00Z",
        scene_id="scene_0000",
        video_id="video1",
        modality="text",
        model="model1",
        embedding_id="embed1",
        component="test",
        targets={"qdrant": {"attempted": True, "committed": True, "ref": "col1"}},
    )

    memory_commit_events.emit_memory_commit_event(cfg, event)

    # Assert no database records
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_commit_events'")
        if cursor.fetchone():
            assert conn.execute("SELECT COUNT(*) FROM memory_commit_events").fetchone()[0] == 0
    finally:
        conn.close()

def test_write_scene_faiss_points_isolation(tmp_path):
    db_path = tmp_path / "memory.db"
    map_db = tmp_path / "sidecar.db"
    cfg = {"paths": {"db_path": str(db_path)}, "ingestion_isolation": True}
    
    # We won't pass an index path, but we test the SQLite maps bypass specifically
    res = scene_visual_embeddings._write_scene_faiss_points(
        cfg,
        points=[],
        index_path=None,
        id_map_db=str(map_db),
        map_table="clip_id_map",
        modality="clip",
        dim=512,
    )
    assert not res["committed"]

def test_video_summarizer_step_isolation(tmp_path):
    db_path = tmp_path / "memory.db"
    cfg = {"paths": {"db_path": str(db_path)}, "ingestion_isolation": True}
    
    # Initialize the entire schema
    conn = memory._connect(str(db_path))
    conn.close()

    res = video_summarizer_step.run_step(cfg, "video_hash_1")
    assert res["success"]
    assert res["video_hash"] == "video_hash_1"

    # Assert no record in summaries table
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 0
    finally:
        conn.close()
