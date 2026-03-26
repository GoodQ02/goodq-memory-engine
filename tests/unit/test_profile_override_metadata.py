from __future__ import annotations

import json
import importlib
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


def test_baseline_forced_wsl_persists_profile_override_metadata(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()

    input_dir = tmp_path / "inbox"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "demo.mp4").write_bytes(b"v")

    output = tmp_path / "results.json"
    workspace = tmp_path / "workspace"

    cfg_template = {
        "paths": {"processing": str(tmp_path / "processing")},
        "phase6": {"enabled": False},
        "knowledge_graph": {"enabled": False},
    }

    class _FakeCompletedProcess:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    monkeypatch.setattr(run_ingestion, "is_baseline", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(
        run_ingestion,
        "probe_wsl_audio_runtime",
        lambda *args, **kwargs: {
            "workspace_ready": True,
            "runtime_ready": True,
            "abi_ready": True,
            "detail": "workspace and Python runtime are ready",
        },
    )
    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "load_configs", lambda *_: cfg_template)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "ffmpeg")
    monkeypatch.setattr(run_ingestion, "_detect_scenes", lambda *a, **k: {"scenes": [], "meta": {}})
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *a, **k: {"scenes": []})
    monkeypatch.setattr(run_ingestion, "_compute_sha256", lambda *a, **k: "videohash")
    monkeypatch.setattr(run_ingestion, "_build_knowledge_graph_from_results", lambda *a, **k: None)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("USERNAME", "jdben")
    monkeypatch.delenv("GOODQ_WSL_USER", raising=False)
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/jdben/goodq_audio")

    def _fake_subprocess_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "git":
            return _FakeCompletedProcess(returncode=0, stdout="deadbeef\n")
        if cmd and cmd[0] == "wsl":
            return _FakeCompletedProcess(returncode=0)
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    monkeypatch.setattr(run_ingestion.subprocess, "run", _fake_subprocess_run)

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
    cfg_snapshot = json.loads((workspace / "_resolved_config.json").read_text(encoding="utf-8"))

    assert results
    first = results[0]
    assert first.get("profile_override") == "wsl_audio_forced_in_baseline"
    video_reason = first.get("profile_override_reason") or ""
    assert video_reason
    assert "GOODQ_REQUIRE_WSL_AUDIO" in video_reason

    run_meta = cfg_snapshot.get("run", {})
    assert run_meta.get("profile_override") == "wsl_audio_forced_in_baseline"
    run_reason = run_meta.get("profile_override_reason") or ""
    assert run_reason
    assert "GOODQ_REQUIRE_WSL_AUDIO" in run_reason
