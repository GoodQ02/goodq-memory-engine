# goodq4all – Local Intelligence, Q‑Style

**Version 1.4.0** | **Status:** Production‑Ready (with active enhancements)  
**Last Major Architecture Review:** 2025‑11‑15

> **Cover Identity:** Formerly `GoodQ_4_All`, now `goodq4all` for consistency with GitHub and deployment scripts.  
> **Real Mission:** A privacy‑first, multimodal “Q from MI6” companion that turns decades of personal video, audio, images, and text into a durable, queryable memory system – running entirely on your own hardware.

[![Production Ready](https://img.shields.io/badge/status-production--ready-brightgreen)]()
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue)]()
[![CUDA 12.1](https://img.shields.io/badge/CUDA-12.1-green)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)]()

---

## Mission Briefing

goodq4all ingests long‑form home media, extracts scenes, voices, faces, emotions, and entities, and builds a unified knowledge graph and analytics layer you can interrogate like a field agent’s briefing room.

- 100% **local processing** (no cloud dependency) with GPU‑accelerated vision, audio, and analytics.
- **Knowledge graph** across scenes and videos with cross‑video timelines and relationship networks.
- **LLM integration** via vLLM/Ollama + a production LLM client, for summaries and interactive querying.
- **Watchdog** hot‑folder ingestion – drop files into `import_inbox/` and the system quietly does the rest.
- **22+ isolated environments** for models and steps, coordinated through a hardened orchestration layer.

For a deep architecture dossier, see `docs/ARCHITECTURE_REFERENCE.md` and `docs/COMPREHENSIVE_ARCHITECTURE_RESEARCH_2025-11-15.md`.

---

## 📋 Table of Contents

- [What is GoodQ?](#what-is-goodq)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Automatic Ingestion (Watchdog)](#automatic-ingestion-watchdog)
- [Knowledge Graph](#knowledge-graph)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Performance](#performance)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🧭 Where to Start (Docs & Status)

- **Docs index:** `docs/DOCUMENTATION_INDEX.md` – full map of project documentation.
- **Shipping surface:** `docs/SHIP_PROFILE.md` – supported commands, environments, and entrypoints.
- **Quickstart (canonical):** `docs/user-guides/QUICK_START_CLEAN.md` – most up-to-date Quick Start.
- **Current status:** `docs/CURRENT_SYSTEM_STATUS.md` – current system health snapshot.
- **Timeline:** `docs/project-history/CHANGELOG.md` – chronological project history.

For deeper dives into specific areas:

- Phases & milestones: `docs/phases/PHASE_INDEX.md`
- Audits & diagnostics: `docs/audits/AUDIT_INDEX.md`
- GPU / LLM / WSL2 / Watchdog: `docs/GPU_LLM_WSL_INDEX.md`, `docs/WATCHDOG_INDEX.md`
- Analytics: `docs/ANALYTICS_INDEX.md`
- Troubleshooting & fixes: `docs/TROUBLESHOOTING_INDEX.md`
- Release validation: `docs/RELEASE_CHECKLIST.md`

---

## Capabilities (At a Glance)

- **Multimodal ingestion**
  - GPU‑accelerated scene detection and frame extraction.
  - Audio diarization (PyAnnote), Whisper transcription, audio emotion and embeddings.
  - Vision stack: BLIP captions, YOLO object detection, face embeddings, CLIP/DINO embeddings, OCR.
- **Durable memory & knowledge graph**
  - `memory.db` and `knowledge_graph.db` for scenes, entities, relationships, and summaries.
  - `unified_goodq.db` for cross‑video entities, timelines, and relationship networks.
- **Search, analytics, and chat**
  - FAISS‑backed vector search across text, vision, and audio.
  - `/api/analytics/*` endpoints and dashboards for scenes, entities, timelines, and embeddings.
  - LLM‑powered scene and video summaries plus interactive querying via a production `llm_client`.
- **Operational hardening**
  - Scene dedupe and content‑addressable storage for reruns.
  - Model lockdown (pinned versions) and environment isolation.
  - Health checks, system readiness scripts, and rich logging for every step.

---

## Requirements

- Windows 11 + WSL2 (Ubuntu) recommended; tested on RTX 40‑series GPUs.
- CUDA 12.1 drivers; vLLM and Ollama if using local LLMs.
- Miniconda for isolated Python envs per step.
- FAISS pinned to 1.9.0 on py3.12 (set via installer for WSL).

### WSL Pipeline Bootstrap (“00Q” Installer)
- Run inside WSL from the repo root:
  ```bash
  cd /mnt/l/goodq4all
  python3 scripts/install_pipeline_wsl.py
  ```
- The 00Q field kit self-heals all pipeline envs, pins CUDA 12.1 torch stacks, installs FAISS 1.9.0 for py3.12 envs, and runs torch/FAISS smoke tests with 00Q-style logging. Safe to rerun anytime.

### Windows Pipeline Bootstrap (“00Q” Installer)
- Run inside Windows PowerShell (from repo root):
  ```powershell
  cd L:\goodq4all
  powershell -ExecutionPolicy Bypass -File scripts\install_pipeline_windows.ps1
  ```
- Creates/fixes all pipeline envs, installs requirements (no-deps), pins CUDA 12.1 torch stacks, installs FAISS 1.9.0, and runs torch/FAISS smoke tests with 00Q-style logging. Idempotent; rerun to self-heal.

---

---

## 🚀 Quick Start

### 1. Launch the Full System
```batch
LAUNCH_GOODQ.bat
```
This opens three windows:
- **Command Center**: Real-time dashboard with GPU stats, DB/FAISS status, memory snapshots
- **API Server**: FastAPI on http://localhost:30000 for retrieval and chat endpoints
- **Documentation**: Auto-opens http://localhost:30000/docs in your browser

### 2. Automatic File Processing (Watchdog)
```batch
START_WATCHDOG.bat
```
Drop files into `import_inbox/` and they'll be automatically processed. Supports:
- **Video**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`
- **Audio**: `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`
- **Images**: `.jpg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.webp`
- **Documents**: `.pdf`, `.txt`, `.md`, `.doc`, `.docx`

Monitor progress:
```batch
MONITOR_WATCHDOG.bat  # Live updates every 5 seconds
CHECK_WATCHDOG.bat    # One-time status check
```

### 3. Manual Processing
```batch
conda activate goodq_zenml
python cli\run_ingestion.py ingest path\to\video.mp4
```

---

## 🔍 Automatic Ingestion (Watchdog)

### What is the Watchdog?

The GoodQ Watchdog is an automatic file monitoring system that watches `import_inbox/` and processes new files immediately. Think of it as a "hot folder" for your AI pipeline – drop in a video, and processing begins automatically.

### Features

- **Automatic Detection**: Scans every 2 seconds for new files
- **Smart Deduplication**: Uses SHA-256 hashing to avoid reprocessing identical files
- **File Stability**: Waits 3 seconds after file stops changing before processing
- **Queue Management**: Processes files sequentially to ensure system stability
- **Status Tracking**: Maintains registry of all processed files with timestamps and status
- **Error Handling**: Failed files moved to `data/failed/` with detailed error logs

### Quick Start

**1. Start the Watchdog**
```batch
START_WATCHDOG.bat
```

**2. Drop Files**
Simply drag and drop files into:
```
L:\goodq4all\import_inbox\
```

**3. Monitor Progress**
```batch
MONITOR_WATCHDOG.bat  # Live dashboard (updates every 5 seconds)
CHECK_WATCHDOG.bat    # One-time status snapshot
```

### File Flow

```
import_inbox/video.mp4
         ↓
    [Detected & Queued]
         ↓
data/processing/video.mp4  (temporary copy)
         ↓
    [Run Pipeline]
         ↓
  ┌─────┴─────┐
  │           │
Success      Failure
  │           │
  ↓           ↓
data/processed/  data/failed/
PROCESSED_video  FAILED_video
```

### Supported File Types

| Type | Extensions |
|------|------------|
| **Video** | `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`, `.m4v` |
| **Audio** | `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.wma` |
| **Image** | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.webp` |
| **Document** | `.pdf`, `.txt`, `.md`, `.doc`, `.docx` |

### Status Dashboard

The `CHECK_WATCHDOG.bat` shows:
- Watchdog running status (PID, CPU, memory)
- File counts (inbox, processing, processed, failed)
- Recent inbox files with sizes
- All-time statistics from registry
- Recent log activity

### Logs & Registry

- **Activity Log**: `logs/watchdog.log` - All watchdog activity and errors
- **State Registry**: `logs/watchdog_state.json` - Hash registry of all processed files
- **Step Logs**: `L:\_DATA\GoodQ_Data\logs\step_runs.jsonl` - Per-step pipeline execution

### How Deduplication Works

1. When a file becomes stable, compute its SHA-256 hash
2. Check `logs/watchdog_state.json` for this hash
3. If found → Mark as `PROCESSED_` and skip
4. If not found → Process and add hash to registry

This means:
- Renaming doesn't fool the system (content hash is checked)
- Copying the same video multiple times only processes once
- Different files with the same name are processed separately

### Advanced Usage

**Test the Watchdog**
```batch
conda activate goodq_zenml
python scripts\test_watchdog.py
```

**Configuration** (edit `scripts/watchdog_ingest.py`):
```python
POLL_INTERVAL = 2.0      # Scan frequency (seconds)
STABILITY_WAIT = 3.0     # Wait for file to stabilize
MAX_WORKERS = 1          # Concurrent processors
```

**View Live Logs**
```powershell
Get-Content L:\goodq4all\logs\watchdog.log -Wait -Tail 20
```

### Integration Tips

- The watchdog is **separate from LAUNCH_GOODQ.bat** to avoid auto-processing on startup
- Start it when you're ready to drop files for processing
- Leave it running in the background for continuous processing
- Use `MONITOR_WATCHDOG.bat` to track progress without checking the console

### Troubleshooting

**Files not detected?**
- Verify file extension is supported
- Check `logs/watchdog.log` for errors
- Ensure watch directory exists: `L:\goodq4all\import_inbox`

**Processing fails?**
- Check `data/failed/` for failed files
- Review error in `logs/watchdog.log`
- Try manual processing to see full error:
  ```batch
  conda activate goodq_zenml
  python cli\run_ingestion.py ingest path\to\file.mp4
  ```

**Files stuck in processing?**
- Check if watchdog process is still running
- Look for errors in `logs/watchdog.log`
- Restart watchdog if needed

📖 **Full Documentation**: See [docs/WATCHDOG_GUIDE.md](docs/WATCHDOG_GUIDE.md) and [docs/diagrams/watchdog_flow.md](docs/diagrams/watchdog_flow.md)

---

## 🕸️ Knowledge Graph

### What is the Knowledge Graph?

The Knowledge Graph creates semantic relationships between all entities detected in your media. Instead of treating each frame or scene in isolation, it connects people, objects, locations, emotions, and events into a queryable network.

### Key Capabilities

- **Entity Tracking**: Track people, objects, and concepts across scenes and time
- **Relationship Discovery**: Automatic detection of co-occurrence, temporal, and semantic relationships
- **Semantic Search**: Find content based on complex criteria (e.g., "scenes with happy emotions and people at the beach")
- **Temporal Narratives**: Get story-like summaries of time periods with key entities and events
- **Scene Similarity**: Find related scenes based on shared entities and context

### Quick Start

**View Graph Statistics**
```bash
conda activate goodq_zenml
python cli/graph_query.py stats
```

**Find All Appearances of a Person**
```bash
python cli/graph_query.py find-person "John"
```

**Get Full Context for a Scene**
```bash
python cli/graph_query.py scene-context scene_0042
```

**Search by Multiple Criteria**
```bash
python cli/graph_query.py search --objects person dog --emotions happy --min-confidence 0.7
```

**Track Concept Over Time**
```bash
python cli/graph_query.py track-concept "birthday"
```

**Get Temporal Narrative**
```bash
python cli/graph_query.py story 0 60  # Get story from 0-60 seconds
```

### How It Works

1. **During Ingestion**: The pipeline extracts entities (people, objects, emotions, locations) from each scene
2. **Graph Construction**: The `build_knowledge_graph` step creates nodes for entities and edges for relationships
3. **Automatic Linking**: Entities are linked to media with timestamps and confidence scores
4. **Relationship Building**:
   - **Co-occurrence**: Entities appearing together in same scene
   - **Temporal**: Entities appearing in adjacent time windows
   - **Semantic**: Domain-specific relationships (person-location, object-emotion, etc.)

### Graph Schema

- **Nodes**: Entities (person, object, location, concept, event, emotion)
- **Edges**: Relationships (co_occurs, located_in, has_emotion, interacts_with, etc.)
- **Media Nodes**: Links to actual video scenes/audio with timestamps
- **Temporal Events**: Time-based occurrences with participating entities

### Advanced Queries

**Python API**
```python
from lib.graph_query import GraphQuery

with GraphQuery('data/knowledge_graph.db') as gq:
    # Find related scenes
    related = gq.find_related_scenes('scene_0042', max_results=5)
    
    # Get scene context with all entities
    context = gq.get_scene_context('scene_0042')
    
    # Search by criteria
    results = gq.search_by_multiple_criteria({
        'objects': ['person', 'car'],
        'emotions': ['happy'],
        'time_range': (0, 100),
        'min_confidence': 0.7
    })
```

### Testing

**Run Knowledge Graph Tests**
```bash
python scripts/test_knowledge_graph.py
```

This creates a test database and validates all query patterns.

📖 **Full Documentation**: See [docs/knowledge_graph.md](docs/knowledge_graph.md)

---

## 🎯 What is GoodQ?
- Readiness passes remain automated: run `python scripts\system_readiness_check.py` and `python scripts\cache_readiness_check.py` before ingest. They self-heal HF/Torch env vars, validate CUDA/PyAnnote, and fail fast if required assets drift from `L:/models`.
- Model and dataset caches now cover the full foundation set: `scripts\download_datasets.py` prefetches sentiment/NLP corpora, math & science benchmarks, geospatial/astronomy references, and baseline ASR datasets into `L:/models/hf/datasets`, and recognises category-specific vendor directories for advanced corpora (COCO, Common Voice, MMLU, etc.).
- The CLI orchestrator ships with "smart memory": before processing a scene it checks SQLite for existing keyframe/audio hashes and reuses stored manifests to skip detection when the video hash matches; every downstream step is logged as `status="skipped"` with `extra.reason="dedupe"` when artifacts already exist, and metadata is reused.
- Every run carries a digital fingerprint. `run_ingestion.py` stamps a UUID, pipeline name, start timestamp, optional git SHA, and a scene manifest hash into `logs/_resolved_config.json`, and those fields propagate to every `step_runs.jsonl` entry.
- Step telemetry is centralized under `L:\_DATA\GoodQ_Data/logs`, now enriched with run metadata so audits can trace skipped vs materialized work across replays.
- Lite ingestion continues end-to-end; the only outstanding blocker is adding `hf_transfer` (or vendoring the SER weights) inside `goodq_audio_emotion` so the audio emotion step no longer short-circuits.
- Legacy `GoodQ_Pipeline` stays reference-only while storage now lives under `L:\_DATA\GoodQ_Data` alongside `goodq4all`.

## Readiness & Caches
- `python scripts/system_readiness_check.py` – verifies env vars, tool paths, CUDA availability, PyAnnote auth, and Hugging Face access. It auto-corrects `HF_HOME/TORCH_HOME/HF_HUB_ENABLE_HF_TRANSFER` for the run and records any fallbacks in the report.
- Gated datasets follow a three-tier flow: reuse vendored caches under `L:/models/hf/datasets` first, fall back to authenticated downloads (honouring `HF_TOKEN` + `hf_transfer`), and gracefully skip with a warning when no token is available.
- `python scripts/cache_readiness_check.py` – confirms required Hugging Face snapshots, YOLO weights, NRC lexicons, and datasets exist under `L:/models`; the dataset section now calls out vendored/cached/gated corpora so you can stage large resources before production runs.
- `conda run -n goodq_text_embed python scripts/download_datasets.py` – warms the lightweight datasets we rely on for smoke tests. Missing repos are logged as warnings so the script never blocks the pipeline.
- Use `HF_DOWNLOAD_GATED=1` with `scripts\download_datasets.py` when you need gated corpora. Common Voice 17, COCO 2017, `lukaemon/mmlu_flan`, SciKnowOrg materials science, tweet_sentiment_multilingual, and speech_commands still require manual approval or updated loaders; they will continue to surface warnings until you vendor them locally or refresh `dataset_specs.py`.

## Open Issues
- **Audio emotion classification**: install `pip install hf_transfer` inside `goodq_audio_emotion` (or vendor the wheel) so Transformers can stream `superb/hubert-large-superb-er` or `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` without timing out.
- **Runtime monitoring**: continue tailing `L:\_DATA\GoodQ_Data/logs/step_runs.jsonl` during long runs – if ingestion pauses, the log will reveal which step is waiting on downloads.
- **Validation plan**: once audio emotion loads cleanly, rerun `pwsh scripts/ingest_videos_lite.ps1 -InputDir import_inbox -MaxFrames 10 -MaxSegments 3` to confirm end-to-end persistence, then graduate to the full orchestrator smoke.

## Why GoodQ Exists
- Desktop-native, privacy-first AI companion inspired by Q from the Bond universe.
- Combines multimodal ingestion (video, audio, documents) with durable memory, diagnostics, and rapid search.
- Runs local-first: CUDA acceleration, local embeddings, optional offline TTS, and configurable LLM endpoints (LM Studio, Ollama, OpenAI-compatible APIs).
- Mission control mindset: health checks, automated backups, and pipeline-level observability are built into every run.

## Major Capabilities
- **Multimodal ingestion**: scene detection, frame captioning, OCR, object/face embeddings, PyAnnote diarization, whisper.cpp transcription, CLAP audio embeddings, SBERT text embeddings.
- **Memory management**: schema introspection, FAISS/DB reconciliation, automatic backups, and ZenML artifact tracking.
- **Mission telemetry**: Command Center CLI, pipeline summaries, and environmental sync that keep caches, tokens, and configs aligned.
- **Home & system awareness**: optional Home Assistant polling and hardware diagnostics for richer context during missions.

## Architecture Overview
- ZenML pipelines coordinate per-step Conda environments for isolation and reproducibility.
- Step runner (`goodq4all.cli.step_runner`) loads items/config JSON, executes a step, and writes results back to disk so PowerShell orchestrators remain simple.
- Persistence layer uses SQLite (`memory.db`) plus FAISS indices for text/image/audio, with ID maps to reconcile embeddings and raw assets.
- Short-term run summaries and long-term compressed history live side-by-side in `memory.db::summaries`, mirroring the Context Engineering guidance used in the original GoodQ stack.

## Key Pipelines
- **ingest_multimodal** (scaffold): discovers inputs, processes audio/image/text, and enriches items with embeddings and analytics.
- **ingest_multimodal_conda**: production pipeline using ZenML decorators and Conda environment delegation for each heavy step.
- **goodq_chat**: chat/mission pipeline (LLM prompt, optional TTS playback).

## Step Highlights
- **Audio**: metadata (mutagen/librosa) → diarization (PyAnnote) → chunking → whisper.cpp transcription (10 s windows) → speaker merge, time hints, music events, emotion (Transformers SER), CLAP embedding, transcript sentiment/tagging.
- **Image**: ffmpeg-scene frames → OCR (tesseract) → caption (BLIP) → detection (YOLO) → face embeddings (face_recognition or facenet-pytorch fallback) → CLIP & DINO embeddings stored in FAISS.
- **Text**: SBERT embeddings, sentiment, emotions, tagger (DSLIM NER with transformers logging suppressed and cached pipelines) and usefulness scoring.
- **Context**: Home Assistant API snapshot, system metrics (psutil + NVIDIA SMI), Command Center summaries.

## Configuration Files
- `configs/config_open.yaml` – primary runtime settings (LLM endpoints, tool paths, video thresholds, tagger model).
- `configs/paths.yaml` – canonical paths for logs, outputs, DB, FAISS, ID maps.
- `configs/entities.yaml` – Home Assistant entities (optional).
- `.env.local` – auto-synced secrets and cache variables (never commit).

## Environment Layout
- `envs/<step>/requirements.txt` – per-step dependency pins; GPU-enabled envs include `image_caption`, `object_detect`, `audio_transcribe`, `audio_diarize`, `audio_emotion`, `face_embed`.
- `scripts/enable_cuda.ps1` – installs CUDA wheels for every GPU env; use `-Verify` to confirm.
- Run `scripts/prepare_step_envs.ps1 -EnvPrefix goodq -LinkProject` to create/update envs and drop `.pth` files pointing to `L:/` so `goodq4all` imports resolve.

## Model Lockdown & Version Pinning
- `configs/model_registry.yaml` – **Central registry** pinning all models to exact commit SHAs and file hashes, preventing version drift.
- `scripts/pin_model_versions.py` – Fetches latest commit SHAs from HuggingFace Hub and updates registry with real versions.
- `scripts/verify_model_lockdown.py` – Verifies all models are properly pinned and assets match expected hashes.
- `scripts/bootstrap_models.py` – Downloads models respecting registry pins for reproducibility.
- **Security**: SHA256 verification for external assets, explicit auth tokens for gated models, offline mode support.
- **Policy**: `auto_update: false` ensures no surprise breaking changes; all updates require manual approval.
- See [docs/MODEL_LOCKDOWN.md](docs/MODEL_LOCKDOWN.md) for complete documentation.

## Quickstart
1. **Optional reset**: `pwsh scripts/reset_goodq_envs.ps1 -EnvPrefix goodq -Force -ClearTemp`
2. **Install & cache warm-up**: `pwsh scripts/install_goodq.ps1 -SetCacheEnv -ModelsCache 'L:/models'`
3. **Preflight**: `pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq -FixMissingCaches`
4. **Dry run**: `pwsh scripts/mission_launch.ps1 -Mode dryrun -EnvPrefix goodq`
5. **Full pipeline + dashboard**: `pwsh scripts/mission_launch.ps1 -Mode pipeline -OpenDashboard`
6. **Lite ingestion sanity check**: `pwsh scripts/ingest_videos_lite.ps1 -InputDir import_inbox -MaxFrames 10 -MaxSegments 3`

## Scripts Worth Knowing
- `scripts/install_goodq.ps1` – one-shot installer (envs, CUDA, optional dry run).
- `scripts/mission_health_check.ps1` – diagnostics (DB/FAISS, env sanity, cache check).
- `scripts/mission_launch.ps1` – orchestrates health, CUDA, pipeline launch, Command Center.
- `scripts/sync_env_local.ps1` – copies approved system env vars into `.env.local` before each run.
- `scripts/enable_cuda.ps1` – ensures GPU wheels across envs; `-Verify` prints per-env status.
- `scripts/reconcile_indices.ps1` – compares FAISS `ntotal` vs DB/ID-map counts, flags drift.
- `scripts/run_full_dry_run.ps1` – generates export bundle with DB, FAISS, logs.
- `scripts/command_center.ps1` – interactive dashboard (GPU, DB/FAISS stats, step log tail).
- `scripts/launch_goodq.bat` – Windows launcher for full-stack mission runs.

## Artifacts & Logs
- Ingestion logs live under `L:\_DATA\GoodQ_Data/logs` until the ZenML artifact store migration completes.
- Lite/full runs emit per-step JSON outputs (`logs/step_runs.jsonl`) and bundle exports (`logs/run_exports/YYMMDD_HHMMSS`).
- Audio/text/image embeddings are written to SQLite (`memory.db`) and FAISS indices defined in `configs/paths.yaml`.
- CLAP ID maps keep FAISS IDs aligned with content fingerprints for auditability.

## Environment Variables
- Required tokens: `PYANNOTE_TOKEN` or `PYANNOTE_AUDIO_AUTH`, `HF_TOKEN`, `OPENAI_API_KEY` (or LM Studio/Ollama equivalents), optional `ELEVENLABS_API_KEY`, `HA_TOKEN`.
- Cache homes: set `HF_HOME` and `TORCH_HOME` to `L:/models`; `TRANSFORMERS_CACHE` is deprecated.
- `scripts/set_env_vars.ps1 -OnlyIfMissing` provides a safe setter for commonly used keys.

## Historical Context
- The original GoodQ_o2-B repository (now archived) introduced the mission-oriented UX, dual TTS, system monitoring, and Home Assistant hooks.
- Its documentation, changelogs, and requirements have been consolidated into `L:/legacy` so the active ZenML project stays lean while preserving institutional knowledge.
- You can still explore experimental modules (LLM orchestration, trend analytics, mission logging) inside the legacy archive; port relevant ideas into `goodq4all` as needed.

## Recent Highlights & Next Steps
- Conda envs rebuilt under `C:/Users/jdben/miniconda3`; installer scripts now target this base and relink the repo automatically.
- `system_readiness_check.py` and `cache_readiness_check.py` both report **GREEN**; vendor modules live under `goodq4all/vendor` to satisfy non-conda imports.
- Lite ingestion (`scripts/ingest_videos_lite.ps1 -VerboseSteps`) runs end-to-end without hangs: diarization, transcription, audio emotion, CLAP, and text pipelines all complete.
- Step telemetry captures `run_id`, pipeline metadata, canonical IDs, and raises an `improbable_duration` flag when GPU-heavy steps finish suspiciously fast.
- Pip/models/dataset caches are centralized (`L:/pip_cache`, `L:/models`), avoiding writes to the system drive and speeding up reruns.
- `python scripts/system_readiness_check.py` — verifies env vars, tool paths, CUDA availability, PyAnnote auth; falls back to normalized paths and records any auto-corrections.
- `python scripts/cache_readiness_check.py --json` — confirms Hugging Face/Torch snapshots, YOLO weights, NRC lexicons, and dataset caches under `L:/models`; optional caches are reported but non-blocking.
- `conda run -n goodq_text_embed python scripts/download_datasets.py` — warms the smoke-test datasets; failures are logged as warnings only.
- `scripts/set_env_vars.ps1` now de-dupes `.env.local` entries so repeated installs no longer append duplicates.
- **Scene idempotence:** `run_ingestion.py` still recomputes image/audio pipelines on every run. Next pass should compute a `scene_manifest_hash`, consult `scene_has_materialized(...)`, and log `skipped` entries instead of reprocessing.
- **Run metadata propagation:** `cfg['run']` is partially in place (logger consumes it) but `run_ingestion.py` still needs to stamp `run_id`, `started_at`, `git_sha`, etc., before writing the config snapshot.
- **Performance polish (optional):** adopt NVDEC (`ffmpeg -hwaccel cuda`), stage scratch on NVMe, enable TF32 (`torch.backends.cuda.matmul.allow_tf32 = True`), and fuse/batch post-ops for additional speed.
