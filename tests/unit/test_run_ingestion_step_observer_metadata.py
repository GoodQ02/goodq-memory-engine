from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest
import typer

from tests.unit.test_witness_admission import candidate, qdrant_transport


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


class _RecorderObserver:
    def __init__(self) -> None:
        self.enabled = True
        self.events = []

    def step_start(self, step, *, total=None, metadata=None):
        self.events.append(("step_start", step, dict(metadata or {})))

    def step_end(self, step, *, metadata=None):
        self.events.append(("step_end", step, dict(metadata or {})))

    def step_error(self, step, *, error, metadata=None):
        self.events.append(("step_error", step, error, dict(metadata or {})))

    def begin_heartbeat(self, step, *, metadata=None):
        self.events.append(("heartbeat_begin", step, dict(metadata or {})))

        def _stop():
            self.events.append(("heartbeat_end", step, dict(metadata or {})))

        return _stop


@pytest.mark.parametrize(
    ("worker_result", "expected_status"),
    [
        (None, "invalid_worker_result"),
        ("not-json", "invalid_worker_result"),
        ({}, "no_transcript_output"),
    ],
)
def test_local_transcription_result_always_has_terminal_metadata(worker_result, expected_status):
    run_ingestion = _load_run_ingestion_module()

    normalized = run_ingestion._normalize_local_transcription_result(worker_result)

    assert normalized["transcript"] is None
    assert normalized["transcript_meta"]["status"] == expected_status
    assert normalized["transcript_meta"]["engine"] == "goodq_audio_transcribe"


def test_local_transcription_result_preserves_worker_failure_metadata():
    run_ingestion = _load_run_ingestion_module()
    worker_result = {
        "transcript": None,
        "transcript_meta": {
            "status": "failed",
            "engine": "hybrid_whisper",
            "model": "medium",
            "device": "cpu",
            "reason": "no_speech_detected",
        },
    }

    normalized = run_ingestion._normalize_local_transcription_result(worker_result)

    assert normalized == worker_result


def test_local_transcription_result_unwraps_successful_async_step_outputs():
    run_ingestion = _load_run_ingestion_module()
    worker_result = {
        "step_name": "audio_transcribe_local",
        "status": "ok",
        "outputs": {
            "transcript": "A real transcript from the worker.",
            "segments": [{"start": 0.0, "end": 1.0, "text": "A real transcript from the worker."}],
            "transcript_meta": {
                "status": "ok",
                "engine": "hybrid_whisper",
                "device": "cpu",
            },
        },
    }

    normalized = run_ingestion._normalize_local_transcription_result(worker_result)

    assert normalized == worker_result["outputs"]
    assert normalized["transcript_meta"]["status"] == "ok"


class _FakePopenSuccess:
    def __init__(self, *args, **kwargs):
        self.pid = 4242
        self.returncode = 0

    def communicate(self, timeout=None):
        return "{}", ""

    def kill(self):
        self.returncode = -9


class _FakePopenFailure:
    def __init__(self, *args, **kwargs):
        self.pid = 5353
        self.returncode = 1

    def communicate(self, timeout=None):
        return "", "simulated_step_failure"

    def kill(self):
        self.returncode = -9


class _FakeSequencedPopen:
    calls = []
    responses = []
    captured_envs = []

    def __init__(self, cmd, *args, **kwargs):
        type(self).calls.append(list(cmd))
        type(self).captured_envs.append(dict(kwargs.get("env") or {}))
        response = type(self).responses.pop(0)
        self.pid = response.get("pid", 6464)
        self.returncode = response["returncode"]
        self._stdout = response.get("stdout", "")
        self._stderr = response.get("stderr", "")

    def communicate(self, timeout=None):
        return self._stdout, self._stderr

    def kill(self):
        self.returncode = -9


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakePopenCaptureEnv:
    captured_env = None

    def __init__(self, *args, **kwargs):
        type(self).captured_env = dict(kwargs.get("env") or {})
        self.pid = 7171
        self.returncode = 0

    def communicate(self, timeout=None):
        return "{}", ""

    def kill(self):
        self.returncode = -9


def _write_cfg(tmp_path: Path, *, host: dict | None = None) -> Path:
    cfg_json = tmp_path / "cfg.json"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    cfg_payload = {
        "run": {"id": "run_test"},
        "paths": {
            "data_root": str(runtime_root),
            "import_inbox": str(runtime_root / "import_inbox"),
            "processing": str(runtime_root / "processing"),
            "log_dir": str(runtime_root / "logs"),
            "db_path": str(runtime_root / "memory.db"),
            "knowledge_graph_db": str(runtime_root / "knowledge_graph.db"),
            "qdrant_storage": str(runtime_root / "qdrant_storage"),
            "models_cache": str(runtime_root / "models"),
        },
    }
    if host:
        cfg_payload["host"] = host
    cfg_json.write_text(json.dumps(cfg_payload), encoding="utf-8")
    return cfg_json


def test_finalize_capability_receipt_writes_degraded_receipt_from_current_run_evidence(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "step_runs.jsonl").write_text(
        json.dumps(
            {
                "run_id": "receipt-run",
                "step": "audio_embed_clap",
                "status": "error",
                "error": "model unavailable",
                "extra": {"optional": True, "reason": "optional_step_failed"},
                "scene_id": "scene-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        run_ingestion,
        "_CURRENT_RUN_CONTEXT",
        {"id": "receipt-run", "warnings": [{"code": "optional_step_failed"}]},
    )
    output = tmp_path / "output" / "scene_ingest_results.json"

    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed",
        cfg={"paths": {"log_dir": str(log_dir)}, "host": {"profile": "BASELINE"}},
        results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=output,
    )

    persisted = json.loads((output.parent / "capability_receipt.json").read_text(encoding="utf-8"))
    assert receipt["outcome"] == "degraded"
    assert persisted["capabilities_by_step"]["audio_embed_clap"]["reason"] == "optional_step_failed"


def test_current_run_capability_reader_counts_malformed_fresh_log_rows(
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "step_runs.jsonl").write_text(
        "{not-json}\n"
        + json.dumps(
            {"run_id": "other-run", "step": "image_ocr", "status": "ok"}
        )
        + "\n"
        + json.dumps(
            {"run_id": "receipt-run", "step": "unknown_step", "status": "ok"}
        )
        + "\n"
        + json.dumps(
            {
                "run_id": "receipt-run",
                "step": "audio_unified_wsl2",
                "status": "ok",
            }
        )
        + "\n"
        + "".join(
            json.dumps({"run_id": "receipt-run", "step": step, "status": "ok"})
            + "\n"
            for step in (
                "video_scene_detect",
                "text_embed",
                "text_embed",
                "scene_visual_embeddings",
                "cross_modal_harmonization",
            )
        )
        + json.dumps(
            {
                "run_id": "receipt-run",
                "step": "image_ocr",
                "status": "ok",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows, malformed_count = run_ingestion._read_current_run_capability_rows(
        {"paths": {"log_dir": str(log_dir)}},
        "receipt-run",
    )

    assert [row["step"] for row in rows] == ["image_ocr"]
    assert malformed_count == 2


def test_release_capability_receipt_fails_closed_on_incomplete_profile_evidence(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "step_runs.jsonl").write_text(
        json.dumps(
            {
                "run_id": "release-receipt-run",
                "step": "audio_transcribe_local",
                "status": "ok",
                "scene_id": "scene-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        run_ingestion,
        "_CURRENT_RUN_CONTEXT",
        {"id": "release-receipt-run", "warnings": []},
    )
    output = tmp_path / "output" / "scene_ingest_results.json"

    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed",
        cfg={
            "paths": {"log_dir": str(log_dir)},
            "host": {"profile": "PUBLIC_GPU_ENHANCED"},
        },
        results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=output,
        input_count=1,
        release_validation=True,
    )

    assert receipt["schema_version"] == 2
    assert receipt["full_coverage"] is True
    assert receipt["outcome"] == "failed"
    assert receipt["summary"]["missing_expected"] > 0
    assert "capability_profile_contract" in receipt["evidence"]


def test_release_validation_requires_an_explicit_isolated_config() -> None:
    run_ingestion = _load_run_ingestion_module()

    with pytest.raises(typer.BadParameter, match="explicit --config"):
        run_ingestion._validate_release_validation_request(
            release_validation=True,
            config=None,
        )


def test_failed_release_receipt_raises_terminal_exit() -> None:
    run_ingestion = _load_run_ingestion_module()

    with pytest.raises(typer.Exit) as excinfo:
        run_ingestion._enforce_release_capability_receipt(
            {"outcome": "failed"},
            release_validation=True,
        )

    assert excinfo.value.exit_code == 1


def test_release_validation_zero_video_run_passes_zero_input_and_exits(
    monkeypatch,
    tmp_path: Path,
    candidate,
    qdrant_transport,
) -> None:
    from cli.witness_environment import build_witness_environment
    from steps.common import progress_tracker

    run_ingestion = _load_run_ingestion_module()
    cfg, config_path, _source = candidate
    root = Path(cfg["witness"]["artifact_root"])
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output = root / "output" / "results.json"
    workspace = root / "workspace"
    captured: dict[str, object] = {}

    # Supply a valid bound witness rather than bypassing its loader or guards.
    # Only the external Qdrant transport is faked by the shared admission fixture.
    for key, value in build_witness_environment(config_path, {}).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(progress_tracker, "LOGS_DIR", Path(cfg["paths"]["log_dir"]))
    monkeypatch.setattr(progress_tracker.ProgressTracker, "_instance", None)
    monkeypatch.setattr(progress_tracker, "_tracker", progress_tracker.ProgressTracker())
    monkeypatch.setattr(
        run_ingestion,
        "_select_ingest_videos",
        lambda selected, explicit: (selected, []),
    )
    monkeypatch.setattr(run_ingestion, "is_baseline", lambda: False)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(
        run_ingestion,
        "_resolve_audio_runtime_contract",
        lambda _cfg: {"selected": "none", "reason": "test"},
    )
    monkeypatch.setattr(
        run_ingestion,
        "_write_cfg_snapshot",
        lambda _cfg, _workspace: tmp_path / "resolved.json",
    )
    monkeypatch.setattr(run_ingestion, "_resolve_processing_root", lambda _cfg: tmp_path)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda _cfg: "ffmpeg")
    monkeypatch.setattr(
        run_ingestion.PipelineObserver,
        "from_runtime",
        lambda **_kwargs: None,
    )

    def _finalize(**kwargs):
        captured.update(kwargs)
        return {"outcome": "failed"}

    monkeypatch.setattr(run_ingestion, "_finalize_capability_receipt", _finalize)

    with pytest.raises(typer.Exit) as excinfo:
        run_ingestion.run(
            input_dir=input_dir,
            input_file=None,
            config=config_path,
            output=output,
            workspace=workspace,
            max_videos=0,
            max_scenes=0,
            scene_threshold=None,
            min_scene_seconds=None,
            force_reprocess=False,
            verbose=False,
            step_timeout=None,
            chunk_size=300.0,
            chunk_overlap=10.0,
            enable_control_agent=False,
            enable_auto_healing=False,
            scene_start_index=None,
            scene_end_index=None,
            scene_indices=None,
            release_validation=True,
        )

    assert excinfo.value.exit_code == 1
    assert captured["input_count"] == 0
    assert captured["release_validation"] is True
    assert captured["cfg"]["ingestion_isolation"] is True
    assert captured["cfg"]["witness"]["promotion_enabled"] is False
    admission = json.loads((root / "witness-admission.json").read_text(encoding="utf-8"))
    assert admission["status"] == "admitted"
    assert set(qdrant_transport["created"]) == set(cfg["qdrant"]["collections"].values())


def test_wsl_component_outcomes_are_logged_as_independent_capability_rows(
    monkeypatch,
) -> None:
    run_ingestion = _load_run_ingestion_module()
    logged: list[dict[str, object]] = []

    def _log_step_run(cfg, step, item, duration_ms, status, error=None, *, extra=None):
        logged.append(
            {
                "step": step,
                "status": status,
                "error": error,
                "extra": dict(extra or {}),
            }
        )

    monkeypatch.setattr(run_ingestion, "log_step_run", _log_step_run)
    run_ingestion._log_wsl_capability_outcomes(
        cfg={"paths": {"log_dir": "unused"}},
        item={"scene_id": "scene-1"},
        duration_ms=125.0,
        outcomes={
            "transcription": {"status": "ok", "reason": "transcript_emitted"},
            "diarization": {"status": "ok", "reason": "speaker_tracks_emitted"},
            "acoustic_emotion": {"status": "ok", "reason": "emotion_emitted"},
            "wav2vec2": {"status": "ok", "reason": "embedding_emitted"},
            "clap_handoff": {
                "status": "ok",
                "reason": "canonical_clap_required",
            },
        },
    )

    assert [row["step"] for row in logged] == [
        "audio_transcribe_local",
        "audio_speaker_merge",
        "audio_emotion",
        "audio_wav2vec2_enrichment",
        "audio_clap_handoff",
    ]
    assert all(row["status"] == "ok" for row in logged)
    assert logged[-1]["extra"]["component"] == "clap_handoff"


def test_base_env_enforces_python_no_user_site(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(tmp_path)

    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)

    env = run_ingestion._base_env(cfg_json)

    assert env["PYTHONNOUSERSITE"] == "1"


def test_base_env_prefers_cfg_gpu_profile_over_stale_no_auto_gpu(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "GPU_ENHANCED", "require_gpu": True},
    )

    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "GPU_ENHANCED"
    assert env["GOODQ_REQUIRE_GPU"] == "1"
    assert env.get("GOODQ_NO_AUTO_GPU") != "1"


def test_base_env_normalizes_public_gpu_profile_to_the_internal_gpu_contract(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "PUBLIC_GPU_ENHANCED", "require_gpu": True},
    )

    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "GPU_ENHANCED"
    assert env["GOODQ_REQUIRE_GPU"] == "1"
    assert env.get("GOODQ_NO_AUTO_GPU") != "1"


def test_base_env_forces_no_auto_gpu_for_baseline_profile(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "BASELINE", "require_gpu": False},
    )

    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "BASELINE"
    assert env["GOODQ_NO_AUTO_GPU"] == "1"


def test_base_env_baseline_clears_stale_require_gpu(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "BASELINE"},
    )

    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)

    env = run_ingestion._base_env(cfg_json)

    assert env["GOODQ_HOST_PROFILE"] == "BASELINE"
    assert env["GOODQ_REQUIRE_GPU"] == "0"
    assert env["GOODQ_NO_AUTO_GPU"] == "1"


def test_run_step_success_emits_scene_metadata_and_pid(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_core_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenSuccess)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_001",
        "scene_id": "scene_0007",
        "scene_index": 7,
    }

    result = run_ingestion._run_step(
        env_name="goodq_core",
        step_name="dummy_step",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}

    start_events = [event for event in observer.events if event[0] == "step_start" and event[1] == "step.dummy_step"]
    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.dummy_step"]
    assert start_events
    assert end_events

    start_meta = start_events[0][2]
    end_meta = end_events[0][2]
    for meta in (start_meta, end_meta):
        assert meta["scene_id"] == "scene_0007"
        assert meta["scene_index"] == 7
        assert meta["video_id"] == "video_test_001"
        assert isinstance(meta["subprocess_pid"], int)
        assert meta["subprocess_pid"] > 0
        assert meta["launcher"] == "direct_env_python"


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("case", ["required", "required_override", "allowed_fallback", "baseline"])
def test_clap_admission_uses_resolved_worker_gpu_policy(monkeypatch, tmp_path, asynchronous, case):
    import asyncio
    from common import vram_allocator
    import configs.python_paths as python_paths

    runner = _load_run_ingestion_module()
    required = case.startswith("required")
    cfg_json = _write_cfg(tmp_path, host={
        "profile": "BASELINE" if case == "baseline" else "GPU_ENHANCED",
        "require_gpu": required,
    })
    # Deliberately oppose the worker configuration, as in the saved CLAP failure.
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0" if required else "1")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    reservations, launches = [], []

    def deny(**kwargs):
        reservations.append(kwargs)
        return False

    monkeypatch.setattr(vram_allocator, "VRAMAllocator", lambda: types.SimpleNamespace(wait_and_reserve=deny))
    monkeypatch.setattr(runner, "_PIPELINE_OBSERVER", _RecorderObserver())
    monkeypatch.setattr(runner, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(runner.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: sys.executable)
    result_text = json.dumps({"clap_meta": {"status": "skipped", "reason": "test_no_audio"}})

    def launch(*args, **kwargs):
        launches.append(kwargs["env"])
        return types.SimpleNamespace(pid=12345, returncode=0, communicate=lambda **_: (result_text, ""))

    async def launch_async(*args, **kwargs):
        process = launch(*args, **kwargs)
        async def communicate():
            return result_text.encode(), b""
        process.communicate = communicate
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch_async)
    args = dict(env_name="goodq_audio_embed", step_name="audio_embed_clap",
                payload={"source_path": str(tmp_path / "saved.wav")}, cfg_json=cfg_json)
    if case == "required_override":
        args["_step_env_overrides"] = {"GOODQ_NO_AUTO_GPU": "1", "GOODQ_CLAP_FORCE_CPU": "1"}
    if required:
        if asynchronous:
            result = asyncio.run(runner._run_step_async(**args))
            assert result["status"] == "error"
            assert "GPU-required" in str(result["errors"])
        else:
            with pytest.raises(RuntimeError, match="GPU-required"):
                runner._run_step(**args)
        assert launches == []
        assert len(reservations) == (case == "required")
    else:
        if asynchronous:
            assert asyncio.run(runner._run_step_async(**args))["status"] == "skipped"
        else:
            assert runner._run_step(**args)["clap_meta"]["status"] == "skipped"
        assert len(launches) == 1
        assert launches[0]["GOODQ_REQUIRE_GPU"] == "0"
        assert launches[0]["GOODQ_NO_AUTO_GPU"] == "1"
        assert len(reservations) == (case == "allowed_fallback")
        if case == "allowed_fallback":
            assert launches[0]["GOODQ_CLAP_FORCE_CPU"] == "1"


@pytest.mark.parametrize("cancel_first", [False, True])
def test_overlapping_gpu_launches_keep_independent_claims(monkeypatch, tmp_path, cancel_first):
    import asyncio
    from common import vram_allocator as vram
    import configs.python_paths as python_paths

    runner = _load_run_ingestion_module()
    cfg = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": True})
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(vram, "REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(vram, "REGISTRY_PATH", tmp_path / "claims.json")
    monkeypatch.setattr(vram, "LOCK_PATH", tmp_path / "claims.lock")
    monkeypatch.setattr(vram, "pid_exists", lambda pid: True)
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", lambda self: (10000, 0))
    monkeypatch.setattr(vram.VRAMAllocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr(runner, "_PIPELINE_OBSERVER", _RecorderObserver())
    monkeypatch.setattr(runner, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(runner.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: sys.executable)

    async def scenario():
        both_spawned = asyncio.Event()
        both_running = asyncio.Event()
        workers = []
        class Worker:
            returncode = 0
            def __init__(self, pid):
                self.pid = pid
                self.done = asyncio.Event()
                self.started = False
                self.terminated = False
            async def communicate(self):
                self.started = True
                if all(w.started for w in workers):
                    both_running.set()
                await self.done.wait()
                return b'{"clap_meta":{"status":"ok"}}', b''
            def terminate(self):
                self.terminated = True
                self.done.set()
            async def wait(self):
                return 0
        async def launch(*a, **kw):
            worker = Worker(1001 + len(workers))
            workers.append(worker)
            if len(workers) == 2:
                claims = vram.VRAMAllocator()._read_registry()
                assert len(claims) == 2
                assert sum(c["claimed_vram_mb"] for c in claims.values()) == 4000
                assert {c["pid"] for c in claims.values()} == {os.getpid()}
                both_spawned.set()
            await both_spawned.wait()
            return worker
        monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch)
        tasks = [asyncio.create_task(runner._run_step_async(
            "goodq_audio_embed", "audio_embed_clap", {"scene_id": str(i)}, cfg,
        )) for i in range(2)]
        await asyncio.wait_for(both_running.wait(), timeout=5)
        claims = vram.VRAMAllocator()._read_registry()
        assert {c["pid"] for c in claims.values()} == {1001, 1002}
        if cancel_first:
            tasks[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[0]
        else:
            # Complete whichever task owns the first fake worker; task order need not equal launch order.
            workers[0].done.set()
            completed, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            assert len(completed) == 1
        assert len(vram.VRAMAllocator()._read_registry()) == 1
        for worker in workers:
            worker.done.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert sum(isinstance(r, asyncio.CancelledError) for r in results) == int(cancel_first)
        assert all(r["status"] == "ok" for r in results if isinstance(r, dict))
        assert sum(w.terminated for w in workers) == int(cancel_first)
        assert vram.VRAMAllocator()._read_registry() == {}
        assert not vram.LOCK_PATH.exists()
    asyncio.run(scenario())


def test_cancelled_admission_wait_drains_allocator_thread(monkeypatch, tmp_path):
    import asyncio
    import threading
    from common import vram_allocator as vram
    runner = _load_run_ingestion_module()
    cfg = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": True})
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(vram, "REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(vram, "REGISTRY_PATH", tmp_path / "claims.json")
    monkeypatch.setattr(vram, "LOCK_PATH", tmp_path / "claims.lock")
    monkeypatch.setattr(vram.VRAMAllocator, "start_heartbeat_daemon", lambda *a: None)
    entered, proceed, finished = threading.Event(), threading.Event(), threading.Event()
    def memory(self):
        entered.set()
        assert proceed.wait(5)
        return (10000, 0)  # Admission succeeds after task cancellation.
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", memory)
    original = vram.VRAMAllocator.wait_and_reserve
    def wait(self, *a, **kw):
        try:
            return original(self, *a, **kw)
        finally:
            finished.set()
    monkeypatch.setattr(vram.VRAMAllocator, "wait_and_reserve", wait)
    async def forbidden_launch(*a, **kw):
        pytest.fail("Cancelled admission must never launch a worker")
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", forbidden_launch)
    async def scenario():
        task = asyncio.create_task(runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg))
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        proceed.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
        assert vram.VRAMAllocator()._read_registry() == {}
    asyncio.run(scenario())


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure_point", ["tempdir", "spawn"])
def test_gpu_claim_released_when_launch_preparation_fails(monkeypatch, tmp_path, asynchronous, failure_point):
    import asyncio
    from common import vram_allocator as vram
    runner = _load_run_ingestion_module()
    cfg = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": True})
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(vram, "REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(vram, "REGISTRY_PATH", tmp_path / "claims.json")
    monkeypatch.setattr(vram, "LOCK_PATH", tmp_path / "claims.lock")
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", lambda self: (10000, 0))
    monkeypatch.setattr(vram.VRAMAllocator, "start_heartbeat_daemon", lambda *a: None)
    def fail(*a, **kw):
        assert len(vram.VRAMAllocator()._read_registry()) == 1
        raise OSError("isolated launch preparation failure")
    if failure_point == "tempdir":
        monkeypatch.setattr(runner.tempfile, "mkdtemp", fail)
    else:
        import configs.python_paths as python_paths
        monkeypatch.setattr(runner, "resolve_conda", lambda: "conda")
        monkeypatch.setattr(runner.shutil, "which", lambda _: "conda")
        monkeypatch.setattr(python_paths, "get_env_python", lambda _: sys.executable)
        monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
        monkeypatch.setattr(runner.subprocess, "Popen", fail)
        async def fail_async(*a, **kw):
            fail(*a, **kw)
        monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", fail_async)
    if asynchronous:
        result = asyncio.run(runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg))
        assert result["status"] == "error"
    else:
        with pytest.raises(OSError, match="launch preparation"):
            runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
    assert vram.VRAMAllocator()._read_registry() == {}


def test_run_step_sanitizes_stale_gpu_disable_flag_for_gpu_profile(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    cfg_json = _write_cfg(
        tmp_path,
        host={"profile": "GPU_ENHANCED", "require_gpu": True},
    )
    direct_env_python = tmp_path / "goodq_audio_embed_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakePopenCaptureEnv.captured_env = None
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenCaptureEnv)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    run_ingestion._run_step(
        env_name="goodq_audio_embed",
        step_name="audio_embed_clap",
        payload={"source_path": str(tmp_path / "dummy.wav")},
        cfg_json=cfg_json,
    )

    captured_env = _FakePopenCaptureEnv.captured_env or {}
    assert captured_env["GOODQ_HOST_PROFILE"] == "GPU_ENHANCED"
    assert captured_env["GOODQ_REQUIRE_GPU"] == "1"
    assert captured_env.get("GOODQ_NO_AUTO_GPU") != "1"


def test_run_step_failure_emits_step_error_with_scene_metadata_and_pid(monkeypatch, tmp_path: Path):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)

    import configs.python_paths as python_paths

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakePopenFailure)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(run_ingestion, "_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS", False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: None)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_002",
        "scene": {"index": 12},
        "scene_id": "scene_0012",
    }

    with pytest.raises(RuntimeError, match="Step dummy_step failed"):
        run_ingestion._run_step(
            env_name="goodq_core",
            step_name="dummy_step",
            payload=payload,
            cfg_json=cfg_json,
        )

    error_events = [event for event in observer.events if event[0] == "step_error" and event[1] == "step.dummy_step"]
    assert error_events
    error_meta = error_events[0][3]

    assert error_meta["scene_id"] == "scene_0012"
    assert error_meta["scene_index"] == 12
    assert error_meta["video_id"] == "video_test_002"
    assert isinstance(error_meta["subprocess_pid"], int)
    assert error_meta["subprocess_pid"] > 0


def test_run_step_retries_optional_steps_via_direct_env_python_on_conda_tmp_failure(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_core_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 7171,
            "returncode": 1,
            "stdout": "",
            "stderr": (
                "Failed to run 'conda activate \"%USERPROFILE%\\\\miniconda3\\\\envs\\\\goodq_core\"'\n"
                "The process cannot access the file because it is being used by another process.\n"
                "ERROR conda.cli.main_run:execute(127): `conda run python ...` failed\n"
                "%TEMP%\\__conda_tmp_17331.txt"
            ),
        },
        {
            "pid": 8181,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(run_ingestion, "_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS", False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_003",
        "scene_id": "scene_0003",
        "scene_index": 3,
    }

    result = run_ingestion._run_step(
        env_name="goodq_core",
        step_name="sentiment",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    assert _FakeSequencedPopen.calls[0][0] == "conda"
    assert _FakeSequencedPopen.calls[0][1:4] == ["run", "-n", "goodq_core"]
    assert _FakeSequencedPopen.calls[1][0] == str(direct_env_python)
    assert _FakeSequencedPopen.calls[1][1].endswith("cli\\step_runner.py")

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.sentiment"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["launcher"] == "direct_env_python"
    assert end_meta["direct_env_fallback_attempt"] == 1
    assert end_meta["scene_id"] == "scene_0003"


def test_run_step_retries_sentiment_once_after_native_crash(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_core_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 9191,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "Loading weights:   0%|          | 0/104 [00:00<?, ?it/s]",
        },
        {
            "pid": 9292,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "dummy_input.json"),
        "video_id": "video_test_004",
        "scene_id": "scene_0004",
        "scene_index": 4,
    }

    result = run_ingestion._run_step(
        env_name="goodq_core",
        step_name="sentiment",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    assert _FakeSequencedPopen.calls[0][0] == str(direct_env_python)
    assert _FakeSequencedPopen.calls[1][0] == str(direct_env_python)

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.sentiment"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 1
    assert end_meta["scene_id"] == "scene_0004"


def test_run_step_retries_dino_with_amp_disable_then_cpu_fallback_after_native_crashes(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_image_caption_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 10101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native dino crash on first gpu attempt",
        },
        {
            "pid": 10102,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native dino crash on second gpu attempt",
        },
        {
            "pid": 10103,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0002.jpg"),
        "video_id": "video_test_dino",
        "scene_id": "scene_0002",
        "scene_index": 2,
    }

    result = run_ingestion._run_step(
        env_name="goodq_image_caption",
        step_name="image_embed_dino",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 3
    assert all(call[0] == str(direct_env_python) for call in _FakeSequencedPopen.calls)

    first_env, second_env, third_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_DINO_DISABLE_AMP") != "1"
    assert first_env.get("GOODQ_DINO_FORCE_CPU") != "1"
    assert second_env["GOODQ_DINO_DISABLE_AMP"] == "1"
    assert second_env.get("GOODQ_DINO_FORCE_CPU") != "1"
    assert third_env["GOODQ_DINO_DISABLE_AMP"] == "1"
    assert third_env["GOODQ_DINO_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.image_embed_dino"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 2
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0002"


def test_run_step_retries_image_caption_with_cpu_fallback_after_native_crash(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_caption_vlm_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 11101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native image caption crash on first gpu attempt",
        },
        {
            "pid": 11102,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0003.jpg"),
        "video_id": "video_test_caption",
        "scene_id": "scene_0003",
        "scene_index": 3,
    }

    result = run_ingestion._run_step(
        env_name="goodq_caption_vlm",
        step_name="image_caption",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    first_env, second_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_IMAGE_CAPTION_FORCE_CPU") != "1"
    assert second_env["GOODQ_IMAGE_CAPTION_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.image_caption"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 1
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0003"


def test_run_step_retries_object_detect_with_cpu_fallback_after_native_crash(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path)
    direct_env_python = tmp_path / "goodq_object_detect_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 12101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native object detect crash on gpu attempt",
        },
        {
            "pid": 12102,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0013.jpg"),
        "video_id": "video_test_detect",
        "scene_id": "scene_0013",
        "scene_index": 13,
    }

    result = run_ingestion._run_step(
        env_name="goodq_object_detect",
        step_name="object_detect",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    first_env, second_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_OBJECT_DETECT_FORCE_CPU") != "1"
    assert second_env["GOODQ_OBJECT_DETECT_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.object_detect"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 1
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0013"


def test_run_step_retries_audio_embed_clap_with_cpu_fallback_after_native_crash(
    monkeypatch,
    tmp_path: Path,
):
    run_ingestion = _load_run_ingestion_module()
    observer = _RecorderObserver()
    cfg_json = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": False})
    direct_env_python = tmp_path / "goodq_audio_embed_python.exe"
    direct_env_python.write_text("", encoding="utf-8")

    import configs.python_paths as python_paths

    _FakeSequencedPopen.calls = []
    _FakeSequencedPopen.captured_envs = []
    _FakeSequencedPopen.responses = [
        {
            "pid": 13101,
            "returncode": 3221226505,
            "stdout": "",
            "stderr": "native clap crash on gpu attempt",
        },
        {
            "pid": 13102,
            "returncode": 0,
            "stdout": "{}",
            "stderr": "",
        },
    ]

    monkeypatch.setattr(run_ingestion, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(run_ingestion, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(run_ingestion.subprocess, "Popen", _FakeSequencedPopen)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: direct_env_python)

    payload = {
        "source_path": str(tmp_path / "scene_0140.wav"),
        "video_id": "video_test_clap",
        "scene_id": "scene_0140",
        "scene_index": 140,
    }

    result = run_ingestion._run_step(
        env_name="goodq_audio_embed",
        step_name="audio_embed_clap",
        payload=payload,
        cfg_json=cfg_json,
    )

    assert result == {}
    assert len(_FakeSequencedPopen.calls) == 2
    first_env, second_env = _FakeSequencedPopen.captured_envs
    assert first_env.get("GOODQ_CLAP_FORCE_CPU") != "1"
    assert second_env["GOODQ_CLAP_FORCE_CPU"] == "1"

    end_events = [event for event in observer.events if event[0] == "step_end" and event[1] == "step.audio_embed_clap"]
    assert end_events
    end_meta = end_events[-1][2]
    assert end_meta["native_retry_attempt"] == 1
    assert end_meta["native_retry_mode"] == "cpu_fallback"
    assert end_meta["scene_id"] == "scene_0140"


def test_resolve_audio_runtime_contract_falls_back_from_stale_env_workspace(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/projects/goodq4all")

    probed_workspaces = []

    def _fake_probe(distro, workspace):
        probed_workspaces.append(workspace)
        if workspace == "/home/testuser/projects/goodq4all":
            return {
                "workspace_ready": False,
                "runtime_ready": False,
                "abi_ready": False,
                "detail": "workspace missing required files",
            }
        if workspace == "/home/testuser/goodq_audio":
            return {
                "workspace_ready": True,
                "runtime_ready": True,
                "abi_ready": True,
                "detail": "workspace and Python runtime are ready",
            }
        raise AssertionError(f"unexpected workspace probe: {workspace}")

    monkeypatch.setattr(run_ingestion, "probe_wsl_audio_runtime", _fake_probe)

    cfg = {
        "host": {
            "wsl_distro": "Ubuntu-22.04",
            "wsl_user": "testuser",
            "wsl_workspace": "/home/testuser/goodq_audio",
        }
    }

    contract = run_ingestion._resolve_audio_runtime_contract(cfg)

    assert probed_workspaces == [
        "/home/testuser/projects/goodq4all",
        "/home/testuser/goodq_audio",
    ]
    assert contract["selected"] == "wsl"
    assert contract["reason"] == "wsl_runtime_ready"
    assert contract["wsl_audio_workspace"] == "/home/testuser/goodq_audio"
    assert contract["wsl_workspace_source"] == "config"
    assert contract["workspace_ready"] is True
    assert contract["wsl_runtime_ready"] is True
    assert os.environ["GOODQ_WSL_WORKSPACE"] == "/home/testuser/goodq_audio"


def test_resolve_audio_runtime_contract_falls_back_from_stale_env_distro(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu")
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq_audio")

    probed_targets = []

    def _fake_probe(distro, workspace):
        probed_targets.append((distro, workspace))
        if distro == "Ubuntu":
            return {
                "workspace_ready": False,
                "runtime_ready": False,
                "abi_ready": False,
                "detail": "workspace missing required files",
            }
        if distro == "Ubuntu-22.04":
            return {
                "workspace_ready": True,
                "runtime_ready": True,
                "abi_ready": True,
                "detail": "workspace and Python runtime are ready",
            }
        raise AssertionError(f"unexpected distro probe: {distro}")

    monkeypatch.setattr(run_ingestion, "probe_wsl_audio_runtime", _fake_probe)

    cfg = {
        "host": {
            "wsl_distro": "Ubuntu-22.04",
            "wsl_user": "testuser",
            "wsl_workspace": "/home/testuser/goodq_audio",
        }
    }

    contract = run_ingestion._resolve_audio_runtime_contract(cfg)

    assert probed_targets == [
        ("Ubuntu", "/home/testuser/goodq_audio"),
        ("Ubuntu-22.04", "/home/testuser/goodq_audio"),
    ]
    assert contract["selected"] == "wsl"
    assert contract["reason"] == "wsl_runtime_ready"
    assert contract["wsl_distro"] == "Ubuntu-22.04"
    assert contract["wsl_distro_source"] == "config"
    assert contract["wsl_audio_workspace"] == "/home/testuser/goodq_audio"
    assert contract["workspace_ready"] is True
    assert "GOODQ_WSL_DISTRO=Ubuntu was unavailable" in contract["workspace_check_message"]
    assert os.environ["GOODQ_WSL_DISTRO"] == "Ubuntu-22.04"


def test_resolve_audio_runtime_contract_requires_distro_in_failure_message(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu")
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq_audio")
    monkeypatch.setattr(
        run_ingestion,
        "probe_wsl_audio_runtime",
        lambda *args, **kwargs: {
            "workspace_ready": False,
            "runtime_ready": False,
            "abi_ready": False,
            "detail": "workspace missing required files",
        },
    )

    cfg = {
        "host": {
            "wsl_distro": "Ubuntu-22.04",
            "wsl_user": "testuser",
            "wsl_workspace": "/home/testuser/goodq_audio",
        }
    }

    with pytest.raises(RuntimeError) as excinfo:
        run_ingestion._resolve_audio_runtime_contract(cfg)

    message = str(excinfo.value)
    assert "Ubuntu:/home/testuser/goodq_audio" in message
    assert "Ubuntu-22.04:/home/testuser/goodq_audio" in message
    assert "GOODQ_WSL_DISTRO, GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE" in message


def test_resolve_audio_runtime_contract_rejects_abi_degraded_transcription_runtime(
    monkeypatch,
):
    run_ingestion = _load_run_ingestion_module()

    monkeypatch.setattr(run_ingestion, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(run_ingestion, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(run_ingestion.shutil, "which", lambda name: "wsl" if name == "wsl" else None)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq_audio")
    monkeypatch.setattr(
        run_ingestion,
        "probe_wsl_audio_runtime",
        lambda *args, **kwargs: {
            "workspace_ready": True,
            "runtime_ready": True,
            "abi_ready": False,
            "detail": "transcription runtime ready; torchvision ABI unavailable (diarization may be degraded)",
        },
    )

    contract = run_ingestion._resolve_audio_runtime_contract(
        {
            "host": {
                "wsl_distro": "Ubuntu-22.04",
                "wsl_user": "testuser",
                "wsl_workspace": "/home/testuser/goodq_audio",
            }
        }
    )

    assert contract["selected"] == "none"
    assert contract["reason"] == "wsl_workspace_abi_degraded"
    assert contract["wsl_runtime_ready"] is True
    assert contract["wsl_abi_ready"] is False
    assert "transcription runtime ready" in contract["wsl_runtime_detail"]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("required", [False, True])
def test_clap_native_retry_honors_resolved_policy(monkeypatch, tmp_path, asynchronous, required):
    import asyncio
    from common import vram_allocator
    import configs.python_paths as python_paths

    runner = _load_run_ingestion_module()
    cfg = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": required})
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0" if required else "1")
    monkeypatch.delenv("GOODQ_NO_AUTO_GPU", raising=False)
    monkeypatch.delenv("GOODQ_CLAP_FORCE_CPU", raising=False)
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(vram_allocator, "VRAMAllocator", lambda: types.SimpleNamespace(
        wait_and_reserve=lambda **kw: True, update_pid=lambda *a: None, release=lambda *a: None))
    monkeypatch.setattr(runner, "_PIPELINE_OBSERVER", _RecorderObserver())
    monkeypatch.setattr(runner, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(runner.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: sys.executable)
    launches = []
    def launch(*args, **kwargs):
        launches.append(kwargs["env"])
        failed = len(launches) == 1
        return types.SimpleNamespace(pid=9876, returncode=3221226505 if failed else 0,
            communicate=lambda **kw: ("" if failed else '{}', "native crash" if failed else ""))
    async def launch_async(*args, **kwargs):
        process = launch(*args, **kwargs)
        stdout, stderr = process.communicate()
        async def communicate(): return stdout.encode(), stderr.encode()
        process.communicate = communicate
        return process
    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch_async)
    args = dict(env_name="goodq_audio_embed", step_name="audio_embed_clap", payload={}, cfg_json=cfg)
    if asynchronous:
        result = asyncio.run(runner._run_step_async(**args))
        if required: assert result["status"] == "error"
    elif required:
        with pytest.raises(RuntimeError): runner._run_step(**args)
    else:
        runner._run_step(**args)
    assert len(launches) == (1 if required else 2)
    if not required:
        assert launches[1]["GOODQ_CLAP_FORCE_CPU"] == "1"
        assert launches[1]["GOODQ_REQUIRE_GPU"] == "0"


def test_log_step_run_concurrent_processes_preserve_all_events_and_receipt_coverage(
    tmp_path: Path,
) -> None:
    import subprocess
    import time
    from lib.ingestion_capability_contract import build_capability_receipt

    runner = _load_run_ingestion_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_id = "concurrent-multiprocess-step-log-run"
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "run": {"id": run_id, "pipeline": "scene_ingest_cli", "timer_unit": "ms"},
    }

    worker_script = tmp_path / "concurrent_step_log_worker.py"
    worker_script.write_text(
        """from __future__ import annotations
import json
import sys
import time
from pathlib import Path

repo_root = Path(sys.argv[1])
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import steps.common.step_logger as step_logger
from steps.common.step_logger import log_step_run

step_logger.MISSION_LOGGER_AVAILABLE = False

log_dir = Path(sys.argv[2])
run_id = sys.argv[3]
proc_idx = int(sys.argv[4])
scenes_per_proc = int(sys.argv[5])
ready_file = Path(sys.argv[6])
go_file = Path(sys.argv[7])

cfg = {
    "paths": {"log_dir": str(log_dir)},
    "run": {"id": run_id, "pipeline": "scene_ingest_cli", "timer_unit": "ms"},
}

ready_file.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 15.0
while not go_file.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("Timed out waiting for start barrier")
    time.sleep(0.002)

unicode_text = "日本語テキスト • Ελληνικά • العربية • 🐋⛳🌊 • café naïve résumé — ∑∏√∞"
for offset in range(scenes_per_proc):
    scene_num = proc_idx * scenes_per_proc + offset
    scene_id = f"scene-{scene_num:04d}"
    for step_name, status, meta_key, meta_status in (
        ("audio_time_hints", "ok", "time_hints_meta", "ok"),
        ("audio_music_events", "not_applicable", "music_events_meta", "none"),
    ):
        event_id = f"proc-{proc_idx:02d}-scene-{scene_num:04d}-{step_name}"
        large_blob = f"blob-{event_id}-" + ("X" * 24576)
        log_step_run(
            cfg,
            step_name,
            {
                "modality": "audio",
                "source_path": f"{scene_id}_{unicode_text}.wav",
                "scene_id": scene_id,
                "scene_index": scene_num,
                "video_id": "video-hash-1",
                "video_hash": "video-hash-1",
            },
            12.345 + offset,
            status,
            extra={
                "event_id": event_id,
                "unicode_note": unicode_text,
                "large_blob": large_blob,
                "reason": "ok" if status == "ok" else "content_appropriate_empty",
                "result_meta": {
                    meta_key: {
                        "status": meta_status,
                        "reason": "ok" if status == "ok" else "content_appropriate_empty",
                    }
                },
                "embedding_emitted": False,
            },
        )
""",
        encoding="utf-8",
    )

    num_procs = 8
    scenes_per_proc = 3
    total_scenes = num_procs * scenes_per_proc
    expected_total_events = total_scenes * 2
    go_file = tmp_path / "go.barrier"
    ready_files = [tmp_path / f"ready_{idx}.flag" for idx in range(num_procs)]

    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(worker_script),
                str(Path(__file__).resolve().parents[2]),
                str(log_dir),
                run_id,
                str(idx),
                str(scenes_per_proc),
                str(ready_files[idx]),
                str(go_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for idx in range(num_procs)
    ]

    wait_deadline = time.monotonic() + 15.0
    while not all(rf.exists() for rf in ready_files):
        if time.monotonic() >= wait_deadline:
            for p in procs:
                p.kill()
            raise AssertionError("Workers did not reach ready barrier in time")
        time.sleep(0.005)

    go_file.write_text("go", encoding="utf-8")

    for idx, proc in enumerate(procs):
        stdout, stderr = proc.communicate(timeout=30)
        assert proc.returncode == 0, f"Worker {idx} failed: stdout={stdout}\nstderr={stderr}"

    jsonl_path = log_dir / "step_runs.jsonl"
    assert jsonl_path.is_file()
    raw_lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(raw_lines) == expected_total_events

    expected_unicode = "日本語テキスト • Ελληνικά • العربية • 🐋⛳🌊 • café naïve résumé — ∑∏√∞"
    seen_event_ids: set[str] = set()
    for line in raw_lines:
        parsed = json.loads(line)
        extra = parsed["extra"]
        event_id = extra["event_id"]
        assert event_id not in seen_event_ids
        seen_event_ids.add(event_id)
        assert extra["unicode_note"] == expected_unicode
        assert expected_unicode in parsed["source_path"]
        assert extra["large_blob"] == f"blob-{event_id}-" + ("X" * 24576)

    expected_event_ids = {
        f"proc-{proc_idx:02d}-scene-{proc_idx * scenes_per_proc + offset:04d}-{step_name}"
        for proc_idx in range(num_procs)
        for offset in range(scenes_per_proc)
        for step_name in ("audio_time_hints", "audio_music_events")
    }
    assert seen_event_ids == expected_event_ids

    step_rows, malformed_count = runner._read_current_run_capability_rows(cfg, run_id)
    assert malformed_count == 0
    assert len(step_rows) == expected_total_events

    scenes = [{"scene_id": f"scene-{i:04d}"} for i in range(total_scenes)]
    expected_capabilities = {
        "audio_time_hints": {
            "disposition": "runtime",
            "runtime_owner": "cli.run_ingestion",
            "implementation": "audio_time_hints",
            "status_surface": "time_hints_meta",
            "asset_ids": [],
            "content_applicability": "audio_present",
            "fallback_policy": "none",
        },
        "audio_music_events": {
            "disposition": "runtime",
            "runtime_owner": "cli.run_ingestion",
            "implementation": "audio_music_events",
            "status_surface": "music_events_meta",
            "asset_ids": [],
            "content_applicability": "music_present",
            "fallback_policy": "none",
        },
    }
    content_truth_by_scene = {
        f"scene-{i:04d}": {"audio_present": True, "music_present": False}
        for i in range(total_scenes)
    }
    receipt = build_capability_receipt(
        run_id=run_id,
        profile="PERSONAL_AIR_GAP",
        terminal_status="completed",
        step_rows=step_rows,
        warnings=[],
        scenes=scenes,
        evidence_paths={"step_runs": str(jsonl_path)},
        expected_capabilities=expected_capabilities,
        malformed_row_count=malformed_count,
        input_count=1,
        full_coverage=True,
        content_truth_by_scene=content_truth_by_scene,
    )
    assert receipt["summary"]["malformed_rows"] == 0
    assert receipt["summary"]["coverage_failures"] == 0
    assert receipt["summary"]["missing_expected"] == 0
    assert receipt["outcome"] == "completed"
    assert receipt["capabilities_by_step"]["audio_time_hints"]["status_counts"] == {"ok": total_scenes}
    assert receipt["capabilities_by_step"]["audio_music_events"]["status_counts"] == {
        "not_applicable": total_scenes
    }


def test_log_step_run_writer_failure_is_visible_rolls_back_partial_write_and_releases_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging
    import subprocess
    from steps.common import step_logger

    runner = _load_run_ingestion_module()
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)

    log_dir = tmp_path / "logs"
    run_id = "writer-failure-recovery-run"
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "run": {"id": run_id, "pipeline": "scene_ingest_cli", "timer_unit": "ms"},
    }

    # 1. Baseline successful write
    step_logger.log_step_run(
        cfg,
        "audio_time_hints",
        {"modality": "audio", "scene_id": "scene-0001"},
        10.0,
        "ok",
        extra={"event_id": "event-1"},
    )
    jsonl_path = log_dir / "step_runs.jsonl"
    baseline_bytes = jsonl_path.read_bytes()
    assert len(baseline_bytes.splitlines()) == 1

    # 2. Inject partial-write failure into os.write when writing to step_runs.jsonl
    real_os_write = step_logger.os.write
    real_os_open = step_logger.os.open
    tracked_jsonl_fds: set[int] = set()

    def _tracking_open(path: str, flags: int, mode: int = 0o777):
        fd = real_os_open(path, flags, mode)
        if str(path).endswith("step_runs.jsonl"):
            tracked_jsonl_fds.add(fd)
        return fd

    def _failing_partial_write(fd: int, data: bytes | memoryview) -> int:
        if fd in tracked_jsonl_fds:
            tracked_jsonl_fds.discard(fd)
            raw = bytes(data)
            half = max(1, len(raw) // 2)
            real_os_write(fd, raw[:half])
            raise OSError("simulated mid-record disk full")
        return real_os_write(fd, data)

    monkeypatch.setattr(step_logger.os, "open", _tracking_open)
    monkeypatch.setattr(step_logger.os, "write", _failing_partial_write)

    with caplog.at_level(logging.WARNING, logger="steps.common.step_logger"):
        step_logger.log_step_run(
            cfg,
            "audio_music_events",
            {"modality": "audio", "scene_id": "scene-0001"},
            15.0,
            "not_applicable",
            extra={"event_id": "event-failed-partial"},
        )

    assert "step_logger operation failed operation=write_step_run" in caplog.text
    assert "simulated mid-record disk full" in caplog.text

    # Partial write was truncated back to exact baseline bytes
    assert jsonl_path.read_bytes() == baseline_bytes

    # 3. Restore os.open/os.write and verify lock was NOT left held (both in-process and child process)
    monkeypatch.setattr(step_logger.os, "open", real_os_open)
    monkeypatch.setattr(step_logger.os, "write", real_os_write)

    step_logger.log_step_run(
        cfg,
        "audio_music_events",
        {"modality": "audio", "scene_id": "scene-0001"},
        15.0,
        "not_applicable",
        extra={"event_id": "event-2"},
    )

    child_code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import steps.common.step_logger as sl; sl.MISSION_LOGGER_AVAILABLE = False; "
        "sl.log_step_run({'paths': {'log_dir': sys.argv[2]}, 'run': {'id': sys.argv[3]}}, "
        "'sentiment', {'modality': 'audio', 'scene_id': 'scene-0001'}, 8.0, 'ok', extra={'event_id': 'event-3'})"
    )
    proc = subprocess.run(
        [sys.executable, "-c", child_code, str(Path(__file__).resolve().parents[2]), str(log_dir), run_id],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr

    step_rows, malformed_count = runner._read_current_run_capability_rows(cfg, run_id)
    assert malformed_count == 0
    assert [row["extra"]["event_id"] for row in step_rows] == ["event-1", "event-2", "event-3"]


def test_log_step_run_crashed_holder_process_does_not_permanently_lock_ledger(
    tmp_path: Path,
) -> None:
    import subprocess
    from steps.common import step_logger

    runner = _load_run_ingestion_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    lock_path = log_dir / step_logger._LOCK_FILENAME
    run_id = "crash-holder-recovery-run"
    cfg = {
        "paths": {"log_dir": str(log_dir)},
        "run": {"id": run_id, "pipeline": "scene_ingest_cli", "timer_unit": "ms"},
    }

    crash_code = (
        "import os, sys; sys.path.insert(0, sys.argv[1]); "
        "from steps.common.step_logger import _StepLogFileLock; "
        "lk = _StepLogFileLock(sys.argv[2]); lk.__enter__(); "
        "os._exit(1)"
    )
    crashed = subprocess.run(
        [sys.executable, "-c", crash_code, str(Path(__file__).resolve().parents[2]), str(lock_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert crashed.returncode == 1

    step_logger.log_step_run(
        cfg,
        "audio_transcribe_local",
        {"modality": "audio", "scene_id": "scene-after-crash"},
        20.0,
        "ok",
        extra={"event_id": "post-crash-event"},
    )
    step_rows, malformed_count = runner._read_current_run_capability_rows(cfg, run_id)
    assert malformed_count == 0
    assert len(step_rows) == 1
    assert step_rows[0]["extra"]["event_id"] == "post-crash-event"
