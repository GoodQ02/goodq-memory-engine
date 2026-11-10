from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

from scripts import wsl2_audio_bridge as bridge_module


def _runner(tmp_path: Path):
    runner = bridge_module.WindowsWSL2AudioRunner.__new__(bridge_module.WindowsWSL2AudioRunner)
    runner._config = {"paths": {"models_cache": str(tmp_path / "shared models")}}
    runner.require_wsl_audio = False
    runner.audio_workspace = "/home/goodq/audio"
    runner.wsl_distro = "GoodQ-Test"
    runner._workspace_checked = True
    runner._workspace_ready = True
    return runner


def _fake_worker(monkeypatch, *, malformed_stdout: bool = False):
    calls = []
    windows_reads = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[4:6] == ["test", "-f"]:
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[4] == "stat":
            return subprocess.CompletedProcess(cmd, 0, str(int(time.time()) + 2), "")
        if cmd[4] == "cat":
            return subprocess.CompletedProcess(cmd, 0, "{}", "")
        if cmd[4:6] == ["bash", "-lc"]:
            script = cmd[-1]
            args = shlex.split(script.split("exec python3 ", 1)[1])
            request_id = shlex.split(re.search(r"GOODQ_BRIDGE_REQUEST_UUID=([^;]+);", script).group(1))[0]
            payload = {"status": "success", "request_uuid": request_id, "audio_file": args[1]}
            return subprocess.CompletedProcess(cmd, 0, "not JSON" if malformed_stdout else json.dumps(payload), "")
        raise AssertionError(f"Unexpected WSL command: {cmd}")

    monkeypatch.setattr(bridge_module.subprocess, "run", run)
    monkeypatch.setattr(
        bridge_module,
        "probe_wsl_audio_runtime",
        lambda *_: {"runtime_ready": True, "abi_ready": True, "diarization_ready": True},
    )
    monkeypatch.setattr(
        bridge_module.os.path, "exists", lambda path: windows_reads.append(str(path)) or False
    )
    return calls, windows_reads


def test_process_audio_binds_unique_witness_outputs_and_offline_environment(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    source = tmp_path / "scene.wav"
    source.touch()
    output_root = tmp_path / "witness output's" / "wsl_audio"
    monkeypatch.setenv("GOODQ_WSL_AUDIO_OUTPUT_ROOT", str(output_root))
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        monkeypatch.setenv(key, "1")
    calls, windows_reads = _fake_worker(monkeypatch)

    first = runner.process_audio(str(source))
    second = runner.process_audio(str(source))

    assert first["status"] == second["status"] == "success"
    expected_outputs = [
        f"{runner.wsl_path(output_root)}/{result['requested_request_uuid']}"
        for result in (first, second)
    ]
    scripts = [cmd[-1] for cmd in calls if cmd[4:6] == ["bash", "-lc"]]
    worker_outputs = [shlex.split(script.split("exec python3 ", 1)[1])[-1] for script in scripts]
    assert worker_outputs == expected_outputs
    assert worker_outputs[0] != worker_outputs[1]
    assert [cmd[-1] for cmd in calls if cmd[4] == "stat"] == [
        f"{output}/result.json" for output in expected_outputs
    ]
    for script in scripts:
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
            assert f"export {key}=1;" in script.split("source ", 1)[1]
        assert "export HF_HOME=" in script
        assert "export PYTHONDONTWRITEBYTECODE=1;" in script.split("source ", 1)[1]
    if os.name == "nt":
        assert windows_reads == [str(output_root / result["requested_request_uuid"] / "result.json") for result in (first, second)]


def test_process_audio_debug_reader_uses_witness_output(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    source = tmp_path / "scene.wav"
    source.touch()
    output_root = tmp_path / "witness" / "wsl_audio"
    monkeypatch.setenv("GOODQ_WSL_AUDIO_OUTPUT_ROOT", str(output_root))
    calls, windows_reads = _fake_worker(monkeypatch, malformed_stdout=True)

    result = runner.process_audio(str(source))

    assert result["bridge_error_reason"] == "stdout_json_parse_failed"
    expected = f"{runner.wsl_path(output_root)}/{result['requested_request_uuid']}/result.json"
    assert [cmd[-1] for cmd in calls if cmd[4] == "cat"] == [expected]
    if os.name == "nt":
        assert windows_reads == [str(output_root / result["requested_request_uuid"] / "result.json")]


def test_vocabulary_is_one_quoted_request_argument(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    source = tmp_path / "scene.wav"
    source.touch()
    calls, _ = _fake_worker(monkeypatch)
    vocabulary = ["O'Neil", "$(not_a_command)"]
    result = runner.process_audio(str(source), transcription_vocabulary=vocabulary)
    assert result["status"] == "success"
    script = next(cmd[-1] for cmd in calls if cmd[4:6] == ["bash", "-lc"])
    args = shlex.split(script.split("exec python3 ", 1)[1])
    assert len(args) == 4
    assert json.loads(args[3]) == vocabulary


def test_process_audio_without_witness_override_retains_existing_output(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    source = tmp_path / "scene.wav"
    source.touch()
    monkeypatch.delenv("GOODQ_WSL_AUDIO_OUTPUT_ROOT", raising=False)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    calls, _ = _fake_worker(monkeypatch)

    result = runner.process_audio(str(source))

    assert result["status"] == "success"
    script = next(cmd[-1] for cmd in calls if cmd[4:6] == ["bash", "-lc"])
    assert shlex.split(script.split("exec python3 ", 1)[1])[-1] == "/home/goodq/audio/output"
    assert "export PYTHONDONTWRITEBYTECODE=" not in script


@pytest.mark.parametrize("offline_value", ["1", "0"])
def test_process_audio_forwards_explicit_offline_flags_without_cache_root(monkeypatch, tmp_path, offline_value):
    runner = _runner(tmp_path)
    runner._config = {"paths": {}}
    source = tmp_path / "scene.wav"
    source.touch()
    for key in ("GOODQ_MODEL_CACHE_ROOT", "HF_HOME", "GOODQ_WSL_AUDIO_OUTPUT_ROOT"):
        monkeypatch.delenv(key, raising=False)
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        monkeypatch.setenv(key, offline_value)
    calls, _ = _fake_worker(monkeypatch)

    result = runner.process_audio(str(source))

    assert result["status"] == "success"
    script = next(cmd[-1] for cmd in calls if cmd[4:6] == ["bash", "-lc"])
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        assert f"export {key}={offline_value};" in script


@pytest.mark.parametrize("witness", [True, False])
def test_workspace_preflight_preserves_shared_cache_refs_for_witness(monkeypatch, tmp_path, witness):
    runner = _runner(tmp_path)
    runner._workspace_checked = False
    models = tmp_path / "shared models"
    ref = models / "hub" / "models--fixture" / "refs" / "main"
    ref.parent.mkdir(parents=True)
    original = b"cached-revision\r\n"
    ref.write_bytes(original)
    if witness:
        monkeypatch.setenv("GOODQ_WSL_AUDIO_OUTPUT_ROOT", str(tmp_path / "witness" / "wsl_audio"))
    else:
        monkeypatch.delenv("GOODQ_WSL_AUDIO_OUTPUT_ROOT", raising=False)
    resolver = types.ModuleType("bootstrap_models")
    resolver.resolve_models_root = lambda: models
    monkeypatch.setitem(sys.modules, "bootstrap_models", resolver)
    monkeypatch.setattr(bridge_module.subprocess, "run", lambda cmd, **_: subprocess.CompletedProcess(cmd, 0))
    monkeypatch.setattr(runner, "_workspace_worker_mismatches", lambda: [])

    assert runner._ensure_workspace_ready() is True

    assert ref.read_bytes() == (original if witness else b"cached-revision")
