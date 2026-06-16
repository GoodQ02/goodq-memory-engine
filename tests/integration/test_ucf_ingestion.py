#!/usr/bin/env python3
"""
Integration test for UCF ingestion.
Verifies that media sources and context frames are properly logged
to the UCF database, and range overlap queries function correctly.
"""

import sys
import os
from pathlib import Path
from steps.common.config_loader import load_configs

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_ucf_ledger():
    import importlib.util
    import sys
    
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


def test_ucf_ingestion_ledger():
    cfg = load_configs({})
    db_dir = cfg.get('paths', {}).get('db_dir')
    assert db_dir is not None, "paths.db_dir must be configured"
    epoch = os.path.basename(db_dir)
    
    data_root = os.getenv("GOODQ_DATA_ROOT") or cfg.get('paths', {}).get('data_root')
    ucf_db_path = Path(db_dir) / 'ucf' / 'ucf_ledger.db'
    
    # Assert database file exists
    assert ucf_db_path.exists(), f"UCF ledger database not found at {ucf_db_path}"
    
    # Access the DB tables using UCFLedgerClient loaded dynamically
    ucf_module = _load_ucf_ledger()
    UCFLedgerClient = ucf_module.UCFLedgerClient
    
    client = UCFLedgerClient(str(ucf_db_path))
    try:
        # Check media_sources
        cursor = client.execute_with_retry("SELECT video_hash, file_path, duration, fps, width, height FROM media_sources")
        media_sources = cursor.fetchall()
        assert len(media_sources) >= 1, "At least one registered media source must exist"
        
        # Verify attributes for at least one registered media source
        found_target = False
        target_video_hash = None
        for row in media_sources:
            video_hash, file_path, duration, fps, width, height = row
            if "05x14 - The Marine Biologist.mp4" in os.path.basename(file_path):
                found_target = True
                target_video_hash = video_hash
                assert duration > 0, f"Duration must be greater than 0, got {duration}"
                assert fps > 0, f"FPS must be greater than 0, got {fps}"
                assert width > 0, f"Width must be greater than 0, got {width}"
                assert height > 0, f"Height must be greater than 0, got {height}"
                break
        
        assert found_target, "Target media source '05x14 - The Marine Biologist.mp4' not found in media_sources"
        
        # Check context_frames
        cursor_cf = client.execute_with_retry(
            """
            SELECT video_hash, ucf_schema_version, t_start, t_end, modality, worker_name, promotion_status
            FROM context_frames
            WHERE video_hash = ?
            """,
            (target_video_hash,)
        )
        context_frames = cursor_cf.fetchall()
        assert len(context_frames) >= 1, f"No context frames found for video_hash {target_video_hash}"
        
        found_staged_video_frame = False
        test_start = None
        test_end = None
        for cf in context_frames:
            v_hash, version, t_start, t_end, modality, worker, status = cf
            if version == "ucf.v0.1" and modality == "video" and worker == "video_scene_detect" and status == "staged":
                found_staged_video_frame = True
                assert t_start >= 0.0, f"Start timestamp must be non-negative, got {t_start}"
                assert t_end >= t_start, f"End timestamp must be after start timestamp, got t_start={t_start}, t_end={t_end}"
                test_start = t_start
                test_end = t_end
                break
                
        assert found_staged_video_frame, "No context frame found matching the required criteria (ucf.v0.1, video, video_scene_detect, staged)"
        
        # Test range overlap queries using client.query_overlap to confirm overlapping records are correctly retrieved.
        query_start = test_start
        query_end = test_end
        
        overlap_results = client.query_overlap(
            video_hash=target_video_hash,
            t_start=query_start,
            t_end=query_end,
            modality="video"
        )
        assert len(overlap_results) >= 1, f"Overlap query failed to retrieve overlapping frames in [{query_start}, {query_end}]"
        
        # Verify the retrieved frame details
        retrieved_frame = overlap_results[0]
        assert retrieved_frame["ucf_schema_version"] == "ucf.v0.1"
        assert retrieved_frame["modality"] == "video"
        assert retrieved_frame["worker_name"] == "video_scene_detect"
        assert retrieved_frame["promotion_status"] == "staged"
        assert retrieved_frame["t_start"] == test_start
        assert retrieved_frame["t_end"] == test_end
        
        # Test query_overlap with a non-overlapping range
        no_overlap_results = client.query_overlap(
            video_hash=target_video_hash,
            t_start=test_end + 1000.0,
            t_end=test_end + 1010.0,
            modality="video"
        )
        assert len(no_overlap_results) == 0, f"Overlap query returned results for non-overlapping range"
        
    finally:
        client.close()
