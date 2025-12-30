#!/bin/bash
# Comprehensive vLLM infrastructure status

echo "═══════════════════════════════════════════════════════════════"
echo "📊 vLLM Infrastructure Status Report"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# GPU Status
echo "GPU Status:"
echo "-----------"
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader
echo ""

# All defined ports
PORTS=(8000 8001 8003 8004 8005)
MODELS=("Qwen2.5-7B-Instruct" "Phi-3.5-mini-instruct" "Llama-3.2-1B-Instruct" "Llama-3.2-3B-Instruct" "Llama-3.2-11B-Vision-Instruct")

echo "vLLM Servers:"
echo "-------------"
for i in "${!PORTS[@]}"; do
    PORT=${PORTS[$i]}
    MODEL_NAME=${MODELS[$i]}
    
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t 2>/dev/null)
        if curl -s --max-time 2 http://localhost:$PORT/v1/models >/dev/null 2>&1; then
            echo "✅ Port $PORT: $MODEL_NAME (PID: $PID) - READY"
        else
            echo "⏳ Port $PORT: $MODEL_NAME (PID: $PID) - STARTING"
        fi
    else
        echo "❌ Port $PORT: $MODEL_NAME - NOT RUNNING"
    fi
done

echo ""
echo "Ollama:"
echo "-------"
if curl -s http://localhost:31434/v1/models >/dev/null 2>&1; then
    MODEL=$(curl -s http://localhost:31434/v1/models | python3 -c "import sys, json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
    echo "✅ Port 31434: $MODEL - READY"
else
    echo "❌ Port 31434: NOT RUNNING"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
