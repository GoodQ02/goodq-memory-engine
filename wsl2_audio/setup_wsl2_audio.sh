#!/bin/bash
################################################################################
# GoodQ4All - WSL2 Audio Processing Environment Setup
# 
# This script sets up a GPU-accelerated audio processing environment in WSL2
# with faster-whisper, pyannote.audio, and Silero VAD
################################################################################

set -e

echo "================================================================================"
echo "  GoodQ4All WSL2 Audio Processing Setup"
echo "================================================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project paths
WINDOWS_PROJECT="/mnt/l/goodq4all"
WSL_HOME="$HOME/goodq_audio"
VENV_PATH="$WSL_HOME/venv"
QUEUE_DIR="$WSL_HOME/queue"
OUTPUT_DIR="$WSL_HOME/output"
LOGS_DIR="$WSL_HOME/logs"

echo "[1/10] Creating directory structure..."
mkdir -p "$WSL_HOME"
mkdir -p "$QUEUE_DIR/pending"
mkdir -p "$QUEUE_DIR/processing"
mkdir -p "$QUEUE_DIR/completed"
mkdir -p "$QUEUE_DIR/failed"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOGS_DIR"

echo "[2/10] Checking CUDA availability..."
if ! nvidia-smi &> /dev/null; then
    echo -e "${RED}ERROR: nvidia-smi not found. CUDA passthrough not configured.${NC}"
    echo "Please ensure you have:"
    echo "  1. Latest NVIDIA drivers for WSL2"
    echo "  2. Windows 11 or Windows 10 with WSL2 support"
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)
GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1)
echo -e "${GREEN}✓ GPU detected: $GPU_NAME ($GPU_MEMORY MB)${NC}"

echo "[3/10] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip \
    python3-venv \
    ffmpeg \
    libsndfile1 \
    sox \
    git \
    curl

echo "[4/10] Creating Python virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

echo "[5/10] Installing PyTorch with CUDA 12.1..."
pip install -q --upgrade pip wheel setuptools
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo "[6/10] Verifying PyTorch CUDA..."
python3 << 'PYEOF'
import torch
if torch.cuda.is_available():
    print(f"✓ PyTorch CUDA available: {torch.version.cuda}")
    print(f"✓ GPU count: {torch.cuda.device_count()}")
    print(f"✓ Current GPU: {torch.cuda.get_device_name(0)}")
else:
    print("✗ PyTorch CUDA NOT available")
    exit(1)
PYEOF

echo "[7/10] Installing audio processing libraries..."
pip install -q \
    faster-whisper \
    pyannote.audio \
    soundfile \
    librosa \
    noisereduce \
    pydub

echo "[8/10] Installing Silero VAD..."
pip install -q silero-vad

echo "[9/10] Installing utilities..."
pip install -q \
    numpy \
    scipy \
    tqdm \
    psutil \
    watchdog

echo "[10/10] Creating service configuration..."
cat > "$WSL_HOME/config.json" << 'EOF'
{
  "queue_dir": "queue",
  "output_dir": "output",
  "logs_dir": "logs",
  "windows_project": "/mnt/l/goodq4all",
  "models": {
    "whisper": "large-v3",
    "diarization": "pyannote/speaker-diarization-3.1",
    "vad": "silero_vad"
  },
  "gpu": {
    "device": "cuda",
    "memory_fraction": 0.8,
    "compute_type": "float16"
  },
  "processing": {
    "chunk_duration_minutes": 30,
    "vad_threshold": 0.5,
    "min_speech_duration_ms": 250,
    "min_silence_duration_ms": 100
  },
  "huggingface_token": null
}
EOF

echo ""
echo "================================================================================"
echo "  Setup Complete!"
echo "================================================================================"
echo ""
echo "Environment details:"
echo "  - WSL Home: $WSL_HOME"
echo "  - Virtual Env: $VENV_PATH"
echo "  - Queue Dir: $QUEUE_DIR"
echo "  - Output Dir: $OUTPUT_DIR"
echo ""
echo "To activate the environment:"
echo "  source $VENV_PATH/bin/activate"
echo ""
echo "Next steps:"
echo "  1. Set your HuggingFace token in config.json (for pyannote models)"
echo "  2. Run the audio service: python3 audio_service.py"
echo ""
