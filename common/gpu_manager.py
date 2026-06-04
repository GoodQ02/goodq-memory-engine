"""
GPU Resource Manager for GoodQ Pipeline
Provides GPU isolation, memory management, and process control
"""

import os
import torch
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class GPUManager:
    """Manages GPU resources for pipeline steps"""
    
    def __init__(
        self,
        gpu_id: int = 0,
        memory_fraction: float = 0.8,
        enable_determinism: bool = False
    ):
        """
        Initialize GPU manager
        
        Args:
            gpu_id: Which GPU to use (0-based index)
            memory_fraction: Fraction of GPU memory to use (0.0-1.0)
            enable_determinism: Enable deterministic algorithms (slower but reproducible)
        """
        self.gpu_id = gpu_id
        self.memory_fraction = memory_fraction
        self.enable_determinism = enable_determinism
        self._initialized = False
        
    def initialize(self) -> bool:
        """Initialize GPU settings for this process"""
        if self._initialized:
            logger.warning("GPU manager already initialized")
            return True
            
        try:
            from steps.common.device_config import device_config
            
            # 1. Pin GPU access - only see specified GPU (CUDA only)
            if device_config.device_kind == "cuda":
                os.environ['CUDA_VISIBLE_DEVICES'] = str(self.gpu_id)
                logger.info(f"[SYMBOL] Set CUDA_VISIBLE_DEVICES={self.gpu_id}")
            
            # 2. Check if device is available
            if device_config.device_kind == "cpu":
                logger.warning("GPU not available, running on CPU")
                self._initialized = True
                return False
                
            # 3. Set memory fraction (CUDA only)
            if device_config.supports_memory_fraction:
                try:
                    torch.cuda.set_per_process_memory_fraction(
                        self.memory_fraction, 
                        0  # Always 0 since we set CUDA_VISIBLE_DEVICES
                    )
                    logger.info(f"[SYMBOL] Set memory fraction to {self.memory_fraction*100:.0f}%")
                except Exception as e:
                    logger.warning(f"Could not set memory fraction: {e}")
            
            # 4. Enable memory growth (PyTorch equivalent)
            device_config.empty_cache()
            
            # 5. Set determinism if requested
            if self.enable_determinism:
                self._enable_deterministic_mode()
                
            # 6. Log GPU info
            self._log_gpu_info()
            
            self._initialized = True
            logger.info("[SYMBOL] GPU manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GPU manager: {e}")
            self._initialized = False
            return False
    
    def _enable_deterministic_mode(self):
        """Enable deterministic algorithms for reproducibility"""
        try:
            # Set Python hash seed
            os.environ['PYTHONHASHSEED'] = '1337'
            
            # Set cuBLAS workspace config
            os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
            
            # Disable cuDNN benchmark
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
            
            # Enable deterministic algorithms
            torch.use_deterministic_algorithms(True, warn_only=True)
            
            logger.info("[SYMBOL] Enabled deterministic mode")
        except Exception as e:
            logger.warning(f"Could not enable full determinism: {e}")
    
    def _log_gpu_info(self):
        """Log GPU information"""
        try:
            from steps.common.device_config import device_config
            if device_config.device_kind == "cuda":
                gpu_name = torch.cuda.get_device_name(0)
                total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
                logger.info(f"GPU: {gpu_name}")
                logger.info(f"Total Memory: {total_memory:.2f} GB")
                logger.info(f"Allocated Memory Limit: {total_memory * self.memory_fraction:.2f} GB")
            elif device_config.device_kind == "mps":
                logger.info("GPU: Apple Metal Performance Shaders (MPS)")
        except Exception as e:
            logger.warning(f"Could not log GPU info: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current GPU memory statistics"""
        from steps.common.device_config import device_config
        if device_config.device_kind != "cuda":
            return {"cuda_available": False, "device": device_config.device_kind}
            
        try:
            allocated = torch.cuda.memory_allocated(0) / 1e9
            reserved = torch.cuda.memory_reserved(0) / 1e9
            total = torch.cuda.get_device_properties(0).total_memory / 1e9
            
            return {
                "cuda_available": True,
                "gpu_id": self.gpu_id,
                "allocated_gb": round(allocated, 2),
                "reserved_gb": round(reserved, 2),
                "total_gb": round(total, 2),
                "utilization_pct": round((allocated / total) * 100, 1)
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"error": str(e)}
    
    def clear_cache(self):
        """Clear GPU cache"""
        from steps.common.device_config import device_config
        device_config.empty_cache()
        logger.debug("Cleared GPU cache")
    
    def get_device(self) -> torch.device:
        """Get the torch device to use"""
        from steps.common.device_config import device_config
        return device_config.torch_device
    
    @staticmethod
    def set_exclusive_mode(enable: bool = True):
        """
        Set GPU to exclusive process mode (requires admin/root)
        
        Args:
            enable: True for exclusive mode, False for default mode
        """
        try:
            import subprocess
            mode = "EXCLUSIVE_PROCESS" if enable else "DEFAULT"
            result = subprocess.run(
                ['nvidia-smi', '-c', mode],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"[SYMBOL] Set GPU to {mode} mode")
                return True
            else:
                logger.warning(f"Could not set GPU mode: {result.stderr}")
                return False
        except Exception as e:
            logger.warning(f"Could not set exclusive mode: {e}")
            return False


# Global GPU manager instance
_gpu_manager: Optional[GPUManager] = None


def get_gpu_manager(
    gpu_id: int = 0,
    memory_fraction: float = 0.8,
    enable_determinism: bool = False
) -> GPUManager:
    """
    Get or create the global GPU manager instance
    
    Args:
        gpu_id: Which GPU to use (0-based index)
        memory_fraction: Fraction of GPU memory to use (0.0-1.0)
        enable_determinism: Enable deterministic algorithms
        
    Returns:
        GPUManager instance
    """
    global _gpu_manager
    
    if _gpu_manager is None:
        _gpu_manager = GPUManager(
            gpu_id=gpu_id,
            memory_fraction=memory_fraction,
            enable_determinism=enable_determinism
        )
        _gpu_manager.initialize()
    
    return _gpu_manager


def initialize_gpu_for_step(
    step_name: str,
    memory_fraction: float = 0.6,
    enable_determinism: bool = False
) -> GPUManager:
    """
    Initialize GPU for a specific pipeline step
    
    Args:
        step_name: Name of the pipeline step
        memory_fraction: Fraction of GPU memory to allocate
        enable_determinism: Enable deterministic mode
        
    Returns:
        Initialized GPUManager
    """
    logger.info(f"[{step_name}] Initializing GPU manager...")
    
    gpu_manager = get_gpu_manager(
        gpu_id=0,
        memory_fraction=memory_fraction,
        enable_determinism=enable_determinism
    )
    
    # Log memory stats
    stats = gpu_manager.get_memory_stats()
    if stats.get("cuda_available"):
        logger.info(f"[{step_name}] GPU Memory: {stats['allocated_gb']}/{stats['total_gb']} GB ({stats['utilization_pct']}%)")
    else:
        logger.info(f"[{step_name}] Running on CPU")
    
    return gpu_manager
