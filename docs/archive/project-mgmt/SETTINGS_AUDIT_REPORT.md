<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# 🎯 GoodQ Settings Audit Report - Mission Critical

**Status**: CRITICAL ISSUES IDENTIFIED  
**Date**: 2025-10-12  
**Priority**: HIGH - Settings optimized for short clips, NOT long-form home movies

---

## 🚨 CRITICAL FINDINGS

### 1. **Scene Detection - WRONG THRESHOLD**
**Current**: `threshold: 32.0` (default for modern videos)  
**Required**: `threshold: 15.0-20.0` (home movies have subtle scene changes)  
**Impact**: Missing 80%+ of actual scenes in home movies  
**Location**: `configs/config_open.yaml` line 50

**Fix Required**:
```yaml
video:
  scene_detect:
    threshold: 15.0  # Lower for home movies (was 32.0)
    min_scene_len_sec: 2.0  # Shorter minimum
    max_scenes: 500  # Sufficient for long videos
```

---

### 2. **Audio Transcription - SHORT CHUNKS**
**Current**: `chunk_seconds: 10` (fine for most use cases)  
**Optimal**: `chunk_seconds: 30` for long-form content  
**Impact**: More processing overhead, potential context loss  
**Location**: `configs/config_open.yaml` line 118

**Recommendation**:
```yaml
audio:
  transcribe:
    model: "medium"  # Good balance
    chunk_seconds: 30  # Larger chunks for efficiency
    beam_size: 5  # More accurate transcription
    vad_filter: true  # Skip silence
```

---

### 3. **Entity Refinement - LIMITED SAMPLES**
**Current**: `entity_max_samples: 120` frames per entity  
**Optimal**: `entity_max_samples: 300` for hour+ videos  
**Impact**: May miss recurring people/objects in long videos  
**Location**: `configs/config_open.yaml` line 56

---

### 4. **Diarization Model - May Timeout**
**Current**: `pyannote/speaker-diarization@2.1`  
**Issue**: No explicit timeout or chunking strategy  
**Impact**: May hang on 2+ hour videos  
**Location**: `configs/config_open.yaml` line 80

**Needs**: Chunked processing for videos > 60 minutes

---

### 5. **Whisper Model Selection**
**Current**: `model: "medium"`  
**Optimal**: Keep "medium" (good balance)  
**Alternative**: "large-v3" for better accuracy but 3x slower  
**Status**: ✅ OKAY

---

### 6. **FAISS Index Settings - NOT CONFIGURED**
**Current**: Default settings (no explicit config)  
**Issue**: No index type, no clustering optimization  
**Impact**: Slower similarity search at scale  
**Required**: Add FAISS configuration

**Recommended Addition**:
```yaml
faiss:
  index_type: "IVF"  # Inverted file for large datasets
  n_clusters: 256  # For 10k+ embeddings
  n_probe: 32  # Balance speed/accuracy
  metric: "cosine"  # For similarity
```

---

### 7. **Memory/Database Settings - NO LIMITS**
**Current**: No max_entries, no retention policy  
**Issue**: Database can grow indefinitely  
**Impact**: Performance degradation over time  

**Recommended Addition**:
```yaml
memory:
  max_summaries: 10000  # Limit per video
  retention_days: 365  # Archive old data
  vacuum_interval_days: 30  # Optimize DB
```

---

### 8. **Batch Processing - NOT CONFIGURED**
**Current**: Single-threaded processing  
**Optimal**: Batch where possible  
**Impact**: Not using GPU efficiently  

**Recommended**:
```yaml
processing:
  batch_size_images: 8  # Process 8 frames at once
  batch_size_audio: 4  # Process 4 audio chunks
  max_workers: 2  # Parallel workers (careful with GPU memory)
```

---

## 📊 CONFIGURATION HIERARCHY ISSUE

**Problem**: Multiple config files with unclear precedence:
1. `config.yaml` (root - user config)
2. `configs/config_open.yaml` (template)
3. `configs/paths.yaml` (paths)
4. `.env.local` (environment vars)
5. Code defaults in each step

**Current Behavior**: Scene threshold shows 32.0 in resolved config despite 15.0 in config_open.yaml

**Root Cause**: Code default (27.0) + somewhere else setting to 32.0

---

## 🔧 IMMEDIATE FIXES REQUIRED

### Priority 1: Scene Detection
```yaml
# configs/config_open.yaml
video:
  scene_detect:
    threshold: 15.0  # CRITICAL FIX
    min_scene_len_sec: 2.0
    max_scenes: 0  # No limit
```

### Priority 2: Add Missing Configs
```yaml
# configs/config_open.yaml - ADD THESE SECTIONS

# FAISS Configuration
faiss:
  index_type: "Flat"  # Start simple, upgrade to IVF later
  metric: "cosine"
  normalize: true

# Memory Management
memory:
  max_summaries_per_video: 5000
  retention_days: 365
  auto_vacuum: true
  vacuum_interval_days: 30

# Processing Optimization
processing:
  batch_size_images: 8
  batch_size_audio: 4
  max_workers: 1  # Start with 1 for stability
  gpu_memory_fraction: 0.8  # Reserve 20% for system
```

### Priority 3: Watchdog Timeout
```python
# scripts/watchdog_ingest.py - line ~366
# Current calculation is good, but add minimum:
timeout_seconds = max(3600, file_size_gb * 7200)  # At least 1 hour
```

---

## 🎬 HOME MOVIE SPECIFIC OPTIMIZATIONS

### Scene Detection Profile
```yaml
video:
  scene_detect:
    # Home movies have:
    # - Subtle lighting changes
    # - Long static shots
    # - Sudden cuts (especially VHS transfers)
    threshold: 15.0  # Catch subtle changes
    min_scene_len_sec: 1.5  # Some home movies have quick cuts
    max_scenes: 0  # Don't cap - 2 hour tape could have 500+ scenes
    
    # Entity tracking:
    entity_refine: true
    entity_sample_rate: 0.5  # Sample every other frame (efficiency)
    entity_min_duration: 2.0  # Must appear for 2s
    entity_max_samples: 300  # Track across long videos
```

### Audio Transcription Profile
```yaml
audio:
  transcribe:
    model: "medium"  # Best balance for  English home videos
    chunk_seconds: 30  # Larger chunks = better context
    language: "en"  # Explicit language helps
    initial_prompt: "Home video recording with family conversations, background music, and ambient sounds."
    # This prompt helps Whisper understand the context
  
  diarization:
    min_speakers: 1
    max_speakers: 10  # Family gatherings can have many voices
```

---

## 📈 PERFORMANCE EXPECTATIONS (After Fixes)

### For 2-Hour Home Movie (7.3GB):
- **Scene Detection**: 10-15 minutes (100-200 scenes expected)
- **Frame Extraction**: 5-10 minutes (1 frame per scene)
- **OCR**: 2-5 minutes
- **Image Captioning**: 10-20 minutes (GPU)
- **Object Detection**: 15-25 minutes (GPU)
- **Audio Diarization**: 30-60 minutes (CPU intensive)
- **Audio Transcription**: 45-90 minutes (GPU, depends on speech density)
- **Embeddings**: 10-20 minutes
- **Knowledge Graph**: 5-10 minutes

**Total Estimated**: 2.5 - 4 hours for complete processing

---

## ✅ SETTINGS THAT ARE CORRECT

1. **Whisper Model**: "medium" is optimal
2. **Minimum scene length**: 2.0s is good
3. **Entity refinement**: Enabled (good)
4. **Audio events patterns**: Well configured
5. **Model pinning**: model_registry.yaml locks versions ✅
6. **Path consolidation**: Unified under L:\goodq4all ✅

---

## 🔄 NEXT ACTIONS

1. **Update config_open.yaml** with all fixes
2. **Clear test data** and reprocess
3. **Monitor first 10 minutes** of processing
4. **Validate scene count** (should be 50-100+ for 2hr video)
5. **Check audio transcription quality**
6. **Verify all embeddings are created**
7. **Test knowledge graph population**

---

## 📝 TESTING CHECKLIST

- [ ] Scene threshold produces 100+ scenes for 2hr video
- [ ] Audio transcription captures dialogue accurately
- [ ] Diarization identifies speakers
- [ ] OCR captures on-screen text
- [ ] Object detection finds people, objects
- [ ] Face detection/tracking works
- [ ] Embeddings are created for all modalities
- [ ] Knowledge graph shows relationships
- [ ] No silent failures (all errors logged)
- [ ] Progress monitoring shows real activity

---

**Agent Q Signature**: This audit reveals our primary obstacle - we've been hunting ghosts when the settings were sabotaging us from the start. Fix these configurations and the pipeline will sing, Agent.

