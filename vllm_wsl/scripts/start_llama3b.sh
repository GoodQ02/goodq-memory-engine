#!/bin/bash
# Start vLLM server with Llama 3.2 3B Instruct
# Balanced model - 82 tok/s

set -e

MODEL_PATH="/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-3B-Instruct"
PORT=8004
LOG_FILE="$HOME/vllm_server/logs/llama3b.log"

echo "═══════════════════════════════════════════════════════════════"
echo "🚀 Starting Llama 3.2 3B Instruct vLLM Server"
echo "═══════════════════════════════════════════════════════════════"
echo "Model: Llama-3.2-3B-Instruct"
echo "Port: $PORT"
echo "Performance: 82 tok/s (balanced)"
echo "VRAM: ~4.8 GB"
echo "Log: $LOG_FILE"
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
echo "Starting vLLM server (this will take ~55 seconds)..."
echo "Logs: tail -f $LOG_FILE"
echo ""

# Start server in background with nohup
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --port $PORT \
    --host 0.0.0.0 \
    --tensor-parallel-size 1 \
    --dtype auto \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.50 \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"
echo "Waiting for server to be ready..."

# Wait for server to be ready (max 90 seconds)
for i in {1..90}; do
    sleep 1
    if curl -s http://localhost:$PORT/v1/models >/dev/null 2>&1; then
        echo ""
        echo "✅ vLLM server is ready!"
        echo "   API endpoint: http://localhost:$PORT/v1"
        echo "   Test: curl http://localhost:$PORT/v1/models"
        echo ""
        exit 0
    fi
    echo -n "."
done

echo ""
echo "⏳ Server taking longer than expected. Check logs:"
echo "   tail -f $LOG_FILE"
echo ""
