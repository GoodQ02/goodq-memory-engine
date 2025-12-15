#!/bin/bash
# Start vLLM server with Llama 3.2 11B Vision Instruct
# Multimodal model - vision + text

set -e

MODEL_PATH="/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-11B-Vision-Instruct"
PORT=8005
LOG_FILE="$HOME/vllm_server/logs/llama11b.log"

echo "═══════════════════════════════════════════════════════════════"
echo "🚀 Starting Llama 3.2 11B Vision Instruct vLLM Server"
echo "═══════════════════════════════════════════════════════════════"
echo "Model: Llama-3.2-11B-Vision-Instruct"
echo "Port: $PORT"
echo "Performance: ~40-50 tok/s (multimodal)"
echo "VRAM: ~12-14 GB"
echo "Log: $LOG_FILE"
echo "Features: Vision + Text understanding"
echo "═══════════════════════════════════════════════════════════════"

# Check if already running
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Port $PORT already in use!"
    echo "Stop existing server: pkill -f 'vllm.entrypoints'"
    exit 1
fi

# Check model exists
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ Model not found: $MODEL_PATH"
    exit 1
fi

# Activate venv if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    source ~/vllm_server/venv/bin/activate
fi

# Create logs directory
mkdir -p ~/vllm_server/logs

echo ""
echo "Starting vLLM server (this will take ~60-90 seconds)..."
echo "Logs: tail -f $LOG_FILE"
echo ""

# Start server in background with nohup
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --port $PORT \
    --host 0.0.0.0 \
    --tensor-parallel-size 1 \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.80 \
    --limit-mm-per-prompt image=1 \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"
echo "Waiting for server to be ready..."

# Wait for server to be ready (max 120 seconds)
for i in {1..120}; do
    sleep 1
    if curl -s http://localhost:$PORT/v1/models >/dev/null 2>&1; then
        echo ""
        echo "✅ vLLM server is ready!"
        echo "   API endpoint: http://localhost:$PORT/v1"
        echo "   Test: curl http://localhost:$PORT/v1/models"
        echo "   Supports: Images + Text prompts"
        echo ""
        exit 0
    fi
    echo -n "."
done

echo ""
echo "⏳ Server taking longer than expected. Check logs:"
echo "   tail -f $LOG_FILE"
echo ""
