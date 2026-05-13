from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path


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


class _FakeTracker:
    def __init__(self) -> None:
        self.started = []
        self.total_steps = []
        self.updated = []
        self.finished = []

    def start_processing(self, filename: str, total_steps: int = 20, run_id: str | None = None):
        self.started.append((filename, total_steps, run_id))

    def set_total_steps(self, total_steps: int):
        self.total_steps.append(total_steps)

    def update_step(self, step_name: str, step_index: int, details=None):
        self.updated.append((step_name, step_index, details or {}))

    def finish_processing(self, status: str = "completed"):
        self.finished.append(status)


def test_run_updates_and_finishes_progress_tracker(monkeypatch, tmp_path: Path):
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

    tracker = _FakeTracker()
    cfg_template = {
        "paths": {"processing": str(processing_root)},
        "phase6": {"enabled": False},
        "knowledge_graph": {"enabled": False},
    }

    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", True)
    monkeypatch.setattr(run_ingestion, "get_tracker", lambda: tracker)
    monkeypatch.setattr(run_ingestion, "finish_processing", tracker.finish_processing)
    monkeypatch.setattr(run_ingestion, "load_configs", lambda *_: cfg_template)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "ffmpeg")
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *a, **k: stored_scenes)
    monkeypatch.setattr(run_ingestion, "_compute_sha256", lambda *a, **k: "videohash")
    monkeypatch.setattr(run_ingestion, "ensure_scene", lambda *a, **k: "scene_0000")
    monkeypatch.setattr(run_ingestion, "scene_has_materialized", lambda *a, **k: {"keyframe": False, "audio": False})
    monkeypatch.setattr(run_ingestion, "get_scene_meta", lambda *a, **k: {})
    monkeypatch.setattr(run_ingestion, "_build_knowledge_graph_from_results", lambda *a, **k: None)
    monkeypatch.setattr(run_ingestion, "_process_frame", lambda *a, **k: {"path": "frame.jpg", "data": {"caption": "frame"}})
    monkeypatch.setattr(
        run_ingestion,
        "_process_audio",
        lambda *a, **k: {"path": "scene.wav", "start": 0.0, "end": 1.0, "data": {"transcript": "hello"}},
    )
    monkeypatch.setattr(run_ingestion, "register_scene_bundle", lambda *a, **k: {"vector_points_attempted": 0})

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

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload and payload[0]["video_id"] == "videohash"
    assert tracker.started
    assert tracker.total_steps[-1] == 2
    assert any(step_name == "Scene Reuse" for step_name, _, _ in tracker.updated)
    assert any(step_name == "Scene 1/1" for step_name, _, _ in tracker.updated)
    assert tracker.finished[-1] == "completed"


def test_progress_tracker_keeps_run_started_at_across_files(monkeypatch, tmp_path: Path):
    from steps.common.progress_tracker import ProgressTracker

    tracker = ProgressTracker()
    monkeypatch.setattr(tracker, "progress_file", tmp_path / "progress.json")
    monkeypatch.setattr(
        tracker,
        "current_state",
        {
            "status": "idle",
            "current_file": None,
            "run_id": None,
            "run_started_at": None,
        },
    )

    tracker.start_processing("one.mp4", total_steps=2, run_id="run-a")
    first = tracker.get_state()
    tracker.finish_processing("completed")
    tracker.start_processing("two.mp4", total_steps=2, run_id="run-a")
    second = tracker.get_state()

    assert first["run_started_at"] == first["started_at"]
    assert second["run_started_at"] == first["run_started_at"]
    assert second["file_started_at"] == second["started_at"]
    assert second["current_file"] == "two.mp4"
