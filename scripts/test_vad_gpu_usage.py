#!/usr/bin/env python3
"""
Test VAD Implementation and GPU Usage

This script tests:
1. VAD preprocessing functionality
2. GPU acceleration
3. Time savings from VAD filtering
4. Integration with audio steps
"""

import os
import sys
import time
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_vad_basic():
    """Test basic VAD functionality"""
    print("=" * 80)
    print("Test 1: Basic VAD Preprocessing")
    print("=" * 80)
    
    try:
        from steps.common.vad_preprocessor import preprocess_audio_with_vad, get_vad_model
        
        # Test model loading
        print("\n[1/3] Loading Silero VAD model...")
        start = time.time()
        model, utils = get_vad_model()
        print(f"✓ Model loaded in {time.time() - start:.2f}s")
        
        # Find a test audio file
        test_files = list(Path(project_root / "data" / "processing").rglob("*.wav"))
        test_files.extend(list(Path(project_root / "_DATA" / "FAMILY_FEAST").rglob("*.mp4"))[:1])
        
        if not test_files:
            print("✗ No test audio files found")
            return False
        
        test_file = str(test_files[0])
        print(f"\n[2/3] Testing VAD on: {Path(test_file).name}")
        
        # Run VAD
        start = time.time()
        vad_path, segments = preprocess_audio_with_vad(
            test_file,
            threshold=0.5,
            min_speech_duration_ms=400,
            min_silence_duration_ms=200,
            extract_to_file=True
        )
        elapsed = time.time() - start
        
        if vad_path and segments:
            print(f"✓ VAD completed in {elapsed:.2f}s")
            print(f"  - Found {len(segments)} speech segments")
            print(f"  - Output: {vad_path}")
            return True
        else:
            print("✗ VAD failed to produce output")
            return False
            
    except Exception as e:
        print(f"✗ VAD test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gpu_detection():
    """Test GPU availability and configuration"""
    print("\n" + "=" * 80)
    print("Test 2: GPU Detection and Configuration")
    print("=" * 80)
    
    try:
        import torch
        
        print(f"\n[1/4] PyTorch version: {torch.__version__}")
        print(f"[2/4] CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"[3/4] CUDA version: {torch.version.cuda}")
            print(f"[4/4] GPU devices:")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"  Device {i}: {props.name}")
                print(f"    - VRAM: {props.total_memory / 1024**3:.2f} GB")
                print(f"    - Compute: {props.major}.{props.minor}")
            return True
        else:
            print("✗ CUDA not available")
            return False
            
    except Exception as e:
        print(f"✗ GPU test failed: {e}")
        return False


def test_audio_emotion_with_vad():
    """Test audio_emotion step with VAD"""
    print("\n" + "=" * 80)
    print("Test 3: Audio Emotion with VAD")
    print("=" * 80)
    
    try:
        from steps.audio_emotion.step import audio_emotion
        
        # Find test audio
        test_files = list(Path(project_root / "_DATA" / "FAMILY_FEAST").rglob("*.mp4"))[:1]
        if not test_files:
            print("✗ No test files found")
            return False
        
        test_file = str(test_files[0])
        print(f"\nTesting with: {Path(test_file).name}")
        
        # Test with VAD enabled
        print("\n[1/2] Running WITH VAD...")
        item = {"source_path": test_file}
        cfg = {"vad_enabled": True}
        
        start = time.time()
        result = audio_emotion(item, cfg)
        elapsed_with_vad = time.time() - start
        
        print(f"  - Time: {elapsed_with_vad:.2f}s")
        print(f"  - Status: {result.get('audio_emotion_meta', {}).get('status')}")
        print(f"  - Emotions: {len(result.get('audio_emotion', []))}")
        
        # Test without VAD
        print("\n[2/2] Running WITHOUT VAD...")
        cfg = {"vad_enabled": False}
        
        start = time.time()
        result = audio_emotion(item, cfg)
        elapsed_without_vad = time.time() - start
        
        print(f"  - Time: {elapsed_without_vad:.2f}s")
        print(f"  - Status: {result.get('audio_emotion_meta', {}).get('status')}")
        print(f"  - Emotions: {len(result.get('audio_emotion', []))}")
        
        if elapsed_with_vad < elapsed_without_vad:
            speedup = elapsed_without_vad / elapsed_with_vad
            print(f"\n✓ VAD provided {speedup:.2f}x speedup!")
        else:
            print(f"\n⚠ VAD was slower (overhead for short audio)")
        
        return True
        
    except Exception as e:
        print(f"✗ Audio emotion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_usage():
    """Test GPU memory usage during processing"""
    print("\n" + "=" * 80)
    print("Test 4: GPU Memory Usage")
    print("=" * 80)
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print("✗ CUDA not available")
            return False
        
        print("\nGPU Memory Stats:")
        for i in range(torch.cuda.device_count()):
            allocated = torch.cuda.memory_allocated(i) / 1024**3
            reserved = torch.cuda.memory_reserved(i) / 1024**3
            total = torch.cuda.get_device_properties(i).total_memory / 1024**3
            
            print(f"\nDevice {i}:")
            print(f"  - Allocated: {allocated:.2f} GB")
            print(f"  - Reserved:  {reserved:.2f} GB")
            print(f"  - Total:     {total:.2f} GB")
            print(f"  - Usage:     {allocated/total*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory test failed: {e}")
        return False


def main():
    print()
    print("=" * 80)
    print("GoodQ4All - VAD and GPU Usage Testing")
    print("=" * 80)
    print()
    
    results = {}
    
    results['vad_basic'] = test_vad_basic()
    results['gpu_detection'] = test_gpu_detection()
    results['audio_emotion_vad'] = test_audio_emotion_with_vad()
    results['memory_usage'] = test_memory_usage()
    
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name:25s} {status}")
    
    all_passed = all(results.values())
    print()
    if all_passed:
        print("✓ All tests PASSED!")
    else:
        print("✗ Some tests FAILED")
    
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
