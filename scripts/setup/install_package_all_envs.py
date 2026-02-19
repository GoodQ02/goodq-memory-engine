"""
Install goodq4all package in editable mode across all conda environments.
This ensures all environments can import goodq4all.steps, goodq4all.lib, etc.
"""
import subprocess
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ENV = os.environ.get("GOODQ_CONDA_ENV", "goodq_core")

# List of all goodq conda environments that need the package
ENVS = [
    CORE_ENV,
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

def install_in_env(env_name):
    """Install goodq4all in editable mode in the specified conda environment."""
    print(f"\n{'='*60}")
    print(f"Installing goodq4all in {env_name}...")
    print('='*60)
    
    try:
        # Use pip install in editable mode
        result = subprocess.run(
            ['conda', 'run', '-n', env_name, 'pip', 'install', '-e', str(REPO_ROOT), '--no-deps'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print(f"[SYMBOL] SUCCESS: goodq4all installed in {env_name}")
            return True
        else:
            print(f"[SYMBOL] FAILED: {env_name}")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"[SYMBOL] ERROR installing in {env_name}: {e}")
        return False

def main():
    print("="*60)
    print("GoodQ4All Package Installation")
    print("="*60)
    print(f"\nInstalling in {len(ENVS)} conda environments...")
    
    successes = []
    failures = []
    
    for env in ENVS:
        if install_in_env(env):
            successes.append(env)
        else:
            failures.append(env)
    
    print("\n" + "="*60)
    print("Installation Summary")
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
        return 0

if __name__ == "__main__":
    sys.exit(main())
