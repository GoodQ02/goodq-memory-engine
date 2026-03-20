# Phase 5 Video Scene Detection - Activation Report
> ⚠ Historical planning document — contains legacy path references.

**Date:** December 5, 2025  
**Status:** READY FOR ACTIVATION  
**Mission:** Integrate lightweight GPU-accelerated video scene detection with audio segmentation pipeline

---

## I. ARCHITECTURE ANALYSIS ✅

### Current System State

**Windows GPU Core Environment (`goodq_core`):**
- Torch 2.5.1+cu121
- CUDA 12.1
- Handles: Image OCR, Captioning, Object Detection, Face Embeddings, CLIP/DINO, Text, Sentiment, Emotion

**WSL2 GPU Audio Environment (`~/goodq_audio/venv`):**
- CUDA 12.1 on Linux
- Handles: Faster-Whisper, VAD, Pyannote, CLAP, Audio Emotion
- **UNTOUCHED in this activation**

**Legacy Scene Detect Environment (`goodq_video_scene_detect`):**
- Torch 2.7.1+cu118 (CUDA 11.8)
- **CUDA MISMATCH** with main pipeline
- **Will be bypassed by Phase 5**

### Phase 5 Implementation Discovered

**Location:** `<project_root>\steps\audio\segmentation\phase5_video_scene_integration.py`

**Key Functions:**
1. `detect_scenes_for_chunk()` - GPU-accelerated per-chunk scene detection
2. `align_scenes_with_audio_segments()` - Harmonizes video/audio boundaries
3. `process_video_chunks_with_scenes()` - **Main entry point**
4. `upgrade_analysis_for_legacy_scene_detect()` - Migration guidance

**Strategy:**
- Processes video in audio-aligned chunks (not full video at once)
- Uses OpenCV + PyTorch on GPU for frame difference detection
- Aligns scene boundaries with audio segment boundaries
- Runs on `goodq_core` (CUDA 12.1) - **No CUDA conflicts**

---

## II. INTEGRATION POINTS IDENTIFIED ✅

### Pipeline Entry Point
**File:** `<project_root>\pipelines\ingest_multimodal_conda.py`  
**Function:** `process_items_step()`  
**Current Video Handling:** None detected - video path exists but no active processing

**Insertion Point:** After `mod == "image"` block, before universal steps

### Step Runner Registration
**File:** `<project_root>\cli\step_runner.py`  
**Current Steps:** 30+ steps registered (audio_transcribe, image_ocr, sentiment, etc.)  
**Required:** Add `video_scene_segmentation` step mapping

### Configuration Files
**Main Config:** `<project_root>\config.yaml` (user/model settings)  
**Segmentation Config:** `<project_root>\configs\segmentation_config.json` (Phase 0-4 settings)  
**Phase Config:** `<project_root>\configs\phased_segmentation.yaml` (All phases, including Phase 5)

**Phase 5 Config Already Present:**
```yaml
phase5:
  scene_threshold: 30.0
  min_scene_len_sec: 2.0
  use_gpu: true
  batch_size: 32
  alignment_tolerance: 0.5
```

---

## III. REQUIRED MODIFICATIONS

### A. Step Runner Registration ✅

**File:** `<project_root>\cli\step_runner.py`  
**Action:** Add video scene segmentation step after line 161 (before `raise SystemExit`)

```python
if step_name == "video_scene_segmentation":
    from goodq4all.steps.audio.segmentation.phase5_video_scene_integration import process_video_chunks_with_scenes
    assert item is not None
    # Extract required inputs from item
    video_path = item.get('path') or item.get('file_path')
    audio_segments = item.get('audio_segments', [])
    output_dir = item.get('output_dir', cfg.get('processing_dir', '<GOODQ_DATA_ROOT>/GoodQ_Data/processing'))
    
    # Call Phase 5 processor
    return process_video_chunks_with_scenes(video_path, audio_segments, output_dir, cfg)
```

### B. Pipeline Integration ✅

**File:** `<project_root>\pipelines\ingest_multimodal_conda.py`  
**Action:** Add video processing block in `process_items_step()` after line 71 (after image block)

```python
if mod == "video":
    # Phase 5: Video scene detection aligned with audio segmentation
    scene_result = run_conda_step("goodq_core", "video_scene_segmentation", enriched, cfg)
    enriched.update(scene_result)
```

### C. Configuration Enhancement ✅

**File:** `<project_root>\configs\segmentation_config.json`  
**Action:** Add Phase 5 section to segmentation config

```json
"phase5": {
  "enabled": true,
  "scene_threshold": 30.0,
  "min_scene_len_sec": 2.0,
  "use_gpu": true,
  "alignment_tolerance": 0.5,
  "comment": "GPU-accelerated chunk-level scene detection on goodq_core (CUDA 12.1)"
}
```

---

## IV. OUTPUT SPECIFICATIONS

### Scene Manifest
**Location:** `<GOODQ_DATA_ROOT>/GoodQ_Data/processing/<video_id>/video_scenes.json`

```json
{
  "total_scenes": 42,
  "scenes": [
    {
      "start": 0.0,
      "end": 8.43,
      "duration": 8.43,
      "confidence": 1.0,
      "strategy": "gpu_chunk_detect"
    }
  ],
  "aligned_segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 12.5,
      "vad_speech": true,
      "video_scenes": [...],
      "scene_count": 2,
      "scene_aligned": true
    }
  ]
}
```

### Temporal Index (Future Phase 6)
**Location:** `<GOODQ_DATA_ROOT>/GoodQ_Data/processing/<video_id>/temporal_index.json`  
**Status:** Prepared in Phase 5, full integration in Phase 6

---

## V. RISK ANALYSIS

### ✅ LOW RISK FACTORS
- **No CUDA conflicts:** Phase 5 uses `goodq_core` (CUDA 12.1), not legacy env
- **No WSL2 changes:** Audio pipeline completely untouched
- **Modular design:** Phase 5 is isolated, can be disabled without breaking pipeline
- **Fallback handling:** Returns full-chunk fallback if OpenCV/PyTorch unavailable

### ⚠️ MEDIUM RISK FACTORS
- **GPU memory:** Scene detection adds GPU load during video processing
  - *Mitigation:* Chunk-level processing prevents full-video memory spikes
- **Processing time:** Per-chunk scene detection adds latency
  - *Mitigation:* GPU acceleration + reasonable chunk sizes (20-40s)

### 🟡 MONITORING POINTS
- GPU utilization during concurrent image + video processing
- Scene detection accuracy on different video types
- Alignment quality between audio/video boundaries

---

## VI. VALIDATION PLAN

### Syntax Validation
```powershell
python -m py_compile <project_root>\cli\step_runner.py
python -m py_compile <project_root>\pipelines\ingest_multimodal_conda.py
python -m py_compile <project_root>\steps\audio\segmentation\phase5_video_scene_integration.py
```

### Runtime Validation
1. **Import Test:** Verify Phase 5 module loads without errors
2. **Config Test:** Confirm Phase 5 settings accessible from config
3. **Step Test:** Run isolated video_scene_segmentation step
4. **Pipeline Test:** Run full multimodal ingestion with video sample

### Success Criteria
- ✅ All syntax checks pass
- ✅ Phase 5 module imports successfully
- ✅ Scene manifest JSON generated with valid structure
- ✅ Aligned segments contain video scene references
- ✅ No CUDA errors or GPU context conflicts
- ✅ Processing completes without hanging

---

## VII. ROLLBACK STRATEGY

### If Issues Occur:
1. **Comment out** video processing block in `ingest_multimodal_conda.py`
2. **Comment out** step registration in `step_runner.py`
3. **Set** `phase5.enabled: false` in `segmentation_config.json`
4. **Revert** to commit before activation

### Rollback Commands:
```powershell
git diff HEAD~1 <project_root>\cli\step_runner.py
git diff HEAD~1 <project_root>\pipelines\ingest_multimodal_conda.py
git checkout HEAD~1 -- <file>  # if needed
```

---

## VIII. ACTIVATION SEQUENCE

### Pre-Flight Checklist
- [x] Phase 5 implementation exists and is complete
- [x] Configuration files contain Phase 5 settings
- [x] Integration points identified in pipeline and step runner
- [x] Risk analysis completed
- [x] Validation plan established
- [x] Rollback strategy documented

### Execution Steps
1. **Update Step Runner** - Register `video_scene_segmentation` step
2. **Update Pipeline** - Add video processing block with `goodq_core` env
3. **Update Config** - Ensure Phase 5 enabled in segmentation config
4. **Syntax Check** - Validate all modified Python files
5. **Commit** - Atomic commit with all changes
6. **Test** - Run validation sequence
7. **Push** - Deploy to GitHub

### Expected Outcome
- Video ingestion includes GPU-accelerated scene detection
- Scene boundaries aligned with audio segments
- Unified temporal index foundation established
- No CUDA conflicts or pipeline disruptions
- System ready for Phase 6 (full harmonization)

---

## IX. NEXT PHASE PREVIEW

### Phase 6: Full Temporal Index Harmonization
- Merge all timelines: frames, scenes, audio chunks, transcripts, speakers
- Create canonical `temporal_index.json` with frame-level precision
- Enable cross-modal queries (e.g., "find scenes where speaker changes coincide with scene cuts")
- Support downstream analysis (summarization, clip extraction, scene understanding)

**Phase 6 Prerequisites (Now Met):**
- ✅ Audio segmentation (Phases 0-4)
- ✅ Video scene detection (Phase 5)
- ✅ Modular pipeline architecture
- ✅ CUDA-unified environment

---

## X. CONCLUSION

**Phase 5 is READY FOR ACTIVATION.**

All components are in place:
- Complete implementation in `phase5_video_scene_integration.py`
- Configuration settings in `phased_segmentation.yaml`
- Clear integration points in pipeline and step runner
- Low-risk deployment with established rollback plan

**Recommended Action:** Proceed with activation sequence.

**Confidence Level:** HIGH

**Estimated Activation Time:** 15-30 minutes

---

*Report Generated: 2025-12-05*  
*Agent: GitHub Copilot CLI (Codex)*  
*Project: GoodQ4All Multimodal Ingestion Pipeline*
<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-03-20 -->
<!-- ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS -->
