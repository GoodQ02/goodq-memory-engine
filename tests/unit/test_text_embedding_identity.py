import sqlite3
import re
import pytest

from steps.text_embed import step as text_step


class FakeVectorBatch:
    def astype(self, _dtype):
        return self

    def __getitem__(self, _index):
        return self

    def tolist(self):
        return [0.0] * 384


class FakeModel:
    max_seq_length = 256

    class tokenizer:
        @staticmethod
        def num_special_tokens_to_add(pair=False):
            return 2

        def __new__(cls, text, **kwargs):
            matches = list(re.finditer(r"\S+", text))
            return {"input_ids": list(range(len(matches))),
                    "offset_mapping": [m.span() for m in matches]}

    def encode(self, _texts, normalize_embeddings=True):
        return FakeVectorBatch()


class FakeStore:
    dim = 384

    def __init__(self):
        self.vectors = []

    def insert(self, vectors):
        self.vectors.extend(vectors)
        return True


@pytest.mark.parametrize("kind", ["image", "document", "audio"])
def test_standalone_text_worker_emits_text_vector_with_source_kind(monkeypatch, tmp_path, kind):
    store = FakeStore()
    monkeypatch.setattr(text_step, "_load_st", lambda: FakeModel())
    monkeypatch.setattr(text_step, "build_text_stores", lambda _cfg: {"qdrant": store})
    result = text_step.text_embed({
        "frame_text": "Content extracted from a standalone source.", "source_kind": kind,
        "modality": kind, "scene_id": "canonical-scene", "video_hash": "source-hash",
    }, {"ingestion_isolation": True, "paths": {"db_path": str(tmp_path / "memory.db")}})
    assert result["embedding_meta"]["status"] == "ok"
    payload = store.vectors[0]["payload"]
    assert payload["modality"] == "text" and payload["source_kind"] == kind
    assert payload["scene_id"] == "canonical-scene"
    assert not (tmp_path / "memory.db").exists()


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


def test_long_document_worker_indexes_every_span_without_encoder_truncation(monkeypatch, tmp_path):
    model = FakeModel()
    model.max_seq_length = 18
    encoded = []
    model.encode = lambda texts, **kwargs: (encoded.extend(texts) or FakeVectorBatch())
    store = FakeStore()
    monkeypatch.setattr(text_step, "_load_st", lambda: model)
    monkeypatch.setattr(text_step, "build_text_stores", lambda _cfg: {"qdrant": store})
    text = "  " + " ".join(["early"] + ["repeat"] * 43 + ["middle"] + ["repeat"] * 43 + ["late"]) + "\n"
    result = text_step.text_embed({"frame_text": text, "source_kind": "document",
        "scene_id": "document-scene", "video_hash": "source-hash"},
        {"ingestion_isolation": True, "paths": {"db_path": str(tmp_path / "memory.db")}})
    meta = result["embedding_meta"]
    assert meta["status"] == "ok"
    chunks = meta["embedding_chunks"]
    assert len(chunks) == len(encoded) == len(store.vectors) > 1
    assert all(len(value.split()) <= 16 for value in encoded)
    assert all(any(marker in value for value in encoded) for marker in ("early", "middle", "late"))
    assert chunks[0]["char_start"] == 0 and chunks[-1]["char_end"] == len(text)
    assert all(b["char_start"] <= a["char_end"] for a, b in zip(chunks, chunks[1:]))
    assert len({v["id"] for v in store.vectors}) == len(chunks)
    for index, (chunk, vector) in enumerate(zip(chunks, store.vectors)):
        assert chunk["chunk_index"] == index
        assert text[chunk["char_start"]:chunk["char_end"]] == chunk["text"]
        assert vector["payload"]["document_chunk"]["text"] == chunk["text"]
        assert vector["payload"]["ucf_promotion_status"] == "staged"


def test_document_chunk_identity_keeps_repeated_passages_distinct():
    item = {"frame_text": "Repeated passage", "source_kind": "document",
            "scene_id": "document-scene", "video_hash": "source-hash"}
    a = text_step._text_embedding_identity({**item, "document_chunk": {"chunk_index": 0, "char_start": 0, "char_end": 16}})
    b = text_step._text_embedding_identity({**item, "document_chunk": {"chunk_index": 1, "char_start": 17, "char_end": 33}})
    assert a != b


def test_long_document_partial_vector_write_cannot_report_complete(monkeypatch, tmp_path):
    model = FakeModel()
    model.max_seq_length = 18
    store = FakeStore()
    def insert(vectors):
        store.vectors.extend(vectors)
        return len(store.vectors) < 2
    store.insert = insert
    monkeypatch.setattr(text_step, "_load_st", lambda: model)
    monkeypatch.setattr(text_step, "build_text_stores", lambda _cfg: {"qdrant": store})
    result = text_step.text_embed({"frame_text": "word " * 80, "source_kind": "document",
        "scene_id": "document-scene", "video_hash": "source-hash"},
        {"ingestion_isolation": True, "paths": {"db_path": str(tmp_path / "memory.db")}})
    assert result["embedding_meta"]["status"] == "error"


def test_document_commit_requires_written_durable_stores_not_read_only_cache(monkeypatch, tmp_path):
    model = FakeModel()
    model.max_seq_length = 18
    stores = {key: FakeStore() for key in ("qdrant", "faiss", "ephemeral")}
    monkeypatch.setattr(text_step, "_load_st", lambda: model)
    monkeypatch.setattr(text_step, "build_text_stores", lambda _cfg: stores)
    result = text_step.text_embed({"frame_text": "word " * 80, "source_kind": "document",
        "scene_id": "document-scene", "video_hash": "source-hash"},
        {"ingestion_isolation": True, "paths": {"db_path": str(tmp_path / "memory.db")}})
    assert result["embedding_meta"]["status"] == "ok"
    assert len(stores["qdrant"].vectors) == len(stores["faiss"].vectors) > 1
    assert not stores["ephemeral"].vectors


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
