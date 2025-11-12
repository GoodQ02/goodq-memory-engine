# GPU Pipeline Optimization Guide

## Overview

The GoodQ4All pipeline has been fully optimized for GPU acceleration. This guide explains the GPU configuration system and how to optimize performance.

## System Configuration

### Hardware Detected
- **GPU**: NVIDIA GeForce RTX 4070 Ti SUPER
- **VRAM**: 16 GB
- **CUDA**: Version 13.0
- **Compute Capability**: 8.9

### Enabled Optimizations
- ✅ TF32 precision (faster matrix operations on Ampere+ GPUs)
- ✅ cuDNN auto-tuner (optimal algorithm selection)
- ✅ Asynchronous kernel launches
- ✅ Per-step memory allocation limits

## GPU Memory Allocation Strategy

Each pipeline step is assigned a specific fraction of total VRAM to prevent out-of-memory errors while maximizing throughput:

| Step | VRAM Allocation | Typical Usage | Notes |
|------|----------------|---------------|-------|
| `video_scene_detect` | 15% (2.4 GB) | Low | OpenCV-based, minimal GPU use |
| `audio_transcribe` | 25% (4.0 GB) | Medium | Whisper medium model |
| `audio_diarize` | 35% (5.6 GB) | High | PyAnnote + speaker embeddings |
| `face_embed` | 20% (3.2 GB) | Medium | FaceNet embeddings |
| `emotion_classify` | 20% (3.2 GB) | Medium | Emotion CNN model |
| `text_embed` | 15% (2.4 GB) | Low | Sentence transformers |
| `image_embed_clip` | 25% (4.0 GB) | Medium | CLIP ViT model |
| `image_embed_dino` | 25% (4.0 GB) | Medium | DINOv2 model |
| `object_detect` | 25% (4.0 GB) | Medium | YOLO detection |
| `object_track_yolo` | 25% (4.0 GB) | Medium | YOLO tracking |
| `image_caption` | 20% (3.2 GB) | Medium | Image captioning model |
| `audio_embed_clap` | 20% (3.2 GB) | Medium | CLAP audio embeddings |
| `audio_emotion` | 15% (2.4 GB) | Low | Audio emotion model |
| `image_ocr` | 15% (2.4 GB) | Low | OCR model |
| `llm_chat` | 40% (6.4 GB) | High | Local LLM (if used) |

## How It Works

### Automatic Configuration

Every GPU-enabled pipeline step automatically imports and configures GPU settings:

```python
# At the top of each step file
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats
```

When a step starts, it:
1. Detects which step is running
2. Sets GPU device to `CUDA:0`
3. Allocates the appropriate VRAM fraction
4. Enables performance optimizations (TF32, cuDNN)
5. Clears any cached memory

### Manual Configuration

You can also manually configure GPU for custom scripts:

```python
from steps.common.gpu_config import configure_gpu, get_device

# Use default allocation for detected step
config = configure_gpu()

# Override with specific allocation
config = configure_gpu("my_step", force_fraction=0.30)

# Get the torch device
device = get_device()  # Returns torch.device("cuda:0") or torch.device("cpu")

# Use in your model
model = MyModel().to(device)
```

## Running Optimization Tests

### Quick Test
Test GPU configuration without running full pipeline:

```bash
conda activate goodq_zenml
python scripts\test_gpu_config.py
```

### Full Monitoring
Run pipeline with real-time GPU monitoring:

```bash
conda activate goodq_zenml
python scripts\monitor_gpu_pipeline.py
```

This will:
- Start the pipeline
- Monitor GPU usage every 2 seconds
- Detect which step is running
- Generate detailed usage report

### Automated Optimization
Run comprehensive multi-iteration optimization:

```bash
RUN_GPU_OPTIMIZATION.bat
```

This will:
1. Verify GPU availability
2. Run multiple pipeline iterations
3. Monitor GPU usage for each step
4. Analyze performance patterns
5. Adjust memory allocations
6. Validate optimizations
7. Generate comprehensive report

## Interpreting Results

### GPU Usage Report

After optimization, you'll get a report like:

```
Step: audio_diarize
Duration: 45.3s
Samples: 23

Memory Usage:
  Average: 4200 MB (26.3%)
  Peak:    5100 MB (31.9%)

GPU Utilization:
  Average: 78.5%
  Peak:    95%

Temperature:
  Average: 62.3°C
  Peak:    68°C

Power Draw:
  Average: 180.5W
  Peak:    245.2W
```

### Optimization Recommendations

The system will suggest adjustments:

- **REDUCE**: Using <60% of allocated memory → can lower allocation
- **INCREASE**: Using >90% of allocated memory → should raise allocation
- **OPTIMAL**: Using 60-90% of allocated memory → no change needed

## Troubleshooting

### Out of Memory Errors

If you see CUDA out-of-memory errors:

1. Check which step failed
2. Reduce its allocation in `steps/common/gpu_config.py`
3. Run optimization again

### Low GPU Utilization

If GPU usage is consistently low (<30%):

- CPU bottleneck: Increase data loading workers
- I/O bottleneck: Use faster storage or increase buffer sizes
- Model too small: GPU is faster than data can be fed

### High Temperature

If GPU temperature exceeds 80°C:

- Improve case ventilation
- Check GPU fans are working
- Reduce clock speeds if needed
- Consider undervolting

## Environment Variables

Control GPU behavior with environment variables:

```bash
# Disable auto GPU configuration
set GOODQ_NO_AUTO_GPU=1

# Force specific GPU device
set CUDA_VISIBLE_DEVICES=0

# Enable deterministic mode (slower but reproducible)
set CUBLAS_WORKSPACE_CONFIG=:4096:8
```

## Advanced: Multi-GPU Support

If you have multiple GPUs, you can distribute steps:

```python
# In gpu_config.py, modify GPU_CONFIGS:
GPU_CONFIGS = {
    "audio_diarize": {"fraction": 0.35, "device": "0"},
    "face_embed": {"fraction": 0.20, "device": "1"},  # Use second GPU
    # ...
}
```

## Performance Tips

### 1. Batch Processing
Process multiple small files instead of one large file for better GPU utilization.

### 2. Concurrent Steps
If using multiple GPUs, run independent steps concurrently.

### 3. Memory Management
Call `clear_cache()` between heavy operations to free VRAM.

### 4. Precision Trade-offs
- FP16 (half precision): 2x faster, half memory, slight accuracy loss
- TF32 (tensor float 32): 1.5x faster, same memory, minimal accuracy loss ✅ Enabled
- FP32 (full precision): Baseline

### 5. Profile First
Always profile before optimizing. The bottleneck might not be GPU!

## Monitoring in Production

### Real-time Monitoring
Use `nvidia-smi` to watch GPU during production:

```bash
# Update every 1 second
nvidia-smi -l 1

# Watch specific metrics
nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv -l 1
```

### Logging GPU Stats
The system logs GPU stats to:
- `logs/gpu_optimization/monitor_report_*.json` (detailed per-run reports)
- Console output during pipeline execution

## Files and Scripts

### Core Files
- `steps/common/gpu_config.py` - Main GPU configuration module
- `config/gpu_optimized.json` - Optimized allocation settings

### Optimization Scripts
- `scripts/test_gpu_config.py` - Quick GPU test
- `scripts/monitor_gpu_pipeline.py` - Real-time monitoring
- `scripts/gpu_pipeline_optimizer.py` - Optimization algorithms
- `scripts/run_gpu_optimization_tests.py` - Multi-iteration testing
- `scripts/gpu_config_injector.py` - Inject GPU config into steps

### Batch Files
- `RUN_GPU_OPTIMIZATION.bat` - Full optimization suite

## Best Practices

1. **Start Conservative**: Begin with lower allocations and increase if needed
2. **Monitor First Run**: Always monitor the first run of a new video type
3. **Test After Changes**: Re-run optimization after model or code changes
4. **Keep Drivers Updated**: Latest NVIDIA drivers often improve performance
5. **Clean Cache Regularly**: Old cached data can fragment memory

## FAQ

**Q: Why not use 100% VRAM for each step?**
A: PyTorch needs headroom for temporary allocations. 100% often causes OOM errors.

**Q: Can I run multiple pipelines simultaneously?**
A: Not recommended on single GPU. Steps will compete for VRAM. Use multiple GPUs or sequential processing.

**Q: Does this work on AMD GPUs?**
A: No, this is CUDA/NVIDIA specific. AMD would need ROCm configuration.

**Q: Will this work in Docker?**
A: Yes, but you need `nvidia-docker` runtime and must pass `--gpus all` flag.

**Q: How do I know if optimization worked?**
A: Compare before/after:
- Processing time should decrease
- GPU utilization should increase
- No out-of-memory errors

## Support

For issues or questions:
1. Check logs in `logs/gpu_optimization/`
2. Review GPU stats with `nvidia-smi`
3. Verify step configurations in `steps/common/gpu_config.py`
4. Run `python scripts/test_gpu_config.py` to verify setup

## Version History

- **v1.0** (2025-11-12): Initial GPU optimization system
  - Auto-configuration for all GPU steps
  - Real-time monitoring
  - Comprehensive optimization suite
  - Production-ready defaults
