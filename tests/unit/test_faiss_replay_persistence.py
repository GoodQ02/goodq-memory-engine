"""Exercise real HNSW identity and disk persistence across retries."""
from pathlib import Path

import numpy as np
import pytest

from steps.common.faiss_utils import add_with_required_ids, create_hnsw_id_index
from steps.common.memory_stores import FaissMemory


def test_repeated_ids_replace_vectors_and_preserve_unrelated_ids():
    faiss = pytest.importorskip("faiss")
    index = create_hnsw_id_index(faiss, 2)
    add_with_required_ids(index, np.array([[1, 0], [0, 1]], dtype="float32"), np.array([11, 12], dtype="int64"))
    add_with_required_ids(index, np.array([[2, 0], [3, 0], [0, 3]], dtype="float32"), np.array([11, 11, 13], dtype="int64"))

    assert index.ntotal == 3
    assert set(faiss.vector_to_array(index.id_map)) == {11, 12, 13}
    np.testing.assert_array_equal(index.reconstruct(11), [3, 0])
    np.testing.assert_array_equal(index.reconstruct(12), [0, 1])
    np.testing.assert_array_equal(index.reconstruct(13), [0, 3])


def test_replay_repairs_existing_duplicates_only_for_its_ids():
    faiss = pytest.importorskip("faiss")
    index = create_hnsw_id_index(faiss, 2)
    # Reproduce an index left by the historical append-only writer.
    index.add_with_ids(np.array([[1, 0], [2, 0], [0, 1], [0, 2]], dtype="float32"), np.array([11, 11, 12, 12], dtype="int64"))
    add_with_required_ids(index, np.array([[3, 0]], dtype="float32"), np.array([11], dtype="int64"))

    assert index.ntotal == 3
    assert faiss.vector_to_array(index.id_map).tolist().count(11) == 1
    assert faiss.vector_to_array(index.id_map).tolist().count(12) == 2
    np.testing.assert_array_equal(index.reconstruct(11), [3, 0])
    np.testing.assert_array_equal(index.reconstruct(12), [0, 2])


def test_identical_replay_preserves_hnsw_without_rebuilding(monkeypatch):
    faiss = pytest.importorskip("faiss")
    index = create_hnsw_id_index(faiss, 2)
    vectors, ids = np.array([[1, 0]], dtype="float32"), np.array([11], dtype="int64")
    add_with_required_ids(index, vectors, ids)

    def unexpected_reset():
        raise AssertionError("an unchanged replay must not rebuild the graph")

    monkeypatch.setattr(index, "reset", unexpected_reset)
    add_with_required_ids(index, vectors, ids)
    assert index.ntotal == 1


def test_faiss_memory_replay_persists_latest_vector(tmp_path: Path):
    faiss = pytest.importorskip("faiss")
    path = tmp_path / "replay.index"
    store = FaissMemory(str(path), 2)
    assert store.insert([{"id": 11, "vector": [1, 0]}]) is True
    assert store.insert([{"id": 11, "vector": [2, 0]}]) is True
    reopened = faiss.read_index(str(path))
    assert reopened.ntotal == 1
    np.testing.assert_array_equal(reopened.reconstruct(11), [2, 0])


def test_failed_faiss_serialization_preserves_previous_disk_index(tmp_path, monkeypatch):
    faiss = pytest.importorskip("faiss")
    path = tmp_path / "durable.index"
    store = FaissMemory(str(path), 2)
    assert store.insert([{"id": 11, "vector": [1, 0]}]) is True
    before = path.read_bytes()

    def interrupted_write(_index, destination):
        Path(destination).write_bytes(b"incomplete serialized index")
        raise OSError("fixture interrupted write")

    monkeypatch.setattr(faiss, "write_index", interrupted_write)
    assert store.insert([{"id": 12, "vector": [0, 1]}]) is False
    assert path.read_bytes() == before
    assert faiss.read_index(str(path)).ntotal == 1
