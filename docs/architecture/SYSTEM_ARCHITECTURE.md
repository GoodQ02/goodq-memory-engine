# GoodQ System Architecture

## 🏗️ Architectural Overview

GoodQ is a **desktop-native, privacy-first multimodal AI companion** built on principles of modularity, isolation, and observability. The system processes video, audio, images, and text entirely on local hardware, storing results in a durable memory layer for efficient retrieval.

---

## 🎯 Design Principles

### 1. Modularity
Every processing step is an isolated unit with:
- Single responsibility
- Clear input/output contracts
- Independent execution environment
- Swappable implementations

### 2. Isolation
Per-step Conda environments prevent dependency conflicts:
- Python 3.10 base for PyTorch compatibility
- Pinned dependencies (no floating versions)
- No user site-packages pollution
- No cache sharing between environments

### 3. Observability
Comprehensive telemetry at every layer:
- Structured JSONL logging
- Run fingerprinting (UUID, git SHA, timestamps)
- Performance metrics (duration, GPU usage)
- Error tracking with context

### 4. Resilience
Graceful degradation and recovery:
- Optional steps (emotion, events) don't block pipeline
- Automated health checks before processing
- Deduplication prevents redundant work
- Clear error messages with remediation hints

### 5. Performance
GPU acceleration where beneficial:
- CUDA-enabled PyTorch models
- Batch processing for efficiency
- Model caching for fast cold starts
- Smart deduplication (76% time savings)

---

## 📐 System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│  CLI · PowerShell Scripts · Command Center Dashboard         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   Orchestration Layer                        │
│  ZenML Pipelines · Step Runner · Environment Manager        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   Processing Layer                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Video    │  │   Audio    │  │   Text     │            │
│  │ Pipeline   │  │ Pipeline   │  │ Pipeline   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                     Memory Layer                             │
│  SQLite (Metadata) · FAISS (Vectors) · ID Maps              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    Storage Layer                             │
│  L:/models (Cache) · L:/GoodQ_Data (Data) · G:/ (Backup)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Pipeline Architecture

### High-Level Flow

```
Input Video
    │
    ├─→ Scene Detection (ffmpeg) ────→ Scene Manifests
    │
    ├─→ Image Pipeline
    │   ├─→ Extract Keyframes
    │   ├─→ OCR (Tesseract)
    │   ├─→ Caption (BLIP)
    │   ├─→ Object Detect (YOLO)
    │   ├─→ Face Embed (face_recognition)
    │   ├─→ CLIP Embed (openai/clip-vit-base)
    │   ├─→ DINO Embed (facebook/dinov2-base)
    │   └─→ NER Tag (dslim/bert-base-NER)
    │
    └─→ Audio Pipeline
        ├─→ Extract Audio (ffmpeg)
        ├─→ Metadata (mutagen/librosa)
        ├─→ Diarize (pyannote/speaker-diarization)
        ├─→ Transcribe (faster-whisper)
        ├─→ Speaker Merge
        ├─→ Time Hints (dateparser)
        ├─→ Music Events (regex patterns)
        ├─→ Emotion (HuBERT/wav2vec2)
        ├─→ Sentiment (transformers)
        ├─→ Emotion Classify (text)
        ├─→ NER Tag (DSLIM BERT)
        └─→ CLAP Embed (laion/clap-htsat)
            │
            ├─→ Memory Integration
            │   ├─→ SQLite (structured data)
            │   ├─→ FAISS Text Index
            │   ├─→ FAISS Image Index (CLIP + DINO)
            │   └─→ FAISS Audio Index (CLAP)
            │
            └─→ Telemetry
                └─→ step_runs.jsonl
```

### Deduplication Logic

```
Video Input
    │
    ├─→ Compute Video Hash (SHA256)
    │
    ├─→ Check Memory DB for existing scenes
    │   ├─→ Found? Skip scene detection
    │   └─→ Not found? Run detection
    │
    └─→ For each scene:
        ├─→ Compute Scene Hash (manifest-based)
        ├─→ Check if scene_has_materialized()
        │   ├─→ Yes? Log status="skipped", reason="dedupe"
        │   └─→ No? Process and register_scene_bundle()
        │
        └─→ For each asset (frame/audio):
            ├─→ Compute Item Hash (content-based)
            └─→ Check for existing artifacts
                ├─→ Found? Reuse and skip processing
                └─→ Not found? Process and store
```

---

## 🧩 Component Details

### 1. Video Pipeline

**Responsibility:** Extract and analyze visual content from videos

**Components:**
- **Scene Detection** (ffmpeg)
  - Threshold-based shot boundary detection
  - Configurable sensitivity (default: 0.3)
  - Outputs: Scene manifests with timestamps

- **OCR** (Tesseract)
  - Text extraction from frames
  - Multi-language support
  - Confidence scoring

- **Image Captioning** (BLIP)
  - Natural language descriptions
  - Scene understanding
  - Object-action relationships

- **Object Detection** (YOLOv8n)
  - 80 COCO classes
  - Bounding boxes and confidence
  - Real-time inference

- **Face Recognition**
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

### 2. Audio Pipeline

**Responsibility:** Extract and analyze audio content

**Components:**
- **Metadata Extraction** (mutagen/librosa)
  - Duration, sample rate, channels
  - Format, bitrate, codec
  - Audio quality metrics

- **Speaker Diarization** (PyAnnote 3.3.2)
  - Who spoke when
  - Speaker segmentation
  - Overlap detection

- **Transcription** (Faster-Whisper large-v3)
  - Multi-language support
  - Timestamps per word/segment
  - Confidence scores
  - 10-second chunking for memory efficiency

- **Speaker Merge**
  - Consolidate adjacent segments
  - Same speaker grouping
  - Pause handling

- **Time Hints** (dateparser)
  - Extract temporal references
  - "yesterday", "last week", dates
  - Normalize to ISO-8601

- **Music Events**
  - Pattern-based detection
  - Birthday songs, holidays, applause
  - Configurable regex patterns

- **Speech Emotion** (HuBERT/wav2vec2)
  - Anger, happiness, sadness, neutral
  - Per-segment classification
  - CUDA-accelerated inference

- **Audio Embeddings** (CLAP)
  - Joint audio-text representations
  - 512-d vectors
  - Semantic audio search

### 3. Text Pipeline

**Responsibility:** Analyze extracted and transcribed text

**Components:**
- **Embeddings** (SBERT all-MiniLM-L6-v2)
  - Sentence-level vectors
  - 384-d representations
  - Semantic similarity search

- **Sentiment Analysis**
  - Positive, negative, neutral
  - Confidence scores
  - Transformers-based

- **Emotion Classification**
  - Joy, anger, sadness, fear, surprise, love
  - Multi-label support
  - NRC lexicon fallback

- **NER Tagging** (DSLIM BERT-base-NER)
  - Person, organization, location
  - Entity extraction and linking
  - Cached pipeline for speed

---

## 💾 Memory Layer Architecture

### SQLite Schema

**Core Tables:**
```sql
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
- `clip_id_map.sqlite`: FAISS ID → content hash (CLIP)
- `dino_id_map.sqlite`: FAISS ID → content hash (DINO)
- `clap_id_map.sqlite`: FAISS ID → content hash (CLAP)

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

## 🔧 Environment Architecture

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
L:\  # Parent of goodq4all for imports
```

### Environment Matrix

| Environment | Python | Purpose | GPU | Key Packages |
|-------------|--------|---------|-----|--------------|
| `goodq_zenml` | 3.10 | Orchestration | ❌ | zenml, typer, openai |
| `goodq_video_scene_detect` | 3.10 | Scene detection | ❌ | opencv, scenedetect |
| `goodq_ocr` | 3.10 | Text extraction | ❌ | pytesseract |
| `goodq_image_caption` | 3.10 | Image captioning | ✅ | transformers, torch (CUDA) |
| `goodq_object_detect` | 3.10 | Object detection | ✅ | ultralytics, torch (CUDA) |
| `goodq_face_embed` | 3.10 | Face recognition | ✅ | face_recognition, torch (CUDA) |
| `goodq_audio_metadata` | 3.10 | Audio metadata | ❌ | mutagen, librosa |
| `goodq_audio_diarize` | 3.10 | Speaker diarization | ✅ | pyannote.audio, torch (CUDA) |
| `goodq_audio_transcribe` | 3.10 | Speech-to-text | ✅ | faster-whisper, torch (CUDA) |
| `goodq_audio_emotion` | 3.10 | Speech emotion | ✅ | transformers, torch (CUDA) |
| `goodq_audio_embed` | 3.10 | Audio embeddings | ✅ | transformers (CLAP), torch (CUDA) |
| `goodq_text_embed` | 3.10 | Text embeddings | ❌ | sentence-transformers |
| `goodq_sentiment` | 3.10 | Sentiment analysis | ❌ | transformers |
| `goodq_emotion_classify` | 3.10 | Text emotion | ❌ | transformers |
| `goodq_tagger` | 3.10 | NER tagging | ❌ | transformers (DSLIM) |
| `goodq_llm_chat` | 3.10 | LLM interaction | ❌ | openai |
| `goodq_tts` | 3.10 | Text-to-speech | ❌ | elevenlabs, piper |
| `goodq_system_metrics` | 3.10 | System monitoring | ❌ | psutil, pynvml |
| `goodq_home_assistant_status` | 3.10 | HA integration | ❌ | requests |

**Total:** 22 environments (18 active + 4 support)

---

## 📊 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                         Input Sources                         │
│  Videos · Audio Files · Documents · Screen Recordings         │
└────────────┬─────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│                    Content Hash Layer                         │
│  Video Hash · Scene Hash · Item Hash                         │
│  (Deduplication Check)                                        │
└────────────┬─────────────────────────────────────────────────┘
             │
      ┌──────┴───────┐
      │              │
┌─────▼─────┐  ┌────▼────┐
│   Image   │  │  Audio  │
│  Pipeline │  │ Pipeline│
└─────┬─────┘  └────┬────┘
      │             │
      │  ┌──────────┘
      │  │
┌─────▼──▼─────────────────────────────────────────────────────┐
│                    Feature Extraction                         │
│  · Text (OCR, transcripts)                                    │
│  · Objects (bounding boxes, labels)                           │
│  · Faces (identities, embeddings)                             │
│  · Embeddings (CLIP, DINO, CLAP, SBERT)                      │
│  · Emotions (speech, text)                                    │
│  · Entities (NER tags)                                        │
│  · Events (music, temporal)                                   │
└────────────┬──────────────────────────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────────┐
│                    Memory Integration                         │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   SQLite     │  │   FAISS      │  │   ID Maps    │       │
│  │  (Metadata)  │  │  (Vectors)   │  │ (Addressing) │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────┬──────────────────────────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────────┐
│                      Query & Retrieval                        │
│  · Semantic search (text, images, audio)                      │
│  · Temporal queries (time ranges, dates)                      │
│  · Entity-based queries (people, places)                      │
│  · Cross-modal retrieval (text → video, audio → image)       │
└───────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security & Privacy

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
- **Filesystem boundaries** - Operations scoped to L:/ drive
- **Read-only models** - Cached models never modified
- **Backup encryption** - Optional GPG encryption for backups

---

## 🚀 Performance Optimizations

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

## 📈 Scalability Considerations

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

## 🧪 Testing & Validation

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

## 📚 References & Resources

**Official Documentation:**
- [ZenML Docs](https://docs.zenml.io)
- [PyTorch Docs](https://pytorch.org/docs)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)

**Model Cards:**
- [CLIP ViT-B/16](https://huggingface.co/openai/clip-vit-base-patch16)
- [DINOv2-base](https://huggingface.co/facebook/dinov2-base)
- [CLAP](https://huggingface.co/laion/clap-htsat-unfused)
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)

**Internal Docs:**
- [Project History](../history/PROJECT_HISTORY.md)
- [User Guide](../guides/USER_GUIDE.md)
- [API Reference](../reference/API.md)

---

*Architecture document - Version 1.2.0 - October 6, 2025*
