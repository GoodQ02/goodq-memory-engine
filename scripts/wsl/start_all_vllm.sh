#!/bin/bash
###############################################################################
# GoodQ4All - Start All vLLM Servers
###############################################################################
# Starts all configured vLLM model servers in WSL with health checks
# Location: ~/goodq4all/scripts/wsl/start_all_vllm.sh
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VLLM_DIR="$HOME/vllm_server"
LOG_DIR="$VLLM_DIR/logs"
VENV="$VLLM_DIR/venv"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 GoodQ4All - Starting All vLLM Servers${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"

# Function to check if port is in use
port_in_use() {
    lsof -i:"$1" > /dev/null 2>&1
}

# Function to wait for server to be ready
wait_for_server() {
    local port=$1
    local max_wait=120  # Increased to 2 minutes for larger models
    local waited=0
    
    echo -e "${YELLOW}⏳ Waiting for server on port $port...${NC}"
    
    while [ $waited -lt $max_wait ]; do
        if curl -s "http://localhost:$port/v1/models" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Server on port $port is ready!${NC}"
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
        if [ $((waited % 30)) -eq 0 ]; then
            echo -e "${BLUE}   Still waiting... (${waited}s/${max_wait}s)${NC}"
        fi
    done
    
    echo -e "${RED}❌ Server on port $port failed to start within ${max_wait}s${NC}"
    return 1
}

# Function to start a vLLM server
start_vllm_server() {
    local name=$1
    local port=$2
    local model_path=$3
    local gpu_util=${4:-0.70}
    local max_len=${5:-8192}
    
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}Starting: $name (Port $port)${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────────────${NC}"
    
    # Check if port already in use
    if port_in_use "$port"; then
        echo -e "${YELLOW}⚠️  Port $port already in use - server may already be running${NC}"
        if curl -s "http://localhost:$port/v1/models" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Server responding - skipping${NC}"
            return 0
        else
            echo -e "${RED}❌ Port in use but server not responding - killing process${NC}"
            lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
            sleep 2
        fi
    fi
    
    # Activate venv and start server
    source "$VENV/bin/activate"
    
    local log_file="$LOG_DIR/$(echo $name | tr '[:upper:]' '[:lower:]' | tr ' ' '_').log"
    
    echo -e "${YELLOW}📝 Logging to: $log_file${NC}"
    
    nohup python3 -m vllm.entrypoints.openai.api_server \
        --model "$model_path" \
        --port "$port" \
        --host 0.0.0.0 \
        --tensor-parallel-size 1 \
        --dtype auto \
        --max-model-len "$max_len" \
        --gpu-memory-utilization "$gpu_util" \
        > "$log_file" 2>&1 &
    
    local pid=$!
    echo -e "${GREEN}🚀 Started with PID: $pid${NC}"
    
    # Wait for server to be ready
    if wait_for_server "$port"; then
        echo -e "${GREEN}✅ $name ready and serving!${NC}"
        return 0
    else
        echo -e "${RED}❌ $name failed to start${NC}"
        return 1
    fi
}

# Kill all existing vLLM processes
echo -e "${YELLOW}🧹 Cleaning up existing vLLM processes...${NC}"
pkill -f "vllm.entrypoints" 2>/dev/null || echo -e "${BLUE}No existing vLLM processes${NC}"
sleep 2

# Start servers (in order of resource usage - smallest first)
MODELS_DIR="/mnt/l/_DATA/models/llm/huggingface"

# 1. Llama 1B - Speed (Port 38005) - 2.3 GB VRAM - ALWAYS START (PRIMARY)
start_vllm_server "Llama-1B-Speed" 38005 \
    "$MODELS_DIR/Llama-3.2-1B-Instruct" 0.35 8192

# Check current VRAM usage before starting additional models
CURRENT_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
echo -e "${BLUE}Current VRAM usage: ${CURRENT_VRAM} MB${NC}"

# 2. Llama 3B - Balanced (Port 38004) - 6 GB VRAM - START IF ENOUGH VRAM
if [ "$CURRENT_VRAM" -lt 6000 ]; then
    start_vllm_server "Llama-3B-Balanced" 38004 \
        "$MODELS_DIR/Llama-3.2-3B-Instruct" 0.35 8192 || echo -e "${YELLOW}⚠️  Llama 3B failed, continuing...${NC}"
else
    echo -e "${YELLOW}⚠️  Skipping Llama 3B - insufficient VRAM (${CURRENT_VRAM}MB used)${NC}"
fi

# Update VRAM check
CURRENT_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)

# 3. Phi-3.5 Mini - Long Context (Port 38001) - 7 GB VRAM - OPTIONAL
if [ "$CURRENT_VRAM" -lt 10000 ]; then
    start_vllm_server "Phi-3.5-LongContext" 38001 \
        "$MODELS_DIR/Phi-3.5-mini-instruct" 0.30 131072 || echo -e "${YELLOW}⚠️  Phi-3.5 failed, continuing...${NC}"
else
    echo -e "${YELLOW}⚠️  Skipping Phi-3.5 - insufficient VRAM (${CURRENT_VRAM}MB used)${NC}"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 vLLM Server Startup Complete!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"

# Summary
echo ""
echo -e "${BLUE}📊 Server Status Summary:${NC}"
echo ""

check_server() {
    local port=$1
    local name=$2
    if curl -s "http://localhost:$port/v1/models" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $name (Port $port) - ONLINE${NC}"
        return 0
    else
        echo -e "${RED}❌ $name (Port $port) - OFFLINE${NC}"
        return 1
    fi
}

check_server 38005 "Llama-1B-Speed      "
check_server 38004 "Llama-3B-Balanced   "
check_server 38001 "Phi-3.5-LongContext "

echo ""
echo -e "${BLUE}📈 GPU Status:${NC}"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader

echo ""
echo -e "${BLUE}🔗 Endpoints:${NC}"
echo -e "  Primary (Speed):    http://localhost:38005/v1/"
echo -e "  Balanced:           http://localhost:38004/v1/"
echo -e "  Long Context:       http://localhost:38001/v1/"
echo -e "  Ollama Fallback:    http://localhost:31434/v1/"

echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo -e "  View all: tail -f $LOG_DIR/*.log"
echo -e "  Monitor:  watch -n 2 'ps aux | grep vllm'"

echo ""
echo -e "${BLUE}🛑 Stop All:${NC}"
echo -e "  pkill -f 'vllm.entrypoints'"

echo ""
echo -e "${GREEN}All servers started successfully! 🚀${NC}"
