"""
Audio GPU Optimization Test Suite
Runs comprehensive tests of audio pipeline with GPU acceleration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import subprocess
import time
from pathlib import Path
from datetime import datetime
import shutil


def check_gpu_available():
    """Check if GPU is available"""
    try:
        result = subprocess.run(
            ["nvidia-smi"], 
            capture_output=True, 
            check=True,
            timeout=5
        )
        print("✅ GPU detected")
        return True
    except:
        print("❌ No GPU detected - tests will run on CPU")
        return False


def check_sample_video():
    """Check if sample video exists"""
    sample_paths = [
        Path("L:/goodq4all/import_inbox/sample.mp4"),
        Path("L:/goodq4all/test_input/sample.mp4"),
        Path("L:/_DATA/FAMILY_FEAST/01. 1987 - 1988.mp4"),
    ]
    
    for path in sample_paths:
        if path.exists():
            print(f"✅ Found sample video: {path}")
            return path
    
    print("❌ No sample video found")
    print("   Please place a video in one of these locations:")
    for path in sample_paths:
        print(f"   - {path}")
    return None


def run_pipeline_test(sample_video, monitor=True):
    """Run pipeline on sample video with optional GPU monitoring"""
    
    print("\n" + "="*80)
    print("Running Pipeline Test")
    print("="*80 + "\n")
    
    # Copy sample to import inbox
    inbox = Path("L:/goodq4all/import_inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    
    test_video = inbox / "gpu_test.mp4"
    
    # Clean up any existing test video
    if test_video.exists():
        test_video.unlink()
    
    print(f"Copying test video to inbox...")
    shutil.copy(sample_video, test_video)
    
    print(f"Test video: {test_video}")
    print(f"Size: {test_video.stat().st_size / (1024*1024):.1f} MB\n")
    
    # Start GPU monitor if requested
    monitor_proc = None
    if monitor:
        print("Starting GPU monitor...")
        monitor_proc = subprocess.Popen(
            [sys.executable, "scripts/audio_gpu_monitor.py"],
            cwd="L:/goodq4all"
        )
        time.sleep(2)
    
    # Run watchdog ingestion
    print("\nStarting pipeline...")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        # Run watchdog in subprocess
        proc = subprocess.Popen(
            [sys.executable, "scripts/watchdog_ingest.py"],
            cwd="L:/goodq4all",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output
        for line in iter(proc.stdout.readline, ''):
            if line:
                print(line.rstrip())
                
                # Check for completion
                if "COMPLETE" in line or "SUCCESS" in line:
                    break
                
                # Check for errors
                if "ERROR" in line or "FAILED" in line:
                    print(f"\n⚠️  Error detected: {line}")
        
        # Wait a bit for completion
        time.sleep(2)
        proc.terminate()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if proc:
            proc.terminate()
    
    elapsed = time.time() - start_time
    
    print("\n" + "-" * 80)
    print(f"Pipeline test completed in {elapsed:.1f}s ({elapsed/60:.1f}min)")
    
    # Stop monitor
    if monitor_proc:
        print("\nStopping GPU monitor...")
        monitor_proc.terminate()
        monitor_proc.wait(timeout=5)
    
    # Clean up test video
    if test_video.exists():
        test_video.unlink()
    
    print("\n" + "="*80)


def run_audio_step_tests():
    """Run individual tests for audio steps"""
    
    print("\n" + "="*80)
    print("Testing Audio Steps Individually")
    print("="*80 + "\n")
    
    # Test diarization
    print("1. Testing Audio Diarization GPU Setup")
    print("-" * 80)
    
    test_code = """
from steps.common.audio_gpu_optimizer import get_audio_gpu_optimizer

optimizer = get_audio_gpu_optimizer()

# Test diarization config
config = optimizer.configure_for_diarization(duration_minutes=15.0)
print(f"Diarization config: {config.memory_fraction*100:.0f}% VRAM, {config.device}")

optimizer.print_memory_stats()

# Test transcription config  
config = optimizer.configure_for_transcription(duration_minutes=15.0)
print(f"Transcription config: {config.memory_fraction*100:.0f}% VRAM, {config.device}")

optimizer.print_memory_stats()

print("✅ Audio GPU optimizer working correctly")
"""
    
    try:
        subprocess.run(
            [sys.executable, "-c", test_code],
            cwd="L:/goodq4all",
            check=True
        )
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    print("\n" + "="*80)


def main():
    """Main test suite"""
    
    print("\n" + "="*80)
    print("Audio GPU Optimization Test Suite")
    print("="*80 + "\n")
    
    print("This will test GPU-accelerated audio processing.\n")
    
    # Check prerequisites
    print("Checking prerequisites...")
    print("-" * 80)
    
    gpu_available = check_gpu_available()
    sample_video = check_sample_video()
    
    if not sample_video:
        print("\n❌ Cannot proceed without sample video")
        return
    
    print("\n" + "="*80)
    print("Test Options:")
    print("="*80)
    print("1. Run full pipeline test with GPU monitoring")
    print("2. Run audio step unit tests")
    print("3. Run both")
    print("4. Generate performance report")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == "1":
        run_pipeline_test(sample_video, monitor=gpu_available)
    
    elif choice == "2":
        run_audio_step_tests()
    
    elif choice == "3":
        run_audio_step_tests()
        run_pipeline_test(sample_video, monitor=gpu_available)
    
    elif choice == "4":
        print("\nGenerating performance report...")
        subprocess.run([sys.executable, "scripts/audio_gpu_report.py"], cwd="L:/goodq4all")
    
    else:
        print("Exiting...")
        return
    
    print("\n" + "="*80)
    print("Test suite complete!")
    print("="*80 + "\n")
    
    # Ask if user wants to see report
    if input("Generate performance report? (y/n): ").lower() == 'y':
        subprocess.run([sys.executable, "scripts/audio_gpu_report.py"], cwd="L:/goodq4all")


if __name__ == "__main__":
    main()
