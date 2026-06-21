from __future__ import annotations

import os
import sys
import socket
import urllib.request
import http.client
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the NetworkBlockError from the original test file
from tests.unit.test_offline_mode_challenger import NetworkBlockError
from tests.unit.test_offline_mode_challenger import block_remote_network

def test_urllib_request_blocked():
    """Verify urllib.request remote calls are blocked and raise NetworkBlockError."""
    with pytest.raises((NetworkBlockError, Exception)) as excinfo:
        urllib.request.urlopen("http://8.8.8.8", timeout=1)
    err = excinfo.value
    # Find NetworkBlockError in context/cause chain or directly
    found = False
    current = err
    while current:
        if isinstance(current, NetworkBlockError):
            found = True
            break
        if "NetworkBlockError" in str(current) or "Blocked connection" in str(current):
            found = True
            break
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    assert found, f"NetworkBlockError not found in urllib chain: {err}"

def test_http_client_blocked():
    """Verify http.client remote calls are blocked and raise NetworkBlockError."""
    conn = http.client.HTTPConnection("8.8.8.8", timeout=1)
    with pytest.raises((NetworkBlockError, Exception)) as excinfo:
        conn.connect()
    err = excinfo.value
    found = False
    current = err
    while current:
        if isinstance(current, NetworkBlockError):
            found = True
            break
        if "NetworkBlockError" in str(current) or "Blocked connection" in str(current):
            found = True
            break
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    assert found, f"NetworkBlockError not found in http.client chain: {err}"

def test_requests_blocked():
    """Verify requests remote calls (if available) are blocked and raise NetworkBlockError."""
    try:
        import requests
    except ImportError:
        pytest.skip("requests library is not installed in this environment")
    
    with pytest.raises((NetworkBlockError, Exception)) as excinfo:
        requests.get("http://8.8.8.8", timeout=1)
    err = excinfo.value
    found = False
    current = err
    while current:
        if isinstance(current, NetworkBlockError):
            found = True
            break
        if "NetworkBlockError" in str(current) or "Blocked connection" in str(current):
            found = True
            break
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    assert found, f"NetworkBlockError not found in requests chain: {err}"

def test_raw_socket_connect_blocked():
    """Verify raw socket connect to remote is blocked."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(NetworkBlockError):
        s.connect(("8.8.8.8", 80))

def test_raw_socket_create_connection_blocked():
    """Verify socket.create_connection to remote is blocked."""
    with pytest.raises(NetworkBlockError):
        socket.create_connection(("8.8.8.8", 80), timeout=1)

def test_loopback_connect_allowed():
    """Verify that loopback connection attempts are not blocked with NetworkBlockError."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(Exception) as excinfo:
        s.connect(("127.0.0.1", 9999))
    assert not isinstance(excinfo.value, NetworkBlockError)

def test_loopback_create_connection_allowed():
    """Verify socket.create_connection to loopback does not raise NetworkBlockError."""
    with pytest.raises(Exception) as excinfo:
        socket.create_connection(("127.0.0.1", 9999), timeout=1)
    assert not isinstance(excinfo.value, NetworkBlockError)

def test_wsl_bridge_sanitization_robustness(monkeypatch):
    """Test carriage-return sanitization robustness in WindowsWSL2AudioRunner."""
    # Mock load_configs to avoid loading actual local file configurations
    try:
        import steps.common.config_loader
        monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda: {})
    except Exception:
        pass
        
    from scripts.wsl2_audio_bridge import WindowsWSL2AudioRunner
    
    # Mock out real workspace verification/filesystem checks so init can succeed
    monkeypatch.setattr(WindowsWSL2AudioRunner, "_resolve_wsl_user", lambda self: "mock_user")
    monkeypatch.setattr(WindowsWSL2AudioRunner, "_resolve_wsl_workspace", lambda self: "/home/mock_user/goodq_audio")
    
    # Test case 1: Trailing carriage returns and extra spaces
    monkeypatch.setenv("GOODQ_WSL_USER", "john_doe\r")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", " /home/john_doe/workspace\r  ")
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04\r")
    
    runner = WindowsWSL2AudioRunner()
    assert runner.wsl_user == "john_doe"
    assert runner.workspace == "/home/john_doe/workspace"
    assert runner.wsl_distro == "Ubuntu-22.04"
    assert runner.audio_workspace == "/home/john_doe/workspace"
    
    # Test case 2: Empty/Missing environment variables
    monkeypatch.delenv("GOODQ_WSL_USER", raising=False)
    monkeypatch.delenv("GOODQ_WSL_WORKSPACE", raising=False)
    monkeypatch.delenv("GOODQ_WSL_DISTRO", raising=False)
    # Also delete potential standard system env vars that might interfere with user resolution
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.delenv("LOGNAME", raising=False)
    
    runner2 = WindowsWSL2AudioRunner()
    assert runner2.wsl_user == "mock_user"
    assert runner2.workspace == "/home/mock_user/goodq_audio"
    assert runner2.wsl_distro == "Ubuntu"
    assert runner2.audio_workspace == "/home/mock_user/goodq_audio"

def test_socket_connect_ex_blocked():
    """Verify that socket.connect_ex is blocked by the network-blocking fixture."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(NetworkBlockError):
        s.connect_ex(("8.8.8.8", 80))

def test_wsl_bridge_path_handling_and_command_construction(monkeypatch):
    """Verify path conversion and shlex-quoted command construction in process_audio."""
    # Mock load_configs to avoid loading actual local file configurations
    try:
        import steps.common.config_loader
        monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda: {})
    except Exception:
        pass

    # Mock probe_wsl_audio_runtime to bypass preflight checks
    import scripts.wsl2_audio_bridge
    monkeypatch.setattr(scripts.wsl2_audio_bridge, "probe_wsl_audio_runtime", lambda distro, workspace: {
        "ready": True,
        "runtime_ready": True,
        "abi_ready": True,
        "diarization_ready": True,
        "wav2vec_enrichment_ready": True,
    })

    from scripts.wsl2_audio_bridge import WindowsWSL2AudioRunner
    import subprocess
    
    monkeypatch.setattr(WindowsWSL2AudioRunner, "_resolve_wsl_user", lambda self: "mock_user")
    monkeypatch.setattr(WindowsWSL2AudioRunner, "_resolve_wsl_workspace", lambda self: "/home/mock_user/goodq_audio")
    
    # Set environment with carriage returns to test that initialization sanitizes them
    monkeypatch.setenv("GOODQ_WSL_USER", "john_doe\r")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/john_doe/workspace\r")
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04\r")
    
    runner = WindowsWSL2AudioRunner()
    # Force workspace to be marked ready and bypass real checks
    runner._workspace_ready = True
    runner._workspace_checked = True
    
    # Mock Path.exists to return True for input file
    monkeypatch.setattr(Path, "exists", lambda self: True)
    
    captured_runs = []
    def mock_run(cmd, *args, **kwargs):
        captured_runs.append(cmd)
        # Return a mock completed process with code 0 and valid json output
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"status": "success", "duration": 10.0}'
        mock_proc.stderr = ''
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Execute process_audio with paths containing mixed slashes, spaces, and backslashes
    input_file = r"C:\My Workspace\Audio Files\sample.wav"
    output_file = r"C:\My Workspace\Audio Files\output.json"
    
    runner.process_audio(input_file, output_file)
    
    # Let's inspect the command that was passed to subprocess.run
    # We expect multiple runs:
    # 1. file_check: ["wsl", "-d", "Ubuntu-22.04", "--", "test", "-f", "/mnt/c/My Workspace/Audio Files/sample.wav"]
    # 2. bridge execution: ["wsl", "-d", "Ubuntu-22.04", "--", "bash", "-lc", bridge_script]
    assert len(captured_runs) >= 2
    
    file_check_cmd = captured_runs[0]
    assert file_check_cmd[0] == "wsl"
    assert file_check_cmd[2] == "Ubuntu-22.04"
    assert file_check_cmd[6] == "/mnt/c/My Workspace/Audio Files/sample.wav"
    
    bridge_cmd = captured_runs[1]
    assert bridge_cmd[0] == "wsl"
    assert bridge_cmd[2] == "Ubuntu-22.04"
    assert bridge_cmd[4] == "bash"
    assert bridge_cmd[5] == "-lc"
    
    bridge_script = bridge_cmd[6]
    assert "source /home/john_doe/workspace/setup_cuda_env.sh" in bridge_script
    assert "'/mnt/c/My Workspace/Audio Files/sample.wav'" in bridge_script
    assert "/home/john_doe/workspace/output" in bridge_script
