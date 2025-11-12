#!/usr/bin/env python3
"""
Test and validate Python path configuration across the GoodQ4All system
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.python_paths import get_config, validate_env, get_env_python, get_conda_exe
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_path_configuration():
    """Test all Python path configuration"""
    print("="*80)
    print("  GoodQ4All Python Path Configuration Test")
    print("="*80)
    print()
    
    # Get configuration
    config = get_config()
    
    # Test 1: Conda base
    print("[TEST 1] Conda Base Installation")
    print(f"  Location: {config.conda_base}")
    print(f"  Status: {'✓ Found' if config.conda_base else '✗ Not found'}")
    print()
    
    # Test 2: Conda executable
    print("[TEST 2] Conda Executable")
    conda_exe = get_conda_exe()
    print(f"  Path: {conda_exe}")
    print(f"  Exists: {'✓ Yes' if (conda_exe and conda_exe.exists()) else '✗ No'}")
    print()
    
    # Test 3: Main environment (goodq_zenml)
    print("[TEST 3] GoodQ ZenML Environment")
    zenml_python = get_env_python('goodq_zenml')
    print(f"  Python: {zenml_python}")
    print(f"  Valid: {'✓ Yes' if validate_env('goodq_zenml') else '✗ No'}")
    print()
    
    # Test 4: All environments
    print("[TEST 4] All Conda Environments")
    all_envs = config.get_all_envs()
    print(f"  Total: {len(all_envs)} environments")
    
    # Key environments for GoodQ4All
    required_envs = [
        'goodq_zenml',
        'goodq_video_scene_detect',
        'goodq_audio_transcribe',
        'goodq_emotion_classify',
        'goodq_face_embed',
        'goodq_object_detect'
    ]
    
    print("  Required environments:")
    for env in required_envs:
        status = '✓' if validate_env(env) else '✗'
        python_path = get_env_python(env)
        print(f"    {status} {env}")
        if python_path:
            print(f"       {python_path}")
    print()
    
    # Test 5: Full configuration dump
    print("[TEST 5] Full Configuration")
    info = config.get_info_dict()
    print(f"  Platform: {info['platform']}")
    print(f"  Initialized: {info['initialized']}")
    print(f"  Conda Base: {info['conda_base']}")
    print(f"  Conda Exe: {info['conda_exe']}")
    print(f"  Total Environments: {len(info['environments'])}")
    print()
    
    # Summary
    print("="*80)
    print("  Summary")
    print("="*80)
    
    all_tests_pass = True
    
    if not conda_exe or not conda_exe.exists():
        print("  ✗ Conda executable not found")
        all_tests_pass = False
    else:
        print("  ✓ Conda executable found")
    
    if not validate_env('goodq_zenml'):
        print("  ✗ Main environment (goodq_zenml) not valid")
        all_tests_pass = False
    else:
        print("  ✓ Main environment (goodq_zenml) valid")
    
    missing_envs = [env for env in required_envs if not validate_env(env)]
    if missing_envs:
        print(f"  ⚠ Missing {len(missing_envs)} required environments:")
        for env in missing_envs:
            print(f"     - {env}")
    else:
        print("  ✓ All required environments present")
    
    print()
    
    if all_tests_pass:
        print("  ✓ ALL TESTS PASSED")
        return 0
    else:
        print("  ✗ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(test_path_configuration())
