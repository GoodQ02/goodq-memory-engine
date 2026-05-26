"""
GPU Status and Diagnostics Tool
Comprehensive check of GPU availability and configuration
"""

import subprocess
import sys
from pathlib import Path


def check_nvidia_driver():
    """Check if NVIDIA drivers are installed"""
    print("\n" + "="*80)
    print("NVIDIA Driver Check")
    print("="*80)
    
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=driver_version,name,memory.total', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            driver_info = result.stdout.strip().split(',')
            print(f"[SYMBOL] Driver Version: {driver_info[0].strip()}")
            print(f"[SYMBOL] GPU Model: {driver_info[1].strip()}")
            print(f"[SYMBOL] Total Memory: {driver_info[2].strip()} MiB")
            return True
        else:
            print("[FAIL] nvidia-smi command failed")
            return False
    except FileNotFoundError:
        print("[FAIL] nvidia-smi not found - NVIDIA drivers may not be installed")
        return False
    except Exception as e:
        print(f"[FAIL] Error checking drivers: {e}")
        return False


def check_cuda_availability():
    """Check if CUDA is available in current Python environment"""
    print("\n" + "="*80)
    print("CUDA Availability Check")
    print("="*80)
    
    try:
        import torch
        
        print(f"[SYMBOL] PyTorch Version: {torch.__version__}")
        
        if torch.cuda.is_available():
            print(f"[SYMBOL] CUDA Available: Yes")
            print(f"[SYMBOL] CUDA Version: {torch.version.cuda}")
            print(f"[SYMBOL] cuDNN Version: {torch.backends.cudnn.version()}")
            print(f"[SYMBOL] Device Count: {torch.cuda.device_count()}")
            
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"\nGPU {i}: {torch.cuda.get_device_name(i)}")
                print(f"  Compute Capability: {props.major}.{props.minor}")
                print(f"  Total Memory: {props.total_memory / 1e9:.2f} GB")
                print(f"  Multi-Processors: {props.multi_processor_count}")
            
            return True
        else:
            print("[FAIL] CUDA Available: No")
            print("\nPossible reasons:")
            print("  - PyTorch was installed without CUDA support (CPU-only version)")
            print("  - CUDA libraries are not installed or not in PATH")
            print("  - GPU is not CUDA-compatible")
            print("\nTo install PyTorch with CUDA 12.4:")
            print("  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
            return False
            
    except ImportError:
        print("[FAIL] PyTorch not installed in this environment")
        print("\nInstall with:")
        print("  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
        return False
    except Exception as e:
        print(f"[FAIL] Error checking CUDA: {e}")
        return False


def check_gpu_utilization():
    """Check current GPU utilization"""
    print("\n" + "="*80)
    print("GPU Utilization")
    print("="*80)
    
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,utilization.memory,temperature.gpu,power.draw', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            gpu_util, mem_util, temp, power = result.stdout.strip().split(',')
            print(f"GPU Utilization: {gpu_util.strip()}%")
            print(f"Memory Utilization: {mem_util.strip()}%")
            print(f"Temperature: {temp.strip()}°C")
            print(f"Power Draw: {power.strip()}W")
            return True
        else:
            print("[FAIL] Could not get GPU utilization")
            return False
    except Exception as e:
        print(f"[FAIL] Error checking utilization: {e}")
        return False


def check_running_processes():
    """Check processes using GPU"""
    print("\n" + "="*80)
    print("GPU Processes")
    print("="*80)
    
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            processes = result.stdout.strip().split('\n')
            if processes and processes[0]:
                print(f"Found {len(processes)} process(es) using GPU:\n")
                for proc in processes:
                    if proc.strip():
                        pid, name, mem = [p.strip() for p in proc.split(',')]
                        print(f"  PID {pid}: {name} ({mem} MiB)")
            else:
                print("No compute processes currently using GPU")
            return True
        else:
            print("[FAIL] Could not get GPU processes")
            return False
    except Exception as e:
        print(f"[FAIL] Error checking processes: {e}")
        return False


def check_environment_variables():
    """Check relevant environment variables"""
    print("\n" + "="*80)
    print("Environment Variables")
    print("="*80)
    
    import os
    
    vars_to_check = [
        'CUDA_VISIBLE_DEVICES',
        'CUDA_PATH',
        'HF_HOME',
        'TORCH_HOME',
        'TRANSFORMERS_CACHE'
    ]
    
    for var in vars_to_check:
        value = os.environ.get(var)
        if value:
            print(f"[SYMBOL] {var}: {value}")
        else:
            print(f"  {var}: (not set)")
    
    return True


def main():
    print("="*80)
    print("GoodQ4All - GPU Diagnostics Tool")
    print("="*80)
    
    results = []
    
    # Run all checks
    results.append(("NVIDIA Drivers", check_nvidia_driver()))
    results.append(("CUDA Availability", check_cuda_availability()))
    results.append(("GPU Utilization", check_gpu_utilization()))
    results.append(("GPU Processes", check_running_processes()))
    results.append(("Environment Vars", check_environment_variables()))
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "[SYMBOL] PASS" if result else "[FAIL] FAIL"
        print(f"{status}: {check_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[OK] All checks passed! GPU is ready for use.")
        return 0
    else:
        print("\n[FAIL] Some checks failed. Review output above for details.")
        print("\nNext steps:")
        print("  1. If NVIDIA drivers failed: Install latest drivers from nvidia.com")
        print("  2. If CUDA failed: Run scripts\\setup_gpu_environments.bat")
        print("  3. Check documentation at docs/GPU_SETUP.md")
        return 1


if __name__ == '__main__':
    sys.exit(main())
