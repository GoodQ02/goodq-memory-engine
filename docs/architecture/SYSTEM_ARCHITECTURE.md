<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ System Architecture

**Last Updated:** March 19, 2026  
**Status:** Operational (verify per-run from artifacts and health checks)  
**Verification Date:** March 1, 2026 (witness run)

> **Note:** This document reflects the runtime architecture. Treat run artifacts and health checks as source-of-truth for current state.

---

## Current Status

This milestone snapshot is constrained to witness-run evidence (`run_id=51e42006-f64d-4b13-a42a-f180bf8ba7f3`) and does not expand profile guarantees beyond existing contracts.

Latest rerun comparison evidence is archived at `docs/archive/proof_of_concept/WITNESS_RUN_002.md` (`run_id=90e366c9-41be-4c37-84b6-52abbf4addb9`).

- Windows runtime remains canonical and deterministic for orchestrated ingestion.
- `BASELINE` remains Windows-safe and CPU-safe; WSL audio is selected only when the active profile or explicit overrides request it.
- Hybrid Windows + WSL architecture remains in force; WSL is an optional, profile-gated audio compute extension rather than a default runtime requirement.
- Knowledge graph is active for scene-linked media persistence.
- Vector parity is deterministic at run scope (`qdrant_ok=true`, `faiss_ok=not_attempted` for Phase 6 witness write).
- Read-only observability is active (structured JSON step events + heartbeat).
- Tagger native-crash mitigation is active; rare native faults remain possible and are surfaced in telemetry.

### Witness-Run Summary

| Field | Value |
| --- | --- |
| `video` | `09. 2002 - 2003.mp4` |
| `scenes_total` | `19` |
| `transcript_scenes` | `18` |
| `audio_backend_selected` | `windows (18/19 scenes; 1 missing)` |
| `wsl2_unified` | `true in this witness run (18/19 scenes; 1 missing), not a default BASELINE guarantee` |
| `phase6_complete` | `true` |
| `qdrant_points_clip` | `19` |
| `qdrant_points_dino` | `19` |
| `kg_media_nodes` | `19` |
| `retry_counts` | `step_error_events=1; retry_events_observed=0` |
| `total_duration_sec` | `1418.856` |

### Known Gaps

- Text/audio vector coverage is not assumed dense for every run; validate modality coverage from artifacts before making claims.
- `tagger` native faults are mitigated, not eliminated.
- Distributed/multi-node operation is out of scope for this milestone.

---

## Architectural Overview

GoodQ4All is a **local, GPU-accelerated multimodal AI pipeline** that processes video, audio, and images entirely on your machine. The supported default is Windows-first `BASELINE`; WSL2 is an optional audio compute extension used only when accelerated profiles or explicit overrides enable it.

**Key Runtime Facts:**
- Scene-first ingestion is active.
- Qdrant is the canonical vector store.
- FAISS is an optional secondary parity/fallback path where configured.
- Windows-local audio fallback remains the safe default contract.
- GPU/WSL acceleration is profile-gated and optional for correctness.

---

## Design Principles (Dec 14, 2025)

### 1. Scene-First Processing (Runtime-Validated)
- Video split into scenes FIRST (~30 scenes for 1hr video)
- Each scene processed independently (frame + audio + entities)
- Parallel-friendly architecture
- Verified: 30 scenes processed Dec 14, 2025

### 2. Unified Environment (Runtime-Validated)
- Single `goodq_core` conda environment (Python 3.10)
- All vision, text, and orchestration models
- Replaced 6 separate environments (30GB disk savings)
- GPU sharing: Windows (vision) + WSL2 (audio) = 85% util stable

### 3. Dual Audio Architecture (Runtime-Validated)
Current contract:
- `BASELINE` defaults to Windows-local audio processing.
- WSL audio is used only when the active profile or explicit overrides enable it and the workspace preflight succeeds.

**Queue-Based Service** (long-running daemon, when WSL audio is enabled):
- PID 177 (verified running Dec 14)
- Preloaded: Whisper medium, Pyannote 3.1, Silero VAD
- Watches: `wsl2_audio/queue_in/`

**Direct Invocation** (per-scene, when WSL audio is enabled):
- Runtime: `process_audio.py`
- On-demand loading with cleanup
- Output: result.json with transcript, diarization, emotion, embeddings

### 4. Observability (Runtime-Validated)
Comprehensive telemetry:
- Scene artifacts: `logs/scene_ingest/<video>/audio/` & `video/`
- Memory DB: `<GOODQ_DATA_ROOT>\GoodQ_Data\memory.db`
- Knowledge Graph: `<GOODQ_DATA_ROOT>\GoodQ_Data\knowledge_graph.db`
- Vector DB: Qdrant on port 6333

### 5. Privacy-First
- All processing local (no cloud)
- GPU: RTX 4070 Ti SUPER 16GB
- Data root: `<GOODQ_DATA_ROOT>\GoodQ_Data\`
- No external API calls except HuggingFace model downloads

---

## System Layers (Dec 14, 2025 Verified)

```
+-------------------------------------------------------------+
|                     User Interface Layer                     |
|  CLI - LAUNCH_GOODQ.bat - Command Window Monitoring         |
|  [Latent] FastAPI (api/server.py - scaffolded, not deployed)      |
|  [Latent] Web UI (ui/ - frontend exists, not deployed)            |
+--------------------------+----------------------------------+
                           |
+--------------------------+----------------------------------+
|                [OK] Orchestration Layer                        |
|  cli/run_ingestion.py - cli/watchdog.py - Scene-First      |
|  [Deprecated] (legacy orchestration removed - direct invocation now)                 |
+--------------------------+----------------------------------+
                           |
+--------------------------+----------------------------------+
|                [OK] Processing Layer                           |
|  +------------+  +------------+  +------------+            |
|  |   Video    |  |   Audio    |  |  Entity    |            |
|  | (Windows)  |  | (Windows default / WSL2 optional) |  | Extraction |            |
|  |  steps/    |  | wsl2_audio/|  |  steps/    |            |
|  +------------+  +------------+  +------------+            |
+--------------------------+----------------------------------+
                           |
+--------------------------+----------------------------------+
|                [OK] Memory Layer                               |
|  SQLite: memory.db - knowledge_graph.db                     |
|  Qdrant: canonical collections (port 6333)                 |
|  FAISS: optional secondary parity/fallback path            |
+--------------------------+----------------------------------+
                           |
+--------------------------+----------------------------------+
|                [OK] Storage Layer                              |
|  <GOODQ_DATA_ROOT>\GoodQ_Data\ (unified root)                        |
|  logs/scene_ingest/ (artifacts)                             |
|  \\wsl.localhost\Ubuntu\...\goodq_audio\ (WSL2)             |
+-------------------------------------------------------------+
```

**Legend:** Operational | Latent (built, not wired) | Deprecated

---

## Pipeline Architecture (Dec 14, 2025 - Golden Path)

### Entry Point
```
python -m cli.run_ingestion --input-dir <GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox
  |
  +--> cli/run_ingestion.py (1541 lines, scene-first architecture)
```

### High-Level Flow (Verified Dec 14, 2025)

```
Input Video (dropped in import_inbox)
    |
    +--> Scene Detection (goodq_video_scene_detect) 
    |   +--> 30 scenes detected (verified)
    |
    +--> Per-Scene Loop (for each of 30 scenes):
        |
        +--> [OK] Frame Processing (Windows, goodq_core env)
        |   +--> Extract keyframe -> logs/scene_ingest/<video>/video/scene_XXXX.jpg
        |   +--> OCR (Tesseract) -> 'ocr_text' field
        |   +--> Caption (BLIP2) -> 'caption' field
        |   +--> Object Detect (YOLOv8) -> 'objects' field
        |   +--> Face Embed (face_recognition)
        |   +--> CLIP Embed (openai/clip-vit-base) -> 512-dim
        |   +--> DINO Embed (facebook/dinov2-base) -> 768-dim
        |   +--> Tagger (image classification)
        |
        +--> [OK] Audio Processing (Windows fallback by default; WSL2 when enabled)
        |   +--> Extract audio chunk -> logs/scene_ingest/<video>/audio/scene_XXXX.wav
        |   +--> audio_metadata (mutagen/librosa)
        |   +--> audio_unified_wsl2() -> WSL2 process_audio.py (when the WSL contract is selected)
        |   |   +--> Transcribe (Whisper large-v3) -> 'transcript'
        |   |   +--> Diarize (Pyannote 3.1) -> 52 segments, 2 speakers (verified)
        |   |   +--> Emotion (Wav2Vec2) -> 8-class
        |   |   +--> Embed (768-dim vectors)
        |   +--> [Deprecated] audio_speaker_merge (legacy, still runs)
        |   +--> [Deprecated] audio_music_events (legacy, still runs)
        |   +--> [Deprecated] audio_time_hints (legacy, still runs)
        |   +--> audio_embed_clap (goodq_audio_embed)
        |
        +--> [OK] Entity Extraction (steps/video/entity_extractor.py:370)
        |   +--> Input: scene_data with 'transcript', 'caption', 'ocr_text', 'objects'
        |   +--> Process: Cross-modal resolution
        |   +--> Output: ExtractedEntity list (people, places, organizations)
        |
        +--> [OK] Knowledge Graph Update (lib/kg_realtime_integration.py:109)
        |   +--> Calls entity_extractor
        |   +--> Resolves entities cross-modally
        |   +--> Inserts into knowledge_graph.db
        |
        +--> [OK] Post-Processing
            +--> register_scene_bundle() -> memory.db
            +--> Qdrant insertion -> http://localhost:6333
                +--> goodq_text (transcript embeddings)
                +--> goodq_image (CLIP + DINO embeddings)
                +--> goodq_audio (CLAP embeddings)
```

**Performance:** ~1-2 hours for 1-hour video (RTX 4070 Ti SUPER)

---

## Component Details (Dec 14, 2025)

### 1. Video Pipeline (Windows - goodq_core environment)

**Responsibility:** Extract and analyze visual content per scene

**Operational Components:**

- **Scene Detection** (goodq_video_scene_detect)
  - Adaptive thresholding
  - Output: 30 scenes for 1hr video (verified)
  - Artifacts: Scene manifests with timestamps

- **OCR** (Tesseract via goodq_core)
  - Text extraction from keyframes
  - Multi-language support
  - Output: 'ocr_text' field

- **Image Captioning** (BLIP2 via goodq_core)
  - Natural language descriptions
  - Scene understanding
  - Output: 'caption' field

- **Object Detection** (YOLOv8 via goodq_core)
  - 80 COCO classes
  - Bounding boxes and confidence
  - Output: 'objects' field (verified Dec 13-14)

- **Face Recognition** (face_recognition via goodq_core)
  - Face detection and alignment
  - 128-d embedding vectors
  - Known face matching

- **Vision Embeddings**
  - **CLIP** (openai/clip-vit-base-patch16)
    - Joint vision-language representations
    - 512-d vectors
    - Zero-shot classification capability
  
  - **DINO** (facebook/dinov2-base)
    - Self-supervised visual features
    - 768-d vectors
    - Strong semantic similarity

### 2. Audio Pipeline (Windows default, WSL2 accelerated when enabled)

**Responsibility:** Extract and analyze audio content per scene

Windows-local fallback remains the default path in `BASELINE`. The WSL2 stack below describes the accelerated bridge used only when that runtime contract is explicitly active.

**Operational Components (Dual Architecture):**

**A. Queue-Based Service** (long-running daemon)
- **Service:** `~/goodq_audio/audio_service.py`
- **Status:** PID 177 (verified Dec 14)
- **Preloaded Models:**
  - Whisper medium
  - Pyannote 3.1 (speaker diarization)
  - Silero VAD (40-60% speedup)
- **Watches:** `~/goodq_audio/queue_in/`
- **Output:** `queue_out/{job_id}_result.json`

**B. Direct Invocation** (per-scene)
- **Script:** `~/goodq_audio/process_audio.py`
- **Model Loading:** On-demand with cleanup
- **Output:** `~/goodq_audio/output/result.json` (38KB verified)
- **Includes:**
  - Transcription (Whisper large-v3)
  - Diarization (52 segments, 2 speakers - verified)
  - Emotion classification (Wav2Vec2, 8-class)
  - Audio embeddings (768-dimensional)
  - Features & metadata

**Latent Capabilities:**
- Music Detection (stub exists, not connected)
- Time Hints (stub exists, not connected)

**Legacy Components (Still Running - Cleanup Planned):**
- audio_speaker_merge
- audio_music_events  
- audio_time_hints

### 3. Entity Extraction & Knowledge Graph (Windows - goodq_core)

**Responsibility:** Extract entities and build knowledge graph

**Operational Components:**

- **Entity Extractor** (`steps/video/entity_extractor.py:370`)
  - Cross-modal resolution
  - Input: transcript, caption, ocr_text, objects
  - Output: ExtractedEntity list (people, places, organizations)
  - Status: Operational (Dec 13-14 fixes applied)

- **Knowledge Graph Integration** (`lib/kg_realtime_integration.py:109`)
  - Real-time insertion
  - Entity resolution
  - Relationship building
  - Database: `<GOODQ_DATA_ROOT>\GoodQ_Data\knowledge_graph.db`
  - Status: Confirmed operational (Dec 14)

**Latent Capabilities:**
- Cross-Modal Harmonizer (`steps/video/cross_modal_harmonizer.py`)
  - Complete but not wired
  - Phase 7 deployment planned

## Storage & Database Architecture (Dec 14, 2025)

### Data Root Structure
```
<GOODQ_DATA_ROOT>\GoodQ_Data\              # [OK] Unified data root
+-- import_inbox\                 # Drop videos here
+-- memory.db                     # Scene bundles & metadata
+-- knowledge_graph.db            # Entity relationships
+-- qdrant\                       # Vector storage (port 6333)

logs\scene_ingest\                # [OK] Scene artifacts (actual location)
+-- <video_name>\
    +-- audio\                    # scene_0000.wav to scene_0029.wav
    +-- video\                    # scene_0000.jpg to scene_0029.jpg

\\wsl.localhost\Ubuntu\...\goodq_audio\  # [OK] WSL2 audio stack
+-- audio_service.py              # Daemon (PID 177)
+-- process_audio.py              # Direct invocation
+-- queue_in\                     # Service input
+-- queue_out\                    # Service output
+-- output\                       # result.json (38KB verified)
```

> **Note:** There is a known config/runtime inconsistency where `config.yaml` specifies `processing: <GOODQ_DATA_ROOT>\GoodQ_Data\processing\` but artifacts actually land in `logs\scene_ingest\`. This is non-breaking and fully documented. See [`docs/technical/ARTIFACT_LOCATION_CONTRACT.md`](../technical/ARTIFACT_LOCATION_CONTRACT.md) for details.

### Database Details

#### 1. Memory Database (`memory.db`)
**Purpose:** Scene bundles, metadata, processing state

**Key Tables:**
- `scene_bundles` - Scene metadata (30 scenes verified)
- `processing_state` - Pipeline progress
- `scene_metadata` - Timestamps, duration, frame counts

**Status:** Runtime-conditional; verify with current artifacts and DB health checks

#### 2. Knowledge Graph Database (`knowledge_graph.db`)
**Purpose:** Entity relationships, cross-modal resolution

**Key Tables:**
- `entities` - People, places, organizations
- `relationships` - Entity connections
- `mentions` - Where entities appear (scene_id, timestamp)

**Integration:** Real-time insertion via `lib/kg_realtime_integration.py:109`  
**Status:** Runtime-conditional; verify with current artifacts and DB health checks

#### 3. Qdrant Vector Database (Port 6333)
**Purpose:** Semantic search across modalities

**Collections:**
- `goodq_text` - Transcript embeddings (SBERT)
- `goodq_image` - Visual embeddings (CLIP + DINO)
- `goodq_audio` - Audio embeddings (CLAP)

**API:** http://localhost:6333  
**Status:** Runtime-conditional; verify with current artifacts and DB health checks

### Deprecated Storage
- FAISS-only storage as sole vector backend
- unified_goodq.db (consolidated into memory.db)
- Old data paths (`<project_root>/data/`)

---
-- Scene tracking
CREATE TABLE scenes (
    scene_id TEXT PRIMARY KEY,
    video_hash TEXT NOT NULL,
    scene_index INTEGER,
    start_time REAL,
    end_time REAL,
    manifest_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Asset tracking
CREATE TABLE assets (
    asset_id TEXT PRIMARY KEY,
    scene_id TEXT REFERENCES scenes(scene_id),
    asset_type TEXT,  -- 'frame', 'audio', 'text'
    content_hash TEXT UNIQUE,
    file_path TEXT,
    metadata JSON
);

-- Processing status
CREATE TABLE scene_bundles (
    scene_id TEXT PRIMARY KEY REFERENCES scenes(scene_id),
    status TEXT,  -- 'pending', 'processing', 'complete', 'failed'
    artifacts JSON,  -- Paths to generated artifacts
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Summaries (long-term memory)
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    summary_type TEXT,  -- 'short_term', 'compressed'
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### FAISS Indices

**Text Index** (`faiss_text.index`)
- Embeddings: SBERT (384-d)
- Index type: Flat (exact search)
- Capacity: ~1M vectors
- Use: Semantic text search

**Image Index - CLIP** (`faiss_clip.index`)
- Embeddings: CLIP ViT-B/16 (512-d)
- Index type: Flat
- Capacity: ~500K vectors
- Use: Visual similarity search

**Image Index - DINO** (`faiss_dino.index`)
- Embeddings: DINOv2-base (768-d)
- Index type: Flat
- Capacity: ~500K vectors
- Use: Fine-grained visual features

**Audio Index** (`faiss_audio.index`)
- Embeddings: CLAP (512-d)
- Index type: Flat
- Capacity: ~500K vectors
- Use: Audio similarity and search

### ID Mapping

**Purpose:** Link FAISS vector IDs to content hashes for auditability

**Databases:**
- `clip_id_map.sqlite`: FAISS ID -> content hash (CLIP)
- `dino_id_map.sqlite`: FAISS ID -> content hash (DINO)
- `clap_id_map.sqlite`: FAISS ID -> content hash (CLAP)

**Schema:**
```sql
CREATE TABLE id_map (
    faiss_id INTEGER PRIMARY KEY,
    content_hash TEXT NOT NULL,
    source_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_content_hash ON id_map(content_hash);
```

---

## Environment Architecture

### Isolation Strategy

**Core Principle:** Each step runs in a dedicated Conda environment with zero shared dependencies.

**Implementation:**
```powershell
# Environment creation
conda create -n goodq_<step_name> python=3.10 -y

# Isolated installation
$env:PYTHONNOUSERSITE = '1'           # No user site
$env:PIP_NO_CACHE_DIR = '1'           # No cache reuse
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

pip install -r requirements.txt `
    --no-cache-dir `
    --no-user `
    --isolated `
    --upgrade-strategy only-if-needed
```

**Project Linking:**
```python
# goodq4all_local.pth in site-packages
<project_root>\  # Parent of goodq4all for imports
```

### Environment Matrix

| Environment | Python | Purpose | GPU | Key Packages |
|-------------|--------|---------|-----|--------------|
| `goodq_core` | 3.10 | Orchestration |  | legacy orchestration, typer, openai |
| `goodq_video_scene_detect` | 3.10 | Scene detection |  | opencv, scenedetect |
| `goodq_ocr` | 3.10 | Text extraction |  | pytesseract |
| `goodq_image_caption` | 3.10 | Image captioning | [OK] | transformers, torch (CUDA) |
| `goodq_object_detect` | 3.10 | Object detection | [OK] | ultralytics, torch (CUDA) |
| `goodq_face_embed` | 3.10 | Face recognition | [OK] | face_recognition, torch (CUDA) |
| `goodq_audio_metadata` | 3.10 | Audio metadata |  | mutagen, librosa |
| `goodq_audio_diarize` | 3.10 | Speaker diarization | [OK] | pyannote.audio, torch (CUDA) |
| `goodq_audio_transcribe` | 3.10 | Speech-to-text | [OK] | faster-whisper, torch (CUDA) |
| `goodq_audio_emotion` | 3.10 | Speech emotion | [OK] | transformers, torch (CUDA) |
| `goodq_audio_embed` | 3.10 | Audio embeddings | [OK] | transformers (CLAP), torch (CUDA) |
| `goodq_text_embed` | 3.10 | Text embeddings |  | sentence-transformers |
| `goodq_sentiment` | 3.10 | Sentiment analysis |  | transformers |
| `goodq_emotion_classify` | 3.10 | Text emotion |  | transformers |
| `goodq_tagger` | 3.10 | NER tagging |  | transformers (DSLIM) |
| `goodq_llm_chat` | 3.10 | LLM interaction |  | openai |
| `goodq_tts` | 3.10 | Text-to-speech |  | elevenlabs, piper |
| `goodq_system_metrics` | 3.10 | System monitoring |  | psutil, pynvml |
| `goodq_home_assistant_status` | 3.10 | HA integration |  | requests |

**Total:** 22 environments (18 active + 4 support)

---

## Data Flow Diagram

```
+--------------------------------------------------------------+
|                         Input Sources                         |
|  Videos - Audio Files - Documents - Screen Recordings         |
+------------+-------------------------------------------------+
             |
+------------v------------------------------------------------+
|                    Content Hash Layer                         |
|  Video Hash - Scene Hash - Item Hash                         |
|  (Deduplication Check)                                        |
+------------+-------------------------------------------------+
             |
      +------+-------+
      |              |
+-----v-----+  +----v----+
|   Image   |  |  Audio  |
|  Pipeline |  | Pipeline|
+-----+-----+  +----+----+
      |             |
      |  +----------+
      |  |
+-----v--v-----------------------------------------------------+
|                    Feature Extraction                         |
|  - Text (OCR, transcripts)                                    |
|  - Objects (bounding boxes, labels)                           |
|  - Faces (identities, embeddings)                             |
|  - Embeddings (CLIP, DINO, CLAP, SBERT)                      |
|  - Emotions (speech, text)                                    |
|  - Entities (NER tags)                                        |
|  - Events (music, temporal)                                   |
+------------+--------------------------------------------------+
             |
+------------v--------------------------------------------------+
|                    Memory Integration                         |
|                                                               |
|  +--------------+  +--------------+  +--------------+       |
|  |   SQLite     |  |   FAISS      |  |   ID Maps    |       |
|  |  (Metadata)  |  |  (Vectors)   |  | (Addressing) |       |
|  +--------------+  +--------------+  +--------------+       |
+------------+--------------------------------------------------+
             |
+------------v--------------------------------------------------+
|                      Query & Retrieval                        |
|  - Semantic search (text, images, audio)                      |
|  - Temporal queries (time ranges, dates)                      |
|  - Entity-based queries (people, places)                      |
|  - Cross-modal retrieval (text -> video, audio -> image)       |
+---------------------------------------------------------------+
```

---

## Security & Privacy

### Privacy-First Design
- **No cloud processing** - All ML models run locally
- **No telemetry** - No phone-home or tracking
- **No external APIs** - Optional (OpenAI, ElevenLabs) only when explicitly configured
- **Local storage** - All data stays on user hardware

### Secret Management
- **`.env.local`** - Secrets never committed to git
- **Environment variables** - System-level for persistence
- **Token scoping** - Least-privilege access (PyAnnote, HuggingFace)
- **Redaction** - Sensitive data masked in logs

### Access Control
- **Filesystem boundaries** - Operations scoped to <project_root> drive
- **Read-only models** - Cached models never modified
- **Backup encryption** - Optional GPG encryption for backups

---

## Performance Optimizations

### GPU Utilization
- **CUDA streams** - Asynchronous model execution
- **Batch processing** - Multiple frames/segments per forward pass
- **Model caching** - Load once, reuse across items
- **Mixed precision** - FP16 inference where supported

### Memory Management
- **Lazy loading** - Models loaded on-demand
- **Explicit cleanup** - `del model; torch.cuda.empty_cache()`
- **Chunking** - Process large videos in segments
- **Streaming** - Iterator-based processing for large datasets

### I/O Optimization
- **NVMe staging** - Temp files on fast SSD
- **Parallel extraction** - ffmpeg + GPU decoding
- **Batch writes** - Group DB inserts/FAISS adds
- **Index caching** - FAISS mmap for large indices

### Deduplication Impact
- **First run:** 158 seconds (full processing)
- **Second run:** 38 seconds (76% cached)
- **Steady state:** 15-20 seconds (95%+ cached)

---

## Scalability Considerations

### Current Capacity (Single Machine)
- **Videos:** 10,000+ with 100K+ scenes
- **Memory DB:** SQLite handles GBs efficiently
- **FAISS indices:** Up to 1M vectors per index (Flat)
- **Processing:** ~10 videos/hour sustained

### Future Scaling Paths

**Horizontal:**
- Distribute steps across multiple GPUs
- Ray/Dask for parallel processing
- Shared NAS for artifact storage
- Redis for coordination

**Vertical:**
- Larger GPU (A6000, RTX 6000 Ada)
- More RAM (128GB+)
- RAID NVMe arrays
- 10Gb networking to NAS

**Index:**
- FAISS IVF indices (100M+ vectors)
- Approximate nearest neighbor (ANN)
- Quantization (PQ, SQ)

---

## Testing & Validation

### Automated Tests
```powershell
# System readiness
python scripts/system_readiness_check.py

# Cache validation
python scripts/cache_readiness_check.py

# Environment health
pwsh scripts/mission_health_check.ps1

# End-to-end smoke test
pwsh scripts/ingest_videos_lite.ps1 -MaxVideos 1 -MaxScenes 2
```

### Manual Validation
1. Check step_runs.jsonl for errors
2. Verify FAISS indices populated (reconcile_indices.ps1)
3. Query memory DB for expected content
4. Visual inspection of extracted frames/captions

### Performance Benchmarks
```powershell
# Track metrics over time
pwsh scripts/benchmark_pipeline.ps1 -InputDir test_videos -Iterations 5
```

---

## References & Resources

**Official Documentation:**
- Historical orchestration framework docs (archived reference only)
- [PyTorch Docs](https://pytorch.org/docs)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)

**Model Cards:**
- [CLIP ViT-B/16](https://huggingface.co/openai/clip-vit-base-patch16)
- [DINOv2-base](https://huggingface.co/facebook/dinov2-base)
- [CLAP](https://huggingface.co/laion/clap-htsat-unfused)
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)

**Internal Docs:**
- [Project History](../archive/PROJECT_HISTORY.md)
- [User Guide](../guides/general/USER_GUIDE.md)
- API Reference

---

*Architecture document - Version 1.2.0 - October 6, 2025*
## GPU & Performance (Dec 14, 2025 Verified)

### Hardware Configuration
- **GPU:** RTX 4070 Ti SUPER 16GB
- **CUDA:** 12.1 (Windows), 12.8 (WSL2)
- **RAM:** 32GB (16GB minimum)
- **Storage:** NVMe SSD (<project_root>\) for code, HDD (<GOODQ_DATA_ROOT>\) for artifacts

### GPU Utilization
**Normal Operating Conditions (Verified Dec 14):**
- Windows (goodq_core): 8-10GB VRAM
- WSL2 (audio service): 4-6GB VRAM
- **Total:** 12-14GB / 16GB (85% utilization)
- **Status:** Stable, concurrent processing confirmed

### Performance Metrics
| Task | Time | GPU Util |
|------|------|----------|
| Scene detection (30 scenes) | 2-20 min | Moderate |
| Per-scene vision processing | ~30-60s | High (85%) |
| Per-scene audio (WSL2 accelerated path) | ~20-40s | High (85%) |
| Entity extraction | ~5-10s | Low (CPU) |
| Knowledge graph update | <1s | N/A (SQLite) |

**Total:** ~1-2 hours for 1-hour video

### Optimization Strategies
1. **Scene-first architecture** - 30 scenes = parallel-friendly
2. **WSL2 audio preload** - Models cached in daemon (PID 177)
3. **Unified environment** - No env switching overhead
4. **GPU sharing** - Windows + WSL2 concurrent = 85% stable

---

## System Status (Dec 14, 2025 Snapshot)

### Runtime-Verified Components
- Scene detection (30 scenes confirmed)
- Frame extraction & vision models (CLIP, DINO, YOLO, BLIP, OCR)
- WSL2 audio processing (Whisper, Pyannote, emotion, CLAP)
- Entity extraction (cross-modal resolution)
- Knowledge graph (real-time insertion)
- Qdrant vector storage (3 collections active)

### Built But Not Wired (Phase 7 - Q1 2026)
- FastAPI server (api/server.py - scaffolded)
- Web UI (ui/ - frontend exists)
- Multimodal search (retrieval/multimodal_search.py)
- Cross-modal harmonizer (steps/video/cross_modal_harmonizer.py)

### Deprecated / Cleanup Planned
- legacy orchestration orchestration (removed, direct invocation now)
- FAISS-only vector operation (Qdrant remains canonical; FAISS may exist as secondary parity/fallback path)
- 6 separate conda environments (unified to goodq_core)
- Legacy audio steps (superseded by unified WSL2)
- Old entity extractor (replaced by steps/video version)

---

## Related Documentation

**Core Documentation (Updated Dec 14-15, 2025):**
- [README.md](../../README.md) - System overview with forensic verification
- [QUICK_START.md](../QUICK_START.md) - Fast launch guide
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - 7 issues, 25+ commands
- [START_HERE.md](../START_HERE.md) - Complete navigation

**Architecture Documentation:**
- [ARCHITECTURE_REFERENCE.md](ARCHITECTURE_REFERENCE.md) - Database schemas (needs Qdrant update)
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Directory layout (if exists)

**Subsystem Guides (Current):**
- [WSL2 Audio](../guides/wsl2/START_HERE_WSL2.md) - Dual architecture details
- [Qdrant Setup](../guides/QDRANT_SETUP.md) - Vector database guide
- [GPU Configuration](../guides/gpu/GPU_SETUP.md) - GPU optimization

---

## Testing & Validation (Dec 14, 2025)

### Automated Health Checks
\\\powershell
# System readiness
python scripts\system_readiness_check.py

# Model cache validation
python scripts\cache_readiness_check.py

# Service verification
Invoke-WebRequest http://localhost:6333/health  # Qdrant
wsl ps aux | grep audio_service                   # WSL2 (PID 177)
nvidia-smi                                         # GPU status
\\\

### Live Test Results (Dec 14, 2025)
[OK] **Input:** 1-hour video  
[OK] **Output:** 30 scenes processed  
[OK] **Audio:** 52 segments, 2 speakers identified (witness run used the WSL-accelerated path; `BASELINE` still defaults to Windows-local audio)  
[OK] **Entity extraction:** Operational  
[OK] **Knowledge graph:** Real-time insertion confirmed  
[OK] **GPU:** 85% utilization stable  
[OK] **Databases:** memory.db + knowledge_graph.db growing  
[OK] **Qdrant:** 3 collections receiving vectors

### Manual Verification
\\\powershell
# Check scene artifacts
Get-ChildItem "logs\scene_ingest\<video>\" -Recurse

# Check databases
Get-Item "<GOODQ_DATA_ROOT>\GoodQ_Data\*.db" | Select-Object Name, Length, LastWriteTime

# Check Qdrant collections
Invoke-WebRequest http://localhost:6333/collections
\\\

---

## Conclusion

GoodQ4All is a local multimodal pipeline with profile-gated acceleration and artifact-driven runtime truth signals.

**Key Achievements:**
- [OK] Scene-first processing (30 scenes verified)
- [OK] Unified environment (goodq_core, 30GB savings)
- [OK] Dual audio architecture (Windows-local default with optional WSL2 acceleration)
- [OK] Cross-modal entity extraction operational
- [OK] Knowledge graph real-time insertion confirmed
- [OK] Qdrant vector storage operational (3 collections)

Operational status should be interpreted from current run artifacts and health checks, not static document claims.

**Performance:** 1-2 hours per 1-hour video (RTX 4070 Ti SUPER)  
**Privacy:** 100% local processing, no cloud dependencies  
**Transparency:** Clear operational vs latent status  

---

**Last Updated:** March 19, 2026  
**Architecture Version:** 2.0 (Scene-First, Unified Environment, Dual Audio)  
**Verification Date:** December 14, 2025  
**Status:** Runtime-conditional; verify from artifacts (`control_agent_status`, `knowledge_graph_status`, `phase6_*`, vector parity fields)

---

*"The best intelligence is the intelligence you control."*
