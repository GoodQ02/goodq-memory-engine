from __future__ import annotations

import importlib
import json
import os
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


class _FakeSequencedPopen:
    calls = []
    responses = []
    captured_envs = []

    def __init__(self, cmd, *args, **kwargs):
        type(self).calls.append(list(cmd))
        type(self).captured_envs.append(dict(kwargs.get("env") or {}))
        response = type(self).responses.pop(0)
        self.pid = response.get("pid", 6464)
        self.returncode = response["returncode"]
        self._stdout = response.get("stdout", "")
        self._stderr = response.get("stderr", "")

    def communicate(self, timeout=None):
        return self._stdout, self._stderr

    def kill(self):
        self.returncode = -9


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakePopenCaptureEnv:
    captured_env = None

    def __init__(self, *args, **kwargs):
        type(self).captured_env = dict(kwargs.get("env") or {})
        self.pid = 7171
        self.returncode = 0

    def communicate(self, timeout=None):
        return "{}", ""

    def kill(self):
        self.returncode = -9


def _write_cfg(tmp_path: Path, *, host: dict | None = None) -> Path:
    cfg_json = tmp_path / "cfg.json"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    cfg_payload = {
        "run": {"id": "run_test"},
        "paths": {
            "data_root": str(runtime_root),
            "import_inbox": str(runtime_root / "import_inbox"),
            "processing": str(runtime_root / "processing"),
            "log_dir": str(runtime_root / "logs"),
            "db_path": str(runtime_root / "memory.db"),
            "knowledge_graph_db": str(runtime_root / "knowledge_graph.db"),
            "qdrant_storage": str(runtime_root / "qdrant_storage"),
            "models_cache": str(runtime_root / "models"),
        },
    }
    if host:
        cfg_payload["host"] = host
    cfg_json.write_text(json.dumps(cfg_payload), encoding="utf-8")
    return cfg_json


def test_base_env_enforces_python_no_user_site(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(tmp_path)

    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)

    env = run_ingestion._base_env(cfg_json)

    assert env["PYTHONNOUSERSITE"] == "1"


def test_base_env_prefers_cfg_gpu_profile_over_stale_no_auto_gpu(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "GPU_ENHANCED", "require_gpu": True},
    )

    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "GPU_ENHANCED"
    assert env["GOODQ_REQUIRE_GPU"] == "1"
    assert env.get("GOODQ_NO_AUTO_GPU") != "1"


def test_base_env_forces_no_auto_gpu_for_baseline_profile(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "BASELINE", "require_gpu": False},
    )

    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "BASELINE"
    assert env["GOODQ_NO_AUTO_GPU"] == "1"


def test_base_env_baseline_clears_stale_require_gpu(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "BASELINE"},
    )

    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "BASELINE"
    assert env["GOODQ_REQUIRE_GPU"] == "0"
    assert env["GOODQ_NO_AUTO_GPU"] == "1"


def test_run_step_success_emits_scene_metadata_and_pid(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_core_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenSuccess)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

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
        assert meta["launcher"] == "direct_env_python"


def test_run_step_sanitizes_stale_gpu_disable_flag_for_gpu_profile(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "GPU_ENHANCED", "require_gpu": True},
    )
    direct_env_python = tmp_path / "goodq_audio_embed_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakePopenCaptureEnv.captured_env = None
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenCaptureEnv)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    run_ingestion._run_step(
        env_name="goodq_audio_embed",
        step_name="audio_embed_clap",
        payload={"source_path": str(tmp_path / "dummy.wav")},
        cfg_json=cfg_json,
    )

    captured_env = _FakePopenCaptureEnv.captured_env or {}
    assert captured_env["GOODQ_HOST_PROFILE"] == "GPU_ENHANCED"
    assert captured_env["GOODQ_REQUIRE_GPU"] == "1"
    assert captured_env.get("GOODQ_NO_AUTO_GPU") != "1"


def test_run_step_failure_emits_step_error_with_scene_metadata_and_pid(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)

    import configs.python_paths as python_paths

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenFailure)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(run_ingestion, "_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS", False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: None)

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


def test_run_step_retries_optional_steps_via_direct_env_python_on_conda_tmp_failure(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_core_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 7171,
            "returncode": 1,
            "stdout": "",
            "stderr": (
                "Failed to run 'conda activate \"C:\\\\Users\\\\jdben\\\\miniconda3\\\\envs\\\\goodq_core\"'\n"
                "The process cannot access the file because it is being used by another process.\n"
                "ERROR conda.cli.main_run:execute(127): `conda run python ...` failed\n"
                "C:\\Users\\jdben\\AppData\\Local\\Temp\\__conda_tmp_17331.txt"
            ),
        },
        {
            "pid": 8181,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(run_ingestion, "_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS", False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_003",
        "scene_id": "scene_0003",
        "scene_index": 3,
    }

    result = run_ingestion._run_step(
        env_name="goodq_core",
        step_name="sentiment",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    assert _FakeSequencedPopen.calls[0][0] == "conda"
    assert _FakeSequencedPopen.calls[0][1:4] == ["run", "-n", "goodq_core"]
    assert _FakeSequencedPopen.calls[1][0] == str(direct_env_python)
    assert _FakeSequencedPopen.calls[1][1].endswith("cli\\step_runner.py")

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.sentiment"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["launcher"] == "direct_env_python"
    assert end_meta["direct_env_fallback_attempt"] == 1
    assert end_meta["scene_id"] == "scene_0003"


def test_run_step_retries_sentiment_once_after_native_crash(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_core_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 9191,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "Loading weights:   0%|          | 0/104 [00:00<?, ?it/s]",
        },
        {
            "pid": 9292,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_004",
        "scene_id": "scene_0004",
        "scene_index": 4,
    }

    result = run_ingestion._run_step(
        env_name="goodq_core",
        step_name="sentiment",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    assert _FakeSequencedPopen.calls[0][0] == str(direct_env_python)
    assert _FakeSequencedPopen.calls[1][0] == str(direct_env_python)

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.sentiment"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 1
    assert end_meta["scene_id"] == "scene_0004"


def test_run_step_retries_dino_with_amp_disable_then_cpu_fallback_after_native_crashes(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_image_caption_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 10101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native dino crash on first gpu attempt",
        },
        {
            "pid": 10102,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native dino crash on second gpu attempt",
        },
        {
            "pid": 10103,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0002.jpg"),
        "video_id": "video_test_dino",
        "scene_id": "scene_0002",
        "scene_index": 2,
    }

    result = run_ingestion._run_step(
        env_name="goodq_image_caption",
        step_name="image_embed_dino",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 3
    assert all(call[0] == str(direct_env_python) for call in _FakeSequencedPopen.calls)

    first_env, second_env, third_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_DINO_DISABLE_AMP") != "1"
    assert first_env.get("GOODQ_DINO_FORCE_CPU") != "1"
    assert second_env["GOODQ_DINO_DISABLE_AMP"] == "1"
    assert second_env.get("GOODQ_DINO_FORCE_CPU") != "1"
    assert third_env["GOODQ_DINO_DISABLE_AMP"] == "1"
    assert third_env["GOODQ_DINO_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.image_embed_dino"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 2
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0002"


def test_run_step_retries_image_caption_with_amp_disable_then_cpu_fallback_after_native_crashes(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_image_caption_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 11101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native image caption crash on first gpu attempt",
        },
        {
            "pid": 11102,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native image caption crash on second gpu attempt",
        },
        {
            "pid": 11103,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0003.jpg"),
        "video_id": "video_test_caption",
        "scene_id": "scene_0003",
        "scene_index": 3,
    }

    result = run_ingestion._run_step(
        env_name="goodq_image_caption",
        step_name="image_caption",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 3
    first_env, second_env, third_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_IMAGE_CAPTION_DISABLE_AMP") != "1"
    assert first_env.get("GOODQ_IMAGE_CAPTION_FORCE_CPU") != "1"
    assert second_env["GOODQ_IMAGE_CAPTION_DISABLE_AMP"] == "1"
    assert second_env.get("GOODQ_IMAGE_CAPTION_FORCE_CPU") != "1"
    assert third_env["GOODQ_IMAGE_CAPTION_DISABLE_AMP"] == "1"
    assert third_env["GOODQ_IMAGE_CAPTION_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.image_caption"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 2
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0003"


def test_run_step_retries_object_detect_with_cpu_fallback_after_native_crash(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_object_detect_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 12101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native object detect crash on gpu attempt",
        },
        {
            "pid": 12102,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0013.jpg"),
        "video_id": "video_test_detect",
        "scene_id": "scene_0013",
        "scene_index": 13,
    }

    result = run_ingestion._run_step(
        env_name="goodq_object_detect",
        step_name="object_detect",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    first_env, second_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_OBJECT_DETECT_FORCE_CPU") != "1"
    assert second_env["GOODQ_OBJECT_DETECT_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.object_detect"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 1
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0013"


def test_resolve_audio_runtime_contract_falls_back_from_stale_env_workspace(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    monkeypatch.setenv("GOODQ_WSL_USER", "jdben")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/jdben/projects/goodq4all")

    probed_workspaces = []

    def _fake_probe(distro, workspace):
        probed_workspaces.append(workspace)
        if workspace == "/home/jdben/projects/goodq4all":
            return {
                "workspace_ready": False,
                "runtime_ready": False,
                "abi_ready": False,
                "detail": "workspace missing required files",
            }
        if workspace == "/home/jdben/goodq_audio":
            return {
                "workspace_ready": True,
                "runtime_ready": True,
                "abi_ready": True,
                "detail": "workspace and Python runtime are ready",
            }
        raise AssertionError(f"unexpected workspace probe: {workspace}")

    monkeypatch.setattr(run_ingestion, "probe_wsl_audio_runtime", _fake_probe)

    cfg = {
        "host": {
            "wsl_distro": "Ubuntu-22.04",
            "wsl_user": "jdben",
            "wsl_workspace": "/home/jdben/goodq_audio",
        }
    }

    contract = run_ingestion._resolve_audio_runtime_contract(cfg)

    assert probed_workspaces == [
        "/home/jdben/projects/goodq4all",
        "/home/jdben/goodq_audio",
    ]
    assert contract["selected"] == "wsl"
    assert contract["reason"] == "wsl_runtime_ready"
    assert contract["wsl_audio_workspace"] == "/home/jdben/goodq_audio"
    assert contract["wsl_workspace_source"] == "config"
    assert contract["workspace_ready"] is True
    assert contract["wsl_runtime_ready"] is True
    assert os.environ["GOODQ_WSL_WORKSPACE"] == "/home/jdben/goodq_audio"


def test_resolve_audio_runtime_contract_falls_back_from_stale_env_distro(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu")
    monkeypatch.setenv("GOODQ_WSL_USER", "jdben")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/jdben/goodq_audio")

    probed_targets = []

    def _fake_probe(distro, workspace):
        probed_targets.append((distro, workspace))
        if distro == "Ubuntu":
            return {
                "workspace_ready": False,
                "runtime_ready": False,
                "abi_ready": False,
                "detail": "workspace missing required files",
            }
        if distro == "Ubuntu-22.04":
            return {
                "workspace_ready": True,
                "runtime_ready": True,
                "abi_ready": True,
                "detail": "workspace and Python runtime are ready",
            }
        raise AssertionError(f"unexpected distro probe: {distro}")

    monkeypatch.setattr(run_ingestion, "probe_wsl_audio_runtime", _fake_probe)

    cfg = {
        "host": {
            "wsl_distro": "Ubuntu-22.04",
            "wsl_user": "jdben",
            "wsl_workspace": "/home/jdben/goodq_audio",
        }
    }

    contract = run_ingestion._resolve_audio_runtime_contract(cfg)

    assert probed_targets == [
        ("Ubuntu", "/home/jdben/goodq_audio"),
        ("Ubuntu-22.04", "/home/jdben/goodq_audio"),
    ]
    assert contract["selected"] == "wsl"
    assert contract["reason"] == "wsl_runtime_ready"
    assert contract["wsl_distro"] == "Ubuntu-22.04"
    assert contract["wsl_distro_source"] == "config"
    assert contract["wsl_audio_workspace"] == "/home/jdben/goodq_audio"
    assert contract["workspace_ready"] is True
    assert "GOODQ_WSL_DISTRO=Ubuntu was unavailable" in contract["workspace_check_message"]
    assert os.environ["GOODQ_WSL_DISTRO"] == "Ubuntu-22.04"


def test_resolve_audio_runtime_contract_requires_distro_in_failure_message(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu")
    monkeypatch.setenv("GOODQ_WSL_USER", "jdben")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/jdben/goodq_audio")
    monkeypatch.setattr(
        run_ingestion,
        "probe_wsl_audio_runtime",
        lambda *args, **kwargs: {
            "workspace_ready": False,
            "runtime_ready": False,
            "abi_ready": False,
            "detail": "workspace missing required files",
        },
    )

    cfg = {
        "host": {
            "wsl_distro": "Ubuntu-22.04",
            "wsl_user": "jdben",
            "wsl_workspace": "/home/jdben/goodq_audio",
        }
    }

    with pytest.raises(RuntimeError) as excinfo:
        run_ingestion._resolve_audio_runtime_contract(cfg)

    message = str(excinfo.value)
    assert "Ubuntu:/home/jdben/goodq_audio" in message
    assert "Ubuntu-22.04:/home/jdben/goodq_audio" in message
    assert "GOODQ_WSL_DISTRO, GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE" in message


def test_resolve_audio_runtime_contract_accepts_abi_degraded_transcription_runtime(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    monkeypatch.setenv("GOODQ_WSL_USER", "jdben")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/jdben/goodq_audio")
    monkeypatch.setattr(
        run_ingestion,
        "probe_wsl_audio_runtime",
        lambda *args, **kwargs: {
            "workspace_ready": True,
            "runtime_ready": True,
            "abi_ready": False,
            "detail": "transcription runtime ready; torchvision ABI unavailable (diarization may be degraded)",
        },
    )

    contract = run_ingestion._resolve_audio_runtime_contract(
        {
            "host": {
                "wsl_distro": "Ubuntu-22.04",
                "wsl_user": "jdben",
                "wsl_workspace": "/home/jdben/goodq_audio",
            }
        }
    )

    assert contract["selected"] == "wsl"
    assert contract["reason"] == "wsl_runtime_ready"
    assert contract["wsl_runtime_ready"] is True
    assert contract["wsl_abi_ready"] is False
    assert "transcription runtime ready" in contract["wsl_runtime_detail"]
