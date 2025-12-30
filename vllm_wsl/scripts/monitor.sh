#!/bin/bash
# Quick monitoring script for vLLM and Ollama services

echo "═══════════════════════════════════════════════════════════════"
echo "🔍 LLM Infrastructure Monitor"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check vLLM
echo "vLLM Server (Port 8003):"
echo "------------------------"
if curl -s http://localhost:8003/v1/models >/dev/null 2>&1; then
    echo "✅ Status: Running"
    PID=$(ps aux | grep "vllm.entrypoints" | grep -v grep | awk '{print $2}')
    echo "   PID: $PID"
    MODEL=$(curl -s http://localhost:8003/v1/models | python3 -c "import sys, json; print(json.load(sys.stdin)['data'][0]['id'].split('/')[-1])" 2>/dev/null)
    echo "   Model: $MODEL"
    echo "   Endpoint: http://localhost:8003/v1/chat/completions"
else
    echo "❌ Status: Not running"
    echo "   Start: ~/vllm_server/scripts/start_llama1b.sh"
fi
echo ""

# Check Ollama
echo "Ollama Server (Port 31434):"
echo "---------------------------"
if curl -s http://localhost:31434/v1/models >/dev/null 2>&1; then
    echo "✅ Status: Running"
    PID=$(ps aux | grep "ollama serve" | grep -v grep | awk '{print $2}')       
    echo "   PID: $PID"
    MODEL=$(curl -s http://localhost:31434/v1/models | python3 -c "import sys, json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
    echo "   Model: $MODEL"
    echo "   Endpoint: http://localhost:31434/v1/chat/completions"
else
    echo "❌ Status: Not running"
    echo "   Start: sudo systemctl start ollama"
fi
echo ""

# Check GPU
echo "GPU Resources:"
echo "--------------"
GPU_INFO=$(nvidia-smi --query-gpu=name,memory.used,memory.free,utilization.gpu --format=csv,noheader)
NAME=$(echo "$GPU_INFO" | cut -d',' -f1)
USED=$(echo "$GPU_INFO" | cut -d',' -f2 | xargs)
FREE=$(echo "$GPU_INFO" | cut -d',' -f3 | xargs)
UTIL=$(echo "$GPU_INFO" | cut -d',' -f4 | xargs)

echo "   Device: $NAME"
echo "   VRAM Used: $USED"
echo "   VRAM Free: $FREE"
echo "   Utilization: $UTIL"
echo ""

# Active connections
echo "Recent Activity:"
echo "----------------"
if [ -f ~/vllm_server/logs/llama1b.log ]; then
    REQUESTS=$(grep -c "POST /v1/chat/completions" ~/vllm_server/logs/llama1b.log 2>/dev/null || echo "0")
    echo "   Total vLLM requests: $REQUESTS"
    LAST_REQUEST=$(grep "POST /v1/chat/completions" ~/vllm_server/logs/llama1b.log 2>/dev/null | tail -1 | awk '{print $2}' || echo "Never")
    echo "   Last request: $LAST_REQUEST"
else
    echo "   No log file found"
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "💡 Quick Commands:"
echo "   Restart vLLM:  ~/vllm_server/scripts/start_llama1b.sh"
echo "   Stop vLLM:     pkill -f vllm.entrypoints"
echo "   View logs:     tail -f ~/vllm_server/logs/llama1b.log"
echo "   GPU stats:     nvidia-smi"
echo "═══════════════════════════════════════════════════════════════"
