# Production Test Findings - November 9, 2025

## Test Summary
**Status**: FAILED - Pipeline stalled at audio_diarize step  
**Duration**: 2+ hours before detection  
**File**: 01. 1987 - 1988.mp4 (7.28GB)

## Critical Issues Discovered

### 1. Multiple Watchdog Instances (CRITICAL)
**Problem**: Two watchdog processes started simultaneously, both trying to process the same file.

**Evidence**:
```
2025-11-09 23:02:09 - Watchdog 1 started
2025-11-09 23:02:20 - Watchdog 1 queued: 01. 1987 - 1988.mp4
2025-11-09 23:02:22 - Watchdog 2 queued: 01. 1987 - 1988.mp4
2025-11-09 23:02:26 - [ERROR] Failed to copy video to temp dir: [WinError 32] The process cannot access the file because it is being used by another process
```

**Root Cause**: No file locking mechanism to prevent multiple watchdog instances.

**Fix Applied**: 
- Added OS-level file lock (`.watchdog.lock`) in main()
- Uses psutil to detect stale locks from dead processes
- Prevents concurrent watchdog instances

---

### 2. Pipeline Stall at audio_diarize
**Problem**: Process stuck at audio_diarize step for 2+ hours with high CPU (1594s CPU time).

**Evidence**:
- PID 62368: Running audio_diarize since 23:33
- No progress, no output, no timeout
- Database remained empty (0 bytes)

**Likely Causes**:
1. Audio diarization model loading/processing issue
2. Large file size (7.28GB) overwhelming step
3. Missing progress logging to detect stall
4. No timeout on individual steps

**Status**: Requires deeper investigation of audio_diarize step

---

### 3. Lack of Progress Visibility
**Problem**: No way to see what step is doing or if it's stuck.

**Impact**:
- Ran for 2+ hours without knowing it was stalled
- UI showed "processing" but no actual progress
- No step-level timeout warnings

**Needed**:
- Progress logging from each step
- Step-level timeouts
- Better UI progress indicators

---

## Zombie Processes Found
At test end, found stuck processes from old run:
- PID 60560: watchdog (old)
- PID 42716: run_ingestion (old)
- PID 51296: api_server (running)
- PID 52168: watchdog (duplicate)
- PID 58860: audio_diarize (stuck)
- PID 62368: audio_diarize (stuck)
- PID 48000: audio_transcribe (zombie)
- PID 58656: audio_transcribe (zombie)

**All killed before restart.**

---

## Test Environment
- OS: Windows
- Python: Miniconda3 (goodq_zenml env)
- File: 01. 1987 - 1988.mp4 (7.28GB, ~2 hours runtime)
- Expected scenes: Long-form (5+ min each)
- Actual progress: 0 scenes completed

---

## Next Steps

### Immediate (DONE)
- [x] Add file lock to prevent multiple watchdogs
- [x] Kill all zombie processes
- [x] Clean processing directory

### High Priority (NEEDED)
- [ ] Fix audio_diarize stall issue
- [ ] Add progress logging to all steps
- [ ] Add step-level timeouts
- [ ] Test with smaller file first

### Medium Priority
- [ ] Add health checks to detect stalls
- [ ] Better process management
- [ ] Auto-recovery for stuck steps

---

## Conclusion
**NO, we did NOT get zero errors.** The test revealed:
1. Critical race condition (multiple watchdogs)
2. Pipeline stall at audio_diarize  
3. No progress visibility
4. Multiple zombie processes

The file lock fix addresses #1. Issues #2-4 remain to be solved.
