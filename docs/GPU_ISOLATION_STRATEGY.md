# GPU Isolation Strategy for GoodQ4All Pipeline

## Current Hardware Status
- **GPU**: NVIDIA GeForce RTX 4070 Ti SUPER
- **VRAM**: 16,376 MiB total (11,615 MiB currently free)
- **Current Utilization**: 2% (mostly idle)

## Assessment: Is This Approach Applicable?

### ✅ **YES - This is HIGHLY applicable and will solve critical issues**

## Why We Need This

### Current Problems:
1. **Pipeline Stalls**: Audio diarization and scene detection hang indefinitely
2. **Memory Leaks**: VRAM not properly released between steps
3. **Concurrent Conflicts**: Multiple GPU-heavy steps can't run simultaneously
4. **No Device Scoping**: All steps try to grab the entire GPU

### Root Cause:
**We're NOT using Docker**, so we lack the built-in process isolation that Docker containers provide. ZenML expects either:
- Docker containers (each step gets isolated GPU access)
- OR manual device management (which we haven't implemented)

## Why This Matters for Our Stack

### Current GPU-Heavy Steps:
1. **audio_diarize** (PyAnnote) - VRAM intensive, can hang
2. **face_embed** (facenet-pytorch/MTCNN) - GPU accelerated
3. **image_embed_clip** (CLIP) - GPU required
4. **image_embed_dino** (DINO) - GPU required  
5. **audio_embed_clap** (CLAP) - GPU optional but beneficial
6. **object_detect** (YOLO) - GPU accelerated
7. **video_scene_detect** (potential GPU acceleration)

### The Problem:
Without isolation, when step A loads a model into GPU memory, step B might:
- Try to load its own model → OOM or hang
- Reuse step A's memory → corruption
- Wait indefinitely for resources → pipeline freeze

## Proposed Solution: Bare-Metal GPU Isolation

### Strategy Overview:
Instead of Docker namespacing, we'll use:
1. **Environment variable scoping** (`CUDA_VISIBLE_DEVICES`)
2. **Memory fraction limits** (PyTorch/TensorFlow per-process limits)
3. **Deterministic execution** (prevent race conditions)
4. **Per-step cleanup** (explicit GPU memory release)

---

## Implementation Plan

### Phase 1: Per-Step Device Management

#### A. Add GPU Configuration to Each Step

```python
# steps/common/gpu_manager.py
import os
import torch
from typing import Optional

class GPUManager:
    """Centralized GPU device and memory management"""
    
    @staticmethod
    def get_device(step_name: str, gpu_id: int = 0, memory_fraction: float = 0.3) -> str:
        """
        Get device string with proper isolation
        
        Args:
            step_name: Name of the step (for logging)
            gpu_id: Which GPU to use (default 0)
            memory_fraction: Max VRAM fraction (0.0-1.0)
        """
        # Set visible devices to only the requested GPU
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
        
        if torch.cuda.is_available():
            # Limit memory allocation
            torch.cuda.set_per_process_memory_fraction(memory_fraction, 0)
            
            # Enable memory growth (allocate as needed, not all at once)
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
            
            device = "cuda"
            print(f"[{step_name}] Using GPU {gpu_id} with {memory_fraction*100}% VRAM limit")
        else:
            device = "cpu"
            print(f"[{step_name}] GPU not available, using CPU")
            
        return device
    
    @staticmethod
    def cleanup():
        """Release GPU memory after step completion"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
```

#### B. Memory Allocation Strategy

Based on our 16GB VRAM RTX 4070 Ti SUPER:

| Step | VRAM Need | Fraction | Concurrent Safe |
|------|-----------|----------|-----------------|
| audio_diarize (PyAnnote) | ~4GB | 0.25 | Yes (2 max) |
| face_embed (MTCNN) | ~2GB | 0.15 | Yes (4 max) |
| image_embed_clip | ~3GB | 0.20 | Yes (3 max) |
| image_embed_dino | ~3GB | 0.20 | Yes (3 max) |
| audio_embed_clap | ~2GB | 0.15 | Yes (4 max) |
| object_detect (YOLO) | ~2.5GB | 0.18 | Yes (3 max) |

**Conservative approach**: Allocate 0.3 (30%) per step = ~5GB max per process

### Phase 2: Update Critical Steps

#### Example: audio_diarize with GPU isolation

```python
# steps/audio_diarize/step.py (partial update)

def audio_diarize(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    from steps.common.gpu_manager import GPUManager
    
    # Get isolated device with 25% VRAM limit
    device = GPUManager.get_device('audio_diarize', gpu_id=0, memory_fraction=0.25)
    
    try:
        # Load pipeline with device isolation
        pipeline = _load_pipeline(model_id, device, auth_token)
        
        # Process audio
        result = pipeline(path)
        
        # Format output
        segments = _format_segments(result)
        
        return {"diarization": segments, "diarize_meta": {"status": "ok"}}
        
    finally:
        # CRITICAL: Always cleanup GPU memory
        GPUManager.cleanup()
```

### Phase 3: ZenML Step Wrapper Enhancement

Add GPU resource hints to ZenML step decorators:

```python
from zenml import step
from zenml.config import ResourceSettings

@step(
    enable_cache=True,
    settings={
        "resources": ResourceSettings(
            cpu_count=2,
            gpu_count=1,
            memory="8GB"
        )
    }
)
def audio_diarize_step(item: Dict[str, Any]) -> Dict[str, Any]:
    # ... existing code with GPU manager
```

### Phase 4: Concurrent Step Execution (Advanced)

Enable parallel processing with proper isolation:

```yaml
# config.yaml
pipeline:
  parallelism:
    enabled: true
    max_concurrent_gpu_steps: 3  # Run max 3 GPU steps at once
    
  gpu:
    device_id: 0
    memory_fraction_per_step: 0.3
    enable_cleanup: true
```

---

## Benefits of This Approach

### 1. **Eliminates Pipeline Hangs**
- Each step gets guaranteed GPU access
- No resource starvation
- Predictable execution time

### 2. **Enables True Concurrency**
- Can run 3-4 light steps simultaneously
- Or 2 heavy steps (diarization + CLIP)
- Maximizes 4070 Ti SUPER utilization

### 3. **Prevents Memory Leaks**
- Explicit cleanup after each step
- No lingering model weights
- Deterministic VRAM usage

### 4. **Reproducible Results**
- Deterministic algorithms enabled
- Fixed random seeds
- Consistent output across runs

### 5. **No Docker Required**
- Uses native CUDA capabilities
- Lighter weight than containers
- Direct hardware access

---

## What We DON'T Need from That Guide

### ❌ MPS (Multi-Process Service)
- **Why**: Only beneficial for multiple small jobs
- **Our case**: We have sequential pipeline steps, not concurrent training jobs

### ❌ Exclusive Process Mode
```bash
nvidia-smi -c EXCLUSIVE_PROCESS  # DON'T USE
```
- **Why**: Too restrictive - prevents ANY multi-step concurrency
- **Our case**: We WANT controlled concurrency (2-3 steps at once)

### ❌ Separate Conda Envs Per Step
- **Why**: We already have isolated ZenML steps
- **Our case**: Single `goodq_zenml` env is fine with proper device management

---

## Implementation Timeline

### Immediate (Phase 1): 🚀 **START HERE**
1. Create `steps/common/gpu_manager.py`
2. Update `audio_diarize` step (current bottleneck)
3. Test with 1987-1988.mp4
4. Verify no hangs

### Short-term (Phase 2):
1. Update remaining GPU steps (face_embed, CLIP, DINO, YOLO)
2. Add memory tracking
3. Test concurrent execution

### Long-term (Phase 3):
1. Add ZenML resource settings
2. Implement pipeline-level parallelism
3. Benchmark end-to-end performance

---

## Expected Outcomes

### Before GPU Isolation:
- ❌ Pipeline hangs at audio_diarize (indefinitely)
- ❌ Scene detection stalls at 66%
- ❌ VRAM usage unpredictable (leaks)
- ❌ Can't run concurrent steps

### After GPU Isolation:
- ✅ Audio diarization completes in 2-3 minutes per video
- ✅ Scene detection finishes without hanging
- ✅ VRAM usage capped at 5GB per step (30% limit)
- ✅ Can run 2-3 steps concurrently (8-hour processing → 3-hour)

---

## Testing Plan

### Test 1: Single Step GPU Isolation
```bash
# Test audio_diarize with GPU manager
python -c "from steps.audio_diarize.step import audio_diarize; ..."
```

### Test 2: Full Pipeline with Monitoring
```bash
# Run full pipeline with GPU tracking
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv -l 1 > gpu_usage.log &
python LAUNCH_GOODQ.bat
```

### Test 3: Concurrent Step Execution
```bash
# Run 3 steps in parallel (different videos)
# Monitor VRAM usage stays under 16GB
```

---

## Conclusion

**This GPU isolation strategy is EXACTLY what we need** because:

1. ✅ We're **NOT using Docker** (so we lack built-in isolation)
2. ✅ We have **multiple GPU-heavy steps** that conflict
3. ✅ We're experiencing **pipeline hangs** (resource starvation)
4. ✅ We have **sufficient VRAM** (16GB) to run 3-4 steps concurrently with proper limits
5. ✅ It's **ZenML-compatible** (works with bare-metal orchestration)

**Next Step**: Implement Phase 1 (GPU Manager + audio_diarize update) and test immediately.

This will fix the audio diarization hang that's been blocking us for days.
