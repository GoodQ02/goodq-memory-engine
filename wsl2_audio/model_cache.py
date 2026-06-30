import os
import logging
import time
import re
from pathlib import Path
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

def redact_sensitive_info(text: str) -> str:
    """Mask sensitive environment token values and hf_* patterns in text."""
    if not isinstance(text, str):
        text = str(text)
    
    # 1. Mask environment token values with <REDACTED>
    for key, val in os.environ.items():
        key_upper = key.upper()
        if any(keyword in key_upper for keyword in ["TOKEN", "SECRET", "PASSWORD", "KEY", "API"]):
            val_stripped = val.strip()
            if val_stripped and len(val_stripped) > 4:
                text = text.replace(val_stripped, "<REDACTED>")
                
    token_keys = ["HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_HUB_TOKEN", "PYANNOTE_TOKEN"]
    for key in token_keys:
        val = os.environ.get(key)
        if val:
            val_stripped = val.strip()
            if val_stripped:
                text = text.replace(val_stripped, "<REDACTED>")

    # 2. Mask regex matches of hf_[a-zA-Z0-9]+ with hf_***
    text = re.sub(r'hf_[a-zA-Z0-9]+', 'hf_***', text)
    
    return text

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

def check_hf_model_cache(repo_id: str) -> bool:
    """Check if a Hugging Face repository has a cached snapshot locally."""
    folder_name = "models--" + repo_id.replace("/", "--")
    candidates = []
    
    # 1. Check GOODQ_MODEL_CACHE_ROOT
    cache_root = os.environ.get("GOODQ_MODEL_CACHE_ROOT")
    if cache_root:
        candidates.extend([
            Path(cache_root) / "hub" / folder_name,
            Path(cache_root) / folder_name,
        ])
        
    # 2. Check HF_HOME or HUGGINGFACE_HUB_CACHE
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home) / "hub" / folder_name)
        
    hf_cache = os.environ.get("HUGGINGFACE_HUB_CACHE") or os.environ.get("HF_HUB_CACHE")
    if hf_cache:
        candidates.extend([
            Path(hf_cache) / folder_name,
            Path(hf_cache) / "hub" / folder_name,
        ])
        
    # 3. Check user home folder (standard location)
    candidates.append(Path.home() / ".cache" / "huggingface" / "hub" / folder_name)
    
    for cand in candidates:
        if cand.is_dir():
            snapshots_dir = cand / "snapshots"
            if snapshots_dir.is_dir():
                for snap in snapshots_dir.iterdir():
                    if snap.is_dir():
                        if "faster-whisper" in repo_id:
                            model_bin = snap / "model.bin"
                            if model_bin.exists():
                                resolved = model_bin.resolve()
                                if resolved.is_file() and resolved.stat().st_size > 0:
                                    return True
                        else:
                            for file_path in snap.rglob('*'):
                                if file_path.is_file():
                                    try:
                                        resolved = file_path.resolve()
                                        if resolved.is_file() and resolved.stat().st_size > 0:
                                            ext = resolved.suffix.lower()
                                            name = resolved.name.lower()
                                            if ext in ('.bin', '.safetensors', '.json', '.pt', '.pth', '.onnx', '.h5', '.ckpt') or name in ('config.json', 'model.bin'):
                                                return True
                                    except Exception:
                                        pass
    return False

def check_whisper_cache(model_name: str) -> bool:
    """Check if Whisper model exists in local Hugging Face cache or local path."""
    if Path(model_name).exists():
        return True
    repo_name = model_name
    if "/" not in repo_name:
        repo_name = f"Systran/faster-whisper-{model_name}"
    return check_hf_model_cache(repo_name)

def check_pyannote_cache(model_name: str) -> bool:
    """Check if PyAnnote diarization pipeline and its sub-models are cached."""
    repos = [
        model_name,
        "pyannote/segmentation-3.0",
        "pyannote/wespeaker-voxceleb-resnet34-LM"
    ]
    return all(check_hf_model_cache(repo) for repo in repos)

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
            "Offline mode: Silero VAD model 'snakers4/silero-vad' (revision 'v4.0' pinned) is missing from local cache (hubconf.py not found in any search path).\n"
            "Status: Non-gated.\n"
            "Requirements: No Hugging Face token or license terms required.\n"
            "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py --download-silero"
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
            summary.append(f"{tok_key} present: Yes")
        else:
            summary.append(f"{tok_key} present: No")
            
    logger_instance.info("[env_summary] Active WSL environment: " + ", ".join(summary))
