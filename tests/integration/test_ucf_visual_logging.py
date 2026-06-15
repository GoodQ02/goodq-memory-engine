#!/usr/bin/env python3
"""
Integration test for UCF visual logging.
Verifies that the ucf_ledger.db correctly stores visual-related context frames
with correct modalities, coordinate normalization, vector metadata, and multiple detection rows.
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cli.run_ingestion import _log_visual_to_ucf_ledger, _load_ucf_ledger

def test_ucf_visual_logging_mock(tmp_path, monkeypatch):
    """
    Verifies that _log_visual_to_ucf_ledger writes correctly to the ledger:
    - Bounding boxes are normalized to [ymin, xmin, ymax, xmax] based on media_sources width and height.
    - Multiple objects / faces create separate rows.
    - DINO and CLIP populate vector metadata.
    - OCR and Captions are recorded.
    - Raw reference files are written and correct.
    """
    # 1. Prepare inputs
    cfg_json = tmp_path / "cfg.json"
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    
    cfg_data = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path)
        },
        "run": {
            "id": "test_run_visual"
        },
        "qdrant": {
            "collections": {
                "clip": "test_clip_col",
                "dino": "test_dino_col"
            },
            "embedding_dims": {
                "clip": 768,
                "dino": 1024
            }
        }
    }
    cfg_json.write_text(json.dumps(cfg_data), encoding="utf-8")
    
    video_hash = "mock_video_hash_visual_456"
    scene_id = "scene_0001"
    
    scene = {
        "start": 5.0,
        "duration": 4.0, # mid timestamp should be 5 + 4/2 = 7.0
        "index": 1
    }
    
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    
    # Mock item with visual outputs
    item = {
        "ocr_text": "Sign post: Stop",
        "ocr_meta": {
            "engine": "tesseract",
            "strategy": "default"
        },
        "caption": "A red stop sign on a street corner",
        "caption_meta": {
            "engine": "blip"
        },
        "objects": [
            {
                "bbox": [192, 108, 384, 216], # absolute x1, y1, x2, y2
                "label": "stop sign",
                "score": 0.95
            },
            {
                "bbox": [576, 324, 768, 432],
                "label": "car",
                "score": 0.88
            }
        ],
        "faces": [
            {
                "bbox": [960, 540, 1056, 648], # absolute x1, y1, x2, y2
                "encoding": [0.1, 0.2, 0.3]
            }
        ],
        "faces_meta": {
            "engine": "facenet-pytorch"
        },
        "dino_meta": {
            "status": "ok",
            "embedding_id": "dino_fingerprint_abc",
            "faiss_id": 999111,
            "qdrant_committed": True,
            "qdrant_collection": "goodq_dino_custom",
            "model": "facebook/dinov2-large"
        },
        "clip_meta": {
            "status": "ok",
            "embedding_id": "clip_fingerprint_xyz",
            "faiss_id": 999222,
            "qdrant_committed": False,
            "model": "openai/clip-vit-large-patch14"
        }
    }
    
    # Set environment variables for the test
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GOODQ_RUN_ID", "test_run_visual")
    
    # Resolve expected DB path
    expected_db_dir = tmp_path / "epochs" / "db" / "ucf"
    expected_db_dir.mkdir(parents=True)
    ucf_db_path = expected_db_dir / "ucf_ledger.db"
    
    # Register the media in the database so the dimensions 1920x1080 are resolved
    ucf_module = _load_ucf_ledger()
    client = ucf_module.UCFLedgerClient(str(ucf_db_path))
    client.init_schema()
    client.register_media(
        video_hash=video_hash,
        file_path="mock_path.mp4",
        duration=60.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    client.close()
    
    # Call visual logging hook
    _log_visual_to_ucf_ledger(
        cfg_json=cfg_json,
        video_hash=video_hash,
        scene_id=scene_id,
        scene=scene,
        frame_dir=frame_dir,
        item=item
    )
    
    # Check that database is populated correctly
    conn = sqlite3.connect(str(ucf_db_path))
    conn.row_factory = sqlite3.Row
    
    # 1. OCR text frame assertions
    ocr_rows = conn.execute("SELECT * FROM context_frames WHERE worker_name='image_ocr'").fetchall()
    assert len(ocr_rows) == 1
    ocr_row = ocr_rows[0]
    assert ocr_row["modality"] == "text"
    assert ocr_row["t_start"] == 7.0
    assert ocr_row["t_end"] == 7.0
    assert ocr_row["raw_ref"] == str((frame_dir / f"{scene_id}_raw_ocr.json").resolve())
    payload_ocr = json.loads(ocr_row["payload"])
    assert payload_ocr["text"] == "Sign post: Stop"
    assert payload_ocr["engine"] == "tesseract"
    
    # 2. Caption text frame assertions
    caption_rows = conn.execute("SELECT * FROM context_frames WHERE worker_name='image_caption'").fetchall()
    assert len(caption_rows) == 1
    caption_row = caption_rows[0]
    assert caption_row["modality"] == "multimodal"
    payload_caption = json.loads(caption_row["payload"])
    assert payload_caption["text"] == "A red stop sign on a street corner"
    assert payload_caption["engine"] == "blip"
    
    # 3. Object detection assertions (2 objects, separate rows)
    object_rows = conn.execute("SELECT * FROM context_frames WHERE worker_name='object_detect' ORDER BY frame_id ASC").fetchall()
    assert len(object_rows) == 2
    
    # Object 1 (stop sign)
    obj1 = object_rows[0]
    assert obj1["modality"] == "video"
    assert obj1["confidence"] == 0.95
    payload_obj1 = json.loads(obj1["payload"])
    assert payload_obj1["label"] == "stop sign"
    # Normalization check: x1=192, y1=108, x2=384, y2=216 against width=1920, height=1080
    # [ymin, xmin, ymax, xmax] -> [108/1080, 192/1920, 216/1080, 384/1920] = [0.1, 0.1, 0.2, 0.2]
    spatial_region1 = json.loads(obj1["spatial_region"])
    assert pytest.approx(spatial_region1) == [0.1, 0.1, 0.2, 0.2]
    
    # Object 2 (car)
    obj2 = object_rows[1]
    assert obj2["confidence"] == 0.88
    payload_obj2 = json.loads(obj2["payload"])
    assert payload_obj2["label"] == "car"
    # Normalization check: x1=576, y1=324, x2=768, y2=432
    # [324/1080, 576/1920, 432/1080, 768/1920] = [0.3, 0.3, 0.4, 0.4]
    spatial_region2 = json.loads(obj2["spatial_region"])
    assert pytest.approx(spatial_region2) == [0.3, 0.3, 0.4, 0.4]
    
    # 4. Face embedding assertions (1 face)
    face_rows = conn.execute("SELECT * FROM context_frames WHERE worker_name='face_embed'").fetchall()
    assert len(face_rows) == 1
    face_row = face_rows[0]
    assert face_row["modality"] == "video"
    # Normalization check: x1=960, y1=540, x2=1056, y2=648
    # [540/1080, 960/1920, 648/1080, 1056/1920] = [0.5, 0.5, 0.6, 0.55]
    spatial_region_face = json.loads(face_row["spatial_region"])
    assert pytest.approx(spatial_region_face) == [0.5, 0.5, 0.6, 0.55]
    payload_face = json.loads(face_row["payload"])
    assert payload_face["face_index"] == 0
    assert payload_face["engine"] == "facenet-pytorch"
    
    # 5. DINOv2 visual embedding assertions
    dino_rows = conn.execute("SELECT * FROM context_frames WHERE worker_name='image_embed_dino'").fetchall()
    assert len(dino_rows) == 1
    dino_row = dino_rows[0]
    assert dino_row["modality"] == "video"
    assert dino_row["vector_key"] == "dino_fingerprint_abc"
    assert dino_row["vector_backend"] == "qdrant"
    assert dino_row["vector_collection"] == "goodq_dino_custom"
    assert dino_row["vector_dim"] == 1024
    assert dino_row["vector_model_tag"] == "facebook/dinov2-large"
    
    # 6. CLIP visual embedding assertions
    clip_rows = conn.execute("SELECT * FROM context_frames WHERE worker_name='image_embed_clip'").fetchall()
    assert len(clip_rows) == 1
    clip_row = clip_rows[0]
    assert clip_row["modality"] == "video"
    assert clip_row["vector_key"] == "clip_fingerprint_xyz"
    assert clip_row["vector_backend"] == "faiss"
    assert clip_row["vector_collection"] == "test_clip_col"
    assert clip_row["vector_dim"] == 768
    assert clip_row["vector_model_tag"] == "openai/clip-vit-large-patch14"
    
    # Verify that raw reference files exist on disk
    for step_type in ["ocr", "caption", "objects", "faces", "dino", "clip"]:
        raw_file = frame_dir / f"{scene_id}_raw_{step_type}.json"
        assert raw_file.exists(), f"Raw file {raw_file} was not written to disk"
        
    conn.close()
