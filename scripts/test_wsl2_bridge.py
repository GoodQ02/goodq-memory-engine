"""Test WSL2 Audio Bridge End-to-End"""
from wsl2_audio_bridge import WSL2AudioBridge
import os
from pathlib import Path

def test_audio_processing():
    print("="*60)
    print("  WSL2 Audio Bridge - End-to-End Test")
    print("="*60)
    print()
    
    # Initialize bridge
    bridge = WSL2AudioBridge()
    
    # Check status
    print("1. Checking bridge status...")
    if not bridge.check_status():
        print("   [FAIL] Bridge not ready!")
        return False
    print("   [OK] Bridge ready")
    print()
    
    # Process test audio
    test_file = os.environ.get("GOODQ_TEST_AUDIO")
    if not test_file:
        print("   [FAIL] GOODQ_TEST_AUDIO must point to a local audio fixture")
        return False
    if not Path(test_file).is_file():
        print(f"   [FAIL] GOODQ_TEST_AUDIO does not exist: {test_file}")
        return False

    print(f"2. Processing test audio: {test_file}")
    
    try:
        result = bridge.process_audio(test_file)
        
        print("   [OK] Processing successful!")
        print()
        print("3. Results:")
        print(f"   - Language: {result['language']}")
        print(f"   - Duration: {result['duration']:.1f}s")
        print(f"   - Segments: {len(result['segments'])}")
        print()
        
        if result['segments']:
            print("4. First segment:")
            seg = result['segments'][0]
            print(f"   - Time: {seg['start']:.1f}s - {seg['end']:.1f}s")
            print(f"   - Text: {seg['text'][:100]}")
            print(f"   - Speaker: {seg['speaker']}")
        
        print()
        print("="*60)
        print("  [OK] ALL TESTS PASSED!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"   [FAIL] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_audio_processing()
    exit(0 if success else 1)
