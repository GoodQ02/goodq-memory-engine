"""
GoodQ4All - Audio Pipeline GPU Test
Tests audio diarization with GPU acceleration
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_audio_pipeline():
    """Test complete audio pipeline with GPU monitoring"""
    print("\n" + "="*80)
    print("GoodQ4All - Audio Pipeline GPU Test")
    print("="*80 + "\n")
    
    # Import after path setup
    import torch
    import torchaudio
    
    print("[1/6] GPU Status Check...")
    if torch.cuda.is_available():
        print(f"  ✓ CUDA Available: {torch.cuda.is_available()}")
        print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
        print(f"  ✓ VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        print(f"  ✓ Current Memory Allocated: {torch.cuda.memory_allocated(0) / 1e9:.2f} GB")
    else:
        print("  ✗ CUDA not available")
        return False
    
    print("\n[2/6] Import GoodQ Steps...")
    try:
        from steps.audio_diarize import audio_diarize
        print("  ✓ audio_diarize imported")
    except Exception as e:
        print(f"  ✗ Failed to import: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[3/6] Find Test Video...")
    # Check for video in import_inbox or processing
    test_video = None
    
    # Check import_inbox
    inbox_path = Path("L:/goodq4all/import_inbox")
    if inbox_path.exists():
        videos = list(inbox_path.glob("*.mp4"))
        if videos:
            test_video = videos[0]
            print(f"  ✓ Found video in import_inbox: {test_video.name}")
    
    # Check processing area
    if not test_video:
        processing_path = Path("L:/goodq4all/data/processing")
        if processing_path.exists():
            for subdir in processing_path.iterdir():
                if subdir.is_dir():
                    videos = list(subdir.glob("*.mp4"))
                    if videos:
                        test_video = videos[0]
                        print(f"  ✓ Found video in processing: {test_video.name}")
                        break
    
    if not test_video:
        print("  ✗ No test video found")
        print("  Place a video file in L:/goodq4all/import_inbox/")
        return False
    
    print(f"\n[4/6] Prepare for Diarization...")
    print(f"  ✓ Step will extract audio internally")
    
    # Estimate duration from video file
    try:
        import subprocess
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(test_video)],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        if duration > 0:
            print(f"  ✓ Video duration: {duration:.1f}s ({duration/60:.1f} min)")
        else:
            duration = 300  # Default estimate
            print(f"  ℹ Using default duration estimate: {duration}s")
    except:
        duration = 300  # Default 5 minutes
        print(f"  ℹ Using default duration estimate: {duration}s")
    
    print(f"\n[5/6] Run Audio Diarization...")
    print(f"  This will test GPU-accelerated diarization")
    print(f"  Expected processing time: ~{duration/30:.0f}s for {duration:.0f}s audio\n")
    
    start_time = time.time()
    start_mem = torch.cuda.memory_allocated(0) / 1e9
    
    try:
        # Prepare item dict for the step
        item = {
            "video_id": test_video.stem,
            "source_path": str(test_video)  # Step expects 'source_path'
        }
        
        # Load config from config.yaml
        import yaml
        config_path = Path("L:/goodq4all/config.yaml")
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
        else:
            cfg = {}
        
        # Ensure audio diarization config is set
        if "audio" not in cfg:
            cfg["audio"] = {}
        if "diarization" not in cfg["audio"]:
            cfg["audio"]["diarization"] = {}
        
        cfg["audio"]["diarization"].update({
            "enabled": True,
            "model": "pyannote/speaker-diarization@2.1",
            "token_env": "HF_TOKEN",
            "vad_enabled": True,
            "vad_threshold": 0.5,
            "vad_min_speech_ms": 400,
            "vad_min_silence_ms": 200
        })
        
        # Run diarization
        print("  Starting diarization pipeline...")
        result = audio_diarize(item, cfg)
        
        end_time = time.time()
        end_mem = torch.cuda.memory_allocated(0) / 1e9
        elapsed = end_time - start_time
        
        print(f"\n  ✓ Diarization completed!")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Speed: {duration/elapsed:.1f}x realtime")
        print(f"  Peak VRAM: {end_mem:.2f} GB (Δ {end_mem - start_mem:.2f} GB)")
        
        if result and "diarization" in result:
            diar_data = result["diarization"]
            print(f"\n  Results:")
            if "speakers" in diar_data:
                print(f"    Speakers detected: {len(diar_data['speakers'])}")
                for speaker, segments in list(diar_data['speakers'].items())[:5]:
                    print(f"    {speaker}: {len(segments)} segments")
            elif "segments" in diar_data:
                segments = diar_data["segments"]
                speakers = set(s.get("speaker", "") for s in segments)
                print(f"    Speakers detected: {len(speakers)}")
                print(f"    Total segments: {len(segments)}")
        
    except Exception as e:
        print(f"  ✗ Diarization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n[6/6] Cleanup...")
    # Clean GPU memory
    torch.cuda.empty_cache()
    print(f"  ✓ GPU memory cleared")
    
    print("\n" + "="*80)
    print("✓ Audio Pipeline Test PASSED")
    print("="*80 + "\n")
    
    return True

if __name__ == "__main__":
    success = test_audio_pipeline()
    sys.exit(0 if success else 1)
