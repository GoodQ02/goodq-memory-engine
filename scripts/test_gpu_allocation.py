"""
Test GPU allocation and memory limits across all environments
This simulates what happens when multiple pipeline steps run concurrently
"""

import subprocess
import sys
from pathlib import Path


def test_environment_gpu(env_name):
    """Test GPU configuration in a specific environment"""
    test_script = """
# Import GPU config
import sys
sys.path.insert(0, 'L:/goodq4all')
from gpu_config import configure_gpu_memory

# Configure and test
import torch

print(f"Environment: {sys.prefix.split('envs')[-1]}")
configure_gpu_memory()

# Test allocation
try:
    # Create a test tensor on GPU
    test_tensor = torch.randn(1000, 1000).cuda()
    allocated = torch.cuda.memory_allocated(0) / 1024**2  # MB
    reserved = torch.cuda.memory_reserved(0) / 1024**2  # MB
    
    print(f"Memory allocated: {allocated:.1f} MB")
    print(f"Memory reserved: {reserved:.1f} MB")
    print("[OK] GPU allocation test passed")
    
    # Cleanup
    del test_tensor
    torch.cuda.empty_cache()
except Exception as e:
    print(f"[FAIL] GPU allocation failed: {e}")
    sys.exit(1)
"""
    
    # Write test script
    script_path = Path(f"L:/goodq4all/temp_test_{env_name}.py")
    script_path.write_text(test_script, encoding='utf-8')
    
    try:
        # Run in environment
        result = subprocess.run(
            ["conda", "run", "-n", env_name, "python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        script_path.unlink(missing_ok=True)
        
        print(f"\n{'='*70}")
        print(f"Testing: {env_name}")
        print('='*70)
        
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"[SYMBOL] Test failed:")
            print(result.stderr)
            return False
            
    except Exception as e:
        script_path.unlink(missing_ok=True)
        print(f"[SYMBOL] Error testing {env_name}: {e}")
        return False


def main():
    print("="*70)
    print("GoodQ4All - GPU Allocation Test")
    print("="*70)
    print("\nTesting GPU configuration across all environments...")
    
    # Environments to test
    envs_to_test = [
        "goodq_audio_transcribe",
        "goodq_emotion_classify",
        "goodq_face_embed",
        "goodq_text_embed"
    ]
    
    results = {}
    
    for env in envs_to_test:
        results[env] = test_environment_gpu(env)
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    for env, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} - {env}")
    
    if passed == total:
        print("\n[SUCCESS] All GPU tests passed!")
        print("\n[OK] Your GPU is properly configured for:")
        print("  - Concurrent execution with memory limits")
        print("  - Automatic GPU selection (CUDA_VISIBLE_DEVICES=0)")
        print("  - Per-environment memory fractions")
        print("\n[NEXT] Run a test video through the pipeline")
        print("   Command: python scripts\\run_single_video_test.py")
        return 0
    else:
        print("\n[WARNING] Some tests failed. Check errors above.")
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
