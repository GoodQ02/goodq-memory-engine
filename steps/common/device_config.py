import os
import sys
import torch
import logging

logger = logging.getLogger(__name__)

class DeviceConfig:
    def __init__(self):
        self._device_kind = None
        self._initialized = False
        
    def _detect(self):
        if self._initialized:
            return
            
        override = os.environ.get("GOODQ_DEVICE")
        if override:
            self._device_kind = override.lower()
            self._initialized = True
            return

        if torch.cuda.is_available():
            self._device_kind = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self._device_kind = "mps"
        else:
            self._device_kind = "cpu"
        self._initialized = True

    @property
    def device_kind(self) -> str:
        self._detect()
        return self._device_kind

    @property
    def torch_device(self) -> torch.device:
        if self.device_kind == "cuda":
            return torch.device("cuda:0")
        elif self.device_kind == "mps":
            return torch.device("mps")
        return torch.device("cpu")

    @property
    def supports_memory_fraction(self) -> bool:
        return self.device_kind == "cuda"

    @property
    def supports_empty_cache(self) -> bool:
        return self.device_kind in ("cuda", "mps")

    @property
    def supports_fp16(self) -> bool:
        if self.device_kind == "mps":
            return os.environ.get("GOODQ_MPS_FP16") == "1"
        return self.device_kind == "cuda"

    @property
    def supports_diarization_accel(self) -> bool:
        if self.device_kind == "mps":
            return os.environ.get("GOODQ_MPS_DIARIZATION") == "1"
        return self.device_kind == "cuda"

    def empty_cache(self):
        if self.device_kind == "cuda":
            torch.cuda.empty_cache()
        elif self.device_kind == "mps":
            try:
                import torch.mps
                torch.mps.empty_cache()
            except (ImportError, AttributeError):
                pass

device_config = DeviceConfig()
