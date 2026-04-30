import sqlite3

from steps.text_embed import step as text_step


class FakeVectorBatch:
    def astype(self, _dtype):
        return self

    def __getitem__(self, _index):
        return self

    def tolist(self):
        return [0.0] * 384


class FakeModel:
    def encode(self, _texts, normalize_embeddings=True):
        return FakeVectorBatch()


class FakeStore:
    dim = 384

    def __init__(self):
        self.vectors = []

    def insert(self, vectors):
        self.vectors.extend(vectors)
        return True


def test_scene_scoped_identity_separates_repeated_frame_text():
    content_hash = text_step._content_fingerprint({"frame_text": "Repeated caption", "modality": "frame_text"})
    first = text_step._text_embedding_identity(
        {
            "frame_text": "Repeated caption",
            "modality": "frame_text",
            "video_id": "episode-a",
            "scene_id": "scene_0010",
        },
        content_hash,
    )
    second = text_step._text_embedding_identity(
        {
            "frame_text": "Repeated caption",
            "modality": "frame_text",
            "video_id": "episode-a",
            "scene_id": "scene_0011",
        },
        content_hash,
    )

    assert first != second


def test_unscoped_identity_preserves_content_hash_fallback():
    item = {"frame_text": "Standalone text", "modality": "frame_text"}
    content_hash = text_step._content_fingerprint(item)

    assert text_step._text_embedding_identity(item, content_hash) == content_hash


def test_text_embed_persists_repeated_scene_text_as_distinct_embeddings(monkeypatch, tmp_path):
    store = FakeStore()
    monkeypatch.setattr(text_step, "_load_st", lambda: FakeModel())
    monkeypatch.setattr(text_step, "build_text_stores", lambda _cfg: {"qdrant": store})

    cfg = {"paths": {"db_path": str(tmp_path / "memory.db")}}
    base_item = {
        "frame_text": "The same generated caption appears in neighboring scenes.",
        "modality": "frame_text",
        "source_path": "frame.jpg",
        "video_id": "episode-a",
    }

    first = text_step.text_embed({**base_item, "scene_id": "scene_0010", "scene_index": 10}, cfg)
    second = text_step.text_embed({**base_item, "scene_id": "scene_0011", "scene_index": 11}, cfg)

    assert first["embedding_meta"]["status"] == "ok"
    assert second["embedding_meta"]["status"] == "ok"
    vector_ids = [item["id"] for item in store.vectors]
    assert len(vector_ids) == 2
    assert len(set(vector_ids)) == 2
    assert {item["payload"]["scene_id"] for item in store.vectors} == {"scene_0010", "scene_0011"}
    assert all(item["payload"]["embedding_identity_scope"] == "scene" for item in store.vectors)

    with sqlite3.connect(tmp_path / "memory.db") as conn:
        embedding_rows = conn.execute(
            "SELECT hash, modality, scene_id FROM embeddings ORDER BY scene_id"
        ).fetchall()
        commit_rows = conn.execute(
            "SELECT embedding_id, modality, scene_id FROM memory_commit_events "
            "WHERE component = 'text_embed' ORDER BY scene_id"
        ).fetchall()

    assert embedding_rows == [
        (vector_ids[0], "frame_text", "scene_0010"),
        (vector_ids[1], "frame_text", "scene_0011"),
    ]
    assert commit_rows == [
        (vector_ids[0], "frame_text", "scene_0010"),
        (vector_ids[1], "frame_text", "scene_0011"),
    ]
