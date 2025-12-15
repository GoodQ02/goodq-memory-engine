#!/bin/bash
# Start vLLM server with Qwen 2.5 7B Instruct

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VLLM_DIR="$(dirname "$SCRIPT_DIR")"

# Activate environment
source "$VLLM_DIR/venv/bin/activate"

# Set cuDNN path
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$VLLM_DIR/venv/lib/python3.12/site-packages/nvidia/cudnn/lib"

# Model configuration
MODEL_PATH="/mnt/l/_DATA/models/llm/huggingface/Qwen2.5-7B-Instruct"
PORT=8000

echo "═══════════════════════════════════════════════════════════════"
echo "Starting vLLM Server: Qwen 2.5 7B Instruct"
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
    --gpu-memory-utilization 0.90 \
    --dtype auto \
    --max-model-len 4096 \
    --enable-prefix-caching \
    2>&1 | tee "$VLLM_DIR/logs/vllm-qwen-$(date +%Y%m%d-%H%M%S).log"
