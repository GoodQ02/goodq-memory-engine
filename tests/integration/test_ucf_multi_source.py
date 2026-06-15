#!/usr/bin/env python3
"""
Integration test for scripts/ucf/validate_ucf_epoch.py multi-source partitioning.
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

def test_ucf_multi_source_happy_path(tmp_path, monkeypatch):
    """
    Verifies that the validator correctly processes and partitions context frames,
    media sources, raw reference checks, reconciliations, and report tables across
    multiple videos in the same epoch, even when scene IDs collide (like scene_0000).
    """
    db_dir = tmp_path / "epoch_multi"
    db_dir.mkdir()
    
    # Mock configs
    test_cfg = {
        "paths": {
            "db_dir": str(db_dir),
            "data_root": str(tmp_path)
        }
    }
    
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.load_configs", lambda x: test_cfg)
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.REPO_ROOT", tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    
    expected_db_dir = tmp_path / "epochs" / "epoch_multi" / "ucf"
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
    
    # Register Video A & Video B
    client.register_media(
        video_hash="hash_video_a",
        file_path="L:\\_DATA\\video_a.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    client.register_media(
        video_hash="hash_video_b",
        file_path="L:\\_DATA\\video_b.mp4",
        duration=12.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    # Generate scene hashes (using make_scene_hash)
    a_hash_0 = make_scene_hash("hash_video_a", 0.0, 5.0)
    a_hash_1 = make_scene_hash("hash_video_a", 5.0, 10.0)
    b_hash_0 = make_scene_hash("hash_video_b", 0.0, 6.0)
    b_hash_1 = make_scene_hash("hash_video_b", 6.0, 12.0)
    
    # Assert scene hashes are distinct despite identical bounds
    assert a_hash_0 != b_hash_0
    
    # Setup mock raw folders and files
    proc_dir_a = tmp_path / "epochs" / "epoch_multi" / "processing" / "video_a" / "audio"
    proc_dir_a.mkdir(parents=True)
    proc_dir_b = tmp_path / "epochs" / "epoch_multi" / "processing" / "video_b" / "audio"
    proc_dir_b.mkdir(parents=True)
    
    # Video A raw files
    raw_tx_a0 = proc_dir_a / f"{a_hash_0}_raw_transcript.json"
    raw_tx_a0.write_text('[{"text": "hello"}, {"text": "a"}]', encoding="utf-8") # 2 segments
    raw_dz_a0 = proc_dir_a / f"{a_hash_0}_raw_diarization.json"
    raw_dz_a0.write_text('[{"speaker": "SPEAKER_00"}]', encoding="utf-8") # 1 turn
    
    raw_tx_a1 = proc_dir_a / f"{a_hash_1}_raw_transcript.json"
    raw_tx_a1.write_text("[]", encoding="utf-8")
    raw_dz_a1 = proc_dir_a / f"{a_hash_1}_raw_diarization.json"
    raw_dz_a1.write_text("[]", encoding="utf-8")
    
    # Video B raw files
    raw_tx_b0 = proc_dir_b / f"{b_hash_0}_raw_transcript.json"
    raw_tx_b0.write_text('[{"text": "world"}]', encoding="utf-8") # 1 segment
    raw_dz_b0 = proc_dir_b / f"{b_hash_0}_raw_diarization.json"
    raw_dz_b0.write_text('[{"speaker": "SPEAKER_01"}, {"speaker": "SPEAKER_02"}]', encoding="utf-8") # 2 turns
    
    raw_tx_b1 = proc_dir_b / f"{b_hash_1}_raw_transcript.json"
    raw_tx_b1.write_text("[]", encoding="utf-8")
    raw_dz_b1 = proc_dir_b / f"{b_hash_1}_raw_diarization.json"
    raw_dz_b1.write_text("[]", encoding="utf-8")
    
    # --- LOG VIDEO A SCENES ---
    client.log_frame("hash_video_a", "epoch_multi", "run_1", 0.0, 5.0, "video", "video_scene_detect", "scenedetect", source_artifact_id="scene_0000", payload={"scene_index": 0})
    client.log_frame("hash_video_a", "epoch_multi", "run_1", 5.0, 10.0, "video", "video_scene_detect", "scenedetect", source_artifact_id="scene_0001", payload={"scene_index": 1})
    
    # --- LOG VIDEO B SCENES ---
    client.log_frame("hash_video_b", "epoch_multi", "run_1", 0.0, 6.0, "video", "video_scene_detect", "scenedetect", source_artifact_id="scene_0000", payload={"scene_index": 0})
    client.log_frame("hash_video_b", "epoch_multi", "run_1", 6.0, 12.0, "video", "video_scene_detect", "scenedetect", source_artifact_id="scene_0001", payload={"scene_index": 1})
    
    # --- LOG VIDEO A AUDIO EVENTS ---
    client.log_frame("hash_video_a", "epoch_multi", "run_1", 0.5, 2.5, "text", "audio_transcribe", "faster_whisper", source_artifact_id=a_hash_0, raw_ref=str(raw_tx_a0), payload={"text": "hello"})
    client.log_frame("hash_video_a", "epoch_multi", "run_1", 3.0, 4.8, "text", "audio_transcribe", "faster_whisper", source_artifact_id=a_hash_0, raw_ref=str(raw_tx_a0), payload={"text": "a"})
    client.log_frame("hash_video_a", "epoch_multi", "run_1", 1.0, 4.0, "audio", "speaker_merge", "pyannote", source_artifact_id=a_hash_0, raw_ref=str(raw_dz_a0), payload={"speaker_id": "SPEAKER_00"})
    
    # --- LOG VIDEO B AUDIO EVENTS ---
    client.log_frame("hash_video_b", "epoch_multi", "run_1", 1.0, 4.0, "text", "audio_transcribe", "faster_whisper", source_artifact_id=b_hash_0, raw_ref=str(raw_tx_b0), payload={"text": "world"})
    client.log_frame("hash_video_b", "epoch_multi", "run_1", 0.5, 3.0, "audio", "speaker_merge", "pyannote", source_artifact_id=b_hash_0, raw_ref=str(raw_dz_b0), payload={"speaker_id": "SPEAKER_01"})
    client.log_frame("hash_video_b", "epoch_multi", "run_1", 3.5, 5.5, "audio", "speaker_merge", "pyannote", source_artifact_id=b_hash_0, raw_ref=str(raw_dz_b0), payload={"speaker_id": "SPEAKER_02"})
    
    client.close()
    
    # Run validation
    ret = run_validation()
    assert ret == 0, "Multi-source happy path validation should pass successfully"
    
    report_json_path = tmp_path / "reports" / "ucf_validation_report.json"
    with open(report_json_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["summary"]["success"] is True
    assert report["summary"]["total_videos_checked"] == 2
    assert report["media_sources_gate"]["status"] == "passed"
    assert report["raw_reconciliation"]["status"] == "passed"
    assert report["absolute_timestamps"]["status"] == "passed"
    
    # Assert shared epoch identifier and single database file path
    assert report["epoch_id"] == "epoch_multi"
    assert Path(report["path_hygiene"]["db_path"]).resolve() == Path(db_path).resolve()
    
    # Ensure correct per-scene stats
    per_scene = report["per_scene_coverage"]
    assert len(per_scene) == 4 # 2 scenes per video, 2 videos
    
    # Filter by video A and B
    a_scenes = [s for s in per_scene if s["video_stem"] == "video_a"]
    b_scenes = [s for s in per_scene if s["video_stem"] == "video_b"]
    
    assert len(a_scenes) == 2
    assert len(b_scenes) == 2
    
    a_scene_0 = [s for s in a_scenes if s["scene_id"] == "scene_0000"][0]
    assert a_scene_0["segment_count"] == 2
    assert a_scene_0["speaker_turn_count"] == 1
    assert a_scene_0["raw_ref_ok"] is True
    
    b_scene_0 = [s for s in b_scenes if s["scene_id"] == "scene_0000"][0]
    assert b_scene_0["segment_count"] == 1
    assert b_scene_0["speaker_turn_count"] == 2
    assert b_scene_0["raw_ref_ok"] is True

def test_ucf_multi_source_unregistered_video_hash_poison_pill(tmp_path, monkeypatch):
    """
    Verifies that a context frame referencing an unregistered video hash fails media_sources_gate.
    """
    db_dir = tmp_path / "epoch_poison"
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
    
    expected_db_dir = tmp_path / "epochs" / "epoch_poison" / "ucf"
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
    
    # Register Video A ONLY
    client.register_media(
        video_hash="hash_video_a",
        file_path="L:\\_DATA\\video_a.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080
    )
    
    # Log a scene detect for Video A (valid)
    client.log_frame("hash_video_a", "epoch_poison", "run_1", 0.0, 5.0, "video", "video_scene_detect", "scenedetect", source_artifact_id="scene_0000", payload={"scene_index": 0})
    
    # Log a scene detect for Video B (UNREGISTERED - POISON PILL!)
    client.log_frame("hash_video_b", "epoch_poison", "run_1", 0.0, 6.0, "video", "video_scene_detect", "scenedetect", source_artifact_id="scene_0000", payload={"scene_index": 0})
    
    client.close()
    
    ret = run_validation()
    assert ret == 1, "Validation should fail due to unregistered video_hash in context frames"
    
    report_json_path = tmp_path / "reports" / "ucf_validation_report.json"
    with open(report_json_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["summary"]["success"] is False
    assert report["media_sources_gate"]["status"] == "failed"
    assert "hash_video_b" in report["media_sources_gate"]["errors"][0]

def test_ucf_multi_source_dirty_duplicate_db_fail(tmp_path, monkeypatch):
    """
    Verifies that a duplicate db in the dirty path triggers path_hygiene_gate failure.
    """
    db_dir = tmp_path / "epoch_dirty"
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
    
    # Create clean db path and db
    expected_db_dir = tmp_path / "epochs" / "epoch_dirty" / "ucf"
    expected_db_dir.mkdir(parents=True)
    db_path = expected_db_dir / "ucf_ledger.db"
    
    # Initialize clean db
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE schema_info (version TEXT)")
    conn.close()
    
    # Create dirty duplicate db file (NOT just empty directory!)
    dirty_ucf_dir = db_dir / "ucf"
    dirty_ucf_dir.mkdir(parents=True)
    dirty_db_file = dirty_ucf_dir / "ucf_ledger.db"
    dirty_db_file.write_text("fake db content", encoding="utf-8")
    
    ret = run_validation()
    assert ret == 1, "Validation should fail due to duplicate dirty db file"
    
    report_json_path = tmp_path / "reports" / "ucf_validation_report.json"
    with open(report_json_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert report["summary"]["success"] is False
    assert report["path_hygiene"]["status"] == "failed"
    assert "duplicate dirty database also exists" in report["path_hygiene"]["errors"][0]
