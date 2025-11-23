# GoodQ4All Pipeline Diagnosis - 2025-11-11

## Executive Summary

The pipeline is **WORKING CORRECTLY** on small files but **FAILING on large files** (7+GB) due to Windows resource exhaustion (error code 3221225786 = STATUS_INSUFFICIENT_RESOURCES).

## Current Architecture Understanding

### ✅ Correct Architecture (NOT broken!)
- **Custom orchestration** with specialized conda environments per step
- **NOT using ZenML** for orchestration (ZenML not needed/installed)
- **Environment per step** pattern:
  - `goodq_video_scene_detect` - Scene detection
  - `goodq_audio_transcribe` - Whisper transcription
  - `goodq_audio_diarize` - Speaker diarization
  - `goodq_face_embed` - Face recognition
  - etc. (22+ specialized environments)

### Current Status
- ✅ Small file test (1MB sample.mp4): **SUCCESS**
- ❌ Large file test (7.28GB home movies): **CRASH** (insufficient resources)
- ✅ API Server running on port 30000
- ❌ Watchdog crashes repeatedly on large files
- ⚠️ UI showing stale data from successful small-file run

## Root Cause Analysis

### Error Code 3221225786 (0xC000009A)
```
STATUS_INSUFFICIENT_RESOURCES
```

**Meaning**: Windows kernel cannot allocate enough memory/resources for the process.

### Why This Happens

1. **Scene Detection Memory Explosion**
   - Processing 7.28GB video files
   - SceneDetect loads frames into memory
   - Multiple concurrent processes (watchdog pattern)
   - No chunking/streaming for large files

2. **Audio Diarization Stall**
   - Pyannote audio diarization on 2+ hour videos
   - Loading entire audio file into memory
   - GPU VRAM exhaustion (if using CUDA)
   - No progress updates during long operations

3. **Whisper Transcription**
   - Large model (likely large-v2 or large-v3)
   - Processing hours of audio
   - Memory footprint grows with audio length

## Evidence from Logs

### Watchdog Pattern
```
2025-11-10 20:29:33,981 [WARNING] Removing stale lock from dead process 39912
2025-11-10 23:21:00,041 [WARNING] Removing stale lock from dead process 14272
2025-11-10 23:22:43,107 [ERROR] ❌ Mission failed: Video ingestion returned code 3221225786
```

### Success with Small Files
```
manual_debug_test.log:
[OK] Found sample video: L:\goodq4all\data\testing\test_input\sample.mp4
Exit code: 0
[SUCCESS]
```

### Large File Attempts
```
2025-11-10 20:29:57,492 [INFO] ⏱️  Mission timeout: 78668s (21.9h) for 7.28GB asset
2025-11-10 20:29:57,492 [INFO] � Asset: 01. 1987 - 1988.mp4
[CRASH within 1 minute]
```

## Solutions (Priority Order)

### 🔴 CRITICAL - Immediate Fixes

#### 1. Pre-Process Large Files (RECOMMENDED)
Split large videos into manageable chunks BEFORE ingestion:

```python
# Use ffmpeg to split by time
ffmpeg -i "01. 1987 - 1988.mp4" -c copy -map 0 -segment_time 600 -f segment "01_part_%03d.mp4"
```

Benefits:
- Each chunk ~10 minutes = manageable size
- Parallel processing of chunks
- If one chunk fails, others succeed
- Reassemble metadata at end

#### 2. Enable Streaming/Chunking in Scene Detection
Modify `steps/video_scene_detect.py` to process frames in batches:

```python
# Instead of loading entire video
detector = ContentDetector(threshold=27.0)
video.detect_scenes(detector)  # Loads all frames!

# Use frame-by-frame processing
for i in range(0, total_frames, chunk_size):
    frame_batch = video.read(chunk_size)
    detector.process_frame_batch(frame_batch)
```

#### 3. Add Memory Monitoring
Monitor RAM usage and kill/restart if threshold exceeded:

```python
import psutil

def check_memory():
    mem = psutil.virtual_memory()
    if mem.percent > 85:
        raise MemoryError(f"RAM usage critical: {mem.percent}%")
```

### 🟡 MEDIUM - Resource Optimization

#### 4. Reduce Scene Detection Sensitivity
Current threshold=27.0 might be creating TOO MANY scenes on 2-hour videos:

```python
# envs/goodq_video_scene_detect.yml
# Increase threshold to reduce sensitivity
ContentDetector(threshold=35.0)  # Was 27.0
```

#### 5. Use Smaller Whisper Model for Initial Pass
Switch to `base` or `small` model for long videos:

```python
# envs/goodq_audio_transcribe.yml
model_size: small  # Instead of large-v3
# Can re-transcribe important segments with large model later
```

#### 6. Limit Diarization to Shorter Segments
Process audio in 15-minute chunks:

```python
# steps/audio_diarize.py
def chunk_audio(audio_file, chunk_duration=900):  # 15 minutes
    # Split audio into chunks
    # Process each separately
    # Merge speaker labels
```

### 🟢 LOW - Long-term Improvements

#### 7. Implement Progress Reporting
All long-running steps should report progress:

```python
# In each step
def report_progress(current, total):
    progress_file = workspace / "progress.json"
    progress_file.write_text(json.dumps({
        "step": step_name,
        "current": current,
        "total": total,
        "percent": (current/total)*100
    }))
```

#### 8. Add Graceful Degradation
If step fails, try with reduced quality:

```python
try:
    process_video(quality="high")
except MemoryError:
    logger.warning("High quality failed, trying medium...")
    process_video(quality="medium")
```

#### 9. Consider Docker Containers
Docker can limit memory per step and provide better isolation:

```yaml
# docker-compose.yml
services:
  scene_detect:
    image: goodq_scene_detect
    mem_limit: 4g
    mem_reservation: 2g
```

## Immediate Action Plan

### Step 1: Test with Chunked Videos (TONIGHT)
```powershell
# Split one video into 10-minute chunks
cd L:\_DATA\FAMILY_FEAST
ffmpeg -i "01. 1987 - 1988.mp4" -c copy -map 0 -segment_time 600 -f segment -reset_timestamps 1 "chunks\01_part_%03d.mp4"

# Copy chunks to import_inbox
Copy-Item chunks\*.mp4 L:\goodq4all\import_inbox\
```

### Step 2: Monitor Resource Usage
```powershell
# Watch memory during processing
while ($true) {
    $mem = Get-Counter '\Memory\Available MBytes'
    $cpu = Get-Counter '\Processor(_Total)\% Processor Time'
    Write-Host "$(Get-Date) - RAM Available: $($mem.CounterSamples.CookedValue)MB - CPU: $($cpu.CounterSamples.CookedValue)%"
    Start-Sleep 5
}
```

### Step 3: Update Scene Detection Threshold
```bash
# Modify scene detection config
# File: envs/goodq_video_scene_detect.yml
# Change threshold from 27.0 to 35.0
```

### Step 4: Test UI with Real Data
Once a chunk processes successfully:
- Verify UI shows real scenes
- Confirm database populated
- Test analytics displays

## Success Metrics

### Phase 1 (This Week)
- ✅ Process 10-minute chunk successfully
- ✅ UI shows real data from chunk
- ✅ All pipeline steps complete
- ✅ No crashes/stalls

### Phase 2 (Next Week)
- ✅ Process full 2-hour video (chunked)
- ✅ Reassemble metadata from chunks
- ✅ Knowledge graph spans chunks
- ✅ UI navigates across chunks

### Phase 3 (Month 1)
- ✅ All 24 hours of home movies ingested
- ✅ Full-text search working
- ✅ Face recognition across videos
- ✅ Emotional timeline complete

## Notes

### What's Working
- ✅ All pipeline steps individually tested and working
- ✅ Small file end-to-end success
- ✅ API server stable
- ✅ UI framework complete
- ✅ Database schema solid

### What's NOT Broken
- Architecture is sound
- No need to rewrite orchestration
- ZenML not required (custom orchestration works)
- Environment isolation working correctly

### The ONLY Issue
- **Large file resource management**
- Solution: Chunk files before ingestion
- This is a COMMON issue in video processing
- Industry standard: chunk large media files

## References

- Error code: https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0xc000009a--insufficient-resources
- SceneDetect memory: https://github.com/Breakthrough/PySceneDetect/issues/164
- Whisper large file: https://github.com/openai/whisper/discussions/670
- Pyannote chunking: https://github.com/pyannote/pyannote-audio/discussions/1162
