<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# ⚡ Immediate Fixes - GoodQ4All
**Priority:** Critical transcription fix  
**Estimated Time:** 1-2 hours  
**Success Criteria:** 95%+ transcript success rate

---

## 🎯 Fix #1: Whisper Transcription Debug Logging (15 min)

### Current Problem
100% transcript failures. Whisper.cpp works when tested directly, but fails silently in pipeline.

### Root Cause
Exception handling in `steps/audio_transcribe/step.py` suppresses error details.

### The Fix

**File:** `L:\goodq4all\steps\audio_transcribe\step.py`

**Location:** Lines 143-189 (function `_transcribe_chunk_whisper_cli`)

**Replace this:**
```python
def _transcribe_chunk_whisper_cli(chunk_path: str, offset: float, whisper_cli: str, whisper_model: str) -> Optional[Dict[str, Any]]:
    try:
        out_prefix = tempfile.NamedTemporaryFile(delete=False).name
        cmd = [
            whisper_cli,
            "-m",
            whisper_model,
            "-f",
            chunk_path,
            "-oj",
            "-of",
            out_prefix,
            "-pp",
        ]
        subprocess.run(cmd, check=True)
        json_path = out_prefix + ".json"
        txt_path = out_prefix + ".txt"
        # ... rest of parsing logic ...
    except Exception as e:
        print(f'[WARN] _transcribe_chunk_whisper_cli returning None')
        return None
```

**With this:**
```python
def _transcribe_chunk_whisper_cli(chunk_path: str, offset: float, whisper_cli: str, whisper_model: str) -> Optional[Dict[str, Any]]:
    try:
        # Check inputs
        if not os.path.isfile(chunk_path):
            print(f'[ERROR] Chunk file not found: {chunk_path}')
            return None
        
        chunk_size = os.path.getsize(chunk_path)
        if chunk_size == 0:
            print(f'[ERROR] Chunk file is empty: {chunk_path}')
            return None
        
        out_prefix = tempfile.NamedTemporaryFile(delete=False).name
        cmd = [
            whisper_cli,
            "-m",
            whisper_model,
            "-f",
            chunk_path,
            "-oj",
            "-of",
            out_prefix,
            "-pp",
        ]
        
        # Run with captured output
        print(f'[DEBUG] Whisper command: {" ".join(cmd)}')
        print(f'[DEBUG] Chunk: {chunk_path} ({chunk_size} bytes)')
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        if result.stdout:
            print(f'[DEBUG] Whisper stdout: {result.stdout[:200]}...')
        if result.stderr:
            print(f'[DEBUG] Whisper stderr: {result.stderr[:200]}...')
        
        json_path = out_prefix + ".json"
        txt_path = out_prefix + ".txt"
        
        # Check if output files were created
        if not os.path.isfile(json_path) and not os.path.isfile(txt_path):
            print(f'[ERROR] Whisper produced no output files')
            print(f'[ERROR] Expected: {json_path} or {txt_path}')
            return None
        
        transcript = None
        segments: List[Dict[str, Any]] = []
        
        if os.path.isfile(json_path):
            json_size = os.path.getsize(json_path)
            print(f'[DEBUG] Found JSON: {json_path} ({json_size} bytes)')
            
            if json_size == 0:
                print(f'[ERROR] JSON file is empty')
            else:
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = _json.load(f)
                    iterable = data if isinstance(data, list) else data.get("segments") or []
                    for seg in iterable:
                        start = float(seg.get("start", 0.0) or 0.0) + offset
                        end = float(seg.get("end", 0.0) or 0.0) + offset
                        text = seg.get("text", "") or ""
                        segments.append({"start": start, "end": end, "text": text})
                    transcript = " ".join(s.get("text", "").strip() for s in segments if s.get("text")) or None
                    print(f'[DEBUG] Parsed {len(segments)} segments from JSON')
                except Exception as json_err:
                    print(f'[ERROR] JSON parsing failed: {str(json_err)}')
                    # Try reading first 500 chars for diagnosis
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            preview = f.read(500)
                        print(f'[ERROR] JSON preview: {preview}...')
                    except:
                        pass
                    segments = []
        
        if transcript is None and os.path.isfile(txt_path):
            txt_size = os.path.getsize(txt_path)
            print(f'[DEBUG] Found TXT: {txt_path} ({txt_size} bytes)')
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    transcript = f.read().strip() or None
                print(f'[DEBUG] Read transcript from TXT: {len(transcript) if transcript else 0} chars')
            except Exception as txt_err:
                print(f'[ERROR] TXT reading failed: {str(txt_err)}')
                transcript = None
        
        if transcript is None:
            print(f'[WARN] No transcript extracted from whisper output')
        
        return {
            "transcript": transcript,
            "segments": segments,
            "engine": "whisper.cpp",
        }
    except subprocess.CalledProcessError as proc_err:
        print(f'[ERROR] Whisper subprocess failed with code {proc_err.returncode}')
        print(f'[ERROR] Command: {" ".join(cmd)}')
        print(f'[ERROR] Stdout: {proc_err.stdout}')
        print(f'[ERROR] Stderr: {proc_err.stderr}')
        return None
    except Exception as e:
        print(f'[ERROR] Whisper transcription failed: {type(e).__name__}: {str(e)}')
        print(f'[ERROR] Chunk: {chunk_path}')
        import traceback
        print(f'[ERROR] Traceback:\n{traceback.format_exc()}')
        return None
    finally:
        # Clean up temp files (but show what we're deleting in debug mode)
        debug_mode = os.environ.get('GOODQ_DEBUG_KEEP_TEMP', '').lower() == 'true'
        for ext in (".json", ".txt", ".srt", ".tsv"):
            try:
                fpath = out_prefix + ext
                if os.path.isfile(fpath):
                    if debug_mode:
                        print(f'[DEBUG] Keeping for inspection: {fpath}')
                    else:
                        os.remove(fpath)
            except Exception as e:
                pass
```

### Testing the Fix

```bash
# Set debug mode
$env:GOODQ_DEBUG_KEEP_TEMP="true"

# Test with a single scene
cd L:\goodq4all
conda activate goodq_zenml
python cli\run_ingestion.py ingest data\processing\1987_1988.mp4 --max-scenes 1

# Check the detailed logs
Get-Content logs\watchdog.log -Tail 100 | Select-String -Pattern "DEBUG|ERROR"
```

### Expected Outcomes

After adding this logging, you'll see one of these:

**Scenario A: JSON file is empty**
```
[DEBUG] Found JSON: /tmp/whisper_abc123.json (0 bytes)
[ERROR] JSON file is empty
```
→ **Fix:** Whisper.cpp may need different flags or model is incompatible

**Scenario B: JSON parsing error**
```
[ERROR] JSON parsing failed: JSONDecodeError
[ERROR] JSON preview: {"error": "...
```
→ **Fix:** Output format different than expected

**Scenario C: Subprocess failure**
```
[ERROR] Whisper subprocess failed with code 1
[ERROR] Stderr: Error loading model...
```
→ **Fix:** Model path or CUDA config issue

**Scenario D: Audio chunk issues**
```
[ERROR] Chunk file is empty: /tmp/chunk.wav
```
→ **Fix:** Audio slicing logic needs adjustment

---

## 🎯 Fix #2: Audio Chunk Validation (10 min)

### Problem
Audio slicing may create invalid/empty WAV files.

### The Fix

**File:** `L:\goodq4all\steps\audio_transcribe\step.py`

**Location:** After line 313 (inside the chunk processing loop)

**Add this validation:**
```python
for chunk in chunks:
    start = float(chunk["start"])
    end = float(chunk["end"])
    speaker = chunk.get("speaker")
    tmp_chunk = _slice_to_wav(path, start, end, ffmpeg_path)
    
    # NEW: Validate chunk before transcribing
    if not tmp_chunk:
        chunk_reports.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "status": "error",
            "error": "slice_failed",
        })
        continue
    
    # NEW: Check chunk is valid
    if not os.path.isfile(tmp_chunk):
        print(f'[ERROR] Chunk file not created: {tmp_chunk}')
        chunk_reports.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "status": "error",
            "error": "chunk_missing",
        })
        continue
    
    chunk_size = os.path.getsize(tmp_chunk)
    if chunk_size < 1000:  # Less than 1KB is likely invalid
        print(f'[ERROR] Chunk too small: {chunk_size} bytes')
        try:
            os.remove(tmp_chunk)
        except:
            pass
        chunk_reports.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "status": "error",
            "error": "chunk_too_small",
        })
        continue
    
    # NEW: Verify it's a valid WAV
    try:
        import soundfile as sf
        with sf.SoundFile(tmp_chunk) as fh:
            duration = fh.frames / fh.samplerate
            if duration < 0.1:
                print(f'[ERROR] Chunk duration too short: {duration}s')
                os.remove(tmp_chunk)
                chunk_reports.append({
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                    "status": "error",
                    "error": "duration_too_short",
                })
                continue
            print(f'[DEBUG] Valid chunk: {chunk_size} bytes, {duration:.2f}s')
    except Exception as val_err:
        print(f'[ERROR] Chunk validation failed: {str(val_err)}')
        try:
            os.remove(tmp_chunk)
        except:
            pass
        chunk_reports.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "status": "error",
            "error": "validation_failed",
        })
        continue
    
    # Continue with transcription...
    try:
        result = None
        if whisper_cli:
            result = _transcribe_chunk_whisper_cli(tmp_chunk, start, whisper_cli, whisper_model_path)
        # ... rest of existing code ...
```

---

## 🎯 Fix #3: Add Diagnostic Script (20 min)

Create a standalone diagnostic that tests transcription in isolation.

**File:** `L:\goodq4all\scripts\diagnose_transcription.py`

```python
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
    whisper_cli = Path("L:/_TOOLS/whisper/whisper-cli.exe")
    whisper_model = Path("L:/_TOOLS/whisper/ggml-large-v3.bin")
    
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
```

**Run it:**
```bash
cd L:\goodq4all
conda activate goodq_zenml
python scripts\diagnose_transcription.py
```

---

## 🎯 Fix #4: Test with Single Scene (5 min)

After applying fixes 1-3, test with one scene:

```bash
# Enable debug mode
$env:GOODQ_DEBUG_KEEP_TEMP="true"

# Find the smallest recent scene
$scene = Get-ChildItem L:\goodq4all\logs\watchdog_20251014_024332\1987_1988\audio\scene_*.wav | Sort-Object Length | Select-Object -First 1

# Process just this scene's parent video
cd L:\goodq4all
conda activate goodq_zenml

# Or better yet, use the diagnostic script first
python scripts\diagnose_transcription.py

# If diagnostic passes, try full pipeline
python cli\run_ingestion.py ingest data\processing\1987_1988.mp4 --max-scenes 1
```

---

## Success Criteria Checklist

After implementing these fixes, you should see:

- ✅ **Diagnostic script passes** all 6 tests
- ✅ **Detailed error logs** show exact failure point (if any)
- ✅ **Chunk validation** catches invalid audio before transcription
- ✅ **At least 1 successful transcript** from test scene
- ✅ **Database shows** `transcript_meta.status = "ok"` for at least some scenes

---

## Next Steps After Fix

1. **If diagnostic passes but pipeline fails:**
   - Issue is in chunk slicing
   - Check audio file duration checks
   - Verify ffmpeg parameters

2. **If diagnostic fails on JSON mode:**
   - Whisper.cpp version incompatibility
   - Try different output flags
   - May need to use faster-whisper instead

3. **If some scenes work, some fail:**
   - Pattern analysis of working vs failing scenes
   - Check audio duration thresholds
   - Review VAD (voice activity detection) settings

4. **Once working at 95%+:**
   - Remove debug logging (or gate behind env var)
   - Update documentation
   - Add integration tests

---

**Fixes Ready to Apply** | Start with Fix #1 | Estimated time: 15 minutes | Expected result: Clear root cause identification

