#!/usr/bin/env python3
"""
Integration test for UCF audio logging.
Verifies that the ucf_ledger.db correctly stores audio-related context frames
with correct schema versions, statuses, and payload fields.
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

from steps.common.config_loader import load_configs
from cli.run_ingestion import _log_audio_to_ucf_ledger, _load_ucf_ledger

def test_ucf_audio_logging_mock(tmp_path, monkeypatch):
    """
    Verifies that _log_audio_to_ucf_ledger writes correctly to the ledger
    with correct modality, schema version, flat payloads, and shifted timestamps.
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
            "id": "test_run_audio"
        }
    }
    cfg_json.write_text(json.dumps(cfg_data), encoding="utf-8")
    
    video_hash = "mock_video_hash_audio_123"
    scene_id = "scene_0001"
    
    scene = {
        "start": 10.0,
        "end": 20.0,
        "index": 1
    }
    
    audio_artifact_dir = tmp_path / "audio_artifacts"
    audio_artifact_dir.mkdir()
    
    # Write mock raw transcript and diarization files on disk
    raw_transcript_file = audio_artifact_dir / f"{scene_id}_raw_transcript.json"
    raw_transcript_file.write_text(json.dumps([{"start": 0.5, "end": 2.0, "text": "hello", "logprob": -0.8}]), encoding="utf-8")
    
    raw_diarization_file = audio_artifact_dir / f"{scene_id}_raw_diarization.json"
    raw_diarization_file.write_text(json.dumps([{"start": 0.5, "end": 2.0, "speaker": "SPEAKER_01"}]), encoding="utf-8")
    
    # Mock item with segments and speaker_segments
    # Segment 1: scene-relative (start=0.5 < scene_start - 0.01) -> should be shifted by 10.0
    # Segment 2: absolute (start=12.0 >= scene_start - 0.01) -> should remain 12.0
    item = {
        "transcript": "hello world",
        "language": "en",
        "segments": [
            {"start": 0.5, "end": 2.0, "text": "hello", "logprob": -0.8},
            {"start": 12.0, "end": 14.0, "text": "world", "logprob": -0.2}
        ],
        "speaker_segments": [
            {"start": 0.5, "end": 2.0, "speaker": "SPEAKER_01"},
            {"start": 12.0, "end": 14.0, "speaker": "SPEAKER_02"}
        ]
    }
    
    # Set environment variables for the test
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GOODQ_RUN_ID", "test_run_audio")
    
    # Run the logging function
    _log_audio_to_ucf_ledger(
        cfg_json=cfg_json,
        video_hash=video_hash,
        scene_id=scene_id,
        scene=scene,
        audio_artifact_dir=audio_artifact_dir,
        item=item
    )
    
    # Resolve expected DB path
    expected_db_path = tmp_path / "epochs" / "db" / "ucf" / "ucf_ledger.db"
    assert expected_db_path.exists(), f"UCF database was not created at {expected_db_path}"
    
    # Query database to assert correctness
    conn = sqlite3.connect(str(expected_db_path))
    conn.row_factory = sqlite3.Row
    
    # Check context_frames
    cur = conn.execute(
        """
        SELECT frame_id, video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
               modality, worker_name, model_tag, confidence, raw_ref, payload, promotion_status
        FROM context_frames
        ORDER BY frame_id ASC
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    assert len(rows) == 4, f"Expected 4 logged frames, got {len(rows)}"
    
    # Frame 0: Text segment 1 (shifted: t_start=10.5, t_end=12.0)
    f0 = rows[0]
    assert f0["video_hash"] == video_hash
    assert f0["ucf_schema_version"] == "ucf.v0.1"
    assert f0["epoch_id"] == "db"
    assert f0["run_id"] == "test_run_audio"
    assert abs(f0["t_start"] - 10.5) < 1e-5
    assert abs(f0["t_end"] - 12.0) < 1e-5
    assert f0["modality"] == "text"
    assert f0["worker_name"] == "audio_transcribe"
    assert f0["model_tag"] == "faster_whisper"
    assert f0["raw_ref"] == str(raw_transcript_file.resolve())
    assert f0["promotion_status"] == "staged"
    
    p0 = json.loads(f0["payload"])
    assert p0["text"] == "hello"
    assert p0["language"] == "en"
    assert p0["segment_index"] == 0
    assert p0["word_count"] == 1
    assert abs(p0["confidence"] - (-0.8)) < 1e-5
    assert p0["identity_status"] == "unresolved"
    
    # Frame 1: Text segment 2 (not shifted: t_start=12.0, t_end=14.0)
    f1 = rows[1]
    assert abs(f1["t_start"] - 12.0) < 1e-5
    assert abs(f1["t_end"] - 14.0) < 1e-5
    p1 = json.loads(f1["payload"])
    assert p1["text"] == "world"
    assert p1["segment_index"] == 1
    assert p1["word_count"] == 1
    assert abs(p1["confidence"] - (-0.2)) < 1e-5
    
    # Frame 2: Audio segment 1 (speaker turn 1, shifted: t_start=10.5, t_end=12.0)
    f2 = rows[2]
    assert f2["modality"] == "audio"
    assert f2["worker_name"] == "speaker_merge"
    assert f2["model_tag"] == "pyannote"
    assert f2["raw_ref"] == str(raw_diarization_file.resolve())
    assert abs(f2["t_start"] - 10.5) < 1e-5
    assert abs(f2["t_end"] - 12.0) < 1e-5
    
    p2 = json.loads(f2["payload"])
    assert p2["speaker_id"] == "SPEAKER_01"
    assert p2["speaker_label"] is None
    assert p2["speaker_confidence"] == 1.0
    assert p2["turn_index"] == 0
    assert p2["source"] == "pyannote"
    assert p2["identity_status"] == "unresolved"
    
    # Frame 3: Audio segment 2 (speaker turn 2, not shifted: t_start=12.0, t_end=14.0)
    f3 = rows[3]
    assert abs(f3["t_start"] - 12.0) < 1e-5
    assert abs(f3["t_end"] - 14.0) < 1e-5
    p3 = json.loads(f3["payload"])
    assert p3["speaker_id"] == "SPEAKER_02"
    assert p3["turn_index"] == 1
