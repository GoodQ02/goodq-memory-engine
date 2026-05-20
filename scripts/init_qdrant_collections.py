"""
Initialize Qdrant collections for GoodQ4All.
Run this after starting Qdrant for the first time.
"""
import sys
import requests
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from steps.common.config_loader import load_configs
except ModuleNotFoundError:
    from goodq4all.steps.common.config_loader import load_configs


def wait_for_qdrant(host: str, max_retries: int = 10, delay: int = 2):
    """Wait for Qdrant to be ready."""
    print(f"[INFO] Waiting for Qdrant at {host}...")
    
    for i in range(max_retries):
        try:
            response = requests.get(f"{host.rstrip('/')}/collections", timeout=2)
            if response.status_code == 200:
                print(f"[OK] Qdrant is healthy!")
                return True
        except Exception as e:
            print(f"[WAIT] Attempt {i+1}/{max_retries}: {str(e)}")
            time.sleep(delay)
    
    print(f"[ERROR] Qdrant not responding after {max_retries} attempts")
    return False


def create_collection(host: str, name: str, dim: int, distance: str = "Cosine"):
    """Create a Qdrant collection."""
    url = f"{host}/collections/{name}"
    
    # Check if collection exists
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            print(f"[SKIP] Collection '{name}' already exists")
            return True
    except:
        pass
    
    # Create collection
    payload = {
        "vectors": {
            "size": dim,
            "distance": distance
        }
    }
    
    try:
        response = requests.put(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[OK] Created collection '{name}' (dim={dim}, distance={distance})")
            return True
        else:
            print(f"[ERROR] Failed to create '{name}': {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception creating '{name}': {e}")
        return False


def main():
    """Initialize all GoodQ4All collections."""
    print("\n" + "="*70)
    print("  GoodQ4All - Initialize Qdrant Collections")
    print("="*70 + "\n")
    
    # Load config
    config = load_configs({})
    
    qdrant_cfg = config.get('qdrant', {})
    
    if not qdrant_cfg.get('enabled', False):
        print("[ERROR] Qdrant is not enabled in config.yaml!")
        print("Set 'qdrant.enabled: true' in configs/config.yaml")
        return 1
    
    host = qdrant_cfg.get('host', 'http://localhost:6333')
    collections = qdrant_cfg.get('collections', {})
    dims = qdrant_cfg.get('embedding_dims', {})
    
    print(f"Qdrant Host: {host}")
    print(f"Collections to create: {len(collections)}\n")
    
    # Wait for Qdrant to be ready
    if not wait_for_qdrant(host):
        print("\n[ERROR] Cannot connect to Qdrant!")
        print("Make sure Qdrant is running:")
        print("  - Run: .\\START_QDRANT.bat")
        print("  - Or install service: INSTALL_QDRANT_SERVICE.bat (as Admin)")
        return 1
    
    print()
    
    # Create collections
    success_count = 0
    for key, collection_name in collections.items():
        dim = dims.get(key, 384)  # Default to 384 if not specified
        if create_collection(host, collection_name, dim):
            success_count += 1
    
    print("\n" + "="*70)
    print(f"  Initialization Complete: {success_count}/{len(collections)} collections created")
    print("="*70 + "\n")
    
    # Show collections
    try:
        response = requests.get(f"{host}/collections", timeout=3)
        if response.status_code == 200:
            result = response.json().get('result', {})
            all_collections = result.get('collections', [])
            
            print("Current collections:")
            for col in all_collections:
                name = col.get('name', 'unknown')
                print(f"  - {name}")
    except:
        pass
    
    print("\nQdrant is ready for ingestion!")
    print(f"Dashboard: {host}/dashboard\n")
    
    return 0 if success_count == len(collections) else 1


if __name__ == '__main__':
    sys.exit(main())
