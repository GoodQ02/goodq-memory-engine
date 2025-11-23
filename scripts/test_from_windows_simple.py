"""Simple test to check if Windows can reach vLLM"""
import requests
import sys

print("Testing Windows → vLLM connectivity...")
print("=" * 60)

urls = [
    "http://localhost:38005/v1/models",
    "http://127.0.0.1:38005/v1/models",
]

for url in urls:
    print(f"\nTrying: {url}")
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"  ✅ SUCCESS!")
            data = response.json()
            model = data['data'][0]['id'].split('/')[-1]
            print(f"  Model: {model}")
            sys.exit(0)
        else:
            print(f"  ❌ HTTP {response.status_code}")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ Connection refused or blocked")
    except requests.exceptions.Timeout:
        print(f"  ❌ Timeout (server not responding)")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "=" * 60)
print("❌ Could not connect to vLLM")
print("\nTroubleshooting:")
print("  1. Check Windows Firewall")
print("  2. Try: wsl --shutdown (then restart)")
print("  3. Verify from WSL: curl http://localhost:38005/v1/models")
