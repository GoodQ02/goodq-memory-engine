"""
Test GPU allocation with a small video
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_gpu_pipeline():
    """Test GPU allocation throughout pipeline"""
    
    print("="*80)
    print("GPU Pipeline Test")
    print("="*80)
    
    # Import steps
    try:
        from steps.common.gpu_config import configure_gpu, print_memory_stats
        from steps.common.gpu_guard import GPUGuard
        
        guard = GPUGuard(max_fraction=0.85)
        
        print("\n1. Checking initial GPU state...")
        stats = guard.check_memory()
        if stats.get("available"):
            print(f"   GPU: {stats['allocated_gb']:.2f} / {stats['total_gb']:.2f} GB")
        
        print("\n2. Testing audio diarization allocation...")
        config = configure_gpu("audio_diarize", force_fraction=0.30)
        if config.get("available"):
            print(f"   [SYMBOL] Allocated {config['allocated_gb']:.2f} GB for diarization")
            print_memory_stats()
        
        print("\n3. Clearing cache...")
        guard.clear_cache_if_needed()
        
        print("\n4. Testing transcription allocation...")
        config = configure_gpu("audio_transcribe", force_fraction=0.25)
        if config.get("available"):
            print(f"   [SYMBOL] Allocated {config['allocated_gb']:.2f} GB for transcription")
        
        print("\n5. Final memory check...")
        stats = guard.check_memory()
        if stats.get("available"):
            print(f"   Memory safe: {stats.get('safe')}")
            print(f"   Used: {stats['reserved_pct']*100:.1f}%")
        
        print("\n" + "="*80)
        print("[SYMBOL] GPU allocation test complete!")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\n[SYMBOL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gpu_pipeline()
    sys.exit(0 if success else 1)
