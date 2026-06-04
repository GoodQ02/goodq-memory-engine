from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

from steps.video.scene_visual_embeddings import run_scene_visual_embeddings


def _load_run_ingestion_module():
    try:
        importlib.import_module("typer")
    except ModuleNotFoundError:
        typer = types.ModuleType("typer")

        class _DummyTyper:
            def __init__(self, *args, **kwargs):
                pass

            def command(self, *args, **kwargs):
                def _decorator(fn):
                    return fn

                return _decorator

        typer.Typer = _DummyTyper
        typer.Option = lambda default=None, *args, **kwargs: default
        typer.echo = lambda *args, **kwargs: None
        typer.BadParameter = Exception
        sys.modules["typer"] = typer

    return importlib.import_module("cli.run_ingestion")


def test_run_artifact_phase6_truth_propagation(monkeypatch, tmp_path: Path):
    for name in (
        "GOODQ_REQUIRE_WSL_AUDIO",
        "GOODQ_REQUIRE_GPU",
        "GOODQ_WSL_DISTRO",
        "GOODQ_WSL_USER",
        "GOODQ_WSL_WORKSPACE",
    ):
        monkeypatch.delenv(name, raising=False)

    run_ingestion = _load_run_ingestion_module()

    input_dir = tmp_path / "inbox"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "demo.mp4").write_bytes(b"v")

    output = tmp_path / "results.json"
    workspace = tmp_path / "workspace"
    processing_root = tmp_path / "processing"

    cfg_template = {
        "paths": {"processing": str(processing_root)},
        "phase6": {"enabled": True},
        "knowledge_graph": {"enabled": False},
    }

    stored_scenes = {
        "scenes": [
            {
                "id": "scene_0000",
                "start": 0.0,
                "end": 1.0,
                "meta": {"index": 0, "duration": 1.0, "confidence": 0.9},
            }
        ],
        "detection_meta": {},
    }

    def _run_step(env_name, step_name, payload, cfg_json):
        if step_name == "scene_visual_embeddings":
            assert env_name == "goodq_image_caption"
            return {"phase6_status": "failed", "error": "vector_commit_failed"}
        if step_name == "cross_modal_harmonization":
            return {"harmonization_status": "complete", "temporal_index_path": None}
        raise AssertionError(f"Unexpected step invocation: {step_name}")

    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "load_configs", lambda *_: cfg_template)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "ffmpeg")
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *a, **k: stored_scenes)
    monkeypatch.setattr(run_ingestion, "_is_video_phase6_complete", lambda *a, **k: True)
    monkeypatch.setattr(run_ingestion, "_compute_sha256", lambda *a, **k: "videohash")
    monkeypatch.setattr(run_ingestion, "ensure_scene", lambda *a, **k: "scene_0000")
    monkeypatch.setattr(run_ingestion, "scene_has_materialized", lambda *a, **k: {"keyframe": True, "audio": True})
    monkeypatch.setattr(
        run_ingestion,
        "get_scene_meta",
        lambda *a, **k: {"keyframe": {"path": "cached_frame.jpg", "hash": "h1"}, "audio": {"path": "cached_audio.wav", "hash": "h2"}},
    )
    monkeypatch.setattr(run_ingestion, "register_scene_bundle", lambda *a, **k: {"status": "ok"})
    monkeypatch.setattr(run_ingestion, "log_step_run", lambda *a, **k: None)
    monkeypatch.setattr(run_ingestion, "_build_knowledge_graph_from_results", lambda *a, **k: None)
    monkeypatch.setattr(run_ingestion, "_run_step", _run_step)

    run_ingestion.run(
        input_dir=input_dir,
        output=output,
        workspace=workspace,
        max_videos=1,
        max_scenes=0,
        scene_threshold=None,
        min_scene_seconds=None,
        force_reprocess=False,
        verbose=False,
        step_timeout=30,
    )

    results = json.loads(output.read_text(encoding="utf-8"))
    assert results
    assert results[0]["phase6_complete"] is False


def test_phase6_early_failure_persists_false(monkeypatch, tmp_path: Path):
    video_id = "v_test"
    processing_root = tmp_path / "processing"
    manifest_dir = processing_root / video_id / "video"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"0")

    manifest_path = manifest_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "video_id": video_id,
                "phase6_complete": True,
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

    mod_extractor.extract_scene_frames = lambda **kwargs: {}
    mod_embedder.embed_scene_frames = lambda *args, **kwargs: {}
    mod_pooler.pool_multiple_scenes = lambda *args, **kwargs: {}

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

    mod_qdrant.QdrantClient = _QdrantClient
    mod_qdrant.QdrantConfig = _QdrantConfig

    monkeypatch.setitem(sys.modules, "steps.video.scene_frame_extractor", mod_extractor)
    monkeypatch.setitem(sys.modules, "steps.video.scene_embedder", mod_embedder)
    monkeypatch.setitem(sys.modules, "steps.video.embedding_pooler", mod_pooler)
    monkeypatch.setitem(sys.modules, "steps.common.qdrant_client", mod_qdrant)

    item = {"id": video_id, "source_path": str(video_path)}
    cfg = {
        "paths": {"processing": str(processing_root)},
        "phase6": {"enabled": True, "retrieval": {"enable": True}},
        "qdrant_host": "http://127.0.0.1:6333",
    }

    result = run_scene_visual_embeddings(item, cfg)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["phase6_status"] == "error"
    assert result["error"] == "frame_extraction_failed"
    assert manifest["phase6_complete"] is False
    assert manifest["phase6_status"] == "failed"
    assert manifest["phase6_error"] == "frame_extraction_failed"
