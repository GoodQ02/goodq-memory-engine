from __future__ import annotations

import sys
import types

import pytest

from steps.common.faiss_utils import add_with_required_ids, create_hnsw_id_index
from steps.common.memory import to_faiss_id
from steps.common.memory_stores import FaissMemory


class _FakeIndex:
    def __init__(self):
        self.added_ids = None

    def add_with_ids(self, vecs, ids):
        self.added_ids = ids

    def add(self, vecs):
        self.added_ids = None


class _FakeFaiss:
    def __init__(self):
        self.write_calls = 0

    def write_index(self, index, path):
        self.write_calls += 1


def test_faiss_id_mapping_is_deterministic_and_insert_accepts_string_id(monkeypatch, tmp_path):
    scene_id = "scene_0000_clip"

    mapped_1 = to_faiss_id(scene_id)
    mapped_2 = to_faiss_id(scene_id)

    assert isinstance(mapped_1, int)
    assert mapped_1 == mapped_2
    assert 0 <= mapped_1 < (1 << 63)

    # Numeric IDs preserve legacy behavior.
    assert to_faiss_id("42") == 42
    assert to_faiss_id(42) == 42

    fake_index = _FakeIndex()
    fake_faiss = _FakeFaiss()

    store = FaissMemory(index_path=str(tmp_path / "memory.index"), dim=4)
    monkeypatch.setattr(store, "_load_index", lambda: (fake_index, fake_faiss))

    ok = store.insert([
        {
            "id": scene_id,
            "vector": [0.1, 0.2, 0.3, 0.4],
            "payload": {"scene_id": "scene_0000", "modality": "clip"},
        }
    ])

    assert ok is True
    assert fake_index.added_ids is not None
    assert int(fake_index.added_ids[0]) == mapped_1


def test_faiss_memory_new_hnsw_index_is_id_mapped(monkeypatch, tmp_path):
    index_path = tmp_path / "memory.index"
    scene_id = "scene_0000_clip"

    class _FakeHnswIndex:
        def __init__(self, dim, links):
            self.dim = dim
            self.links = links
            self.hnsw = types.SimpleNamespace(efConstruction=None, efSearch=None)

        def add_with_ids(self, _vecs, _ids):
            raise RuntimeError("add_with_ids not implemented for raw HNSW")

    class _FakeIdMapIndex:
        def __init__(self, base):
            self.base = base
            self.ntotal = 0
            self.added_ids = None

        def add_with_ids(self, _vecs, ids):
            self.added_ids = ids
            self.ntotal += 1

    fake_faiss = types.ModuleType("faiss")
    fake_faiss.IndexHNSWFlat = _FakeHnswIndex
    fake_faiss.IndexIDMap2 = _FakeIdMapIndex
    fake_faiss.written_index = None

    def _write_index(index, _path):
        fake_faiss.written_index = index

    fake_faiss.write_index = _write_index
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)

    store = FaissMemory(index_path=str(index_path), dim=4)
    ok = store.insert([
        {
            "id": scene_id,
            "vector": [0.1, 0.2, 0.3, 0.4],
            "payload": {"scene_id": "scene_0000", "modality": "clip"},
        }
    ])

    assert ok is True
    assert isinstance(fake_faiss.written_index, _FakeIdMapIndex)
    assert fake_faiss.written_index.added_ids is not None
    assert int(fake_faiss.written_index.added_ids[0]) == to_faiss_id(scene_id)


def test_create_hnsw_id_index_requires_id_map_support():
    class _FakeHnswIndex:
        def __init__(self, dim, links):
            self.dim = dim
            self.links = links
            self.hnsw = types.SimpleNamespace(efConstruction=None, efSearch=None)

    fake_faiss = types.SimpleNamespace(IndexHNSWFlat=_FakeHnswIndex)

    with pytest.raises(RuntimeError, match="faiss_index_id_map_unavailable"):
        create_hnsw_id_index(fake_faiss, 4)


def test_add_with_required_ids_rejects_plain_hnsw():
    class _PlainIndex:
        def add(self, _vecs):
            raise AssertionError("plain add must not be used for stable-ID writes")

    with pytest.raises(RuntimeError, match="faiss_index_lacks_add_with_ids"):
        add_with_required_ids(_PlainIndex(), [[0.1, 0.2]], [42])


def test_add_with_required_ids_wraps_add_with_ids_failure():
    class _RawHnswLikeIndex:
        def add_with_ids(self, _vecs, _ids):
            raise RuntimeError("add_with_ids not implemented for this index")

    with pytest.raises(RuntimeError, match="faiss_add_with_ids_failed"):
        add_with_required_ids(_RawHnswLikeIndex(), [[0.1, 0.2]], [42])


def test_add_with_required_ids_rejects_vector_id_mismatch():
    class _IdMapIndex:
        def add_with_ids(self, _vecs, _ids):
            raise AssertionError("mismatched vector/id counts must fail before FAISS")

    with pytest.raises(RuntimeError, match="faiss_id_count_mismatch"):
        add_with_required_ids(_IdMapIndex(), [[0.1, 0.2], [0.3, 0.4]], [42])


def test_faiss_memory_rejects_vectors_without_explicit_ids(monkeypatch, tmp_path):
    fake_index = _FakeIndex()
    fake_faiss = _FakeFaiss()

    store = FaissMemory(index_path=str(tmp_path / "memory.index"), dim=4)
    monkeypatch.setattr(store, "_load_index", lambda: (fake_index, fake_faiss))

    ok = store.insert([
        {
            "vector": [0.1, 0.2, 0.3, 0.4],
            "payload": {"scene_id": "scene_0000", "modality": "clip"},
        }
    ])

    assert ok is False
    assert fake_index.added_ids is None
    assert fake_faiss.write_calls == 0
