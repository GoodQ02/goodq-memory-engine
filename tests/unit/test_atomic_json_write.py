from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest

import steps.video.scene_visual_embeddings as scene_visual_embeddings


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


@pytest.mark.parametrize(
    "module_name",
    [
        "steps.video.scene_visual_embeddings",
        "cli.run_ingestion",
    ],
)
def test_atomic_json_write_keeps_target_valid_on_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module_name: str,
) -> None:
    if module_name == "cli.run_ingestion":
        module = _load_run_ingestion_module()
    else:
        module = scene_visual_embeddings
    writer = module._atomic_write_json

    target = tmp_path / f"{module.__name__.replace('.', '_')}.json"
    original = {"status": "old", "count": 1}
    target.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    new_data = {"status": "new", "count": 2}

    def _boom_replace(src: str, dst: str) -> None:
        raise RuntimeError("simulated_replace_failure")

    monkeypatch.setattr(module.os, "replace", _boom_replace)

    with pytest.raises(RuntimeError, match="simulated_replace_failure"):
        writer(target, new_data)

    persisted = json.loads(target.read_text(encoding="utf-8"))
    assert persisted == original
    assert (target.parent / f"{target.name}.tmp").exists()
