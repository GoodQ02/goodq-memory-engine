from __future__ import annotations

import json
import importlib
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


def test_audio_embed_clap_failure_preserves_transcript_payload(monkeypatch, tmp_path: Path):
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

    mod_local = types.ModuleType("steps.audio_transcribe.step")

    def _audio_transcribe(*args, **kwargs):
        return {
            "transcript": "late clap failure should not erase this",
            "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "baseline"}],
            "transcript_meta": {"status": "success", "duration": 1.0},
        }

    mod_local.audio_transcribe = _audio_transcribe
    monkeypatch.setitem(sys.modules, "steps.audio_transcribe.step", mod_local)

    recorded_warnings = []

    def _record_run_warning(cfg_path, code, message, context):
        recorded_warnings.append(
            {
                "code": code,
                "message": message,
                "context": context,
            }
        )

    monkeypatch.setattr(run_ingestion, "_record_run_warning", _record_run_warning)

    def _run_step(env_name, step_name, payload, cfg_path):
        if step_name == "text_embed":
            return {"embedding_meta": {"status": "ok"}}
        if step_name == "audio_embed_clap":
            raise RuntimeError("clap exploded")
        return {}

    monkeypatch.setattr(run_ingestion, "_run_step", _run_step)

    result = _process_audio(
        cfg_json=cfg_json,
        ffmpeg="ffmpeg",
        video_path=video_path,
        scene={"start": 0.0, "end": 2.0, "index": 10},
        audio_dir=audio_dir,
        audio_artifact_dir=tmp_path / "processing" / "audio",
        video_hash="vh",
        scene_id="s10",
    )

    assert result is not None
    assert result["data"]["transcript"] == "late clap failure should not erase this"
    assert result["data"]["clap_meta"]["status"] == "error"
    assert "clap exploded" in result["data"]["clap_meta"]["error"]
    assert result["data"]["audio_step_warnings"] == [
        {
            "step": "audio_embed_clap",
            "env": "goodq_audio_embed",
            "error": "clap exploded",
        }
    ]

    scene = {"duration": 2.0, "audio": result["data"]}
    assert run_ingestion._classify_scene_content(scene, empty_duration_threshold_sec=1.0) == "signal"

    assert recorded_warnings == [
        {
            "code": "optional_audio_step_failed",
            "message": "clap exploded",
            "context": {
                "step": "audio_embed_clap",
                "env": "goodq_audio_embed",
                "scene_id": "s10",
                "scene_index": 10,
            },
        }
    ]


@pytest.mark.parametrize(
    ("failing_step", "expected_meta_field"),
    [
        ("sentiment", "sentiment_meta"),
        ("emotion_classify", "emotion_meta"),
    ],
)
def test_optional_audio_text_enrichment_failure_preserves_transcript_payload(
    monkeypatch,
    tmp_path: Path,
    failing_step: str,
    expected_meta_field: str,
):
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

    mod_local = types.ModuleType("steps.audio_transcribe.step")

    def _audio_transcribe(*args, **kwargs):
        return {
            "transcript": "dialogue survives late enrichment failure",
            "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "dialogue"}],
            "transcript_meta": {"status": "success", "duration": 1.0},
        }

    mod_local.audio_transcribe = _audio_transcribe
    monkeypatch.setitem(sys.modules, "steps.audio_transcribe.step", mod_local)

    recorded_warnings = []

    def _record_run_warning(cfg_path, code, message, context):
        recorded_warnings.append(
            {
                "code": code,
                "message": message,
                "context": context,
            }
        )

    monkeypatch.setattr(run_ingestion, "_record_run_warning", _record_run_warning)

    def _run_step(env_name, step_name, payload, cfg_path):
        if step_name == "text_embed":
            return {"embedding_meta": {"status": "ok"}}
        if step_name == failing_step:
            raise RuntimeError(f"{failing_step} exploded")
        return {}

    monkeypatch.setattr(run_ingestion, "_run_step", _run_step)

    result = _process_audio(
        cfg_json=cfg_json,
        ffmpeg="ffmpeg",
        video_path=video_path,
        scene={"start": 0.0, "end": 2.0, "index": 20},
        audio_dir=audio_dir,
        audio_artifact_dir=tmp_path / "processing" / "audio",
        video_hash="vh",
        scene_id="s20",
    )

    assert result is not None
    assert result["data"]["transcript"] == "dialogue survives late enrichment failure"
    assert result["data"][expected_meta_field]["status"] == "error"
    assert f"{failing_step} exploded" in result["data"][expected_meta_field]["error"]
    assert result["data"]["audio_step_warnings"] == [
        {
            "step": failing_step,
            "env": "goodq_core",
            "error": f"{failing_step} exploded",
        }
    ]

    scene = {"duration": 2.0, "audio": result["data"]}
    assert run_ingestion._classify_scene_content(scene, empty_duration_threshold_sec=1.0) == "signal"

    assert recorded_warnings == [
        {
            "code": "optional_audio_step_failed",
            "message": f"{failing_step} exploded",
            "context": {
                "step": failing_step,
                "env": "goodq_core",
                "scene_id": "s20",
                "scene_index": 20,
            },
        }
    ]
