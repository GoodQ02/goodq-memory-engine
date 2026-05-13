# GoodQ Audio Processing - CUDA/cuDNN Setup

## Summary

This is an operator note for validating the WSL2 audio CUDA/cuDNN runtime.
The configured expected / bootstrap-target project lane is the conservative WSL audio stack documented in
`docs/reference/WSL_AUDIO_RUNTIME.md` and pinned in
`wsl2_audio/requirements-bootstrap-constraints.txt`.

### Current Configuration

- **GPU**: local NVIDIA GPU when available
- **Host driver CUDA report**: may be newer than the package lane
- **Bootstrap-target WSL audio torch lane**: `torch==2.5.1+cu121`
- **Bootstrap-target WSL audio torchvision lane**: `torchvision==0.20.1+cu121`
- **Bootstrap-target WSL audio torchaudio lane**: `torchaudio==2.5.1+cu121`
- **Bootstrap-target WSL diarization lane**: `pyannote.audio==3.3.2`
  paired with `huggingface-hub==0.35.3`
- **Bootstrap constraints**: `wsl2_audio/requirements-bootstrap-constraints.txt`
- **Status rule**: run the diagnostics below on the target machine before
  treating the local WSL audio worker as ready

`wsl2_audio/requirements-locked.txt` may still contain a historical package
snapshot and is not the bootstrap-authoritative WSL audio torch lane until it is
regenerated from a validated worker. It also must not override the PyAnnote /
Hugging Face Hub compatibility pair in the bootstrap constraints. The active
sourced worker may also differ from the bootstrap target; trust the runtime
recorder for observed truth.

## Quick Start

### 1. Activate CUDA Environment

Instead of using the standard venv activation, use:

```bash
source ~/goodq_audio/setup_cuda_env.sh
```

This script:
- Sets up LD_LIBRARY_PATH with NVIDIA cuDNN and CUDA libraries
- Activates the virtual environment
- Ensures all CUDA/cuDNN libraries are accessible

### 2. Verify CUDA Setup

Run the diagnostic script:

```bash
python3 ~/goodq_audio/check_cuda.py
```

This will verify:
- CUDA availability
- cuDNN functionality
- All audio processing libraries
- Environment configuration

### 3. Process Audio Files

```bash
cd ~/goodq_audio
./process.sh /path/to/audio.wav /path/to/output_dir
```

## What Was Fixed

### Issue
You were getting this error:
```
Unable to load any of {libcudnn_ops.so.9.1.0, libcudnn_ops.so.9.1, libcudnn_ops.so.9, libcudnn_ops.so}
Invalid handle. Cannot load symbol cudnnCreateTensorDescriptor
```

### Root Cause
The cuDNN libraries were installed via pip (`nvidia-cudnn-cu12`) but weren't in the system's library search path (LD_LIBRARY_PATH).

### Solution
Created `setup_cuda_env.sh` which sets LD_LIBRARY_PATH to include:
- `nvidia/cudnn/lib` - cuDNN libraries
- `nvidia/cublas/lib` - cuBLAS libraries
- `nvidia/cuda_nvrtc/lib` - CUDA NVRTC libraries
- `nvidia/cuda_runtime/lib` - CUDA runtime libraries

## Files Created

1. **~/goodq_audio/setup_cuda_env.sh** - CUDA environment activation script
2. **~/goodq_audio/check_cuda.py** - Comprehensive diagnostic tool
3. **~/goodq_audio/process.sh** - Updated to use CUDA environment

## Library Locations

cuDNN libraries are located at:
```
~/goodq_audio/venv/lib/python3.12/site-packages/nvidia/cudnn/lib/
```

Available libraries:
- libcudnn.so.9
- libcudnn_ops.so.9
- libcudnn_cnn.so.9
- libcudnn_adv.so.9
- libcudnn_graph.so.9
- libcudnn_heuristic.so.9
- libcudnn_engines_precompiled.so.9
- libcudnn_engines_runtime_compiled.so.9

## Testing

### Basic CUDA Test
```bash
source ~/goodq_audio/setup_cuda_env.sh
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0)}')"
```

Expected output:
```
CUDA: True, GPU: <local NVIDIA GPU>
```

### cuDNN Test
```bash
source ~/goodq_audio/setup_cuda_env.sh
python3 -c "import torch; print(f'cuDNN version: {torch.backends.cudnn.version()}')"
```

Expected output:
```
cuDNN version: 91002
```

### Full Diagnostic
```bash
source ~/goodq_audio/setup_cuda_env.sh
python3 ~/goodq_audio/check_cuda.py
```

## Troubleshooting

### If CUDA is not available:
1. Check nvidia-smi: `nvidia-smi`
2. Verify driver: Should show CUDA Version 13.0+

### If cuDNN errors persist:
1. Ensure you're using the setup script: `source ~/goodq_audio/setup_cuda_env.sh`
2. Check LD_LIBRARY_PATH: `echo $LD_LIBRARY_PATH`
3. Run diagnostics: `python3 ~/goodq_audio/check_cuda.py`

### If libraries are missing:
```bash
source ~/goodq_audio/venv/bin/activate
pip list | grep nvidia
```

Should show:
- nvidia-cudnn-cu12
- nvidia-cuda-runtime-cu12
- nvidia-cuda-nvrtc-cu12
- nvidia-cublas-cu12

## Important Notes

1. **Always use `setup_cuda_env.sh` instead of direct venv activation** when working with CUDA/GPU operations
2. PyTorch has cuDNN bundled but uses the pip-installed version when available
3. WSL2 accesses GPU through the Windows NVIDIA driver (no separate driver needed in WSL)
4. The configured GoodQ WSL audio bootstrap target is `2.5.1+cu121`; do not
   promote or downgrade the active runtime lane without a targeted WSL audio
   smoke and witness proving the change

## Next Steps

After diagnostics pass, the WSL audio worker can:

- Run audio processing with GPU acceleration
- Use faster-whisper with CUDA
- Run pyannote.audio models on GPU
- Run transformers inference on CUDA

For any issues, run `python3 ~/goodq_audio/check_cuda.py` to diagnose.
