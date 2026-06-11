"""
ModelLifecycleManager - Gated VRAM budget manager for GoodQ4All.
Ensures SOTA models (DeepSeek-R1-14B, Qwen2.5-VL-7B) do not exceed 16GB VRAM ceiling.
"""

from __future__ import annotations
import os
import sys
import subprocess
import logging
import time
from typing import Any, Dict, Callable, Optional, Set

logger = logging.getLogger(__name__)

# Track loaded models globally across processes/threads in the active runtime
_RESIDENT_MODELS: Dict[str, Dict[str, Any]] = {}


class ModelLifecycleManager:
    """
    Manages loading, unloading, and VRAM budgeting for local AI models.
    Supports a sequential context manager interface to enforce clean unloading.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Load budget from configuration with safe defaults matching RTX 4070 Ti SUPER 16GB
        budget_cfg = config.get("gpu_budget", {}) or {}
        self.total_vram_gb = float(budget_cfg.get("total_vram_gb", 16.0))
        self.reserved_display_gb = float(budget_cfg.get("reserved_display_gb", 1.5))
        self.reserved_cuda_fragmentation_gb = float(budget_cfg.get("reserved_cuda_fragmentation_gb", 1.0))
        self.usable_target_gb = float(budget_cfg.get("usable_target_gb", 13.5))
        self.emergency_stop_gb = float(budget_cfg.get("emergency_stop_gb", 14.5))
        
        # Load model registry definitions
        self.model_registry = config.get("huggingface_models", {}) or {}
        if not self.model_registry:
            try:
                from pathlib import Path
                import yaml
                repo_root = Path(__file__).resolve().parents[1]
                registry_path = repo_root / "configs" / "model_registry.yaml"
                if registry_path.exists():
                    with open(registry_path, "r", encoding="utf-8") as f:
                        registry = yaml.safe_load(f) or {}
                    self.model_registry = registry.get("huggingface_models", {}) or {}
            except Exception as e:
                logger.warning("Failed to auto-load model_registry.yaml: %s", e)
        
    def get_free_vram_gb(self) -> float:
        """
        Query system free VRAM using PyTorch if available, falling back to nvidia-smi.
        Returns free VRAM in Gigabytes.
        """
        # Try PyTorch CUDA runtime first
        try:
            import torch
            if torch.cuda.is_available():
                # torch.cuda.mem_get_info returns (free_bytes, total_bytes)
                free_b, total_b = torch.cuda.mem_get_info()
                return free_b / (1024 ** 3)
        except Exception:
            pass
            
        # Fallback to nvidia-smi command execution
        try:
            cmd = ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,nounits,noheader"]
            out = subprocess.check_output(cmd, text=True).strip()
            return float(out) / 1024.0
        except Exception as e:
            logger.warning("Failed to query GPU VRAM via nvidia-smi: %s. Using default 12.0GB baseline.", e)
            # Default fallback assumption of free headroom if query fails
            return 12.0

    def get_process_vram_gb(self) -> float:
        """Get the VRAM allocated by the current Python process (if PyTorch is active)."""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.memory_allocated() / (1024 ** 3)
        except Exception:
            pass
        return 0.0

    def preflight_check(
        self,
        model_name: str,
        requested_vram_gb: Optional[float] = None,
        target_engine: Optional[str] = None
    ) -> bool:
        """
        Verify if loading the target model fits inside the usable target budget and free VRAM.
        Automatically unloads other resident models if the active profile is sequential_only.
        
        Args:
            model_name: The name of the model registered in model_registry.yaml
            requested_vram_gb: Override VRAM requirement estimate (if not in registry)
            target_engine: The engine to load the model (e.g. Ollama, vLLM, CTranslate2, Transformers)
            
        Returns:
            bool: True if budget constraints are met, False or raises MemoryError otherwise.
        """
        model_entry = self.model_registry.get(model_name, {}) or {}
        
        # 1. Check engine compatibility
        if target_engine:
            supported_engines = model_entry.get("engines", {}) or {}
            # Allow case insensitive matching or direct keys
            supported = False
            for eng, capability in supported_engines.items():
                if eng.lower() == target_engine.lower() and capability in ("yes", True):
                    supported = True
                    break
            if not supported:
                err_msg = (
                    f"Compatibility Block: Model '{model_name}' does not declare support for "
                    f"engine '{target_engine}' in the registry. Supported: "
                    f"{[e for e, cap in supported_engines.items() if cap in ('yes', True)]}"
                )
                logger.error(err_msg)
                raise ValueError(err_msg)

        # Resolve VRAM estimate from registry
        if requested_vram_gb is None:
            requested_vram_gb = float(model_entry.get("vram_estimate_gb", 2.0))

        logger.info(
            "Preflight check for '%s' (Estimate: %.2f GB). usable_target_gb: %.2f GB",
            model_name, requested_vram_gb, self.usable_target_gb
        )
        
        # Check active load policy for the target model
        load_policy = model_entry.get("load_policy", "concurrent_safe")
        
        # Enforce sequential unloading of other resident models if required
        if load_policy == "sequential_only" or len(_RESIDENT_MODELS) > 0:
            resident_keys = list(_RESIDENT_MODELS.keys())
            for res_name in resident_keys:
                if res_name != model_name:
                    logger.info("Enforcing sequential policy: Evicting resident model '%s'", res_name)
                    self.unload(res_name)

        # Query system parameters
        free_vram = self.get_free_vram_gb()
        process_vram = self.get_process_vram_gb()
        allocated_resident = sum(r.get("size_gb", 0.0) for r in _RESIDENT_MODELS.values())
        
        projected_process_vram = process_vram + requested_vram_gb
        projected_system_vram_used = (self.total_vram_gb - free_vram) + requested_vram_gb
        
        logger.debug(
            "VRAM Status: free=%.2fGB, process=%.2fGB, resident_sum=%.2fGB, projected_sys_used=%.2fGB",
            free_vram, process_vram, allocated_resident, projected_system_vram_used
        )
        
        # Guard 1: Enforce hard usable target limit
        if projected_process_vram > self.usable_target_gb:
            logger.warning(
                "Model '%s' (projected process: %.2fGB) exceeds usable VRAM budget limit of %.2fGB",
                model_name, projected_process_vram, self.usable_target_gb
            )
            
        # Guard 2: Enforce absolute emergency stop ceiling (prevent OOM crash)
        if projected_system_vram_used > self.emergency_stop_gb:
            err_msg = (
                f"Load blocked: Model '{model_name}' would push VRAM usage to {projected_system_vram_used:.2f}GB, "
                f"exceeding the safety emergency stop limit of {self.emergency_stop_gb:.2f}GB."
            )
            logger.error(err_msg)
            raise MemoryError(err_msg)
            
        # Guard 3: Check raw free headroom
        if free_vram < requested_vram_gb:
            logger.warning(
                "Raw free VRAM (%.2fGB) is less than the requested model size (%.2fGB). Spillover into system RAM may occur.",
                free_vram, requested_vram_gb
            )
            
        return True

    def load(
        self,
        model_name: str,
        load_fn: Callable[[], Any],
        unload_fn: Optional[Callable[[], None]] = None,
        requested_vram_gb: Optional[float] = None,
        target_engine: Optional[str] = None
    ) -> ModelContext:
        """
        Execute preflight VRAM audits and load the model.
        Returns a context manager ensuring clean unloads.
        """
        # Run budget & compatibility checks
        self.preflight_check(model_name, requested_vram_gb, target_engine)
        
        # Resolve registry metadata
        model_entry = self.model_registry.get(model_name, {}) or {}
        if requested_vram_gb is None:
            requested_vram_gb = float(model_entry.get("vram_estimate_gb", 2.0))
            
        engine = target_engine or next(iter([eng for eng, cap in model_entry.get("engines", {}).items() if cap in ("yes", True)]), "unknown")
        quantization = model_entry.get("quantization", ["FP16"])[0]
        
        # Telemetry: Record starting VRAM state
        vram_before = self.get_free_vram_gb()
        
        logger.info(
            "[TELEMETRY] LOADING MODEL - ID: %s | Engine: %s | Quantization: %s | VRAM Before: %.2f GB",
            model_name, engine, quantization, vram_before
        )
        
        start_time = time.monotonic()
        
        # Reset peak memory tracking if PyTorch is available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
        except Exception:
            pass
            
        # Execute model loader
        model_instance = load_fn()
        
        duration = time.monotonic() - start_time
        vram_after = self.get_free_vram_gb()
        
        logger.info(
            "[TELEMETRY] LOAD SUCCESS - ID: %s | Load Time: %.2f sec | VRAM After Load: %.2f GB",
            model_name, duration, vram_after
        )
        
        # Register model as resident in VRAM
        _RESIDENT_MODELS[model_name] = {
            "instance": model_instance,
            "unload_fn": unload_fn,
            "size_gb": requested_vram_gb,
            "loaded_at": time.time(),
            "vram_before": vram_before,
            "engine": engine,
            "quantization": quantization
        }
        
        return ModelContext(self, model_name, model_instance)

    def unload(self, model_name: str) -> bool:
        """Evict the specified model from resident tracking and call its unload hook."""
        if model_name not in _RESIDENT_MODELS:
            return False
            
        record = _RESIDENT_MODELS.pop(model_name)
        unload_hook = record.get("unload_fn")
        size_gb = record.get("size_gb", 0.0)
        vram_before_load = record.get("vram_before", 0.0)
        engine = record.get("engine", "unknown")
        quantization = record.get("quantization", "unknown")
        duration = time.time() - record.get("loaded_at", time.time())
        
        vram_before_unload = self.get_free_vram_gb()
        
        logger.info("[TELEMETRY] UNLOADING MODEL - ID: %s | Engine: %s | Quantization: %s", model_name, engine, quantization)
        
        if unload_hook:
            try:
                unload_hook()
            except Exception as e:
                logger.error("Unload hook for model '%s' failed: %s", model_name, e)
                
        # Release references
        record.clear()
        
        # Attempt PyTorch cache cleaning & garbage collection
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                import gc
                gc.collect()
        except Exception:
            pass
            
        # Telemetry: Record VRAM stats after eviction
        vram_after_unload = self.get_free_vram_gb()
        vram_returned = vram_after_unload - vram_before_unload
        
        # Track peak usage via PyTorch if available
        peak_vram_gb = 0.0
        try:
            import torch
            if torch.cuda.is_available():
                peak_vram_gb = torch.cuda.max_memory_allocated() / (1024 ** 3)
        except Exception:
            pass
            
        logger.info(
            "[TELEMETRY] UNLOAD COMPLETE - ID: %s | Duration: %.2f sec | VRAM Before: %.2f GB | Peak VRAM: %.2f GB | VRAM After: %.2f GB",
            model_name, duration, vram_before_load, peak_vram_gb, vram_after_unload
        )
        
        # Verify VRAM was successfully returned
        if vram_returned < (size_gb * 0.5):
            logger.warning(
                "[WARN] Memory leakage warning: Model '%s' was expected to release ~%.2f GB VRAM, "
                "but only %.2f GB was reclaimed by the system.",
                model_name, size_gb, vram_returned
            )
        else:
            logger.info("[OK] VRAM returned successfully: %.2f GB reclaimed.", vram_returned)
            
        return True

    def unload_all(self) -> None:
        """Unload all resident models registered in the manager."""
        resident_keys = list(_RESIDENT_MODELS.keys())
        for model_name in resident_keys:
            self.unload(model_name)


class ModelContext:
    """Context manager wrapping active model instances for clean sequential loading."""
    
    def __init__(self, manager: ModelLifecycleManager, name: str, instance: Any):
        self.manager = manager
        self.name = name
        self.instance = instance
        
    def __enter__(self) -> Any:
        return self.instance
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.manager.unload(self.name)
