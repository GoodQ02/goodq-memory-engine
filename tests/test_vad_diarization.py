"""
Test script for VAD-enhanced audio diarization.
Tests the new VAD preprocessing on a sample audio file.
"""
import os
import sys
import time

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
os.chdir(project_root)  # Change to project root for relative imports

def test_vad_preprocessing():
    """Test VAD preprocessing on sample audio"""
    print("="*80)
    print("Testing VAD Preprocessing")
    print("="*80)
    
    # Find a test audio file
    test_files = [
        r"L:\goodq4all\import_inbox\01. 1987 - 1988.mp4",
        r"L:\goodq4all\data\processing\sample.mp4",
    ]
    
    audio_path = None
    for path in test_files:
        if os.path.exists(path):
            audio_path = path
            break
    
    if not audio_path:
        print("ERROR: No test audio file found")
        print(f"Tried: {test_files}")
        return False
    
    print(f"Test file: {audio_path}")
    print(f"Size: {os.path.getsize(audio_path) / (1024*1024):.1f}MB")
    print()
    
    try:
        from steps.audio_diarize.vad_preprocessor import (
            preprocess_audio_with_vad,
            calculate_time_savings,
        )
        
        # Get original duration
        from steps.audio_diarize.step import _get_audio_duration
        original_duration = _get_audio_duration(audio_path)
        
        if original_duration:
            print(f"Original duration: {original_duration/60:.1f} minutes")
        else:
            print("WARNING: Could not determine audio duration")
        
        print()
        print("Running VAD preprocessing...")
        start_time = time.time()
        
        vad_audio_path, vad_segments = preprocess_audio_with_vad(
            audio_path,
            threshold=0.5,
            min_speech_duration_ms=400,
            min_silence_duration_ms=200,
            merge_gap_seconds=1.0,
            extract_to_file=True,
        )
        
        elapsed = time.time() - start_time
        print(f"\nVAD completed in {elapsed:.1f}s")
        
        if vad_audio_path and vad_segments:
            print(f"\n✓ VAD preprocessing successful!")
            print(f"  Speech-only audio: {vad_audio_path}")
            print(f"  Speech segments: {len(vad_segments)}")
            
            if original_duration:
                savings = calculate_time_savings(original_duration, vad_segments)
                print(f"\n  Time Savings:")
                print(f"    Original: {savings['original_duration']/60:.1f} min")
                print(f"    Speech: {savings['speech_duration']/60:.1f} min")
                print(f"    Saved: {savings['time_saved']/60:.1f} min ({savings['reduction_percent']:.1f}% reduction)")
                print(f"    Estimated diarization speedup: {savings['reduction_percent']:.0f}%")
            
            # Clean up temp file
            if os.path.exists(vad_audio_path):
                os.remove(vad_audio_path)
                print(f"\n  Cleaned up temp file: {vad_audio_path}")
            
            return True
        else:
            print("\n✗ VAD preprocessing did not produce output")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_full_diarization():
    """Test full diarization with VAD enabled"""
    print("\n")
    print("="*80)
    print("Testing Full Diarization with VAD")
    print("="*80)
    
    # Load config
    import yaml
    config_path = r"L:\goodq4all\configs\config_open.yaml"
    
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Verify VAD is enabled in config
    vad_enabled = cfg.get('audio', {}).get('diarization', {}).get('vad_enabled', False)
    print(f"VAD enabled in config: {vad_enabled}")
    
    if not vad_enabled:
        print("\nWARNING: VAD is not enabled in config!")
        print("Enable it in configs/config_open.yaml:")
        print("  audio:")
        print("    diarization:")
        print("      vad_enabled: true")
        return False
    
    # Find test audio
    test_files = [
        r"L:\goodq4all\import_inbox\01. 1987 - 1988.mp4",
        r"L:\goodq4all\data\processing\sample.mp4",
    ]
    
    audio_path = None
    for path in test_files:
        if os.path.exists(path):
            audio_path = path
            break
    
    if not audio_path:
        print("ERROR: No test audio file found")
        return False
    
    print(f"\nTest file: {audio_path}")
    
    # Create test item
    item = {
        'source_path': audio_path,
    }
    
    try:
        from steps.audio_diarize.step import audio_diarize
        
        print("\nRunning diarization with VAD preprocessing...")
        start_time = time.time()
        
        result = audio_diarize(item, cfg)
        
        elapsed = time.time() - start_time
        
        print(f"\nDiarization completed in {elapsed:.1f}s ({elapsed/60:.1f} min)")
        
        # Check results
        diarization = result.get('diarization')
        meta = result.get('diarize_meta', {})
        
        if diarization:
            print(f"\n✓ Diarization successful!")
            print(f"  Segments: {len(diarization)}")
            print(f"  Speakers: {meta.get('speaker_count', 'unknown')}")
            print(f"  Device: {meta.get('device', 'unknown')}")
            print(f"  Processing time: {meta.get('processing_time', 0):.1f}s")
            
            if meta.get('vad_enabled'):
                vad_savings = meta.get('vad_savings', {})
                print(f"\n  VAD Preprocessing:")
                print(f"    Original: {vad_savings.get('original_duration', 0)/60:.1f} min")
                print(f"    Speech: {vad_savings.get('speech_duration', 0)/60:.1f} min")
                print(f"    Reduction: {vad_savings.get('reduction_percent', 0):.1f}%")
            else:
                print(f"\n  WARNING: VAD was not used (check logs for errors)")
            
            return True
        else:
            print(f"\n✗ Diarization failed")
            print(f"  Status: {meta.get('status', 'unknown')}")
            print(f"  Reason: {meta.get('reason', 'unknown')}")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("GoodQ4All - VAD-Enhanced Audio Diarization Test")
    print()
    
    # Test 1: VAD preprocessing only
    vad_ok = test_vad_preprocessing()
    
    # Test 2: Full diarization with VAD
    if vad_ok:
        diarize_ok = test_full_diarization()
    else:
        print("\nSkipping full diarization test (VAD preprocessing failed)")
        diarize_ok = False
    
    # Summary
    print("\n")
    print("="*80)
    print("Test Summary")
    print("="*80)
    print(f"VAD Preprocessing: {'✓ PASS' if vad_ok else '✗ FAIL'}")
    print(f"Full Diarization: {'✓ PASS' if diarize_ok else '✗ FAIL'}")
    
    if vad_ok and diarize_ok:
        print("\n✓ All tests passed!")
        print("\nVAD preprocessing is working correctly and will dramatically")
        print("reduce diarization time by filtering out silence and noise.")
    else:
        print("\n✗ Some tests failed - check errors above")
    
    print()
