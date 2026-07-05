#!/usr/bin/env python3
"""
Challenger integration test suite.
Verifies:
1. Timestamp rounding (12.3456 vs 12.346) causing conflict updates in ucf_ledger.db,
   and confirming that all metadata fields (model_tag, raw_ref, source_artifact_id, etc.)
   are successfully updated on conflict.
2. Live Qdrant payload verification and asserting that AssertionError is raised if we
   assert successful validation with incorrect live payloads.
"""

import sys
import os
import sqlite3
import json
import hashlib
import requests
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cli.run_ingestion import _load_ucf_ledger
from scripts.ucf.validate_ucf_epoch import run_validation

@pytest.fixture
def setup_challenger_env(tmp_path, monkeypatch):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    
    cfg_data = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path),
            "faiss_clip_path": str(tmp_path / "faiss_clip.index"),
            "faiss_dino_path": str(tmp_path / "faiss_dino.index"),
            "clip_id_map_db": str(tmp_path / "clip_id_map.sqlite"),
            "dino_id_map_db": str(tmp_path / "dino_id_map.sqlite"),
            "processing": str(tmp_path / "processing"),
            "db_path": str(tmp_path / "memory.db"),
        },
        "qdrant": {
            "collections": {
                "clip": "goodq_clip_epoch_2026_06_15_ucf_clean_verify",
                "dino": "goodq_dino_epoch_2026_06_15_ucf_clean_verify",
                "audio": "goodq_audio_epoch_2026_06_15_ucf_clean_verify",
                "text": "goodq_text_epoch_2026_06_15_ucf_clean_verify"
            },
            "embedding_dims": {
                "clip": 768,
                "dino": 1024,
                "audio": 512,
                "text": 384
            },
            "host": "http://127.0.0.1:6333"
        }
    }
    
    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(json.dumps(cfg_data), encoding="utf-8")
    
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    
    import scripts.ucf.validate_ucf_epoch
    monkeypatch.setattr(scripts.ucf.validate_ucf_epoch, "load_configs", lambda x: cfg_data)
    monkeypatch.setattr(scripts.ucf.validate_ucf_epoch, "REPO_ROOT", tmp_path)
    
    expected_db_dir = db_dir / "ucf"
    expected_db_dir.mkdir(parents=True, exist_ok=True)
    ucf_db_path = expected_db_dir / "ucf_ledger.db"
    
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    client.init_schema()
    client.close()
    
    raw_ref_file = tmp_path / "mock_ref.json"
    raw_ref_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    
    return {
        "tmp_path": tmp_path,
        "ucf_db_path": ucf_db_path,
        "cfg_data": cfg_data,
        "raw_ref_str": str(raw_ref_file.resolve())
    }

def test_rounding_and_metadata_updates_on_conflict(setup_challenger_env):
    """Verify that t_start values (e.g. 12.3456 vs 12.346) round to the same value
    and trigger ON CONFLICT update, successfully updating all metadata fields."""
    ucf_db_path = setup_challenger_env["ucf_db_path"]
    
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    
    video_hash = "mock_video_hash_rounding"
    client.register_media(
        video_hash=video_hash,
        file_path="mock_video.mp4",
        duration=60.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    # First insert: high precision start 12.3456 (rounds to 12.346)
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch1",
        run_id="run1",
        t_start=12.3456,
        t_end=15.000,
        modality="audio",
        worker_name="audio_embed_clap",
        model_tag="initial_model",
        confidence=0.8,
        source_artifact_id="initial_artifact_id",
        raw_ref="initial_raw_ref.json",
        payload={"text": "hello"},
        promotion_status="staged"
    )
    
    # Verify the first insert was rounded to 12.346
    frames = client.query_overlap(video_hash, 0.0, 30.0)
    assert len(frames) == 1
    assert frames[0]["t_start"] == 12.346
    assert frames[0]["model_tag"] == "initial_model"
    assert frames[0]["raw_ref"] == "initial_raw_ref.json"
    assert frames[0]["source_artifact_id"] == "initial_artifact_id"
    assert frames[0]["payload"] == {"text": "hello"}
    
    # Second insert with slightly different t_start 12.346 (rounds to 12.346)
    # which matches exactly, causing conflict and updating metadata.
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch1",
        run_id="run2",
        t_start=12.346,
        t_end=15.000,
        modality="audio",
        worker_name="audio_embed_clap",
        model_tag="updated_model",
        confidence=0.95,
        source_artifact_id="updated_artifact_id",
        raw_ref="updated_raw_ref.json",
        payload={"text": "world"},
        promotion_status="validated"
    )
    
    # Verify only one frame remains and all metadata fields were updated correctly
    frames_after = client.query_overlap(video_hash, 0.0, 30.0)
    assert len(frames_after) == 1
    f = frames_after[0]
    assert f["t_start"] == 12.346
    assert f["t_end"] == 15.000
    assert f["run_id"] == "run2"
    assert f["confidence"] == 0.95
    assert f["model_tag"] == "updated_model"
    assert f["raw_ref"] == "updated_raw_ref.json"
    assert f["source_artifact_id"] == "updated_artifact_id"
    assert f["payload"] == {"text": "world"}
    assert f["promotion_status"] == "validated"
    
    client.close()

def test_live_qdrant_payload_validation_and_assertion_error(setup_challenger_env):
    """Verify live Qdrant payload verification and that AssertionError is raised
    if we assert a successful validation when payloads or hashes mismatch."""
    ucf_db_path = setup_challenger_env["ucf_db_path"]
    raw_ref_str = setup_challenger_env["raw_ref_str"]
    
    # Check if live Qdrant is accessible. If not, skip this test.
    qdrant_host = "http://127.0.0.1:6333"
    try:
        r = requests.get(f"{qdrant_host}/collections", timeout=3)
        if r.status_code != 200:
            pytest.skip("Live Qdrant is not running/accessible on 6333.")
    except Exception:
        pytest.skip("Live Qdrant is not running/accessible on 6333.")
        
    # Get a sample point from the live audio collection to verify payload keys
    collection = "goodq_audio_epoch_2026_06_15_ucf_clean_verify"
    r_scroll = requests.post(f"{qdrant_host}/collections/{collection}/points/scroll", json={"limit": 1}, timeout=3)
    res = r_scroll.json().get("result", {})
    points = res.get("points", [])
    if not points:
        pytest.skip(f"No points found in collection {collection} to test with.")
        
    sample_point = points[0]
    sample_key = sample_point["id"]
    sample_payload = sample_point["payload"]
    
    # Extract actual payload attributes
    live_video_hash = sample_payload.get("video_hash") or sample_payload.get("video_id")
    live_scene_id = sample_payload.get("scene_id")
    
    assert live_video_hash is not None, "Live point must have a video_id/video_hash"
    assert live_scene_id is not None, "Live point must have a scene_id"
    
    # Write this live reference into our temporary ucf_ledger DB
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    
    # Register the video hash associated with the live point
    client.register_media(
        video_hash=live_video_hash,
        file_path="mock_video.mp4",
        duration=6000.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    # Log frame with correct matching video_hash and vector_key
    client.log_frame(
        video_hash=live_video_hash,
        epoch_id="epoch_2026_06_15_ucf_clean_verify",
        run_id="run_1",
        t_start=1.0,
        t_end=10.0,
        modality="audio",
        worker_name="audio_embed_clap",
        model_tag="laion/clap-htsat-unfused",
        confidence=1.0,
        vector_key=sample_key,
        vector_backend="qdrant",
        vector_collection=collection,
        vector_dim=512,
        vector_model_tag="laion/clap-htsat-unfused",
        source_artifact_id=live_scene_id,
        raw_ref=raw_ref_str,
        payload={"faiss_id": 123},
        promotion_status="staged"
    )
    client.close()
    
    # A. Run validator in strict mode. It should return 1 because the live payload is missing
    # epoch_id, scene_hash, ucf_frame_id.
    # Asserting that strict mode returns 0 should raise AssertionError.
    code_strict = run_validation(mode="strict")
    with pytest.raises(AssertionError):
        assert code_strict == 0
    assert code_strict == 1
    
    # B. Run validator in online mode. Since it matches video_hash and scene_id, and modality check
    # passes (as modality is not set in live Qdrant payload, which is bypassed by the if p_modality guard),
    # this should return 0 (success).
    code_online = run_validation(mode="online")
    assert code_online == 0
    
    # C. Now, simulate incorrect payload by registering a frame with a mismatched video_hash.
    # (E.g. we point vector_key to the same live point, but we associate it with a different video_hash in the DB).
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    # Delete the old frame
    conn = sqlite3.connect(str(ucf_db_path))
    conn.execute("DELETE FROM context_frames")
    conn.commit()
    conn.close()
    
    mismatched_video_hash = "mismatched_video_hash_999"
    client.register_media(
        video_hash=mismatched_video_hash,
        file_path="mock_video_2.mp4",
        duration=6000.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    client.log_frame(
        video_hash=mismatched_video_hash,
        epoch_id="epoch_2026_06_15_ucf_clean_verify",
        run_id="run_1",
        t_start=1.0,
        t_end=10.0,
        modality="audio",
        worker_name="audio_embed_clap",
        model_tag="laion/clap-htsat-unfused",
        confidence=1.0,
        vector_key=sample_key,
        vector_backend="qdrant",
        vector_collection=collection,
        vector_dim=512,
        vector_model_tag="laion/clap-htsat-unfused",
        source_artifact_id=live_scene_id,
        raw_ref=raw_ref_str,
        payload={"faiss_id": 123},
        promotion_status="staged"
    )
    client.close()
    
    # Now run validator in online mode. It should return 1 because the video_hash in live Qdrant point
    # payload does not match the mismatched_video_hash in the DB frame.
    # Asserting that online mode returns 0 should raise AssertionError.
    code_online_mismatch = run_validation(mode="online")
    with pytest.raises(AssertionError):
        assert code_online_mismatch == 0
    assert code_online_mismatch == 1
