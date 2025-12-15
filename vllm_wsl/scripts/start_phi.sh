#!/bin/bash
# Start vLLM server with Phi-3.5 Mini Instruct

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VLLM_DIR="$(dirname "$SCRIPT_DIR")"

# Activate environment
source "$VLLM_DIR/venv/bin/activate"

# Set cuDNN path
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$VLLM_DIR/venv/lib/python3.12/site-packages/nvidia/cudnn/lib"

# Model configuration
MODEL_PATH="/mnt/l/_DATA/models/llm/huggingface/Phi-3.5-mini-instruct"
PORT=8001

echo "═══════════════════════════════════════════════════════════════"
echo "Starting vLLM Server: Phi-3.5 Mini Instruct"
echo "═══════════════════════════════════════════════════════════════"
echo "Model: $MODEL_PATH"
echo "Port: $PORT"
echo "API: http://localhost:$PORT/v1/"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Start vLLM
vllm serve "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port $PORT \
    --gpu-memory-utilization 0.85 \
    --dtype auto \
    --max-model-len 8192 \
    --enable-prefix-caching \
    2>&1 | tee "$VLLM_DIR/logs/vllm-phi-$(date +%Y%m%d-%H%M%S).log"
