#!/usr/bin/env python3
"""
GoodQ4All - LLM Connectivity Test
Tests all configured LLM endpoints from Windows
"""

import sys
import time
import requests
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from llm_client import LLMClient

def test_endpoint(url, name, timeout=5):
    """Test a single endpoint"""
    try:
        response = requests.get(f"{url}/models", timeout=timeout)
        if response.status_code == 200:
            print(f"[OK] {name:25s} - ONLINE  ({url})")
            return True
        else:
            print(f"[FAIL] {name:25s} - ERROR {response.status_code}  ({url})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] {name:25s} - CONNECTION REFUSED  ({url})")
        return False
    except requests.exceptions.Timeout:
        print(f"[FAIL] {name:25s} - TIMEOUT  ({url})")
        return False
    except Exception as e:
        print(f"[FAIL] {name:25s} - ERROR: {e}")
        return False

def main():
    print("\n" + "="*70)
    print(" GoodQ4All - LLM Connectivity Test")
    print("="*70 + "\n")
    
    # Test individual endpoints
    print("Testing Individual Endpoints:")
    print("-" * 70)
    
    endpoints = [
        ("http://localhost:38005/v1", "Llama-1B-Speed"),
        ("http://localhost:38004/v1", "Llama-3B-Balanced"),
        ("http://localhost:38001/v1", "Phi-3.5-LongContext"),
        ("http://localhost:38000/v1", "Qwen-Quality"),
        ("http://localhost:11434/v1", "Ollama-Fallback"),
    ]
    
    results = []
    for url, name in endpoints:
        results.append(test_endpoint(url, name))
        time.sleep(0.2)
    
    print("\n" + "-" * 70)
    print(f"Results: {sum(results)}/{len(results)} endpoints online")
    print("-" * 70 + "\n")
    
    # Test LLMClient
    print("Testing LLMClient Integration:")
    print("-" * 70)
    
    try:
        client = LLMClient()
        print(f"[OK] LLMClient initialized")
        print(f"   - {len(client.MODELS)} models configured")
        healthy = client.get_healthy_models()
        print(f"   - {len(healthy)} models healthy: {[m.name for m in healthy]}")
        
        # Try to chat
        print("\nTesting Chat Completion:")
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'Hello from GoodQ4All!' in 10 words or less."}],
            max_tokens=30
        )
        
        if response:
            print(f"[OK] Chat successful!")
            # Response is a dict with 'choices' key
            content = response.get('choices', [{}])[0].get('message', {}).get('content', str(response))
            print(f"   Response: {content[:150]}...")
            print("\n" + "="*70)
            print("[SYMBOL] LLM Infrastructure is OPERATIONAL!")
            print("="*70)
            return 0
        else:
            print(f"[FAIL] Chat failed - no healthy models")
            return 1
            
    except Exception as e:
        print(f"[FAIL] LLMClient error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
