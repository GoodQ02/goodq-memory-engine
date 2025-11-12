"""
Audio Pipeline GPU Optimization
Specialized GPU management for audio processing (diarization & transcription)
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioGPUConfig:
    """Configuration for audio GPU processing"""
    device: str  # "cuda" or "cpu"
    memory_fraction: float  # Fraction of GPU memory to use
    batch_size: int  # Optimal batch size for this GPU
    compute_type: str  # "float16", "int8", etc.
    use_flash_attention: bool  # Enable flash attention if available
    num_streams: int  # Number of CUDA streams for parallel processing


class AudioGPUOptimizer:
    """
    Intelligent GPU optimization for audio processing.
    Monitors GPU usage and automatically adjusts memory allocation.
    """
    
    def __init__(self):
        self.device = self._detect_device()
        self.torch = None
        self._initialized = False
        self._warmup_complete = False
        
        # Performance tracking
        self.processing_times = []
        self.memory_peaks = []
        self.throughput_samples = []
        
        logger.info(f"[AudioGPU] Detected device: {self.device}")
    
    def _detect_device(self) -> str:
        """Detect best available device"""
        try:
            import torch
            self.torch = torch
            
            if torch.cuda.is_available():
                # Check GPU memory
                total_memory = torch.cuda.get_device_properties(0).total_memory
                total_gb = total_memory / (1024 ** 3)
                
                logger.info(f"[AudioGPU] CUDA available: {torch.cuda.get_device_name(0)}")
                logger.info(f"[AudioGPU] Total VRAM: {total_gb:.1f} GB")
                
                return "cuda"
            else:
                logger.warning("[AudioGPU] CUDA not available, using CPU")
                return "cpu"
        except ImportError:
            logger.warning("[AudioGPU] PyTorch not available, using CPU")
            return "cpu"
    
    def configure_for_diarization(self, duration_minutes: float = None) -> AudioGPUConfig:
        """
        Configure GPU for speaker diarization.
        
        PyAnnote audio models are VRAM-hungry:
        - Base model: ~2-3GB
        - With embeddings: ~3-4GB
        - Peak during processing: ~4-6GB
        
        Strategy:
        - Short audio (<10min): Use 40% VRAM, process whole file
        - Medium audio (10-30min): Use 35% VRAM, chunk if needed
        - Long audio (>30min): Use 30% VRAM, aggressive chunking
        """
        
        if self.device != "cuda":
            return AudioGPUConfig(
                device="cpu",
                memory_fraction=0.0,
                batch_size=1,
                compute_type="float32",
                use_flash_attention=False,
                num_streams=1
            )
        
        # Dynamic memory allocation based on audio duration
        if duration_minutes is None or duration_minutes < 10:
            memory_fraction = 0.40  # 40% for short audio
            logger.info("[AudioGPU] Diarization config: SHORT audio (40% VRAM)")
        elif duration_minutes < 30:
            memory_fraction = 0.35  # 35% for medium audio
            logger.info(f"[AudioGPU] Diarization config: MEDIUM audio ({duration_minutes:.1f}min, 35% VRAM)")
        else:
            memory_fraction = 0.30  # 30% for long audio
            logger.info(f"[AudioGPU] Diarization config: LONG audio ({duration_minutes:.1f}min, 30% VRAM)")
        
        # Apply memory limit
        self._apply_memory_fraction(memory_fraction)
        
        return AudioGPUConfig(
            device="cuda",
            memory_fraction=memory_fraction,
            batch_size=1,  # PyAnnote processes one file at a time
            compute_type="float16",
            use_flash_attention=False,  # Not supported by PyAnnote yet
            num_streams=1
        )
    
    def configure_for_transcription(self, duration_minutes: float = None) -> AudioGPUConfig:
        """
        Configure GPU for Whisper transcription.
        
        Whisper models VRAM usage:
        - tiny: ~1GB
        - base: ~1GB
        - small: ~2GB
        - medium: ~5GB (our default)
        - large: ~10GB
        
        Strategy:
        - Use 25-30% VRAM for medium model
        - Enable flash attention for speed
        - Use FP16 for 2x speed improvement
        - Batch processing where possible
        """
        
        if self.device != "cuda":
            return AudioGPUConfig(
                device="cpu",
                memory_fraction=0.0,
                batch_size=1,
                compute_type="int8",
                use_flash_attention=False,
                num_streams=1
            )
        
        # Whisper is more memory-efficient than PyAnnote
        memory_fraction = 0.28  # 28% is safe for medium model
        
        logger.info(f"[AudioGPU] Transcription config: medium model (28% VRAM)")
        
        # Apply memory limit
        self._apply_memory_fraction(memory_fraction)
        
        # Check if flash attention is available
        use_flash_attention = self._check_flash_attention()
        
        return AudioGPUConfig(
            device="cuda",
            memory_fraction=memory_fraction,
            batch_size=4,  # Process 4 chunks in parallel
            compute_type="float16",  # FP16 for 2x speedup
            use_flash_attention=use_flash_attention,
            num_streams=2  # Overlap processing with data transfer
        )
    
    def _apply_memory_fraction(self, fraction: float):
        """Apply memory fraction limit to GPU"""
        if self.torch and self.device == "cuda":
            try:
                self.torch.cuda.set_per_process_memory_fraction(fraction, 0)
                logger.info(f"[AudioGPU] Set memory fraction to {fraction*100:.0f}%")
                
                # Enable memory efficiency features
                self.torch.backends.cudnn.benchmark = True
                logger.info("[AudioGPU] Enabled cuDNN benchmark mode")
                
            except Exception as e:
                logger.warning(f"[AudioGPU] Failed to set memory fraction: {e}")
    
    def _check_flash_attention(self) -> bool:
        """Check if flash attention is available"""
        try:
            # Try importing flash attention
            import flash_attn
            logger.info("[AudioGPU] Flash attention available")
            return True
        except ImportError:
            logger.debug("[AudioGPU] Flash attention not available")
            return False
    
    def warmup_gpu(self):
        """
        Warmup GPU with small operations to initialize CUDA kernels.
        This prevents first-run latency in actual processing.
        """
        if self._warmup_complete or self.device != "cuda":
            return
        
        if not self.torch:
            return
        
        try:
            logger.info("[AudioGPU] Warming up GPU...")
            start = time.time()
            
            # Small tensor operations to initialize CUDA
            x = self.torch.randn(1000, 1000, device="cuda")
            y = self.torch.randn(1000, 1000, device="cuda")
            z = self.torch.matmul(x, y)
            
            # Synchronize to ensure operations complete
            self.torch.cuda.synchronize()
            
            elapsed = time.time() - start
            logger.info(f"[AudioGPU] Warmup complete in {elapsed:.2f}s")
            
            self._warmup_complete = True
            
        except Exception as e:
            logger.warning(f"[AudioGPU] Warmup failed: {e}")
    
    def clear_cache(self):
        """Clear GPU cache to free memory"""
        if self.torch and self.device == "cuda":
            try:
                self.torch.cuda.empty_cache()
                self.torch.cuda.synchronize()
                logger.debug("[AudioGPU] Cache cleared")
            except Exception as e:
                logger.warning(f"[AudioGPU] Cache clear failed: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current GPU memory statistics"""
        if not self.torch or self.device != "cuda":
            return {"device": "cpu", "available": False}
        
        try:
            allocated = self.torch.cuda.memory_allocated(0) / (1024 ** 3)
            reserved = self.torch.cuda.memory_reserved(0) / (1024 ** 3)
            total = self.torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            
            return {
                "device": "cuda",
                "available": True,
                "allocated_gb": allocated,
                "reserved_gb": reserved,
                "total_gb": total,
                "free_gb": total - allocated,
                "utilization": (allocated / total) * 100 if total > 0 else 0
            }
        except Exception as e:
            logger.warning(f"[AudioGPU] Failed to get memory stats: {e}")
            return {"device": "cuda", "available": False, "error": str(e)}
    
    def print_memory_stats(self):
        """Print current GPU memory statistics"""
        stats = self.get_memory_stats()
        
        if stats.get("available"):
            logger.info(f"[AudioGPU] Memory: {stats['allocated_gb']:.2f}GB / {stats['total_gb']:.2f}GB "
                       f"({stats['utilization']:.1f}% used)")
        else:
            logger.info(f"[AudioGPU] Device: {stats['device']}")
    
    def record_performance(self, step_name: str, duration_seconds: float, 
                          audio_duration_seconds: float, memory_peak_gb: float = None):
        """Record performance metrics for analysis"""
        
        realtime_factor = audio_duration_seconds / duration_seconds if duration_seconds > 0 else 0
        
        sample = {
            "step": step_name,
            "timestamp": time.time(),
            "processing_time": duration_seconds,
            "audio_duration": audio_duration_seconds,
            "realtime_factor": realtime_factor,
            "memory_peak_gb": memory_peak_gb or self.get_memory_stats().get("allocated_gb", 0)
        }
        
        self.processing_times.append(sample)
        
        if memory_peak_gb:
            self.memory_peaks.append(memory_peak_gb)
        
        logger.info(f"[AudioGPU] Performance: {step_name} processed {audio_duration_seconds:.1f}s audio "
                   f"in {duration_seconds:.1f}s ({realtime_factor:.2f}x realtime)")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        if not self.processing_times:
            return {"status": "no_data"}
        
        # Calculate averages
        avg_realtime = sum(s["realtime_factor"] for s in self.processing_times) / len(self.processing_times)
        avg_memory = sum(self.memory_peaks) / len(self.memory_peaks) if self.memory_peaks else 0
        
        # Group by step
        by_step = {}
        for sample in self.processing_times:
            step = sample["step"]
            if step not in by_step:
                by_step[step] = []
            by_step[step].append(sample)
        
        step_stats = {}
        for step, samples in by_step.items():
            avg_rt = sum(s["realtime_factor"] for s in samples) / len(samples)
            step_stats[step] = {
                "count": len(samples),
                "avg_realtime_factor": avg_rt,
                "avg_processing_time": sum(s["processing_time"] for s in samples) / len(samples)
            }
        
        return {
            "status": "ok",
            "total_samples": len(self.processing_times),
            "overall_avg_realtime_factor": avg_realtime,
            "overall_avg_memory_gb": avg_memory,
            "by_step": step_stats,
            "device": self.device
        }
    
    def optimize_for_next_run(self) -> Dict[str, float]:
        """
        Analyze performance and suggest optimized memory fractions.
        
        Returns recommended memory fractions for each step.
        """
        report = self.get_performance_report()
        
        if report.get("status") != "ok":
            return {}
        
        suggestions = {}
        
        # If we're running well below memory capacity, can increase allocation
        # If we're hitting limits, should decrease
        
        avg_mem = report.get("overall_avg_memory_gb", 0)
        total_mem = self.get_memory_stats().get("total_gb", 0)
        
        if total_mem > 0:
            utilization = avg_mem / total_mem
            
            if utilization < 0.5:
                # Underutilizing GPU, can increase allocation
                suggestions["recommendation"] = "increase"
                suggestions["diarization"] = 0.45
                suggestions["transcription"] = 0.35
                logger.info("[AudioGPU] GPU underutilized, increasing allocation recommended")
                
            elif utilization > 0.85:
                # Near capacity, decrease allocation
                suggestions["recommendation"] = "decrease"
                suggestions["diarization"] = 0.25
                suggestions["transcription"] = 0.20
                logger.warning("[AudioGPU] GPU near capacity, decreasing allocation recommended")
                
            else:
                # Good balance
                suggestions["recommendation"] = "maintain"
                suggestions["diarization"] = 0.35
                suggestions["transcription"] = 0.28
                logger.info("[AudioGPU] GPU utilization optimal")
        
        return suggestions


# Global optimizer instance
_audio_gpu_optimizer = None


def get_audio_gpu_optimizer() -> AudioGPUOptimizer:
    """Get singleton audio GPU optimizer"""
    global _audio_gpu_optimizer
    
    if _audio_gpu_optimizer is None:
        _audio_gpu_optimizer = AudioGPUOptimizer()
    
    return _audio_gpu_optimizer
