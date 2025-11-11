# Audio Diarization Stalling - Root Cause Analysis & Fix

## Issue Summary
The audio diarization step was stalling during video ingestion, preventing the pipeline from completing successfully.

## Root Causes Identified

### 1. **Unicode Encoding Error (CRITICAL)**
**Location:** `cli/run_ingestion.py` lines 474, 548, 576  
**Problem:** Subprocess calls used `text=True` without specifying encoding, defaulting to Windows charmap codec which cannot handle Unicode characters like '→' in ffmpeg output.

**Error Message:**
```
[ERROR] Frame extraction failed for scene 0: 'charmap' codec can't encode character '\u2192' in position 2: character maps to <undefined>
```

**Fix Applied:**
- Added `encoding='utf-8'` and `errors='replace'` to all subprocess.run() calls
- Files updated:
  - `cli/run_ingestion.py` (3 locations)
  - `scripts/watchdog_ingest.py` (1 location)
  - `steps/audio_transcribe/step.py` (1 location)
  - `steps/common/conda_runner.py` (1 location)

### 2. **Missing Step Timeout Configuration**
**Location:** `scripts/watchdog_ingest.py` line 407  
**Problem:** Watchdog wasn't passing `--step-timeout` to run_ingestion, allowing individual steps to hang indefinitely.

**Fix Applied:**
- Added `--step-timeout 600` (10 minutes) to watchdog command
- This provides adequate time for diarization on 5-minute scene chunks while preventing infinite hangs

### 3. **Lack of Progress Logging in Diarization**
**Location:** `steps/audio_diarize/step.py`  
**Problem:** No visibility into diarization progress or performance, making it appear "stuck" even when running normally.

**Fix Applied:**
- Added timing and progress logging
- Added file size logging
- Added segment count reporting
- Added device (CPU/GPU) reporting
- Added config check to skip if disabled

## Configuration Changes

### Config: `config.yaml`
```yaml
audio:
  diarization:
    enabled: true  # Can disable if not needed
    min_speakers: 1
    max_speakers: 10
    model: "pyannote/speaker-diarization@2.1"  # Explicit model config
```

### Timeout Settings
- **Per-step timeout:** 600 seconds (10 minutes)
- **Total video timeout:** Dynamic based on file size (8 hours + 3 hours per GB)
- **Scene minimum duration:** 300 seconds (5 minutes) - prevents excessive scene splitting

## Testing Recommendations

1. **Test with sample video** (2GB file):
   ```powershell
   python -m cli.run_ingestion --input-dir "L:/_DATA/FAMILY_FEAST" --workspace "L:/goodq4all/logs/test" --output "L:/goodq4all/logs/test_results.json" --step-timeout 600 --verbose
   ```

2. **Monitor logs for:**
   - `[DIARIZE] Starting diarization...` - Confirms step started
   - `[DIARIZE] Completed in Xs` - Confirms step completed
   - No charmap encoding errors
   - Proper scene detection (5+ minute scenes, not 2-second scenes)

3. **Check output:**
   - `output/videos/[video_name]/audio/` - Should contain scene audio files
   - `data/memory.db` - Query for diarization segments
   - Progress tracker updates

## Expected Behavior After Fix

1. **No encoding errors** - Unicode characters handled gracefully
2. **Diarization completes** - Within 10-minute timeout per scene
3. **Progress visibility** - Clear logging of each step
4. **Graceful degradation** - If PyAnnote auth token missing, step skips with warning instead of failing

## Performance Notes

- **PyAnnote on CPU:** ~30-60 seconds per minute of audio
- **PyAnnote on GPU (CUDA):** ~3-10 seconds per minute of audio
- **5-minute scenes:** Expected 2.5-5 minutes on CPU, 15-50 seconds on GPU

## Related Files Modified

1. `cli/run_ingestion.py` - Fixed encoding + subprocess calls
2. `scripts/watchdog_ingest.py` - Added step timeout + encoding fix
3. `steps/audio_diarize/step.py` - Added logging + config checks
4. `steps/audio_transcribe/step.py` - Fixed encoding
5. `steps/common/conda_runner.py` - Fixed encoding

## Verification Steps

Run the validation script:
```powershell
python L:/goodq4all/scripts/validate_python_paths.py
```

Check for remaining encoding issues:
```powershell
Get-ChildItem -Path "L:\goodq4all" -Recurse -Filter "*.py" | Select-String -Pattern "subprocess.run.*text=True" | Where-Object { $_.Line -notlike "*encoding*" }
```

## Next Steps

1. **Test full ingestion** with real home movie
2. **Monitor GPU utilization** during diarization
3. **Consider alternative:** If PyAnnote continues to be slow, could switch to Whisper's built-in speaker detection or use pyannote-audio's faster models
4. **Optimize:** If needed, could pre-filter silent portions before diarization

---
**Status:** ✅ FIXED  
**Date:** 2025-11-10  
**Tested:** Pending real-world validation
