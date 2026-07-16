<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/reference/WSL_AUDIO_RUNTIME.md -->
<!-- DOC_ARCHIVED_ON: 2026-07-10 -->

# Audio Diarization Optimization Plan

> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS

## Current State Analysis

### Bottlenecks Identified
1. **PyAnnote Pipeline** - Runs on entire audio file in one shot
2. **No Chunking** - Long files take exponentially longer
3. **Single-threaded** - No parallelization
4. **No Caching** - Reprocesses same speakers every time
5. **GPU Memory** - Not efficiently managed for long audio

### Current Performance
- **Sample video** (~30 min): Unknown (need to test)
- **Full home movie** (~2-3 hours): Stalls/hangs

## Optimization Strategy

### Phase 1: Intelligent Chunking ✅ IMPLEMENT FIRST
**Goal**: Break audio into manageable chunks before diarization

**Changes**:
1. Split audio into 5-10 minute chunks
2. Process each chunk independently
3. Merge speaker labels across chunks using speaker embeddings
4. Cache speaker embeddings for reuse

**Expected Improvement**: 3-5x faster for long files

### Phase 2: GPU Memory Management
**Goal**: Prevent OOM errors and optimize VRAM usage

**Changes**:
1. Set explicit CUDA memory limits
2. Clear GPU cache between chunks
3. Use mixed precision (FP16) when possible
4. Implement batch processing with memory monitoring

**Expected Improvement**: Handle 3+ hour files without hanging

### Phase 3: Speaker Embedding Cache
**Goal**: Reuse speaker profiles across videos

**Changes**:
1. Extract and save speaker embeddings
2. Build speaker library over time
3. Match new speakers against known profiles
4. Enable "family member detection" across videos

**Expected Improvement**: Faster processing + better speaker consistency

### Phase 4: VAD Pre-filtering (Optional)
**Goal**: Skip silence before diarization

**Changes**:
1. Run Voice Activity Detection first
2. Only process segments with speech
3. Maintain timeline mapping

**Expected Improvement**: 2x faster on videos with lots of silence

### Phase 5: Concurrent Processing (Future)
**Goal**: Process multiple chunks in parallel

**Changes**:
1. Implement worker pool for chunks
2. Maintain GPU isolation per worker
3. Smart scheduling to prevent resource conflicts

**Expected Improvement**: 2-4x faster with proper GPU management

## Implementation Priority

1. **Phase 1** - CRITICAL - Prevents hangs
2. **Phase 2** - HIGH - Ensures stability
3. **Phase 3** - MEDIUM - Nice to have, adds value
4. **Phase 4** - LOW - Good optimization
5. **Phase 5** - FUTURE - Complex, needs careful design

## Success Metrics

- ✅ Process 2-hour video without hanging
- ✅ Complete diarization in < 10% of video duration
- ✅ Accurate speaker labels (verified by user)
- ✅ Consistent speaker IDs across multiple videos
- ✅ GPU memory stays under 80% usage

## Testing Plan

1. Test with 30-min sample first
2. Scale to 1-hour video
3. Test full 2-3 hour home movie
4. Monitor GPU usage and timing
5. Validate speaker accuracy

---

**Status**: Ready to implement Phase 1
**Next Action**: Create chunked diarization implementation
