from __future__ import annotations

import importlib
import sqlite3
import sys
import types
from pathlib import Path

import pytest

from steps.common import memory


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


def test_offset_local_audio_result_to_scene_translates_relative_segments():
    run_ingestion = _load_run_ingestion_module()

    local_result = {
        "transcript": "Wait, I just want to see something.",
        "segments": [
            {
                "start": 0.0,
                "end": 1.84,
                "text": "Wait, I just want to see something.",
                "words": [
                    {"start": 0.0, "end": 0.42, "word": "Wait,"},
                    {"start": 0.43, "end": 1.84, "word": "something."},
                ],
            }
        ],
        "transcript_meta": {
            "status": "ok",
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.84,
                    "text": "Wait, I just want to see something.",
                }
            ],
            "chunks": [
                {
                    "start": 0.0,
                    "end": 10.0,
                    "status": "ok",
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 1.84,
                            "text": "Wait, I just want to see something.",
                        }
                    ],
                }
            ],
        },
    }

    normalized = run_ingestion._offset_local_audio_result_to_scene(local_result, 928.68)

    assert local_result["segments"][0]["start"] == 0.0
    assert normalized["segments"][0]["start"] == pytest.approx(928.68)
    assert normalized["segments"][0]["end"] == pytest.approx(930.52)
    assert normalized["segments"][0]["words"][0]["start"] == pytest.approx(928.68)
    assert normalized["transcript_meta"]["segments"][0]["start"] == pytest.approx(928.68)
    assert normalized["transcript_meta"]["chunks"][0]["start"] == pytest.approx(928.68)
    assert normalized["transcript_meta"]["chunks"][0]["segments"][0]["end"] == pytest.approx(930.52)


def test_register_scene_bundle_preserves_explicit_zero_segment_start(tmp_path: Path):
    cfg = {"paths": {"db_path": str(tmp_path / "memory.db")}}
    audio_path = tmp_path / "scene_0028.wav"
    audio_path.write_bytes(b"RIFF")

    result = memory.register_scene_bundle(
        cfg,
        video_hash="video_hash_1",
        scene={"start": 928.68, "end": 960.04, "index": 28},
        scene_id="scene_0028",
        audio={
            "path": str(audio_path),
            "start": 928.68,
            "end": 960.04,
            "data": {
                "speaker_transcript": [
                    {
                        "start": 0.0,
                        "end": 1.84,
                        "speaker": "SPEAKER_00",
                        "text": "Wait, I just want to see something.",
                    }
                ]
            },
        },
    )

    assert len(result["segments"]) == 1

    conn = sqlite3.connect(str(tmp_path / "memory.db"))
    try:
        rows = conn.execute("SELECT start, end, speaker FROM segments").fetchall()
    finally:
        conn.close()

    assert rows == [(0.0, 1.84, "SPEAKER_00")]
