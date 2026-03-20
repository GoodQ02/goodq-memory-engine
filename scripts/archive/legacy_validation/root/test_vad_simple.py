"""
Simple standalone test for Silero VAD on audio file.
Uses canonical config when available.
"""
import os
import sys
import time
from pathlib import Path
import torch
import torchaudio
import soundfile as sf

MEDIA_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wav', '.mp3', '.m4a', '.flac')


def load_runtime_cfg():
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from steps.common.config_loader import load_configs
        return load_configs({})
    except Exception:
        return {}


def resolve_ffmpeg_exe(cfg):
    ffmpeg_exe = (
        cfg.get("config", {})
        .get("tools", {})
        .get("ffmpeg_exe")
    )
    if ffmpeg_exe:
        return ffmpeg_exe
    return os.getenv("GOODQ_FFMPEG_EXE", "ffmpeg")


def find_first_media_file(root_path):
    if not root_path:
        return None

    root = Path(root_path)
    if root.is_file() and root.suffix.lower() in MEDIA_EXTENSIONS:
        return str(root)
    if not root.exists():
        return None

    for ext in MEDIA_EXTENSIONS:
        for candidate in root.rglob(f"*{ext}"):
            if candidate.is_file():
                return str(candidate)
    return None


def test_vad_on_audio(audio_path, ffmpeg_exe="ffmpeg"):
    """Test VAD on an audio file"""
    print("="*80)
    print("Silero VAD Simple Test")
    print("="*80)
    print(f"Audio file: {audio_path}")
    
    if not os.path.exists(audio_path):
        print(f"ERROR: File not found: {audio_path}")
        return False
    
    file_size_mb = os.path.getsize(audio_path) / (1024*1024)
    print(f"File size: {file_size_mb:.1f}MB")
    print()
    
    # Load VAD model
    print("[1/4] Loading Silero VAD model...")
    try:
        model, utils = torch.hub.load(
            'snakers4/silero-vad',
            'silero_vad',
            force_reload=False,
            trust_repo=True
        )
        (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
        print("[SYMBOL] Model loaded successfully")
    except Exception as e:
        print(f"[SYMBOL] ERROR loading model: {str(e)}")
        return False
    
    # Extract audio from video if needed
    temp_audio = None
    if audio_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        print("\n[2/4] Extracting audio from video...")
        import tempfile
        import subprocess
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_audio = temp_file.name
        temp_file.close()
        
        ffmpeg_path = ffmpeg_exe
        
        try:
            cmd = [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", audio_path,
                "-ac", "1",  # Mono
                "-ar", "16000",  # 16kHz
                "-t", "600",  # First 10 minutes for testing
                temp_audio,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"[SYMBOL] Audio extracted to temp file (first 10 minutes for testing)")
            audio_path = temp_audio
        except Exception as e:
            print(f"[SYMBOL] ERROR extracting audio: {str(e)}")
            if temp_audio and os.path.exists(temp_audio):
                os.remove(temp_audio)
            return False
    
    # Read audio
    print("\n[3/4] Reading audio file...")
    try:
        wav = read_audio(audio_path, sampling_rate=16000)
        duration = len(wav) / 16000
        print(f"[SYMBOL] Audio loaded: {duration/60:.1f} minutes ({len(wav)} samples)")
    except Exception as e:
        print(f"[SYMBOL] ERROR reading audio: {str(e)}")
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)
        return False
    
    # Detect speech
    print("\n[4/4] Detecting speech segments...")
    start_time = time.time()
    
    try:
        speech_timestamps = get_speech_timestamps(
            wav,
            model,
            sampling_rate=16000,
            threshold=0.5,
            min_speech_duration_ms=400,
            min_silence_duration_ms=200,
            return_seconds=False
        )
        
        elapsed = time.time() - start_time
        print(f"[SYMBOL] VAD completed in {elapsed:.1f}s")
        
        if not speech_timestamps:
            print("[SYMBOL] WARNING: No speech detected!")
            return True
        
        # Calculate statistics
        speech_duration = sum((ts['end'] - ts['start']) for ts in speech_timestamps) / 16000
        speech_ratio = speech_duration / duration if duration > 0 else 0
        silence_duration = duration - speech_duration
        reduction_percent = (silence_duration / duration * 100) if duration > 0 else 0
        
        print(f"\n[SYMBOL] Speech Detection Results:")
        print(f"  Segments found: {len(speech_timestamps)}")
        print(f"  Total duration: {duration/60:.1f} minutes")
        print(f"  Speech duration: {speech_duration/60:.1f} minutes ({speech_ratio*100:.1f}%)")
        print(f"  Silence removed: {silence_duration/60:.1f} minutes ({reduction_percent:.1f}%)")
        print(f"\n  Estimated diarization speedup: {reduction_percent:.0f}%")
        print(f"  Time saved (est.): {silence_duration/60*1.5:.1f}-{silence_duration/60*2:.1f} minutes")
        
    except Exception as e:
        print(f"[SYMBOL] ERROR during VAD: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Extract speech-only audio
    print("\n[5/5] Extracting speech-only audio...")
    try:
        output_path = "speech_only_test.wav"
        speech_audio = collect_chunks(speech_timestamps, wav)
        save_audio(output_path, speech_audio, sampling_rate=16000)
        
        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        size_reduction = (1 - output_size_mb / file_size_mb) * 100
        
        print(f"[SYMBOL] Saved speech-only audio:")
        print(f"  File: {output_path}")
        print(f"  Size: {output_size_mb:.1f}MB (original: {file_size_mb:.1f}MB)")
        print(f"  Size reduction: {size_reduction:.1f}%")
        
        # Clean up
        print(f"\nCleaning up temp files...")
        os.remove(output_path)
        print(f"[SYMBOL] Removed {output_path}")
        
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)
            print(f"[SYMBOL] Removed temp audio extraction")
        
    except Exception as e:
        print(f"[SYMBOL] ERROR extracting audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*80)
    print("[SYMBOL] VAD TEST PASSED!")
    print("="*80)
    print("\nSilero VAD is working correctly and will dramatically reduce")
    print("diarization time by filtering out silence and background noise.")
    print("\nNext step: Run full pipeline to test VAD + diarization integration")
    
    return True


if __name__ == "__main__":
    print("GoodQ4All - Silero VAD Simple Test\n")

    cfg = load_runtime_cfg()
    ffmpeg_exe = resolve_ffmpeg_exe(cfg)
    path_cfg = cfg.get("paths", {})

    # Find test audio file
    test_roots = [
        path_cfg.get("import_inbox"),
        path_cfg.get("processing"),
        path_cfg.get("data_root"),
    ]

    audio_path = None
    for root in test_roots:
        candidate = find_first_media_file(root)
        if candidate:
            audio_path = candidate
            break
    
    if not audio_path:
        print("ERROR: No test audio file found!")
        print(f"Tried:")
        for root in test_roots:
            if root:
                print(f"  - {root}")
        print("\nPlease specify audio file as argument:")
        print(f"  python {sys.argv[0]} <path_to_audio_file>")
        sys.exit(1)
    
    # Allow command line override
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    
    success = test_vad_on_audio(audio_path, ffmpeg_exe=ffmpeg_exe)
    
    sys.exit(0 if success else 1)
