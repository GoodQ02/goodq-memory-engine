# GPU Setup Guide

> Role: Canonical GPU setup guide for GoodQ4All `GPU_ENHANCED` profile. Use this document to configure acceleration tiers. For runtime management patterns, see `docs/GPU_MANAGEMENT_GUIDE.md` and `docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md`.

## Overview

GoodQ4All uses GPU acceleration for compute-intensive tasks when running the `GPU_ENHANCED` profile. This guide explains how to configure GPU support without changing baseline correctness semantics.

## Profile Scope

- `UNSET`: legacy canonical behavior.
- `BASELINE`: CPU-safe mode; GPU setup is not required.
- `GPU_ENHANCED`: apply this guide to enable CUDA throughput paths.

Example profile selection:

```powershell
$env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

## GPU Architecture

### Why GPU Matters

GPU acceleration provides **10-50x speedup** for:
- **Audio Diarization** (PyAnnote): 30x faster speaker identification
- **Audio Transcription** (Faster Whisper): 15x faster speech-to-text
- **Face Embedding** (FaceNet): 20x faster face recognition
- **Emotion Classification** (RoBERTa): 25x faster sentiment analysis
- **Image Embeddings** (CLIP/DINO): 40x faster visual understanding

### Environment Structure

Each pipeline step runs in its own isolated conda environment with specific dependencies. This prevents version conflicts; GPU-enabled environments are only required for `GPU_ENHANCED`.

## Prerequisites (`GPU_ENHANCED`)

### Hardware Requirements
- **NVIDIA GPU** with CUDA Compute Capability 3.5+
- **16GB+ VRAM** recommended for optimal performance
- Your system: **NVIDIA GeForce RTX 4070 Ti SUPER** (16GB VRAM) ✅

### Software Requirements
1. **NVIDIA Drivers**: Version 525+ (You have: 581.80 ✅)
2. **CUDA**: Installed via PyTorch (automatic)
3. **Conda**: For environment management ✅

## Quick Setup

### Option 1: Automated Setup (Recommended)

Run the quick setup script:

```bash
cd L:\goodq4all
python scripts\quick_gpu_setup.py
```

This will:
1. Uninstall CPU-only PyTorch from each environment
2. Install CUDA-enabled PyTorch with correct versions
3. Verify CUDA works in each environment
4. Report any failures

**Time**: ~10-15 minutes (one-time setup)

### Option 2: Manual Setup

For each environment, run:

```bash
# Audio Diarization (PyTorch 2.5.1 + CUDA 12.4)
conda activate audio_diarize
pip uninstall -y torch torchaudio torchvision
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124

# Audio Transcription (PyTorch 2.3.1 + CUDA 12.1)
conda activate audio_transcribe
pip uninstall -y torch
pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cu121

# Emotion Classification (PyTorch 2.3.1 + CUDA 12.1)
conda activate emotion_classify
pip uninstall -y torch torchvision
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121

# Face Embedding (PyTorch 2.3.1 + CUDA 12.1)
conda activate face_embed
pip uninstall -y torch torchvision
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121

# Text Embedding (PyTorch 2.3.1 + CUDA 12.1)
conda activate text_embed
pip uninstall -y torch torchvision
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
```

## Verification

### Check GPU Status

```bash
cd L:\goodq4all
python scripts\check_gpu_status.py
```

Expected output:
```
✓ PASS: NVIDIA Drivers
✓ PASS: CUDA Availability
✓ PASS: GPU Utilization
✓ PASS: GPU Processes
✓ PASS: Environment Vars
```

### Test Specific Environment

```bash
conda activate audio_diarize
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}')"
```

Expected output:
```
CUDA: True
Device: NVIDIA GeForce RTX 4070 Ti SUPER
```

## GPU Configuration

### Memory Management

The pipeline uses conservative memory allocation to prevent OOM errors:

| Step | Memory Fraction | Typical Usage |
|------|----------------|---------------|
| audio_diarize | 35% | ~5.7 GB |
| audio_transcribe | 30% | ~4.9 GB |
| image_embed_clip | 30% | ~4.9 GB |
| face_embed | 25% | ~4.1 GB |
| emotion_classify | 30% | ~4.9 GB |

These are configured in `gpu_config.py` and can be adjusted if needed.

### Environment Variables

The pipeline automatically sets:
- `CUDA_VISIBLE_DEVICES=0` - Use first GPU only
- `HF_HOME=L:/models` - Cache models locally
- `TORCH_HOME=L:/models` - Cache PyTorch models
- `PYTHONHASHSEED=1337` - Deterministic behavior
- `CUBLAS_WORKSPACE_CONFIG=:4096:8` - Reproducible results

### Performance Optimization

For maximum performance:

1. **Close GPU-heavy applications** before running pipeline
2. **Monitor GPU usage**: `nvidia-smi -l 1`
3. **Adjust memory fractions** in `gpu_config.py` if needed
4. **Use batch processing** when possible

## Troubleshooting

### Issue: "CUDA not available"

**Cause**: CPU-only PyTorch is installed

**Solution**:
```bash
conda activate <environment_name>
pip uninstall torch torchvision torchaudio
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
```

### Issue: "CUDA out of memory"

**Cause**: GPU memory exhausted

**Solutions**:
1. Close other GPU applications
2. Reduce memory fractions in `gpu_config.py`
3. Process smaller batches
4. Clear GPU cache: `torch.cuda.empty_cache()`

### Issue: "nvidia-smi not found"

**Cause**: NVIDIA drivers not installed or not in PATH

**Solution**:
1. Download drivers from https://www.nvidia.com/drivers
2. Install and reboot
3. Verify: `nvidia-smi`

### Issue: Environment not activating

**Cause**: Conda environment doesn't exist

**Solution**:
```bash
# Recreate environment
conda env create -f envs/<step_name>/requirements.txt
```

## Performance Benchmarks

### Expected Speedup (GPU vs CPU)

- **Audio Diarization**: ~30x faster
  - CPU: ~2 hours for 1-hour video
  - GPU: ~4 minutes for 1-hour video

- **Audio Transcription**: ~15x faster
  - CPU: ~90 minutes for 1-hour audio
  - GPU: ~6 minutes for 1-hour audio

- **Face Embedding**: ~20x faster
  - CPU: ~5 seconds per image
  - GPU: ~0.25 seconds per image

- **Emotion Classification**: ~25x faster
  - CPU: ~2 seconds per text
  - GPU: ~0.08 seconds per text

## Advanced Configuration

### Multiple GPUs

If you have multiple GPUs, you can assign different steps to different GPUs:

Edit `gpu_config.py`:
```python
def setup_step_gpu(step_name: str, gpu_id: int = 0):
    # Assign specific steps to specific GPUs
    gpu_assignments = {
        "audio_diarize": 0,
        "audio_transcribe": 0,
        "image_embed_clip": 1,  # Use second GPU
        "face_embed": 1
    }
    
    gpu_id = gpu_assignments.get(step_name, 0)
    # ... rest of function
```

### Exclusive GPU Mode

For maximum performance, set GPU to exclusive mode:

```bash
# Requires admin/root
nvidia-smi -c EXCLUSIVE_PROCESS
```

Reset to default:
```bash
nvidia-smi -c DEFAULT
```

### MPS (Linux/WSL2 Only)

For better GPU sharing on Linux:

```bash
sudo nvidia-cuda-mps-control -d
export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=70
```

## Monitoring

### Real-time GPU Usage

```bash
# Watch GPU every 1 second
nvidia-smi -l 1

# Or with detailed info
watch -n 1 nvidia-smi
```

### Log GPU Usage

```bash
# Log to file
nvidia-smi --query-gpu=timestamp,utilization.gpu,utilization.memory,temperature.gpu --format=csv -l 1 > gpu_log.csv
```

### Python Monitoring

```python
from gpu_config import GPUManager

# Get current stats
stats = GPUManager.get_gpu_stats()
print(f"GPU Usage: {stats['utilization_pct']}%")
print(f"Memory: {stats['allocated_gb']}/{stats['total_gb']} GB")
```

## FAQ

**Q: Do I need to install CUDA separately?**
A: No, PyTorch bundles CUDA libraries. Just install with `--index-url`.

**Q: Can I use CPU if GPU setup fails?**
A: Yes. `BASELINE` remains supported and CPU-safe.

**Q: How much faster is GPU?**
A: 10-50x depending on the task. Audio diarization sees the biggest gains.

**Q: Will this work on AMD GPUs?**
A: No, currently only NVIDIA GPUs with CUDA are supported.

**Q: Can I run multiple pipeline steps simultaneously?**
A: Yes, but monitor GPU memory. You may need to reduce memory fractions.

## Support

For issues:
1. Run diagnostics: `python scripts\check_gpu_status.py`
2. Check logs in `logs/` directory
3. Review error messages carefully
4. Check GPU memory: `nvidia-smi`

## Related Files

- `gpu_config.py` - Central GPU configuration
- `scripts/quick_gpu_setup.py` - Automated setup
- `scripts/check_gpu_status.py` - Diagnostics
- `scripts/setup_gpu_environments.bat` - Windows batch setup
- `scripts/validate_gpu_setup.bat` - Validation script
