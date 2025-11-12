"""
Test individual components of audio diarization pipeline
Identifies performance bottlenecks and stalls
"""

import os
import sys
import time
import torch
from pathlib import Path

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_step(step_num, title):
    print(f"\n[{step_num}] {title}")
    print("-" * 80)

def test_gpu_detection():
    """Test 1: GPU Detection and Configuration"""
    print_step(1, "GPU Detection and Configuration")
    
    try:
        cuda_available = torch.cuda.is_available()
        print(f"  CUDA Available: {cuda_available}")
        
        if cuda_available:
            device_count = torch.cuda.device_count()
            print(f"  GPU Count: {device_count}")
            
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                print(f"\n  GPU {i}: {props.name}")
                print(f"    Total Memory: {props.total_memory / 1024**3:.2f} GB")
                print(f"    Compute Capability: {props.major}.{props.minor}")
            
            # Test memory allocation
            print("\n  Testing memory allocation...")
            start = time.time()
            test_tensor = torch.randn(1000, 1000).cuda()
            torch.cuda.synchronize()
            elapsed = time.time() - start
            print(f"  ✓ Memory allocation test: {elapsed*1000:.2f}ms")
            
            # Clean up
            del test_tensor
            torch.cuda.empty_cache()
            
        else:
            print("  ⚠ Warning: No GPU detected, will use CPU")
        
        print("  ✓ GPU detection complete")
        return True
        
    except Exception as e:
        print(f"  ❌ GPU detection failed: {e}")
        return False

def test_pipeline_loading():
    """Test 2: Pipeline Loading (PyAnnote model)"""
    print_step(2, "Pipeline Loading (PyAnnote model)")
    
    try:
        from pyannote.audio import Pipeline
        
        print("  Loading pyannote/speaker-diarization-3.1...")
        start = time.time()
        
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token="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"
        )
        
        # Move to GPU if available
        if torch.cuda.is_available():
            pipeline = pipeline.to(torch.device("cuda"))
            print("  ✓ Pipeline moved to GPU")
        
        elapsed = time.time() - start
        print(f"  ✓ Pipeline loaded in {elapsed:.2f}s")
        
        return True, pipeline
        
    except Exception as e:
        print(f"  ❌ Pipeline loading failed: {e}")
        return False, None

def test_audio_duration():
    """Test 3: Audio Duration Detection"""
    print_step(3, "Audio Duration Detection")
    
    try:
        import subprocess
        
        # Find a test audio file
        test_files = [
            r"L:\_DATA\FAMILY_FEAST\01. 1987 - 1988.mp4",
            r"L:\goodq4all\import_inbox\sample.mp4",
        ]
        
        test_file = None
        for f in test_files:
            if os.path.exists(f):
                test_file = f
                break
        
        if not test_file:
            print("  ⚠ No test file found, skipping")
            return False
        
        print(f"  Test file: {Path(test_file).name}")
        
        # Get duration using ffprobe
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            test_file
        ]
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - start
        
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            print(f"  Duration: {duration:.2f}s ({duration/60:.2f} min)")
            print(f"  Detection time: {elapsed*1000:.2f}ms")
            print("  ✓ Duration detection successful")
            return True, test_file, duration
        else:
            print(f"  ❌ ffprobe failed: {result.stderr}")
            return False, None, None
        
    except Exception as e:
        print(f"  ❌ Duration detection failed: {e}")
        return False, None, None

def test_chunk_extraction():
    """Test 4: Audio Chunk Extraction (FFmpeg)"""
    print_step(4, "Audio Chunk Extraction (FFmpeg)")
    
    try:
        import subprocess
        
        # Use test file from previous test
        test_files = [
            r"L:\_DATA\FAMILY_FEAST\01. 1987 - 1988.mp4",
            r"L:\goodq4all\import_inbox\sample.mp4",
        ]
        
        test_file = None
        for f in test_files:
            if os.path.exists(f):
                test_file = f
                break
        
        if not test_file:
            print("  ⚠ No test file found, skipping")
            return False
        
        # Extract 10 second chunk to temp
        output_file = r"L:\goodq4all\data\temp\test_chunk.wav"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite
            '-ss', '0',  # Start at 0s
            '-t', '10',  # Duration 10s
            '-i', test_file,
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            output_file
        ]
        
        print(f"  Extracting 10s chunk...")
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - start
        
        if result.returncode == 0 and os.path.exists(output_file):
            size = os.path.getsize(output_file) / 1024
            print(f"  ✓ Chunk extracted in {elapsed:.2f}s")
            print(f"  File size: {size:.1f} KB")
            return True, output_file
        else:
            print(f"  ❌ Extraction failed: {result.stderr}")
            return False, None
        
    except Exception as e:
        print(f"  ❌ Chunk extraction failed: {e}")
        return False, None

def test_single_chunk_diarization(pipeline, audio_file):
    """Test 5: Single Chunk Diarization (short sample)"""
    print_step(5, "Single Chunk Diarization (10s sample)")
    
    if pipeline is None or audio_file is None:
        print("  ⚠ Skipping (prerequisites not met)")
        return False
    
    try:
        print(f"  Processing: {Path(audio_file).name}")
        print(f"  GPU Available: {torch.cuda.is_available()}")
        
        # Monitor GPU memory before
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            mem_before = torch.cuda.memory_allocated() / 1024**2
            print(f"  GPU Memory (before): {mem_before:.1f} MB")
        
        # Run diarization
        start = time.time()
        diarization = pipeline(audio_file)
        elapsed = time.time() - start
        
        # Monitor GPU memory after
        if torch.cuda.is_available():
            mem_after = torch.cuda.memory_allocated() / 1024**2
            mem_peak = torch.cuda.max_memory_allocated() / 1024**2
            print(f"  GPU Memory (after): {mem_after:.1f} MB")
            print(f"  GPU Memory (peak): {mem_peak:.1f} MB")
        
        # Print results
        print(f"\n  ✓ Diarization complete in {elapsed:.2f}s")
        print(f"  Processing speed: {10/elapsed:.2f}x realtime")
        
        # Count speakers
        speakers = set()
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.add(speaker)
        
        print(f"  Speakers detected: {len(speakers)}")
        print(f"  Segments: {len(list(diarization.itertracks()))}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Diarization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_header("GoodQ4All - Audio Diarization Component Tests")
    
    # Test 1: GPU Detection
    gpu_ok = test_gpu_detection()
    
    # Test 2: Pipeline Loading
    pipeline_ok, pipeline = test_pipeline_loading()
    
    # Test 3: Duration Detection
    duration_ok, test_file, duration = test_audio_duration()
    
    # Test 4: Chunk Extraction
    chunk_ok, chunk_file = test_chunk_extraction()
    
    # Test 5: Single Chunk Diarization
    if pipeline_ok and chunk_ok:
        diarization_ok = test_single_chunk_diarization(pipeline, chunk_file)
    else:
        print_step(5, "Single Chunk Diarization (SKIPPED)")
        print("  ⚠ Skipping due to previous failures")
        diarization_ok = False
    
    # Summary
    print_header("Test Summary")
    results = {
        "GPU Detection": gpu_ok,
        "Pipeline Loading": pipeline_ok,
        "Duration Detection": duration_ok,
        "Chunk Extraction": chunk_ok,
        "Single Chunk Diarization": diarization_ok,
    }
    
    for test, result in results.items():
        status = "✓" if result else "❌"
        color = "\033[92m" if result else "\033[91m"
        print(f"  {color}{status}\033[0m {test}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
