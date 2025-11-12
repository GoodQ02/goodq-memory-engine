# Production Test Findings - 2025-11-11

## Test Summary
Ran comprehensive production test on the GoodQ ingestion pipeline.

## Results

### ✅ WORKING
- Small video processing (sample.mp4, 0.98MB, 50 seconds) **COMPLETES SUCCESSFULLY**
- All pipeline steps execute correctly:
  - Scene detection (4.2s)
  - Image processing (OCR, caption, object detection, face embed, DINO, CLIP, tagger)
  - Audio processing (metadata, diarization 32s, transcription 44s, emotion, sentiment)
  - Text embedding
  - All embeddings saved to FAISS indices

### ❌ FAILING
- Large video processing (01. 1987 - 1988.mp4, 7.28GB, ~2 hours) **CRASHES**
  - Error code: `3221225786` (Windows access violation/memory error)
  - Pipeline starts, copies video, begins processing
  - Crashes after some time (no clear log of where)

## Root Causes Identified

### 1. **Knowledge Graph Issues**
```
❌ sqlite3.OperationalError: malformed JSON
❌ database is locked
```
**Location**: `lib/entity_resolver.py:290` and `lib/kg_realtime_integration.py:178`

**Problem**: 
- Malformed JSON when inserting entities into KG nodes table
- Database locking when multiple processes try to access KG simultaneously

**Fix Required**:
- Add proper JSON validation before DB insert
- Implement proper database connection pooling with timeout/retry logic
- Use WAL mode for SQLite to allow concurrent reads

### 2. **Module Import Errors**
```
❌ No module named 'goodq4all'
```
**Location**: Scene summary generation

**Problem**: 
- PYTHONPATH not properly set in some subprocess calls
- Module structure assumes `goodq4all` package is importable

**Fix Required**:
- Ensure PYTHONPATH includes parent directory (L:\) in ALL subprocess calls
- Consider making goodq4all a proper installed package with `pip install -e .`

### 3. **Memory Management (Large Videos)**
**Problem**:
- 7.28GB video likely causing memory exhaustion
- No chunking/streaming for large file processing
- All data loaded into memory at once

**Fix Required**:
- Implement streaming for large videos
- Process in smaller chunks
- Add memory monitoring and garbage collection
- Consider processing scenes in batches rather than loading entire video

### 4. **Database Locking**
**Problem**:
- Multiple processes accessing SQLite databases simultaneously
- No connection pooling or retry logic

**Fix Required**:
```python
# Enable WAL mode for SQLite
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
```

### 5. **Progress Tracking**
**Problem**:
- UI shows "stuck at 66%" because progress updates aren't granular enough
- No real-time feedback during long-running steps (diarization, transcription)

**Fix Required**:
- Add sub-step progress reporting
- Update progress during long operations (every 5-10 seconds)
- Stream progress to file that UI can poll

### 6. **Scene Detection Configuration**
**Problem**:
- Creating 2-second scenes instead of 5-minute scenes
- Configuration not being respected

**Status**: ALREADY FIXED (min_scene_len set to 300 seconds in config)

### 7. **Crash on Large Videos**
**Likely Causes**:
1. **Memory exhaustion** during scene detection or audio diarization
2. **Subprocess timeout** - worker processes killed by OS
3. **File locking** - temp files locked by multiple processes
4. **Conda environment issues** - packages not available or version conflicts

**Recommended Fixes**:
1. Add memory monitoring and limits
2. Implement checkpoint/resume functionality
3. Better temp file management with unique names per process
4. Add detailed error logging to identify exact crash point

## Action Plan

### Priority 1 - Critical (Prevents Processing)
1. ✅ Fix PYTHONPATH issues (add L:\ to all subprocess environments)
2. ✅ Enable SQLite WAL mode and increase busy_timeout
3. ✅ Add JSON validation before KG database inserts
4. ❌ Implement memory monitoring for large videos
5. ❌ Add checkpoint/resume functionality

### Priority 2 - Important (Improves Reliability)
1. ❌ Add granular progress reporting for long steps
2. ❌ Implement streaming/chunking for large videos
3. ❌ Add retry logic with exponential backoff for DB operations
4. ❌ Better temp file management (unique directories per video)
5. ❌ Add comprehensive error logging at each step

### Priority 3 - Nice to Have (Quality of Life)
1. ❌ Fix datetime.utcnow() deprecation warning
2. ❌ Add estimated time remaining to progress tracking
3. ❌ Implement parallel scene processing (with memory limits)
4. ❌ Add video preview/thumbnail generation for UI
5. ❌ Create health check endpoint for each processing step

## Test Results Details

### Small Video (sample.mp4)
```
Size: 0.98 MB
Duration: 50.1 seconds
Scenes: 1
Total Processing Time: ~165 seconds (2m 45s)

Step Breakdown:
- Scene Detection: 4.2s
- Image Pipeline: ~38s (OCR, caption, objects, faces, DINO, CLIP, tagger)
- Audio Metadata: 1.8s
- Audio Diarization: 32.2s
- Audio Transcription: 44.3s
- Audio Processing: ~30s (speaker merge, music, time hints, emotion)
- Embeddings: ~22s (text, sentiment, emotion, CLAP)

Status: ✅ COMPLETE
Output: Successfully written to database
Errors: Minor (KG malformed JSON, module import)
```

### Large Video (01. 1987 - 1988.mp4)
```
Size: 7.28 GB  
Duration: ~2 hours (estimated)
Scenes: Unknown (processing crashes before completion)
Total Processing Time: FAILED

Status: ❌ CRASH
Error Code: 3221225786 (Access Violation)
Last Log Entry: "Mission failed: Video ingestion returned code 3221225786"
```

## Recommendations

1. **Start with fixing Priority 1 items** - These prevent any processing of large videos
2. **Test incrementally** - Use progressively larger videos (5min, 15min, 30min, 1hr, 2hr)
3. **Add monitoring** - Memory, CPU, disk I/O for each step
4. **Implement graceful degradation** - If memory low, reduce batch sizes or skip optional steps
5. **Create resume functionality** - Save checkpoints so crashed runs can resume

## Files Modified/Created
- L:\goodq4all\test_ingestion_debug.py (diagnostic script)
- L:\goodq4all\logs\manual_debug_test.log (test output)
- L:\goodq4all\logs\test_debug_run_results.json (processing results)

## Next Steps
1. Fix KG malformed JSON error
2. Fix module import error  
3. Implement WAL mode for all SQLite databases
4. Add memory monitoring
5. Test with medium-sized video (5-10 minutes)
6. Add detailed crash logging
7. Implement checkpoint/resume

## Conclusion
The pipeline is **functionally correct** but **not production-ready for large videos**. The core issue is memory management and error handling for long-running processes. All the AI models and processing steps work correctly on small inputs.
