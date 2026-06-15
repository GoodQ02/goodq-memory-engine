#!/usr/bin/env python3
"""
Stress test for range overlap queries on the UCF ledger.
Verifies boundary conditions, exact matches, containment, and edge cases.
"""

import sys
import os
import sqlite3
import pytest
from pathlib import Path
from steps.common.config_loader import load_configs

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def _load_ucf_ledger():
    import importlib.util
    ucf_ledger_path = REPO_ROOT / '.agents' / 'skills' / 'ucf-invariant-anchor' / 'scripts' / 'ucf_ledger.py'
    if not ucf_ledger_path.exists():
        raise FileNotFoundError(f"ucf_ledger.py not found at {ucf_ledger_path}")
    
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for ucf_ledger at {ucf_ledger_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["ucf_ledger"] = module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def temp_ucf_ledger(tmp_path):
    """Creates a temporary ucf_ledger.db for testing."""
    ucf_module = _load_ucf_ledger()
    db_path = tmp_path / "test_ucf_ledger.db"
    client = ucf_module.UCFLedgerClient(str(db_path))
    client.init_schema()
    
    # Register dummy media
    client.register_media(
        video_hash="test_hash_12345",
        file_path="test_video.mp4",
        duration=100.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    yield client
    client.close()

def test_ledger_range_overlap_scenarios(temp_ucf_ledger):
    client = temp_ucf_ledger
    video_hash = "test_hash_12345"
    epoch = "test_epoch"
    run = "test_run"
    
    # Let's insert a reference event from t=10.0 to t=20.0
    client.log_frame(
        video_hash=video_hash,
        epoch_id=epoch,
        run_id=run,
        t_start=10.0,
        t_end=20.0,
        modality="video",
        worker_name="test_worker",
        model_tag="test_model",
        payload={"label": "reference_event"}
    )
    
    # Let's test the 11 scenarios listed:
    
    # 1. Event before Query (no overlap): Event [10, 20], Query [25, 30]
    res = client.query_overlap(video_hash, 25.0, 30.0)
    assert len(res) == 0, "Query completely after event should return 0 results"
    
    # 2. Event meets Query (touching at start of query): Event [10, 20], Query [20, 25]
    res = client.query_overlap(video_hash, 20.0, 25.0)
    assert len(res) == 0, "Query touching event boundary e_end == q_start should return 0 results"
    
    # 3. Event overlaps start of Query: Event [10, 20], Query [15, 25]
    res = client.query_overlap(video_hash, 15.0, 25.0)
    assert len(res) == 1, "Query overlapping end of event should return 1 result"
    assert res[0]["payload"]["label"] == "reference_event"
    
    # 4. Event starts Query: Event [10, 20], Query [10, 15]
    res = client.query_overlap(video_hash, 10.0, 15.0)
    assert len(res) == 1
    
    # 5. Event during Query (strictly inside): Event [10, 20], Query [5, 25]
    res = client.query_overlap(video_hash, 5.0, 25.0)
    assert len(res) == 1
    
    # 6. Event equals Query: Event [10, 20], Query [10, 20]
    res = client.query_overlap(video_hash, 10.0, 20.0)
    assert len(res) == 1
    
    # 7. Event contains Query: Event [10, 20], Query [12, 18]
    res = client.query_overlap(video_hash, 12.0, 18.0)
    assert len(res) == 1
    
    # 8. Event overlaps end of Query: Event [10, 20], Query [5, 15]
    res = client.query_overlap(video_hash, 5.0, 15.0)
    assert len(res) == 1
    
    # 9. Event finishes Query: Event [10, 20], Query [15, 20]
    res = client.query_overlap(video_hash, 15.0, 20.0)
    assert len(res) == 1
    
    # 10. Event met by Query (touching at end of query): Event [10, 20], Query [5, 10]
    res = client.query_overlap(video_hash, 5.0, 10.0)
    assert len(res) == 0, "Query touching event boundary e_start == q_end should return 0 results"
    
    # 11. Event after Query (no overlap): Event [10, 20], Query [0, 5]
    res = client.query_overlap(video_hash, 0.0, 5.0)
    assert len(res) == 0

def test_point_events_and_queries(temp_ucf_ledger):
    client = temp_ucf_ledger
    video_hash = "test_hash_12345"
    epoch = "test_epoch"
    run = "test_run"
    
    # Log a point event (zero-duration event) at t=15.0
    client.log_frame(
        video_hash=video_hash,
        epoch_id=epoch,
        run_id=run,
        t_start=15.0,
        t_end=15.0,
        modality="video",
        worker_name="test_worker",
        model_tag="test_model",
        payload={"label": "point_event"}
    )
    
    # Query that contains the point event: [14.0, 16.0]
    res = client.query_overlap(video_hash, 14.0, 16.0)
    assert len(res) == 1, "Point event should be matched by query containing it"
    assert res[0]["payload"]["label"] == "point_event"
    
    # Query that ends at the point event: [10.0, 15.0]
    res = client.query_overlap(video_hash, 10.0, 15.0)
    assert len(res) == 0, "Query ending at point event boundary should not overlap"
    
    # Query that starts at the point event: [15.0, 20.0]
    res = client.query_overlap(video_hash, 15.0, 20.0)
    assert len(res) == 0, "Query starting at point event boundary should not overlap"

def test_modality_filtering(temp_ucf_ledger):
    client = temp_ucf_ledger
    video_hash = "test_hash_12345"
    epoch = "test_epoch"
    run = "test_run"
    
    # Log audio event [10, 20]
    client.log_frame(
        video_hash=video_hash,
        epoch_id=epoch,
        run_id=run,
        t_start=10.0,
        t_end=20.0,
        modality="audio",
        worker_name="test_worker",
        model_tag="test_model",
        payload={"label": "audio_event"}
    )
    
    # Log video event [10, 20]
    client.log_frame(
        video_hash=video_hash,
        epoch_id=epoch,
        run_id=run,
        t_start=10.0,
        t_end=20.0,
        modality="video",
        worker_name="test_worker",
        model_tag="test_model",
        payload={"label": "video_event"}
    )
    
    # Query with modality=audio
    res = client.query_overlap(video_hash, 12.0, 18.0, modality="audio")
    assert len(res) == 1
    assert res[0]["payload"]["label"] == "audio_event"
    
    # Query with modality=video
    res = client.query_overlap(video_hash, 12.0, 18.0, modality="video")
    assert len(res) == 1
    assert res[0]["payload"]["label"] == "video_event"
    
    # Query without modality (both should return)
    res = client.query_overlap(video_hash, 12.0, 18.0)
    assert len(res) == 2
