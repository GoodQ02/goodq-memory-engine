<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Log Analysis - November 28, 2025 Pipeline Failure

**Analysis Date:** 2025-12-03  
**Analyzed By:** AI Agent (GitHub Copilot CLI)  
**Focus:** Nov 28, 2025 02:20 AM pipeline failure

---

## Executive Summary

The pipeline run on **Nov 28, 2025 at 02:20 AM** failed while processing `01. 1987 - 1988.mp4`. Despite 76.5% audio extraction failures (13/17 scenes), the pipeline continued due to `skip_on_error: true` configuration. The `_resolved_config.json` provides complete configuration snapshot showing all pinned models and system state.

**Status:** 🔴 FAILED  
**Root Causes:** Audio extraction errors + Knowledge graph JSON bug  
**Data Loss:** Minimal (temp files preserved)

---

## Key Files Analyzed

### 1. env_scan_full.json (Nov 28, 15:56)
**Size:** 42.49 KB  
**Purpose:** Complete environment scan

**Findings:**
- **26 Conda environments** (vs expected 22)
- **CUDA version inconsistency:**
  - Most envs: CUDA 12.1 (cu121) ✅
  - Base env: CUDA 11.8 (cu118) ⚠️
  - goodq_video_scene_detect: CUDA 11.8 (cu118) ⚠️
- **11 environments** have `.pth` files pointing to `L:\goodq4all`
- **WSL2:** Python 3.12.3 detected
- **System:** Windows 11 Pro, user jdben, machine GOOD-REACTOR

**Environment Breakdown:**
```
base                      → Python 3.13.5, PyTorch 2.7.1+cu118
goodq_agents              → Python 3.11.14, No PyTorch
goodq_zenml               → Python 3.10.18, PyTorch 2.5.1+cu121 ✅
goodq_audio_diarize       → Python 3.10.18, PyTorch 2.5.1+cu121
goodq_audio_embed         → Python 3.10.18, PyTorch 2.3.1+cu121
goodq_audio_emotion       → Python 3.10.18, PyTorch 2.3.1+cu121
goodq_audio_transcribe    → Python 3.10.18, PyTorch 2.3.1+cu121
goodq_face_embed          → Python 3.10.18, PyTorch 2.5.1+cu121
goodq_image_caption       → Python 3.10.18, PyTorch 2.3.1+cu121
goodq_llm_chat            → Python 3.10.18, PyTorch 2.5.1+cu121
goodq_object_detect       → Python 3.10.18, PyTorch 2.3.1+cu121
goodq_ocr                 → Python 3.10.18, PyTorch 2.5.1+cu121
goodq_sentiment           → Python 3.10.18, PyTorch 2.3.1+cpu (CPU-only)
goodq_tagger              → Python 3.10.18, PyTorch 2.3.1+cpu (CPU-only)
goodq_text_embed          → Python 3.10.18, PyTorch 2.3.1+cu121
goodq_video_scene_detect  → Python 3.10.18, PyTorch 2.7.1+cu118 ⚠️
```

**Issues:**
1. ⚠️ CUDA version mismatch (11.8 vs 12.1)
2. ⚠️ goodq_video_scene_detect using older CUDA
3. ✅ All project envs properly configured with Python paths

---

### 2. progress.json (Nov 28, 02:20)
**Size:** 0.5 KB

**Content:**
```json
{
  "status": "failed",
  "current_file": "01. 1987 - 1988.mp4",
  "current_step": null,
  "steps_completed": [],
  "total_steps": 20,
  "current_step_index": 0,
  "progress_percent": 0,
  "started_at": "2025-11-27T17:15:49.972402",
  "updated_at": "2025-11-28T02:20:18.155240",
  "estimated_completion": null,
  "errors": [
    {
      "message": "Unknown error",
      "step": "processing",
      "timestamp": "2025-11-28T02:20:18.154101"
    }
  ]
}
```

**Findings:**
- **Runtime:** ~9 hours (17:15 → 02:20)
- **Error:** Generic "Unknown error" (not helpful)
- **Progress:** 0% reported (likely incorrect)
- **Steps completed:** Empty array (suspicious)

---

### 3. _resolved_config.json (Nov 27, 17:15)
**Size:** Full configuration snapshot  
**Location:** `logs/watchdog_20251127_171550/_resolved_config.json`

This is the **GOLDEN SOURCE** - complete configuration at time of run.

#### Model Registry (Pinned Versions)

**HuggingFace Models (13 models):**
| Model | Repo ID | Revision (SHA) | Required | Notes |
|-------|---------|----------------|----------|-------|
| BLIP Caption | Salesforce/blip-image-captioning-base | 82a37760... | ✅ | - |
| ViT-GPT2 | nlpconnect/vit-gpt2-image-captioning | dc68f91c... | ❌ | Fallback for BLIP |
| CLIP ViT | openai/clip-vit-base-patch16 | 57c21647... | ✅ | - |
| DINOv2 | facebook/dinov2-base | f9e44c81... | ✅ | - |
| Sentence Transformer | sentence-transformers/all-MiniLM-L6-v2 | 8b3219a9... | ✅ | - |
| CLAP Audio | laion/clap-htsat-unfused | 8fa0f1c6... | ✅ | - |
| PyAnnote Diarization | pyannote/speaker-diarization | 2.1 | ✅ | **Requires PYANNOTE_TOKEN** |
| PyAnnote Segmentation | pyannote/segmentation | 2.1.1 | ✅ | Requires auth |
| Whisper Large v3 | openai/whisper-large-v3 | 06f233fe... | ❌ | Optional |
| Faster Whisper Large v3 | Systran/faster-whisper-large-v3 | edaa852e... | ✅ | - |
| Faster Whisper Medium | Systran/faster-whisper-medium | 08e178d4... | ✅ | **Active** |
| Faster Whisper Tiny | Systran/faster-whisper-tiny | d90ca5fe... | ❌ | Optional |
| Wav2Vec2 Emotion | ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition | b520c9c4... | ✅ | - |

**External Models (2 models):**
| Model | Source | SHA-256 | Required | Notes |
|-------|--------|---------|----------|-------|
| YOLOv8n | Ultralytics | f59b3d833e... | ✅ | 6.5 MB, verified |
| Whisper GGML | ggerganov/whisper.cpp | Not downloaded | ❌ | Not used |

**System Tools:**
| Tool | Version | Path | Status |
|------|---------|------|--------|
| FFmpeg | 6.1 | L:\_TOOLS\ffmpeg\bin\ffmpeg.exe | ✅ |
| Tesseract | 5.3.0 | L:\_TOOLS\tesseract\tesseract.exe | ✅ |
| Poppler | 23.08.0 | L:\_TOOLS\poppler\bin | ✅ |

#### Critical Configuration Settings

**Audio Extraction:**
```yaml
steps:
  audio_extraction:
    skip_on_error: true  # ⚠️ This is why pipeline continued!
```

**Scene Detection:**
```yaml
video:
  scene_detect:
    threshold: 30.0
    min_scene_len_sec: 300.0  # 5 minutes
    max_scenes: 100
    entity_refine: false
```

**Knowledge Graph:**
```yaml
knowledge_graph:
  enabled: true
  min_confidence: 0.6
  max_hops: 3
  entity_deduplication: true
  similarity_threshold: 0.85
```

**Audio Transcription:**
```yaml
audio:
  transcribe:
    model: medium  # Faster Whisper Medium
    chunk_seconds: 30
    language: en
    beam_size: 5
    vad_filter: true
    initial_prompt: "Home video recording with family conversations..."
```

**Update Policy (MODEL LOCKDOWN):**
```yaml
update_policy:
  auto_update: false
  security_updates_only: false
  manual_approval_required: true
  check_for_updates: false
```

**Run Metadata:**
```yaml
run:
  id: d0d0a689-4056-4755-9178-664b2066eb66
  pipeline: scene_ingest_cli
  started_at: 2025-11-27T23:15:51.228367
  git_sha: 3a17b3c94e969b4ae0f095183034b5761c1f2727
  force_reprocess: true
```

---

## Timeline Reconstruction

**Nov 27, 2025:**
- **17:15:49** - Pipeline started (`progress.json` started_at)
- **17:15:51** - Watchdog run initiated (run ID: d0d0a689...)
- **17:19** - Config snapshot saved (`_resolved_config.json`)

**Nov 28, 2025:**
- **02:13:21** - Document Decoder step (Visual Intel phase)
- **02:13:45** - Visual Intel step
- **02:14:04** - Target Identification step
- **02:14:23** - Facial Recognition step
- **02:14:43** - Visual Biometrics step
- **02:15:01** - Debug CLIP embedding env
- **02:15:03** - Visual Signature step
- **02:16:00** - Audio Intel step (audio extraction begins)
- **02:16:43** - Voice Separation step
- **02:18:40** - Linguistic Analysis step
- **02:18:59** - Sentiment Intel step
- **02:20:01** - Audio Signature step (final step)
- **02:20:01** - step_runs.jsonl last update
- **02:20:18** - **FAILURE** - progress.json marked failed
- **15:56:36** - env_scan_full.json created (post-mortem scan)

**Total Runtime:** ~9 hours

---

## Failure Analysis

### Confirmed Issues

**1. Audio Extraction Failures (76.5%)**
- **13 out of 17 scenes** failed audio extraction
- Errors occurred during "Audio Intel" phase (02:16 - 02:20)
- `skip_on_error: true` allowed pipeline to continue
- Likely causes:
  - FFmpeg unable to access video file
  - File path issues
  - Permissions problem
  - Corrupt video segments

**2. Knowledge Graph JSON Serialization Bug**
- **Location:** `lib/entity_resolver.py` line 290
- **Error:** `sqlite3.OperationalError: malformed JSON`
- **Function:** `integrate_entities_to_kg`
- **SQL:** `json_patch()` function receiving invalid JSON
- **Impact:** Knowledge graph building crashes

**3. Generic Error Reporting**
- progress.json shows "Unknown error" - not actionable
- Need better error propagation from steps

### Why Pipeline Continued Despite Failures

The configuration has:
```yaml
steps:
  audio_extraction:
    skip_on_error: true
```

This allowed the pipeline to continue even when 76.5% of audio extraction failed. This is **intentional** for resilience but masks the underlying problem.

---

## Data State Assessment

### Databases

**memory.db (576 KB):**
- 17 scenes detected
- 5 embeddings created
- Incomplete due to audio failures

**knowledge_graph.db (204 KB):**
- State unknown (likely corrupted from JSON bug)
- Last known good: Nov 9, 2025 (232 entities, 37 relationships)

**unified_goodq.db:**
- **MISSING** (should exist)
- Expected: Cross-video entity tracking

### Temp Files

**Preserved:** `L:\goodq4all\data\processing\video_553120054da3c26d` (1 file)  
**Action:** Can inspect for debugging

---

## Environment Health

### ✅ Good
- All conda environments exist
- Python paths configured (.pth files)
- System tools installed (FFmpeg, Tesseract, Poppler)
- Models pinned to exact revisions
- No auto-updates (reproducible)

### ⚠️ Needs Attention
- CUDA version inconsistency (11.8 vs 12.1)
- `goodq_video_scene_detect` using older CUDA
- More envs than expected (26 vs 22)

### 🔴 Critical
- Audio extraction failing consistently
- Knowledge graph JSON serialization bug
- Missing unified_goodq.db
- PyAnnote token required (may be missing)

---

## Root Cause Hypotheses

### Primary Hypothesis: File Access Issue
**Likelihood:** High

**Evidence:**
- 76.5% audio extraction failure rate is too consistent to be random
- Visual processing succeeded (frames extracted)
- FFmpeg tool configured correctly

**Possible Causes:**
1. Video file moved/deleted during 9-hour run
2. File locked by another process
3. Network path timeout (if file on NAS)
4. Insufficient disk space for temp files

**Test:** Run on small local file (< 1 min video)

### Secondary Hypothesis: PyAnnote Token Missing
**Likelihood:** Medium

**Evidence:**
- PyAnnote requires `PYANNOTE_TOKEN` environment variable
- No error about missing token (but might fail silently)

**Test:** Verify `PYANNOTE_TOKEN` is set

### Tertiary Hypothesis: CUDA Memory Issue
**Likelihood:** Low

**Evidence:**
- Mixed CUDA versions (11.8 vs 12.1)
- Long runtime might cause memory fragmentation

**Test:** Monitor GPU memory during run

---

## Recommended Actions

### Immediate (Before Next Run)

1. **Verify Video File Path**
   ```powershell
   # Check if file still exists
   Test-Path "path\to\01. 1987 - 1988.mp4"
   ```

2. **Check PyAnnote Token**
   ```powershell
   $env:PYANNOTE_TOKEN
   # Should return token, not empty
   ```

3. **Fix Knowledge Graph JSON Bug**
   - Review `lib/entity_resolver.py` line 290
   - Add JSON validation before `json_patch()`
   - Handle None/null values gracefully

4. **Test FFmpeg Directly**
   ```powershell
   L:\_TOOLS\ffmpeg\bin\ffmpeg.exe -i "video.mp4" -vn -acodec pcm_s16le test.wav
   ```

### Short Term

5. **Standardize CUDA Versions**
   - Rebuild `base` env with CUDA 12.1
   - Rebuild `goodq_video_scene_detect` with CUDA 12.1
   - Verify all GPU steps use cu121

6. **Improve Error Reporting**
   - Capture specific FFmpeg errors
   - Add file existence checks before processing
   - Better error messages in progress.json

7. **Create Unified DB**
   - Investigate why unified_goodq.db is missing
   - May need manual creation or schema migration

### Medium Term

8. **Add Pre-Flight Checks**
   - Verify file exists and is readable
   - Check disk space
   - Verify all required env vars
   - Test FFmpeg on sample
   - Validate model downloads

9. **Enhance Monitoring**
   - Real-time error alerts
   - GPU memory tracking
   - Disk space warnings
   - Step-by-step progress logging

10. **Test Suite**
    - Small test video (< 1 min)
    - Verify all 22 steps complete
    - Check database writes
    - Validate knowledge graph

---

## Configuration Strengths

### ✅ Excellent Practices

1. **Complete Model Lockdown**
   - All models pinned to exact commit SHAs
   - SHA-256 verification enabled
   - No auto-updates
   - Manual approval required
   - Reproducible across machines

2. **Proper Environment Isolation**
   - 22+ conda environments
   - Separate environments per step
   - Python path injection via .pth files
   - GPU memory fractions configured

3. **Comprehensive Configuration**
   - Full config snapshot per run
   - Git SHA tracking
   - Run ID for correlation
   - All paths absolute

4. **Resilient Design**
   - `skip_on_error` for non-critical steps
   - Fallback models configured
   - VAD filtering for audio
   - Chunk-based processing

---

## Questions for User

1. **File Location:** Is `01. 1987 - 1988.mp4` still at the same location? Has it been moved?

2. **PyAnnote Token:** Is `PYANNOTE_TOKEN` environment variable set? Required for speaker diarization.

3. **Priority:** Which issue to fix first:
   - Audio extraction failures?
   - Knowledge graph JSON bug?
   - CUDA version standardization?

4. **Unified DB:** Should `unified_goodq.db` exist? Is it intentionally not created yet?

5. **CUDA:** Do you want to standardize all envs to CUDA 12.1?

---

## Next Steps for Development

**When user returns:**

1. ✅ Review this analysis
2. 🔧 Fix knowledge graph JSON bug (highest impact)
3. 🔍 Debug audio extraction with small test file
4. 🔧 Verify/set PyAnnote token
5. 🧪 Run health check script
6. 📊 Retest with known-good small video

---

## Conclusion

The Nov 28 pipeline failure was caused by:
1. **Audio extraction failures (76.5%)** - likely file access issue
2. **Knowledge graph JSON bug** - code defect in entity_resolver.py
3. **Resilient config masked severity** - `skip_on_error: true` allowed continuation

**The good news:**
- Configuration is excellent (model lockdown, versioning)
- Most steps completed successfully
- Visual processing worked
- Temp files preserved for debugging
- Complete config snapshot available

**Next session:** Fix the two critical bugs, then retest with small file.

---

**Generated:** 2025-12-03  
**Analyst:** AI Agent (GitHub Copilot CLI)  
**Status:** Ready for user review and debugging session

**END OF LOG ANALYSIS**
