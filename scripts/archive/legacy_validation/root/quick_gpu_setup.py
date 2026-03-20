"""
Quick GPU Setup - Install PyTorch with CUDA in all GPU-capable environments
This is a Python script that can be run directly to set up GPU support
"""

import subprocess
import sys
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


def run_command(cmd, env_name=None):
    """Run a command and return success status"""
    try:
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            print(f"  [FAIL] Command failed:")
            print(f"  {result.stderr}")
            return False
        
        print(f"  [SYMBOL] Success")
        return True
    except subprocess.TimeoutExpired:
        print(f"  [FAIL] Command timed out")
        return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def activate_and_run(env_name, commands):
    """Activate conda environment and run commands"""
    for cmd in commands:
        full_cmd = f"conda activate {env_name} && {cmd}"
        if not run_command([full_cmd], env_name):
            return False
    return True


def setup_environment(env_name, config):
    """Setup PyTorch with CUDA for a specific environment"""
    print(f"\n{'='*80}")
    print(f"Setting up: {env_name}")
    print(f"{'='*80}")
    
    # Build uninstall command
    uninstall_packages = ["torch"]
    if "torchvision_version" in config:
        uninstall_packages.append("torchvision")
    if "torchaudio_version" in config:
        uninstall_packages.append("torchaudio")
    
    # Build install command
    install_packages = [f"torch=={config['torch_version']}"]
    if "torchvision_version" in config:
        install_packages.append(f"torchvision=={config['torchvision_version']}")
    if "torchaudio_version" in config:
        install_packages.append(f"torchaudio=={config['torchaudio_version']}")
    
    cuda_index = f"https://download.pytorch.org/whl/cu{config['cuda_version']}"
    
    commands = [
        # Uninstall CPU-only versions
        f"pip uninstall -y {' '.join(uninstall_packages)}",
        # Install CUDA-enabled versions
        f"pip install {' '.join(install_packages)} --index-url {cuda_index}",
        # Verify CUDA works
        "python -c \"import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'[SYMBOL] CUDA {torch.version.cuda} on {torch.cuda.get_device_name(0)}')\"" 
    ]
    
    return activate_and_run(env_name, commands)


def main():
    print("="*80)
    print("GoodQ4All - Quick GPU Setup")
    print("="*80)
    print("\nThis will install PyTorch with CUDA support in GPU-capable environments")
    print(f"Environments to update: {len(GPU_ENVIRONMENTS)}")
    print("\nThis may take 10-15 minutes depending on internet speed...")
    print("="*80)
    
    input("\nPress ENTER to continue or CTRL+C to cancel...")
    
    success_count = 0
    failed_envs = []
    
    for env_name, config in GPU_ENVIRONMENTS.items():
        if setup_environment(env_name, config):
            success_count += 1
            print(f"[SYMBOL] {env_name} configured successfully")
        else:
            failed_envs.append(env_name)
            print(f"[FAIL] {env_name} configuration failed")
    
    # Summary
    print("\n" + "="*80)
    print("Setup Summary")
    print("="*80)
    print(f"\nSuccessful: {success_count}/{len(GPU_ENVIRONMENTS)}")
    
    if failed_envs:
        print(f"Failed: {', '.join(failed_envs)}")
        print("\n[FAIL] Some environments failed. Check errors above.")
        return 1
    else:
        print("\n[OK] All environments configured successfully!")
        print("\nGPU acceleration is now enabled for:")
        for env in GPU_ENVIRONMENTS.keys():
            print(f"  - {env}")
        print("\nYou can now run the pipeline with GPU acceleration")
        print("Test with: python scripts\\check_gpu_status.py")
        return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[FAIL] Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Setup failed: {e}")
        sys.exit(1)
