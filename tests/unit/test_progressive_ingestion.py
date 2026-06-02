import tempfile
import json
import sqlite3
from pathlib import Path
import pytest

from cli.run_ingestion import _make_id
from steps.common.atomic_io import atomic_write_json
from steps.video.scene_visual_embeddings import _mirror_scene_vector_status

def test_window_grouping_logic():
    # Test deterministic overlap window index calculation
    chunk_size = 300.0
    chunk_overlap = 10.0
    step = chunk_size - chunk_overlap
    
    scenes = [
        {"start": 0.0, "end": 50.0},
        {"start": 289.0, "end": 295.0},
        {"start": 290.0, "end": 310.0},
        {"start": 300.0, "end": 350.0},
        {"start": 580.0, "end": 610.0},
    ]
    
    grouped = {}
    for scene in scenes:
        window_idx = int(scene["start"] // step)
        grouped.setdefault(window_idx, []).append(scene)
        
    # Expect:
    # 0.0 -> window 0
    # 289.0 -> window 0 (289 // 290 = 0)
    # 290.0 -> window 1 (290 // 290 = 1)
    # 300.0 -> window 1 (300 // 290 = 1)
    # 580.0 -> window 2 (580 // 290 = 2)
    assert len(grouped[0]) == 2
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1


def test_checkpoint_read_write(tmp_path):
    checkpoint_path = tmp_path / "progressive_ingestion_state.json"
    
    state_record = {
        "run_id": "test_run",
        "video_hash": "test_hash",
        "window_idx": 2,
        "window_start": 580.0,
        "window_end": 880.0,
        "scene_ids_committed": ["s1", "s2"],
        "main_db_committed": True,
        "kg_db_committed": True,
        "vectors_committed": True,
        "manifest_updated": True,
        "temporal_index_updated": True,
    }
    
    atomic_write_json(checkpoint_path, state_record)
    assert checkpoint_path.exists()
    
    loaded = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "test_run"
    assert loaded["window_idx"] == 2


def test_mirror_scene_vector_status_incremental():
    # Verify that visual embeddings status mirroring does not overwrite
    # other scenes' status flags if they were not in the current batch
    scenes = [
        {"id": "scene_1", "qdrant_ok": True, "faiss_ok": True},
        {"id": "scene_2", "qdrant_ok": False, "faiss_ok": False},
        {"id": "scene_3", "qdrant_ok": "not_attempted", "faiss_ok": "not_attempted"},
    ]
    
    pooled_clip = {"scene_2": True}
    pooled_dino = {"scene_2": True}
    
    _mirror_scene_vector_status(
        scenes,
        pooled_clip=pooled_clip,
        pooled_dino=pooled_dino,
        qdrant_ok=True,
        faiss_ok=True
    )
    
    # scene_1 should be completely untouched
    assert scenes[0]["qdrant_ok"] is True
    # scene_2 should be updated
    assert scenes[1]["qdrant_ok"] is True
    # scene_3 should be completely untouched
    assert scenes[2]["qdrant_ok"] == "not_attempted"
