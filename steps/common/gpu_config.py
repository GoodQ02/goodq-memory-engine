"""
GPU Configuration Module
Auto-configures GPU settings when imported by pipeline steps
"""

import logging
import os
import sys
from pathlib import Path

from steps.common.profile_config import (
    is_baseline,
    log_runtime_profile_state,
    require_gpu,
)


def _console_print(text: str) -> None:
    """Print diagnostics without crashing on cp1252-only consoles."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_text)


# Determine which step is importing this
def get_step_name():
    """Detect which step is importing this module"""
    import inspect
    frame = inspect.currentframe()
    try:
        # Walk up the stack to find the step directory
        while frame:
            filename = frame.f_code.co_filename
            path = Path(filename)
            
            # Check if we're in a step directory
            if 'steps' in path.parts:
                parts = list(path.parts)
                steps_idx = parts.index('steps')
                if steps_idx + 1 < len(parts):
                    step_name = parts[steps_idx + 1]
                    # Map step names to GPU config names
                    return step_name
            
            frame = frame.f_back
    finally:
        del frame
    
    return None

def configure_gpu(step_name=None, force_fraction=None):
    """Configure GPU settings for the current step"""
    
    if step_name is None:
        step_name = get_step_name()
    
    # GPU configuration per step (fraction of total VRAM)
    GPU_CONFIGS = {
        "video_scene_detect": 0.20,      # GPU-accelerated frame difference + histogram
        "audio_transcribe": 0.25,        # Whisper medium
        "audio_diarize": 0.35,           # PyAnnote + embeddings
        "face_embed": 0.20,              # OpenCV YuNet/SFace
        "emotion_classify": 0.20,        # Emotion CNN
        "text_embed": 0.15,              # Sentence transformers
        "image_embed_clip": 0.25,        # CLIP ViT
        "image_embed_dino": 0.25,        # DINOv2
        "object_detect": 0.25,           # YOLO
        "object_track_yolo": 0.25,       # YOLO tracking
        "image_caption": 0.20,           # BLIP or similar
        "audio_embed_clap": 0.20,        # CLAP audio embeddings
        "audio_emotion": 0.15,           # Audio emotion model
        "image_ocr": 0.15,               # OCR model
        "llm_chat": 0.40,                # LLM (if local)
    }
    
    # Default fraction if step not found
    memory_fraction = force_fraction if force_fraction else GPU_CONFIGS.get(step_name, 0.20)
    
    # Set environment variables BEFORE importing torch
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["CUDA_LAUNCH_BLOCKING"] = "0"  # Async kernel launches for speed
    
    # Try to configure PyTorch
    try:
        import torch
        
        if torch.cuda.is_available():
            # Set memory fraction
            torch.cuda.set_per_process_memory_fraction(memory_fraction, 0)
            
            # Enable TF32 for better performance on Ampere+ GPUs (RTX 30xx, 40xx)
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            
            # Optimize CUDA settings
            torch.backends.cudnn.benchmark = True  # Auto-tune kernels
            torch.backends.cudnn.enabled = True
            
            # Enable cuDNN auto-tuner for optimal algorithm selection
            torch.backends.cudnn.deterministic = False  # For speed over reproducibility
            
            # Clear any existing cache
            torch.cuda.empty_cache()
            
            # Get device properties
            device_props = torch.cuda.get_device_properties(0)
            total_memory_gb = device_props.total_memory / 1024**3
            allocated_gb = total_memory_gb * memory_fraction
            
            _console_print(f"╔{'═'*78}╗")
            _console_print(f"║ GPU Configuration: {step_name or 'unknown':>57} ║")
            _console_print(f"╠{'═'*78}╣")
            _console_print(f"║ Device: {device_props.name:<67} ║")
            _console_print(f"║ Total VRAM: {total_memory_gb:>6.2f} GB{' '*55} ║")
            _console_print(f"║ Allocated: {allocated_gb:>6.2f} GB ({memory_fraction*100:>5.1f}%){' '*43} ║")
            _console_print(f"║ CUDA Capability: {device_props.major}.{device_props.minor}{' '*57} ║")
            _console_print(f"║ TF32 Enabled: {'Yes' if torch.backends.cuda.matmul.allow_tf32 else 'No':<66} ║")
            _console_print(f"║ cuDNN Benchmark: {'Yes' if torch.backends.cudnn.benchmark else 'No':<63} ║")
            _console_print(f"╚{'═'*78}╝")
            
            return {
                "available": True,
                "device": "cuda:0",
                "device_name": device_props.name,
                "total_memory_gb": total_memory_gb,
                "allocated_gb": allocated_gb,
                "memory_fraction": memory_fraction,
                "tf32_enabled": True,
                "cudnn_benchmark": True
            }
        else:
            if require_gpu():
                raise RuntimeError(f"CUDA required but unavailable for step '{step_name}'")
            _console_print(f"[SYMBOL] CUDA not available for {step_name} - using CPU")
            return {
                "available": False,
                "device": "cpu"
            }
            
    except ImportError as e:
        if require_gpu():
            raise RuntimeError(f"PyTorch required for GPU step '{step_name}' but is not installed") from e
        _console_print(f"[SYMBOL] PyTorch not installed for {step_name} - GPU config skipped")
        return {
            "available": False,
            "device": "cpu",
            "reason": "pytorch_not_installed"
        }
    except Exception as e:
        if require_gpu():
            raise RuntimeError(f"GPU configuration failed for step '{step_name}': {e}") from e
        _console_print(f"[SYMBOL] GPU configuration failed for {step_name}: {e}")
        return {
            "available": False,
            "device": "cpu",
            "reason": str(e)
        }

def get_device():
    """Get the configured torch device"""
    try:
        import torch
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    except Exception:
        return "cpu"

def clear_cache():
    """Clear GPU cache to free memory"""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass

def print_memory_stats():
    """Print current GPU memory statistics"""
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            max_allocated = torch.cuda.max_memory_allocated(0) / 1024**3
            
            _console_print(
                f"GPU Memory - Allocated: {allocated:.2f} GB, "
                f"Reserved: {reserved:.2f} GB, "
                f"Peak: {max_allocated:.2f} GB"
            )
            return {
                "allocated_gb": allocated,
                "reserved_gb": reserved,
                "peak_gb": max_allocated
            }
    except Exception:
        pass
    return None


# Auto-configure on import (can be disabled with GOODQ_NO_AUTO_GPU=1)
if is_baseline():
    # Baseline profile is CPU-safe by default; preserve explicit flag contract.
    os.environ["GOODQ_NO_AUTO_GPU"] = "1"

if require_gpu() and os.getenv("GOODQ_NO_AUTO_GPU") == "1":
    raise RuntimeError("GOODQ_REQUIRE_GPU=1 but GPU auto-config is disabled (GOODQ_NO_AUTO_GPU=1)")

if os.getenv("GOODQ_NO_AUTO_GPU") != "1":
    _gpu_config = configure_gpu()
else:
    reason = "host_profile_baseline" if is_baseline() else "auto_config_disabled"
    _gpu_config = {"available": False, "device": "cpu", "reason": reason}

log_runtime_profile_state(
    logger=logging.getLogger(__name__),
    context="steps.common.gpu_config",
    gpu_enabled=bool(_gpu_config.get("available")),
    wsl_enabled=None,
)

# Export for use by steps
__all__ = ['configure_gpu', 'get_device', 'clear_cache', 'print_memory_stats', '_gpu_config']
