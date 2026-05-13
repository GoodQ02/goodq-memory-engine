"""
Test script for WSL2 audio bridge
"""

import os
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from wsl2_audio.audio_bridge import WSL2AudioBridge


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = ("*.wav", "*.mp3", "*.mp4", "*.m4a")


def _configured_audio_locations():
    """Return explicit, bounded locations for local bridge smoke inputs."""
    direct_file = os.environ.get("GOODQ_TEST_AUDIO")
    if direct_file:
        yield Path(direct_file)

    for env_name in ("GOODQ_AUDIO_TEST_DIR", "GOODQ_IMPORT_INBOX"):
        value = os.environ.get(env_name)
        if value:
            yield Path(value)

    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        root = Path(data_root)
        yield root / "GoodQ_Data" / "processing"
        yield root / "GoodQ_Data" / "import_inbox"

    yield REPO_ROOT / "import_inbox"
    yield REPO_ROOT / "samples" / "ingestion"


def _find_audio_file():
    checked = []
    for location in _configured_audio_locations():
        checked.append(location)
        if location.is_file():
            return location, checked
        if location.is_dir():
            for ext in AUDIO_EXTENSIONS:
                files = sorted(location.glob(ext))
                if files:
                    return files[0], checked
    return None, checked


def main():
    print("="*80)
    print("  GoodQ4All - WSL2 Audio Bridge Test")
    print("="*80)
    print()
    
    # Initialize bridge
    print("[1/3] Initializing bridge...")
    bridge = WSL2AudioBridge()
    print("[SYMBOL] Bridge initialized")
    print()
    
    # Check if the canonical WSL audio runtime is ready
    print("[2/3] Checking WSL2 audio runtime...")
    if bridge._is_wsl_service_running():
        print("[SYMBOL] WSL2 audio runtime is ready")
    else:
        print("[SYMBOL] WSL2 audio runtime is NOT ready")
        print()
        print("Check the canonical runtime reference and WSL workspace setup:")
        print("  docs\\reference\\WSL_AUDIO_RUNTIME.md")
        print("  docs\\guides\\llm\\WSL2_AUDIO_SETUP.md")
        print()
        return
    print()
    
    # Find a test audio file
    print("[3/3] Looking for test audio...")
    
    audio_file, checked_paths = _find_audio_file()
    
    if not audio_file:
        print("[SYMBOL] No test audio file found")
        print("  Provide an audio file through GOODQ_TEST_AUDIO, GOODQ_AUDIO_TEST_DIR,")
        print("  GOODQ_IMPORT_INBOX, GOODQ_DATA_ROOT, or the repo samples/ingestion folder.")
        print("  Checked:")
        for p in checked_paths:
            print(f"    {p}")
        return
    
    print(f"[SYMBOL] Found test file: {audio_file}")
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
        print(f"[SYMBOL] Transcription successful!")
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
        print(f"[SYMBOL] Transcription failed")
        print(f"Status: {result.get('status')}")
        print(f"Error: {result.get('error')}")
    
    print()
    print("="*80)
    print("  Test Complete")
    print("="*80)


if __name__ == '__main__':
    main()
