from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
import pytest
import cli.watchdog as watchdog

from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg


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

    bridge_module = types.ModuleType("steps.audio.audio_wsl2_bridge")
    observed: dict[str, str] = {}

    def fake_audio_unified_wsl2(audio_path: str, *, scene_id=None, duration=None, **kwargs):
        observed["audio_path"] = audio_path
        observed["scene_id"] = scene_id
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
    processor = watchdog.WatchdogProcessor(cfg)

    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"not a real wav, but the bridge is mocked")

    assert processor.ingest_audio(audio_path, "run-audio-wsl") is True
    assert observed["audio_path"].endswith("sample.wav")

    processed_dir = Path(cfg["paths"]["processed"])
    sidecars = list(processed_dir.glob("sample.*.audio_result.json"))
    assert len(sidecars) == 1
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["audio_backend_effective"] == "wsl"
    assert payload["embeddings_status"] == "success"
