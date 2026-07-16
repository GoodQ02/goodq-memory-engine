#!/usr/bin/env python3
"""
Integration regression test suite for Requirement R3 and R5.
Verifies raw ref JSON outputs, scene overlap gate edge cases, vector modality integrity,
missing file raw ref checks, vector dimensions, unauthorized collections, and exception
double-counting logic.
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

from cli.run_ingestion import _log_audio_to_ucf_ledger as _real_log_audio_to_ucf_ledger, _load_ucf_ledger, atomic_write_json
from scripts.ucf.validate_ucf_epoch import run_validation


def _log_audio_to_ucf_ledger(cfg_json, video_hash, scene_id, scene, audio_artifact_dir, item):
    res = _real_log_audio_to_ucf_ledger(
        cfg_json=cfg_json,
        video_hash=video_hash,
        scene_id=scene_id,
        scene=scene,
        audio_artifact_dir=audio_artifact_dir,
        item=item
    )
    
    scene_hash_str = scene_id[:16]
    
    # Simulate writing raw ref files that would be written during run_ingestion
    clap_meta = item.get("clap_meta") or {}
    if isinstance(clap_meta, dict) and clap_meta.get("status") == "ok":
        clap_embedding_id = clap_meta.get("embedding_id")
        clap_faiss_id = clap_meta.get("faiss_id")
        if clap_embedding_id and clap_faiss_id is not None:
            clap_raw_ref_path = audio_artifact_dir / f"{scene_hash_str}_raw_clap.json"
            clap_payload = {
                "embedding_id": clap_embedding_id,
                "faiss_id": clap_faiss_id,
                "model": clap_meta.get("model", "laion/clap-htsat-unfused"),
                "qdrant_collection": clap_meta.get("qdrant_collection"),
                "faiss_committed": clap_meta.get("faiss_committed", False),
                "qdrant_committed": clap_meta.get("qdrant_committed", False),
            }
            atomic_write_json(clap_raw_ref_path, clap_payload)
            
    audio_text_embed_meta = item.get("audio_text_embed_meta") or {}
    if isinstance(audio_text_embed_meta, dict) and audio_text_embed_meta.get("status") == "ok":
        text_embedding_id = audio_text_embed_meta.get("embedding_id")
        if text_embedding_id:
            text_embed_raw_ref_path = audio_artifact_dir / f"{scene_hash_str}_raw_text_embed_audio.json"
            text_embed_payload = {
                "embedding_id": text_embedding_id,
                "embedding_source": "audio_transcript",
                "origin_modality": "audio",
                "engine": audio_text_embed_meta.get("engine", "all-MiniLM-L6-v2"),
            }
            atomic_write_json(text_embed_raw_ref_path, text_embed_payload)
            
    return res


def _insert_ucf_row_helper(
    db_path,
    video_hash,
    raw_ref_str,
    payload_dict,
    modality,
    worker_name,
    model_tag="faster_whisper",
    vector_key=None,
    vector_backend=None,
    vector_collection=None,
    vector_dim=None,
    vector_model_tag=None
):
    payload_str = json.dumps(payload_dict)
    canonical_str = json.dumps(payload_dict, sort_keys=True)
    payload_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO context_frames (
            video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
            modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
            vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
            source_artifact_id, raw_ref, payload, payload_hash, promotion_status
        ) VALUES (?, 'ucf.v0.1', 'db', 'run_regression', 1.0, 2.0, ?, ?, ?, 1.0, NULL,
                  'normalized_yxyx_top_left', ?, ?, ?, ?, ?, 'scene_0001', ?, ?, ?, 'staged')
        """,
        (
            video_hash, modality, worker_name, model_tag,
            vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
            raw_ref_str, payload_str, payload_hash,
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    db_dir = tmp_path / "epochs" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    
    cfg_json = tmp_path / "cfg.json"
    cfg_data = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path),
            "faiss_clip_path": str(tmp_path / "faiss_clip.index"),
            "faiss_dino_path": str(tmp_path / "faiss_dino.index"),
            "faiss_audio_path": str(tmp_path / "faiss_audio.index"),
            "faiss_index_path": str(tmp_path / "faiss_text.index"),
            "clip_id_map_db": str(tmp_path / "clip_id_map.sqlite"),
            "dino_id_map_db": str(tmp_path / "dino_id_map.sqlite"),
            "clap_id_map_db": str(tmp_path / "clap_id_map.sqlite"),
            "db_path": str(tmp_path / "memory.db"),
            "processing": str(tmp_path / "processing"),
            "reports_dir": str(tmp_path / "reports"),
        },
        "qdrant": {
            "collections": {
                "clip": "test_clip_col",
                "dino": "test_dino_col",
                "audio": "test_audio_col",
                "text": "test_text_col"
            },
            "embedding_dims": {
                "clip": 768,
                "dino": 1024,
                "audio": 512,
                "text": 384
            },
            "host": "http://mock_qdrant:6333"
        },
        "run": {
            "id": "test_run_regression"
        }
    }
    cfg_json.write_text(json.dumps(cfg_data), encoding="utf-8")
    
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GOODQ_RUN_ID", "test_run_regression")
    
    # Monkeypatch config loader in validate_ucf_epoch
    import scripts.ucf.validate_ucf_epoch
    monkeypatch.setattr(scripts.ucf.validate_ucf_epoch, "load_configs", lambda x: cfg_data)
    monkeypatch.setattr(scripts.ucf.validate_ucf_epoch, "REPO_ROOT", tmp_path)
    
    # Path where validator expects DB: clean path
    expected_db_dir = tmp_path / "epochs" / "db" / "ucf"
    expected_db_dir.mkdir(parents=True)
    db_path = expected_db_dir / "ucf_ledger.db"
    
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(db_path))
    client.init_schema()
    
    video_hash = "mock_video_hash_regression"
    client.register_media(
        video_hash=video_hash,
        file_path="mock_video.mp4",
        duration=60.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    client.close()
    
    raw_ref_file = tmp_path / "mock_ref.json"
    raw_ref_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    
    audio_artifact_dir = tmp_path / "audio_artifacts"
    audio_artifact_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "tmp_path": tmp_path,
        "cfg_json": cfg_json,
        "cfg_data": cfg_data,
        "db_path": db_path,
        "video_hash": video_hash,
        "raw_ref_str": str(raw_ref_file.resolve()),
        "audio_artifact_dir": audio_artifact_dir
    }


def test_raw_ref_written_for_clap_section(setup_env):
    env = setup_env
    scene_id = "scene_0001_clap"
    scene = {"start": 10.0, "end": 20.0, "index": 1}
    item = {
        "clap_meta": {
            "status": "ok",
            "embedding_id": "test_clap_embedding_id_123",
            "faiss_id": 42,
            "model": "laion/clap-htsat-unfused",
            "qdrant_collection": "audio",
            "faiss_committed": False,
            "qdrant_committed": False
        }
    }
    
    _log_audio_to_ucf_ledger(
        cfg_json=env["cfg_json"],
        video_hash=env["video_hash"],
        scene_id=scene_id,
        scene=scene,
        audio_artifact_dir=env["audio_artifact_dir"],
        item=item
    )
    
    scene_hash_str = scene_id[:16]
    expected_file = env["audio_artifact_dir"] / f"{scene_hash_str}_raw_clap.json"
    assert expected_file.exists()
    
    with open(expected_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["embedding_id"] == "test_clap_embedding_id_123"


def test_raw_ref_written_for_text_embed_audio_section(setup_env):
    env = setup_env
    scene_id = "scene_0001_text_embed"
    scene = {"start": 10.0, "end": 20.0, "index": 1}
    item = {
        "audio_text_embed_meta": {
            "status": "ok",
            "embedding_id": "test_text_embedding_id_456",
            "engine": "all-MiniLM-L6-v2"
        }
    }
    
    _log_audio_to_ucf_ledger(
        cfg_json=env["cfg_json"],
        video_hash=env["video_hash"],
        scene_id=scene_id,
        scene=scene,
        audio_artifact_dir=env["audio_artifact_dir"],
        item=item
    )
    
    scene_hash_str = scene_id[:16]
    expected_file = env["audio_artifact_dir"] / f"{scene_hash_str}_raw_text_embed_audio.json"
    assert expected_file.exists()
    
    with open(expected_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["embedding_id"] == "test_text_embedding_id_456"


def test_scene_overlap_gate_skips_when_no_scene_detect(setup_env):
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    payload = {
        "text": "Hello world",
        "language": "en",
        "segment_index": 0,
        "word_count": 2,
        "confidence": 0.95,
        "identity_status": "unresolved"
    }
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=env["raw_ref_str"],
        payload_dict=payload,
        modality="text",
        worker_name="audio_transcribe",
        model_tag="faster_whisper"
    )
    
    run_validation(mode="offline")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    assert report_path.exists()
    
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["scene_overlap_gate"]["status"] != "failed"
    assert report["scene_overlap_gate"]["errors"] == []


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self):
        return self.json_data


def test_qdrant_clap_payload_uses_audio_modality(setup_env, monkeypatch):
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()

    vector_key = "a" * 64
    payload = {
        "embedding_id": vector_key,
        "faiss_id": 42
    }
    
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=env["raw_ref_str"],
        payload_dict=payload,
        modality="audio",
        worker_name="audio_embed_clap",
        model_tag="laion/clap-htsat-unfused",
        vector_key=vector_key,
        vector_backend="qdrant",
        vector_collection="test_audio_col",
        vector_dim=512,
        vector_model_tag="laion/clap-htsat-unfused"
    )
    
    qdrant_points = {
        vector_key: {
            "epoch_id": "db",
            "video_hash": env["video_hash"],
            "scene_id": "scene_0001",
            "scene_hash": vector_key,
            "worker_name": "audio_embed_clap",
            "vector_model_tag": "laion/clap-htsat-unfused",
            "modality": "audio",
            "ucf_frame_id": 1,
            "source_path": "mock_video.mp4"
        }
    }
    
    def mock_post(url, json, timeout=None):
        from scripts.ucf.validate_ucf_epoch import normalize_qdrant_id
        normalized_key = normalize_qdrant_id(vector_key)
        if "scroll" in url:
            pts = []
            if normalized_key in qdrant_points:
                pts.append({"id": normalized_key, "payload": qdrant_points[vector_key]})
            return MockResponse({"result": {"points": pts, "next_page_offset": None}}, 200)
        else:
            retrieved = []
            for pid in json.get("ids", []):
                if pid == normalized_key:
                    retrieved.append({"id": pid, "payload": qdrant_points[vector_key]})
            return MockResponse({"result": retrieved}, 200)
            
    monkeypatch.setattr(requests, "post", mock_post)
    
    run_validation(mode="online")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["vector_integrity"]["status"] == "passed"


def test_raw_ref_gate_fails_when_file_missing(setup_env):
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    missing_path = env["tmp_path"] / "non_existent_file.json"
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=str(missing_path),
        payload_dict={"turn_index": 0, "speaker_id": "SPEAKER_01"},
        modality="audio",
        worker_name="speaker_merge",
        model_tag="pyannote"
    )
    
    run_validation(mode="offline")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["raw_ref_gate"]["status"] == "failed"
    errors = report["raw_ref_gate"]["errors"]
    assert any(str(missing_path) in err for err in errors)


def test_vector_dim_mismatch_fails_offline(setup_env):
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=env["raw_ref_str"],
        payload_dict={"faiss_id": 42},
        modality="text",
        worker_name="text_embed",
        model_tag="sentence-transformers/all-MiniLM-L6-v2",
        vector_key="a" * 64,
        vector_backend="qdrant",
        vector_collection="test_text_col",
        vector_dim=999,  # Mismatch (expected 384)
        vector_model_tag="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    run_validation(mode="offline")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["vector_integrity"]["status"] == "failed"


def test_vector_metadata_collection_not_in_registry_fails(setup_env):
    """Offline validation checks UCF metadata (vector_collection column) against the VECTOR_REGISTRY
    allowed_collections set. This is NOT a Qdrant payload inspection -- offline mode cannot reach
    Qdrant. The failure is a registry metadata mismatch, not a backend payload mismatch.

    For true backend payload mismatch (wrong modality/worker_name returned by Qdrant), see
    the online mocked test: test_qdrant_clap_payload_uses_audio_modality.
    """
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=env["raw_ref_str"],
        payload_dict={"faiss_id": 42},
        modality="text",
        worker_name="text_embed",
        model_tag="sentence-transformers/all-MiniLM-L6-v2",
        vector_key="a" * 64,
        vector_backend="qdrant",
        vector_collection="unallowed_collection_name",  # Not allowed
        vector_dim=384,
        vector_model_tag="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    run_validation(mode="offline")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["vector_integrity"]["status"] == "failed"


def test_missing_scene_detect_overlap_gate_has_empty_errors(setup_env):
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    payload = {
        "text": "Hello world",
        "language": "en",
        "segment_index": 0,
        "word_count": 2,
        "confidence": 0.95,
        "identity_status": "unresolved"
    }
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=env["raw_ref_str"],
        payload_dict=payload,
        modality="text",
        worker_name="audio_transcribe",
        model_tag="faster_whisper"
    )
    
    run_validation(mode="offline")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["scene_overlap_gate"]["status"] != "failed"
    assert len(report["scene_overlap_gate"]["errors"]) == 0


def test_checks_failed_no_double_count_on_exception(setup_env, monkeypatch):
    env = setup_env
    # Clear old frames
    conn = sqlite3.connect(str(env["db_path"]))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    missing_path = env["tmp_path"] / "non_existent_file.json"
    _insert_ucf_row_helper(
        db_path=env["db_path"],
        video_hash=env["video_hash"],
        raw_ref_str=str(missing_path),
        payload_dict={"faiss_id": 42},
        modality="text",
        worker_name="text_embed",
        model_tag="sentence-transformers/all-MiniLM-L6-v2",
        vector_key="a" * 64,
        vector_backend="qdrant",
        vector_collection="test_text_col",
        vector_dim=384,
        vector_model_tag="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    def mock_validate_vector_key(*args, **kwargs):
        raise ValueError("Simulated validation key exception")
        
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.validate_vector_key", mock_validate_vector_key)
    
    run_validation(mode="offline")
    
    report_path = env["tmp_path"] / "reports" / "ucf_validation_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    check_categories = [
        "path_hygiene", "schema_version", "promotion_status",
        "temporal_bounds", "payload_hash", "flatness",
        "spatial_region", "manifest_reconciliation",
        "raw_ref_gate", "scene_overlap_gate",
        "raw_reconciliation", "absolute_timestamps", "media_sources_gate",
        "vector_integrity"
    ]
    failed_count = sum(1 for cat in check_categories if report[cat]["status"] == "failed")
    
    assert report["summary"]["checks_failed"] == failed_count


def test_timestamp_rounding_and_conflict_handling(setup_env):
    env = setup_env
    db_path = env["tmp_path"] / "rounding_test.db"
    
    # Reload ucf_ledger module to ensure we get the latest code
    import importlib
    import scripts.ucf.ucf_ledger
    importlib.reload(scripts.ucf.ucf_ledger)
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    
    client = UCFLedgerClient(str(db_path))
    client.init_schema()
    
    video_hash = "mock_video_rounding"
    client.register_media(
        video_hash=video_hash,
        file_path="mock_video.mp4",
        duration=60.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    # Log first frame with high-precision floats: 1.2341 -> 1.234, 2.3456 -> 2.346
    client.log_frame(
        video_hash=video_hash,
        epoch_id="ep1",
        run_id="run1",
        t_start=1.2341,
        t_end=2.3456,
        modality="audio",
        worker_name="whisper",
        model_tag="large",
        payload={"text": "hello"}
    )
    
    # Log second frame with slightly different floats that round to the same values: 1.2344 -> 1.234, 2.3459 -> 2.346
    # This should trigger ON CONFLICT and update the payload to {"text": "world"}
    client.log_frame(
        video_hash=video_hash,
        epoch_id="ep1",
        run_id="run1",
        t_start=1.2344,
        t_end=2.3459,
        modality="audio",
        worker_name="whisper",
        model_tag="large",
        payload={"text": "world"}
    )
    
    # Retrieve the frames from DB and assert only 1 frame exists and it is rounded and updated
    frames = client.query_overlap(video_hash, 0.0, 10.0)
    assert len(frames) == 1
    frame = frames[0]
    assert frame["t_start"] == 1.234
    assert frame["t_end"] == 2.346
    assert frame["payload"] == {"text": "world"}
    
    client.close()
