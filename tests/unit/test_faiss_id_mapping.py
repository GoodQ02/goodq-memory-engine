from __future__ import annotations

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
