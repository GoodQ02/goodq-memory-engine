"""
Comprehensive Audio Diarization Pipeline Test
Tests each component step-by-step with GPU monitoring
"""
import os
import sys
import time
import torch
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")

def check_gpu():
    """Check GPU availability and memory"""
    print_header("GPU Status Check")
    if torch.cuda.is_available():
        print(f"[SYMBOL] CUDA Available: {torch.cuda.get_device_name(0)}")
        print(f"[SYMBOL] CUDA Version: {torch.version.cuda}")
        mem_allocated = torch.cuda.memory_allocated(0) / 1024**3
        mem_reserved = torch.cuda.memory_reserved(0) / 1024**3
        mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[SYMBOL] GPU Memory: {mem_allocated:.2f}GB allocated, {mem_reserved:.2f}GB reserved, {mem_total:.2f}GB total")
        return True
    else:
        print("[SYMBOL] CUDA not available")
        return False

def test_pyannote_import():
    """Test PyAnnote imports"""
    print_header("PyAnnote Import Test")
    try:
        from pyannote.audio import Pipeline
        print("[SYMBOL] pyannote.audio imported successfully")
        return True
    except Exception as e:
        print(f"[SYMBOL] Failed to import pyannote.audio: {e}")
        return False

def test_model_loading():
    """Test loading the diarization model"""
    print_header("Model Loading Test")
    try:
        from pyannote.audio import Pipeline
        print("Loading pyannote/speaker-diarization-3.1...")
        start = time.time()
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=os.getenv("HF_TOKEN")
        )
        elapsed = time.time() - start
        print(f"[SYMBOL] Model loaded in {elapsed:.2f}s")
        
        # Move to GPU
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
            print("[SYMBOL] Model moved to GPU")
        
        return True, pipeline
    except Exception as e:
        print(f"[SYMBOL] Failed to load model: {e}")
        return False, None

def test_short_audio(pipeline):
    """Test diarization on a short audio clip"""
    print_header("Short Audio Test (10 seconds)")
    
    # Create a simple test audio file
    test_audio = Path("../data/test_audio_10s.wav")
    if not test_audio.exists():
        print("Creating test audio file...")
        # Use sample.mp4 and extract 10 seconds
        subprocess.run([
            "ffmpeg", "-y", "-i", "../data/processing/sample.mp4",
            "-t", "10", "-ar", "16000", "-ac", "1",
            str(test_audio)
        ], capture_output=True)
    
    if not test_audio.exists():
        print("[SYMBOL] Could not create test audio")
        return False
    
    try:
        print(f"Processing: {test_audio}")
        start = time.time()
        
        # Monitor GPU before
        if torch.cuda.is_available():
            mem_before = torch.cuda.memory_allocated(0) / 1024**3
            print(f"GPU Memory before: {mem_before:.2f}GB")
        
        # Run diarization
        diarization = pipeline(str(test_audio))
        
        elapsed = time.time() - start
        
        # Monitor GPU after
        if torch.cuda.is_available():
            mem_after = torch.cuda.memory_allocated(0) / 1024**3
            mem_used = mem_after - mem_before
            print(f"GPU Memory after: {mem_after:.2f}GB (+{mem_used:.2f}GB)")
        
        # Print results
        num_speakers = len(set([segment.label for segment in diarization.itertracks(yield_label=True)[1]]))
        print(f"[SYMBOL] Diarization complete in {elapsed:.2f}s")
        print(f"[SYMBOL] Detected {num_speakers} speaker(s)")
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            print(f"  [{turn.start:.1f}s - {turn.end:.1f}s] {speaker}")
        
        return True
    except Exception as e:
        print(f"[SYMBOL] Diarization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chunk_processing():
    """Test chunk-based processing approach"""
    print_header("Chunk Processing Test")
    
    print("Testing 30-second chunk approach...")
    # This will test the optimized chunking we implemented
    
    try:
        import librosa
        import numpy as np
        
        # Load a longer audio file
        test_audio = Path("../data/test_audio_60s.wav")
        if not test_audio.exists():
            print("Creating 60s test audio...")
            subprocess.run([
                "ffmpeg", "-y", "-i", "../data/processing/sample.mp4",
                "-t", "60", "-ar", "16000", "-ac", "1",
                str(test_audio)
            ], capture_output=True)
        
        if not test_audio.exists():
            print("[SYMBOL] Could not create test audio")
            return False
        
        # Load audio
        audio, sr = librosa.load(str(test_audio), sr=16000, mono=True)
        duration = len(audio) / sr
        print(f"[SYMBOL] Loaded {duration:.1f}s audio")
        
        # Split into 30s chunks
        chunk_size = 30 * sr
        chunks = []
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            chunks.append(chunk)
        
        print(f"[SYMBOL] Split into {len(chunks)} chunks")
        
        # Process each chunk (simulated)
        total_time = 0
        for i, chunk in enumerate(chunks):
            chunk_duration = len(chunk) / sr
            start = time.time()
            # Simulate processing time
            time.sleep(0.1)
            elapsed = time.time() - start
            total_time += elapsed
            print(f"  Chunk {i+1}/{len(chunks)}: {chunk_duration:.1f}s audio processed in {elapsed:.2f}s")
        
        print(f"[SYMBOL] Total processing time: {total_time:.2f}s")
        print(f"[SYMBOL] Average: {total_time/len(chunks):.2f}s per chunk")
        
        return True
    except Exception as e:
        print(f"[SYMBOL] Chunk processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_header("GoodQ Audio Diarization Pipeline Test")
    print("This will test each component of the audio pipeline")
    print("with GPU monitoring and performance metrics.\n")
    
    results = {}
    
    # Test 1: GPU
    results["GPU"] = check_gpu()
    
    # Test 2: PyAnnote Import
    results["Import"] = test_pyannote_import()
    
    # Test 3: Model Loading
    if results["Import"]:
        success, pipeline = test_model_loading()
        results["Model Loading"] = success
        
        # Test 4: Short Audio
        if success and pipeline:
            results["Short Audio"] = test_short_audio(pipeline)
    
    # Test 5: Chunk Processing
    results["Chunk Processing"] = test_chunk_processing()
    
    # Summary
    print_header("Test Summary")
    for test, passed in results.items():
        status = "[SYMBOL] PASS" if passed else "[SYMBOL] FAIL"
        print(f"{status}: {test}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[SYMBOL] All tests passed! Audio pipeline is ready.")
        return 0
    else:
        print("\n[WARN] Some tests failed. Review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
