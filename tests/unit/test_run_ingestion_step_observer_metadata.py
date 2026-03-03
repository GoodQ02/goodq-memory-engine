from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest


def _load_run_ingestion_module():
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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


class _RecorderObserver:
    def __init__(self) -> None:
        self.enabled = True
        self.events = []

    def step_start(self, step, *, total=None, metadata=None):
        self.events.append(("step_start", step, dict(metadata or {})))

    def step_end(self, step, *, metadata=None):
        self.events.append(("step_end", step, dict(metadata or {})))

    def step_error(self, step, *, error, metadata=None):
        self.events.append(("step_error", step, error, dict(metadata or {})))

    def begin_heartbeat(self, step, *, metadata=None):
        self.events.append(("heartbeat_begin", step, dict(metadata or {})))

        def _stop():
            self.events.append(("heartbeat_end", step, dict(metadata or {})))

        return _stop


class _FakePopenSuccess:
    def __init__(self, *args, **kwargs):
        self.pid = 4242
        self.returncode = 0

    def communicate(self, timeout=None):
        return "{}", ""

    def kill(self):
        self.returncode = -9


class _FakePopenFailure:
    def __init__(self, *args, **kwargs):
        self.pid = 5353
        self.returncode = 1

    def communicate(self, timeout=None):
        return "", "simulated_step_failure"

    def kill(self):
        self.returncode = -9


def _write_cfg(tmp_path: Path) -> Path:
    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(json.dumps({"run": {"id": "run_test"}}), encoding="utf-8")
    return cfg_json


def test_run_step_success_emits_scene_metadata_and_pid(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenSuccess)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_001",
        "scene_id": "scene_0007",
        "scene_index": 7,
    }

    result = run_ingestion._run_step(
        env_name="goodq_core",
        step_name="dummy_step",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}

    start_events = [event for event in observer.events if event[0] == "step_start" and event[1] == "step.dummy_step"]
    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.dummy_step"]
    assert start_events
    assert end_events

    start_meta = start_events[0][2]
    end_meta = end_events[0][2]
    for meta in (start_meta, end_meta):
        assert meta["scene_id"] == "scene_0007"
        assert meta["scene_index"] == 7
        assert meta["video_id"] == "video_test_001"
        assert isinstance(meta["subprocess_pid"], int)
        assert meta["subprocess_pid"] > 0


def test_run_step_failure_emits_step_error_with_scene_metadata_and_pid(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenFailure)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_002",
        "scene": {"index": 12},
        "scene_id": "scene_0012",
    }

    with pytest.raises(RuntimeError, match="Step dummy_step failed"):
        run_ingestion._run_step(
            env_name="goodq_core",
            step_name="dummy_step",
            payload=payload,
            cfg_json=cfg_json,
        )

    error_events = [event for event in observer.events if event[0] == "step_error" and event[1] == "step.dummy_step"]
    assert error_events
    error_meta = error_events[0][3]

    assert error_meta["scene_id"] == "scene_0012"
    assert error_meta["scene_index"] == 12
    assert error_meta["video_id"] == "video_test_002"
    assert isinstance(error_meta["subprocess_pid"], int)
    assert error_meta["subprocess_pid"] > 0
