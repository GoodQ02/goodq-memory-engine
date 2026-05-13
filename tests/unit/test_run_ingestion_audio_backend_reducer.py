from __future__ import annotations

import importlib
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


@pytest.mark.parametrize(
    "scene_outputs, expected",
    [
        ([], "none"),
        ([{"audio_backend_selected": "wsl"}], "wsl"),
        ([{"audio_backend_selected": "windows"}], "windows"),
        (
            [
                {"audio_backend_selected": "wsl"},
                {"audio_backend_selected": "windows"},
            ],
            "mixed",
        ),
        ([{"audio_backend_selected": "WSL"}], "wsl"),
        ([{"audio_backend_selected": "none"}], "none"),
        ([{"audio_backend_selected": None}, {}], "none"),
        (
            [
                {"audio_backend_selected": "wsl"},
                {"audio_backend_selected": "none"},
                {"audio_backend_selected": "invalid"},
            ],
            "wsl",
        ),
        ([None, "bad", 123], "none"),
    ],
)
def test_aggregate_audio_backend_contract(scene_outputs, expected):
    run_ingestion = _load_run_ingestion_module()

    result = run_ingestion._aggregate_audio_backend(scene_outputs)

    assert result is not None
    assert result in {"wsl", "windows", "mixed", "none"}
    assert result == expected


def test_audio_backend_events_since_keeps_video_scope():
    run_ingestion = _load_run_ingestion_module()
    run_context = {
        "audio_backend_events": [
            {"scene_id": "scene_a", "downgrade_reason": "windows_unavailable_in_scene"},
            {"scene_id": "scene_b", "downgrade_reason": "wsl_unavailable_in_scene"},
        ]
    }

    events = run_ingestion._audio_backend_events_since(run_context, 1)

    assert events == [{"scene_id": "scene_b", "downgrade_reason": "wsl_unavailable_in_scene"}]
    events[0]["scene_id"] = "mutated"
    assert run_context["audio_backend_events"][1]["scene_id"] == "scene_b"
