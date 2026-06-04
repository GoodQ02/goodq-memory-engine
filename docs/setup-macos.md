# macOS (Apple Silicon) Setup Guide

This guide details how to install, configure, and run GoodQ4All natively on macOS (Apple Silicon / Intel).

---

## 1. System Dependencies

GoodQ4All relies on several external binary packages for media framing, document indexing, and Optical Character Recognition (OCR). Install these using [Homebrew](https://brew.sh):

```bash
# Install core system packages
brew install ffmpeg poppler tesseract tesseract-lang qdrant
```

## 2. Python Conda Environment

Set up a native arm64 Conda environment for optimal Apple Silicon acceleration support.

```bash
# Create and activate environment
conda create -n goodq_core python=3.10 -y
conda activate goodq_core

# Install PyTorch with Metal Performance Shaders (MPS) support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
# Note: On macOS, standard pip install of torch includes MPS support out-of-the-box.
pip install torch torchvision torchaudio
```

## 3. External Tool Discovery

The `ToolResolver` automatically scans standard Homebrew paths:
* `/opt/homebrew/bin` (Apple Silicon default)
* `/usr/local/bin` (Intel default)

If your installations are in a custom location, export `GOODQ_TOOLS_ROOT` or add them to your `PATH`.

## 4. Platform Folder Conventions

GoodQ4All adheres to macOS application support conventions. By default, files are placed in:
* **Data Root**: `~/Library/Application Support/GoodQ4All`
* **Configuration**: `~/Library/Preferences/GoodQ4All`
* **Cache**: `~/Library/Caches/GoodQ4All`
* **Logs**: `~/Library/Logs/GoodQ4All`

### Environment Path Overrides
You can customize these directories by exporting environment variables in your active shell or adding them to `.env.local` at the project root:

```bash
export GOODQ_DATA_ROOT="/custom/data/path"
export GOODQ_LOGS_ROOT="/custom/logs/path"
export GOODQ_CACHE_ROOT="/custom/cache/path"
```

## 5. GPU & Hardware Acceleration (Metal Performance Shaders)

On Apple Silicon (M1/M2/M3/M4), the system detects Metal hardware support and selects `mps` as the active torch device.

### MPS Audio Diarization Defaults
Due to half-precision (`float16`) LayerNorm limitations in the PyAnnote diarization library under MPS, GoodQ4All defaults to:
* **Whisper Transcription**: CPU-based execution (`float32` / `int8` representation) for ctranslate2 compatibility.
* **Speaker Diarization**: CPU-based execution by default (`GOODQ_MPS_DIARIZATION=0`) to ensure 100% precision correctness.

To force diarization to run on the Metal GPU (which may introduce precision warnings or minor output drift):
```bash
export GOODQ_MPS_DIARIZATION="1"
```

To force the entire audio pipeline to CPU:
```bash
export GOODQ_DEVICE="cpu"
```

## 6. Verification

Run the bootstrap verification script to ensure your environment is fully configured:

```bash
python scripts/bootstrap_verify.py --profile desktop
```
