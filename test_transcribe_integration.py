"""
Integration Test: Audio Transcribe with WSL2 Fallback
Tests the seamless WSL2-first, Windows-fallback architecture
"""
import sys
import os
import json
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

# Also add parent for goodq4all imports
sys.path.insert(0, str(REPO_ROOT.parent))

def test_integration():
    print("="*70)
    print("  AUDIO TRANSCRIBE - WSL2 INTEGRATION TEST")
    print("="*70)
    print()
    
    # Import the step
    from steps.audio_transcribe.step import audio_transcribe
    from steps.common.config_loader import load_configs
    
    # Load config
    print("1. Loading configuration...")
    cfg = load_configs({})
    print("   ✅ Config loaded")
    print()
    
    # Prepare test item
    test_audio = r"L:\goodq4all\data\temp\test_chunk.wav"
    
    if not Path(test_audio).exists():
        print(f"   ❌ Test audio not found: {test_audio}")
        return False
    
    print(f"2. Testing audio file: {Path(test_audio).name}")
    print(f"   Size: {Path(test_audio).stat().st_size} bytes")
    print()
    
    item = {
        "source_path": test_audio,
        "modality": "audio",
        "scene_id": "test_integration"
    }
    
    # Test transcription
    print("3. Running transcription...")
    try:
        result = audio_transcribe(item, cfg)
        
        if not result:
            print("   ❌ No result returned")
            return False
        
        print("   ✅ Transcription complete!")
        print()
        
        # Analyze results
        print("4. Results:")
        transcript = result.get("transcript")
        meta = result.get("transcript_meta", {})
        segments = result.get("segments", [])
        
        print(f"   - Method: {meta.get('method', 'unknown')}")
        print(f"   - Status: {meta.get('status', 'unknown')}")
        
        if meta.get('method') == 'wsl2_gpu':
            print(f"   - Duration: {meta.get('duration', 0):.1f}s")
            print(f"   - Processing: {meta.get('processing_time', 0):.1f}s")
            print(f"   - Speed: {meta.get('realtime_factor', 0):.1f}x realtime")
        
        print(f"   - Segments: {len(segments)}")
        
        if transcript:
            print(f"   - Transcript: {transcript[:100]}...")
        else:
            print("   - Transcript: (empty)")
        
        print()
        
        # Verify quality
        print("5. Quality checks:")
        
        checks = {
            "Has transcript": bool(transcript),
            "Has segments": len(segments) > 0,
            "Has metadata": bool(meta),
            "Status is success": meta.get('status') == 'success',
        }
        
        all_passed = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}")
            if not passed:
                all_passed = False
        
        print()
        print("="*70)
        if all_passed:
            print("  ✅ ALL TESTS PASSED - INTEGRATION SUCCESSFUL!")
        else:
            print("  ⚠️  SOME TESTS FAILED - CHECK RESULTS ABOVE")
        print("="*70)
        
        return all_passed
        
    except Exception as e:
        print(f"   ❌ Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
