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


def test_control_agent_disabled_without_llm_client_persists_state(monkeypatch, tmp_path: Path):
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

    cfg_template = {
        "paths": {"processing": str(tmp_path / "processing")},
        "phase6": {"enabled": False},
        "knowledge_graph": {"enabled": False},
    }

    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", True)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "load_configs", lambda *_: cfg_template)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "ffmpeg")
    monkeypatch.setattr(run_ingestion, "_detect_scenes", lambda *a, **k: {"scenes": [], "meta": {}})
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *a, **k: {"scenes": []})
    monkeypatch.setattr(run_ingestion, "_compute_sha256", lambda *a, **k: "videohash")
    monkeypatch.setattr(run_ingestion, "_build_knowledge_graph_from_results", lambda *a, **k: None)

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
    assert first["control_agent_status"] == "disabled_no_llm_client"
    assert "llm_client" in (first["control_agent_reason"] or "")

    run_meta = cfg_snapshot.get("run", {})
    assert run_meta.get("control_agent_status") == "disabled_no_llm_client"
    assert "llm_client" in (run_meta.get("control_agent_reason") or "")
