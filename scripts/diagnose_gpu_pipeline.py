"""
Comprehensive GPU Pipeline Diagnostic Tool
Identifies why GPU is not being utilized properly during processing
"""
import os
import sys
import json
import psutil
import subprocess
from pathlib import Path

def check_gpu_availability():
    """Check if GPU is available to PyTorch"""
    print("\n" + "="*80)
    print("GPU AVAILABILITY CHECK")
    print("="*80)
    
    try:
        import torch
        print(f"✓ PyTorch version: {torch.__version__}")
        print(f"✓ CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✓ CUDA version: {torch.version.cuda}")
            print(f"✓ Device count: {torch.cuda.device_count()}")
            print(f"✓ Current device: {torch.cuda.current_device()}")
            print(f"✓ Device name: {torch.cuda.get_device_name(0)}")
            print(f"✓ Device capability: {torch.cuda.get_device_capability(0)}")
            mem_total = torch.cuda.get_device_properties(0).total_memory / 1e9
            mem_alloc = torch.cuda.memory_allocated(0) / 1e9
            mem_reserved = torch.cuda.memory_reserved(0) / 1e9
            print(f"✓ Total VRAM: {mem_total:.2f} GB")
            print(f"✓ Allocated: {mem_alloc:.2f} GB ({mem_alloc/mem_total*100:.1f}%)")
            print(f"✓ Reserved: {mem_reserved:.2f} GB ({mem_reserved/mem_total*100:.1f}%)")
        else:
            print("✗ CUDA not available!")
            return False
    except Exception as e:
        print(f"✗ Error checking PyTorch: {e}")
        return False
    
    return True

def check_nvidia_smi():
    """Check NVIDIA GPU status"""
    print("\n" + "="*80)
    print("NVIDIA GPU STATUS")
    print("="*80)
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, check=True
        )
        print(result.stdout.strip())
    except Exception as e:
        print(f"✗ Error running nvidia-smi: {e}")
        return False
    
    return True

def check_cuda_processes():
    """Check which processes are using CUDA"""
    print("\n" + "="*80)
    print("CUDA PROCESSES")
    print("="*80)
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv"],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        if not output or "pid" in output.lower() and len(output.split('\n')) <= 1:
            print("⚠ No CUDA processes currently running!")
        else:
            print(output)
    except Exception as e:
        print(f"✗ Error checking CUDA processes: {e}")
        return False
    
    return True

def check_python_processes():
    """Check all Python processes"""
    print("\n" + "="*80)
    print("PYTHON PROCESSES")
    print("="*80)
    
    python_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'memory_info', 'cpu_percent']):
        try:
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                python_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not python_procs:
        print("⚠ No Python processes running!")
        return False
    
    for proc in python_procs:
        try:
            info = proc.info
            mem_mb = info['memory_info'].rss / 1024 / 1024 if info.get('memory_info') else 0
            cmdline = ' '.join(info.get('cmdline', []))[:100] if info.get('cmdline') else 'N/A'
            print(f"\nPID: {info['pid']}")
            print(f"  Memory: {mem_mb:.1f} MB")
            print(f"  CPU: {info.get('cpu_percent', 0):.1f}%")
            print(f"  Command: {cmdline}...")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return True

def check_env_variables():
    """Check CUDA-related environment variables"""
    print("\n" + "="*80)
    print("CUDA ENVIRONMENT VARIABLES")
    print("="*80)
    
    cuda_vars = [
        'CUDA_VISIBLE_DEVICES',
        'CUDA_DEVICE_ORDER',
        'CUDA_LAUNCH_BLOCKING',
        'TORCH_CUDA_ARCH_LIST',
        'PYTORCH_CUDA_ALLOC_CONF'
    ]
    
    for var in cuda_vars:
        value = os.environ.get(var, 'Not set')
        print(f"{var}: {value}")
    
    return True

def check_step_configs():
    """Check configuration of GPU-enabled steps"""
    print("\n" + "="*80)
    print("STEP GPU CONFIGURATION")
    print("="*80)
    
    base_dir = Path(__file__).parent.parent
    steps_dir = base_dir / "steps"
    
    gpu_steps = [
        'video_scene_detect',
        'audio_diarize',
        'audio_transcribe',
        'emotion_classify',
        'face_embed',
        'text_embed'
    ]
    
    for step_name in gpu_steps:
        step_dir = steps_dir / step_name
        if not step_dir.exists():
            print(f"⚠ {step_name}: Directory not found")
            continue
        
        step_file = step_dir / "step.py"
        if not step_file.exists():
            print(f"⚠ {step_name}: step.py not found")
            continue
        
        # Check for GPU usage in code
        code = step_file.read_text(encoding='utf-8')
        has_cuda = 'cuda' in code.lower() or 'gpu' in code.lower()
        has_device = 'device' in code.lower()
        
        print(f"\n{step_name}:")
        print(f"  CUDA references: {'✓' if has_cuda else '✗'}")
        print(f"  Device references: {'✓' if has_device else '✗'}")
    
    return True

def check_current_processing():
    """Check what's currently being processed"""
    print("\n" + "="*80)
    print("CURRENT PROCESSING STATUS")
    print("="*80)
    
    base_dir = Path(__file__).parent.parent
    
    # Check processing directory
    processing_dir = base_dir / "data" / "processing"
    if processing_dir.exists():
        items = list(processing_dir.rglob("*"))
        if items:
            print(f"\nProcessing directory has {len(items)} items")
            for item in items[:10]:  # Show first 10
                if item.is_file():
                    size_mb = item.stat().st_size / 1024 / 1024
                    print(f"  {item.name}: {size_mb:.1f} MB")
        else:
            print("⚠ Processing directory is empty")
    
    # Check watchdog log
    watchdog_log = base_dir / "logs" / "watchdog.log"
    if watchdog_log.exists():
        print("\nLast 10 lines of watchdog.log:")
        lines = watchdog_log.read_text(encoding='utf-8').strip().split('\n')
        for line in lines[-10:]:
            print(f"  {line}")
    
    return True

def main():
    """Run all diagnostics"""
    print("="*80)
    print("GoodQ4All GPU Pipeline Diagnostic")
    print("="*80)
    
    checks = [
        ("GPU Availability", check_gpu_availability),
        ("NVIDIA GPU Status", check_nvidia_smi),
        ("CUDA Processes", check_cuda_processes),
        ("Python Processes", check_python_processes),
        ("Environment Variables", check_env_variables),
        ("Step Configurations", check_step_configs),
        ("Current Processing", check_current_processing),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n✗ Error in {name}: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    if not results.get("GPU Availability"):
        print("• GPU is not available to PyTorch - check CUDA installation")
    
    if results.get("GPU Availability") and not any("CUDA" in str(p) for p in results.get("CUDA Processes", "")):
        print("• GPU is available but not being used - check step GPU configuration")
        print("• Verify CUDA_VISIBLE_DEVICES is set correctly")
        print("• Check that models are being moved to GPU with .to(torch.device('cuda'))")
    
    if results.get("Python Processes") and not results.get("CUDA Processes"):
        print("• Python processes running but not using GPU")
        print("• This indicates GPU code is not being executed")
        print("• Check step implementations for device placement")
    
    print("\n" + "="*80)
    print("END OF DIAGNOSTIC")
    print("="*80)

if __name__ == "__main__":
    main()
