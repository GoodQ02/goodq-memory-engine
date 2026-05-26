"""
Test WSL Audio Processing Integration
Tests the WSL-based GPU-accelerated audio processing
"""
import json
import subprocess
import sys
from pathlib import Path

def test_wsl_audio_processing():
    """Test WSL audio processing with a real file"""
    
    # Find a test audio file
    test_file = Path(r"L:\_DATA\GoodQ_Data\temp\test_chunk.wav")
    
    if not test_file.exists():
        print(f"[FAIL] Test file not found: {test_file}")
        return False
    
    # Convert Windows path to WSL path
    wsl_path = f"/mnt/l/L:/_DATA/GoodQ_Data/temp/test_chunk.wav"
    
    print(f"[SYMBOL] Testing WSL audio processing...")
    print(f"   File: {test_file}")
    print(f"   WSL Path: {wsl_path}")
    
    try:
        # Run WSL processing
        result = subprocess.run(
            ["wsl", "~/goodq_audio/scripts/process.sh", wsl_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            print(f"[FAIL] Processing failed with code {result.returncode}")
            print(f"   STDERR: {result.stderr}")
            return False
        
        # Parse JSON output (last line of stdout)
        lines = result.stdout.strip().split('\n')
        json_line = lines[-1]
        
        data = json.loads(json_line)
        
        if data.get('status') != 'success':
            print(f"[FAIL] Processing returned error: {data.get('error')}")
            return False
        
        segments = data.get('segments', [])
        language = data.get('language', 'unknown')
        duration = data.get('duration', 0)
        speakers = data.get('speakers_detected', 0)
        
        print(f"[OK] Processing successful!")
        print(f"   Language: {language}")
        print(f"   Duration: {duration}s")
        print(f"   Segments: {len(segments)}")
        print(f"   Speakers: {speakers}")
        print(f"   Sample text: {segments[0]['text'][:50]}..." if segments else "")
        
        return True
        
    except subprocess.TimeoutExpired:
        print(f"[FAIL] Processing timed out after 120s")
        return False
    except json.JSONDecodeError as e:
        print(f"[FAIL] Failed to parse JSON output: {e}")
        print(f"   Output: {result.stdout}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_wsl_audio_processing()
    sys.exit(0 if success else 1)
