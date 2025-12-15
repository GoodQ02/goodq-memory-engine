#!/bin/bash
# Start vLLM Server

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VLLM_DIR="$(dirname "$SCRIPT_DIR")"

# Source activation script
source "$VLLM_DIR/activate.sh"

# Default settings
MODEL_PATH="${1:-facebook/opt-125m}"  # Default to small test model
HOST="${VLLM_HOST:-0.0.0.0}"
PORT="${VLLM_PORT:-8000}"

echo "═══════════════════════════════════════════════════════════════"
echo "Starting vLLM Server"
echo "═══════════════════════════════════════════════════════════════"
echo "Model: $MODEL_PATH"
echo "Host: $HOST"
echo "Port: $PORT"
echo "GPU Memory Utilization: 90%"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Start vLLM server
vllm serve "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --gpu-memory-utilization 0.90 \
    --dtype auto \
    --max-model-len 4096 \
    --enable-prefix-caching \
    2>&1 | tee "$VLLM_LOGS_DIR/vllm-$(date +%Y%m%d-%H%M%S).log"
