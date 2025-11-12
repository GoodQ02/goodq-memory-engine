# Audio Pipeline GPU Optimization Guide

## Overview

This document explains the GPU optimization system for audio processing in GoodQ4All, specifically for speaker diarization and transcription.

## Architecture

### Components

1. **Audio GPU Optimizer** (`steps/common/audio_gpu_optimizer.py`)
   - Centralized GPU configuration management
   - Dynamic memory allocation based on workload
   - Performance tracking and optimization recommendations
   - Automatic GPU warmup and cache management

2. **Optimized Steps**
   - `audio_diarize`: Speaker diarization with PyAnnote Audio
   - `audio_transcribe`: Speech transcription with Faster-Whisper

3. **Monitoring Tools**
   - `audio_gpu_monitor.py`: Real-time GPU monitoring
   - `audio_gpu_report.py`: Performance analysis and recommendations
   - `test_audio_gpu_optimization.py`: Comprehensive test suite

## How It Works

### Memory Allocation Strategy

The system uses **dynamic memory allocation** based on audio duration and processing requirements:

#### Diarization (PyAnnote Audio)
- **Short audio** (<10min): 40% VRAM - process whole file
- **Medium audio** (10-30min): 35% VRAM - chunked if needed  
- **Long audio** (>30min): 30% VRAM - aggressive chunking

#### Transcription (Whisper)
- **All durations**: 28% VRAM for medium model
- Uses FP16 precision for 2x speedup
- Batch processing with 4 chunks in parallel
- 2 CUDA streams for overlapped processing

### Why These Numbers?

**PyAnnote Memory Requirements:**
- Base model: ~2-3GB
- With embeddings: ~3-4GB  
- Peak during processing: ~4-6GB

**Whisper Medium Model:**
- Base usage: ~5GB
- With FP16: ~2.5GB
- Additional overhead: ~2GB
- Safe allocation: ~28% of typical 8-12GB GPUs

### GPU Optimization Features

1. **Automatic Configuration**
   - Detects available VRAM
   - Selects optimal compute type (FP16/INT8)
   - Enables flash attention if available

2. **Warmup**
   - Initializes CUDA kernels before processing
   - Eliminates first-run latency
   - Warms up both GPU and model

3. **Cache Management**
   - Clears GPU cache between chunks
   - Prevents memory fragmentation
   - Ensures stable memory usage

4. **Performance Tracking**
   - Records processing times
   - Calculates realtime factors
   - Tracks memory peaks
   - Generates optimization suggestions

## Usage

### Automatic (Recommended)

The GPU optimizer is **automatically activated** when you run the pipeline:

```batch
LAUNCH_GOODQ.bat
```

The steps will automatically:
1. Detect GPU availability
2. Configure optimal memory allocation
3. Warmup GPU kernels
4. Track performance
5. Suggest optimizations

### Manual Testing

#### Run Full Test Suite
```batch
TEST_AUDIO_GPU.bat
```

This will:
- Check GPU availability
- Test audio steps individually
- Run full pipeline with monitoring
- Generate performance report

#### Monitor GPU in Real-Time
```batch
conda activate goodq_zenml
python scripts/audio_gpu_monitor.py
```

#### Generate Performance Report
```batch
conda activate goodq_zenml
python scripts/audio_gpu_report.py
```

## Performance Metrics

### Typical Performance (NVIDIA RTX 3060 12GB)

**Diarization:**
- Processing speed: 1.5-2.0x realtime
- VRAM usage: 3-5GB peak
- Example: 60min audio in 30-40min

**Transcription:**
- Processing speed: 8-12x realtime  
- VRAM usage: 4-6GB peak
- Example: 60min audio in 5-8min

**Combined Pipeline:**
- Total speedup: ~2.5x compared to CPU
- Memory efficient: Uses <50% of 12GB VRAM
- Stable: No OOM errors with proper chunking

## Optimization Recommendations

The system analyzes GPU usage and provides recommendations:

### "Increase" Recommendation
**When:** GPU utilization < 50%  
**Meaning:** You have headroom to process larger chunks or use higher precision
**Action:** System will automatically increase memory allocation on next run

### "Decrease" Recommendation  
**When:** GPU utilization > 85%
**Meaning:** Near memory limits, risk of OOM errors
**Action:** System will automatically reduce allocation and increase chunking

### "Maintain" Recommendation
**When:** GPU utilization 50-85%
**Meaning:** Optimal balance between speed and stability
**Action:** Current settings are ideal

## Troubleshooting

### Out of Memory (OOM) Errors

**Symptoms:**
```
RuntimeError: CUDA out of memory
```

**Solutions:**
1. System will automatically reduce memory allocation
2. Manually set lower fractions in `gpu_config.py`
3. Increase audio chunk size to reduce overhead
4. Close other GPU applications

### Slow Processing

**Symptoms:**
- Realtime factor < 1.0x
- GPU utilization low (<30%)

**Causes:**
- CPU bottleneck (data loading)
- Small chunks creating overhead
- Model not loaded on GPU

**Solutions:**
1. Check GPU is actually being used: `nvidia-smi`
2. Increase chunk size for better GPU utilization
3. Enable FP16 precision if not already
4. Verify CUDA is properly installed

### GPU Not Detected

**Symptoms:**
```
[AudioGPU] CUDA not available, using CPU
```

**Solutions:**
1. Install NVIDIA drivers
2. Install CUDA Toolkit
3. Reinstall PyTorch with CUDA:
   ```batch
   conda activate audio_diarize
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

## Advanced Configuration

### Custom Memory Fractions

Edit `steps/common/audio_gpu_optimizer.py`:

```python
def configure_for_diarization(self, duration_minutes: float = None):
    # Change default 40% to 50%
    memory_fraction = 0.50  
    ...
```

### Disable GPU for Specific Steps

Edit step config:

```python
# Force CPU mode
device = "cpu"
```

### Enable Flash Attention

If you have flash-attn installed:

```batch
conda activate audio_transcribe  
pip install flash-attn --no-build-isolation
```

The system will automatically detect and use it.

## Monitoring and Logging

### GPU Logs Location
```
L:\goodq4all\logs\gpu_reports\
L:\goodq4all\logs\gpu_monitoring\
```

### Real-Time Monitoring
- Launch `audio_gpu_monitor.py` in separate terminal
- Watch live VRAM, utilization, temperature, power
- Automatically saves CSV data

### Performance Reports
- Run `audio_gpu_report.py` after processing
- View per-step performance breakdown
- Get optimization recommendations
- Historical data for comparison

## Best Practices

1. **Always warmup** - Let the system initialize on first run
2. **Monitor memory** - Check GPU stats after each video
3. **Adjust chunking** - Balance chunk size vs. overhead
4. **Clear cache** - System does this automatically, but manual clears help
5. **Track performance** - Use built-in tracking to optimize over time
6. **Update regularly** - Keep CUDA, PyTorch, and models updated

## Known Limitations

1. **Single GPU only** - Currently uses GPU 0 only
2. **No multi-GPU** - Cannot distribute across multiple GPUs
3. **Fixed precision** - FP16 for GPU, INT8 for CPU
4. **PyAnnote chunking** - Must chunk long audio manually
5. **Windows paths** - Optimized for Windows, may need tweaks for Linux

## Future Improvements

- [ ] Multi-GPU support
- [ ] Dynamic precision switching
- [ ] Automatic chunk size optimization
- [ ] Better memory prediction
- [ ] Integration with ZenML resource management
- [ ] Docker container GPU passthrough
- [ ] Tensorboard integration for monitoring

## References

- PyAnnote Audio: https://github.com/pyannote/pyannote-audio
- Faster-Whisper: https://github.com/guillaumekln/faster-whisper
- CUDA Memory Management: https://pytorch.org/docs/stable/notes/cuda.html
- Flash Attention: https://github.com/Dao-AILab/flash-attention

## Support

For issues:
1. Check logs in `L:\goodq4all\logs\`
2. Run `TEST_AUDIO_GPU.bat` for diagnostics
3. Generate performance report for analysis
4. Review this guide for troubleshooting steps

---

**Version:** 1.0.0  
**Last Updated:** 2025-11-12  
**Author:** GoodQ4All Development Team
