#!/bin/bash
set -euo pipefail

# Check if arguments are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <audio_file> <output_dir>"
    echo "Example: $0 ~/audio/test.wav ~/output"
    exit 1
fi

AUDIO_FILE="$1"
OUTPUT_DIR="$2"

# Source CUDA environment setup (includes venv activation)
source ~/goodq_audio/setup_cuda_env.sh

# Run the audio processing script
python3 ~/goodq_audio/process_audio.py "$AUDIO_FILE" "$OUTPUT_DIR"
