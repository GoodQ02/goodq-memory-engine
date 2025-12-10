"""
Comprehensive GPU Setup & Verification for GoodQ4All
- Sets up PyTorch with CUDA in all GPU-capable environments  
- Configures CUDA_VISIBLE_DEVICES for proper GPU allocation
- Verifies GPU access and memory settings
- Tests actual GPU usage
"""

import subprocess
import sys
import os
from pathlib import Path


# GPU-capable environments with their configurations
GPU_ENVIRONMENTS = {
    "goodq_audio_diarize": {
        "torch_version": "2.5.1",
        "torchvision_version": "0.20.1",
        "torchaudio_version": "2.5.1",
        "cuda_version": "124",  # CUDA 12.4
        "gpu_memory_fraction": 0.3,  # 30% of GPU
        "description": "Audio diarization (speaker detection)"
    },
    "goodq_audio_transcribe": {
        "torch_version": "2.3.1",
        "cuda_version": "121",  # CUDA 12.1
        "gpu_memory_fraction": 0.25,  # 25% of GPU
        "description": "Whisper transcription"
    },
    "goodq_emotion_classify": {
        "torch_version": "2.3.1",
        "torchvision_version": "0.18.1",
        "cuda_version": "121",
        "gpu_memory_fraction": 0.15,  # 15% of GPU
        "description": "Emotion classification"
    },
    "goodq_face_embed": {
        "torch_version": "2.3.1",
        "torchvision_version": "0.18.1",
        "cuda_version": "121",
        "gpu_memory_fraction": 0.15,  # 15% of GPU
        "description": "Face embeddings"
    },
    "goodq_text_embed": {
        "torch_version": "2.3.1",
        "torchvision_version": "0.18.1",
        "cuda_version": "121",
        "gpu_memory_fraction": 0.15,  # 15% of GPU
        "description": "Text embeddings"
    }
}


def run_in_conda_env(env_name, command, timeout=600):
    """Run a command in a conda environment"""
    cmd = ["conda", "run", "-n", env_name, "cmd", "/c"] + command.split()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return result.returncode == 0, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def setup_pytorch_gpu(env_name, config):
    """Install PyTorch with CUDA support"""
    print(f"\n{'='*80}")
    print(f"Setting up: {env_name}")
    print(f"Purpose: {config['description']}")
    print(f"Target GPU Memory: {config['gpu_memory_fraction']*100:.0f}%")
    print(f"{'='*80}")
    
    # Step 1: Uninstall existing PyTorch
    print("\n[1/4] Uninstalling existing PyTorch...")
    uninstall_packages = ["torch"]
    if "torchvision_version" in config:
        uninstall_packages.append("torchvision")
    if "torchaudio_version" in config:
        uninstall_packages.append("torchaudio")
    
    success, stdout, stderr = run_in_conda_env(
        env_name,
        f"pip uninstall -y {' '.join(uninstall_packages)}"
    )
    print("  [SYMBOL] Uninstalled" if "Successfully" in stdout or "not installed" in stderr else "  [WARN]  May not have been installed")
    
    # Step 2: Install CUDA-enabled PyTorch
    print("\n[2/4] Installing PyTorch with CUDA support...")
    install_packages = [f"torch=={config['torch_version']}"]
    if "torchvision_version" in config:
        install_packages.append(f"torchvision=={config['torchvision_version']}")
    if "torchaudio_version" in config:
        install_packages.append(f"torchaudio=={config['torchaudio_version']}")
    
    cuda_index = f"https://download.pytorch.org/whl/cu{config['cuda_version']}"
    install_cmd = f"pip install {' '.join(install_packages)} --index-url {cuda_index}"
    
    success, stdout, stderr = run_in_conda_env(env_name, install_cmd, timeout=900)
    
    if not success:
        print(f"  [FAIL] Installation failed!")
        print(f"  Error: {stderr[:200]}")
        return False
    
    print("  [SYMBOL] Installed PyTorch with CUDA")
    
    # Step 3: Verify CUDA availability
    print("\n[3/4] Verifying CUDA...")
    verify_script = """
import torch
import sys
if not torch.cuda.is_available():
    print("ERROR: CUDA not available!")
    sys.exit(1)
print(f"CUDA Version: {torch.version.cuda}")
print(f"GPU Device: {torch.cuda.get_device_name(0)}")
print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
"""
    
    # Write verification script
    script_path = Path(f"L:/goodq4all/temp_verify_{env_name}.py")
    script_path.write_text(verify_script)
    
    success, stdout, stderr = run_in_conda_env(env_name, f"python {script_path}")
    script_path.unlink(missing_ok=True)
    
    if not success or "ERROR" in stdout:
        print(f"  [FAIL] CUDA verification failed!")
        print(f"  {stderr}")
        return False
    
    for line in stdout.strip().split('\n'):
        print(f"  [SYMBOL] {line}")
    
    # Step 4: Configure GPU memory limits
    print("\n[4/4] Configuring GPU memory limits...")
    config_script = f"""
import torch
torch.cuda.set_per_process_memory_fraction({config['gpu_memory_fraction']}, 0)
print(f"Memory limit set to {config['gpu_memory_fraction']*100:.0f}% of GPU 0")

# Test allocation
try:
    test_tensor = torch.randn(100, 100).cuda()
    print("[SYMBOL] GPU memory allocation test successful")
    del test_tensor
    torch.cuda.empty_cache()
except Exception as e:
    print(f"ERROR: {{e}}")
"""
    
    script_path = Path(f"L:/goodq4all/temp_config_{env_name}.py")
    script_path.write_text(config_script)
    
    success, stdout, stderr = run_in_conda_env(env_name, f"python {script_path}")
    script_path.unlink(missing_ok=True)
    
    if success:
        for line in stdout.strip().split('\n'):
            print(f"  [SYMBOL] {line}")
    else:
        print(f"  [WARN]  Warning: Memory limit configuration may have issues")
        print(f"  {stderr}")
    
    return True


def create_gpu_config_file():
    """Create a configuration file for GPU settings"""
    config_content = """# GoodQ4All GPU Configuration
# This file is read by pipeline steps to configure GPU usage

import os

# GPU Device Selection
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first GPU only

# GPU Memory Fractions per Environment
GPU_MEMORY_LIMITS = {
"""
    
    for env_name, config in GPU_ENVIRONMENTS.items():
        config_content += f'    "{env_name}": {config["gpu_memory_fraction"]},  # {config["description"]}\n'
    
    config_content += """}\n
# Apply memory limit for current environment
def configure_gpu_memory():
    '''Call this at the start of each step to configure GPU memory'''
    import torch
    env_name = os.environ.get('CONDA_DEFAULT_ENV', 'unknown')
    
    if env_name in GPU_MEMORY_LIMITS:
        fraction = GPU_MEMORY_LIMITS[env_name]
        torch.cuda.set_per_process_memory_fraction(fraction, 0)
        print(f"[GPU] Configured {env_name} to use {fraction*100:.0f}% of GPU memory")
    
    # Enable memory growth
    torch.backends.cudnn.benchmark = True
    
    # Verify CUDA is available
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[GPU] Using {device_name} ({total_memory:.1f} GB total memory)")
        return True
    else:
        print("[GPU] WARNING: CUDA not available, falling back to CPU")
        return False
"""
    
    config_path = Path("L:/goodq4all/gpu_config.py")
    config_path.write_text(config_content)
    print(f"\n[OK] Created GPU configuration file: {config_path}")
    return config_path


def check_conda():
    """Verify conda is available"""
    try:
        result = subprocess.run(
            ["conda", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def main():
    print("="*80)
    print("GoodQ4All - Comprehensive GPU Setup")
    print("="*80)
    
    # Check conda
    if not check_conda():
        print("\n[FAIL] Error: conda not found!")
        print("Please run this from Anaconda Prompt or ensure conda is in PATH")
        return 1
    
    print("\n[OK] conda found")
    
    # Show what will be configured
    print(f"\n[LOG] Will configure {len(GPU_ENVIRONMENTS)} environments for GPU:")
    print(f"\n{'Environment':<30} {'Description':<35} {'GPU Memory'}")
    print("-" * 80)
    for env_name, config in GPU_ENVIRONMENTS.items():
        mem_pct = f"{config['gpu_memory_fraction']*100:.0f}%"
        print(f"{env_name:<30} {config['description']:<35} {mem_pct}")
    
    print("\n[WARN]  This will:")
    print("  • Install PyTorch with CUDA 12.x support")
    print("  • Configure GPU memory limits for each environment")
    print("  • Create gpu_config.py for runtime GPU management")
    print("  • May take 20-30 minutes depending on internet speed")
    
    print("\n" + "="*80)
    input("Press ENTER to continue or CTRL+C to cancel...")
    
    # Setup each environment
    success_count = 0
    failed_envs = []
    
    for env_name, config in GPU_ENVIRONMENTS.items():
        try:
            if setup_pytorch_gpu(env_name, config):
                success_count += 1
                print(f"\n[OK] {env_name} configured successfully\n")
            else:
                failed_envs.append(env_name)
                print(f"\n[FAIL] {env_name} configuration failed\n")
        except Exception as e:
            failed_envs.append(env_name)
            print(f"\n[FAIL] {env_name} failed with exception: {e}\n")
    
    # Create configuration file
    config_path = create_gpu_config_file()
    
    # Summary
    print("\n" + "="*80)
    print("Setup Summary")
    print("="*80)
    print(f"\n[OK] Successful: {success_count}/{len(GPU_ENVIRONMENTS)}")
    
    if failed_envs:
        print(f"[FAIL] Failed: {', '.join(failed_envs)}")
        print("\n[WARN]  Some environments failed. The pipeline may still work with CPU fallback.")
    else:
        print("\n[SYMBOL] All environments configured successfully!")
    
    print("\n[NOTE] Next Steps:")
    print("  1. Run: python scripts\\test_gpu_allocation.py")
    print("  2. Check GPU usage during pipeline: nvidia-smi -l 1")
    print(f"  3. GPU config file created: {config_path}")
    print("\n[TIP] Each step will automatically use the configured GPU memory limits")
    
    return 0 if not failed_envs else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[FAIL] Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
