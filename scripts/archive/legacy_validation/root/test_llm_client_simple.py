"""
Test LLM Client from Windows
Run this from Windows PowerShell: python L:\\goodq4all\\scripts\\test_llm_client_simple.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.llm_client import LLMClient

def test_llm_client():
    print("=" * 70)
    print("[SYMBOL] Testing LLM Client")
    print("=" * 70)
    print()
    
    # Initialize client
    print("1. Initializing LLM client...")
    try:
        client = LLMClient()
        print("   [OK] Client initialized")
        print(f"   [STATS] Models configured: {len(client.MODELS)}")
    except Exception as e:
        print(f"   [FAIL] Failed to initialize: {e}")
        return
    
    print()
    
    # Check health
    print("2. Checking model health...")
    status = client.get_status()
    print(f"   [STATS] Total models: {status['models_total']}")
    print(f"   [OK] Healthy: {status['models_healthy']}")
    print(f"   [FAIL] Unhealthy: {status['models_unhealthy']}")
    print()
    
    # Show health details
    for name, health in status['health_status'].items():
        if health['healthy']:
            print(f"   [OK] {name}: {health['response_time_ms']:.0f}ms")
        else:
            error = health.get('last_error', 'Unknown error')[:60]
            print(f"   [FAIL] {name}: {error}...")
    
    print()
    
    # Test chat
    print("3. Testing chat completion...")
    try:
        response = client.chat(
            messages=[
                {"role": "user", "content": "Say: Hello from Windows!"}
            ],
            max_tokens=20
        )
        
        print("   [OK] Chat successful!")
        print(f"   [BOT] Model used: {client.get_active_model()}")
        print(f"   [SYMBOL] Response: {response['choices'][0]['message']['content']}")
        print(f"   [STATS] Tokens: {response['usage']['total_tokens']}")
        
    except Exception as e:
        print(f"   [FAIL] Chat failed: {e}")
    
    print()
    print("=" * 70)
    print("[OK] Test complete!")
    print("=" * 70)

if __name__ == "__main__":
    test_llm_client()
