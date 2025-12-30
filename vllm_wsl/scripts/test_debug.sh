#!/bin/bash
# Comprehensive test and debug tool for GoodQ4All LLM infrastructure

echo "═══════════════════════════════════════════════════════════════"
echo "🔧 GoodQ4All LLM Infrastructure Test & Debug Tool"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output (if terminal supports it)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function with timeout
test_endpoint() {
    local port=$1
    local name=$2
    local timeout=${3:-3}
    
    echo -n "Testing $name (port $port)... "
    
    # Check if port is listening
    if ! ss -tlnp 2>&1 | grep -q ":$port "; then
        echo -e "${RED}❌ Port not listening${NC}"
        return 1
    fi
    
    # Try to get models
    response=$(timeout $timeout curl -s http://localhost:$port/v1/models 2>&1)
    if [ $? -eq 0 ] && echo "$response" | grep -q "object"; then
        model=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['data'][0]['id'].split('/')[-1] if '/' in d['data'][0]['id'] else d['data'][0]['id'])" 2>/dev/null)
        echo -e "${GREEN}✅ $model${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ Port listening but not responding${NC}"
        return 2
    fi
}

# Test chat completion
test_chat() {
    local port=$1
    local name=$2
    
    echo -n "Testing $name chat completion... "
    
    # Get model name first
    model=$(curl -s http://localhost:$port/v1/models | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['data'][0]['id'])" 2>/dev/null)
    
    if [ -z "$model" ]; then
        echo -e "${RED}❌ Cannot get model name${NC}"
        return 1
    fi
    
    response=$(timeout 10 curl -s http://localhost:$port/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"$model\",
        \"messages\": [{\"role\": \"user\", \"content\": \"Say: OK\"}],
        \"max_tokens\": 5
      }" 2>&1)
    
    if echo "$response" | grep -q "content"; then
        content=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:50])" 2>/dev/null)
        echo -e "${GREEN}✅ \"$content\"${NC}"
        return 0
    else
        echo -e "${RED}❌ Chat failed${NC}"
        return 1
    fi
}

echo "══════════════════════════════════════════════════════════"
echo "1. GPU Status"
echo "══════════════════════════════════════════════════════════"
nvidia-smi --query-gpu=name,memory.used,memory.free,utilization.gpu --format=csv,noheader
echo ""

echo "══════════════════════════════════════════════════════════"
echo "2. Service Health Check"
echo "══════════════════════════════════════════════════════════"
test_endpoint 8003 "Llama 1B (Speed)" 3
test_endpoint 8004 "Llama 3B (Balanced)" 5
test_endpoint 8001 "Phi-3.5 Mini (Long Context)" 3
test_endpoint 8000 "Qwen 2.5 7B (Quality)" 3
test_endpoint 31434 "Ollama Phi4 (Fallback)" 3
echo ""

echo "══════════════════════════════════════════════════════════"
echo "3. Chat Completion Tests"
echo "══════════════════════════════════════════════════════════"

# Test Llama 1B
if ss -tlnp 2>&1 | grep -q ":8003 "; then
    test_chat 8003 "Llama 1B"
fi

# Test Llama 3B
if ss -tlnp 2>&1 | grep -q ":8004 "; then
    test_chat 8004 "Llama 3B"
fi

# Test Ollama
if ss -tlnp 2>&1 | grep -q ":31434 "; then
    test_chat 31434 "Ollama"
fi

echo ""

echo "══════════════════════════════════════════════════════════"
echo "4. Process Information"
echo "══════════════════════════════════════════════════════════"
echo "vLLM Processes:"
ps aux | grep "vllm.entrypoints" | grep -v grep | awk '{print "  PID: " $2 " | Memory: " $4"% | " $11 " " $12 " " $13}' | head -5
echo ""
echo "Ollama Process:"
ps aux | grep "ollama serve" | grep -v grep | awk '{print "  PID: " $2 " | Memory: " $4"%"}'
echo ""

echo "══════════════════════════════════════════════════════════"
echo "5. Network Ports"
echo "══════════════════════════════════════════════════════════"
echo "Active LLM ports:"
ss -tlnp 2>&1 | grep -E ":(8000|8001|8003|8004|8005|31434)" | awk '{print "  " $4}' | sort
echo ""

echo "══════════════════════════════════════════════════════════"
echo "6. Recent Logs"
echo "══════════════════════════════════════════════════════════"
echo "Llama 1B last 3 lines:"
if [ -f ~/vllm_server/logs/llama-1b-speed.log ]; then
    tail -3 ~/vllm_server/logs/llama-1b-speed.log | sed 's/^/  /'
else
    echo "  No log file"
fi
echo ""

echo "Llama 3B last 3 lines:"
if [ -f ~/vllm_server/logs/llama-3b-balanced.log ]; then
    tail -3 ~/vllm_server/logs/llama-3b-balanced.log | sed 's/^/  /'
else
    echo "  No log file"
fi
echo ""

echo "══════════════════════════════════════════════════════════"
echo "7. Windows Connectivity Test"
echo "══════════════════════════════════════════════════════════"
echo "From Windows, test with:"
echo ""
echo "  curl http://localhost:8003/v1/models"
echo "  curl http://localhost:8004/v1/models"
echo "  curl http://localhost:31434/v1/models"
echo ""
echo "Or run the Control Agent:"
echo "  cd L:\\goodq4all"
echo "  python scripts\\run_control_agent.py"
echo ""

echo "══════════════════════════════════════════════════════════"
echo "8. Quick Actions"
echo "══════════════════════════════════════════════════════════"
echo "  Restart Llama 1B:  ~/vllm_server/scripts/start_llama1b.sh"
echo "  Restart Llama 3B:  ~/vllm_server/scripts/start_llama3b.sh"
echo "  Stop all vLLM:     pkill -f vllm.entrypoints"
echo "  Monitor logs:      tail -f ~/vllm_server/logs/*.log"
echo "  Re-run this test:  ~/vllm_server/scripts/test_debug.sh"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "✅ Test Complete"
echo "═══════════════════════════════════════════════════════════"
