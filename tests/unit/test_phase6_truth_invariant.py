from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from steps.video.scene_visual_embeddings import run_scene_visual_embeddings


class _FakeVec:
    def __init__(self, dim: int):
        self._dim = dim

    def tolist(self):
        return [0.0] * self._dim


def test_phase6_commit_failure_sets_manifest_false(monkeypatch, tmp_path: Path):
    video_id = "v_test"
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
                "scenes": [
                    {
                        "scene_id": "scene_0",
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

    def _embed_scene_frames(scene_frames, model_type="clip", batch_size=8):
        dim = 512 if model_type == "clip" else 768
        return {"scene_0": [[0.0] * dim]}

    def _pool_multiple_scenes(embeddings, strategy="mean"):
        sample = next(iter(embeddings.values()))
        dim = len(sample[0])
        return {"scene_0": _FakeVec(dim)}

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
            # Simulate partial vector commit failure:
            # clip succeeds, dino fails.
            return "dino" not in self.cfg.collection

    mod_extractor.extract_scene_frames = _extract_scene_frames
    mod_embedder.embed_scene_frames = _embed_scene_frames
    mod_embedder._MODELS = {"clip": {"model": object()}, "dino": {"model": object()}}
    mod_pooler.pool_multiple_scenes = _pool_multiple_scenes
    mod_qdrant.QdrantClient = _QdrantClient
    mod_qdrant.QdrantConfig = _QdrantConfig

    monkeypatch.setitem(sys.modules, "steps.video.scene_frame_extractor", mod_extractor)
    monkeypatch.setitem(sys.modules, "steps.video.scene_embedder", mod_embedder)
    monkeypatch.setitem(sys.modules, "steps.video.embedding_pooler", mod_pooler)
    monkeypatch.setitem(sys.modules, "steps.common.qdrant_client", mod_qdrant)

    item = {"id": video_id, "source_path": str(video_path)}
    cfg = {
        "paths": {"processing": str(processing_root)},
        "phase6": {
            "enabled": True,
            "retrieval": {"enable": True},
            "clip_collection": "clip_test",
            "dino_collection": "dino_test",
        },
        "qdrant_host": "http://127.0.0.1:6333",
    }

    result = run_scene_visual_embeddings(item, cfg)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["phase6_status"] == "failed"
    assert result["error"] == "vector_commit_failed"
    assert manifest["phase6_complete"] is False
    assert manifest["phase6_vector_commit"]["clip_committed"] is True
    assert manifest["phase6_vector_commit"]["dino_committed"] is False
    scene_entry = manifest["scenes"][0]
    assert scene_entry["vector_points_attempted"] == 2
    assert scene_entry["qdrant_ok"] is False
    assert scene_entry["faiss_ok"] == "not_attempted"


def test_phase6_missing_visual_modality_sets_manifest_false(monkeypatch, tmp_path: Path):
    video_id = "v_test"
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
                "scenes": [
                    {
                        "scene_id": "scene_0",
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

    def _embed_scene_frames(scene_frames, model_type="clip", batch_size=8):
        dim = 512 if model_type == "clip" else 768
        if model_type == "clip":
            return {}
        return {"scene_0": [[0.0] * dim]}

    def _pool_multiple_scenes(embeddings, strategy="mean"):
        if not embeddings:
            return {}
        sample = next(iter(embeddings.values()))
        dim = len(sample[0])
        return {"scene_0": _FakeVec(dim)}

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
    mod_qdrant.QdrantClient = _QdrantClient
    mod_qdrant.QdrantConfig = _QdrantConfig

    monkeypatch.setitem(sys.modules, "steps.video.scene_frame_extractor", mod_extractor)
    monkeypatch.setitem(sys.modules, "steps.video.scene_embedder", mod_embedder)
    monkeypatch.setitem(sys.modules, "steps.video.embedding_pooler", mod_pooler)
    monkeypatch.setitem(sys.modules, "steps.common.qdrant_client", mod_qdrant)

    item = {"id": video_id, "source_path": str(video_path)}
    cfg = {
        "paths": {"processing": str(processing_root)},
        "phase6": {
            "enabled": True,
            "retrieval": {"enable": True},
            "clip_collection": "clip_test",
            "dino_collection": "dino_test",
        },
        "qdrant": {"host": "http://127.0.0.1:6333"},
    }

    result = run_scene_visual_embeddings(item, cfg)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["phase6_status"] == "failed"
    assert result["error"] == "missing_scene_embeddings"
    assert result["missing_clip_scene_ids"] == ["scene_0"]
    assert manifest["phase6_complete"] is False
    assert manifest["phase6_status"] == "failed"
    assert manifest["phase6_error"] == "missing_scene_embeddings"
    scene_entry = manifest["scenes"][0]
    assert scene_entry["vector_points_attempted"] == 1
    assert scene_entry["qdrant_ok"] is False
    assert scene_entry["faiss_ok"] == "not_attempted"


def test_phase6_uses_nested_qdrant_host(monkeypatch, tmp_path: Path):
    video_id = "v_test"
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
                "scenes": [
                    {
                        "scene_id": "scene_0",
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
    seen_hosts = []

    def _extract_scene_frames(**kwargs):
        return {"scene_0": [{"path": str(frame_path)}]}

    def _embed_scene_frames(scene_frames, model_type="clip", batch_size=8):
        dim = 512 if model_type == "clip" else 768
        return {"scene_0": [[0.0] * dim]}

    def _pool_multiple_scenes(embeddings, strategy="mean"):
        sample = next(iter(embeddings.values()))
        dim = len(sample[0])
        return {"scene_0": _FakeVec(dim)}

    class _QdrantConfig:
        def __init__(self, host, collection, dim, distance="Cosine"):
            self.host = host
            self.collection = collection
            self.dim = dim
            self.distance = distance

    class _QdrantClient:
        def __init__(self, cfg):
            self.cfg = cfg
            seen_hosts.append(cfg.host)

        def upsert(self, points):
            return True

    mod_extractor.extract_scene_frames = _extract_scene_frames
    mod_embedder.embed_scene_frames = _embed_scene_frames
    mod_embedder._MODELS = {"clip": {"model": object()}, "dino": {"model": object()}}
    mod_pooler.pool_multiple_scenes = _pool_multiple_scenes
    mod_qdrant.QdrantClient = _QdrantClient
    mod_qdrant.QdrantConfig = _QdrantConfig

    monkeypatch.setitem(sys.modules, "steps.video.scene_frame_extractor", mod_extractor)
    monkeypatch.setitem(sys.modules, "steps.video.scene_embedder", mod_embedder)
    monkeypatch.setitem(sys.modules, "steps.video.embedding_pooler", mod_pooler)
    monkeypatch.setitem(sys.modules, "steps.common.qdrant_client", mod_qdrant)

    item = {"id": video_id, "source_path": str(video_path)}
    cfg = {
        "paths": {"processing": str(processing_root)},
        "phase6": {
            "enabled": True,
            "retrieval": {"enable": True},
            "clip_collection": "clip_test",
            "dino_collection": "dino_test",
        },
        "qdrant": {"host": "http://10.0.0.9:6333"},
    }

    result = run_scene_visual_embeddings(item, cfg)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["phase6_status"] == "complete"
    assert manifest["phase6_complete"] is True
    assert manifest["phase6_status"] == "complete"
    assert "phase6_error" not in manifest
    assert seen_hosts == ["http://10.0.0.9:6333", "http://10.0.0.9:6333"]
