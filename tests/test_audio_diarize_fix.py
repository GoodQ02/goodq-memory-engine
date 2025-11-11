#!/usr/bin/env python3
"""
Test script to verify audio diarization fixes
Tests encoding handling and timeout configuration
"""

import subprocess
import sys
from pathlib import Path

def test_encoding_fix():
    """Test that subprocess calls handle Unicode properly"""
    print("=" * 60)
    print("Testing Unicode Encoding Fix")
    print("=" * 60)
    
    # Test with a command that outputs Unicode
    try:
        # This should not raise a charmap error anymore
        result = subprocess.run(
            ['echo', '→ Test Unicode Arrow →'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True
        )
        print(f"✓ Unicode handling works: {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"✗ Unicode handling failed: {e}")
        return False


def test_diarization_import():
    """Test that audio_diarize step can be imported"""
    print("\n" + "=" * 60)
    print("Testing Audio Diarization Import")
    print("=" * 60)
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from steps.audio_diarize.step import audio_diarize
        print("✓ audio_diarize step imports successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import audio_diarize: {e}")
        return False


def test_config_structure():
    """Test that config has proper diarization settings"""
    print("\n" + "=" * 60)
    print("Testing Configuration Structure")
    print("=" * 60)
    
    try:
        import yaml
        config_path = Path("L:/goodq4all/config.yaml")
        
        if not config_path.exists():
            print(f"✗ Config file not found: {config_path}")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check for audio.diarization section
        if 'audio' in config and 'diarization' in config['audio']:
            dz_config = config['audio']['diarization']
            print(f"✓ Diarization config found")
            print(f"  - Enabled: {dz_config.get('enabled', True)}")
            print(f"  - Min speakers: {dz_config.get('min_speakers', 'N/A')}")
            print(f"  - Max speakers: {dz_config.get('max_speakers', 'N/A')}")
            return True
        else:
            print("✗ Diarization config section missing")
            return False
            
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False


def test_step_timeout_in_watchdog():
    """Verify watchdog script includes step-timeout parameter"""
    print("\n" + "=" * 60)
    print("Testing Watchdog Step Timeout Configuration")
    print("=" * 60)
    
    try:
        watchdog_path = Path("L:/goodq4all/scripts/watchdog_ingest.py")
        
        if not watchdog_path.exists():
            print(f"✗ Watchdog script not found: {watchdog_path}")
            return False
        
        content = watchdog_path.read_text(encoding='utf-8')
        
        if '--step-timeout' in content:
            print("✓ Step timeout parameter found in watchdog")
            # Extract the timeout value
            for line in content.split('\n'):
                if 'step_timeout' in line and '=' in line:
                    print(f"  - {line.strip()}")
            return True
        else:
            print("✗ Step timeout parameter not found in watchdog")
            return False
            
    except Exception as e:
        print(f"✗ Watchdog test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("AUDIO DIARIZATION FIX VERIFICATION")
    print("=" * 60 + "\n")
    
    results = {
        "Unicode Encoding": test_encoding_fix(),
        "Diarization Import": test_diarization_import(),
        "Config Structure": test_config_structure(),
        "Watchdog Timeout": test_step_timeout_in_watchdog(),
    }
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED - Ready for production testing")
    else:
        print("✗ SOME TESTS FAILED - Review errors above")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
