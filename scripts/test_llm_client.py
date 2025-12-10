#!/usr/bin/env python3
"""
GoodQ4All LLM Client Integration Test
Tests vLLM → Ollama → LMStudio fallback chain
"""

import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from llm_client import LLMClient
import json

def main():
    print("=" * 80)
    print("[LAUNCH] GoodQ4All LLM Client Integration Test")
    print("=" * 80)
    print()
    
    # Initialize client
    print("[LOG] Initializing LLM Client...")
    client = LLMClient()
    print(f"[OK] Client initialized with {len(client.MODELS)} models")
    print("   Configured models:")
    for model in client.MODELS:
        print(f"     - {model.name:25} @ {model.endpoint}")
    print()
    
    # Test 1: Health check all endpoints
    print("-" * 80)
    print("TEST 1: Health Check All Endpoints")
    print("-" * 80)
    health = client.check_all_health(force=True)
    
    for model_name, status in health.items():
        icon = "[OK]" if status.is_healthy else "[FAIL]"
        print(f"{icon} {model_name:25} - {'HEALTHY' if status.is_healthy else 'UNHEALTHY':10} ({status.response_time_ms:.0f}ms)")
        if status.last_error:
            print(f"   Error: {status.last_error}")
    
    healthy_count = sum(1 for s in health.values() if s.is_healthy)
    print(f"\n[STATS] {healthy_count}/{len(health)} models healthy")
    print()
    
    # Test 2: Simple chat completion
    print("-" * 80)
    print("TEST 2: Simple Chat Completion")
    print("-" * 80)
    test_message = "Hello! Please respond with a brief greeting."
    print(f"[SYMBOL] Sending: {test_message}")
    
    try:
        response = client.chat([{"role": "user", "content": test_message}])
        print(f"[OK] Response received:")
        print(f"   Model: {response.get('model', 'unknown')}")
        if 'choices' in response and len(response['choices']) > 0:
            message = response['choices'][0]['message']['content']
            print(f"   Message: {message[:200]}")
        print(f"   Tokens: {response.get('usage', {})}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    print()
    
    # Test 3: Multi-turn conversation
    print("-" * 80)
    print("TEST 3: Multi-turn Conversation")
    print("-" * 80)
    conversation = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "And if we multiply that by 3?"}
    ]
    
    try:
        response = client.chat(conversation)
        print(f"[OK] Multi-turn response:")
        if 'choices' in response and len(response['choices']) > 0:
            message = response['choices'][0]['message']['content']
            print(f"   Message: {message}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    print()
    
    # Test 4: Streaming response
    print("-" * 80)
    print("TEST 4: Streaming Response")
    print("-" * 80)
    print("[SYMBOL] Requesting stream...")
    
    try:
        response = client.chat(
            [{"role": "user", "content": "Count from 1 to 5"}],
            stream=True
        )
        print("[OK] Stream:")
        print("   ", end="")
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data = line_text[6:]
                    if data.strip() == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                print(content, end="", flush=True)
                    except:
                        pass
        print()
        print("[OK] Stream complete")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    print()
    
    # Test 5: Fallback mechanism
    print("-" * 80)
    print("TEST 5: Model Selection Strategies")
    print("-" * 80)
    
    try:
        # Test speed preference
        print("Testing prefer_speed...")
        response = client.chat(
            [{"role": "user", "content": "Hi"}],
            prefer_speed=True,
            max_tokens=10
        )
        print(f"[OK] Speed-preferred model: {response.get('model', 'unknown')}")
        
        # Test quality preference
        print("Testing prefer_quality...")
        response = client.chat(
            [{"role": "user", "content": "Hi"}],
            prefer_quality=True,
            max_tokens=10
        )
        print(f"[OK] Quality-preferred model: {response.get('model', 'unknown')}")
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    print()
    
    # Final Summary
    print("=" * 80)
    print("[STATS] TEST SUMMARY")
    print("=" * 80)
    status = client.get_status()
    print(f"[OK] Total Models: {status['models_total']}")
    print(f"[OK] Healthy Models: {status['models_healthy']}")
    print(f"[FAIL] Unhealthy Models: {status['models_unhealthy']}")
    print(f"[OK] Fallback Chain: {'OPERATIONAL' if status['models_healthy'] > 1 else 'LIMITED'}")
    print()
    print("[TARGET] Integration test complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
