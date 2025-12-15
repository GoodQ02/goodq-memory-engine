#!/bin/bash
set -euo pipefail

# Minimal GoodQ Audio Processing - Transcription Only
AUDIO_FILE="$1"
OUTPUT_DIR="$2"

source ~/goodq_audio/venv/bin/activate

python3 << 'PYTHON_EOF'
import sys
import json
import os
import torch
from pathlib import Path
from faster_whisper import WhisperModel

audio_file = sys.argv[1] if len(sys.argv) > 1 else os.getenv("AUDIO_FILE", "")
output_dir = sys.argv[2] if len(sys.argv) > 2 else os.getenv("OUTPUT_DIR", "")

result = {"status": "error", "message": "Unknown error"}

try:
    if not audio_file or not Path(audio_file).exists():
        result = {"status": "error", "message": f"Audio file not found: {audio_file}"}
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        
        model = WhisperModel("base", device=device, compute_type=compute_type)
        segments, info = model.transcribe(audio_file, language="en", beam_size=5)
        
        transcription = " ".join([seg.text for seg in segments])
        
        result = {
            "status": "success",
            "transcription": transcription,
            "language": info.language,
            "device": device
        }
        
        if output_dir:
            output_file = Path(output_dir) / "result.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

except Exception as e:
    result = {"status": "error", "message": str(e)}

print(json.dumps(result))
PYTHON_EOF
