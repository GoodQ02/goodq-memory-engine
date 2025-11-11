# GPU Management Quick Reference

## Basic Usage

### In Pipeline Steps

```python
from gpu_config import setup_step_gpu

def my_step(item, cfg):
    # Configure GPU at start of step
    gpu_config = setup_step_gpu("my_step_name")
    
    # Use the device from config
    device = gpu_config["device"]  # "cuda" or "cpu"
    
    # Your model initialization here
    model = MyModel().to(device)
    
    # Rest of step logic...
```

### Standalone Script

```python
from gpu_config import GPUManager

# Configure for specific step
config = GPUManager.configure_gpu("emotion_classify")
print(f"Using device: {config['device']}")
print(f"Memory fraction: {config['memory_fraction']}")

# Get GPU stats
stats = GPUManager.get_gpu_stats()
if stats:
    for device in stats["devices"]:
        print(f"GPU {device['id']}: {device['name']}")
        print(f"  Memory: {device['memory_allocated_mb']:.2f} MB")
        print(f"  Total: {device['memory_total_mb']:.2f} MB")

# Clear GPU cache
GPUManager.clear_cache()
```

## Memory Fractions by Step

| Step | Memory Fraction | Typical Model |
|------|----------------|---------------|
| `emotion_classify` | 30% | RoBERTa-base |
| `object_detect` | 30% | YOLO v8n |
| `image_embed_clip` | 25% | CLIP ViT-B/16 |
| `image_embed_dino` | 25% | DINOv2-base |
| `face_embed` | 20% | FaceNet |
| `audio_embed_clap` | 20% | CLAP HTSAT |
| `text_embed` | 15% | MiniLM-L6 |
| `default` | 20% | Fallback |

## Environment Variables Set

```bash
# GPU device pinning
CUDA_VISIBLE_DEVICES=0

# Model caching
HF_HOME=L:/models
TORCH_HOME=L:/models
TRANSFORMERS_CACHE=L:/models/transformers

# Deterministic behavior
PYTHONHASHSEED=1337
CUBLAS_WORKSPACE_CONFIG=:4096:8

# Disable unnecessary features
HF_HUB_ENABLE_HF_TRANSFER=0
```

## PyTorch Settings Applied

```python
# Memory limit
torch.cuda.set_per_process_memory_fraction(fraction, device_id)

# Deterministic mode
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True
torch.use_deterministic_algorithms(True, warn_only=True)
```

## Monitoring GPU Usage

### During Pipeline Execution

```bash
# Watch GPU usage in real-time (Windows)
nvidia-smi -l 1

# Query specific metrics
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv -l 1
```

### In Python

```python
from gpu_config import GPUManager

# Get current stats
stats = GPUManager.get_gpu_stats()

# Clear cache to free memory
GPUManager.clear_cache()
```

## Testing

### Quick GPU Test
```bash
python gpu_config.py
```

### Full Test Suite
```bash
python test_pipeline_gpu.py
```

### Test Specific Step
```python
from gpu_config import GPUManager

# Test emotion classifier
config = GPUManager.configure_gpu("emotion_classify")
print(f"Emotion classifier on {config['device']} with {config['memory_fraction']}% memory")

# Verify settings
stats = GPUManager.get_gpu_stats()
```

## Troubleshooting

### GPU Not Detected
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"PyTorch version: {torch.__version__}")
```

### Memory Issues
```python
# Clear cache
from gpu_config import GPUManager
GPUManager.clear_cache()

# Reduce memory fractions in config.yaml
# processing.gpu.memory_fractions.your_step: 0.15  # Lower value
```

### Multiple Processes
```python
# Each step runs in its own process via ZenML
# Memory fractions prevent conflicts
# No additional configuration needed
```

## Advanced Configuration

### Custom Memory Fraction

Edit `config.yaml`:
```yaml
processing:
  gpu:
    memory_fractions:
      my_custom_step: 0.25  # 25% of GPU memory
```

Or in code:
```python
from gpu_config import GPUManager

# Temporarily override
GPUManager.MEMORY_FRACTIONS["my_step"] = 0.40
config = GPUManager.configure_gpu("my_step")
```

### Multi-GPU Support (Future)

```python
# Configure for specific GPU
config = GPUManager.configure_gpu("my_step", gpu_id=1)
```

### Enable MPS (Linux/WSL2 only)

```python
from gpu_config import GPUManager

# Enable NVIDIA Multi-Process Service
GPUManager.enable_mps(thread_percentage=70)
```

## Integration with Pipeline

### ZenML Step Decorator

```python
@step(enable_cache=False)
def my_gpu_step(item: dict, config: dict) -> dict:
    # GPU config happens automatically via step module imports
    # Or explicitly:
    from gpu_config import setup_step_gpu
    gpu_cfg = setup_step_gpu("my_gpu_step")
    
    # Use device
    device = gpu_cfg["device"]
    # ... rest of step
```

## Performance Tips

1. **Batch Processing**: Group similar operations to maximize GPU utilization
2. **Memory Fractions**: Tune based on actual model sizes
3. **Clear Cache**: Call `GPUManager.clear_cache()` between large operations
4. **Monitor**: Use `nvidia-smi` to watch for memory leaks
5. **Deterministic**: Keep enabled for reproducibility, disable for speed if needed

## See Also

- `docs/PHASE_2_COMPLETE.md` - Full implementation details
- `gpu_config.py` - Source code and configuration
- `test_pipeline_gpu.py` - Test suite
- `config.yaml` - Main configuration file
