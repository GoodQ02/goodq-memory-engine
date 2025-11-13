"""
Test script for WSL2 audio bridge
"""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from wsl2_audio.audio_bridge import WSL2AudioBridge

def main():
    print("="*80)
    print("  GoodQ4All - WSL2 Audio Bridge Test")
    print("="*80)
    print()
    
    # Initialize bridge
    print("[1/3] Initializing bridge...")
    bridge = WSL2AudioBridge()
    print("✓ Bridge initialized")
    print()
    
    # Check if service is running
    print("[2/3] Checking WSL2 service...")
    if bridge._is_wsl_service_running():
        print("✓ WSL2 audio service is running")
    else:
        print("✗ WSL2 audio service is NOT running")
        print()
        print("To start the service, open WSL2 and run:")
        print("  cd ~/goodq_audio")
        print("  source venv/bin/activate")
        print("  python3 /mnt/l/goodq4all/wsl2_audio/audio_service.py")
        print()
        return
    print()
    
    # Find a test audio file
    print("[3/3] Looking for test audio...")
    
    test_paths = [
        Path("L:/goodq4all/data/processing"),
        Path("L:/goodq4all/import_inbox"),
        Path("L:/_DATA/FAMILY_FEAST")
    ]
    
    audio_file = None
    for test_path in test_paths:
        if test_path.exists():
            for ext in ['*.wav', '*.mp3', '*.mp4', '*.m4a']:
                files = list(test_path.glob(ext))
                if files:
                    audio_file = files[0]
                    break
            if audio_file:
                break
    
    if not audio_file:
        print("✗ No test audio file found")
        print("  Please place an audio file in one of these locations:")
        for p in test_paths:
            print(f"    {p}")
        return
    
    print(f"✓ Found test file: {audio_file}")
    print()
    
    # Test transcription
    print("="*80)
    print("  Testing Transcription")
    print("="*80)
    print()
    print(f"Submitting: {audio_file.name}")
    print("This may take a few minutes...")
    print()
    
    start_time = time.time()
    
    result = bridge.transcribe(
        str(audio_file),
        language="en",
        beam_size=5,
        timeout=600  # 10 minutes
    )
    
    elapsed = time.time() - start_time
    
    print()
    print("="*80)
    print("  Results")
    print("="*80)
    print()
    
    if result.get('status') == 'success':
        print(f"✓ Transcription successful!")
        print()
        print(f"Processing time: {elapsed:.1f}s")
        
        if 'info' in result:
            info = result['info']
            print(f"Audio duration: {info.get('duration', 0):.1f}s")
            print(f"Real-time factor: {info.get('rtf', 0):.2f}x")
            print(f"Language: {info.get('language', 'unknown')}")
        
        print()
        print("Transcription:")
        print("-" * 80)
        
        full_text = result.get('full_text', '')
        if len(full_text) > 500:
            print(full_text[:500] + "...")
        else:
            print(full_text)
        
        print("-" * 80)
        print()
        print(f"Total segments: {len(result.get('transcription', []))}")
        
    else:
        print(f"✗ Transcription failed")
        print(f"Status: {result.get('status')}")
        print(f"Error: {result.get('error')}")
    
    print()
    print("="*80)
    print("  Test Complete")
    print("="*80)


if __name__ == '__main__':
    main()
