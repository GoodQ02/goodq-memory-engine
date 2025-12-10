"""
Comprehensive Vision GPU Setup Script
Installs CUDA-enabled PyTorch for all vision-related environments
"""

import subprocess
import sys
import time
import os

# Prefer a WSL/Unix-friendly conda hook so we don't hit "Run 'conda init' before 'conda activate'"
CONDA_SH = os.path.expanduser("~/miniconda3/etc/profile.d/conda.sh")

def run_command(cmd, env_name=None):
    """Run a command and return success status"""
    try:
        if env_name:
            # Use bash -lc with an explicit conda hook to avoid "Run 'conda init' before 'conda activate'"
            if os.path.isfile(CONDA_SH):
                activate_cmd = f"bash -lc 'source \"{CONDA_SH}\" && conda activate {env_name} && {cmd}'"
            else:
                activate_cmd = f"conda activate {env_name} && {cmd}"
            result = subprocess.run(
                activate_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600
            )
        else:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600
            )
        
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def install_torch_for_env(env_name, retry_count=3):
    """Install CUDA PyTorch for a specific environment with retries"""
    print(f"\n{'='*80}")
    print(f"Installing CUDA PyTorch for: {env_name}")
    print(f"{'='*80}\n")
    
    for attempt in range(retry_count):
        if attempt > 0:
            print(f"  Retry attempt {attempt + 1}/{retry_count}...")
            time.sleep(5)
        
        # Step 1: Clean up any partial downloads
        print("  [1/4] Cleaning pip cache...")
        run_command("pip cache purge", env_name)
        
        # Step 2: Uninstall existing torch (if any)
        print("  [2/4] Removing existing PyTorch...")
        run_command("pip uninstall -y torch torchvision torchaudio", env_name)
        
        # Step 3: Install CUDA PyTorch (pinned, CUDA 12.1 to match working stack)
        print("  [3/4] Installing CUDA PyTorch (cu121, pinned)...")
        success, stdout, stderr = run_command(
            "pip install --no-cache-dir "
            "torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1 "
            "--extra-index-url https://download.pytorch.org/whl/cu121",
            env_name
        )
        
        if not success:
            print(f"  [FAIL] Installation failed: {stderr[:200]}")
            continue
        
        # Step 4: Verify installation
        print("  [4/4] Verifying installation...")
        success, stdout, stderr = run_command(
            "python -c \"import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \\\"CPU\\\"}')\"",
            env_name
        )
        
        if success:
            print(f"\n[OK] {env_name} - CUDA PyTorch installed successfully!")
            print(stdout)
            return True
        else:
            print(f"  [FAIL] Verification failed: {stderr[:200]}")
    
    print(f"\n[FAIL] {env_name} - Failed after {retry_count} attempts")
    return False

def main():
    """Main execution"""
    print("="*80)
    print("GoodQ4All - Vision GPU Setup")
    print("="*80)
    print("\nThis will install CUDA-enabled PyTorch for all vision environments")
    print("Estimated time: 10-20 minutes per environment\n")
    
    # List of vision environments to update
    vision_envs = [
        "goodq_face_embed",
        "goodq_emotion_classify",
        "goodq_video_scene_detect"
    ]
    
    print(f"Environments to update: {len(vision_envs)}")
    for env in vision_envs:
        print(f"  - {env}")
    
    input("\nPress ENTER to continue or CTRL+C to cancel...")
    
    results = {}
    for env in vision_envs:
        results[env] = install_torch_for_env(env)
    
    # Summary
    print("\n" + "="*80)
    print("Installation Summary")
    print("="*80)
    
    successful = [env for env, success in results.items() if success]
    failed = [env for env, success in results.items() if not success]
    
    if successful:
        print(f"\n[OK] Successful ({len(successful)}):")
        for env in successful:
            print(f"   - {env}")
    
    if failed:
        print(f"\n[FAIL] Failed ({len(failed)}):")
        for env in failed:
            print(f"   - {env}")
    
    print("\n" + "="*80)
    
    if len(successful) == len(vision_envs):
        print("[SYMBOL] All vision environments configured successfully!")
        return 0
    else:
        print("[WARN]  Some environments failed. Check errors above.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[FAIL] Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FAIL] Unexpected error: {e}")
        sys.exit(1)
