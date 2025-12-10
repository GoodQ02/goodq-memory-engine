"""
Quick GPU Test - Verify GPU configuration is working
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from steps.common.gpu_config import configure_gpu, get_device, print_memory_stats, clear_cache

def test_gpu_config():
    print("\n" + "="*80)
    print("Testing GPU Configuration")
    print("="*80 + "\n")
    
    # Test auto-configuration
    print("1. Auto-configuration (from import):\n")
    from steps.common import gpu_config
    print(f"   Config: {gpu_config._gpu_config}\n")
    
    # Test manual configuration with different fractions
    test_steps = [
        ("audio_transcribe", 0.25),
        ("audio_diarize", 0.35),
        ("face_embed", 0.20),
    ]
    
    print("2. Testing different memory allocations:\n")
    for step_name, fraction in test_steps:
        print(f"\n   Testing {step_name} ({fraction*100:.0f}% VRAM):")
        config = configure_gpu(step_name, force_fraction=fraction)
        print(f"   Result: {config}")
        
        if config.get("available"):
            print_memory_stats()
            clear_cache()
    
    # Test device selection
    print("\n3. Device Selection Test:\n")
    device = get_device()
    print(f"   Selected device: {device}")
    
    # Try to allocate a small tensor
    try:
        import torch
        if torch.cuda.is_available():
            print("\n4. Tensor Allocation Test:\n")
            test_tensor = torch.randn(1000, 1000).to(device)
            print(f"   [SYMBOL] Successfully allocated tensor on {device}")
            print(f"   Tensor shape: {test_tensor.shape}")
            print_memory_stats()
            del test_tensor
            clear_cache()
            print(f"   [SYMBOL] Tensor freed, cache cleared")
        else:
            print("\n4. CUDA not available - skipping tensor test")
    except Exception as e:
        print(f"\n4. [FAIL] Tensor allocation failed: {e}")
    
    print("\n" + "="*80)
    print("GPU Configuration Test Complete")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_gpu_config()
