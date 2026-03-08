#!/bin/bash
# GoodQ4All - WSL2 Audio Quick Install
# Run this inside WSL2: wsl -d <distro> -- bash <wsl_project_root>/scripts/wsl2_quick_install.sh

set -e

echo "================================================================================"
echo "  GoodQ4All WSL2 Audio Setup"
echo "================================================================================"
echo ""

# Get current user
USER_NAME=$(whoami)
WORKSPACE="$HOME/goodq_audio"

echo "[1/6] Installing system packages..."
sudo apt update -qq
sudo apt install -y python3.12-venv python3-pip ffmpeg libsndfile1 portaudio19-dev

echo ""
echo "[2/6] Creating workspace..."
mkdir -p "$WORKSPACE"/{scripts,models,queue_in,queue_out,logs}
cd "$WORKSPACE"

echo ""
echo "[3/6] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "[4/6] Installing PyTorch with CUDA..."
pip install --upgrade pip -q
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo ""
echo "[5/6] Installing audio libraries..."
pip install faster-whisper openai-whisper pyannote.audio
pip install librosa soundfile scipy numpy

echo ""
echo "[6/6] Creating processing script..."
cat > "$WORKSPACE/process_audio.py" << 'SCRIPT_EOF'
#!/usr/bin/env python3
"""GPU-Accelerated Audio Processor for GoodQ"""
import sys
import json
import torch
from faster_whisper import WhisperModel
from pathlib import Path

def process_audio(audio_path, output_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}", file=sys.stderr)
    
    model = WhisperModel("base", device=device, compute_type="float16" if device=="cuda" else "int8")
    
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=400
        )
    )
    
    result = {
        "language": info.language,
        "duration": info.duration,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in segments
        ]
    }
    
    Path(output_path).write_text(json.dumps(result, indent=2))
    print(f"Processed {len(result['segments'])} segments", file=sys.stderr)
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: process_audio.py <input> <output>", file=sys.stderr)
        sys.exit(1)
    process_audio(sys.argv[1], sys.argv[2])
SCRIPT_EOF

chmod +x "$WORKSPACE/process_audio.py"

echo ""
echo "================================================================================"
echo "  Installation Complete!"
echo "================================================================================"
echo ""
echo "Workspace: $WORKSPACE"
echo "Virtual env: $WORKSPACE/venv"
echo ""
echo "Testing installation..."
source "$WORKSPACE/venv/bin/activate"
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU only\"}')"

echo ""
echo "================================================================================"
echo "  Setup successful! WSL2 audio processing is ready."
echo "================================================================================"
echo ""
echo "Test from Windows with:"
echo "  python <project_root>\\wsl2_audio_bridge.py"
echo ""
