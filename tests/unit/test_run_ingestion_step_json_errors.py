from __future__ import annotations

import importlib
import sys
import types

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


def test_parse_step_result_json_accepts_dict_payload():
    run_ingestion = _load_run_ingestion_module()

    result = run_ingestion._parse_step_result_json(
        '{"status":"ok"}',
        step_name="image_embed_clip",
        env_name="goodq_image_caption",
        source="output.json",
    )

    assert result == {"status": "ok"}


def test_parse_step_result_json_reports_step_context_for_invalid_json():
    run_ingestion = _load_run_ingestion_module()

    with pytest.raises(RuntimeError) as excinfo:
        run_ingestion._parse_step_result_json(
            "[WARN] something noisy happened",
            step_name="image_embed_clip",
            env_name="goodq_image_caption",
            source="output.json",
        )

    message = str(excinfo.value)
    assert "image_embed_clip" in message
    assert "goodq_image_caption" in message
    assert "output.json" in message
    assert "invalid JSON" in message
