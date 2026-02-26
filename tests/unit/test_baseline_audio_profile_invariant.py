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


def test_baseline_profile_skips_unified_wsl(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    _process_audio = run_ingestion._process_audio

    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(json.dumps({"audio": {}, "run": {"id": "run_test"}}), encoding="utf-8")

    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "scene.wav"
    video_path.write_bytes(b"v")
    audio_path.write_bytes(b"a")

    audio_dir = tmp_path / "artifacts" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: False)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion, "_extract_audio_chunk", lambda *a, **k: audio_path)

    state = {"unified_called": False, "local_called": False}

    mod_unified = types.ModuleType("steps.audio.audio_wsl2_bridge")

    def _audio_unified_wsl2(*args, **kwargs):
        state["unified_called"] = True
        return {}

    mod_unified.audio_unified_wsl2 = _audio_unified_wsl2
    monkeypatch.setitem(sys.modules, "steps.audio.audio_wsl2_bridge", mod_unified)

    mod_local = types.ModuleType("steps.audio_transcribe.step")

    def _audio_transcribe(*args, **kwargs):
        state["local_called"] = True
        return {
            "transcript": "baseline",
            "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "baseline"}],
        }

    mod_local.audio_transcribe = _audio_transcribe
    monkeypatch.setitem(sys.modules, "steps.audio_transcribe.step", mod_local)

    merge_calls = []

    def _run_step(env_name, step_name, payload, cfg_path):
        merge_calls.append((env_name, step_name))
        return {}

    monkeypatch.setattr(run_ingestion, "_run_step", _run_step)

    result = _process_audio(
        cfg_json=cfg_json,
        ffmpeg="ffmpeg",
        video_path=video_path,
        scene={"start": 0.0, "end": 2.0},
        audio_dir=audio_dir,
        audio_artifact_dir=tmp_path / "processing" / "audio",
        video_hash="vh",
        scene_id="s1",
    )

    assert state["unified_called"] is False
    assert state["local_called"] is True
    assert result is not None
    assert result["data"]["transcript"] == "baseline"
    assert len(result["data"]["segments"]) == 1
    assert ("goodq_audio_transcribe", "audio_speaker_merge") in merge_calls
