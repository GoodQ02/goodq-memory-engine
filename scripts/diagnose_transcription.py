"""Diagnostic script for audio transcription issues."""
import os
import sys
import subprocess
import tempfile
from pathlib import Path

def main():
    print("=" * 80)
    print("WHISPER TRANSCRIPTION DIAGNOSTIC")
    print("=" * 80)
    
    # Configuration
    whisper_cli = Path("L:/Tools/whisper/whisper-cli.exe")
    whisper_model = Path("L:/Tools/whisper/ggml-large-v3.bin")
    
    # Find a test audio file
    workspace = Path("L:/goodq4all/logs")
    test_audio = None
    for audio_dir in workspace.glob("watchdog_*/*/audio"):
        for wav in audio_dir.glob("scene_*.wav"):
            if wav.stat().st_size > 10000:  # At least 10KB
                test_audio = wav
                break
        if test_audio:
            break
    
    if not test_audio:
        print("[ERROR] No test audio files found")
        return 1
    
    print(f"\n[1] Test Audio: {test_audio}")
    print(f"    Size: {test_audio.stat().st_size:,} bytes")
    
    # Check whisper.cpp
    print(f"\n[2] Whisper CLI: {whisper_cli}")
    if not whisper_cli.exists():
        print("    [ERROR] Whisper CLI not found!")
        return 1
    print("    [OK] Found")
    
    print(f"\n[3] Whisper Model: {whisper_model}")
    if not whisper_model.exists():
        print("    [ERROR] Model not found!")
        return 1
    print(f"    [OK] Found ({whisper_model.stat().st_size / 1e9:.2f} GB)")
    
    # Test direct transcription (plain text)
    print(f"\n[4] Testing direct transcription (text mode)...")
    cmd_txt = [
        str(whisper_cli),
        "-m", str(whisper_model),
        "-f", str(test_audio),
        "-nt"  # No timestamps
    ]
    try:
        result = subprocess.run(cmd_txt, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            transcript = result.stdout.strip()
            print(f"    [OK] Transcript: {transcript[:100]}...")
        else:
            print(f"    [ERROR] Return code: {result.returncode}")
            print(f"    Stderr: {result.stderr[:200]}")
            return 1
    except subprocess.TimeoutExpired:
        print("    [ERROR] Timeout after 60s")
        return 1
    except Exception as e:
        print(f"    [ERROR] {type(e).__name__}: {str(e)}")
        return 1
    
    # Test JSON output (what pipeline uses)
    print(f"\n[5] Testing JSON output mode...")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_prefix = Path(tmpdir) / "whisper_test"
        cmd_json = [
            str(whisper_cli),
            "-m", str(whisper_model),
            "-f", str(test_audio),
            "-oj",
            "-of", str(out_prefix)
        ]
        try:
            result = subprocess.run(cmd_json, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                print(f"    [ERROR] Return code: {result.returncode}")
                print(f"    Stderr: {result.stderr[:200]}")
                return 1
            
            json_path = Path(str(out_prefix) + ".json")
            if not json_path.exists():
                print(f"    [ERROR] JSON file not created: {json_path}")
                return 1
            
            json_size = json_path.stat().st_size
            print(f"    [OK] JSON created: {json_size} bytes")
            
            if json_size == 0:
                print(f"    [ERROR] JSON file is empty!")
                return 1
            
            # Parse JSON
            import json
            with open(json_path) as f:
                data = json.load(f)
            
            if isinstance(data, list):
                segments = data
            else:
                segments = data.get("segments", [])
            
            print(f"    [OK] Parsed {len(segments)} segments")
            
            if segments:
                first = segments[0]
                print(f"    Sample: {first.get('text', '')}...")
            else:
                print(f"    [WARN] No segments in JSON")
            
        except subprocess.TimeoutExpired:
            print("    [ERROR] Timeout after 60s")
            return 1
        except json.JSONDecodeError as e:
            print(f"    [ERROR] JSON parsing failed: {str(e)}")
            # Show file content
            with open(json_path) as f:
                preview = f.read(500)
            print(f"    JSON preview: {preview}...")
            return 1
        except Exception as e:
            print(f"    [ERROR] {type(e).__name__}: {str(e)}")
            return 1
    
    # Test with -pp flag (post-process)
    print(f"\n[6] Testing with post-processing (-pp flag)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_prefix = Path(tmpdir) / "whisper_test_pp"
        cmd_pp = [
            str(whisper_cli),
            "-m", str(whisper_model),
            "-f", str(test_audio),
            "-oj",
            "-of", str(out_prefix),
            "-pp"  # Post-process flag used in pipeline
        ]
        try:
            result = subprocess.run(cmd_pp, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                print(f"    [ERROR] Return code: {result.returncode}")
                print(f"    Stderr: {result.stderr[:200]}")
                return 1
            
            json_path = Path(str(out_prefix) + ".json")
            if json_path.exists():
                json_size = json_path.stat().st_size
                print(f"    [OK] JSON with -pp: {json_size} bytes")
                
                if json_size > 0:
                    import json
                    with open(json_path) as f:
                        data = json.load(f)
                    segments = data if isinstance(data, list) else data.get("segments", [])
                    print(f"    [OK] {len(segments)} segments")
                else:
                    print(f"    [WARN] JSON is empty with -pp flag")
            else:
                print(f"    [ERROR] No JSON produced with -pp flag")
                return 1
                
        except Exception as e:
            print(f"    [ERROR] {type(e).__name__}: {str(e)}")
            return 1
    
    print(f"\n{'=' * 80}")
    print("DIAGNOSTIC COMPLETE: ALL TESTS PASSED ✓")
    print("=" * 80)
    print("\nWhisper.cpp is working correctly.")
    print("If pipeline transcription still fails, the issue is in:")
    print("  1. Audio chunk slicing (creates invalid WAV files)")
    print("  2. File path handling (temp files not found)")
    print("  3. Output parsing logic (JSON structure mismatch)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
