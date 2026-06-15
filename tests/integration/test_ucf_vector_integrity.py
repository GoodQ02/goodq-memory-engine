#!/usr/bin/env python3
"""
Integration test suite for UCF Phase 0.7 Vector Reference Integrity Gate.
Verifies vector registry schema, key format validation, live Qdrant payload verification,
FAISS sidecar map checking, and scoped orphan detection.
"""

import sys
import os
import json
import sqlite3
import hashlib
import pytest
import requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cli.run_ingestion import _load_ucf_ledger
from scripts.ucf.validate_ucf_epoch import run_validation


@pytest.fixture
def setup_validator_env(tmp_path, monkeypatch):
    """Sets up a mock UCF ledger and config environment."""
    cfg_json = tmp_path / "cfg.json"
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    
    # Mock config data
    cfg_data = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path),
            "faiss_clip_path": str(tmp_path / "faiss_clip.index"),
            "faiss_dino_path": str(tmp_path / "faiss_dino.index"),
            "clip_id_map_db": str(tmp_path / "clip_id_map.sqlite"),
            "dino_id_map_db": str(tmp_path / "dino_id_map.sqlite"),
            "processing": str(tmp_path / "processing")
        },
        "qdrant": {
            "collections": {
                "clip": "test_clip_col",
                "dino": "test_dino_col"
            },
            "embedding_dims": {
                "clip": 768,
                "dino": 1024
            },
            "host": "http://mock_qdrant:6333"
        }
    }
    cfg_json.write_text(json.dumps(cfg_data), encoding="utf-8")
    
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    
    # Monkeypatch config loader
    import scripts.ucf.validate_ucf_epoch
    monkeypatch.setattr(scripts.ucf.validate_ucf_epoch, "load_configs", lambda x: cfg_data)
    
    # Initialize UCF DB path
    expected_db_dir = tmp_path / "epochs" / "db" / "ucf"
    expected_db_dir.mkdir(parents=True)
    ucf_db_path = expected_db_dir / "ucf_ledger.db"
    
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    client.init_schema()
    
    # Register mock video
    video_hash = "mock_video_hash_123"
    client.register_media(
        video_hash=video_hash,
        file_path="mock_video.mp4",
        duration=60.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    client.close()
    
    # Create raw_ref dummy file
    raw_ref_file = tmp_path / "mock_ref.json"
    raw_ref_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    
    return {
        "tmp_path": tmp_path,
        "ucf_db_path": ucf_db_path,
        "video_hash": video_hash,
        "cfg_data": cfg_data,
        "raw_ref_str": str(raw_ref_file.resolve())
    }


def test_offline_validation_failures(setup_validator_env):
    """Verifies that offline validation correctly flags malformed schema, dims, or collections."""
    ucf_db_path = setup_validator_env["ucf_db_path"]
    video_hash = setup_validator_env["video_hash"]
    raw_ref_str = setup_validator_env["raw_ref_str"]
    
    # Helper to insert and test a row
    def test_log_row(vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag, modality="video", worker_name="image_embed_clip"):
        conn = sqlite3.connect(str(ucf_db_path))
        conn.execute("DELETE FROM context_frames")
        conn.commit()
        
        payload_dict = {"faiss_id": 12345}
        payload_str = json.dumps(payload_dict)
        canonical_str = json.dumps(payload_dict, sort_keys=True)
        payload_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        
        # Manually insert into context_frames to allow custom malformed values bypassing Pydantic
        conn.execute(
            """
            INSERT INTO context_frames (
                video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
                modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
                vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
                source_artifact_id, raw_ref, payload, payload_hash, promotion_status
            ) VALUES (?, 'ucf.v0.1', 'db', 'run_1', 1.0, 2.0, ?, ?, ?, 1.0, NULL, 'normalized_yxyx_top_left', ?, ?, ?, ?, ?, 'scene_0001', ?, ?, ?, 'staged')
            """,
            (video_hash, modality, worker_name, vector_model_tag, vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag, raw_ref_str, payload_str, payload_hash)
        )
        conn.commit()
        conn.close()
        
        return run_validation(mode="offline")

    # 1. Valid CLIP key (SHA-256) -> Should pass
    code = test_log_row("a" * 64, "qdrant", "test_clip_col", 768, "openai/clip-vit-large-patch14")
    assert code == 0
    
    # 2. Malformed key format (not UUID or 64-hex SHA-256) -> Should fail
    code = test_log_row("not_a_hash", "qdrant", "test_clip_col", 768, "openai/clip-vit-large-patch14")
    assert code == 1
    
    # 3. Mismatched dimension (768 expected, got 1024) -> Should fail
    code = test_log_row("a" * 64, "qdrant", "test_clip_col", 1024, "openai/clip-vit-large-patch14")
    assert code == 1
    
    # 4. Mismatched collection (test_dino_col used for CLIP) -> Should fail
    code = test_log_row("a" * 64, "qdrant", "test_dino_col", 768, "openai/clip-vit-large-patch14")
    assert code == 1

    # 5. Mismatched modality (expected video, got text) -> Should fail
    code = test_log_row("a" * 64, "qdrant", "test_clip_col", 768, "openai/clip-vit-large-patch14", modality="text")
    assert code == 1


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self):
        return self.json_data


def test_online_validation_qdrant(setup_validator_env, monkeypatch):
    """Verifies that online/strict modes connect to Qdrant, check payloads, and find orphans."""
    ucf_db_path = setup_validator_env["ucf_db_path"]
    video_hash = setup_validator_env["video_hash"]
    raw_ref_str = setup_validator_env["raw_ref_str"]
    
    # Helper to insert a valid row
    conn = sqlite3.connect(str(ucf_db_path))
    payload_dict = {"faiss_id": 12345}
    payload_str = json.dumps(payload_dict)
    canonical_str = json.dumps(payload_dict, sort_keys=True)
    payload_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    
    conn.execute(
        """
        INSERT INTO context_frames (
            video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
            modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
            vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
            source_artifact_id, raw_ref, payload, payload_hash, promotion_status
        ) VALUES (?, 'ucf.v0.1', 'db', 'run_1', 1.0, 2.0, 'video', 'image_embed_clip', 'openai/clip-vit-large-patch14', 1.0, NULL, 'normalized_yxyx_top_left', ?, 'qdrant', 'test_clip_col', 768, 'openai/clip-vit-large-patch14', 'scene_0001', ?, ?, ?, 'staged')
        """,
        (video_hash, "a" * 64, raw_ref_str, payload_str, payload_hash)
    )
    conn.commit()
    conn.close()

    # Case A: Qdrant point exists with correct payload -> Pass
    qdrant_points = {
        "a" * 64: {
            "video_id": video_hash,
            "scene_id": "scene_0001",
            "modality": "clip",
            "model": "clip"
        }
    }
    
    def mock_post(url, json, timeout=None):
        from scripts.ucf.validate_ucf_epoch import normalize_qdrant_id
        normalized_a = normalize_qdrant_id("a" * 64)
        if "scroll" in url:
            pts = []
            if "test_clip_col" in url and "a" * 64 in qdrant_points:
                pts.append({"id": normalized_a, "payload": qdrant_points["a" * 64]})
            return MockResponse({"result": {"points": pts, "next_page_offset": None}}, 200)
        else:
            retrieved = []
            for pid in json.get("ids", []):
                if pid == normalized_a and "a" * 64 in qdrant_points:
                    retrieved.append({"id": pid, "payload": qdrant_points["a" * 64]})
                elif pid in qdrant_points:
                    retrieved.append({"id": pid, "payload": qdrant_points[pid]})
            return MockResponse({"result": retrieved}, 200)
            
    monkeypatch.setattr(requests, "post", mock_post)
    
    code = run_validation(mode="online")
    assert code == 0

    # In strict mode: should fail because the payload is missing epoch_id, scene_hash, and ucf_frame_id
    code = run_validation(mode="strict")
    assert code == 1

    # Now provide the complete standardized payload
    qdrant_points["a" * 64] = {
        "epoch_id": "db",
        "video_hash": video_hash,
        "scene_id": "scene_0001",
        "scene_hash": "a" * 64,
        "worker_name": "image_embed_clip",
        "vector_model_tag": "openai/clip-vit-large-patch14",
        "modality": "video",
        "ucf_frame_id": 1,
        "source_path": "mock_video.mp4",
        "faiss_id": 12345
    }

    # Strict mode: should pass now with standardized payload!
    code = run_validation(mode="strict")
    assert code == 0

    # Case B: Qdrant point video_id mismatched -> Fail
    qdrant_points["a" * 64]["video_hash"] = "wrong_video_hash"
    qdrant_points["a" * 64]["video_id"] = "wrong_video_hash"
    code = run_validation(mode="online")
    assert code == 1
    
    # Reset video_id / video_hash
    qdrant_points["a" * 64]["video_hash"] = video_hash
    qdrant_points["a" * 64]["video_id"] = video_hash

    # Case C: Qdrant point missing -> Fail
    qdrant_points.clear()
    code = run_validation(mode="online")
    assert code == 1

    # Case D: Qdrant connection error -> Warn in online, Fail in strict
    def mock_post_error(url, json, timeout=None):
        raise requests.exceptions.ConnectionError("Mocked Qdrant down")
        
    monkeypatch.setattr(requests, "post", mock_post_error)
    
    # Online mode: should print warning but return 0 (passed since connection warning is non-fatal)
    code = run_validation(mode="online")
    assert code == 0
    
    # Strict mode: should fail since backend is down
    code = run_validation(mode="strict")
    assert code == 1


def test_online_validation_faiss(setup_validator_env, monkeypatch):
    """Verifies FAISS index checking, SQLite sidecar matching, and scoped orphans."""
    ucf_db_path = setup_validator_env["ucf_db_path"]
    video_hash = setup_validator_env["video_hash"]
    raw_ref_str = setup_validator_env["raw_ref_str"]
    tmp_path = setup_validator_env["tmp_path"]
    cfg_data = setup_validator_env["cfg_data"]

    faiss_index_path = Path(cfg_data["paths"]["faiss_clip_path"])
    sidecar_db_path = Path(cfg_data["paths"]["clip_id_map_db"])

    # Make sure parent directory of index exists
    faiss_index_path.parent.mkdir(parents=True, exist_ok=True)

    # Insert a FAISS backend row into ledger
    conn = sqlite3.connect(str(ucf_db_path))
    payload_dict = {"faiss_id": 999}
    payload_str = json.dumps(payload_dict)
    canonical_str = json.dumps(payload_dict, sort_keys=True)
    payload_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    
    conn.execute("DELETE FROM context_frames")
    conn.execute(
        """
        INSERT INTO context_frames (
            video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
            modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
            vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
            source_artifact_id, raw_ref, payload, payload_hash, promotion_status
        ) VALUES (?, 'ucf.v0.1', 'db', 'run_1', 1.0, 2.0, 'video', 'image_embed_clip', 'openai/clip-vit-large-patch14', 1.0, NULL, 'normalized_yxyx_top_left', ?, 'faiss', 'test_clip_col', 768, 'openai/clip-vit-large-patch14', 'scene_0001', ?, ?, ?, 'staged')
        """,
        (video_hash, "b" * 64, raw_ref_str, payload_str, payload_hash)
    )
    conn.commit()
    conn.close()

    # Create real FAISS index using python
    import faiss
    import numpy as np
    base_index = faiss.IndexHNSWFlat(768, 32)
    index = faiss.IndexIDMap2(base_index)
    index.add_with_ids(np.random.random((1, 768)).astype("float32"), np.array([999], dtype="int64"))
    faiss.write_index(index, str(faiss_index_path))

    # Create real SQLite sidecar map
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute(
            "CREATE TABLE IF NOT EXISTS clip_id_map (faiss_id INTEGER PRIMARY KEY, hash TEXT, source_path TEXT, created_at TEXT)"
        )
        sidecar_conn.execute(
            "INSERT INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
            (999, "b" * 64, f"L:/_DATA/epochs/db/processing/mock_video/frames/scene_0001.png", "2026-06-14T00:00:00")
        )
    sidecar_conn.close()

    # Case A: Valid FAISS and sidecar -> Pass
    code = run_validation(mode="online")
    assert code == 0

    # In strict mode: should fail because sidecar DB is missing identity columns
    code = run_validation(mode="strict")
    assert code == 1

    # Re-create sidecar table with all columns and standard payloads
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute("DROP TABLE IF EXISTS clip_id_map")
        sidecar_conn.execute(
            """
            CREATE TABLE clip_id_map (
                faiss_id INTEGER PRIMARY KEY,
                hash TEXT,
                source_path TEXT,
                created_at TEXT,
                epoch_id TEXT,
                video_hash TEXT,
                scene_id TEXT,
                scene_hash TEXT,
                worker_name TEXT,
                vector_model_tag TEXT,
                modality TEXT,
                ucf_frame_id INTEGER
            )
            """
        )
        sidecar_conn.execute(
            """
            INSERT INTO clip_id_map(
                faiss_id, hash, source_path, created_at,
                epoch_id, video_hash, scene_id, scene_hash,
                worker_name, vector_model_tag, modality, ucf_frame_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                999, "b" * 64, f"L:/_DATA/epochs/db/processing/mock_video/frames/scene_0001.png", "2026-06-14T00:00:00",
                "db", video_hash, "scene_0001", "b" * 64, "image_embed_clip", "openai/clip-vit-large-patch14", "video", 1
            )
        )
    sidecar_conn.close()

    # Strict mode: should pass now!
    code = run_validation(mode="strict")
    assert code == 0

    # Case B: Sidecar DB missing or mismatch -> Fail
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute("DELETE FROM clip_id_map")
        sidecar_conn.execute(
            "INSERT INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
            (999, "wrong_hash", f"L:/_DATA/epochs/db/processing/mock_video/frames/scene_0001.png", "2026-06-14T00:00:00")
        )
    sidecar_conn.close()
    
    code = run_validation(mode="online")
    assert code == 1


def test_scoped_orphan_detection(setup_validator_env, monkeypatch):
    """Verifies that orphans in active epoch/video scope trigger failures, while other scopes are ignored."""
    ucf_db_path = setup_validator_env["ucf_db_path"]
    video_hash = setup_validator_env["video_hash"]
    raw_ref_str = setup_validator_env["raw_ref_str"]
    tmp_path = setup_validator_env["tmp_path"]
    cfg_data = setup_validator_env["cfg_data"]

    faiss_index_path = Path(cfg_data["paths"]["faiss_clip_path"])
    sidecar_db_path = Path(cfg_data["paths"]["clip_id_map_db"])

    # Make sure parent directory of index exists
    faiss_index_path.parent.mkdir(parents=True, exist_ok=True)

    # Register UCF row for point 999
    conn = sqlite3.connect(str(ucf_db_path))
    payload_dict = {"faiss_id": 999}
    payload_str = json.dumps(payload_dict)
    canonical_str = json.dumps(payload_dict, sort_keys=True)
    payload_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    
    conn.execute("DELETE FROM context_frames")
    conn.execute(
        """
        INSERT INTO context_frames (
            video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
            modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
            vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
            source_artifact_id, raw_ref, payload, payload_hash, promotion_status
        ) VALUES (?, 'ucf.v0.1', 'db', 'run_1', 1.0, 2.0, 'video', 'image_embed_clip', 'openai/clip-vit-large-patch14', 1.0, NULL, 'normalized_yxyx_top_left', ?, 'faiss', 'test_clip_col', 768, 'openai/clip-vit-large-patch14', 'scene_0001', ?, ?, ?, 'staged')
        """,
        (video_hash, "c" * 64, raw_ref_str, payload_str, payload_hash)
    )
    conn.commit()
    conn.close()

    # Create real FAISS index containing both 999 (logged) and 888 (in-scope orphan) and 777 (out-of-scope orphan)
    import faiss
    import numpy as np
    base_index = faiss.IndexHNSWFlat(768, 32)
    index = faiss.IndexIDMap2(base_index)
    index.add_with_ids(np.random.random((3, 768)).astype("float32"), np.array([999, 888, 777], dtype="int64"))
    faiss.write_index(index, str(faiss_index_path))

    # Create real SQLite sidecar map
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute("DROP TABLE IF EXISTS clip_id_map")
        sidecar_conn.execute(
            "CREATE TABLE IF NOT EXISTS clip_id_map (faiss_id INTEGER PRIMARY KEY, hash TEXT, source_path TEXT, created_at TEXT)"
        )
        # 999 is valid
        sidecar_conn.execute(
            "INSERT INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
            (999, "c" * 64, f"L:/_DATA/epochs/db/processing/mock_video/frames/scene_0001.png", "2026-06-14T00:00:00")
        )
        # 888 is an orphan for active video 'mock_video'
        sidecar_conn.execute(
            "INSERT INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
            (888, "d" * 64, f"L:/_DATA/epochs/db/processing/mock_video/frames/scene_0002.png", "2026-06-14T00:00:00")
        )
        # 777 is an orphan for a completely different historical video 'old_video'
        sidecar_conn.execute(
            "INSERT INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
            (777, "e" * 64, f"L:/_DATA/epochs/db/processing/old_video/frames/scene_0001.png", "2026-06-14T00:00:00")
        )
    sidecar_conn.close()

    # In online mode: warns on in-scope orphan, ignores out-of-scope orphan -> should pass but issue warning
    code = run_validation(mode="online")
    assert code == 0
    
    # In strict mode: fails on in-scope orphan -> should return 1 (failure)
    code = run_validation(mode="strict")
    assert code == 1


def test_strict_multi_source_vector_closure(setup_validator_env, monkeypatch):
    """
    UCF Phase 0.7b — Strict Multi-Source Vector Closure
    Goal: Prove vector integrity survives multi-video same-epoch validation in strict mode.
    """
    ucf_db_path = setup_validator_env["ucf_db_path"]
    video_hash_a = setup_validator_env["video_hash"] # mock_video_hash_123
    video_hash_b = "mock_video_hash_456"
    raw_ref_str = setup_validator_env["raw_ref_str"]
    tmp_path = setup_validator_env["tmp_path"]
    cfg_data = setup_validator_env["cfg_data"]

    faiss_index_path = Path(cfg_data["paths"]["faiss_clip_path"])
    sidecar_db_path = Path(cfg_data["paths"]["clip_id_map_db"])
    faiss_index_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize client and register both videos
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    # Clear old frames
    client.execute_with_retry("DELETE FROM context_frames")
    client.execute_with_retry("DELETE FROM media_sources WHERE video_hash = ?", (video_hash_b,))
    
    # Register Video B
    client.register_media(
        video_hash=video_hash_b,
        file_path="mock_video_b.mp4",
        duration=120.0,
        fps=30.0,
        width=1280,
        height=720
    )

    # Log colliding scene IDs (scene_0000) for both Video A and Video B
    # Video A frame_id = 1
    client.log_frame(
        video_hash=video_hash_a, epoch_id="db", run_id="run_1", t_start=1.0, t_end=2.0,
        modality="video", worker_name="image_embed_clip", model_tag="openai/clip-vit-large-patch14",
        vector_key="a"*64, vector_backend="qdrant", vector_collection="test_clip_col",
        vector_dim=768, vector_model_tag="openai/clip-vit-large-patch14",
        source_artifact_id="scene_0000", raw_ref=raw_ref_str, payload={"faiss_id": 101}
    )
    # Video B frame_id = 2
    client.log_frame(
        video_hash=video_hash_b, epoch_id="db", run_id="run_1", t_start=1.0, t_end=2.0,
        modality="video", worker_name="image_embed_clip", model_tag="openai/clip-vit-large-patch14",
        vector_key="b"*64, vector_backend="faiss", vector_collection="test_clip_col",
        vector_dim=768, vector_model_tag="openai/clip-vit-large-patch14",
        source_artifact_id="scene_0000", raw_ref=raw_ref_str, payload={"faiss_id": 202}
    )
    client.close()

    # Setup mock Qdrant points with standard payloads matching identity fields
    # Point "a" * 64 belongs to Video A
    qdrant_points = {
        "a" * 64: {
            "epoch_id": "db",
            "video_hash": video_hash_a,
            "scene_id": "scene_0000",
            "scene_hash": "a" * 64,
            "worker_name": "image_embed_clip",
            "vector_model_tag": "openai/clip-vit-large-patch14",
            "modality": "video",
            "ucf_frame_id": 1,
            "source_path": "mock_video.mp4",
            "faiss_id": 101
        }
    }

    def mock_post(url, json, timeout=None):
        from scripts.ucf.validate_ucf_epoch import normalize_qdrant_id
        normalized_a = normalize_qdrant_id("a" * 64)
        if "scroll" in url:
            pts = []
            if "test_clip_col" in url and "a" * 64 in qdrant_points:
                pts.append({"id": normalized_a, "payload": qdrant_points["a" * 64]})
            return MockResponse({"result": {"points": pts, "next_page_offset": None}}, 200)
        else:
            retrieved = []
            for pid in json.get("ids", []):
                if pid == normalized_a and "a" * 64 in qdrant_points:
                    retrieved.append({"id": pid, "payload": qdrant_points["a" * 64]})
                elif pid in qdrant_points:
                    retrieved.append({"id": pid, "payload": qdrant_points[pid]})
            return MockResponse({"result": retrieved}, 200)

    monkeypatch.setattr(requests, "post", mock_post)

    # Setup FAISS Index for Video B (faiss_id = 202)
    import faiss
    import numpy as np
    base_index = faiss.IndexHNSWFlat(768, 32)
    index = faiss.IndexIDMap2(base_index)
    index.add_with_ids(np.random.random((1, 768)).astype("float32"), np.array([202], dtype="int64"))
    faiss.write_index(index, str(faiss_index_path))

    # Setup SQLite sidecar map with complete identity schema for Video B
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute("DROP TABLE IF EXISTS clip_id_map")
        sidecar_conn.execute(
            """
            CREATE TABLE clip_id_map (
                faiss_id INTEGER PRIMARY KEY,
                hash TEXT,
                source_path TEXT,
                created_at TEXT,
                epoch_id TEXT,
                video_hash TEXT,
                scene_id TEXT,
                scene_hash TEXT,
                worker_name TEXT,
                vector_model_tag TEXT,
                modality TEXT,
                ucf_frame_id INTEGER
            )
            """
        )
        sidecar_conn.execute(
            """
            INSERT INTO clip_id_map(
                faiss_id, hash, source_path, created_at,
                epoch_id, video_hash, scene_id, scene_hash,
                worker_name, vector_model_tag, modality, ucf_frame_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                202, "b" * 64, f"L:/_DATA/epochs/db/processing/mock_video_b/frames/scene_0000.png", "2026-06-14T00:00:00",
                "db", video_hash_b, "scene_0000", "b" * 64, "image_embed_clip", "openai/clip-vit-large-patch14", "video", 2
            )
        )
    sidecar_conn.close()

    # 1. Clean Controlled Epoch: strict validation must pass!
    code = run_validation(mode="strict")
    assert code == 0

    # 2. Orphans from outside current epoch are ignored:
    # Add an out-of-scope orphan to FAISS sidecar DB (different epoch)
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute(
            """
            INSERT INTO clip_id_map(
                faiss_id, hash, source_path, created_at,
                epoch_id, video_hash, scene_id, scene_hash,
                worker_name, vector_model_tag, modality, ucf_frame_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                777, "e" * 64, f"L:/_DATA/epochs/db/processing/old_video/frames/scene_0001.png", "2026-06-14T00:00:00",
                "other_epoch", "old_video", "scene_0001", "e" * 64, "image_embed_clip", "openai/clip-vit-large-patch14", "video", 999
            )
        )
    sidecar_conn.close()
    # Also add 777 to the FAISS index so it is loaded
    index.add_with_ids(np.random.random((1, 768)).astype("float32"), np.array([777], dtype="int64"))
    faiss.write_index(index, str(faiss_index_path))

    # Strict mode validation must STILL pass because 777 is out-of-scope!
    code = run_validation(mode="strict")
    assert code == 0

    # 3. In-scope orphan vectors fail strict mode:
    # Add an in-scope orphan (mock_video_b but not logged in UCF ledger)
    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
    with sidecar_conn:
        sidecar_conn.execute(
            """
            INSERT INTO clip_id_map(
                faiss_id, hash, source_path, created_at,
                epoch_id, video_hash, scene_id, scene_hash,
                worker_name, vector_model_tag, modality, ucf_frame_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                888, "d" * 64, f"L:/_DATA/epochs/db/processing/mock_video_b/frames/scene_0002.png", "2026-06-14T00:00:00",
                "db", video_hash_b, "scene_0002", "d" * 64, "image_embed_clip", "openai/clip-vit-large-patch14", "video", 1000
            )
        )
    sidecar_conn.close()
    index.add_with_ids(np.random.random((1, 768)).astype("float32"), np.array([888], dtype="int64"))
    faiss.write_index(index, str(faiss_index_path))

    # Strict mode validation must now FAIL due to the in-scope orphan!
    code = run_validation(mode="strict")
    assert code == 1
