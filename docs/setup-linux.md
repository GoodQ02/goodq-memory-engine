# Linux Setup Guide

This guide details how to install, configure, and run GoodQ4All natively on Linux systems (Ubuntu, Debian, Arch Linux, etc.).

---

## 1. System Dependencies

GoodQ4All requires system packages for document and media parsing, OCR, and vector storage. Install these using your distribution's package manager:

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y ffmpeg poppler-utils tesseract-ocr qdrant
```

### Arch Linux
```bash
sudo pacman -S --needed ffmpeg poppler tesseract tesseract-data-eng qdrant
```

## 2. Python Conda Environment

Set up a conda virtual environment with CUDA GPU acceleration or CPU support.

```bash
# Create and activate environment
conda create -n goodq_core python=3.10 -y
conda activate goodq_core

# Install PyTorch with CUDA 12.1 acceleration (if NVIDIA GPU is available)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# OR install CPU-only PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## 3. Platform Folder Conventions (XDG Spec)

On Linux, GoodQ4All complies with the XDG Base Directory Specification:
* **Data Root**: `~/.local/share/goodq4all` (respects `XDG_DATA_HOME`)
* **Configuration**: `~/.config/goodq4all` (respects `XDG_CONFIG_HOME`)
* **Cache**: `~/.cache/goodq4all` (respects `XDG_CACHE_HOME`)
* **Logs**: `~/.local/state/goodq4all/logs` (respects `XDG_STATE_HOME`)

### Environment Path Overrides
You can customize these locations by exporting environment variables or specifying them in `.env.local` at the project root:

```bash
export GOODQ_DATA_ROOT="/var/lib/goodq4all"
export GOODQ_LOGS_ROOT="/var/log/goodq4all"
export GOODQ_CACHE_ROOT="/var/cache/goodq4all"
```

## 4. Hardware Acceleration

The system automatically detects CUDA-capable GPUs on Linux and configures PyTorch and ctranslate2 (Whisper) execution paths to use CUDA.

If no GPU is present or if you want to enforce CPU processing:
```bash
export GOODQ_DEVICE="cpu"
```

## 5. Verification

Verify your installation by running the preflight checks:

```bash
python scripts/bootstrap_verify.py --profile desktop
```
