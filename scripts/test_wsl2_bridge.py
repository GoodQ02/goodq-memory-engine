"""Test WSL2 Audio Bridge End-to-End"""
from wsl2_audio_bridge import WSL2AudioBridge
import json

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
        print("   ❌ Bridge not ready!")
        return False
    print("   ✅ Bridge ready")
    print()
    
    # Process test audio
    test_file = r"L:\_DATA\GoodQ_Data\temp\test_chunk.wav"
    print(f"2. Processing test audio: {test_file}")
    
    try:
        result = bridge.process_audio(test_file)
        
        print("   ✅ Processing successful!")
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
        print("  ✅ ALL TESTS PASSED!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"   ❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_audio_processing()
    exit(0 if success else 1)
