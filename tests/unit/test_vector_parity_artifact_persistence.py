from __future__ import annotations

from pathlib import Path

import numpy as np

from steps.common import memory


def test_register_scene_bundle_reports_summary_vector_parity(monkeypatch, tmp_path: Path) -> None:
    cfg = {"paths": {"db_path": str(tmp_path / "memory.db")}}
    inserted = []

    class _SummaryEncoder:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 384), dtype="float32")

    class _StubRouter:
        def __init__(self):
            self.stores = {}

        def insert(self, points):
            inserted.extend(points)
            return {"qdrant": True, "faiss": False}

    monkeypatch.setattr("steps.common.memory_manager.build_memory_router", lambda _cfg: _StubRouter())
    monkeypatch.setattr("steps.text_embed.step._load_st", lambda: _SummaryEncoder())

    result = memory.register_scene_bundle(
        cfg,
        video_hash="video_hash_1",
        scene={"start": 0.0, "end": 1.0, "index": 0},
        scene_id="scene_0000",
        frame={"data": {"caption": "A person enters a room."}},
    )

    assert len(inserted) == 1
    assert len(inserted[0]["vector"]) == 384
    assert inserted[0]["payload"]["modality"] == "text"
    assert inserted[0]["payload"]["embedding_source"] == "scene_summary"
    assert result["vector_points_attempted"] == 1
    assert result["vector_store_results"] == {"qdrant": True, "faiss": False}
    assert result["qdrant_ok"] is True
    assert result["faiss_ok"] is False
