from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


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


def test_classify_scene_content_signal_with_transcript_text():
    run_ingestion = _load_run_ingestion_module()

    scene = {
        "duration": 12.0,
        "audio": {
            "transcript": "hello world",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
            "transcript_meta": {"status": "success", "duration": 1.0},
        },
    }

    state = run_ingestion._classify_scene_content(scene, empty_duration_threshold_sec=1.0)

    assert state == "signal"


def test_classify_scene_content_signal_when_duration_missing_but_transcript_present():
    run_ingestion = _load_run_ingestion_module()

    scene = {
        "duration": 12.0,
        "audio": {
            "transcript": "still meaningful",
            "segments": [{"start": 0.0, "end": 1.0, "text": "still meaningful"}],
            "transcript_meta": {"status": "success"},
        },
    }

    state = run_ingestion._classify_scene_content(scene, empty_duration_threshold_sec=1.0)

    assert state == "signal"


def test_classify_scene_content_empty_when_success_but_empty_short():
    run_ingestion = _load_run_ingestion_module()

    scene = {
        "duration": 0.5,
        "audio": {
            "path": "audio/scene_0001.wav",
            "transcript": "",
            "segments": [],
            "transcript_meta": {"status": "success", "duration": 0.0},
        },
    }

    state = run_ingestion._classify_scene_content(scene, empty_duration_threshold_sec=1.0)

    assert state == "empty"


def test_classify_scene_content_processing_error_with_audio_error():
    run_ingestion = _load_run_ingestion_module()

    scene = {
        "duration": 20.0,
        "audio_error": "ffmpeg failed",
        "audio": {
            "transcript_meta": {"status": "success", "duration": 0.0},
            "transcript": "",
            "segments": [],
        },
    }

    state = run_ingestion._classify_scene_content(scene, empty_duration_threshold_sec=1.0)

    assert state == "processing_error"


def test_extract_step_failure_details_preserves_step_and_raw_message():
    run_ingestion = _load_run_ingestion_module()

    raw_message = (
        "Step image_embed_dino failed (goodq_image_caption) [returncode=7]\n"
        "STDOUT: \n"
        "STDERR: FutureWarning: autocast() is deprecated\n"
        "RuntimeError: CUDA kernel launch failed"
    )

    details = run_ingestion._extract_step_failure_details(
        RuntimeError(raw_message),
        stage_label="Keyframe",
    )

    assert details["step"] == "image_embed_dino"
    assert details["env"] == "goodq_image_caption"
    assert details["returncode"] == "7"
    assert details["raw_message"] == raw_message
    assert "Keyframe step image_embed_dino failed" in details["message"]
    assert "CUDA kernel launch failed" in details["message"]


def test_aggregate_content_summary_counts_and_sums():
    run_ingestion = _load_run_ingestion_module()

    scenes = [
        {"content_state": "signal"},
        {"content_state": "empty"},
        {"content_state": "processing_error"},
        {"content_state": "signal"},
    ]

    summary = run_ingestion._aggregate_content_summary(scenes)

    assert summary == {"signal": 2, "empty": 1, "processing_error": 1}
    assert sum(summary.values()) == len(scenes)
