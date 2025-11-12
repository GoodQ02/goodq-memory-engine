"""
GPU Isolation and Memory Management Configuration
Phase 2 Implementation - Bare Metal GPU Control

This module provides centralized GPU management for the GoodQ4All pipeline.
It implements memory isolation, device pinning, and deterministic behavior
without requiring Docker containers.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GPUManager:
    """Manages GPU resources across pipeline steps"""
    
    # Memory allocation per step (as fraction of total GPU memory)
    MEMORY_FRACTIONS = {
        "emotion_classify": 0.30,  # RoBERTa emotion model
        "face_embed": 0.20,         # FaceNet PyTorch
        "image_embed_clip": 0.25,   # CLIP vision model
        "image_embed_dino": 0.25,   # DINOv2 model
        "audio_embed_clap": 0.20,   # CLAP audio model
        "text_embed": 0.15,         # SentenceTransformers
        "object_detect": 0.30,      # YOLO v8
        "default": 0.20             # Fallback for other steps
    }
    
    @staticmethod
    def configure_gpu(step_name: str = "default", gpu_id: int = 0) -> dict:
        """
        Configure GPU settings for a specific pipeline step.
        
        Args:
            step_name: Name of the pipeline step
            gpu_id: GPU device ID (default: 0)
            
        Returns:
            dict with device info and configuration
        """
        # Pin to specific GPU
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", str(gpu_id))
        
        # Model caching paths
        os.environ.setdefault("HF_HOME", "L:/models")
        os.environ.setdefault("TORCH_HOME", "L:/models")
        os.environ.setdefault("TRANSFORMERS_CACHE", "L:/models/transformers")
        
        # Disable unnecessary features
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
        
        # Deterministic behavior
        os.environ.setdefault("PYTHONHASHSEED", "1337")
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        
        memory_fraction = GPUManager.MEMORY_FRACTIONS.get(
            step_name, 
            GPUManager.MEMORY_FRACTIONS["default"]
        )
        
        config = {
            "gpu_id": gpu_id,
            "step_name": step_name,
            "memory_fraction": memory_fraction,
            "device": "cpu"  # Default
        }
        
        # Try to configure PyTorch if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.set_per_process_memory_fraction(memory_fraction, gpu_id)
                torch.backends.cudnn.benchmark = False
                torch.backends.cudnn.deterministic = True
                torch.use_deterministic_algorithms(True, warn_only=True)
                config["device"] = "cuda"
                logger.info(
                    f"GPU configured for {step_name}: "
                    f"device={config['device']}, "
                    f"memory_fraction={memory_fraction:.2%}"
                )
            else:
                logger.info(f"GPU not available for {step_name}, using CPU")
        except Exception as e:
            logger.warning(f"Could not configure GPU for {step_name}: {str(e)}")
        
        return config
    
    @staticmethod
    def enable_mps(thread_percentage: int = 70) -> bool:
        """
        Enable NVIDIA MPS (Multi-Process Service) for better GPU sharing.
        Linux/WSL2 only.
        
        Args:
            thread_percentage: Percentage of GPU threads to allocate
            
        Returns:
            bool indicating success
        """
        if os.name == 'nt':
            logger.warning("MPS is not available on Windows")
            return False
        
        try:
            os.environ["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(thread_percentage)
            logger.info(f"MPS enabled with {thread_percentage}% thread allocation")
            return True
        except Exception as e:
            logger.error(f"Failed to enable MPS: {str(e)}")
            return False
    
    @staticmethod
    def get_gpu_stats() -> Optional[dict]:
        """
        Get current GPU memory usage and stats.
        
        Returns:
            dict with GPU statistics or None if unavailable
        """
        try:
            import torch
            if not torch.cuda.is_available():
                return None
            
            stats = {
                "device_count": torch.cuda.device_count(),
                "current_device": torch.cuda.current_device(),
                "devices": []
            }
            
            for i in range(torch.cuda.device_count()):
                device_stats = {
                    "id": i,
                    "name": torch.cuda.get_device_name(i),
                    "memory_allocated_mb": torch.cuda.memory_allocated(i) / 1024**2,
                    "memory_reserved_mb": torch.cuda.memory_reserved(i) / 1024**2,
                    "memory_total_mb": torch.cuda.get_device_properties(i).total_memory / 1024**2
                }
                stats["devices"].append(device_stats)
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get GPU stats: {str(e)}")
            return None
    
    @staticmethod
    def clear_cache():
        """Clear PyTorch GPU cache"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("GPU cache cleared")
        except Exception as e:
            logger.debug(f"Could not clear GPU cache: {str(e)}")


def setup_step_gpu(step_name: str) -> dict:
    """
    Convenience function to setup GPU for a pipeline step.
    Call this at the start of each GPU-intensive step.
    
    Args:
        step_name: Name of the step (e.g., 'emotion_classify')
        
    Returns:
        Configuration dict
    """
    return GPUManager.configure_gpu(step_name)


if __name__ == "__main__":
    # Test GPU configuration
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 80)
    print("GPU Configuration Test")
    print("=" * 80)
    
    # Test configuration for each step
    for step in GPUManager.MEMORY_FRACTIONS.keys():
        if step != "default":
            config = GPUManager.configure_gpu(step)
            print(f"\n{step}:")
            print(f"  Device: {config['device']}")
            print(f"  Memory Fraction: {config['memory_fraction']:.2%}")
    
    # Display GPU stats if available
    print("\n" + "=" * 80)
    stats = GPUManager.get_gpu_stats()
    if stats:
        print("GPU Statistics:")
        for device in stats["devices"]:
            print(f"\nGPU {device['id']}: {device['name']}")
            print(f"  Allocated: {device['memory_allocated_mb']:.2f} MB")
            print(f"  Reserved: {device['memory_reserved_mb']:.2f} MB")
            print(f"  Total: {device['memory_total_mb']:.2f} MB")
    else:
        print("No GPU available")
    print("=" * 80)
