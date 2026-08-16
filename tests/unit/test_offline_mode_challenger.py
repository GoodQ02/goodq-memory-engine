from __future__ import annotations

import os
import sys
import types
import pytest
import torch
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the modules under test
from wsl2_audio import process_audio
from wsl2_audio import model_cache

@pytest.fixture(autouse=True)
def _clear_gpu_requirements(monkeypatch):
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setattr(process_audio, "require_gpu", lambda: False)

def test_whisper_model_supports_local_files_only():
    """Verify that WhisperModel supports local_files_only argument."""
    from faster_whisper import WhisperModel
    import inspect
    sig = inspect.signature(WhisperModel.__init__)
    assert "local_files_only" in sig.parameters
    # Check default is False
    assert sig.parameters["local_files_only"].default is False

def test_process_audio_missing_whisper_cache_raises_descriptive_error(monkeypatch, tmp_path: Path):
    """Verify missing Whisper cache raises descriptive OSError to caller."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda x: False)
    
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    
    waveform = torch.zeros((1, 16000))
    monkeypatch.setattr(process_audio.torchaudio, "load", lambda _: (waveform, 16000))
    
    with pytest.raises(OSError) as excinfo:
        process_audio.process_audio(str(audio_file), None)
        
    error_msg = str(excinfo.value)
    assert "Offline mode: Faster-Whisper model" in error_msg
    assert "Status: Non-gated." in error_msg
    assert "Requirements: No Hugging Face token" in error_msg
    assert "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py" in error_msg

def test_process_audio_corrupted_whisper_cache_propagates_error(monkeypatch, tmp_path: Path):
    """Verify that corrupted Whisper cache propagates the loader exception to caller."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda x: True)
    
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("ctranslate2: Open failed: model.bin is empty or corrupted")
            
    monkeypatch.setattr(process_audio, "WhisperModel", MockWhisperModel)
    
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    
    waveform = torch.zeros((1, 16000))
    monkeypatch.setattr(process_audio.torchaudio, "load", lambda _: (waveform, 16000))
    
    with pytest.raises(RuntimeError) as excinfo:
        process_audio.process_audio(str(audio_file), None)
        
    assert "ctranslate2: Open failed" in str(excinfo.value)

def test_audio_service_corrupted_whisper_cache_propagates_error(monkeypatch):
    """Verify that audio service raises when Whisper load fails due to corruption."""
    monkeypatch.setitem(sys.modules, "soundfile", types.ModuleType("soundfile"))
    from wsl2_audio import audio_service
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda x: True)
    
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("ctranslate2: Open failed: model.bin is empty or corrupted")
            
    monkeypatch.setattr(audio_service, "WhisperModel", MockWhisperModel)
    
    service = object.__new__(audio_service.AudioService)
    service.config = {
        "gpu": {"device": "cpu", "compute_type": "int8"},
        "models": {
            "whisper": "medium",
            "diarization": "pyannote/speaker-diarization-3.1",
        },
    }
    service.whisper_model = None
    service.diarization_pipeline = None
    service.vad_model = None
    
    # Mock VAD load to prevent external network access
    monkeypatch.setattr(model_cache, "load_silero_vad", lambda *args, **kwargs: ("vad", [None, None, None, None, "collect"]))
    
    with pytest.raises(RuntimeError) as excinfo:
        service._load_models()
        
    assert "ctranslate2: Open failed" in str(excinfo.value)

def test_token_redaction_in_process_audio_exceptions(monkeypatch, tmp_path: Path):
    """Verify that sensitive HF tokens are redacted from exception messages when online load fails."""
    monkeypatch.setenv("GOODQ_OFFLINE", "0")
    monkeypatch.setattr(model_cache, "is_offline_mode", lambda: False)
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda x: True)
    
    # Mock WhisperModel to succeed quickly
    class MockWhisperModel:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, *args, **kwargs):
            return iter(()), types.SimpleNamespace(language="en", language_probability=1.0)
            
    monkeypatch.setattr(process_audio, "WhisperModel", MockWhisperModel)
    
    # Pass a sensitive token
    fake_token = "hf_secret_token_123456789_leak_test"
    monkeypatch.setenv("HF_TOKEN", fake_token)
    
    # Mock PyAnnote Pipeline to raise an exception containing the token
    class MockPipeline:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            # Check if token is passed (online mode attempt)
            token_used = kwargs.get("token") or kwargs.get("use_auth_token")
            if token_used == fake_token:
                raise ValueError(f"Authentication failed for token: {token_used}")
            # If local_only is True (first attempt), we raise normal error
            raise ValueError("Local files not found")
            
    monkeypatch.setattr(process_audio, "DiarizationPipeline", MockPipeline, raising=False)
    monkeypatch.setattr(process_audio, "DIARIZATION_AVAILABLE", True)
    
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    
    waveform = torch.zeros((1, 16000))
    monkeypatch.setattr(process_audio.torchaudio, "load", lambda _: (waveform, 16000))
    
    result = process_audio.process_audio(str(audio_file), None)
    
    # Verify the token did not leak into result but was redacted
    assert result["diarization_status"] == "error"
    assert fake_token not in result["diarization_error"]
    assert "<REDACTED>" in result["diarization_error"] or "hf_***" in result["diarization_error"]


# --- Hardened No-Network Verification (R5) Fixtures and Tests ---

class NetworkBlockError(RuntimeError):
    """Exception raised when network connection is blocked in offline mode."""
    pass

@pytest.fixture(autouse=True)
def block_remote_network(monkeypatch):
    """Fixture that blocks remote network connection attempts, allowing only loopback."""
    import socket
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def mock_connect(self, address):
        host = address[0]
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        raise NetworkBlockError(f"Blocked connection to remote host '{host}' when GOODQ_OFFLINE=1.")

    def mock_connect_ex(self, address):
        host = address[0]
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect_ex(self, address)
        raise NetworkBlockError(f"Blocked connect_ex to remote host '{host}' when GOODQ_OFFLINE=1.")

    def mock_create_connection(address, timeout=None, source_address=None):
        host = address[0]
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_create_connection(address, timeout, source_address)
        raise NetworkBlockError(f"Blocked create_connection to remote host '{host}' when GOODQ_OFFLINE=1.")

    monkeypatch.setattr(socket.socket, "connect", mock_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", mock_connect_ex)
    monkeypatch.setattr(socket, "create_connection", mock_create_connection)

def test_socket_network_block_works():
    """Verify that socket connect attempts to external hosts raise NetworkBlockError."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(NetworkBlockError):
        s.connect(("8.8.8.8", 80))
        
    with pytest.raises(NetworkBlockError):
        socket.create_connection(("google.com", 80))

def test_silero_vad_offline_load_from_cache(monkeypatch):
    """Verify Silero VAD loads from local cache with source='local' and no network calls."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    fake_path = "/fake/silero_vad"
    monkeypatch.setattr(model_cache, "resolve_silero_local_path", lambda: fake_path)
    
    mock_model = MagicMock()
    mock_utils = MagicMock()
    
    load_calls = []
    def mock_torch_hub_load(repo_or_dir, model, source, **kwargs):
        load_calls.append((repo_or_dir, model, source, kwargs))
        return mock_model, mock_utils
        
    monkeypatch.setattr(torch.hub, "load", mock_torch_hub_load)
    
    model, utils = model_cache.load_silero_vad()
    
    assert model is mock_model
    assert utils is mock_utils
    assert len(load_calls) == 1
    assert load_calls[0][0] == fake_path
    assert load_calls[0][2] == "local"

def test_silero_vad_offline_missing_cache_raises_error(monkeypatch):
    """Verify Silero VAD raises OSError if offline but cache is missing."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "resolve_silero_local_path", lambda: None)
    
    with pytest.raises(OSError) as excinfo:
        model_cache.load_silero_vad()
        
    assert "Offline mode: Silero VAD model" in str(excinfo.value)
    assert "python3 scripts/install_pipeline_wsl.py --download-silero" in str(excinfo.value)

def test_faster_whisper_offline_load_from_cache(monkeypatch, tmp_path):
    """Verify faster-whisper loads from cache passing local_files_only=True."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda _: True)
    
    constructor_calls = []
    class MockWhisperModel:
        def __init__(self, model_size_or_path, **kwargs):
            constructor_calls.append((model_size_or_path, kwargs))
        def transcribe(self, *args, **kwargs):
            return iter(()), MagicMock()
            
    monkeypatch.setattr(process_audio, "WhisperModel", MockWhisperModel)
    monkeypatch.setattr(process_audio.torchaudio, "load", lambda _: (torch.zeros(1, 16000), 16000))
    monkeypatch.setattr(process_audio, "DIARIZATION_AVAILABLE", False)
    monkeypatch.setattr(process_audio, "TRANSFORMERS_AVAILABLE", False)
    
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"dummy")
    
    result = process_audio.process_audio(str(audio_file), None)
    
    assert len(constructor_calls) == 1
    assert constructor_calls[0][1].get("local_files_only") is True

def test_pyannote_offline_load_success(monkeypatch, tmp_path):
    """Verify PyAnnote is loaded from local cache using local_files_only=True without network calls."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "check_pyannote_cache", lambda _: True)
    
    class MockWhisperModel:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, *args, **kwargs): return iter([]), MagicMock()
    monkeypatch.setattr(process_audio, "WhisperModel", MockWhisperModel)
    
    pyannote_init_args = []
    class MockPipeline:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            pyannote_init_args.append((model_name, kwargs))
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock()
            return mock_instance
            
    monkeypatch.setattr(process_audio, "DiarizationPipeline", MockPipeline, raising=False)
    monkeypatch.setattr(process_audio, "DIARIZATION_AVAILABLE", True)
    monkeypatch.setattr(process_audio, "TRANSFORMERS_AVAILABLE", False)
    monkeypatch.setattr(process_audio.torchaudio, "load", lambda _: (torch.zeros(1, 16000), 16000))
    
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"dummy")
    
    result = process_audio.process_audio(str(audio_file), None)
    
    # The mocked pipeline emits no tracks.  A successful offline load must
    # therefore preserve the explicit zero-speaker completion outcome.
    assert result["diarization_status"] == "completed_no_speakers"
    assert len(pyannote_init_args) == 1
    assert pyannote_init_args[0][1].get("local_files_only") is True

def test_pyannote_offline_missing_cache_raises_error(monkeypatch):
    """Verify PyAnnote pipeline raises OSError when offline and cache is missing."""
    mock_pipeline_cls = MagicMock()
    mock_pipeline_cls.from_pretrained.side_effect = RuntimeError("Local files not found")
    
    with pytest.raises(OSError) as excinfo:
        process_audio._load_pyannote_pipeline(
            pipeline_cls=mock_pipeline_cls,
            model_name="pyannote/speaker-diarization-3.1",
            token="fake_token",
            cache_dir="/fake/cache",
            is_offline=True
        )
        
    assert "Offline mode: PyAnnote diarization pipeline failed to load locally" in str(excinfo.value)
    mock_pipeline_cls.from_pretrained.assert_called_once()

def test_transformers_offline_load_success(monkeypatch, tmp_path):
    """Verify Wav2Vec2 models are loaded from cache using local_files_only=True without network calls."""
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    monkeypatch.setattr(model_cache, "check_whisper_cache", lambda _: True)
    monkeypatch.setattr(model_cache, "check_hf_model_cache", lambda _: True)
    
    class MockWhisperModel:
        def __init__(self, *args, **kwargs): pass
        def transcribe(self, *args, **kwargs): return iter([]), MagicMock()
    monkeypatch.setattr(process_audio, "WhisperModel", MockWhisperModel)
    
    monkeypatch.setattr(process_audio, "DIARIZATION_AVAILABLE", False)
    monkeypatch.setattr(process_audio, "TRANSFORMERS_AVAILABLE", True)
    
    classification_args = []
    class MockClassification:
        @classmethod
        def from_pretrained(cls, repo, **kwargs):
            classification_args.append((repo, kwargs))
            mock_instance = MagicMock()
            mock_logits = MagicMock()
            mock_logits.logits = torch.zeros(1, 8)
            mock_instance.return_value = mock_logits
            mock_instance.to.return_value = mock_instance
            return mock_instance
            
    model_args = []
    class MockModel:
        @classmethod
        def from_pretrained(cls, repo, **kwargs):
            model_args.append((repo, kwargs))
            mock_instance = MagicMock()
            mock_hs = MagicMock()
            mock_hs.last_hidden_state = torch.zeros(1, 10, 768)
            mock_instance.return_value = mock_hs
            mock_instance.to.return_value = mock_instance
            return mock_instance
            
    extractor_args = []
    class MockExtractor:
        @classmethod
        def from_pretrained(cls, repo, **kwargs):
            extractor_args.append((repo, kwargs))
            mock_instance = MagicMock()
            mock_instance.return_value = {"input_values": torch.zeros(1, 1000)}
            return mock_instance
            
    monkeypatch.setattr(process_audio, "Wav2Vec2ForSequenceClassification", MockClassification)
    monkeypatch.setattr(process_audio, "Wav2Vec2Model", MockModel)
    monkeypatch.setattr(process_audio, "Wav2Vec2FeatureExtractor", MockExtractor)
    monkeypatch.setattr(process_audio.torchaudio, "load", lambda _: (torch.zeros(1, 16000), 16000))
    
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"dummy")
    
    result = process_audio.process_audio(str(audio_file), None)
    
    assert len(classification_args) == 1
    assert classification_args[0][1].get("local_files_only") is True
    assert len(model_args) == 1
    assert model_args[0][1].get("local_files_only") is True

