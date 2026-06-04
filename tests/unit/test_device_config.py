import sys
import os
import torch
from unittest.mock import patch, MagicMock
from steps.common.device_config import DeviceConfig

def test_device_config_cuda():
    config = DeviceConfig()
    with patch("torch.cuda.is_available", return_value=True), \
         patch.dict(os.environ, {}, clear=True):
        # Reset detect state
        config._initialized = False
        config._detect()
        assert config.device_kind == "cuda"
        assert config.supports_memory_fraction is True
        assert config.supports_fp16 is True

def test_device_config_mps():
    config = DeviceConfig()
    
    # Mock torch.backends.mps
    mock_backends = MagicMock()
    mock_backends.mps = MagicMock()
    mock_backends.mps.is_available.return_value = True
    
    with patch("torch.cuda.is_available", return_value=False), \
         patch("torch.backends", mock_backends), \
         patch.dict(os.environ, {}, clear=True):
        config._initialized = False
        config._detect()
        assert config.device_kind == "mps"
        assert config.supports_memory_fraction is False
        assert config.supports_fp16 is False  # Restricted on MPS by default
        assert config.supports_diarization_accel is False

def test_device_config_override():
    config = DeviceConfig()
    with patch.dict(os.environ, {"GOODQ_DEVICE": "cpu"}):
        config._initialized = False
        config._detect()
        assert config.device_kind == "cpu"
        assert config.supports_memory_fraction is False
