#!/usr/bin/env python3
"""
Stress tests for the UCF ledger.

Covers two scenarios:
  1. Range overlap query boundary conditions (exact matches, containment, edge cases).
  2. WAL concurrency: multi-threaded simultaneous writes to a single UCFLedgerClient
     database, verifying no data loss and no unhandled OperationalError.
"""

import sys
import os
import sqlite3
import threading
import pytest
from pathlib import Path
from steps.common.config_loader import load_configs
from scripts.ucf.ucf_ledger import UCFLedgerClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

@pytest.fixture
def temp_ucf_ledger(tmp_path):
    """Creates a temporary ucf_ledger.db for testing."""
    db_path = tmp_path / "test_ucf_ledger.db"
    client = UCFLedgerClient(str(db_path))
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


# ---------------------------------------------------------------------------
# H2 — WAL concurrency stress tests
# ---------------------------------------------------------------------------

class TestUCFWALConcurrency:
    """
    Stress-tests UCFLedgerClient WAL behavior under multi-threaded simultaneous writes.

    Simulates real multi-agent concurrency by opening independent sqlite3 connections
    per thread (mirroring how separate pipeline workers behave in production). Verifies:
      - No data loss under contention (exact row count).
      - No unhandled OperationalError from the retry layer.
    """

    N_THREADS = 8
    FRAMES_PER_THREAD = 10
    EXPECTED_TOTAL = N_THREADS * FRAMES_PER_THREAD  # 80

    @staticmethod
    def _ucf_ledger_module():
        """Load ucf_ledger from the canonical scripts path (not the skill copy)."""
        import importlib.util
        ledger_path = REPO_ROOT / "scripts" / "ucf" / "ucf_ledger.py"
        spec = importlib.util.spec_from_file_location("ucf_ledger_wal", str(ledger_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def _init_db(db_path, mod):
        """Initialise schema and register a shared media source."""
        client = mod.UCFLedgerClient(str(db_path))
        client.init_schema()
        client.register_media(
            video_hash="wal_test_video",
            file_path="wal_test.mp4",
            duration=300.0,
            fps=30.0,
            width=1920,
            height=1080,
        )
        client.close()

    def test_concurrent_writers_no_data_loss(self, tmp_path):
        """
        H2-a: 8 threads × 10 frames each must produce exactly 80 rows.

        Each thread opens its own sqlite3 connection (WAL allows concurrent readers
        and a single writer per checkpoint window). The UCFLedgerClient retry logic
        must absorb any transient 'database is locked' errors transparently.
        """
        mod = self._ucf_ledger_module()
        db_path = tmp_path / "wal_stress.db"
        self._init_db(db_path, mod)

        errors: list = []
        write_lock = threading.Lock()  # Serialise per-thread error list appends only

        def writer(thread_id: int):
            try:
                # Each thread gets its own connection — mirrors real multi-process agents
                conn = sqlite3.connect(str(db_path), timeout=30.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                for i in range(TestUCFWALConcurrency.FRAMES_PER_THREAD):
                    t = float(thread_id * 100 + i)
                    conn.execute(
                        """
                        INSERT INTO context_frames (
                            video_hash, ucf_schema_version, epoch_id, run_id,
                            t_start, t_end, modality, worker_name, model_tag,
                            confidence, spatial_space, payload, payload_hash,
                            promotion_status
                        ) VALUES (
                            'wal_test_video', 'ucf.v0.1', 'wal_epoch', 'wal_run',
                            ?, ?, 'video', 'wal_worker', 'wal_model',
                            1.0, 'normalized_yxyx_top_left', '{}', 'aabbcc',
                            'staged'
                        )
                        """,
                        (t, t + 1.0),
                    )
                    conn.commit()
                conn.close()
            except Exception as exc:
                with write_lock:
                    errors.append((thread_id, str(exc)))

        threads = [
            threading.Thread(target=writer, args=(tid,), name=f"wal-writer-{tid}")
            for tid in range(self.N_THREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        # No thread must have raised an unhandled exception
        assert errors == [], f"WAL writer threads raised errors: {errors}"

        # All threads joined within timeout
        assert all(not t.is_alive() for t in threads), "Some writer threads are still running"

        # Exactly EXPECTED_TOTAL rows must exist — no silent data loss
        conn = sqlite3.connect(str(db_path))
        row_count = conn.execute(
            "SELECT count(*) FROM context_frames WHERE video_hash = 'wal_test_video'"
        ).fetchone()[0]
        conn.close()
        assert row_count == self.EXPECTED_TOTAL, (
            f"Expected {self.EXPECTED_TOTAL} rows after concurrent writes, got {row_count}"
        )

    def test_retry_backoff_under_contention(self, tmp_path):
        """
        H2-b: UCFLedgerClient.execute_with_retry() must absorb contention without leaking OperationalError.

        Each thread creates its own UCFLedgerClient instance (mirroring how separate
        pipeline workers operate in production — sqlite3 connections cannot be shared
        across threads). All 8 clients write to the same WAL database simultaneously.
        The retry layer (5 attempts, random backoff) must ensure all writes complete.
        Exactly N_THREADS rows must exist after all threads finish.
        """
        mod = self._ucf_ledger_module()
        db_path = tmp_path / "wal_retry.db"
        self._init_db(db_path, mod)

        errors: list = []
        write_lock = threading.Lock()

        def retry_writer(thread_id: int):
            # Each thread owns its connection — this is the correct production model.
            # sqlite3 connections cannot be shared across threads.
            client = mod.UCFLedgerClient(str(db_path))
            try:
                t = float(thread_id)
                client.execute_with_retry(
                    """
                    INSERT INTO context_frames (
                        video_hash, ucf_schema_version, epoch_id, run_id,
                        t_start, t_end, modality, worker_name, model_tag,
                        confidence, spatial_space, payload, payload_hash,
                        promotion_status
                    ) VALUES (
                        'wal_test_video', 'ucf.v0.1', 'retry_epoch', 'retry_run',
                        ?, ?, 'audio', 'retry_worker', 'retry_model',
                        1.0, 'normalized_yxyx_top_left', '{}', 'ddeeff',
                        'staged'
                    )
                    """,
                    (t, t + 1.0),
                )
            except Exception as exc:
                with write_lock:
                    errors.append((thread_id, str(exc)))
            finally:
                client.close()

        threads = [
            threading.Thread(target=retry_writer, args=(tid,), name=f"retry-writer-{tid}")
            for tid in range(self.N_THREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        # No OperationalError must have escaped the retry layer
        assert errors == [], f"execute_with_retry leaked errors under contention: {errors}"

        # All threads joined within timeout
        assert all(not t.is_alive() for t in threads), "Some retry writer threads are still running"

        # Exactly N_THREADS rows written — no silent loss
        conn = sqlite3.connect(str(db_path))
        row_count = conn.execute(
            "SELECT count(*) FROM context_frames WHERE epoch_id = 'retry_epoch'"
        ).fetchone()[0]
        conn.close()
        assert row_count == self.N_THREADS, (
            f"Expected {self.N_THREADS} rows from retry writers, got {row_count}"
        )

