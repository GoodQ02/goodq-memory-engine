import os
import time
import json
import uuid
import pytest
from pathlib import Path
from steps.common.faiss_utils import FaissLock

def test_concurrent_acquisition(tmp_path):
    index_path = tmp_path / "test_index"
    
    # Process 1 acquires lock
    lock1 = FaissLock(index_path, timeout=1.0, delay=0.05)
    lock1.acquire()
    assert lock1.has_lock
    assert lock1.lock_path.exists()
    
    # Process 2 attempts to acquire lock, should fail due to timeout
    lock2 = FaissLock(index_path, timeout=0.2, delay=0.05)
    with pytest.raises(TimeoutError):
        lock2.acquire()
        
    lock1.release()
    assert not lock1.has_lock
    assert not lock1.lock_path.exists()
    
    # Now Process 2 can acquire lock
    lock2.acquire()
    assert lock2.has_lock
    lock2.release()


def test_prune_stale_lock_dead_pid(tmp_path, monkeypatch):
    index_path = tmp_path / "test_index"
    lock_path = Path(f"{index_path}.lock")
    
    # Simulate an existing lock with a dead/nonexistent PID (e.g. 999999)
    metadata = {
        "schema_version": 1,
        "lock_id": str(uuid.uuid4()),
        "pid": 999999,
        "hostname": "test-host",
        "process_start_time": time.time(),
        "acquired_at": time.time() - 10,
        "heartbeat": time.time() - 10
    }
    
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)
        
    # FaissLock should inspect this, see PID 999999 is dead, prune it, and acquire successfully
    original_alive = FaissLock._is_process_alive
    def mock_alive(self, pid, start_time):
        if pid == 999999:
            return False
        return original_alive(self, pid, start_time)
        
    monkeypatch.setattr(FaissLock, "_is_process_alive", mock_alive)
    
    lock = FaissLock(index_path, timeout=1.0)
    lock.acquire()
    assert lock.has_lock
    # The lock file should now have our new metadata
    with open(lock_path, "r", encoding="utf-8") as f:
        new_meta = json.load(f)
    assert new_meta["lock_id"] == lock.lock_id
    assert new_meta["pid"] == os.getpid()
    
    lock.release()


def test_corrupt_metadata_handling(tmp_path, monkeypatch):
    index_path = tmp_path / "test_index"
    lock_path = Path(f"{index_path}.lock")
    
    # Write corrupt metadata
    lock_path.write_text("corrupt json text", encoding="utf-8")
    
    # fresh corrupt metadata should NOT be pruned immediately
    lock = FaissLock(index_path, timeout=0.2, delay=0.05)
    with pytest.raises(TimeoutError):
        lock.acquire()
        
    # Now simulate time passing beyond the stale threshold (STALE_AFTER_SECONDS is 120)
    current_time = time.time()
    monkeypatch.setattr(time, "time", lambda: current_time + 130)
    
    # Now lock should be pruned and acquired
    lock.acquire()
    assert lock.has_lock
    lock.release()


def test_heartbeat_updates_metadata(tmp_path):
    index_path = tmp_path / "test_index"
    
    # Instantiate lock with short heartbeat interval for test speed
    lock = FaissLock(index_path, timeout=1.0)
    lock.HEARTBEAT_INTERVAL_SECONDS = 0.1
    
    lock.acquire()
    assert lock.has_lock
    
    # Read initial heartbeat
    initial_hb = lock.metadata["heartbeat"]
    
    # Wait for heartbeat thread to update
    time.sleep(0.3)
    
    # Read metadata from file
    with open(lock.lock_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    assert meta["heartbeat"] > initial_hb
    lock.release()


def test_release_does_not_unlink_others(tmp_path):
    index_path = tmp_path / "test_index"
    
    lock1 = FaissLock(index_path, timeout=1.0)
    lock1.acquire()
    assert lock1.has_lock
    
    # Directly overwrite the lock file with a newer lock metadata (e.g. from process 2)
    meta2 = {
        "schema_version": 1,
        "lock_id": "newer-lock-id",
        "pid": 12345,
        "hostname": "other-host",
        "process_start_time": time.time(),
        "acquired_at": time.time(),
        "heartbeat": time.time()
    }
    with open(lock1.lock_path, "w", encoding="utf-8") as f:
        json.dump(meta2, f)
        
    # Now lock1 releases. It should NOT delete the lock file because lock_id doesn't match
    lock1.release()
    assert lock1.lock_path.exists()
    
    # Cleanup
    lock1.lock_path.unlink()
