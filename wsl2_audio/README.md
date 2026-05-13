# GoodQ4All - WSL2 Audio Offload System

## Overview

This system offloads audio processing (transcription and diarization) from Windows to WSL2 Linux, where GPU acceleration works more reliably and efficiently with PyTorch-based models.

### Architecture

The active runtime uses a unified local WSL worker selected by the canonical
Windows ingestion/runtime surface.

- Windows remains the primary host.
- WSL is a compute extension for accelerated audio.
- The canonical bridge is `scripts/wsl2_audio_bridge.py`.
- Legacy helper imports under `wsl2_audio/` are compatibility wrappers only.
- No queue-directory watcher or pipeline-file editing is required for normal operation.

### Benefits

1. **Better GPU Utilization**: Linux PyTorch has better CUDA support than Windows
2. **Faster Processing**: faster-whisper is significantly faster than OpenAI Whisper
3. **VAD Preprocessing**: Silero VAD removes silence, reducing processing time by 30-60%
4. **Stability**: Fewer environment conflicts, no Windows-specific issues
5. **Scalability**: Easy to add more processing power or distribute across machines

### Performance Gains

Typical speedups compared to Windows-native processing:
- Transcription: **3-5x faster**
- Diarization: **2-3x faster**
- Combined: **Overall 4x faster** with VAD

Example: 1 hour of audio
- Windows (CPU): ~60 minutes
- Windows (GPU): ~20 minutes
- WSL2 (GPU + VAD): **~5 minutes**

## Installation

### Prerequisites

1. **Windows 11 or Windows 10 21H2+** with WSL2 support
2. **NVIDIA GPU** with latest drivers (581.80+ for WSL2)
3. **WSL2 Ubuntu** distribution
4. **16GB+ VRAM** recommended (works with 8GB but slower)

### Step 1: Windows Setup

Open PowerShell 7 in the project directory:

```powershell
cd <repo_root>
.\wsl2_audio\setup_windows.ps1
```

This will:
- Create necessary directories
- Generate bridge configuration
- Check WSL2 and CUDA availability
- Copy scripts to WSL2

### Step 2: WSL2 Environment Setup

Open WSL2 Ubuntu terminal:

```bash
cd ~/goodq_audio
./setup_wsl2_audio.sh
```

This will:
- Install system dependencies (ffmpeg, libsndfile, etc.)
- Create Python virtual environment
- Install the configured bootstrap-target WSL audio CUDA 12.1 trio:
  - `torch==2.5.1+cu121`
  - `torchvision==0.20.1+cu121`
  - `torchaudio==2.5.1+cu121`
- Install faster-whisper, `pyannote.audio==3.3.2`,
  `huggingface-hub==0.35.3`, Silero VAD, and related audio packages through
  `wsl2_audio/requirements-bootstrap-constraints.txt`
- Generate default configuration

### Step 3: Configure HuggingFace Token

PyAnnote diarization requires a HuggingFace account and token.

1. Create account at https://huggingface.co
2. Accept terms for: https://huggingface.co/pyannote/speaker-diarization-3.1
3. Get token from: https://huggingface.co/settings/tokens
4. Edit config in WSL2:

```bash
nano ~/goodq_audio/config.json
```

Replace `"huggingface_token": null` with an env reference:
```json
"huggingface_token": "${PYANNOTE_TOKEN}"
```

### Step 4: Verify the Runtime

In WSL2 terminal:

```bash
cd <repo_root>
python scripts/wsl2_audio_bridge.py
```

Or from Windows:

```cmd
.\wsl2_audio\start_wsl2_service.bat
```

This verifies that the canonical WSL audio runtime is ready.

### Step 5: Test the Bridge

From Windows:

```cmd
cd <repo_root>
python .\wsl2_audio\test_bridge.py
```

This will submit a test audio file and verify the complete workflow.

## Usage

### Canonical Runtime Selection

The active runtime does not require pipeline-file edits.

- Launch the system through the canonical repo-root launcher:
  - `LAUNCH_GOODQ.bat`
  - `LAUNCH_GOODQ.ps1`
- Ingestion is owned by `cli.run_ingestion`.
- The active WSL path is the unified bridge selected by runtime profile and flags, not by swapping `_wsl2` step modules into pipeline files.

For the current operator-facing contract, see:

- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/guides/llm/WSL2_AUDIO_SETUP.md`

### Direct Python API

```python
from wsl2_audio.audio_bridge import transcribe_wsl2, diarize_wsl2

# Transcribe
result = transcribe_wsl2(
    "path/to/audio.mp3",
    language="en",  # or None for auto-detect
    beam_size=5,
    timeout=600
)

# Diarize
result = diarize_wsl2(
    "path/to/audio.mp3",
    timeout=1800
)

# Both
from wsl2_audio.audio_bridge import transcribe_and_diarize_wsl2

result = transcribe_and_diarize_wsl2(
    "path/to/audio.mp3",
    language="en",
    timeout=1800
)
```

### Configuration

Edit `~/goodq_audio/config.json` in WSL2:

```json
{
  "models": {
    "whisper": "large-v3",  // or "medium", "small"
    "diarization": "pyannote/speaker-diarization-3.1",
    "vad": "silero_vad"
  },
  "gpu": {
    "device": "cuda",
    "memory_fraction": 0.8,  // Use 80% of VRAM
    "compute_type": "float16"  // or "int8" for lower VRAM
  },
  "processing": {
    "chunk_duration_minutes": 30,
    "vad_threshold": 0.5,  // Higher = more aggressive silence removal
    "min_speech_duration_ms": 250,
    "min_silence_duration_ms": 100
  }
}
```

## Troubleshooting

### Runtime Not Ready

Check bridge readiness:
```bash
python scripts/wsl2_audio_bridge.py
```

### CUDA Not Available

Verify CUDA passthrough:
```cmd
wsl nvidia-smi
```

If not working:
1. Update NVIDIA drivers: https://developer.nvidia.com/cuda/wsl
2. Update WSL: `wsl --update`
3. Restart WSL: `wsl --shutdown` then reopen terminal

### Model Download Fails

Models are large (2-7GB). Ensure stable internet.

Check disk space:
```bash
df -h ~
```

Models are cached in `~/.cache/huggingface/` and `~/.cache/torch/`

### Jobs Timeout

Increase timeout in bridge calls:
```python
result = transcribe_wsl2(audio_path, timeout=3600)  # 1 hour
```

Or in config (`bridge_config.json`):
```json
{
  "timeout_seconds": 7200
}
```

### Permission Errors

Ensure WSL2 can read Windows files:
```bash
ls -la /mnt/<drive>/<repo_root>/
```

If permission denied, check Windows folder permissions.

## Monitoring

### Runtime Status

```cmd
python scripts\wsl2_audio_bridge.py
```

### GPU Usage

```cmd
wsl nvidia-smi
```

Watch in real-time:
```cmd
wsl watch -n 1 nvidia-smi
```

## Performance Tuning

### For Maximum Speed

```json
{
  "gpu": {
    "memory_fraction": 0.9,
    "compute_type": "float16"
  },
  "processing": {
    "vad_threshold": 0.6  // More aggressive VAD
  }
}
```

### For Lower VRAM (8GB GPUs)

```json
{
  "models": {
    "whisper": "medium"  // Instead of large-v3
  },
  "gpu": {
    "memory_fraction": 0.7,
    "compute_type": "int8"  // Quantized
  }
}
```

### For Better Accuracy

```json
{
  "models": {
    "whisper": "large-v3"
  },
  "gpu": {
    "compute_type": "float16"  // Full precision
  },
  "processing": {
    "vad_threshold": 0.4,  // Less aggressive VAD
    "min_speech_duration_ms": 500  // Longer segments
  }
}
```

## Maintenance

### Update Models / Packages

Do not run broad `pip install --upgrade` commands in the WSL audio venv. The
runtime depends on the pinned bootstrap constraints in
`wsl2_audio/requirements-bootstrap-constraints.txt`, including the
`pyannote.audio==3.3.2` / `huggingface-hub==0.35.3` compatibility pair.

To repair or refresh the WSL audio environment, pull the latest repo and rerun
the bootstrap/setup path so the constraints file is restaged into the WSL
workspace. Confirm readiness with:

```powershell
conda run -n goodq_core python scripts/wsl_audio_preflight.py --compact
```

### Clean Cache

```bash
rm -rf ~/.cache/huggingface/hub/models--*
rm -rf ~/.cache/torch/hub/
```

### Reset Everything

```bash
cd ~
rm -rf goodq_audio
```

Then re-run setup scripts.

## Support

For issues, check:
1. Windows event logs
2. Pipeline logs: canonical Windows host log directory (`cfg.paths.log_dir`)
3. Runtime reference: `docs/reference/WSL_AUDIO_RUNTIME.md`

Common fixes:
- Restart WSL2: `wsl --shutdown`
- Re-run bridge readiness: `python scripts/wsl2_audio_bridge.py`
- Check GPU: `wsl nvidia-smi`
- Check disk: `wsl df -h`
