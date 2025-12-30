#!/bin/bash
# Start all available vLLM servers intelligently
# Manages GPU memory and starts models based on priority and available VRAM

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "🚀 Starting All vLLM Servers"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating vLLM environment..."
    source ~/vllm_server/venv/bin/activate
fi

# Function to check if port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
}

# Function to get free GPU memory
get_free_vram() {
    nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits
}

# Function to wait for server to be ready
wait_for_server() {
    local port=$1
    local max_wait=$2
    local name=$3
    
    echo -n "Waiting for $name to be ready"
    for i in $(seq 1 $max_wait); do
        if curl -s --max-time 2 http://localhost:$port/v1/models >/dev/null 2>&1; then
            echo " ✅"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    echo " ⏳ (taking longer than expected)"
    return 1
}

echo "Current GPU Status:"
echo "-------------------"
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader
echo ""

# Stop any existing vLLM servers
if ps aux | grep "vllm.entrypoints" | grep -v grep >/dev/null; then
    echo "⚠️  Stopping existing vLLM servers..."
    pkill -f vllm.entrypoints
    sleep 5
    echo "✅ Stopped"
    echo ""
fi

FREE_VRAM=$(get_free_vram)
echo "Available VRAM: ${FREE_VRAM} MiB"
echo ""

# Strategy: Start models based on available memory
# Priority: Llama 1B (speed) + one quality model

echo "═══════════════════════════════════════════════════════════════"
echo "Starting servers (in background)..."
echo "═══════════════════════════════════════════════════════════════"
echo ""

SERVERS_STARTED=0

# 1. Always start Llama 1B (fastest, ~11-12 GB VRAM)
if ! port_in_use 8003; then
    echo "🚀 Starting Llama-3.2-1B-Instruct (Port 8003)..."
    ~/vllm_server/scripts/start_llama1b.sh &
    SERVERS_STARTED=$((SERVERS_STARTED + 1))
    sleep 5
fi

# Wait for Llama 1B to start
wait_for_server 8003 60 "Llama 1B"

# Check remaining memory
FREE_VRAM=$(get_free_vram)
echo ""
echo "Remaining VRAM: ${FREE_VRAM} MiB"
echo ""

# 2. If we have enough memory (>7 GB), start Phi-3.5 Mini
if [ $FREE_VRAM -gt 7000 ] && ! port_in_use 8001; then
    echo "🚀 Starting Phi-3.5-mini-instruct (Port 8001)..."
    ~/vllm_server/scripts/start_phi.sh >/dev/null 2>&1 &
    SERVERS_STARTED=$((SERVERS_STARTED + 1))
    sleep 5
    wait_for_server 8001 90 "Phi-3.5 Mini"
    
    FREE_VRAM=$(get_free_vram)
    echo ""
    echo "Remaining VRAM: ${FREE_VRAM} MiB"
    echo ""
fi

# 3. If we have enough memory (>5 GB), start Llama 3B
if [ $FREE_VRAM -gt 5000 ] && ! port_in_use 8004; then
    echo "🚀 Starting Llama-3.2-3B-Instruct (Port 8004)..."
    ~/vllm_server/scripts/start_llama3b.sh >/dev/null 2>&1 &
    SERVERS_STARTED=$((SERVERS_STARTED + 1))
    sleep 5
    wait_for_server 8004 90 "Llama 3B"
    
    FREE_VRAM=$(get_free_vram)
    echo ""
    echo "Remaining VRAM: ${FREE_VRAM} MiB"
    echo ""
fi

# 4. If we still have lots of memory (>14 GB), start Qwen (requires stopping others)
# This is unlikely with other models running
if [ $FREE_VRAM -gt 14000 ] && ! port_in_use 8000; then
    echo "🚀 Starting Qwen2.5-7B-Instruct (Port 8000)..."
    ~/vllm_server/scripts/start_qwen.sh >/dev/null 2>&1 &
    SERVERS_STARTED=$((SERVERS_STARTED + 1))
    sleep 5
    wait_for_server 8000 120 "Qwen 2.5 7B"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "📊 Final Status"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check all ports
ACTIVE=0
for port in 8000 8001 8003 8004 8005; do
    if curl -s --max-time 2 http://localhost:$port/v1/models >/dev/null 2>&1; then
        MODEL=$(curl -s http://localhost:$port/v1/models | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['data'][0]['id'].split('/')[-1] if '/' in d['data'][0]['id'] else d['data'][0]['id'])" 2>/dev/null)
        echo "✅ Port $port: $MODEL"
        ACTIVE=$((ACTIVE + 1))
    fi
done

echo ""
echo "GPU Status:"
nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu --format=csv,noheader | awk -F, '{print "  VRAM Used: " $1 " | Free: " $2 " | Util: " $3}'
echo ""

echo "Ollama Status:"
if curl -s http://localhost:31434/v1/models >/dev/null 2>&1; then
    MODEL=$(curl -s http://localhost:31434/v1/models | python3 -c "import sys, json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
    echo "  ✅ Port 31434: $MODEL"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Startup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Active vLLM Servers: $ACTIVE"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8003/v1/models  # Llama 1B (fastest)"
echo "  curl http://localhost:8001/v1/models  # Phi-3.5 (long context)"
echo "  curl http://localhost:8004/v1/models  # Llama 3B (balanced)"
echo ""
echo "Monitor:"
echo "  ~/vllm_server/scripts/test_debug.sh"
echo "  ~/vllm_server/scripts/status_all.sh"
echo ""
