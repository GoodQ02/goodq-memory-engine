from __future__ import annotations

from typing import Any, Dict, List, Optional

import steps.common.memory_manager as memory_manager
from steps.common.memory_router import MemoryRouter
from steps.common.memory_store import MemoryConfig, MemoryDims
from steps.common import memory_stores


class _DummyStore:
    def __init__(self, hits: Optional[List[Dict[str, Any]]] = None):
        self.hits = hits or []
        self.inserted: list[list[dict[str, Any]]] = []

    def insert(self, vectors: List[Dict[str, Any]]) -> bool:
        self.inserted.append(vectors)
        return True

    def query(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.hits[:top_k]

    def stats(self) -> Dict[str, Any]:
        return {"available": True}


def test_build_memory_router_normalizes_legacy_chroma_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        memory_manager,
        "build_text_stores",
        lambda _cfg: {
            "qdrant": _DummyStore(),
            "faiss": _DummyStore(),
            "ephemeral": _DummyStore(),
        },
    )

    router = memory_manager.build_memory_router(
        {
            "memory": {
                "routing": {
                    "read_priority": ["qdrant", "faiss", "chroma"],
                    "write_targets": ["chroma", "qdrant"],
                }
            }
        }
    )

    assert router.config.read_priority == ["qdrant", "faiss", "ephemeral"]
    assert router.config.write_targets == ["ephemeral", "qdrant"]


def test_memory_router_resolves_legacy_chroma_reads_to_ephemeral_store() -> None:
    router = MemoryRouter(
        {
            "ephemeral": _DummyStore(
                hits=[{"id": "scene-1", "score": 0.9, "payload": {"scene_id": "scene-1"}}]
            )
        },
        config=MemoryConfig(
            read_priority=["chroma"],
            write_targets=["qdrant"],
            dims=MemoryDims(text=3, image=3, audio=3),
        ),
    )

    hits = router.query([0.1, 0.2, 0.3], top_k=1)

    assert len(hits) == 1
    assert hits[0]["id"] == "scene-1"
    assert router.stats()["routing"]["read_priority"] == ["ephemeral"]


def test_ephemeral_memory_logs_truthful_store_names(monkeypatch) -> None:
    emitted = {}

    def _capture(db_path, events, *, policy):
        emitted["events"] = events
        emitted["policy"] = policy

    monkeypatch.setattr(memory_stores, "emit_retrieval_events", _capture)

    cache = memory_stores.EphemeralMemory(dim=3, ttl_seconds=30, max_items=8)
    cache.insert(
        [
            {
                "id": "hit-1",
                "vector": [1.0, 0.0, 0.0],
                "payload": {"scene_id": "scene-1", "modality": "text"},
            }
        ]
    )

    hits = cache.query([1.0, 0.0, 0.0], top_k=1)

    assert len(hits) == 1
    assert emitted["events"][0].store == "ephemeral"
    assert emitted["events"][0].details["store_type"] == "ephemeral_cache"
    assert emitted["events"][0].details["store_ref"] == "ephemeral_memory"
    assert emitted["policy"] is cache.retrieval_event_policy
