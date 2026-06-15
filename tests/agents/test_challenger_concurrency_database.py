import os
import sys
import time
import pytest
import sqlite3
import hashlib
import json
import numpy as np
from pathlib import Path
import threading

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mini_agent_client import ReentrantFileLock, MiniAgentClient
from scripts.ucf.validate_ucf_epoch import get_video_stem_from_source_path

def _load_ucf_ledger():
    import importlib.util
    ucf_ledger_path = REPO_ROOT / 'scripts' / 'ucf' / 'ucf_ledger.py'
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["ucf_ledger"] = module
    spec.loader.exec_module(module)
    return module

# =====================================================================
# CHALLENGE 1: Windows Lock Contention PermissionError Crash Test
# =====================================================================
def test_reentrant_lock_windows_contention(tmp_path):
    """
    Simulates high concurrency on the lock file to trigger the Windows PermissionError crash
    and verifies that the lock is acquired successfully after the first holder releases it.
    """
    lock_file = tmp_path / "test_concurrency.lock"
    lock = ReentrantFileLock(lock_file)
    
    ready = threading.Event()
    release = threading.Event()
    
    # Acquire lock in thread 1 and hold it
    def hold_lock():
        with lock.lock():
            ready.set()
            release.wait()

    t = threading.Thread(target=hold_lock, daemon=True)
    t.start()
    ready.wait()

    # Thread 2 tries to acquire the lock.
    # It should wait. After a delay, Thread 1 releases the lock.
    lock2 = ReentrantFileLock(lock_file)
    
    def release_after_delay():
        time.sleep(0.1)
        release.set()
        
    t_release = threading.Thread(target=release_after_delay, daemon=True)
    t_release.start()
    
    start = time.time()
    with lock2.lock():
        duration = time.time() - start
        
    assert duration >= 0.1
    t.join()
    t_release.join()


# =====================================================================
# CHALLENGE 2: CLAP ID Map Primary Key Conflict Test
# =====================================================================
def test_clap_id_map_silent_overwrite(tmp_path):
    """
    Verifies that clap_id_map does NOT overwrite mappings for different videos due to lacking video_hash PK.
    """
    from steps.audio_embed_clap.step import _ensure_clap_map
    map_db = tmp_path / "clap_id_map.sqlite"
    _ensure_clap_map(str(map_db))

    conn = sqlite3.connect(str(map_db))
    # Add video 1
    conn.execute(
        "INSERT INTO clap_id_map(video_hash, faiss_id, hash, source_path, created_at) VALUES (?,?,?,?,?)",
        ("video1.mp4", 101, "hash_abc", "video1.mp4", "2026-06-14")
    )
    conn.commit()

    # Add video 2 with same faiss_id (due to prefix collision or hash mod)
    conn.execute(
        "INSERT OR REPLACE INTO clap_id_map(video_hash, faiss_id, hash, source_path, created_at) VALUES (?,?,?,?,?)",
        ("video2.mp4", 101, "hash_xyz", "video2.mp4", "2026-06-14")
    )
    conn.commit()

    # Verify that the mapping for video1 is STILL present (no data loss)
    rows = conn.execute("SELECT source_path FROM clap_id_map WHERE faiss_id = 101 ORDER BY video_hash").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == "video1.mp4"
    assert rows[1][0] == "video2.mp4"
    conn.close()


# =====================================================================
# CHALLENGE 3: Media Registration Overly Strict Tolerance Drift Test
# =====================================================================
def test_media_registration_tolerance_drift(tmp_path):
    """
    Verifies that register_media does NOT raise a ValueError for harmless duration drifts (< 50ms)
    violating the 50ms spec, but still raises for drifts > 50ms.
    """
    ucf_module = _load_ucf_ledger()
    db_path = tmp_path / "ucf_ledger.db"
    client = ucf_module.UCFLedgerClient(str(db_path))
    client.init_schema()

    # Register original video
    client.register_media(
        video_hash="vid_123",
        file_path="vid.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080
    )

    # Re-registering with 2ms duration drift (perfectly safe, well under 50ms limit)
    client.register_media(
        video_hash="vid_123",
        file_path="vid.mp4",
        duration=10.002, # 2ms drift
        fps=30.0,
        width=1920,
        height=1080
    )
    
    # Re-registering with 60ms drift (should fail)
    with pytest.raises(ValueError) as excinfo:
        client.register_media(
            video_hash="vid_123",
            file_path="vid.mp4",
            duration=10.060, # 60ms drift
            fps=30.0,
            width=1920,
            height=1080
        )
    assert "Conflict in structural attributes" in str(excinfo.value)
    client.close()


# =====================================================================
# CHALLENGE 4: Orphan Check Validation Bypass Test
# =====================================================================
def test_scoped_orphan_check_path_bypass():
    """
    Verifies that get_video_stem_from_source_path returns None
    if the source path does not contain the video stem in its parts.
    """
    checked_stems = {"my_video"}
    
    # Scenario A: Standard path -> matches
    stem1 = get_video_stem_from_source_path("C:/data/my_video/frames/001.png", checked_stems)
    assert stem1 == "my_video"

    # Scenario B: Bypassed path -> returns None
    stem2 = get_video_stem_from_source_path("C:/temp/frames/001.png", checked_stems)
    assert stem2 is None
