#!/bin/bash
set -e

echo "================================================================================"
echo "  GoodQ4All WSL2 Audio Setup - Interactive Installation"
echo "================================================================================"
echo ""
echo "This script will install GPU-accelerated audio processing in WSL2"
echo ""
echo "You will be prompted for your sudo password when needed."
echo ""

# Step 1: Install system packages
echo "[1/6] Installing system packages (requires sudo)..."
sudo apt update
sudo apt install -y python3.12-venv python3-pip ffmpeg libsndfile1 build-essential

# Step 2: Create virtual environment
echo "[2/6] Creating Python virtual environment..."
cd ~/goodq_audio
python3 -m venv venv

# Step 3: Activate venv
echo "[3/6] Activating virtual environment..."
source venv/bin/activate

# Step 4: Install PyTorch with CUDA
echo "[4/6] Installing PyTorch with CUDA 12.1 (this will take a few minutes)..."
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Step 5: Install audio processing libraries
echo "[5/6] Installing Whisper and PyAnnote..."
pip install openai-whisper faster-whisper pyannote.audio

# Step 6: Test installation
echo "[6/6] Testing installation..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')"

echo ""
echo "================================================================================"
echo "  ✅ Installation Complete!"
echo "================================================================================"
echo ""
echo "Virtual environment created at: ~/goodq_audio/venv"
echo ""
