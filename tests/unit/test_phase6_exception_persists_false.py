from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from steps.video.scene_visual_embeddings import run_scene_visual_embeddings


def test_phase6_exception_persists_false(monkeypatch, tmp_path: Path):
    video_id = "v_exception"
    processing_root = tmp_path / "processing"
    manifest_dir = processing_root / video_id / "video"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"0")
    frame_path = manifest_dir / "scene_0000.jpg"
    frame_path.write_bytes(b"frame")

    manifest_path = manifest_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "video_id": video_id,
                "phase6_complete": True,
                "phase6_status": "complete",
                "scenes": [
                    {
                        "scene_id": "scene_0",
                        "id": "scene_0",
                        "index": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "confidence": 0.9,
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    mod_extractor = types.ModuleType("steps.video.scene_frame_extractor")
    mod_embedder = types.ModuleType("steps.video.scene_embedder")
    mod_pooler = types.ModuleType("steps.video.embedding_pooler")
    mod_qdrant = types.ModuleType("steps.common.qdrant_client")

    def _extract_scene_frames(**kwargs):
        return {"scene_0": [{"path": str(frame_path)}]}

    def _embed_scene_frames(*args, **kwargs):
        raise RuntimeError("forced_phase6_core_exception")

    def _pool_multiple_scenes(*args, **kwargs):
        return {}

    class _QdrantConfig:
        def __init__(self, host, collection, dim, distance="Cosine"):
            self.host = host
            self.collection = collection
            self.dim = dim
            self.distance = distance

    class _QdrantClient:
        def __init__(self, cfg):
            self.cfg = cfg

        def upsert(self, points):
            return True

    mod_extractor.extract_scene_frames = _extract_scene_frames
    mod_embedder.embed_scene_frames = _embed_scene_frames
    mod_embedder._MODELS = {"clip": {"model": object()}, "dino": {"model": object()}}
    mod_pooler.pool_multiple_scenes = _pool_multiple_scenes
    mod_qdrant.QdrantConfig = _QdrantConfig
    mod_qdrant.QdrantClient = _QdrantClient

    monkeypatch.setitem(sys.modules, "steps.video.scene_frame_extractor", mod_extractor)
    monkeypatch.setitem(sys.modules, "steps.video.scene_embedder", mod_embedder)
    monkeypatch.setitem(sys.modules, "steps.video.embedding_pooler", mod_pooler)
    monkeypatch.setitem(sys.modules, "steps.common.qdrant_client", mod_qdrant)

    item = {"id": video_id, "source_path": str(video_path)}
    cfg = {
        "paths": {"processing": str(processing_root)},
        "phase6": {
            "enabled": True,
            "retrieval": {"enable": False},
        },
    }

    result = run_scene_visual_embeddings(item, cfg)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["phase6_status"] == "failed"
    assert result["error"] == "exception"
    assert result["exc_type"] == "RuntimeError"

    assert manifest["phase6_complete"] is False
    assert manifest["phase6_status"] == "failed"
    assert "exception" in str(manifest.get("phase6_error", ""))
