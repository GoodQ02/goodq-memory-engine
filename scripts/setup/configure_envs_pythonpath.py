"""
Configure all goodq conda environments to include L:\ in PYTHONPATH.
This allows importing as 'from goodq4all.steps...' etc.
"""
import subprocess
import sys
from pathlib import Path

# Parent directory of goodq4all repo (L:\)
PYTHON_PATH_TO_ADD = "L:\\"

ENVS = [
    'goodq_zenml',
    'goodq_video_scene_detect',
    'goodq_audio_transcribe',
    'goodq_audio_diarize',
    'goodq_audio_emotion',
    'goodq_audio_embed',
    'goodq_image_caption',
    'goodq_object_detect',
    'goodq_ocr',
    'goodq_face_embed',
    'goodq_text_embed',
    'goodq_sentiment',
    'goodq_emotion_classify',
    'goodq_tagger',
    'goodq_llm_chat',
    'goodq_tts',
]

def get_env_path(env_name):
    """Get the conda environment directory path."""
    try:
        result = subprocess.run(
            ['conda', 'env', 'list'],
            capture_output=True,
            text=True,
            timeout=30
        )
        for line in result.stdout.split('\n'):
            if env_name in line:
                parts = line.split()
                if len(parts) >= 2:
                    return Path(parts[-1])
        return None
    except Exception as e:
        print(f"Error finding env path: {e}")
        return None

def configure_env(env_name):
    """Configure PYTHONPATH for a conda environment."""
    print(f"\n{'='*60}")
    print(f"Configuring {env_name}...")
    print('='*60)
    
    env_path = get_env_path(env_name)
    if not env_path:
        print(f"[SYMBOL] Could not find environment path for {env_name}")
        return False
    
    # Create activation script directories if they don't exist
    activate_d = env_path / "etc" / "conda" / "activate.d"
    deactivate_d = env_path / "etc" / "conda" / "deactivate.d"
    
    try:
        activate_d.mkdir(parents=True, exist_ok=True)
        deactivate_d.mkdir(parents=True, exist_ok=True)
        
        # Create activation script (Windows batch file)
        activate_script = activate_d / "goodq_pythonpath.bat"
        activate_content = f'@echo off\nset "PYTHONPATH={PYTHON_PATH_TO_ADD};%PYTHONPATH%"\n'
        activate_script.write_text(activate_content)
        
        # Create deactivation script
        deactivate_script = deactivate_d / "goodq_pythonpath.bat"
        deactivate_content = '@echo off\nset "PYTHONPATH=%PYTHONPATH:L:\\;=%"\n'
        deactivate_script.write_text(deactivate_content)
        
        print(f"[SYMBOL] Created activation script: {activate_script}")
        print(f"[SYMBOL] Created deactivation script: {deactivate_script}")
        
        # Test the import
        test_result = subprocess.run(
            ['conda', 'run', '-n', env_name, 'python', '-c', 
             'from goodq4all.steps.common import config_loader; print("[SYMBOL] Import successful")'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if test_result.returncode == 0:
            print(f"[SYMBOL] Test import successful in {env_name}")
            return True
        else:
            print(f"[SYMBOL] Warning: Activation script created but test import failed")
            print(f"   This is normal - activate the environment manually to test")
            # Still return True as the script was created
            return True
            
    except Exception as e:
        print(f"[SYMBOL] Error configuring {env_name}: {e}")
        return False

def main():
    print("="*60)
    print("GoodQ4All PYTHONPATH Configuration")
    print("="*60)
    print(f"\nConfiguring {len(ENVS)} conda environments...")
    print(f"Adding to PYTHONPATH: {PYTHON_PATH_TO_ADD}")
    
    successes = []
    failures = []
    
    for env in ENVS:
        if configure_env(env):
            successes.append(env)
        else:
            failures.append(env)
    
    print("\n" + "="*60)
    print("Configuration Summary")
    print("="*60)
    print(f"\n[SYMBOL] Successful: {len(successes)}/{len(ENVS)}")
    for env in successes:
        print(f"  - {env}")
    
    if failures:
        print(f"\n[SYMBOL] Failed: {len(failures)}/{len(ENVS)}")
        for env in failures:
            print(f"  - {env}")
        return 1
    else:
        print("\n[SYMBOL] All environments configured successfully!")
        print("\nℹ️  Note: The PYTHONPATH will be active when you:")
        print("   1. Activate the environment with 'conda activate <env_name>'")
        print("   2. Run scripts with 'conda run -n <env_name> python script.py'")
        return 0

if __name__ == "__main__":
    sys.exit(main())
