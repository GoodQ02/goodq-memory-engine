from __future__ import annotations

import os
import time
import json
import socket
import uuid
import threading
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None


class FaissLock:
    """A cross-process file lock for FAISS index files using exclusive file creation and JSON metadata heartbeats."""

    HEARTBEAT_INTERVAL_SECONDS = 10
    STALE_AFTER_SECONDS = 120

    def __init__(self, index_path: str | Path, timeout: float = 30.0, delay: float = 0.05):
        if not index_path:
            raise ValueError("index_path must be specified")
        self.lock_path = Path(f"{index_path}.lock")
        self.timeout = timeout
        self.delay = delay
        self.has_lock = False
        self.lock_id = None
        self.metadata = {}
        self._stop_heartbeat_event = None
        self._heartbeat_thread = None

    def __enter__(self):
        self.acquire()
        return self

    def acquire(self):
        os.makedirs(self.lock_path.parent, exist_ok=True)
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # O_EXCL ensures atomicity across processes and threads
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    self.lock_id = str(uuid.uuid4())
                    pid = os.getpid()
                    hostname = socket.gethostname()
                    
                    process_start_time = None
                    if psutil is not None:
                        try:
                            process_start_time = psutil.Process(pid).create_time()
                        except Exception:
                            pass
                    
                    now = time.time()
                    self.metadata = {
                        "schema_version": 1,
                        "lock_id": self.lock_id,
                        "pid": pid,
                        "hostname": hostname,
                        "process_start_time": process_start_time,
                        "acquired_at": now,
                        "heartbeat": now
                    }
                    
                    json_str = json.dumps(self.metadata)
                    os.write(fd, json_str.encode('utf-8'))
                    try:
                        os.fsync(fd)
                    except OSError:
                        pass
                    os.close(fd)
                    
                    self.has_lock = True
                    self._start_heartbeat()
                    return self
                except Exception as e:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    try:
                        self.lock_path.unlink()
                    except Exception:
                        pass
                    raise e
            except (FileExistsError, PermissionError):
                self._check_and_prune_stale_lock()
                time.sleep(self.delay)
        raise TimeoutError(f"Could not acquire lock on {self.lock_path} within {self.timeout} seconds")

    def _check_and_prune_stale_lock(self):
        if not self.lock_path.exists():
            return
        
        try:
            mtime = self.lock_path.stat().st_mtime
        except FileNotFoundError:
            return
            
        metadata = None
        try:
            with open(self.lock_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            # Metadata is corrupt/unreadable.
            # Do NOT immediately delete it unless lock file age exceeds STALE_AFTER_SECONDS.
            if time.time() - mtime > self.STALE_AFTER_SECONDS:
                self._prune("corrupt and older than stale threshold")
            return

        # Validate metadata schema
        if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
            if time.time() - mtime > self.STALE_AFTER_SECONDS:
                self._prune("invalid schema and older than stale threshold")
            return
            
        pid = metadata.get("pid")
        heartbeat = metadata.get("heartbeat", mtime)
        process_start_time = metadata.get("process_start_time")
        
        if not isinstance(pid, int):
            if time.time() - mtime > self.STALE_AFTER_SECONDS:
                self._prune("invalid PID and older than stale threshold")
            return
            
        # Check if the process is dead
        is_alive = self._is_process_alive(pid, process_start_time)
        
        if is_alive is False:
            self._prune(f"owning process {pid} is dead")
        elif is_alive is True:
            if time.time() - heartbeat > self.STALE_AFTER_SECONDS:
                self._prune(f"owning process {pid} is alive but heartbeat is stale")
        else:
            # Liveness cannot be determined. Rely on heartbeat and lock-file age.
            now = time.time()
            if now - heartbeat > self.STALE_AFTER_SECONDS or now - mtime > self.STALE_AFTER_SECONDS:
                self._prune("liveness undetermined and heartbeat/file age is stale")

    def _is_process_alive(self, pid: int, expected_start_time: float | None) -> bool | None:
        """
        Check if process is alive.
        Returns True if alive, False if dead, and None if liveness cannot be determined.
        """
        if psutil is not None:
            try:
                proc = psutil.Process(pid)
                if expected_start_time is not None:
                    try:
                        create_time = proc.create_time()
                        if abs(create_time - expected_start_time) < 2.0:
                            return proc.is_running()
                        else:
                            return False
                    except Exception:
                        return False
                return proc.is_running()
            except psutil.NoSuchProcess:
                return False
            except Exception:
                return None
        
        # Fallback without psutil
        if os.name == 'nt':
            import subprocess
            try:
                proc = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                exists = str(pid) in proc.stdout and "INFO:" not in proc.stdout
                return exists
            except Exception:
                return None
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError as e:
                import errno
                if e.errno == errno.ESRCH:
                    return False
                return True

    def _prune(self, reason: str):
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def _start_heartbeat(self):
        self._stop_heartbeat_event = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f"FaissLockHeartbeat-{self.lock_id}"
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        while not self._stop_heartbeat_event.wait(self.HEARTBEAT_INTERVAL_SECONDS):
            if not self.has_lock:
                break
            try:
                self._update_heartbeat()
            except Exception:
                pass

    def _update_heartbeat(self):
        if not self.has_lock or not self.lock_path.exists():
            return
        
        # Atomically update the lock file
        self.metadata["heartbeat"] = time.time()
        temp_path = self.lock_path.with_suffix(f".tmp.{self.lock_id}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.lock_path)
        except Exception:
            try:
                temp_path.unlink()
            except Exception:
                pass

    def release(self):
        if self._stop_heartbeat_event is not None:
            self._stop_heartbeat_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=0.1)
            
        if self.has_lock:
            try:
                if self.lock_path.exists():
                    try:
                        with open(self.lock_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        if metadata.get("lock_id") == self.lock_id:
                            self.lock_path.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
            self.has_lock = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def create_hnsw_id_index(faiss_module: Any, dim: int, links: int = 32) -> Any:
    """Create a HNSW FAISS index that can accept stable explicit IDs."""
    if not hasattr(faiss_module, "IndexIDMap2"):
        raise RuntimeError("faiss_index_id_map_unavailable")
    base_index = faiss_module.IndexHNSWFlat(dim, links)
    base_index.hnsw.efConstruction = 200
    base_index.hnsw.efSearch = 50
    return faiss_module.IndexIDMap2(base_index)


def add_with_required_ids(index: Any, vectors: Any, ids: Any) -> None:
    """Add vectors to FAISS only when explicit stable IDs are supported."""
    try:
        if len(vectors) != len(ids):
            raise RuntimeError("faiss_id_count_mismatch")
    except TypeError:
        pass
    add_with_ids = getattr(index, "add_with_ids", None)
    if not callable(add_with_ids):
        raise RuntimeError("faiss_index_lacks_add_with_ids")
    try:
        add_with_ids(vectors, ids)
    except Exception as exc:
        raise RuntimeError("faiss_add_with_ids_failed") from exc
