from __future__ import annotations

import os
import json
import importlib
import sys
import types
import wave
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


def _write_silent_wav(path: Path, *, sample_rate: int = 16000, frames: int = 0) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frames)


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


def test_structured_wsl_audio_error_downgrades_to_local_transcription(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    _process_audio = run_ingestion._process_audio

    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(
        json.dumps(
            {"audio": {}, "run": {"id": "run_test"}, "paths": {"log_dir": str(tmp_path / "logs")}}
        ),
        encoding="utf-8",
    )

    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "scene.wav"
    video_path.write_bytes(b"v")
    audio_path.write_bytes(b"a")

    audio_dir = tmp_path / "artifacts" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion, "_extract_audio_chunk", lambda *a, **k: audio_path)

    mod_unified = types.ModuleType("steps.audio.audio_wsl2_bridge")

    def _audio_unified_wsl2(*args, **kwargs):
        return {
            "status": "error",
            "error": "WSL ABI preflight failed before audio processing",
            "bridge_error_reason": "wsl_env_runtime_unavailable",
            "bridge_error_details": {"detail": "transcription runtime unavailable"},
            "bridge_env_warnings": ["transcription runtime unavailable"],
        }

    mod_unified.audio_unified_wsl2 = _audio_unified_wsl2
    monkeypatch.setitem(sys.modules, "steps.audio.audio_wsl2_bridge", mod_unified)

    mod_local = types.ModuleType("steps.audio_transcribe.step")
    observed = {}

    def _audio_transcribe(item, cfg):
        observed["use_wsl2"] = ((cfg.get("audio", {}) or {}).get("transcribe", {}) or {}).get("use_wsl2")
        observed["require_wsl_audio"] = os.environ.get("GOODQ_REQUIRE_WSL_AUDIO")
        return {
            "transcript": "fallback transcript",
            "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "fallback transcript"}],
            "transcript_meta": {"status": "success", "duration": 1.0},
        }

    mod_local.audio_transcribe = _audio_transcribe
    monkeypatch.setitem(sys.modules, "steps.audio_transcribe.step", mod_local)

    merge_calls = []
    logged_steps = []

    def _run_step(env_name, step_name, payload, cfg_path):
        merge_calls.append((env_name, step_name))
        return {}

    def _log_step_run(cfg, step_name, item, duration_ms, status, error=None, *, extra=None):
        logged_steps.append(
            {
                "step": step_name,
                "status": status,
                "error": error,
                "extra": dict(extra or {}),
            }
        )

    monkeypatch.setattr(run_ingestion, "_run_step", _run_step)
    monkeypatch.setattr(run_ingestion, "log_step_run", _log_step_run)

    result = _process_audio(
        cfg_json=cfg_json,
        ffmpeg="ffmpeg",
        video_path=video_path,
        scene={"start": 0.0, "end": 2.0, "index": 3},
        audio_dir=audio_dir,
        audio_artifact_dir=tmp_path / "processing" / "audio",
        video_hash="vh",
        scene_id="scene_0003",
        audio_runtime_contract={
            "selected": "wsl",
            "reason": "wsl_runtime_ready",
        },
    )

    assert result is not None
    assert result["data"]["transcript"] == "fallback transcript"
    assert result["data"]["audio_backend_selected"] == "wsl"
    assert result["data"]["audio_backend_effective"] == "windows"
    assert result["data"]["audio_backend_unavailable_details"]["reason"] == "wsl_env_runtime_unavailable"
    assert observed == {
        "use_wsl2": False,
        "require_wsl_audio": "0",
    }
    assert ("goodq_audio_transcribe", "audio_speaker_merge") in merge_calls
    assert any(entry["step"] == "audio_unified_wsl2" and entry["status"] == "error" for entry in logged_steps)


def test_structured_wsl_audio_error_forces_local_fallback_even_when_wsl_required(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    _process_audio = run_ingestion._process_audio

    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text(
        json.dumps(
            {"audio": {}, "run": {"id": "run_test"}, "paths": {"log_dir": str(tmp_path / "logs")}}
        ),
        encoding="utf-8",
    )

    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "scene.wav"
    video_path.write_bytes(b"v")
    audio_path.write_bytes(b"a")

    audio_dir = tmp_path / "artifacts" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(run_ingestion, "_extract_audio_chunk", lambda *a, **k: audio_path)
    monkeypatch.setenv("GOODQ_REQUIRE_WSL_AUDIO", "1")

    mod_unified = types.ModuleType("steps.audio.audio_wsl2_bridge")

    def _audio_unified_wsl2(*args, **kwargs):
        return {
            "status": "error",
            "error": "Processing timeout after 600s",
            "bridge_error_reason": "wsl_timeout",
            "bridge_error_details": {"timeout_seconds": 600},
        }

    mod_unified.audio_unified_wsl2 = _audio_unified_wsl2
    monkeypatch.setitem(sys.modules, "steps.audio.audio_wsl2_bridge", mod_unified)

    mod_local = types.ModuleType("steps.audio_transcribe.step")
    observed = {}

    def _audio_transcribe(item, cfg):
        observed["use_wsl2"] = ((cfg.get("audio", {}) or {}).get("transcribe", {}) or {}).get("use_wsl2")
        observed["require_wsl_audio"] = os.environ.get("GOODQ_REQUIRE_WSL_AUDIO")
        return {
            "transcript": "forced local fallback transcript",
            "transcript_segments": [{"start": 0.0, "end": 1.0, "text": "forced local fallback transcript"}],
            "transcript_meta": {"status": "success", "duration": 1.0},
        }

    mod_local.audio_transcribe = _audio_transcribe
    monkeypatch.setitem(sys.modules, "steps.audio_transcribe.step", mod_local)

    monkeypatch.setattr(run_ingestion, "_run_step", lambda *args, **kwargs: {})
    monkeypatch.setattr(run_ingestion, "log_step_run", lambda *args, **kwargs: None)

    result = _process_audio(
        cfg_json=cfg_json,
        ffmpeg="ffmpeg",
        video_path=video_path,
        scene={"start": 0.0, "end": 2.0, "index": 4},
        audio_dir=audio_dir,
        audio_artifact_dir=tmp_path / "processing" / "audio",
        video_hash="vh",
        scene_id="scene_0004",
        audio_runtime_contract={
            "selected": "wsl",
            "reason": "wsl_runtime_required",
        },
    )

    assert result is not None
    assert result["data"]["transcript"] == "forced local fallback transcript"
    assert result["data"]["audio_backend_selected"] == "wsl"
    assert result["data"]["audio_backend_effective"] == "windows"
    assert result["data"]["audio_backend_effective_reason"] == "wsl_unified_error_fallback"
    assert observed == {
        "use_wsl2": False,
        "require_wsl_audio": "0",
    }
    assert os.environ.get("GOODQ_REQUIRE_WSL_AUDIO") == "1"


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


def test_audio_embed_clap_skips_invalid_audio_before_model_load(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    from steps.audio_embed_clap.step import audio_embed_clap

    audio_path = tmp_path / "silent.wav"
    _write_silent_wav(audio_path, frames=0)

    result = audio_embed_clap({"source_path": str(audio_path)}, {"paths": {}})

    assert result["clap_meta"]["status"] == "skipped"
    assert result["clap_meta"]["reason"] in {"audio_too_small", "audio_too_short", "audio_empty", "invalid_audio"}


def test_audio_embed_clap_reports_missing_model_cache(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    from steps.audio_embed_clap import step as clap_step

    audio_path = tmp_path / "valid.wav"
    _write_silent_wav(audio_path, frames=16000)

    clap_step._CLAP.update({"model": None, "proc": None, "device": "cpu", "model_dir": None})
    monkeypatch.setattr(clap_step, "_torchaudio_preflight", lambda: True)
    monkeypatch.setattr(clap_step, "_inspect_audio_input", lambda _path: None)
    monkeypatch.setattr(clap_step, "_configure_model_env", lambda: tmp_path / "models")
    monkeypatch.setattr(clap_step, "_resolve_local_model_dir", lambda _root: None)
    monkeypatch.setattr(clap_step, "_preferred_device", lambda: "cpu")

    result = clap_step.audio_embed_clap({"source_path": str(audio_path)}, {"paths": {}})

    assert result["clap_meta"]["status"] == "unavailable"
    assert result["clap_meta"]["reason"] == "model_not_cached"
    assert result["clap_meta"]["model"] == "laion/clap-htsat-unfused"
    assert "bootstrap_models.py" in result["clap_meta"]["install_hint"]


def test_audio_embed_clap_force_cpu_env_overrides_cuda(monkeypatch) -> None:
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    monkeypatch.setenv("GOODQ_CLAP_FORCE_CPU", "1")
    from steps.audio_embed_clap import step as clap_step

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: True)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert clap_step._preferred_device() == "cpu"


def test_audio_embed_clap_qdrant_payload_keeps_scene_video_metadata(monkeypatch) -> None:
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    from steps.audio_embed_clap.step import _build_qdrant_audio_payload

    payload = _build_qdrant_audio_payload(
        {
            "scene_id": "scene-alpha",
            "scene_index": 7,
            "video_id": "video-alpha",
            "video_hash": "hash-alpha",
            "scene": {"start": 12.5, "end": 15.0, "duration": 2.5},
            "audio_backend_effective": "wsl",
        },
        source_path="processing/audio/scene_0007.wav",
        faiss_id=12345,
        embedding_id="embedding-alpha",
        created_at="2026-04-30T12:05:43+00:00",
        cfg={"run": {"id": "run-alpha"}},
    )

    assert payload == {
        "source_path": "processing/audio/scene_0007.wav",
        "modality": "audio",
        "faiss_id": 12345,
        "embedding_id": "embedding-alpha",
        "component": "audio_embed_clap",
        "step": "audio_embed_clap",
        "model": "laion/clap-htsat-unfused",
        "created_at": "2026-04-30T12:05:43+00:00",
        "commit_ts_utc": "2026-04-30T12:05:43+00:00",
        "ucf_promotion_status": "staged",
        "run_id": "run-alpha",
        "scene_id": "scene-alpha",
        "video_id": "video-alpha",
        "video_hash": "hash-alpha",
        "start": 12.5,
        "end": 15.0,
        "duration": 2.5,
        "scene_index": 7,
        "audio_backend_effective": "wsl",
    }


def test_audio_embed_clap_qdrant_payload_without_run_id_does_not_claim_current_run(monkeypatch) -> None:
    monkeypatch.delenv("GOODQ_RUN_ID", raising=False)
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    from steps.audio_embed_clap.step import _build_qdrant_audio_payload

    payload = _build_qdrant_audio_payload(
        {
            "scene_id": "scene-alpha",
            "scene_index": 7,
            "video_id": "video-alpha",
        },
        source_path="processing/audio/scene_0007.wav",
        faiss_id=12345,
        embedding_id="embedding-alpha",
        created_at="2026-04-30T12:05:43+00:00",
    )

    assert payload["scene_id"] == "scene-alpha"
    assert payload["embedding_id"] == "embedding-alpha"
    assert payload["component"] == "audio_embed_clap"
    assert payload["model"] == "laion/clap-htsat-unfused"
    assert payload["created_at"] == "2026-04-30T12:05:43+00:00"
    assert "run_id" not in payload


def test_audio_embed_clap_runtime_upsert_sends_qdrant_provenance(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    from steps.audio_embed_clap import step as clap_step

    audio_path = tmp_path / "scene.wav"
    _write_silent_wav(audio_path, frames=16000)

    import numpy as np

    class _FakeInputFeatures:
        def to(self, _device):
            return self

    class _FakeFeatures:
        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.array([[0.25, 0.5, 0.75]], dtype="float32")

    class _FakeProcessor:
        def __call__(self, **_kwargs):
            return {"input_features": _FakeInputFeatures()}

    class _FakeModel:
        def get_audio_features(self, *, input_features):
            assert isinstance(input_features, _FakeInputFeatures)
            return _FakeFeatures()

    qdrant_points = []
    emitted_events = []
    sqlite_embeddings = []
    faiss_writes = []

    class _FakeQdrantClient:
        cfg = types.SimpleNamespace(collection="goodq_audio_test")

        def upsert(self, points):
            qdrant_points.extend(points)
            return True

    class _FakeIndex:
        def __init__(self, _dim, _neighbors):
            self.hnsw = types.SimpleNamespace(efConstruction=None, efSearch=None)
            self.ntotal = 0

        def add_with_ids(self, feats, ids):
            assert feats.shape == (1, 3)
            self.ntotal += len(ids)

        def add(self, feats):
            self.ntotal += len(feats)

    fake_torch = types.ModuleType("torch")
    fake_librosa = types.ModuleType("librosa")
    fake_librosa.load = lambda _path, sr, mono: (np.array([0.1, -0.2], dtype="float32"), sr)

    fake_faiss = types.ModuleType("faiss")
    fake_faiss.IndexHNSWFlat = _FakeIndex
    fake_faiss.IndexIDMap2 = lambda base: base
    fake_faiss.read_index = lambda _path: _FakeIndex(3, 32)
    fake_faiss.write_index = lambda index, path: faiss_writes.append((index, path))

    fake_text_step = types.ModuleType("steps.text_embed.step")
    fake_text_step._content_fingerprint = lambda _item: "0123456789abcdef0123456789abcdef"

    fake_memory = types.ModuleType("steps.common.memory")

    def _fake_upsert_embedding(*args, **kwargs):
        sqlite_embeddings.append((args, kwargs))

    fake_memory.upsert_embedding = _fake_upsert_embedding

    fake_commit_events = types.ModuleType("steps.common.memory_commit_events")
    fake_commit_events.utc_now_iso = lambda: "2026-05-01T12:00:00+00:00"

    class _FakeMemoryCommitEvent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_commit_events.MemoryCommitEvent = _FakeMemoryCommitEvent
    fake_commit_events.emit_memory_commit_event = lambda _cfg, event: emitted_events.append(event)

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "librosa", fake_librosa)
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)
    monkeypatch.setitem(sys.modules, "steps.text_embed.step", fake_text_step)
    monkeypatch.setitem(sys.modules, "steps.common.memory", fake_memory)
    monkeypatch.setitem(sys.modules, "steps.common.memory_commit_events", fake_commit_events)

    monkeypatch.setattr(clap_step, "_inspect_audio_input", lambda _path: None)
    monkeypatch.setattr(clap_step, "_torchaudio_preflight", lambda: True)
    monkeypatch.setattr(clap_step, "_preferred_device", lambda: "cpu")
    monkeypatch.setattr(clap_step, "_load", lambda _device: (True, None))
    monkeypatch.setattr(clap_step, "build_qdrant_client", lambda _cfg, dim, key: _FakeQdrantClient())
    monkeypatch.setitem(clap_step._CLAP, "model", _FakeModel())
    monkeypatch.setitem(clap_step._CLAP, "proc", _FakeProcessor())
    monkeypatch.setitem(clap_step._CLAP, "device", "cpu")
    monkeypatch.setitem(clap_step._CLAP, "model_dir", str(tmp_path / "models"))

    result = clap_step.audio_embed_clap(
        {
            "source_path": str(audio_path),
            "scene_id": "scene-alpha",
            "scene_index": 7,
            "video_id": "video-alpha",
            "video_hash": "hash-alpha",
            "scene": {"start": 12.5, "end": 15.0, "duration": 2.5},
            "audio_backend_effective": "wsl",
        },
        {
            "run": {"id": "run-alpha"},
            "vad_enabled": False,
            "paths": {
                "faiss_audio_path": str(tmp_path / "faiss" / "audio.index"),
                "db_path": str(tmp_path / "memory.db"),
            },
        },
    )

    assert result["clap_meta"]["status"] == "ok"
    assert result["clap_meta"]["component"] == "audio_embed_clap"
    assert result["clap_meta"]["step"] == "audio_embed_clap"
    assert result["clap_meta"]["model"] == "laion/clap-htsat-unfused"
    assert result["clap_meta"]["run_id"] == "run-alpha"
    assert result["clap_meta"]["embedding_id"] == "0123456789abcdef0123456789abcdef"
    assert result["clap_meta"]["commit_ts_utc"] == "2026-05-01T12:00:00+00:00"
    assert result["clap_meta"]["qdrant_attempted"] is True
    assert result["clap_meta"]["qdrant_committed"] is True
    assert result["clap_meta"]["qdrant_collection"] == "goodq_audio_test"
    assert "source_path" not in result["clap_meta"]
    assert len(faiss_writes) == 1
    assert len(qdrant_points) == 1
    assert len(sqlite_embeddings) == 1
    assert len(emitted_events) == 1

    point = qdrant_points[0]
    assert point["id"] == "0123456789abcdef0123456789abcdef"
    assert point["vector"] == [0.25, 0.5, 0.75]

    payload = point["payload"]
    assert payload["run_id"] == "run-alpha"
    assert payload["embedding_id"] == "0123456789abcdef0123456789abcdef"
    assert payload["component"] == "audio_embed_clap"
    assert payload["step"] == "audio_embed_clap"
    assert payload["model"] == "laion/clap-htsat-unfused"
    assert payload["created_at"] == "2026-05-01T12:00:00+00:00"
    assert payload["commit_ts_utc"] == "2026-05-01T12:00:00+00:00"
    assert payload["source_path"] == str(audio_path)
    assert payload["scene_id"] == "scene-alpha"
    assert payload["video_id"] == "video-alpha"
    assert payload["video_hash"] == "hash-alpha"
    assert payload["scene_index"] == 7
    assert payload["audio_backend_effective"] == "wsl"


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


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_reason"),
    [
        ({}, "no_text", "no_text"),
        ({"transcript": "hi"}, "skipped", "too_short"),
    ],
)
def test_sentiment_guards_skip_invalid_text_inputs(
    payload,
    expected_status: str,
    expected_reason: str,
):
    from steps.sentiment.step import sentiment

    result = sentiment(payload, {"config": {}})

    assert result["sentiment"] is None
    assert result["sentiment_meta"]["status"] == expected_status
    assert result["sentiment_meta"]["reason"] == expected_reason


def test_emotion_classify_surfaces_model_unavailable_reason(monkeypatch):
    from steps.emotion_classify import step as emotion_step

    monkeypatch.setitem(emotion_step._EMO, "model", None)
    monkeypatch.setitem(emotion_step._EMO, "tok", None)
    monkeypatch.setitem(emotion_step._EMO, "labels", [])
    monkeypatch.setitem(emotion_step._EMO, "device", "cpu")
    monkeypatch.setitem(emotion_step._EMO, "error", "torch.load safety gate requires torch 2.6")
    monkeypatch.setattr(emotion_step, "_load_emotion", lambda: None)

    result = emotion_step.emotion_classify({"transcript": "family memory with laughter"}, {"config": {}})

    assert result["emotions"] is None
    assert result["emotion_meta"]["status"] == "unavailable"
    assert result["emotion_meta"]["engine"] == "cardiffnlp"
    assert result["emotion_meta"]["reason"] == "model_load_failed"
    assert "torch.load safety gate" in result["emotion_meta"]["error"]


def test_emotion_classify_loads_sequence_model_with_safetensors(monkeypatch):
    import sys
    import types

    from steps.emotion_classify import step as emotion_step

    monkeypatch.setitem(emotion_step._EMO, "model", None)
    monkeypatch.setitem(emotion_step._EMO, "tok", None)
    monkeypatch.setitem(emotion_step._EMO, "labels", [])
    monkeypatch.setitem(emotion_step._EMO, "device", "cpu")
    monkeypatch.setitem(emotion_step._EMO, "error", None)
    monkeypatch.setattr(
        emotion_step,
        "setup_step_gpu",
        lambda step_name: {"device": "cpu", "step_name": step_name},
    )

    fake_torch = types.ModuleType("torch")
    fake_transformers = types.ModuleType("transformers")
    model_kwargs = {}

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, name):
            return cls()

    class FakeModel:
        @classmethod
        def from_pretrained(cls, name, **kwargs):
            model_kwargs.update(kwargs)
            return cls()

        def to(self, device):
            return self

        def eval(self):
            return self

    fake_transformers.AutoTokenizer = FakeTokenizer
    fake_transformers.AutoModelForSequenceClassification = FakeModel
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    emotion_step._load_emotion()

    assert model_kwargs["use_safetensors"] is True
    assert emotion_step._EMO["model"] is not None


@pytest.mark.parametrize(
    ("step_name", "result", "expected_status", "expected_reason", "expected_embedding"),
    [
        (
            "audio_embed_clap",
            {"clap_meta": {"status": "skipped", "reason": "audio_silent"}},
            "skipped",
            "audio_embed_clap_audio_silent",
            False,
        ),
        (
            "audio_emotion",
            {"audio_emotion_meta": {"status": "unavailable"}},
            "skipped",
            "audio_emotion_unavailable",
            False,
        ),
        (
            "emotion_classify",
            {"emotion_meta": {"status": "no_text"}},
            "skipped",
            "emotion_classify_no_text",
            False,
        ),
        (
            "sentiment",
            {"sentiment_meta": {"status": "skipped", "reason": "too_short"}},
            "skipped",
            "sentiment_too_short",
            False,
        ),
    ],
)
def test_step_runner_meta_outcome_preserves_optional_skip_observability(
    step_name: str,
    result: dict,
    expected_status: str,
    expected_reason: str,
    expected_embedding: bool,
):
    from cli.step_runner import _derive_step_log_outcome

    status, error, extra = _derive_step_log_outcome(step_name, result, verbose=False)

    assert status == expected_status
    assert error is None
    assert extra is not None
    assert extra["reason"] == expected_reason
    assert extra["embedding_emitted"] is expected_embedding


def test_step_runner_meta_outcome_surfaces_optional_structured_error():
    from cli.step_runner import _derive_step_log_outcome

    status, error, extra = _derive_step_log_outcome(
        "image_caption",
        {"caption_meta": {"status": "error", "error": "CUDA out of memory"}},
        verbose=False,
    )

    assert status == "error"
    assert error == "CUDA out of memory"
    assert extra is not None
    assert extra["reason"] == "image_caption_error"
