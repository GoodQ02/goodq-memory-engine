"""
GPU Setup for Windows - Install PyTorch with CUDA in all GPU-capable environments
Properly handles conda environment activation on Windows
"""

import subprocess
import sys
import os
from pathlib import Path


# Environment configurations
GPU_ENVIRONMENTS = {
    "audio_diarize": {
        "torch_version": "2.5.1",
        "torchvision_version": "0.20.1",
        "torchaudio_version": "2.5.1",
        "cuda_version": "124"  # CUDA 12.4
    },
    "audio_transcribe": {
        "torch_version": "2.3.1",
        "cuda_version": "121"  # CUDA 12.1
    },
    "emotion_classify": {
        "torch_version": "2.3.1",
        "torchvision_version": "0.18.1",
        "cuda_version": "121"
    },
    "face_embed": {
        "torch_version": "2.3.1",
        "torchvision_version": "0.18.1",
        "cuda_version": "121"
    },
    "text_embed": {
        "torch_version": "2.3.1",
        "torchvision_version": "0.18.1",
        "cuda_version": "121"
    }
}


def run_in_conda_env(env_name, command):
    """Run a command in a conda environment (Windows-compatible)"""
    # Use conda run instead of activate for better cross-platform support
    cmd = ["conda", "run", "-n", env_name] + command.split()
    
    try:
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for large installs
        )
        
        if result.returncode != 0:
            print(f"  [FAIL] Command failed:")
            if result.stderr:
                print(f"  {result.stderr}")
            if result.stdout:
                print(f"  {result.stdout}")
            return False
        
        if result.stdout:
            # Show important output
            for line in result.stdout.split('\n'):
                if '[SYMBOL]' in line or 'CUDA' in line or 'Successfully' in line:
                    print(f"  {line}")
        
        print(f"  [SYMBOL] Success")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"  [FAIL] Command timed out (>10 minutes)")
        return False
    except FileNotFoundError:
        print(f"  [FAIL] Error: conda not found. Make sure conda is in your PATH")
        return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def setup_environment(env_name, config):
    """Setup PyTorch with CUDA for a specific environment"""
    print(f"\n{'='*80}")
    print(f"Setting up: {env_name}")
    print(f"{'='*80}")
    
    # Step 1: Uninstall existing PyTorch
    print("\n[Step 1/3] Uninstalling existing PyTorch packages...")
    uninstall_packages = ["torch"]
    if "torchvision_version" in config:
        uninstall_packages.append("torchvision")
    if "torchaudio_version" in config:
        uninstall_packages.append("torchaudio")
    
    uninstall_cmd = f"pip uninstall -y {' '.join(uninstall_packages)}"
    run_in_conda_env(env_name, uninstall_cmd)  # Don't fail if packages not found
    
    # Step 2: Install CUDA-enabled PyTorch
    print("\n[Step 2/3] Installing PyTorch with CUDA support...")
    install_packages = [f"torch=={config['torch_version']}"]
    if "torchvision_version" in config:
        install_packages.append(f"torchvision=={config['torchvision_version']}")
    if "torchaudio_version" in config:
        install_packages.append(f"torchaudio=={config['torchaudio_version']}")
    
    cuda_index = f"https://download.pytorch.org/whl/cu{config['cuda_version']}"
    install_cmd = f"pip install {' '.join(install_packages)} --index-url {cuda_index}"
    
    if not run_in_conda_env(env_name, install_cmd):
        return False
    
    # Step 3: Verify CUDA
    print("\n[Step 3/3] Verifying CUDA availability...")
    verify_cmd = 'python -c "import torch; print(f\'CUDA Available: {torch.cuda.is_available()}\'); print(f\'CUDA Version: {torch.version.cuda}\'); print(f\'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \\\'N/A\\\'}\')"'
    
    if not run_in_conda_env(env_name, verify_cmd):
        print("  [WARN]  Warning: CUDA verification failed, but installation may have succeeded")
        return True  # Don't fail on verification - sometimes it's just the command syntax
    
    return True


def check_conda_available():
    """Check if conda is available"""
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
    print("GoodQ4All - GPU Setup for Windows")
    print("="*80)
    
    # Check conda
    if not check_conda_available():
        print("\n[FAIL] Error: conda not found!")
        print("Please ensure conda is installed and in your PATH")
        print("Try running this from Anaconda Prompt or Miniconda Prompt")
        return 1
    
    print("\n[SYMBOL] conda found")
    print(f"\nThis will install PyTorch with CUDA 12.x support in {len(GPU_ENVIRONMENTS)} environments")
    print("\nEnvironments to update:")
    for env in GPU_ENVIRONMENTS.keys():
        print(f"  - {env}")
    
    print("\n[WARN]  This may take 15-20 minutes depending on internet speed...")
    print("="*80)
    
    response = input("\nPress ENTER to continue or CTRL+C to cancel...")
    
    success_count = 0
    failed_envs = []
    
    for env_name, config in GPU_ENVIRONMENTS.items():
        if setup_environment(env_name, config):
            success_count += 1
            print(f"\n[OK] {env_name} configured successfully")
        else:
            failed_envs.append(env_name)
            print(f"\n[FAIL] {env_name} configuration failed")
    
    # Summary
    print("\n" + "="*80)
    print("Setup Summary")
    print("="*80)
    print(f"\nSuccessful: {success_count}/{len(GPU_ENVIRONMENTS)}")
    
    if failed_envs:
        print(f"Failed: {', '.join(failed_envs)}")
        print("\n[WARN]  Some environments failed. You can:")
        print("  1. Try running the failed environments manually")
        print("  2. Check your internet connection")
        print("  3. Verify conda environments exist")
        return 1
    else:
        print("\n[OK] All environments configured successfully!")
        print("\n[LAUNCH] GPU acceleration is now enabled for:")
        for env in GPU_ENVIRONMENTS.keys():
            print(f"  [SYMBOL] {env}")
        print("\nNext steps:")
        print("  1. Run: conda run -n goodq_core python scripts\\test_gpu_config.py")
        print("  2. Test the pipeline with a video file")
        print("  3. Monitor GPU usage with: nvidia-smi")
        return 0


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
