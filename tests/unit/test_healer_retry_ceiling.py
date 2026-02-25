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

        typer.Typer = _DummyTyper
        typer.Option = lambda default=None, *args, **kwargs: default
        typer.echo = lambda *args, **kwargs: None
        typer.BadParameter = Exception
        sys.modules["typer"] = typer

    return importlib.import_module("cli.run_ingestion")


def test_healer_retry_ceiling_caps_at_three(monkeypatch, tmp_path: Path, caplog):
    run_ingestion = _load_run_ingestion_module()

    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(
        json.dumps(
            {
                "run": {
                    "id": "run_test",
                    "healer_retry_count": 0,
                    "healer_retry_by_step": {},
                }
            }
        ),
        encoding="utf-8",
    )

    calls = {"subprocess": 0, "heal": 0}

    def _fake_subprocess_run(*args, **kwargs):
        calls["subprocess"] += 1
        return types.SimpleNamespace(returncode=1, stdout="stdout", stderr="stderr")

    class _FakeControlAgent:
        def __init__(self, *args, **kwargs):
            pass

        def auto_heal_failure(self, *args, **kwargs):
            calls["heal"] += 1
            return {"success": True}

    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_ingestion, "ControlAgent", _FakeControlAgent)
    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", True)
    monkeypatch.setattr(
        run_ingestion,
        "_CURRENT_RUN_CONTEXT",
        {"id": "run_test", "healer_retry_count": 0, "healer_retry_by_step": {}},
    )

    with caplog.at_level("WARNING"):
        with pytest.raises(RuntimeError):
            run_ingestion._run_step(
                env_name="goodq_core",
                step_name="failing_step",
                payload={"source_path": "dummy"},
                cfg_json=cfg_json,
            )

    assert calls["subprocess"] == run_ingestion.MAX_HEALER_RETRIES + 1
    assert calls["heal"] == run_ingestion.MAX_HEALER_RETRIES + 1
    assert run_ingestion._CURRENT_RUN_CONTEXT["healer_retry_count"] == run_ingestion.MAX_HEALER_RETRIES
    assert run_ingestion._CURRENT_RUN_CONTEXT["healer_retry_by_step"]["failing_step"] == run_ingestion.MAX_HEALER_RETRIES

    persisted = json.loads(cfg_json.read_text(encoding="utf-8"))
    assert persisted["run"]["healer_retry_count"] == run_ingestion.MAX_HEALER_RETRIES
    assert persisted["run"]["healer_retry_by_step"]["failing_step"] == run_ingestion.MAX_HEALER_RETRIES
    assert "Healer retry ceiling reached for step=failing_step" in caplog.text
