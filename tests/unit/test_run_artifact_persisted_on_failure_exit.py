from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest


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

        class _DummyExit(Exception):
            def __init__(self, code: int = 1):
                super().__init__(f"exit:{code}")
                self.exit_code = code

        typer.Typer = _DummyTyper
        typer.Option = lambda default=None, *args, **kwargs: default
        typer.echo = lambda *args, **kwargs: None
        typer.BadParameter = Exception
        typer.Exit = _DummyExit
        sys.modules["typer"] = typer

    return importlib.import_module("cli.run_ingestion")


def test_run_artifact_written_before_failure_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        "phase6": {"enabled": False},
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

    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "load_configs", lambda *_: cfg_template)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "ffmpeg")
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *a, **k: stored_scenes)
    monkeypatch.setattr(run_ingestion, "_compute_sha256", lambda *a, **k: "videohash")
    monkeypatch.setattr(run_ingestion, "ensure_scene", lambda *a, **k: "scene_0000")
    monkeypatch.setattr(run_ingestion, "scene_has_materialized", lambda *a, **k: {"keyframe": False, "audio": False})
    monkeypatch.setattr(run_ingestion, "get_scene_meta", lambda *a, **k: {})
    monkeypatch.setattr(run_ingestion, "register_scene_bundle", lambda *a, **k: {"status": "ok"})
    monkeypatch.setattr(run_ingestion, "_build_knowledge_graph_from_results", lambda *a, **k: None)
    def _raise_frame(*args, **kwargs):
        raise RuntimeError("frame_fail")

    def _raise_audio(*args, **kwargs):
        raise RuntimeError("audio_fail")

    monkeypatch.setattr(run_ingestion, "_process_frame", _raise_frame)
    monkeypatch.setattr(run_ingestion, "_process_audio", _raise_audio)

    typer_mod = importlib.import_module("typer")
    with pytest.raises(typer_mod.Exit):
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

    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert payload
    scene_errors = payload[0]["scenes"][0].get("errors", {})
    assert "frame" in scene_errors
    assert "audio" in scene_errors
