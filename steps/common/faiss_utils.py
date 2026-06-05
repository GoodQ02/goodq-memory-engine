from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


class FaissLock:
    """A cross-process file lock for FAISS index files using exclusive file creation."""

    def __init__(self, index_path: str | Path, timeout: float = 30.0, delay: float = 0.05):
        if not index_path:
            raise ValueError("index_path must be specified")
        self.lock_path = Path(f"{index_path}.lock")
        self.timeout = timeout
        self.delay = delay
        self.has_lock = False

    def __enter__(self):
        os.makedirs(self.lock_path.parent, exist_ok=True)
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # O_EXCL ensures atomicity across processes and threads
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self.has_lock = True
                return self
            except (FileExistsError, PermissionError):
                # Auto-heal/delete stale lock files older than 60 seconds
                try:
                    if time.time() - self.lock_path.stat().st_mtime > 60.0:
                        try:
                            self.lock_path.unlink()
                        except FileNotFoundError:
                            pass
                except Exception:
                    pass
                time.sleep(self.delay)
        raise TimeoutError(f"Could not acquire lock on {self.lock_path} within {self.timeout} seconds")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.has_lock:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
            self.has_lock = False


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
