from __future__ import annotations

from pathlib import Path

from steps.common import memory


def test_register_scene_bundle_persists_vector_parity(monkeypatch, tmp_path: Path) -> None:
    cfg = {"paths": {"db_path": str(tmp_path / "memory.db")}}

    class _StubRouter:
        def __init__(self):
            self.stores = {}

        def insert(self, points):
            return {"qdrant": True, "faiss": False}

    monkeypatch.setattr("steps.common.memory_manager.build_memory_router", lambda _cfg: _StubRouter())

    result = memory.register_scene_bundle(
        cfg,
        video_hash="video_hash_1",
        scene={"start": 0.0, "end": 1.0, "index": 0},
        scene_id="scene_0000",
        frame={"data": {"clip_embedding": [0.1, 0.2]}},
    )

    assert result["vector_points_attempted"] == 1
    assert result["vector_store_results"] == {"qdrant": True, "faiss": False}
    assert result["qdrant_ok"] is True
    assert result["faiss_ok"] is False
