"""
GPU Memory Guard
Monitors GPU memory and prevents OOM errors
"""

import os
import time
import logging

logger = logging.getLogger(__name__)

class GPUGuard:
    """Monitors and guards against GPU OOM"""
    
    def __init__(self, max_fraction=0.90):
        self.max_fraction = max_fraction
        self.torch = None
        self._init_torch()
    
    def _init_torch(self):
        """Initialize PyTorch if available"""
        try:
            import torch
            self.torch = torch
            if torch.cuda.is_available():
                self.device_props = torch.cuda.get_device_properties(0)
                self.total_memory = self.device_props.total_memory
                logger.info(f"[GPUGuard] Monitoring {torch.cuda.get_device_name(0)}")
                logger.info(f"[GPUGuard] Total VRAM: {self.total_memory/1024**3:.2f} GB")
        except ImportError:
            logger.warning("[GPUGuard] PyTorch not available")
    
    def check_memory(self):
        """Check current GPU memory usage"""
        if not self.torch or not self.torch.cuda.is_available():
            return {"available": False}
        
        try:
            allocated = self.torch.cuda.memory_allocated(0)
            reserved = self.torch.cuda.memory_reserved(0)
            
            allocated_pct = allocated / self.total_memory
            reserved_pct = reserved / self.total_memory
            
            return {
                "available": True,
                "allocated_gb": allocated / 1024**3,
                "reserved_gb": reserved / 1024**3,
                "total_gb": self.total_memory / 1024**3,
                "allocated_pct": allocated_pct,
                "reserved_pct": reserved_pct,
                "safe": reserved_pct < self.max_fraction
            }
        except Exception as e:
            logger.error(f"[GPUGuard] Error checking memory: {e}")
            return {"available": False, "error": str(e)}
    
    def wait_for_memory(self, required_gb, timeout=60):
        """
        Wait for enough GPU memory to become available
        
        Args:
            required_gb: Required memory in GB
            timeout: Maximum wait time in seconds
            
        Returns:
            True if memory available, False if timeout
        """
        if not self.torch or not self.torch.cuda.is_available():
            return True  # No GPU, proceed anyway
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            stats = self.check_memory()
            
            if not stats.get("available"):
                return True  # No GPU, proceed
            
            free_gb = stats["total_gb"] - stats["reserved_gb"]
            
            if free_gb >= required_gb:
                logger.info(f"[GPUGuard] {free_gb:.2f} GB available (need {required_gb:.2f} GB)")
                return True
            
            logger.warning(f"[GPUGuard] Waiting for {required_gb:.2f} GB (only {free_gb:.2f} GB free)...")
            time.sleep(2)
        
        logger.error(f"[GPUGuard] Timeout waiting for {required_gb:.2f} GB GPU memory")
        return False
    
    def clear_cache_if_needed(self):
        """Clear GPU cache if memory usage is high"""
        if not self.torch or not self.torch.cuda.is_available():
            return
        
        stats = self.check_memory()
        
        if stats.get("available") and not stats.get("safe"):
            logger.warning(f"[GPUGuard] High memory usage ({stats['reserved_pct']*100:.1f}%), clearing cache...")
            self.torch.cuda.empty_cache()
            self.torch.cuda.synchronize()
            
            # Check again
            stats_after = self.check_memory()
            freed_gb = stats["reserved_gb"] - stats_after["reserved_gb"]
            logger.info(f"[GPUGuard] Freed {freed_gb:.2f} GB")
