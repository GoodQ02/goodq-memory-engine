#!/usr/bin/env python3
"""
Integration test for scripts/ucf/validate_ucf_epoch.py.
Verifies the validator rules: Raw Ref Gate, Scene Overlap Gate, and
discretized transcript coverage report metrics (including point events).
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

from scripts.ucf.validate_ucf_epoch import run_validation, is_overlapping, make_scene_hash

def test_is_overlapping():
    # 1. Standard overlap cases (max(start1, start2) < min(end1, end2))
    assert is_overlapping(1.0, 2.0, 1.5, 2.5) is True
    assert is_overlapping(1.0, 2.0, 2.0, 3.0) is False  # Touch but no overlap
    assert is_overlapping(1.0, 2.0, 0.5, 1.0) is False  # Touch but no overlap
    assert is_overlapping(1.0, 2.0, 0.0, 3.0) is True

    # 2. Point event cases
    assert is_overlapping(1.5, 1.5, 1.0, 2.0) is True   # Point inside standard
    assert is_overlapping(1.0, 2.0, 1.5, 1.5) is True   # Standard overlaps point
    assert is_overlapping(1.0, 1.0, 1.0, 2.0) is True   # Point on boundary
    assert is_overlapping(1.0, 2.0, 2.0, 2.0) is True   # Point on boundary
    assert is_overlapping(2.5, 2.5, 1.0, 2.0) is False  # Point outside standard
    assert is_overlapping(1.0, 2.0, 2.5, 2.5) is False  # Standard does not overlap point

def test_ucf_validation_logic(tmp_path, monkeypatch):
    """
    Sets up a mock ucf_ledger database, runs the validation script,
    and asserts the success/failure statuses and coverage report metrics.
    """
    db_dir = tmp_path / "epoch_123"
    db_dir.mkdir()
    
    # Mock configs
    test_cfg = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path)
        }
    }
    
    # Monkeypatch load_configs in validate_ucf_epoch
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.load_configs", lambda x: test_cfg)
    # Monkeypatch REPO_ROOT in validate_ucf_epoch so it writes reports inside tmp_path
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.REPO_ROOT", tmp_path)
    # Monkeypatch environment variable
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    
    # Path where validator expects DB: clean path
    expected_db_dir = tmp_path / "epochs" / "epoch_123" / "ucf"
    expected_db_dir.mkdir(parents=True)
    db_path = expected_db_dir / "ucf_ledger.db"
    
    # Import ucf_ledger dynamically from skill scripts
    ucf_ledger_path = REPO_ROOT / '.agents' / 'skills' / 'ucf-invariant-anchor' / 'scripts' / 'ucf_ledger.py'
    import importlib.util
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    ucf_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ucf_module)
    UCFLedgerClient = ucf_module.UCFLedgerClient
    
    client = UCFLedgerClient(str(db_path))
    client.init_schema()
    
    video_hash = "test_video_hash"
    client.register_media(
        video_hash=video_hash,
        file_path="L:\\_DATA\\test_video.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    scene_hash_1 = make_scene_hash(video_hash, 1.0, 4.0)
    scene_hash_2 = make_scene_hash(video_hash, 5.0, 8.0)

    # Create mock raw transcript files in the expected path
    processing_dir = tmp_path / "epochs" / "epoch_123" / "processing" / "test_video" / "audio"
    processing_dir.mkdir(parents=True)
    raw_file_1 = processing_dir / f"{scene_hash_1}_raw_transcript.json"
    raw_file_1.write_text('[{"text": "hello"}, {"text": "world"}]', encoding="utf-8")
    raw_file_2 = processing_dir / f"{scene_hash_2}_raw_transcript.json"
    raw_file_2.write_text("[]", encoding="utf-8")
    
    # Scene 1: scene_0000 [1.0, 4.0]
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_123",
        run_id="run_1",
        t_start=1.0,
        t_end=4.0,
        modality="video",
        worker_name="video_scene_detect",
        model_tag="scenedetect",
        source_artifact_id="scene_0000",
        payload={"scene_index": 0, "duration": 3.0}
    )
    
    # Scene 2: scene_0001 [5.0, 8.0]
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_123",
        run_id="run_1",
        t_start=5.0,
        t_end=8.0,
        modality="video",
        worker_name="video_scene_detect",
        model_tag="scenedetect",
        source_artifact_id="scene_0001",
        payload={"scene_index": 1, "duration": 3.0}
    )
    
    # Transcript 1: overlaps scene_0000 [1.5, 3.5]
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_123",
        run_id="run_1",
        t_start=1.5,
        t_end=3.5,
        modality="text",
        worker_name="audio_transcribe",
        model_tag="faster_whisper",
        source_artifact_id=scene_hash_1,
        raw_ref=str(raw_file_1),
        payload={"text": "hello"}
    )
    
    # Transcript 2: overlaps scene_0000 [2.0, 3.9]
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_123",
        run_id="run_1",
        t_start=2.0,
        t_end=3.9,
        modality="text",
        worker_name="audio_transcribe",
        model_tag="faster_whisper",
        source_artifact_id=scene_hash_1,
        raw_ref=str(raw_file_1),
        payload={"text": "world"}
    )
    
    client.close()
    
    # Run validation
    ret = run_validation()
    assert ret == 0, "Validation should pass successfully"
    
    # Assert report exists
    report_json_path = tmp_path / "reports" / "ucf_validation_report.json"
    report_md_path = tmp_path / "reports" / "ucf_validation_report.md"
    assert report_json_path.exists()
    assert report_md_path.exists()
    
    # Read validation JSON
    with open(report_json_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["summary"]["success"] is True
    assert report["raw_ref_gate"]["status"] == "passed"
    assert report["scene_overlap_gate"]["status"] == "passed"
    assert report["raw_reconciliation"]["status"] == "passed"
    assert report["absolute_timestamps"]["status"] == "passed"
    
    cov = report["transcript_coverage"]
    per_scene = report["per_scene_coverage"]
    
    assert len(per_scene) == 2
    assert per_scene[0]["scene_id"] == "scene_0000"
    assert per_scene[0]["segment_count"] == 2
    assert per_scene[0]["raw_ref_ok"] is True
    
    assert per_scene[1]["scene_id"] == "scene_0001"
    assert per_scene[1]["segment_count"] == 0
    assert per_scene[1]["raw_ref_ok"] is True
    
    assert cov["silent_scenes_by_type"]["speech_not_detected"] == ["test_video:scene_0001"]
    assert cov["cross_boundary_segments"] == 0
    assert cov["orphan_audio_segments"] == 0
    
    # scene duration: 3.0 + 3.0 = 6.0
    assert abs(cov["total_scene_duration"] - 6.0) < 1e-5
    # transcript duration: (3.5 - 1.5) + (3.9 - 2.0) = 2.0 + 1.9 = 3.9
    assert abs(cov["total_transcript_duration"] - 3.9) < 1e-5
    
    # Check Markdown report output contains percent scene time
    md_content = report_md_path.read_text(encoding="utf-8")
    assert "Percent Scene Time with Transcript" in md_content
    assert "scene_0000" in md_content

def test_ucf_validation_failure_modes(tmp_path, monkeypatch):
    """
    Verifies that the validator registers failures under invalid states
    (e.g., missing raw_ref or non-overlapping transcript).
    """
    db_dir = tmp_path / "epoch_456"
    db_dir.mkdir()
    
    test_cfg = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path)
        }
    }
    
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.load_configs", lambda x: test_cfg)
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.REPO_ROOT", tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    
    expected_db_dir = tmp_path / "epochs" / "epoch_456" / "ucf"
    expected_db_dir.mkdir(parents=True)
    db_path = expected_db_dir / "ucf_ledger.db"
    
    ucf_ledger_path = REPO_ROOT / '.agents' / 'skills' / 'ucf-invariant-anchor' / 'scripts' / 'ucf_ledger.py'
    import importlib.util
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    ucf_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ucf_module)
    UCFLedgerClient = ucf_module.UCFLedgerClient
    
    client = UCFLedgerClient(str(db_path))
    client.init_schema()
    
    video_hash = "test_video_hash"
    client.register_media(
        video_hash=video_hash,
        file_path="L:\\_DATA\\test_video.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    scene_hash_1 = make_scene_hash(video_hash, 1.0, 4.0)

    # Scene 1: scene_0000 [1.0, 4.0]
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_456",
        run_id="run_1",
        t_start=1.0,
        t_end=4.0,
        modality="video",
        worker_name="video_scene_detect",
        model_tag="scenedetect",
        source_artifact_id="scene_0000",
        payload={"scene_index": 0, "duration": 3.0}
    )
    
    # Scene 2: scene_0001 [5.0, 8.0]
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_456",
        run_id="run_1",
        t_start=5.0,
        t_end=8.0,
        modality="video",
        worker_name="video_scene_detect",
        model_tag="scenedetect",
        source_artifact_id="scene_0001",
        payload={"scene_index": 1, "duration": 3.0}
    )

    # Transcript 1: does NOT overlap scene_0000 or scene_0001 [8.5, 9.5]
    # Also, raw_ref file does NOT exist
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_456",
        run_id="run_1",
        t_start=8.5,
        t_end=9.5,
        modality="text",
        worker_name="audio_transcribe",
        model_tag="faster_whisper",
        source_artifact_id=scene_hash_1,
        raw_ref=str(tmp_path / "non_existent.json"),
        payload={"text": "lonely world"}
    )
    
    client.close()
    
    ret = run_validation()
    assert ret == 1, "Validation should fail due to raw_ref and overlap violations"
    
    report_json_path = tmp_path / "reports" / "ucf_validation_report.json"
    with open(report_json_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["summary"]["success"] is False
    assert report["raw_ref_gate"]["status"] == "failed"
    assert report["scene_overlap_gate"]["status"] == "failed"
    assert report["absolute_timestamps"]["status"] == "failed"
    assert report["transcript_coverage"]["silent_scenes_by_type"]["no_audio_stream"] == ["test_video:scene_0001"]
    assert report["transcript_coverage"]["orphan_audio_segments"] == 1
