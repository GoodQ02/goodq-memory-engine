<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GPU Management Quick Start Guide

## Overview
The GoodQ pipeline now includes automatic GPU resource management. This guide shows you how to use it.

## Zero Configuration Required
**The system works out of the box!** GPU management is automatically enabled when you run the pipeline.

## How It Works

### Automatic Features
1. **GPU Detection**: Automatically detects and uses your NVIDIA GPU
2. **Memory Management**: Each step gets a pre-configured memory limit
3. **Cache Clearing**: GPU memory cleared before/after each step
4. **Fallback**: Automatically uses CPU if GPU unavailable

### What Happens Behind the Scenes
```
[Your video] → Watchdog → Pipeline
                              ↓
                    For each step:
                    1. Initialize GPU (if available)
                    2. Allocate memory fraction
                    3. Clear cache
                    4. Run step
                    5. Clear cache again
                    6. Log stats
```

## Quick Commands

### Check GPU Status
```bash
python common/gpu_monitor.py --check-only
```

### Run All Tests
```bash
python test_gpu_management.py
```

### Monitor GPU During Processing
```bash
# In one terminal
python common/gpu_monitor.py --interval 5

# In another terminal  
# Run your pipeline normally
```

### View GPU Process List
```bash
nvidia-smi
```

## Configuration (Optional)

### Adjust Memory for Specific Steps

Edit `config/gpu_config.yaml`:

```yaml
step_memory_fractions:
  # Increase memory for heavy step
  image_embed_clip: 0.8  # Was 0.7, now 80%
  
  # Decrease for lighter step
  sentiment: 0.2  # Was 0.3, now 20%
```

### Enable Logging
```yaml
memory:
  log_memory_stats: true  # Log GPU memory usage
```

### Enable Deterministic Mode (for reproducibility)
```yaml
gpu:
  deterministic: true  # Makes runs reproducible (slower)
```

## Troubleshooting

### GPU Not Detected
**Check**: Is CUDA installed?
```bash
nvidia-smi
```

**Check**: Does PyTorch see GPU?
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

### Out of Memory Errors
**Solution**: Reduce memory fractions in `config/gpu_config.yaml`

```yaml
step_memory_fractions:
  # Reduce all by 20%
  image_embed_clip: 0.5  # Was 0.7
  image_embed_dino: 0.5  # Was 0.7
  default: 0.3           # Was 0.5
```

### Step Running on CPU Instead of GPU
**Check**: Is the conda environment active?
```bash
conda info --envs
# Should show (goodq_core) as active
```

**Check**: Are environment variables set?
```bash
echo $env:CUDA_VISIBLE_DEVICES  # Should be "0"
```

### Multiple Processes Fighting for GPU
**Solution**: The system prevents this by default. But if needed:

1. Stop all processes
2. Check what's running:
   ```bash
   nvidia-smi
   ```
3. Restart only what you need

## Understanding Memory Fractions

### What They Mean
- **0.3 (30%)**: Light models, minimal VRAM needed
- **0.5 (50%)**: Medium models, balanced usage
- **0.7 (70%)**: Heavy models, large embeddings
- **0.8 (80%)**: Very heavy models, maximum allocation

### Current Settings (17GB GPU)
```
Heavy Models (70%):  ~12 GB
  - CLIP embeddings
  - DINO embeddings

Medium Models (60%):  ~10 GB
  - Scene detection
  - Object detection
  - Image captioning
  - Face embedding

Light Models (30-40%):  ~5-7 GB
  - Text embedding
  - Sentiment analysis
  - Audio processing
```

### For Smaller GPUs
If you have 8-12 GB GPU, reduce ALL fractions:

```yaml
step_memory_fractions:
  # Reduce by 30%
  image_embed_clip: 0.5
  image_embed_dino: 0.5
  video_scene_detect: 0.4
  default: 0.35
```

## Monitoring During Long Runs

### Option 1: Command Line
```bash
# Watch GPU usage every 5 seconds
python common/gpu_monitor.py --interval 5
```

### Option 2: With Logging
```bash
# Log to file for later analysis
python common/gpu_monitor.py --interval 5 --log-file logs/gpu_monitor.log
```

### Option 3: nvidia-smi
```bash
# Built-in NVIDIA tool
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv -l 5
```

## Performance Tips

### Maximize Throughput
1. **Close Other GPU Applications**: Chrome, video players, etc.
2. **Use Larger Memory Fractions**: If you have headroom
3. **Clear Cache Aggressively**: Keep `clear_cache_after_step: true`

### Minimize Errors
1. **Start Conservative**: Use default fractions first
2. **Monitor First Run**: Watch for OOM errors
3. **Adjust Gradually**: Increase fractions 10% at a time

### Balance Speed vs Safety
```yaml
# Fast but risky (may OOM)
step_memory_fractions:
  default: 0.9

# Safe but slower
step_memory_fractions:
  default: 0.4
```

## Expected Behavior

### Normal Operation
```
✓ GPU initialized for step
✓ Memory allocated: X.XX GB
✓ Step completed in Y.Ys
✓ GPU cache cleared
```

### If GPU Unavailable
```
⚠ GPU not available, using CPU
✓ Step completed in Y.Ys (slower)
```

### If Memory Insufficient
```
✗ CUDA out of memory
→ Solution: Reduce memory fraction for this step
```

## FAQ

**Q: Do I need to configure anything?**  
A: No! It works automatically with sensible defaults.

**Q: Will it slow down my pipeline?**  
A: No, overhead is <5%. GPU management actually prevents slowdowns from memory issues.

**Q: Can I disable GPU management?**  
A: Yes, but not recommended. The system gracefully falls back to CPU if GPU unavailable.

**Q: What if I don't have a GPU?**  
A: Pipeline automatically runs on CPU. No errors.

**Q: Can I use multiple GPUs?**  
A: Not in Phase 1. Phase 2 will add multi-GPU support.

**Q: How do I know it's working?**  
A: Run the test suite: `python test_gpu_management.py`

**Q: Where are the logs?**  
A: Check `logs/watchdog.log` for pipeline logs

## Quick Reference Card

```bash
# Test everything
python test_gpu_management.py

# Check GPU
python common/gpu_monitor.py --check-only

# Monitor live
python common/gpu_monitor.py --interval 5

# Check processes
nvidia-smi

# View config
cat config/gpu_config.yaml

# View logs
tail -f logs/watchdog.log
```

## Getting Help

### Check Logs
```bash
# Pipeline logs
tail -n 100 logs/watchdog.log

# Step-specific logs (if verbose enabled)
ls logs/watchdog_*/
```

### Run Diagnostics
```bash
# Full system test
python test_gpu_management.py

# GPU availability only
python -c "from common.gpu_monitor import get_gpu_availability; print(get_gpu_availability())"
```

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "CUDA not available" | No GPU/drivers | Install NVIDIA drivers |
| "Out of memory" | Fraction too high | Reduce in config |
| "Process already using GPU" | Multiple processes | Stop others |
| Steps very slow | Using CPU | Check GPU detection |

---

**Need more help?** Check the full documentation in `GPU_PHASE_1_COMPLETE.md`
