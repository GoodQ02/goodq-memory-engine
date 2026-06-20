import os
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

def is_offline_mode() -> bool:
    """Check if offline mode is requested or configured."""
    env_offline = (
        os.environ.get("GOODQ_OFFLINE", "").strip() in ("1", "true", "TRUE", "yes", "ON") or
        os.environ.get("HF_HUB_OFFLINE", "").strip() in ("1", "true", "TRUE", "yes", "ON") or
        os.environ.get("TRANSFORMERS_OFFLINE", "").strip() in ("1", "true", "TRUE", "yes", "ON")
    )
    return env_offline

def resolve_silero_local_path() -> Optional[str]:
    """
    Search environment variables and standard paths to resolve the local directory
    for Silero VAD (which must contain hubconf.py).
    """
    candidates = []
    
    # 1. Check GOODQ_MODEL_CACHE_ROOT
    cache_root = os.environ.get("GOODQ_MODEL_CACHE_ROOT")
    if cache_root:
        cache_path = Path(cache_root)
        candidates.extend([
            cache_path / "torchhub" / "snakers4_silero-vad_master",
            cache_path / "hub" / "snakers4_silero-vad_master",
            cache_path / "snakers4_silero-vad_master",
        ])
        
    # 2. Check TORCH_HOME
    torch_home = os.environ.get("TORCH_HOME")
    if torch_home:
        torch_path = Path(torch_home)
        candidates.extend([
            torch_path / "hub" / "snakers4_silero-vad_master",
            torch_path / "snakers4_silero-vad_master",
        ])
        
    # 3. Check HF_HOME or HUGGINGFACE_HUB_CACHE
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home) / "hub" / "snakers4_silero-vad_master")
        
    hf_cache = os.environ.get("HUGGINGFACE_HUB_CACHE") or os.environ.get("HF_HUB_CACHE")
    if hf_cache:
        candidates.append(Path(hf_cache) / "snakers4_silero-vad_master")
        
    # 4. Check user home folder (standard torch.hub location)
    candidates.append(Path.home() / ".cache" / "torch" / "hub" / "snakers4_silero-vad_master")

    # Filter and find the first one that exists and contains hubconf.py
    for cand in candidates:
        if cand.is_dir() and (cand / "hubconf.py").is_file():
            resolved = str(cand.absolute())
            logger.info(f"[model_cache] Resolved Silero VAD local cache directory: {resolved}")
            return resolved
            
    logger.warning("[model_cache] Could not find local Silero VAD cache directory containing hubconf.py")
    return None

def load_silero_vad(offline: bool = False) -> Tuple[Any, Any]:
    """
    Loads Silero VAD model and returns (model, utils).
    Ensures that offline mode never attempts internet downloads.
    """
    import torch
    
    is_offline = offline or is_offline_mode()
    local_path = resolve_silero_local_path()
    
    if local_path:
        logger.info(f"[model_cache] Loading Silero VAD locally from: {local_path} (offline={is_offline})")
        model, utils = torch.hub.load(
            repo_or_dir=local_path,
            model='silero_vad',
            source='local',
            force_reload=False,
            onnx=False
        )
        return model, utils
        
    if is_offline:
        raise OSError(
            "Offline mode: Silero VAD is missing from local cache (hubconf.py not found in any search path). "
            "Please connect to the internet and run the model bootstrap script on the host."
        )
        
    logger.info("[model_cache] Local cache miss. Loading Silero VAD from GitHub (online mode)...")
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        onnx=False
    )
    return model, utils

def log_env_summary(logger_instance: logging.Logger):
    """Log redacted environment variables for debugging and support."""
    keys = [
        "GOODQ_MODEL_CACHE_ROOT",
        "TORCH_HOME",
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "PYANNOTE_CACHE",
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "GOODQ_OFFLINE",
        "GOODQ_REQUIRE_GPU",
        "GOODQ_REQUIRE_WSL_AUDIO",
        "GOODQ_WSL_DISTRO",
        "GOODQ_WSL_USER",
        "GOODQ_WSL_WORKSPACE",
        "GOODQ_WSL_AUDIO_CACHE_FALLBACK",
    ]
    summary = []
    for k in keys:
        val = os.environ.get(k)
        if val is not None:
            summary.append(f"{k}={val}")
            
    # Include tokens but redacted
    for tok_key in ("HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_HUB_TOKEN", "PYANNOTE_TOKEN"):
        val = os.environ.get(tok_key)
        if val:
            redacted = f"{val[:5]}...{val[-5:]}" if len(val) > 10 else "present"
            summary.append(f"{tok_key}={redacted}")
            
    logger_instance.info("[env_summary] Active WSL environment: " + ", ".join(summary))
