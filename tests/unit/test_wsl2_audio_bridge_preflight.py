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
