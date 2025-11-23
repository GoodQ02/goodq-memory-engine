#!/bin/bash
# ============================================================================
# GoodQ4All - WSL System Monitor
# ============================================================================

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function monitor-all() {
    echo -e "${BLUE}=== GoodQ4All Service Status ===${NC}"
    echo ""
    
    echo -e "${YELLOW}vLLM Service:${NC}"
    sudo systemctl status vllm-llama1b.service --no-pager | head -15
    echo ""
    
    echo -e "${YELLOW}API Endpoints:${NC}"
    curl -s http://localhost:38005/v1/models > /dev/null 2>&1 && echo -e "  ✅ vLLM @ localhost:38005" || echo -e "  ❌ vLLM @ localhost:38005"
    curl -s http://localhost:31434/v1/models > /dev/null 2>&1 && echo -e "  ✅ Ollama @ localhost:31434" || echo -e "  ❌ Ollama @ localhost:31434"
    echo ""
    
    echo -e "${YELLOW}GPU Status:${NC}"
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "  No GPU detected"
    echo ""
}

function monitor-gpu() {
    echo -e "${BLUE}=== GPU Monitoring (Ctrl+C to exit) ===${NC}"
    echo ""
    watch -n 1 nvidia-smi
}

function monitor-vllm() {
    echo -e "${BLUE}=== vLLM Logs (Ctrl+C to exit) ===${NC}"
    echo ""
    tail -f ~/vllm_server/logs/vllm-service.log
}

function monitor-ports() {
    echo -e "${BLUE}=== Port Usage ===${NC}"
    echo ""
    echo -e "${YELLOW}GoodQ4All Ports:${NC}"
    sudo netstat -tlnp 2>/dev/null | grep -E ':(38000|38001|38004|38005|31434|36335)' || echo "  No services detected"
    echo ""
}

# Show initial status
monitor-all

# Export functions for interactive use
export -f monitor-all monitor-gpu monitor-vllm monitor-ports

echo -e "${GREEN}"
echo "Monitor commands available:"
echo "  monitor-all      - Show all service status"
echo "  monitor-gpu      - Watch GPU utilization"
echo "  monitor-vllm     - Tail vLLM logs"
echo "  monitor-ports    - Show port usage"
echo -e "${NC}"
