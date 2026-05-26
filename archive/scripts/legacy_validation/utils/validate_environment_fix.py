"""
Validate that all environment fixes are working
"""
import os
import subprocess
import sys
from pathlib import Path

def test_conda_activation(env_name):
    """Test if conda environment can be activated"""
    try:
        # Use PowerShell to test activation
        cmd = f'conda activate {env_name} && python -c "import sys; print(sys.executable)"'
        result = subprocess.run(
            ['powershell', '-Command', cmd],
            capture_output=True,
            text=True,
            timeout=30,
            shell=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        else:
            return False, result.stderr
            
    except Exception as e:
        return False, str(e)


def main():
    print("="*80)
    print("  GoodQ4All - Environment Validation")
    print("="*80)
    print()
    
    # Key environments to test
    critical_envs = [
        'goodq_audio_diarize',
        'goodq_audio_transcribe',
        'goodq_video_scene_detect',
        os.environ.get("GOODQ_CONDA_ENV", "goodq_core")
    ]
    
    print("Testing critical environments...")
    print()
    
    all_passed = True
    
    for env_name in critical_envs:
        print(f"Testing: {env_name}...", end=" ")
        success, result = test_conda_activation(env_name)
        
        if success:
            print("[SYMBOL] PASS")
            print(f"  Python: {result}")
        else:
            print("[SYMBOL] FAIL")
            print(f"  Error: {result}")
            all_passed = False
        print()
    
    print("="*80)
    if all_passed:
        print("  [SYMBOL] All environments validated successfully!")
    else:
        print("  [SYMBOL] Some environments failed validation")
        print("  Please check conda environment installation")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
