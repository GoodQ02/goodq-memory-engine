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


import pytest

@pytest.mark.parametrize("device", ["cuda", "mps", "cpu"])
def test_gpu_manager_cache_cleanup_routes_to_device(monkeypatch, device):
    from common.gpu_manager import GPUManager
    from steps.common import device_config as module
    config = DeviceConfig()
    config._initialized, config._device_kind = True, device
    monkeypatch.setattr(module, "device_config", config)
    cuda, mps = MagicMock(), MagicMock()
    monkeypatch.setattr(torch.cuda, "empty_cache", cuda)
    monkeypatch.setattr(torch.mps, "empty_cache", mps)
    GPUManager.clear_cache(object())
    assert cuda.call_count == (device == "cuda")
    assert mps.call_count == (device == "mps")


def test_gpu_cache_cleanup_failure_is_visible(monkeypatch):
    from common.gpu_manager import GPUManager
    from steps.common import device_config as module
    config = DeviceConfig()
    config._initialized, config._device_kind = True, "cuda"
    monkeypatch.setattr(module, "device_config", config)
    monkeypatch.setattr(torch.cuda, "empty_cache", MagicMock(side_effect=RuntimeError("cleanup failed")))
    with pytest.raises(RuntimeError, match="cleanup failed"):
        GPUManager.clear_cache(object())


def test_gpu_manager_initialization_reaches_cache_cleanup(monkeypatch):
    from common.gpu_manager import GPUManager
    from steps.common import device_config as module
    config = DeviceConfig()
    config._initialized, config._device_kind = True, "cuda"
    monkeypatch.setattr(module, "device_config", config)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    clear = MagicMock()
    monkeypatch.setattr(torch.cuda, "empty_cache", clear)
    monkeypatch.setattr(torch.cuda, "set_per_process_memory_fraction", MagicMock())
    monkeypatch.setattr(GPUManager, "_log_gpu_info", lambda self: None)
    manager = GPUManager()
    assert manager.initialize() is True
    assert manager._initialized is True
    clear.assert_called_once_with()
