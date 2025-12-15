#!/bin/bash
# Test all downloaded vLLM models

echo "═══════════════════════════════════════════════════════════════"
echo "vLLM MODEL TESTING SCRIPT"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Test function
test_model() {
    local model_name=$1
    local port=$2
    local api_url="http://localhost:$port"
    
    echo "Testing: $model_name"
    echo "API URL: $api_url/v1/chat/completions"
    echo ""
    
    # Check if server is running
    if ! curl -s "$api_url/health" >/dev/null 2>&1; then
        echo "  ❌ Server not running on port $port"
        echo "     Start with: ~/vllm_server/scripts/start_${model_name}.sh"
        echo ""
        return 1
    fi
    
    echo "  ✅ Server is running"
    
    # Test OpenAI API
    echo "  Testing OpenAI API compatibility..."
    response=$(curl -s "$api_url/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'"$model_name"'",
            "messages": [{"role": "user", "content": "Say OK if you can read this"}],
            "max_tokens": 10
        }')
    
    if echo "$response" | grep -q "choices"; then
        echo "  ✅ OpenAI API working"
        message=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null)
        echo "  Response: $message"
    else
        echo "  ❌ OpenAI API failed"
        echo "  Response: $response"
    fi
    
    # Test inference speed
    echo "  Testing inference speed..."
    start_time=$(date +%s%N)
    curl -s "$api_url/v1/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'"$model_name"'",
            "prompt": "Count to 10:",
            "max_tokens": 50
        }' >/dev/null
    end_time=$(date +%s%N)
    duration=$(( (end_time - start_time) / 1000000 ))
    echo "  ⏱️  Response time: ${duration}ms"
    
    echo ""
}

# Test all models
echo "Checking which models are running..."
echo ""

test_model "qwen" 8000
test_model "phi" 8001
test_model "llama" 8002

echo "═══════════════════════════════════════════════════════════════"
echo "Testing complete!"
echo ""
echo "To start a model:"
echo "  Qwen:  ~/vllm_server/scripts/start_qwen.sh"
echo "  Phi:   ~/vllm_server/scripts/start_phi.sh"
echo "  Llama: ~/vllm_server/scripts/start_llama.sh (not downloaded)"
echo "═══════════════════════════════════════════════════════════════"
