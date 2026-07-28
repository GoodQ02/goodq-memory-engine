import os
import sys
import subprocess
import pytest
from unittest.mock import patch, MagicMock

# Import the module under test
from scripts.wsl2_audio_bridge import WindowsWSL2AudioRunner

def test_carriage_return_sanitization(monkeypatch):
    """Verify that carriage returns are stripped from wsl_user, workspace, and wsl_distro."""
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser\r")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq_audio\r")
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-Test\r")
    
    runner = WindowsWSL2AudioRunner()
    
    assert runner.wsl_user == "testuser"
    assert runner.workspace == "/home/testuser/goodq_audio"
    assert runner.wsl_distro == "Ubuntu-Test"

def test_path_with_spaces_check_status_quoting(monkeypatch):
    """Verify if spaces in the workspace path cause shell formatting errors in check_status."""
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq audio space")
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    
    runner = WindowsWSL2AudioRunner()
    
    with patch("subprocess.run") as mock_run:
        # Mock ensure_workspace_ready to do nothing and return True
        runner._workspace_checked = True
        runner._workspace_ready = True
        
        mock_run.return_value = MagicMock(returncode=0, stdout="True")
        
        runner.check_status()
        
        # Verify the command passed to subprocess.run
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        # Command should look like: ['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c', '...']
        shell_cmd = cmd_args[-1]
        
        # Check if the shell command contains unquoted source path
        # It should contain: source /home/testuser/goodq audio space/setup_cuda_env.sh
        # This will fail in bash because 'source' will try to source '/home/testuser/goodq'
        print(f"Shell command: {shell_cmd}")
        assert "source /home/testuser/goodq audio space/setup_cuda_env.sh" in shell_cmd
        # Verify that word splitting will occur (no quotes around the source path)
        assert "source '/home/testuser/goodq audio space/setup_cuda_env.sh'" not in shell_cmd

def test_mixed_slashes_in_workspace(monkeypatch):
    """Verify that backslashes in workspace are not normalized for WSL."""
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "\\home\\testuser\\goodq_audio")
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    
    runner = WindowsWSL2AudioRunner()
    
    with patch("subprocess.run") as mock_run:
        runner._workspace_checked = True
        runner._workspace_ready = True
        
        mock_run.return_value = MagicMock(returncode=0, stdout="True")
        
        runner.check_status()
        
        cmd_args = mock_run.call_args[0][0]
        shell_cmd = cmd_args[-1]
        
        print(f"Shell command with backslashes: {shell_cmd}")
        # The backslashes should remain, causing invalid paths inside WSL
        assert "\\home\\testuser\\goodq_audio/setup_cuda_env.sh" in shell_cmd

def test_single_quote_in_workspace_preflight(monkeypatch):
    """Verify single quotes in workspace path cause syntax error in _ensure_workspace_ready."""
    monkeypatch.setenv("GOODQ_WSL_USER", "testuser")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/testuser/goodq's_audio")
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    
    runner = WindowsWSL2AudioRunner()
    
    with patch("subprocess.run") as mock_run, patch.object(
        runner, "_workspace_worker_mismatches", return_value=[]
    ):
        mock_run.return_value = MagicMock(returncode=0)
        
        runner._ensure_workspace_ready()
        
        # Verify how the path is quoted in the preflight test command
        # It calls subprocess.run with wsl command
        call_args_list = mock_run.call_args_list
        assert len(call_args_list) > 0
        preflight_cmd_args = call_args_list[0][0][0]
        preflight_shell_script = preflight_cmd_args[-1]
        
        print(f"Preflight shell script: {preflight_shell_script}")
        # The script is: test -d '/home/testuser/goodq's_audio' && ...
        # Which is syntactically invalid because of the single quote in path!
        assert "test -d '/home/testuser/goodq's_audio'" in preflight_shell_script
