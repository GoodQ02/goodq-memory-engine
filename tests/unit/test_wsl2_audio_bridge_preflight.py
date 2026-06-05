from __future__ import annotations

import importlib
import sys
from pathlib import Path
import subprocess


def _load_bridge_module():
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return importlib.import_module("scripts.wsl2_audio_bridge")


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_workspace_preflight_retries_once_after_timeout(monkeypatch):
    bridge_module = _load_bridge_module()

    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq_audio")
    monkeypatch.delenv("GOODQ_REQUIRE_WSL_AUDIO", raising=False)

    calls = {"count": 0}

    def _fake_run(cmd, capture_output=True, timeout=None):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
        return _Result(returncode=0)

    monkeypatch.setattr(bridge_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(bridge_module.time, "sleep", lambda _seconds: None)

    bridge = bridge_module.WSL2AudioBridge()

    assert bridge._ensure_workspace_ready() is True
    assert calls["count"] == 2


def test_process_audio_raises_on_inaccessible_mount(monkeypatch, tmp_path):
    bridge_module = _load_bridge_module()

    dummy_file = tmp_path / "test.wav"
    dummy_file.touch()

    bridge = bridge_module.WindowsWSL2AudioRunner()
    bridge._workspace_checked = True
    bridge._workspace_ready = True

    run_calls = []
    def _fake_run(cmd, capture_output=True, timeout=None):
        run_calls.append(cmd)
        return _Result(returncode=1)

    monkeypatch.setattr(bridge_module.subprocess, "run", _fake_run)

    import pytest
    with pytest.raises(FileNotFoundError) as exc_info:
        bridge.process_audio(str(dummy_file))

    assert "is not mounted or accessible" in str(exc_info.value)
    assert len(run_calls) == 2
    assert "-f" in run_calls[0]
    assert "-d" in run_calls[1]


def test_process_audio_raises_on_missing_file_in_mounted_drive(monkeypatch, tmp_path):
    bridge_module = _load_bridge_module()

    dummy_file = tmp_path / "test.wav"
    dummy_file.touch()

    bridge = bridge_module.WindowsWSL2AudioRunner()
    bridge._workspace_checked = True
    bridge._workspace_ready = True

    run_calls = []
    def _fake_run(cmd, capture_output=True, timeout=None):
        run_calls.append(cmd)
        if "-f" in cmd:
            return _Result(returncode=1)
        if "-d" in cmd:
            return _Result(returncode=0)
        return _Result(returncode=0)

    monkeypatch.setattr(bridge_module.subprocess, "run", _fake_run)

    import pytest
    with pytest.raises(FileNotFoundError) as exc_info:
        bridge.process_audio(str(dummy_file))

    assert "Ensure the file has been successfully written" in str(exc_info.value)

