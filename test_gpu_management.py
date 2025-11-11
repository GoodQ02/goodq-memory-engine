"""
Test GPU Resource Management Implementation
Validates that GPU isolation and memory management are working correctly
"""

import sys
from pathlib import Path

# Add parent to path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def test_gpu_availability():
    """Test 1: Check if GPU is available"""
    print("\n" + "="*80)
    print("TEST 1: GPU Availability Check")
    print("="*80)
    
    from common.gpu_monitor import get_gpu_availability
    
    avail = get_gpu_availability()
    print(f"\nGPU Available: {avail.get('available')}")
    if avail.get('available'):
        print(f"GPU ID: {avail.get('gpu_id')}")
        print(f"GPU Name: {avail.get('name')}")
        print(f"Total Memory: {avail.get('memory_total_mb')} MB")
    else:
        print(f"Reason: {avail.get('reason')}")
    
    return avail.get('available', False)


def test_gpu_manager_init():
    """Test 2: Initialize GPU Manager"""
    print("\n" + "="*80)
    print("TEST 2: GPU Manager Initialization")
    print("="*80)
    
    try:
        from common.gpu_manager import GPUManager
        
        # Create manager with 60% memory allocation
        manager = GPUManager(
            gpu_id=0,
            memory_fraction=0.6,
            enable_determinism=False
        )
        
        # Initialize
        success = manager.initialize()
        print(f"\nInitialization: {'SUCCESS' if success else 'FAILED'}")
        
        # Get memory stats
        stats = manager.get_memory_stats()
        print("\nMemory Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Get device
        device = manager.get_device()
        print(f"\nCompute Device: {device}")
        
        return success
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gpu_config_loading():
    """Test 3: Load GPU Configuration"""
    print("\n" + "="*80)
    print("TEST 3: GPU Configuration Loading")
    print("="*80)
    
    try:
        import yaml
        
        config_path = REPO_ROOT / 'config' / 'gpu_config.yaml'
        if not config_path.exists():
            print(f"\nERROR: Config file not found: {config_path}")
            return False
        
        with open(config_path, 'r') as f:
            gpu_config = yaml.safe_load(f)
        
        print("\nGPU Configuration:")
        print(f"  Device ID: {gpu_config.get('gpu', {}).get('device_id')}")
        print(f"  Deterministic: {gpu_config.get('gpu', {}).get('deterministic')}")
        print(f"  Exclusive Mode: {gpu_config.get('gpu', {}).get('exclusive_mode')}")
        
        print("\nStep Memory Fractions:")
        step_fractions = gpu_config.get('step_memory_fractions', {})
        for step, fraction in sorted(step_fractions.items()):
            print(f"  {step}: {fraction}")
        
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_environment_variables():
    """Test 4: Check Environment Variables"""
    print("\n" + "="*80)
    print("TEST 4: Environment Variables")
    print("="*80)
    
    import os
    
    env_vars = [
        'CUDA_VISIBLE_DEVICES',
        'HF_HOME',
        'TORCH_HOME',
        'PYTHONPATH',
        'CUBLAS_WORKSPACE_CONFIG',
        'PYTHONHASHSEED'
    ]
    
    print("\nEnvironment Variables:")
    for var in env_vars:
        value = os.environ.get(var, '<not set>')
        print(f"  {var}: {value}")
    
    return True


def test_torch_cuda():
    """Test 5: PyTorch CUDA Detection"""
    print("\n" + "="*80)
    print("TEST 5: PyTorch CUDA Detection")
    print("="*80)
    
    try:
        import torch
        
        print(f"\nPyTorch Version: {torch.__version__}")
        print(f"CUDA Available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"CUDA Version: {torch.version.cuda}")
            print(f"Device Count: {torch.cuda.device_count()}")
            print(f"Current Device: {torch.cuda.current_device()}")
            print(f"Device Name: {torch.cuda.get_device_name(0)}")
            
            # Get memory info
            props = torch.cuda.get_device_properties(0)
            total_mem = props.total_memory / 1e9
            print(f"Total Memory: {total_mem:.2f} GB")
            
            allocated = torch.cuda.memory_allocated(0) / 1e9
            reserved = torch.cuda.memory_reserved(0) / 1e9
            print(f"Allocated: {allocated:.2f} GB")
            print(f"Reserved: {reserved:.2f} GB")
            
        return torch.cuda.is_available()
        
    except ImportError:
        print("\nERROR: PyTorch not installed")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_step_initialization():
    """Test 6: Simulate Step Initialization"""
    print("\n" + "="*80)
    print("TEST 6: Step Initialization Simulation")
    print("="*80)
    
    try:
        from common.gpu_manager import initialize_gpu_for_step
        
        # Simulate initializing a step
        step_name = "video_scene_detect"
        print(f"\nInitializing GPU for step: {step_name}")
        
        gpu_manager = initialize_gpu_for_step(
            step_name=step_name,
            memory_fraction=0.6,
            enable_determinism=False
        )
        
        # Get stats
        stats = gpu_manager.get_memory_stats()
        print("\nGPU Stats After Initialization:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Clear cache
        print("\nClearing GPU cache...")
        gpu_manager.clear_cache()
        
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("GPU RESOURCE MANAGEMENT TEST SUITE")
    print("="*80)
    
    results = {}
    
    # Run tests
    results['gpu_availability'] = test_gpu_availability()
    results['gpu_manager_init'] = test_gpu_manager_init()
    results['gpu_config_loading'] = test_gpu_config_loading()
    results['environment_variables'] = test_environment_variables()
    results['torch_cuda'] = test_torch_cuda()
    results['step_initialization'] = test_step_initialization()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("="*80)
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
