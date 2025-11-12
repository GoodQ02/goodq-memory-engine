"""
Audio Diarization Component Breakdown Test
Isolates and tests each function to identify bottlenecks and stalls
"""
import os
import sys
import time
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def test_gpu_detection():
    """Test 1: GPU Detection and Configuration"""
    print_section("TEST 1: GPU Detection and Configuration")
    
    try:
        import torch
        print(f"✓ PyTorch imported successfully")
        print(f"  PyTorch version: {torch.__version__}")
        
        cuda_available = torch.cuda.is_available()
        print(f"  CUDA available: {cuda_available}")
        
        if cuda_available:
            print(f"  CUDA version: {torch.version.cuda}")
            print(f"  GPU device: {torch.cuda.get_device_name(0)}")
            print(f"  GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            
            # Test GPU allocation
            start = time.time()
            test_tensor = torch.zeros(1000, 1000).cuda()
            elapsed = time.time() - start
            print(f"  GPU allocation test: {elapsed*1000:.1f}ms")
            
            # Check memory
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"  Memory allocated: {allocated:.3f} GB")
            print(f"  Memory reserved: {reserved:.3f} GB")
            
            del test_tensor
            torch.cuda.empty_cache()
            print(f"✓ GPU configuration successful")
        else:
            print(f"⚠ CUDA not available - will use CPU")
        
        return True
        
    except Exception as e:
        print(f"✗ GPU detection failed: {e}")
        return False

def test_pipeline_loading():
    """Test 2: PyAnnote Pipeline Loading"""
    print_section("TEST 2: PyAnnote Pipeline Loading")
    
    try:
        from pyannote.audio import Pipeline
        print(f"✓ PyAnnote imported successfully")
        
        # Check for auth token
        auth_token = os.getenv("PYANNOTE_TOKEN") or os.getenv("HF_TOKEN")
        if not auth_token:
            print(f"✗ No authentication token found")
            print(f"  Set PYANNOTE_TOKEN or HF_TOKEN environment variable")
            return False
        
        print(f"✓ Auth token found")
        
        # Test pipeline loading
        model_id = "pyannote/speaker-diarization@2.1"
        print(f"  Loading model: {model_id}")
        
        start = time.time()
        pipeline = Pipeline.from_pretrained(model_id, use_auth_token=auth_token)
        elapsed = time.time() - start
        
        print(f"✓ Model loaded in {elapsed:.1f}s")
        
        # Test GPU transfer
        import torch
        if torch.cuda.is_available():
            print(f"  Moving model to GPU...")
            start = time.time()
            pipeline.to(torch.device("cuda"))
            elapsed = time.time() - start
            print(f"✓ Model transferred to GPU in {elapsed:.1f}s")
            
            # Check GPU memory
            allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"  GPU memory after load: {allocated:.3f} GB")
        
        return True
        
    except Exception as e:
        print(f"✗ Pipeline loading failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_audio_duration():
    """Test 3: Audio Duration Detection"""
    print_section("TEST 3: Audio Duration Detection")
    
    # Find test audio file
    test_files = [
        "L:\\goodq4all\\import_inbox\\sample.mp4",
        "L:\\goodq4all\\test_input\\sample.mp4",
        "L:\\_DATA\\FAMILY_FEAST\\01. 1987 - 1988.mp4",
    ]
    
    test_file = None
    for f in test_files:
        if os.path.exists(f):
            test_file = f
            break
    
    if not test_file:
        print(f"✗ No test audio file found")
        return False
    
    print(f"  Test file: {os.path.basename(test_file)}")
    print(f"  Size: {os.path.getsize(test_file) / 1024**2:.1f} MB")
    
    # Test with soundfile
    try:
        import soundfile as sf
        start = time.time()
        info = sf.info(test_file)
        elapsed = time.time() - start
        
        duration = info.duration if hasattr(info, 'duration') else info.frames / info.samplerate
        print(f"✓ soundfile detection: {duration/60:.1f} min in {elapsed*1000:.0f}ms")
    except Exception as e:
        print(f"✗ soundfile failed: {e}")
    
    # Test with librosa
    try:
        import librosa
        start = time.time()
        duration = librosa.get_duration(filename=test_file)
        elapsed = time.time() - start
        
        print(f"✓ librosa detection: {duration/60:.1f} min in {elapsed*1000:.0f}ms")
        return True
    except Exception as e:
        print(f"✗ librosa failed: {e}")
    
    return False

def test_audio_extraction():
    """Test 4: Audio Chunk Extraction (FFmpeg)"""
    print_section("TEST 4: Audio Chunk Extraction (FFmpeg)")
    
    # Find test audio file
    test_files = [
        "L:\\goodq4all\\import_inbox\\sample.mp4",
        "L:\\goodq4all\\test_input\\sample.mp4",
        "L:\\_DATA\\FAMILY_FEAST\\01. 1987 - 1988.mp4",
    ]
    
    test_file = None
    for f in test_files:
        if os.path.exists(f):
            test_file = f
            break
    
    if not test_file:
        print(f"✗ No test audio file found")
        return False
    
    print(f"  Test file: {os.path.basename(test_file)}")
    
    # Test extraction
    try:
        import subprocess
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp.name
        tmp.close()
        
        # Extract first 30 seconds
        start = time.time()
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", "0",
            "-t", "30",
            "-i", test_file,
            "-ac", "1",
            "-ar", "16000",
            tmp_path,
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True)
        elapsed = time.time() - start
        
        size_mb = os.path.getsize(tmp_path) / 1024**2
        print(f"✓ Extracted 30s chunk in {elapsed:.1f}s ({size_mb:.1f} MB)")
        
        # Clean up
        os.remove(tmp_path)
        return True
        
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False

def test_short_diarization():
    """Test 5: Single Chunk Diarization (short sample)"""
    print_section("TEST 5: Short Audio Diarization (30 seconds)")
    
    # Find test audio
    test_files = [
        "L:\\goodq4all\\import_inbox\\sample.mp4",
        "L:\\goodq4all\\test_input\\sample.mp4",
        "L:\\_DATA\\FAMILY_FEAST\\01. 1987 - 1988.mp4",
    ]
    
    test_file = None
    for f in test_files:
        if os.path.exists(f):
            test_file = f
            break
    
    if not test_file:
        print(f"✗ No test audio file found")
        return False
    
    print(f"  Test file: {os.path.basename(test_file)}")
    
    try:
        import subprocess
        from pyannote.audio import Pipeline
        import torch
        
        # Extract short clip
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp.name
        tmp.close()
        
        print(f"  Extracting 30s test clip...")
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", "0",
            "-t", "30",
            "-i", test_file,
            "-ac", "1",
            "-ar", "16000",
            tmp_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Load pipeline
        print(f"  Loading pipeline...")
        auth_token = os.getenv("PYANNOTE_TOKEN") or os.getenv("HF_TOKEN")
        if not auth_token:
            print(f"✗ No auth token")
            return False
        
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization@2.1", use_auth_token=auth_token)
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            pipeline.to(torch.device("cuda"))
            print(f"  Using GPU")
        else:
            print(f"  Using CPU")
        
        # Run diarization with detailed timing
        print(f"  Running diarization on 30s clip...")
        print(f"  [This should take 30-90 seconds max]")
        
        start = time.time()
        diarization = pipeline(tmp_path)
        elapsed = time.time() - start
        
        # Count segments
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        
        print(f"✓ Diarization completed in {elapsed:.1f}s ({30/elapsed:.2f}x realtime)")
        print(f"  Found {len(segments)} segments")
        print(f"  Speakers: {len(set(s['speaker'] for s in segments))}")
        
        # Clean up
        os.remove(tmp_path)
        
        if elapsed > 180:  # More than 3 minutes for 30 seconds
            print(f"⚠ WARNING: Diarization is VERY SLOW")
            print(f"  Expected: 30-90s")
            print(f"  Actual: {elapsed:.0f}s")
            print(f"  This indicates a serious performance issue!")
        
        return True
        
    except Exception as e:
        print(f"✗ Diarization failed: {e}")
        import traceback
        print(traceback.format_exc())
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False

def test_memory_profile():
    """Test 6: Memory Profiling During Diarization"""
    print_section("TEST 6: Memory Profiling")
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print(f"⚠ GPU not available, skipping memory test")
            return True
        
        print(f"  Initial GPU state:")
        print(f"  Allocated: {torch.cuda.memory_allocated() / 1024**3:.3f} GB")
        print(f"  Reserved: {torch.cuda.memory_reserved() / 1024**3:.3f} GB")
        print(f"  Total: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        
        # Test allocation patterns
        print(f"\n  Testing allocation patterns...")
        
        # Small allocation
        start = time.time()
        t1 = torch.zeros(100, 100).cuda()
        elapsed1 = time.time() - start
        mem1 = torch.cuda.memory_allocated() / 1024**3
        print(f"  Small (100x100): {elapsed1*1000:.1f}ms, {mem1:.3f} GB")
        
        # Medium allocation
        start = time.time()
        t2 = torch.zeros(1000, 1000).cuda()
        elapsed2 = time.time() - start
        mem2 = torch.cuda.memory_allocated() / 1024**3
        print(f"  Medium (1000x1000): {elapsed2*1000:.1f}ms, {mem2:.3f} GB")
        
        # Large allocation
        start = time.time()
        t3 = torch.zeros(5000, 5000).cuda()
        elapsed3 = time.time() - start
        mem3 = torch.cuda.memory_allocated() / 1024**3
        print(f"  Large (5000x5000): {elapsed3*1000:.1f}ms, {mem3:.3f} GB")
        
        # Clean up
        del t1, t2, t3
        torch.cuda.empty_cache()
        
        print(f"\n  After cleanup:")
        print(f"  Allocated: {torch.cuda.memory_allocated() / 1024**3:.3f} GB")
        print(f"  Reserved: {torch.cuda.memory_reserved() / 1024**3:.3f} GB")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory profiling failed: {e}")
        return False

def main():
    """Run all tests"""
    print("""
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║                                                                          ║
    ║         Audio Diarization Component Breakdown Testing Suite             ║
    ║                                                                          ║
    ║  This will test each component individually to identify bottlenecks     ║
    ║                                                                          ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    results = {}
    
    # Run tests
    results['gpu_detection'] = test_gpu_detection()
    results['pipeline_loading'] = test_pipeline_loading()
    results['audio_duration'] = test_audio_duration()
    results['audio_extraction'] = test_audio_extraction()
    results['short_diarization'] = test_short_diarization()
    results['memory_profile'] = test_memory_profile()
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} - {test}")
    
    print(f"\n  Overall: {passed}/{total} tests passed")
    
    if passed < total:
        print(f"\n  ⚠ BOTTLENECKS IDENTIFIED:")
        for test, result in results.items():
            if not result:
                print(f"    - {test}")
        print(f"\n  Focus optimization efforts on failed components above.")
    else:
        print(f"\n  ✓ All components working - issue may be in integration/coordination")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    main()
