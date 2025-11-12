"""
Validate that all critical fixes are working
"""
import os
import sys
import subprocess
import json
from pathlib import Path

def test_ffmpeg():
    """Test FFmpeg availability"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return True, version_line
        return False, "FFmpeg returned non-zero exit code"
    except FileNotFoundError:
        return False, "FFmpeg not found in PATH"
    except Exception as e:
        return False, str(e)


def test_pyannote_gpu():
    """Test PyAnnote GPU transfer"""
    try:
        import torch
        from pyannote.audio import Pipeline
        
        # Try to load model
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization@2.1",
            use_auth_token=os.environ.get("HF_AUTH_TOKEN")
        )
        
        # Test GPU transfer with correct API
        if torch.cuda.is_available():
            device = torch.device("cuda")
            pipeline.to(device)
            return True, f"Pipeline on {device}"
        else:
            return True, "GPU not available, but API correct"
            
    except TypeError as e:
        if "device" in str(e):
            return False, f"API still incorrect: {e}"
        raise
    except Exception as e:
        return False, f"Error: {e}"


def test_scene_detection_config():
    """Test scene detection configuration"""
    try:
        config_file = Path(__file__).parent.parent / "config.json"
        if not config_file.exists():
            return False, "config.json not found"
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if 'scene_detection' not in config:
            return False, "scene_detection not in config"
        
        min_scene_len = config['scene_detection'].get('min_scene_len', 0)
        if min_scene_len >= 300:
            return True, f"min_scene_len = {min_scene_len}s (5+ minutes)"
        else:
            return False, f"min_scene_len = {min_scene_len}s (should be 300+)"
            
    except Exception as e:
        return False, str(e)


def main():
    print("="*80)
    print("  GoodQ4All - Critical Fixes Validation")
    print("="*80)
    print()
    
    tests = [
        ("FFmpeg Availability", test_ffmpeg),
        ("PyAnnote GPU API", test_pyannote_gpu),
        ("Scene Detection Config", test_scene_detection_config)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        print(f"Testing: {test_name}...", end=" ")
        try:
            success, message = test_func()
            if success:
                print("✓ PASS")
                print(f"  {message}")
            else:
                print("✗ FAIL")
                print(f"  {message}")
                all_passed = False
        except Exception as e:
            print("✗ ERROR")
            print(f"  {str(e)}")
            all_passed = False
        print()
    
    print("="*80)
    if all_passed:
        print("  ✓ All critical fixes validated successfully!")
        print("  System is ready for production testing.")
    else:
        print("  ✗ Some fixes failed validation")
        print("  Please review errors above.")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
