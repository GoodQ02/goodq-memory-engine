from __future__ import annotations

import json
import os
import sys
import types
import copy
import hashlib
import wave
import subprocess
from pathlib import Path
import pytest
import cli.watchdog as watchdog

from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg


def _write_fixture_wav(path):
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 16000)


def _retained_audio(processor, source):
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return processor.processing_dir / digest / f"{digest}.wav"


def test_pid_exists_with_psutil(monkeypatch) -> None:
    # Test path where psutil is available
    class MockPsutil:
        @staticmethod
        def pid_exists(pid: int) -> bool:
            return pid == 12345

    monkeypatch.setitem(sys.modules, "psutil", MockPsutil)
    
    assert watchdog._pid_exists(12345) is True
    assert watchdog._pid_exists(99999) is False


def test_pid_exists_windows_fallback(monkeypatch) -> None:
    # Test path where psutil is NOT available, on Windows
    monkeypatch.setitem(sys.modules, "psutil", None)
    monkeypatch.setattr(os, "name", "nt")

    class MockCompletedProcess:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.returncode = 0

    def mock_run(cmd, **kwargs):
        # cmd is ["tasklist", "/FI", "PID eq <pid>", "/NH"]
        pid_arg = cmd[2]
        if "12345" in pid_arg:
            return MockCompletedProcess("watchdog.exe                  12345 Console                    1      4,012 K")
        else:
            return MockCompletedProcess("INFO: No tasks are running which match the specified criteria.")

    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)

    assert watchdog._pid_exists(12345) is True
    assert watchdog._pid_exists(99999) is False


def test_pid_exists_posix_fallback(monkeypatch) -> None:
    # Test path where psutil is NOT available, on POSIX
    monkeypatch.setitem(sys.modules, "psutil", None)
    monkeypatch.setattr(os, "name", "posix")

    def mock_kill(pid: int, sig: int):
        if pid == 12345:
            return
        raise OSError(3, "No such process")

    monkeypatch.setattr(os, "kill", mock_kill)

    assert watchdog._pid_exists(12345) is True
    assert watchdog._pid_exists(99999) is False


def test_check_system_restart_events_windows(monkeypatch) -> None:
    # Test system restart events parser on Windows
    monkeypatch.setattr(os, "name", "nt")

    class MockCompletedProcess:
        def __init__(self, stdout: str, returncode: int = 0):
            self.stdout = stdout
            self.returncode = returncode

    fake_json = """
    {
        "TimeCreated": "/Date(1717200000000)/",
        "Id": 1074,
        "Message": "The process C:\\\\Windows\\\\system32\\\\shutdown.exe has initiated the restart..."
    }
    """
    
    called_cmd = []
    def mock_run(cmd, **kwargs):
        called_cmd.append(cmd)
        return MockCompletedProcess(fake_json)

    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Calling should run without errors
    watchdog._check_system_restart_events()
    assert len(called_cmd) == 1
    assert "powershell" in called_cmd[0][0]


def test_cleanup_stale_processing_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    cfg = _watchdog_cfg(tmp_path)
    processor = watchdog.WatchdogProcessor(cfg)

    processing_dir = Path(cfg["paths"]["processing"])

    # Create files in processing directory
    stale_video = processing_dir / "stale_video.mp4"
    stale_video.write_bytes(b"video")
    
    stale_tmp = processing_dir / "stale_temp.tmp"
    stale_tmp.write_bytes(b"temp")

    # Create a non-stale file (e.g. unknown extension/type)
    not_stale = processing_dir / "keep_me.txt"
    not_stale.write_bytes(b"keep")

    # Create a stale directory
    stale_dir = processing_dir / "video_123"
    stale_dir.mkdir()
    (stale_dir / "frame.jpg").write_bytes(b"frame")

    # Call cleanup_stale_processing_files
    processor.cleanup_stale_processing_files()

    # The stale_video should be unlinked/deleted
    assert not stale_video.exists()

    # The stale_tmp should be unlinked/deleted
    assert not stale_tmp.exists()

    # The stale_dir should be deleted
    assert not stale_dir.exists()

    # The not_stale file should NOT be deleted
    assert not_stale.exists()


def test_ingest_audio_prefers_wsl_unified_when_required(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: False)
    monkeypatch.setattr(watchdog, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(watchdog.shutil, "which", lambda name: "wsl.exe" if name == "wsl" else None)

    from steps.audio.audio_wsl2_bridge import unified_transcription_options
    bridge_module = types.ModuleType("steps.audio.audio_wsl2_bridge")
    bridge_module.unified_transcription_options = unified_transcription_options
    observed: dict[str, str] = {}

    def fake_audio_unified_wsl2(audio_path: str, *, scene_id=None, duration=None, **kwargs):
        observed["audio_path"] = audio_path
        observed["scene_id"] = scene_id
        observed["vocabulary"] = kwargs.get("transcription_vocabulary")
        return {
            "status": "success",
            "transcript": "hello from wsl",
            "segments": [],
            "wsl2_unified": True,
            "embeddings": [0.1, 0.2],
            "embedding_dim": 768,
            "embeddings_status": "success",
        }

    bridge_module.audio_unified_wsl2 = fake_audio_unified_wsl2
    monkeypatch.setitem(sys.modules, "steps.audio.audio_wsl2_bridge", bridge_module)

    cfg = _watchdog_cfg(tmp_path)
    cfg.setdefault("audio", {}).setdefault("transcribe", {})["vocabulary"] = ["Joe"]
    processor = watchdog.WatchdogProcessor(cfg)

    audio_path = tmp_path / "sample.wav"
    _write_fixture_wav(audio_path)
    monkeypatch.setattr("steps.common.conda_runner.run_conda_step", lambda *_a, **_kw: {})

    assert processor.ingest_audio(audio_path, "run-audio-wsl") is True
    assert Path(observed["audio_path"]) == _retained_audio(processor, audio_path)
    assert observed["vocabulary"] == ["Joe"]

    processed_dir = Path(cfg["paths"]["processed"])
    sidecars = list(processed_dir.glob("sample.*.audio_result.json"))
    assert len(sidecars) == 1
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["audio_backend_effective"] == "wsl"
    assert payload["embeddings_status"] == "success"


@pytest.fixture
def standalone_audio_dispatch(tmp_path, monkeypatch):
    """Keep the caller, JSON transport and CLI dispatch real; fake compute only."""
    from cli import step_runner
    from steps.common import conda_runner, tool_paths, step_logger, progress_tracker
    from steps.audio_transcribe import step as transcriber

    cfg = _watchdog_cfg(tmp_path)
    cfg["audio"] = {"transcribe": {"use_wsl2": True, "model": "small"}}
    observed = {"steps": [], "local_calls": [], "result": {
        "transcript": "A deterministic speech fixture.",
        "transcript_meta": {"status": "ok", "reason": "transcript_available"},
    }}
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: False)
    monkeypatch.setattr(watchdog, "require_wsl_audio", lambda: False)
    monkeypatch.setattr(progress_tracker, "add_error", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_tracker, "start_processing", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_tracker, "finish_processing", lambda *_a, **_k: None)
    monkeypatch.setattr(progress_tracker, "get_tracker", lambda: types.SimpleNamespace(update_step=lambda *_a, **_k: None))
    monkeypatch.setattr(conda_runner, "_resolve_models_root", lambda: str(tmp_path / "models"))
    monkeypatch.setattr(tool_paths, "resolve_conda", lambda: "fixture-conda")
    monkeypatch.setattr(step_runner, "load_cfg", lambda *_a, **_k: {})
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    gpu_module = types.ModuleType("common.gpu_manager")
    gpu_module.initialize_gpu_for_step = lambda *_a, **_k: types.SimpleNamespace(clear_cache=lambda: None)
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu_module)

    def transcribe(item, resolved):
        observed["local_calls"].append((dict(item), copy.deepcopy(resolved)))
        if isinstance(observed["result"], Exception):
            raise observed["result"]
        return copy.deepcopy(observed["result"])

    monkeypatch.setattr(transcriber, "audio_transcribe", transcribe)
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    from steps.audio.audio_wsl2_bridge import unified_transcription_options
    bridge = types.ModuleType("steps.audio.audio_wsl2_bridge")
    bridge.unified_transcription_options = unified_transcription_options
    bridge._build_wsl_capability_outcomes = _build_wsl_capability_outcomes
    bridge.audio_transcribe_wsl2 = lambda *_a, **_k: pytest.fail("local fallback entered WSL")
    bridge.audio_unified_wsl2 = lambda *_a, **_k: observed["wsl_result"]
    monkeypatch.setitem(sys.modules, "steps.audio.audio_wsl2_bridge", bridge)
    real_dispatch = step_runner.run_step

    def dispatch(name, item, resolved):
        observed["steps"].append(name)
        if name in {"audio_transcribe", "audio_transcribe_local"}:
            return real_dispatch(name, item, resolved)
        return {}  # Unrelated perception/enrichment never runs or writes stores.

    monkeypatch.setattr(step_runner, "run_step", dispatch)

    def child_process(cmd, **kwargs):
        if cmd[0] == "git":
            return subprocess.CompletedProcess(cmd, 0, "fixture-head", "")
        assert cmd[:3] == ["fixture-conda", "run", "-n"]
        assert cmd[4:6] == ["python", "-m"]
        assert cmd[6] == "cli.step_runner"
        with monkeypatch.context() as child:
            child.setattr(sys, "argv", ["cli.step_runner", *cmd[7:]])
            try:
                step_runner.main()
            except Exception as exc:
                raise subprocess.CalledProcessError(1, cmd, stderr=str(exc)) from exc
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(conda_runner.subprocess, "run", child_process)
    processor = watchdog.WatchdogProcessor(cfg)
    source = tmp_path / "speech.wav"
    _write_fixture_wav(source)
    return processor, source, observed, cfg, bridge


def test_standalone_audio_runs_real_local_dispatch_and_persists_result(standalone_audio_dispatch):
    processor, source, observed, cfg, _bridge = standalone_audio_dispatch
    before = copy.deepcopy(cfg)
    assert processor.ingest_audio(source, "standalone-run") is True
    assert len(observed["local_calls"]) == 1
    item, resolved = observed["local_calls"][0]
    assert Path(item["source_path"]) == _retained_audio(processor, source)
    assert observed["steps"][0] == "audio_transcribe_local"
    assert resolved["audio"]["transcribe"]["use_wsl2"] is False
    assert cfg == before
    sidecar, = processor.processed_dir.glob("*.audio_result.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["transcript"] == observed["result"]["transcript"]
    assert payload["transcript_meta"] == observed["result"]["transcript_meta"]
    assert payload["run_id"] == "standalone-run"
    assert payload["audio_backend_effective"] == "windows"


@pytest.mark.parametrize("result", [
    {"transcript": "", "transcript_meta": {"status": "empty", "reason": "no_speech_detected"}},
    {"transcript": None, "transcript_meta": {"status": "empty", "reason": "no_speech_detected"}},
])
def test_standalone_audio_preserves_explicit_empty_transcription(standalone_audio_dispatch, result):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    observed["result"] = result
    assert processor.ingest_audio(source, "empty-run") is True
    assert len(observed["local_calls"]) == 1
    sidecar, = processor.processed_dir.glob("*.audio_result.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["transcript_meta"] == result["transcript_meta"]
    assert payload["transcript"] == result["transcript"]


@pytest.mark.parametrize("result", [
    {}, {"transcript": ""}, None,
    {"transcript": "", "transcript_meta": {"status": "ok"}},
    *[{"transcript": None, "transcript_meta": {"status": status, "reason": status}}
      for status in ("no_file", "no_chunks", "model_unavailable", "error", "failed", "partial")],
    RuntimeError("backend execution failed"),
])
def test_standalone_audio_rejects_unproven_or_failed_transcription(standalone_audio_dispatch, result):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    observed["result"] = result
    with pytest.raises(Exception, match="[Tt]ranscri|backend execution failed"):
        processor.ingest_audio(source, "failed-run")
    assert not list(processor.processed_dir.glob("*.audio_result.json"))
    assert _retained_audio(processor, source).exists(), "failure input must survive"


@pytest.mark.parametrize("result", [
    {"transcript_meta": {"status": "empty"}},
    {"transcript": [], "transcript_meta": {"status": "empty"}},
    {"transcript": "text", "transcript_meta": []},
    {"transcript": "text", "transcript_meta": {"status": "partial", "reason": "transcript_available_with_chunk_errors"}},
    {"transcript": None, "transcript_meta": {"status": "empty", "reason": "execution_failed", "error": "decoder failed"}},
    {"transcript": None, "transcript_meta": {"status": "empty"}},
    {"transcript": "text", "transcript_meta": {"status": "ok", "error": "decoder failed"}},
])
def test_standalone_audio_rejects_malformed_or_partial_results(standalone_audio_dispatch, result):
    from steps.common.conda_runner import StepExecutionError

    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    observed["result"] = result
    with pytest.raises(StepExecutionError, match="Transcription"):
        processor.ingest_audio(source, "invalid-result-run")
    assert not list(processor.processed_dir.glob("*.audio_result.json"))


def test_standalone_audio_missing_source_never_dispatches(standalone_audio_dispatch):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    source.unlink()
    assert processor.ingest_audio(source, "missing-input") is False
    assert not observed["steps"]
    assert not list(processor.processed_dir.glob("*.audio_result.json"))


@pytest.mark.parametrize("text,status,reason", [
    ("Recorded speech", "ok", "transcript_emitted"),
    ("", "not_applicable", "no_text"),
])
def test_standalone_audio_preserves_wsl_transcription_receipts(
        standalone_audio_dispatch, monkeypatch, text, status, reason):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(watchdog.shutil, "which", lambda _name: "fixture-wsl")
    outcome = {"status": status, "reason": reason, "raw_status": "success"}
    observed["wsl_result"] = {
        "status": "success", "transcript": text, "transcript_meta": {"status": "success"},
        "wsl_capability_outcomes": {"transcription": outcome},
    }
    assert processor.ingest_audio(source, "wsl-result") is True
    assert "audio_embed_clap" in observed["steps"] and "text_embed" in observed["steps"]
    assert observed["steps"].index("audio_speaker_merge") < observed["steps"].index("text_embed")
    assert observed["steps"].index("emotion_classify") < observed["steps"].index("text_embed")
    assert "audio_transcribe_local" not in observed["steps"]
    sidecar, = processor.processed_dir.glob("*.audio_result.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["transcript"] == text
    assert payload["wsl_capability_outcomes"]["transcription"] == outcome


def test_standalone_audio_wsl_empty_without_receipt_uses_local_fallback(standalone_audio_dispatch, monkeypatch):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(watchdog.shutil, "which", lambda _name: "fixture-wsl")
    observed["wsl_result"] = {"status": "success", "transcript": "", "transcript_meta": {"status": "success"}}
    assert processor.ingest_audio(source, "wsl-unproven") is True
    assert len(observed["local_calls"]) == 1


@pytest.mark.parametrize('speech_seconds', [0, None, -1, float('nan'), 1])
def test_standalone_audio_requires_completed_zero_speech_evidence(standalone_audio_dispatch, monkeypatch, speech_seconds):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    monkeypatch.setattr(watchdog, 'require_wsl_audio', lambda: True)
    monkeypatch.setattr(watchdog.shutil, 'which', lambda _name: 'fixture-wsl')
    observed['wsl_result'] = {
        'status': 'success', 'transcript': '', 'transcript_outcome': 'no_speech',
        'transcript_meta': {'status': 'success', 'speech_detection': {
            'status': 'completed', 'method': 'silero_vad', 'input_duration_seconds': 5,
            'speech_duration_seconds': speech_seconds}},
        'wsl_capability_outcomes': {'transcription': {'status': 'not_applicable', 'reason': 'no_speech_detected'}},
    }
    if speech_seconds == 0:
        assert processor.ingest_audio(source, 'detected-no-speech') is True
        assert not observed['local_calls']
    else:
        with pytest.raises(Exception, match='Transcription'):
            processor.ingest_audio(source, 'unproven-no-speech')
        assert not observed['steps']


def test_standalone_audio_accepts_evidenced_whisper_no_speech_veto(standalone_audio_dispatch, monkeypatch):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    monkeypatch.setattr(watchdog, 'require_wsl_audio', lambda: True)
    monkeypatch.setattr(watchdog.shutil, 'which', lambda _name: 'fixture-wsl')
    observed['wsl_result'] = {
        'status':'success', 'transcript':'', 'transcript_outcome':'no_speech',
        'transcript_meta':{'status':'success', 'transcription_quality': {
            'status':'completed', 'rule':'whisper_no_speech_threshold', 'threshold':0.6,
            'accepted_segment_count':0,'decoded_segment_count':1,
            'rejected_segments':[{'text':'candidate', 'no_speech_probability':0.91}]}},
        'wsl_capability_outcomes':{'transcription':{'status':'not_applicable','reason':'no_speech_detected'}},
    }
    assert processor.ingest_audio(source,'whisper-no-speech') is True
    assert not observed['local_calls']


@pytest.mark.parametrize("outcomes", [None, {}, {"transcription": "error"},
    {"transcription": {"status": "ok", "error": "decoder failed"}}])
def test_standalone_audio_wsl_malformed_receipt_is_not_legacy_success(
        standalone_audio_dispatch, monkeypatch, outcomes):
    from steps.common.conda_runner import StepExecutionError

    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    monkeypatch.setattr(watchdog, "require_wsl_audio", lambda: True)
    monkeypatch.setattr(watchdog.shutil, "which", lambda _name: "fixture-wsl")
    observed["wsl_result"] = {
        "status": "success", "transcript": "Some text", "wsl_capability_outcomes": outcomes,
    }
    with pytest.raises(StepExecutionError, match="Transcription"):
        processor.ingest_audio(source, "bad-wsl-receipt")
    assert not observed["steps"]
    assert not list(processor.processed_dir.glob("*.audio_result.json"))


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("failure", ["structured", "exception", "component"])
def test_standalone_audio_wsl_failure_obeys_required_policy(standalone_audio_dispatch, monkeypatch, required, failure):
    processor, source, observed, _cfg, bridge = standalone_audio_dispatch
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(watchdog, "require_wsl_audio", lambda: required)
    monkeypatch.setattr(watchdog.shutil, "which", lambda _name: "fixture-wsl")

    def failed_wsl(*_a, **_k):
        if failure == "exception":
            raise RuntimeError("fixture WSL failed")
        if failure == "structured":
            return {"status": "error", "error": "fixture WSL failed"}
        return {"status": "success", "transcript": "", "transcript_meta": {"status": "error"},
                "wsl_capability_outcomes": {"transcription": {"status": "error", "reason": "transcription_failed"}}}

    bridge.audio_unified_wsl2 = failed_wsl
    if required:
        with pytest.raises(Exception):
            processor.ingest_audio(source, "required-wsl")
        assert not observed["local_calls"]
        assert not list(processor.processed_dir.glob("*.audio_result.json"))
        assert _retained_audio(processor, source).exists()
    else:
        assert processor.ingest_audio(source, "optional-wsl") is True
        assert len(observed["local_calls"]) == 1


def test_standalone_failed_transcription_reaches_failed_registry(standalone_audio_dispatch):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    observed["result"] = {"transcript": None, "transcript_meta": {"status": "model_unavailable"}}
    assert processor.process_file(source, "fixture-content-hash") is False
    state = json.loads(processor.state_file.read_text(encoding="utf-8"))
    assert state["fixture-content-hash"]["status"] == "failed"
    assert "model_unavailable" in state["fixture-content-hash"]["error"]
    assert not list(processor.processed_dir.glob("*.wav"))


def test_standalone_completed_transcription_reaches_caller_sidecar(standalone_audio_dispatch):
    processor, source, observed, _cfg, _bridge = standalone_audio_dispatch
    assert processor.process_file(source, "fixture-content-hash") is True
    state = json.loads(processor.state_file.read_text(encoding="utf-8"))
    record = state["fixture-content-hash"]
    assert record["status"] == "success"
    sidecar, = processor.processed_dir.glob("*.audio_result.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["run_id"] == record["run_id"]
    assert payload["transcript"] == observed["result"]["transcript"]
    assert list(processor.processed_dir.glob("PROCESSED_*.wav"))
