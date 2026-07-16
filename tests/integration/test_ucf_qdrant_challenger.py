#!/usr/bin/env python3
"""
Challenger integration test suite.
Verifies:
1. Timestamp rounding (12.3456 vs 12.346) causing conflict updates in ucf_ledger.db,
   and confirming that all metadata fields (model_tag, raw_ref, source_artifact_id, etc.)
   are successfully updated on conflict.
2. Live Qdrant payload verification against an explicitly selected current epoch,
   including a mismatched-payload negative control.
"""

import sys
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
from tests.runtime_profile import (
    expected_epoch_collections,
    require_live_profile,
    require_runtime_evidence,
    selected_runtime_epoch,
)

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

@pytest.mark.live_runtime
def test_live_qdrant_payload_matching_and_mismatch(setup_challenger_env, goodq_test_profile):
    """Verify current-epoch Qdrant payload matching and mismatch detection."""
    ucf_db_path = setup_challenger_env["ucf_db_path"]
    raw_ref_str = setup_challenger_env["raw_ref_str"]
    require_live_profile(goodq_test_profile, "live Qdrant payload witness")
    epoch_id = selected_runtime_epoch(goodq_test_profile)
    collection = expected_epoch_collections(goodq_test_profile, epoch_id)["audio"]

    qdrant_host = "http://127.0.0.1:6333"
    try:
        r = requests.get(f"{qdrant_host}/collections", timeout=3)
    except requests.RequestException as exc:
        require_runtime_evidence(
            goodq_test_profile,
            False,
            f"Qdrant request failed: {type(exc).__name__}",
        )
        return
    require_runtime_evidence(
        goodq_test_profile,
        r.status_code == 200,
        f"Qdrant collection inventory returned HTTP {r.status_code}",
    )
    collections = [
        item.get("name", "")
        for item in r.json().get("result", {}).get("collections", [])
    ]
    require_runtime_evidence(
        goodq_test_profile,
        collection in collections,
        f"required audio collection is absent: {collection}",
    )
    setup_challenger_env["cfg_data"]["qdrant"]["collections"]["audio"] = collection

    r_scroll = requests.post(
        f"{qdrant_host}/collections/{collection}/points/scroll",
        json={"limit": 1, "with_payload": True, "with_vector": False},
        timeout=3,
    )
    require_runtime_evidence(
        goodq_test_profile,
        r_scroll.status_code == 200,
        f"Qdrant scroll returned HTTP {r_scroll.status_code}",
    )
    res = r_scroll.json().get("result", {})
    points = res.get("points", [])
    require_runtime_evidence(
        goodq_test_profile,
        bool(points),
        f"no points found in required collection {collection}",
    )

    sample_point = points[0]
    sample_key = sample_point["id"]
    sample_payload = sample_point["payload"]

    live_video_hash = sample_payload.get("video_hash") or sample_payload.get("video_id")
    live_scene_id = sample_payload.get("scene_id")
    live_epoch_id = sample_payload.get("epoch_id") or epoch_id
    live_ucf_frame_id = sample_payload.get("ucf_frame_id")

    assert live_video_hash is not None, "Live point must have a video_id/video_hash"
    assert live_scene_id is not None, "Live point must have a scene_id"
    require_runtime_evidence(
        goodq_test_profile,
        live_ucf_frame_id is not None,
        "sample Qdrant payload has no ucf_frame_id",
    )
    require_runtime_evidence(
        goodq_test_profile,
        live_epoch_id == epoch_id,
        f"sample Qdrant payload epoch mismatch: {live_epoch_id!r}",
    )

    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))

    client.register_media(
        video_hash=live_video_hash,
        file_path="mock_video.mp4",
        duration=6000.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    client.log_frame(
        video_hash=live_video_hash,
        epoch_id=live_epoch_id,
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
    conn = sqlite3.connect(str(ucf_db_path))
    conn.execute(
        "UPDATE context_frames SET frame_id = ? WHERE vector_key = ?",
        (int(live_ucf_frame_id), str(sample_key)),
    )
    conn.commit()
    conn.close()

    code_online = run_validation(mode="online")
    assert code_online == 0

    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
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
        epoch_id=live_epoch_id,
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
    conn = sqlite3.connect(str(ucf_db_path))
    conn.execute(
        "UPDATE context_frames SET frame_id = ? WHERE vector_key = ?",
        (int(live_ucf_frame_id), str(sample_key)),
    )
    conn.commit()
    conn.close()

    code_online_mismatch = run_validation(mode="online")
    assert code_online_mismatch == 1
