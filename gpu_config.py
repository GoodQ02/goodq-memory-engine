"""
Centralized GPU Configuration for GoodQ4All Pipeline
Single source of truth for GPU management across all pipeline steps
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GPUManager:
    """Manages GPU resources across pipeline steps with memory isolation"""
    
    # Memory allocation per step (as fraction of total GPU memory)
    # Conservative allocations to prevent OOM errors
    MEMORY_FRACTIONS = {
        # Audio processing
        "audio_diarize": 0.35,          # PyAnnote speaker diarization
        "audio_transcribe": 0.30,       # Faster Whisper transcription
        "audio_embed_clap": 0.25,       # CLAP audio embeddings
        "audio_emotion": 0.20,          # Audio emotion detection
        
        # Image/Video processing  
        "image_embed_clip": 0.30,       # CLIP vision embeddings
        "image_embed_dino": 0.30,       # DINOv2 embeddings
        "face_embed": 0.25,             # FaceNet embeddings
        "object_detect": 0.35,          # YOLO object detection
        "object_track_yolo": 0.35,      # YOLO object tracking
        "video_scene_detect": 0.20,     # Scene detection
        
        # NLP processing
        "emotion_classify": 0.30,       # RoBERTa emotion classification
        "text_embed": 0.20,             # SentenceTransformers
        "llm_chat": 0.40,               # LLM inference (if needed)
        
        # Default fallback
        "default": 0.25
    }
    
    _initialized = False
    _current_step = None
    
    @staticmethod
    def configure_environment(gpu_id: int = 0):
        """Configure environment variables for GPU access"""
        # Pin to specific GPU
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        
        # Model caching - use L:/models for all models
        os.environ["HF_HOME"] = "L:/models"
        os.environ["TORCH_HOME"] = "L:/models"
        os.environ["TRANSFORMERS_CACHE"] = "L:/models/transformers"
        os.environ["HF_HUB_CACHE"] = "L:/models/hub"
        
        # Disable unnecessary features
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid deadlocks
        
        # Deterministic behavior for reproducibility
        os.environ["PYTHONHASHSEED"] = "1337"
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        
        logger.debug(f"GPU environment configured: CUDA_VISIBLE_DEVICES={gpu_id}")
    
    @staticmethod
    def setup_pytorch(device: str, memory_fraction: float = 0.3):
        """Configure PyTorch for optimal GPU usage"""
        try:
            import torch
            
            if device == "cuda" and torch.cuda.is_available():
                # Set memory fraction
                try:
                    torch.cuda.set_per_process_memory_fraction(memory_fraction, 0)
                except Exception as e:
                    logger.warning(f"Could not set memory fraction: {e}")
                
                # Disable cuDNN benchmark for deterministic behavior
                torch.backends.cudnn.benchmark = False
                torch.backends.cudnn.deterministic = True
                
                # Use deterministic algorithms when possible
                try:
                    torch.use_deterministic_algorithms(True, warn_only=True)
                except Exception:
                    pass  # Older PyTorch versions
                
                # Clear any existing cache
                torch.cuda.empty_cache()
                
                logger.debug(f"PyTorch configured: memory_fraction={memory_fraction:.2%}")
        except ImportError:
            pass  # PyTorch not installed
        except Exception as e:
            logger.warning(f"Failed to configure PyTorch: {e}")
    
    @staticmethod
    def clear_cache():
        """Clear GPU cache to free memory"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                import gc
                gc.collect()
                logger.debug("GPU cache cleared")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Could not clear GPU cache: {e}")
    
    @staticmethod
    def get_device() -> str:
        """Get the best available device"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"
    
    @staticmethod
    def get_gpu_stats() -> Optional[Dict[str, Any]]:
        """Get current GPU memory usage"""
        try:
            import torch
            if not torch.cuda.is_available():
                return None
            
            allocated = torch.cuda.memory_allocated(0) / 1024**3  # GB
            reserved = torch.cuda.memory_reserved(0) / 1024**3    # GB
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
            
            return {
                "allocated_gb": round(allocated, 2),
                "reserved_gb": round(reserved, 2),
                "total_gb": round(total, 2),
                "free_gb": round(total - reserved, 2),
                "utilization_pct": round((allocated / total) * 100, 1)
            }
        except Exception as e:
            logger.debug(f"Could not get GPU stats: {e}")
            return None


def setup_step_gpu(step_name: str, gpu_id: int = 0) -> Dict[str, Any]:
    """
    Configure GPU for a specific pipeline step.
    Call this at the beginning of each step that needs GPU.
    
    Args:
        step_name: Name of the pipeline step
        gpu_id: GPU device ID (default: 0)
        
    Returns:
        dict with configuration:
            - device: "cuda" or "cpu"
            - step_name: name of the step
            - memory_fraction: allocated memory fraction
            - gpu_stats: current GPU stats (if available)
    """
    # Configure environment variables (only needs to happen once)
    if not GPUManager._initialized:
        GPUManager.configure_environment(gpu_id)
        GPUManager._initialized = True
    
    # Get memory fraction for this step
    memory_fraction = GPUManager.MEMORY_FRACTIONS.get(
        step_name,
        GPUManager.MEMORY_FRACTIONS["default"]
    )
    
    # Determine device
    device = GPUManager.get_device()
    
    # Configure PyTorch if using CUDA
    if device == "cuda":
        GPUManager.setup_pytorch(device, memory_fraction)
    
    # Build configuration
    config = {
        "device": device,
        "step_name": step_name,
        "memory_fraction": memory_fraction,
        "gpu_id": gpu_id if device == "cuda" else None
    }
    
    # Add GPU stats if available
    stats = GPUManager.get_gpu_stats()
    if stats:
        config["gpu_stats"] = stats
        logger.info(
            f"[{step_name}] GPU configured: device={device}, "
            f"memory={memory_fraction:.1%}, "
            f"used={stats['allocated_gb']:.2f}/{stats['total_gb']:.2f}GB "
            f"({stats['utilization_pct']}%)"
        )
    else:
        logger.info(f"[{step_name}] Running on {device.upper()}")
    
    # Track current step for debugging
    GPUManager._current_step = step_name
    
    return config


def resolve_device() -> str:
    """
    Simple device resolution helper.
    Returns "cuda" if available, otherwise "cpu".
    """
    return GPUManager.get_device()


if __name__ == "__main__":
    # Test GPU configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    print("=" * 80)
    print("GPU Configuration Test")
    print("=" * 80)
    print()
    
    # Test each step
    test_steps = ["audio_diarize", "audio_transcribe", "image_embed_clip", 
                  "face_embed", "emotion_classify"]
    
    for step in test_steps:
        config = setup_step_gpu(step)
        print(f"{step}:")
        print(f"  Device: {config['device']}")
        print(f"  Memory Fraction: {config['memory_fraction']:.1%}")
        if 'gpu_stats' in config:
            stats = config['gpu_stats']
            print(f"  GPU Usage: {stats['allocated_gb']:.2f}GB / {stats['total_gb']:.2f}GB")
        print()
        
        # Clear cache between tests
        GPUManager.clear_cache()
    
    print("=" * 80)
    print("Test complete!")
    print("=" * 80)
