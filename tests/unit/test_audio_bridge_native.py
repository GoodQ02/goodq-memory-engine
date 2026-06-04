import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
from scripts.wsl2_audio_bridge import NativeAudioRunner, WSL2AudioBridge, AudioRunner, WindowsWSL2AudioRunner

def test_native_audio_runner_init():
    runner = NativeAudioRunner()
    assert runner.audio_workspace.endswith("wsl2_audio")
    assert runner.output_dir.endswith("wsl2_audio/output")

def test_native_audio_runner_success():
    runner = NativeAudioRunner()
    
    mock_payload = {
        "status": "success",
        "audio_file": "L:/_DATA/test.wav",
        "request_uuid": "mock-uuid-1234",
        "transcription": "Hello World",
        "word_timestamps": []
    }
    
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps(mock_payload)
    mock_proc.stderr = ""
    
    # Mock file existence for the audio file
    with patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run", return_value=mock_proc) as mock_run, \
         patch.dict(os.environ, {}, clear=True):
        
        result = runner.process_audio("L:/_DATA/test.wav", timeout=120)
        
        assert result["status"] == "success"
        assert result["transcription"] == "Hello World"
        assert result["requested_request_uuid"] is not None
        assert result["returned_request_uuid"] == "mock-uuid-1234"
        
        # Verify subprocess.run call
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert cmd[1].endswith("process_audio.py")
        assert cmd[2] == str(Path("L:/_DATA/test.wav").resolve())
        
        # Verify that environment had device set appropriately
        env = kwargs.get("env", {})
        if sys.platform == "darwin":
            assert env.get("GOODQ_DEVICE") == "mps"
            assert env.get("GOODQ_MPS_DIARIZATION") == "0"
        elif sys.platform.startswith("linux"):
            assert "GOODQ_DEVICE" in env

def test_native_audio_runner_fallback_to_file():
    runner = NativeAudioRunner()
    
    mock_payload = {
        "status": "success",
        "audio_file": "L:/_DATA/test.wav",
        "request_uuid": "mock-uuid-1234",
        "transcription": "Hello from result.json",
        "word_timestamps": []
    }
    
    mock_proc = MagicMock()
    # Process prints nothing to stdout but writes result.json
    mock_proc.returncode = 0
    mock_proc.stdout = ""
    mock_proc.stderr = ""
    
    def mock_exists_fn(self):
        # We need Path("L:/_DATA/test.wav").exists() and result_json_file.exists() to be True
        return True

    def mock_read_text_fn(self):
        return json.dumps(mock_payload)
        
    with patch("pathlib.Path.exists", mock_exists_fn), \
         patch("pathlib.Path.read_text", mock_read_text_fn), \
         patch("subprocess.run", return_value=mock_proc), \
         patch.dict(os.environ, {}, clear=True):
        
        result = runner.process_audio("L:/_DATA/test.wav", timeout=120)
        assert result["status"] == "success"
        assert result["transcription"] == "Hello from result.json"

def test_native_audio_runner_timeout():
    runner = NativeAudioRunner()
    
    import subprocess
    with patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="process_audio.py", timeout=10)):
        
        result = runner.process_audio("L:/_DATA/test.wav", timeout=10)
        assert result["status"] == "error"
        assert "timeout" in result["bridge_error_reason"]

def test_wsl2_audio_bridge_routing():
    # Test on non-Windows (should route to NativeAudioRunner)
    with patch("sys.platform", "darwin"), \
         patch.dict(os.environ, {}, clear=True):
        bridge = WSL2AudioBridge()
        assert isinstance(bridge.runner, NativeAudioRunner)

    # Test on Windows (should route to WindowsWSL2AudioRunner by default)
    with patch("sys.platform", "win32"), \
         patch.dict(os.environ, {}, clear=True):
        bridge = WSL2AudioBridge()
        assert isinstance(bridge.runner, WindowsWSL2AudioRunner)

    # Test on Windows with override (should route to NativeAudioRunner)
    with patch("sys.platform", "win32"), \
         patch.dict(os.environ, {"GOODQ_NATIVE_AUDIO": "1"}, clear=True):
        bridge = WSL2AudioBridge()
        assert isinstance(bridge.runner, NativeAudioRunner)
