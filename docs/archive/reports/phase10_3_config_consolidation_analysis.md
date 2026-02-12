<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# PHASE 10.3 — CONFIG CONSOLIDATION ANALYSIS (Step 1 of 2)

**Generated:** 2025-12-07  
**Status:** ANALYSIS ONLY — NO FILES MODIFIED  
**Purpose:** Design canonical configuration schema for GoodQ4All

---

## A. CONFIG FILES DISCOVERED

### Primary Config Files (configs/)
| File | Size | Last Modified | Status |
|------|------|---------------|--------|
| `config.yaml` | 9,971 bytes | 2025-12-06 | ✅ **CANONICAL** (current master) |
| `gpu_config.yaml` | 1,526 bytes | 2025-11-11 | ⚠️ REDUNDANT - merge into config.yaml |
| `paths.yaml` | 1,927 bytes | 2025-11-19 | ⚠️ REDUNDANT - already in config.yaml |
| `phase4_audio.yaml` | 1,549 bytes | 2025-12-03 | ⚠️ REDUNDANT - subset in config.yaml |
| `phased_segmentation.yaml` | 3,483 bytes | 2025-12-03 | ⚠️ REDUNDANT - fully in config.yaml |
| `segmentation_config.json` | 1,564 bytes | 2025-12-05 | ⚠️ REDUNDANT - JSON version of YAML |
| `model_registry.yaml` | 4,904 bytes | 2025-11-23 | 🔧 KEEP - model definitions |
| `models_config.yaml` | 1,231 bytes | 2025-11-22 | ⚠️ REDUNDANT - partial overlap |
| `entities.yaml` | 177 bytes | 2025-09-10 | ❓ UNCLEAR - minimal content |

### Other Config Files Found
| File | Location | Status |
|------|----------|--------|
| `config.json` | L:\goodq4all\ | ❌ ROOT LEVEL - should not exist |
| `config.yaml` | L:\goodq4all\ | ❌ ROOT LEVEL - duplicate of configs/config.yaml |
| `config_wsl2_audio.json` | wsl2_audio/ | ✅ KEEP - WSL2 bridge config |
| `config.json` | wsl2_audio/ | ⚠️ DUPLICATE - merge with above |

### Resolved Config Snapshots (logs/)
- Multiple `_resolved_config.json` files in various log directories
- These are runtime snapshots - **DO NOT MODIFY**, but useful for validation

---

## B. CONFIG KEYS EXTRACTED

### Master config.yaml Structure
```yaml
user:              # User identity & personality
model:             # AI agent identity
paths:             # All filesystem paths
llm:               # LLM endpoint config
tts:               # Text-to-speech settings
home_assistant:    # Home automation integration
system:            # Hardware specs
gpu:               # GPU configuration
envs:              # Conda environment mapping
qdrant:            # Vector database settings
segmentation:      # Phases 0-5 configuration
  phase0:          # Audio normalization
  phase1:          # VAD segmentation
  phase2:          # Pyannote
  phase3:          # Chunking
  phase4:          # Audio processing
  phase5:          # Scene detection
video:             # Video-specific settings
  scene_detect:    # Scene detection params
phase6:            # Visual embeddings & fusion
api:               # FastAPI server config
ui:                # UI serving config
pipeline:          # General pipeline settings
output:            # Output artifact settings
logging:           # Logging configuration
```

### gpu_config.yaml (REDUNDANT)
```yaml
gpu:
  device_id: 0
  deterministic: false
  exclusive_mode: false

step_memory_fractions:  # Per-step GPU memory
  video_scene_detect: 0.6
  audio_transcribe: 0.4
  # ... 15+ more entries

memory:
  clear_cache_before_step: true
  clear_cache_after_step: true
  log_memory_stats: true

monitoring:
  enable_profiling: false
  log_interval_seconds: 0
```

**Action:** Merge `step_memory_fractions` into `config.yaml` under `gpu.step_memory:`

### paths.yaml (FULLY REDUNDANT)
All paths already exist in `config.yaml` under `paths:` section.

**Action:** Archive this file.

### phase4_audio.yaml (REDUNDANT)
All keys already in `config.yaml` under `segmentation.phase4:`.

**Action:** Archive this file.

### phased_segmentation.yaml (REDUNDANT)
All phased settings already in `config.yaml` under `segmentation:`.

**Action:** Archive this file.

### segmentation_config.json (REDUNDANT)
JSON duplicate of YAML configs.

**Action:** Archive this file.

---

## C. CONFIG DEPENDENCY MAP

### Modules Using Config

| Module | Config Keys Used |
|--------|------------------|
| `cli/run_ingestion.py` | `cfg['run']`, `cfg['force_reprocess']` |
| `pipelines/goodq_chat.py` | `cfg['context']` |
| `steps/audio/segmentation/phase2_pyannote.py` | `cfg['device']`, `cfg['model']` |
| `steps/video_scene_detect/step.py` | `cfg['config']['video']` ⚠️ **DOUBLE NESTING** |
| `steps/video_summarizer/step.py` | `cfg['paths']['db_path']` |
| `scripts/*` | Various path and param access |
| `test_phase6.py` | `cfg['data_root']` |

### Critical Finding: Double-Nested Config Access
Some modules use `cfg['config']['video']` while others use `cfg['video']`.

**Root Cause:** Legacy config loader used to wrap everything in `cfg['config']`.  
**Current State:** `config.yaml` is top-level, so `cfg['video']` is correct.

**Action Required:** Remove double-nesting in:
- `steps/video_scene_detect/step.py` (line 25)
- Any other modules using `cfg['config']['...']`

---

## D. CONFLICT REPORT

### 1. **Duplicate Keys Across Files**

| Key | Defined In | Conflict |
|-----|------------|----------|
| `paths.*` | config.yaml, paths.yaml | ✅ Identical |
| `segmentation.phase*` | config.yaml, phased_segmentation.yaml | ✅ Identical |
| `segmentation.phase4.*` | config.yaml, phase4_audio.yaml | ✅ Identical |
| `gpu.device_id` | config.yaml ❌ MISSING, gpu_config.yaml ✅ | ⚠️ **MISSING IN MASTER** |
| `step_memory_fractions` | gpu_config.yaml ONLY | ⚠️ **NOT IN MASTER** |

### 2. **Keys Defined But Never Used**

```yaml
user.nickname          # Personality, not consumed by code
user.music_style       # Documentation only
model.zone_*           # UI concept, not implemented
system.cpu/ram/ssd     # Documentation, not runtime
home_assistant.*       # Integration not active
```

**Action:** Keep these as documentation/metadata. Harmless.

### 3. **Keys Used But Missing Definitions**

| Key | Used In | Missing From |
|-----|---------|--------------|
| `cfg['run']` | cli/run_ingestion.py | config.yaml (runtime-injected) |
| `cfg['force_reprocess']` | cli/run_ingestion.py | config.yaml (runtime-injected) |
| `cfg['context']` | goodq_chat.py | config.yaml (runtime-injected) |
| `cfg['data_root']` | test_phase6.py | config.yaml ⚠️ **SHOULD BE paths.data_root** |

**Action:** Document that `run`, `force_reprocess`, `context` are runtime-only.

### 4. **Conflicting Defaults**

| Key | Config 1 | Config 2 | Resolution |
|-----|----------|----------|------------|
| `scene_threshold` | config.yaml: 30.0 | phased_segmentation.yaml: 30.0 | ✅ Match |
| `max_chunk_duration` | config.yaml: 40.0 | phased_segmentation.yaml: 40.0 | ✅ Match |

**No actual conflicts found** — redundant files are perfectly aligned.

### 5. **Deprecated Keys (ZenML Cleanup)**

These keys are NO LONGER USED after Phase 9.4 ZenML removal:
```yaml
zenml.*           # Fully removed
pipeline.zenml_*  # Fully removed
```

**Action:** Already removed. ✅

---

## E. PROPOSED CANONICAL CONFIG SCHEMA

### Unified config.yaml (Enhanced)

```yaml
# ============================================================================
# GoodQ4All Master Configuration
# Unified configuration for all phases of the multimodal ingestion pipeline
# Last updated: 2025-12-07 (Phase 10.3 Consolidation)
# ============================================================================

# USER & MODEL IDENTITY
user:
  name: Joseph Domingo Benvenuti
  nickname: GoodSex, Joes, Agent, 00-Joes, Joe
  # ... (keep existing user metadata)

model:
  identity: 'GoodQ: Digital embodiment of Q from James Bond'
  # ... (keep existing model metadata)

# ============================================================================
# PATHS
# ============================================================================
paths:
  # Core directories (repo-internal)
  log_dir: L:/goodq4all/logs
  output_directory: L:/goodq4all/output
  db_dir: L:/goodq4all/data
  db_path: L:/goodq4all/data/memory.db
  knowledge_graph_db: L:/goodq4all/data/knowledge_graph.db
  faiss_dir: L:/goodq4all/data/faiss
  config_dir: L:/goodq4all/configs
  
  # Data paths (L:/_DATA sandbox)
  data_root: L:/_DATA/GoodQ_Data
  import_inbox: L:/_DATA/GoodQ_Data/import_inbox
  processing: L:/_DATA/GoodQ_Data/processing
  models_cache: L:/_DATA/models
  
  # Segmentation subdirectories
  chunk_subdir: chunks
  audio_subdir: audio
  video_subdir: video
  metadata_subdir: metadata
  
  # External tools (L:/_TOOLS)
  tesseract_path: L:/_TOOLS/tesseract
  ffmpeg_path: L:/_TOOLS/ffmpeg/bin
  poppler_path: L:/_TOOLS/poppler/bin
  
  # FAISS indices
  faiss_index_path: L:/goodq4all/data/faiss_indices/text/faiss_text.index
  faiss_audio_path: L:/goodq4all/data/faiss_indices/audio/faiss_audio.index
  faiss_dino_path: L:/goodq4all/data/faiss_indices/dino/faiss_dino.index
  faiss_clip_path: L:/goodq4all/data/faiss_indices/clip/faiss_clip.index
  
  # ID mapping databases
  clap_id_map_db: L:/goodq4all/data/databases/clap_id_map.sqlite
  clip_id_map_db: L:/goodq4all/data/databases/clip_id_map.sqlite
  dino_id_map_db: L:/goodq4all/data/databases/dino_id_map.sqlite
  known_faces_db_path: L:/goodq4all/data/databases/known_faces.json
  chroma_dir: L:/goodq4all/data/databases/chroma

# ============================================================================
# LLM & TTS
# ============================================================================
llm:
  api_url: http://localhost:1234/v1/chat/completions
  model_id: LM_STUDIO_GOODQ

tts:
  elevenlabs_voice_id: 4YYIPFl9wE5c4L2eu2Gb
  piper_voice: joe
  last_used_voice: moviephone

# ============================================================================
# HOME ASSISTANT
# ============================================================================
home_assistant:
  url: http://192.168.0.154:8123
  token: <REDACTED>

# ============================================================================
# SYSTEM HARDWARE
# ============================================================================
system:
  cpu: Intel Core i7-14700KF
  gpu: NVIDIA GeForce RTX 4070 Ti SUPER with 16GB GDDR6X
  ram1: 32GB Crucial DDR5 at 5200MHz
  ram2: 32GB Crucial DDR5 at 5200MHz
  # ... (keep hardware metadata)

# ============================================================================
# GPU CONFIGURATION (CONSOLIDATED)
# ============================================================================
gpu:
  enabled: true
  cuda_version: "12.1"
  torch_version: "2.5.1+cu121"
  primary_env: goodq_core
  memory_fraction: 0.85
  allow_growth: true
  
  # Device settings (from gpu_config.yaml)
  device_id: 0
  deterministic: false
  exclusive_mode: false
  
  # Per-step memory allocation (from gpu_config.yaml)
  step_memory:
    video_scene_detect: 0.6
    audio_transcribe: 0.4
    audio_diarize: 0.75
    audio_emotion: 0.4
    audio_embed_clap: 0.5
    image_caption: 0.6
    image_ocr: 0.4
    image_embed_dino: 0.7
    image_embed_clip: 0.7
    object_detect: 0.6
    face_embed: 0.6
    text_embed: 0.4
    emotion_classify: 0.4
    sentiment: 0.3
    default: 0.5
  
  # Memory management (from gpu_config.yaml)
  memory:
    clear_cache_before_step: true
    clear_cache_after_step: true
    log_memory_stats: true
  
  # Performance monitoring (from gpu_config.yaml)
  monitoring:
    enable_profiling: false
    log_interval_seconds: 0

# ============================================================================
# ENVIRONMENT ROUTING
# ============================================================================
envs:
  core: goodq_core
  audio_transcribe: goodq_audio_transcribe
  audio_embed: goodq_audio_embed
  audio_emotion: goodq_audio_emotion
  audio_metadata: goodq_audio_metadata
  video_scene_detect: goodq_video_scene_detect  # legacy

# ============================================================================
# QDRANT VECTOR DATABASE
# ============================================================================
qdrant:
  host: http://localhost:6333
  collections:
    clip: goodq_clip
    dino: goodq_dino
    text: goodq_text
    audio: goodq_audio
  embedding_dims:
    clip: 512
    dino: 768
    text: 384
    audio: 512

# ============================================================================
# PHASED SEGMENTATION ENGINE (Phases 0-5)
# ============================================================================
segmentation:
  enabled: true
  mode: phased
  
  phase0:
    target_sample_rate: 16000
    channels: 1
    bit_depth: 16
    codec: pcm_s16le
  
  phase1:
    aggressiveness: 3
    frame_duration_ms: 30
    min_speech_duration: 0.3
    min_silence_duration: 0.5
    padding_duration: 0.1
  
  phase2:
    enabled: false
    min_duration_off: 0.0
    min_duration_on: 0.0
    model: pyannote/segmentation
    device: cuda
    use_auth_token: null
  
  phase3:
    min_chunk_duration: 1.0
    max_chunk_duration: 40.0
    target_chunk_duration: 20.0
    chunk_padding_ms: 250
    chunk_overlap_ms: 500
    merge_threshold: 2.0
  
  phase4:
    enable_transcription: true
    enable_diarization: true
    enable_embeddings: true
    enable_emotion: true
    enable_music_detection: true
    whisper_model: medium
    language: null
    beam_size: 5
    best_of: 5
    temperature: 0.0
    min_speakers: null
    max_speakers: null
    diarize_timeout: 7200
    chunk_timeout: 600
    max_parallel_chunks: 2
    clap_model: laion/clap-htsat-fused
    emotion_model: ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition
  
  phase5:
    enabled: true
    scene_threshold: 30.0
    min_scene_len_sec: 2.0
    use_gpu: true
    batch_size: 32
    alignment_tolerance: 0.5

# ============================================================================
# VIDEO PROCESSING
# ============================================================================
video:
  scene_detect:
    threshold: 30.0
    min_scene_len_sec: 300.0
    max_scenes: 0
    entity_refine: false
    entity_sample_rate: 0.5
    entity_min_duration: 300.0
    entity_max_samples: 300

# ============================================================================
# PHASE 6: SCENE VISUAL EMBEDDINGS & CROSS-MODAL FUSION
# ============================================================================
phase6:
  enabled: true
  frame_sampling_strategy: uniform
  frames_per_scene: 3
  max_gpu_batch_size: 8
  clip_collection: goodq_clip
  dino_collection: goodq_dino
  retrieval:
    enable: true
    fusion_weights:
      text: 0.5
      visual: 0.4
      audio: 0.1

# ============================================================================
# API CONFIGURATION
# ============================================================================
api:
  enabled: true
  host: 127.0.0.1
  port: 8000
  reload: true
  cors_enabled: false
  max_upload_size: 5368709120  # 5GB

# ============================================================================
# UI CONFIGURATION
# ============================================================================
ui:
  enabled: true
  serve_from: L:/goodq4all/ui
  theme: dark

# ============================================================================
# PIPELINE SETTINGS
# ============================================================================
pipeline:
  parallel_processing: false
  max_workers: 4
  save_intermediate: true
  cleanup_temp_files: false
  retry_on_failure: true
  max_retries: 3

# ============================================================================
# OUTPUT SETTINGS
# ============================================================================
output:
  save_chunks: true
  save_manifests: true
  save_embeddings: true
  compression: false

# ============================================================================
# LOGGING
# ============================================================================
logging:
  level: INFO
  save_logs: true
  verbose: true
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

## F. PROPOSED VALIDATION LAYER

### Recommendation: **Pydantic v2** (Best Option)

**Reasons:**
1. Already installed (used by FastAPI)
2. Type-safe with IDE autocomplete
3. Runtime validation
4. Clear error messages
5. JSON Schema export capability
6. Nested model support

**Alternative Considered:** dataclass + typeguard (simpler but less validation)

**Implementation Plan:**
```python
# goodq4all/config/schema.py
from pydantic import BaseModel, Field
from typing import Optional, Dict

class PathsConfig(BaseModel):
    log_dir: str
    data_root: str
    import_inbox: str
    processing: str
    # ...

class GPUConfig(BaseModel):
    enabled: bool = True
    cuda_version: str
    device_id: int = 0
    step_memory: Dict[str, float]
    # ...

class Phase6Config(BaseModel):
    enabled: bool = True
    frame_sampling_strategy: str = "uniform"
    frames_per_scene: int = 3
    # ...

class GoodQConfig(BaseModel):
    paths: PathsConfig
    gpu: GPUConfig
    phase6: Phase6Config
    # ...
```

Then modify `config_loader.py`:
```python
def load_configs(overrides: Dict[str, Any] | None = None) -> GoodQConfig:
    raw_cfg = _read_yaml(unified_config_path)
    if overrides:
        raw_cfg.update(overrides)
    return GoodQConfig(**raw_cfg)  # Validates on construction
```

---

## G. REQUIRED MODULE PATCHES

### Modules Requiring Changes

| File | Line | Current | Required Change |
|------|------|---------|-----------------|
| `steps/video_scene_detect/step.py` | 25 | `cfg['config']['video']` | `cfg['video']` |
| `test_phase6.py` | 21 | `cfg['data_root']` | `cfg['paths']['data_root']` |

### Search Pattern for Double-Nesting
```bash
grep -r "cfg\['config'\]" --include="*.py"
```

**Expected:** Only 1-2 legacy references remain.

---

## H. PROPOSED FILES TO ARCHIVE

Move to `archive/deprecated_2025_12_07/configs/`:

1. ✅ `gpu_config.yaml` (merged into config.yaml)
2. ✅ `paths.yaml` (fully redundant)
3. ✅ `phase4_audio.yaml` (fully redundant)
4. ✅ `phased_segmentation.yaml` (fully redundant)
5. ✅ `segmentation_config.json` (JSON duplicate)
6. ✅ `models_config.yaml` (merge into model_registry.yaml)
7. ⚠️ `config_open.yaml` (if still exists - legacy fallback)
8. ✅ Root-level `config.json` (duplicate)
9. ✅ Root-level `config.yaml` (duplicate)

**Keep:**
- ✅ `config.yaml` (canonical master)
- ✅ `model_registry.yaml` (model definitions)
- ✅ `entities.yaml` (if used by any module)
- ✅ `wsl2_audio/config*.json` (WSL2 bridge)

---

## I. QUESTIONS NEEDING USER APPROVAL

### 1. **Pydantic Validation Layer**
**Question:** Implement Pydantic schema validation for type safety?  
**Impact:** Better error messages, autocomplete, but adds strictness.  
**Recommendation:** ✅ **YES** — low risk, high benefit.

### 2. **Archive vs Delete**
**Question:** Archive redundant configs or delete permanently?  
**Impact:** Archiving allows rollback; deletion is cleaner.  
**Recommendation:** ✅ **ARCHIVE** (industry standard).

### 3. **GPU Step Memory Fractions**
**Question:** Keep per-step GPU memory tuning or use defaults?  
**Impact:** Fine-grained control vs simplicity.  
**Recommendation:** ✅ **KEEP** — already tuned values are valuable.

### 4. **Config Loader Backward Compatibility**
**Question:** Support legacy `cfg['config']['...']` access temporarily?  
**Impact:** Smooth transition vs clean break.  
**Recommendation:** ⚠️ **CLEAN BREAK** — only 1-2 files affected.

### 5. **WSL2 Audio Config**
**Question:** Merge `config_wsl2_audio.json` + `config.json` into one?  
**Impact:** Simpler structure but may affect WSL2 bridge.  
**Recommendation:** ✅ **YES** — merge into single `wsl2_bridge_config.json`.

---

## J. SUMMARY & NEXT STEPS

### Current State
- ✅ **9 config files** found in `configs/`
- ✅ **6 are redundant** (gpu_config, paths, phase4, phased_seg, seg_config, models_config)
- ✅ **1 is canonical** (config.yaml)
- ✅ **1 is essential** (model_registry.yaml)
- ✅ **1 is minimal** (entities.yaml)

### Conflicts Detected
- ✅ **Zero actual conflicts** — all redundant files match canonical
- ⚠️ **Minor issue:** gpu_config.yaml has fields missing from config.yaml
- ⚠️ **Legacy nesting:** 1-2 modules use `cfg['config']['...']`

### Readiness for Step 2 (Execution)
**Status:** ✅ **READY TO PROCEED**

**Upon Approval, Phase 10.3 Step 2 will:**
1. Merge gpu_config.yaml into config.yaml
2. Archive 6 redundant config files
3. Implement Pydantic validation (optional)
4. Fix double-nesting in video_scene_detect/step.py
5. Update config_loader.py documentation
6. Create migration guide
7. Run full validation tests
8. Commit changes

---

**END OF ANALYSIS REPORT**

**Awaiting User Approval to Proceed to Phase 10.3 Step 2 (Execution)**
