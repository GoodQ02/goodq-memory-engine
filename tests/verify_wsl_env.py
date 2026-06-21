import os
import sys

def main():
    print("--- WSL Verification ---")
    print("GOODQ_OFFLINE:", os.environ.get("GOODQ_OFFLINE"))
    print("HF_HUB_OFFLINE:", os.environ.get("HF_HUB_OFFLINE"))
    print("TRANSFORMERS_OFFLINE:", os.environ.get("TRANSFORMERS_OFFLINE"))
    print("HF_HUB_CACHE:", os.environ.get("HF_HUB_CACHE"))
    print("GOODQ_WSL_AUDIO_CACHE_FALLBACK:", os.environ.get("GOODQ_WSL_AUDIO_CACHE_FALLBACK"))
    
    # Check cache directory
    cache_dir = os.environ.get("HF_HUB_CACHE")
    if cache_dir:
        exists = os.path.isdir(cache_dir)
        writable = os.access(cache_dir, os.W_OK) if exists else False
        print(f"Shared Cache Dir: {cache_dir}")
        print(f"  Exists: {exists}")
        print(f"  Writable: {writable}")
    else:
        print("HF_HUB_CACHE is not set (running in fallback local mode).")
        
    local_dir = os.path.expanduser("~/.cache/huggingface/hub")
    local_exists = os.path.isdir(local_dir)
    local_writable = os.access(local_dir, os.W_OK) if local_exists else os.access(os.path.expanduser("~"), os.W_OK)
    print(f"Local Fallback Dir: {local_dir}")
    print(f"  Exists: {local_exists}")
    print(f"  Writable: {local_writable}")

if __name__ == "__main__":
    main()
