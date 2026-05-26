<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Phase 2: Audio Diarization Optimization

## Date: 2025-11-11
## Status: 🚀 IN PROGRESS

---

## Objective
Optimize audio diarization to reduce processing time from hours to minutes for long home videos (60+ minutes).

---

## Current Performance Baseline

### Current Configuration
- **Chunk Size**: 10 minutes
- **GPU Memory**: 50% allocation
- **Device**: RTX 4070 Ti SUPER (17GB)
- **Model**: pyannote/speaker-diarization@2.1
- **Processing Speed**: ~1-2x realtime (slow for 60min videos)

### Performance Issues
1. ❌ **Sequential chunking** - Processes one chunk at a time
2. ❌ **GPU underutilization** - Only 50% memory allocated
3. ❌ **No batching** - Each chunk processed individually
4. ❌ **Redundant I/O** - Extracts chunks to disk repeatedly
5. ❌ **No caching** - Reloads model for each file

---

## Optimization Strategies

### 🎯 Strategy 1: Increase GPU Memory Allocation ⚡ QUICK WIN
**Current**: 50% GPU memory  
**Proposed**: 70-80% GPU memory  
**Expected Impact**: 20-30% faster processing  
**Implementation Time**: 5 minutes

**Changes:**
```yaml
# config/gpu_config.yaml
step_memory_fractions:
  audio_diarize: 0.75  # Increase from 0.5 to 0.75
```

**Risk**: Low - RTX 4070 Ti has 17GB, plenty of headroom

---

### 🎯 Strategy 2: Optimize Chunk Size 🎯 MEDIUM IMPACT
**Current**: 10-minute chunks  
**Proposed**: Dynamic chunk sizing based on GPU memory  
**Expected Impact**: 15-25% faster  
**Implementation Time**: 30 minutes

**Logic**:
- Small files (<20 min): Process whole file
- Medium files (20-40 min): 20-minute chunks
- Large files (>40 min): 15-minute chunks

**Rationale**: Reduces overhead from chunk merging and temp file I/O

---

### 🎯 Strategy 3: Model Warmup & Caching 🔥 HIGH IMPACT
**Current**: Model loaded fresh for each file  
**Proposed**: Keep model in memory across files  
**Expected Impact**: 10-20s saved per file  
**Implementation Time**: 15 minutes

**Changes**:
- Use persistent pipeline cache (already implemented with `_PIPELINES` dict)
- Add warmup run on first load
- Clear cache only when switching devices

---

### 🎯 Strategy 4: Reduce Audio Resampling 🎯 MEDIUM IMPACT
**Current**: Extracts chunk to temp file at 16kHz mono  
**Proposed**: Pre-convert entire audio once, chunk in memory  
**Expected Impact**: 10-15% faster for long files  
**Implementation Time**: 45 minutes

**Approach**:
1. Convert entire audio to 16kHz mono WAV once
2. Load into memory array
3. Slice array for chunks (no FFmpeg calls)
4. Process chunks from memory

---

### 🎯 Strategy 5: Parallelize Chunks (Advanced) 🚀 HIGHEST IMPACT
**Current**: Sequential processing  
**Proposed**: Process 2-3 chunks concurrently  
**Expected Impact**: 2-3x faster  
**Implementation Time**: 2 hours  
**Risk**: High - Requires careful GPU memory management

**Approach**:
- Use Python multiprocessing
- Allocate GPU memory fraction per worker
- Process chunks in parallel
- Merge results at end

**Requirements**:
- Careful memory fraction calculation
- Process synchronization
- Error handling per worker

---

### 🎯 Strategy 6: Skip Silence Detection (Optional) ⚡ QUICK WIN
**Current**: Processes all audio  
**Proposed**: Detect silence, skip diarization for silent chunks  
**Expected Impact**: 5-20% faster (depends on silence amount)  
**Implementation Time**: 30 minutes

**Logic**:
- Run fast VAD (Voice Activity Detection)
- Only diarize chunks with speech
- Mark silent chunks as no-speaker

---

## Implementation Priority

### 🥇 **Phase 2.1: Quick Wins (30 minutes)**
1. ✅ Increase GPU memory to 75%
2. ✅ Optimize chunk size (dynamic)
3. ✅ Verify model caching working

**Expected**: 30-40% speedup

---

### 🥈 **Phase 2.2: Medium Optimizations (90 minutes)**
1. Pre-convert audio (avoid repeated FFmpeg calls)
2. Add warmup routine
3. Implement silence detection

**Expected**: Additional 20-30% speedup

---

### 🥉 **Phase 2.3: Advanced (Future)**
1. Parallel chunk processing
2. GPU streaming
3. Custom PyAnnote pipeline configuration

**Expected**: 2-3x total speedup

---

## Testing Plan

### Test Cases
1. **Short video** (5 min): Baseline, should process in <30s
2. **Medium video** (20 min): Test chunking optimization
3. **Long video** (60 min): Full optimization test
4. **Very long video** (2+ hours): Stress test

### Metrics to Track
- ⏱️ Processing time (seconds)
- � GPU memory usage (%)
- � GPU utilization (%)
- � Speaker detection accuracy
- ⚠️ Error rate

---

## Implementation Checklist

### Phase 2.1 (Now)
- [ ] Update gpu_config.yaml (memory: 0.5 → 0.75)
- [ ] Add dynamic chunk sizing
- [ ] Test with 60-minute home video
- [ ] Measure performance improvement
- [ ] Document results

### Phase 2.2 (Next)
- [ ] Implement pre-conversion strategy
- [ ] Add model warmup
- [ ] Add silence detection
- [ ] Re-test with home video
- [ ] Update UI with progress details

### Phase 2.3 (Future)
- [ ] Design parallel processing architecture
- [ ] Implement worker pool
- [ ] Test concurrent processing
- [ ] Benchmark vs sequential
- [ ] Deploy to production

---

## Expected Results

### Before Optimization
- 60-minute video: ~90-120 minutes processing time (1.5-2x realtime)

### After Phase 2.1
- 60-minute video: ~50-70 minutes (1.2-1.5x realtime)

### After Phase 2.2
- 60-minute video: ~30-40 minutes (0.5-0.7x realtime)

### After Phase 2.3
- 60-minute video: ~15-20 minutes (0.25-0.33x realtime)

---

## Risk Assessment

### Low Risk
✅ GPU memory increase (plenty of VRAM)  
✅ Chunk size optimization (tested)  
✅ Model caching (already implemented)

### Medium Risk
⚠️ Pre-conversion (disk space needed)  
⚠️ Silence detection (might affect accuracy)

### High Risk
❌ Parallel processing (complex, GPU memory conflicts)

---

## Next Steps

1. **Immediate**: Implement Phase 2.1 (GPU memory + chunk size)
2. **Test**: Run on real 60-minute home video
3. **Measure**: Document performance improvement
4. **Iterate**: Move to Phase 2.2 if needed
5. **Deploy**: Update production system

---

**Status**: Ready to begin Phase 2.1! 🚀
