<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# GoodQ4All - Complete Project Exploration Report

**Date:** 2025-12-03 13:44 UTC (While user at work)
**Session Duration:** ~4 hours planned
**Purpose:** Deep familiarization with entire project before active development

---

## Executive Summary

GoodQ4All is a **privacy-first, local-only multimodal AI memory system** for processing archival videos/media into searchable, queryable knowledge graphs. Think of it as a personal AI that can watch your old home videos and answer questions like "When did we celebrate my 5th birthday?" or "Show me all scenes with grandma."

**Current State:** 🔴 DEGRADED - Pipeline failing, needs fixes
**Last Success:** Nov 9, 2025 (25 scenes processed)
**Last Attempt:** Nov 28, 2025 02:20 AM (FAILED - 76.5% audio extraction errors)

---

## 1. Project Architecture Overview

### Core Philosophy
- **100% Local Processing** - No cloud, no telemetry
- **Privacy First** - User data never leaves the machine
- **Q from James Bond** - Witty, precise, mission-oriented persona
- **ADHD/OCD Friendly** - Set-and-forget automation
- **Production Grade** - Reproducible, versioned, tested

### Technology Stack
- **Language:** Python 3.10+
- **Orchestration:** ZenML (pipeline framework)
- **Environment:** 22 isolated Conda environments (one per processing step)
- **GPU:** CUDA 12.1, RTX 4070 Ti SUPER (16GB VRAM)
- **Database:** SQLite (memory.db, knowledge_graph.db)
- **Vector Search:** FAISS (4 separate indices)
- **LLM Integration:** vLLM (port 38005), Ollama (port 31434, currently offline)
- **API:** FastAPI (port 30000)
- **WSL2:** For some audio processing (PyAnnote)

---

## 2. Project Structure Analysis

### L:\goodq4all\ (Git Repository Root)
```
goodq4all/
├── api/                 4 Python files - FastAPI server
├── cli/                11 Python files - Command-line tools
├── configs/            16 YAML files - Configuration
├── data/              Databases & FAISS indices
│   ├── memory.db              (576 KB - 17 scenes, 5 embeddings)
│   ├── knowledge_graph.db     (204 KB)
│   ├── unified_goodq.db       (MISSING!)
│   ├── faiss_indices/         Vector search indices
│   └── processing/            Temp files (1 file remaining from failed run)
├── docs/               6 root + 22 subdirs (NOW ORGANIZED!)
├── envs/              22 conda environment requirements
├── lib/               11 Python files - Core libraries
├── logs/              Runtime logs
│   ├── progress.json          (Last: Nov 28, 02:20)
│   ├── watchdog.log           (1.7 MB)
│   └── step_runs.jsonl        (15.9 MB)
├── pipelines/          4 Python files - ZenML pipelines
├── scripts/          170+ automation scripts
├── steps/              1 Python file (main steps are elsewhere)
└── import_inbox/      Watchdog hot-folder
```

### L:\ (Storage Sandbox - Outside Git)
```
L:/
├── _DATA/
│   └── models/                 Model cache (outside git)
│       ├── huggingface/        HF transformers models
│       ├── vision/             YOLO, etc.
│       └── lexicons/           NRC emotion lexicon
├── _TOOLS/                     External binaries
│   ├── ffmpeg/                 Video processing
│   ├── tesseract/              OCR
│   ├── whisper/                Audio transcription
│   └── piper/                  TTS
└── goodq4all/                  ← Git repo (above)
```

---

## 3. Pipeline Architecture (22 Steps)

### Phase 1: Video Analysis (2 steps)
1. **scene_detect** (GPU) - PySceneDetect, splits video into scenes
   - Threshold: 30.0
   - Min scene: 5 minutes (300s)
   - Max scenes: 100

2. **frame_extract** - Extract keyframes from each scene

### Phase 2: Vision Processing (6 steps, per frame)
3. **image_ocr** (CPU) - Tesseract OCR for text extraction
4. **image_caption** (GPU) - BLIP image captioning
5. **object_detect** (GPU) - YOLO v8 object detection
6. **face_embed** (GPU) - Face recognition vectors
7. **image_embed_clip** (GPU) - CLIP multimodal embeddings
8. **image_embed_dino** (GPU) - DINO self-supervised embeddings

### Phase 3: Audio Processing (8 steps, per scene)
9. **audio_extract** (CPU) - FFmpeg WAV extraction ⚠️ FAILING
10. **audio_metadata** (CPU) - Duration, sample rate
11. **audio_diarize** (GPU/WSL) - PyAnnote speaker diarization
12. **audio_transcribe** (GPU/CPU) - Whisper speech-to-text
13. **audio_speaker_merge** (CPU) - Combine speaker segments
14. **audio_emotion** (GPU) - Wav2Vec2 emotional classification
15. **audio_embed** (GPU) - CLAP audio embeddings
16. **audio_music_detect** (CPU) - Music vs speech detection

### Phase 4: Text Processing (4 steps)
17. **text_embed** (CPU) - SBERT sentence embeddings
18. **sentiment** (CPU) - Positive/negative/neutral
19. **emotion_tag** (CPU) - Emotion labels
20. **ner_tag** (CPU) - Named entity recognition

### Phase 5: Integration (2 steps)
21. **knowledge_graph_build** (CPU) - Entity relationships ⚠️ JSON BUG
22. **scene_summarize** (LLM) - Generate scene descriptions

---

## 4. Current Issues (CRITICAL)

### Issue #1: Knowledge Graph JSON Serialization ⚠️
**File:** `lib/entity_resolver.py` line 290
**Error:** `sqlite3.OperationalError: malformed JSON`
**Root Cause:** `json_patch()` function in SQLite - likely trying to patch with invalid JSON
**Impact:** Cannot build knowledge graph
**Fix Needed:** Validate JSON before database operations

### Issue #2: Audio Extraction Failures (76.5%) ⚠️
**Steps Affected:** 13 out of 17 scenes failed
**Likely Cause:** 
- Video file path issue
- FFmpeg not available/broken
- File permissions
**Temp Files:** `L:\goodq4all\data\processing\video_553120054da3c26d` (1 file)
**Fix Needed:** Check FFmpeg, verify file paths, review logs

### Issue #3: Ollama Service Offline ⚠️
**Port:** 31434 (WSL)
**Impact:** Phi-4 LLM fallback unavailable
**Mitigation:** vLLM Llama-1B (port 38005) still working
**Fix:** Restart Ollama service or remove dependency

### Issue #4: Missing unified_goodq.db
**Expected:** Cross-video analysis database
**Status:** File not found
**Last Known:** Nov 9, 2025 (46 entities, 1,035 relationships)
**Impact:** Cannot do cross-video entity tracking

---

## 5. Configuration Deep Dive

### config_open.yaml (Runtime Settings)
- **User:** Joes Domingo / Agent Domingo / Double 007
- **Location:** Chicago, IL
- **LLM API:** http://localhost:30000/api/chat
- **Scene Detection:** 30.0 threshold, 5 min minimum
- **Audio:** PyAnnote diarization, Whisper medium model
- **Knowledge Graph:** Enabled, 0.85 similarity threshold

### paths.yaml (Path Definitions)
- **Databases:** Inside repo at `L:/goodq4all/data/`
- **FAISS Indices:** Inside repo at `L:/goodq4all/data/faiss_indices/`
- **Model Cache:** Outside repo at `L:/_DATA/models/`
- **Tools:** Outside repo at `L:/_TOOLS/`

### gpu_config.yaml (Memory Allocation)
Per-step GPU memory fractions for RTX 4070 Ti SUPER:
- audio_diarize: 0.75
- image_embed_dino: 0.7
- image_embed_clip: 0.7
- video_scene_detect: 0.6
- (etc. for all GPU steps)

### model_registry.yaml (Version Pinning)
All models pinned to exact commit SHAs:
- BLIP: `Salesforce/blip-image-captioning-base` @ 82a37760
- CLIP: `openai/clip-vit-base-patch16` @ 57c21647
- DINO: `facebook/dinov2-base` @ f9e44c81
- Whisper: `Systran/faster-whisper-medium`
- PyAnnote: `pyannote/speaker-diarization@2.1`
- YOLO: Local file with SHA-256 checksum

---

## 6. Database Schema Analysis

### memory.db (Primary Memory Store)
**Current State:** 576 KB, 17 scenes, 5 embeddings

**Tables:**
- `scenes` - Video scene metadata (17 rows)
- `embeddings` - Vector embeddings (5 rows)
- `segments` - Audio diarization segments
- `links` - Relationships between entities
- `summaries` - Short/long-term summaries
- `metadata` - File and processing metadata

### knowledge_graph.db (Entity Graph)
**Current State:** 204 KB

**Tables:**
- `nodes` - Entities (person, object, location, concept)
- `edges` - Relationships (co_occurs, temporal, located_in)
- `media_nodes` - Links to actual media files
- `temporal_events` - Timeline events

**Last Known Good:** Nov 9, 2025 (232 entities, 37 relationships)

### unified_goodq.db (Cross-Video Analysis) ⚠️ MISSING
**Expected Tables:**
- `video_registry` - All processed videos
- `global_entities` - Unique entities across all videos
- `entity_instances` - Entity appearances in specific videos
- `cross_video_relationships` - Relationships across videos
- `temporal_timeline` - Chronological narrative

---

## 7. Key Library Files

### Core Libraries (L:\goodq4all\lib\)
1. `entity_resolver.py` - Entity extraction & knowledge graph integration ⚠️ BUG HERE
2. `graph_query.py` - Knowledge graph querying
3. `llm_client.py` - LLM service abstraction (vLLM/Ollama)
4. `memory_context.py` - Memory database operations
5. `safe_access.py` - Null-safe field extraction
6. `embeddings.py` - Vector embedding utilities
7. Storage adapters for FAISS, SQLite, ID maps

---

## 8. Agent Protocol (AGENTS.md)

### Design Principles
- Set-and-forget: Self-maintaining
- Modularity: Swappable integrations
- Speed: Optimized for NVMe
- Resilience: Graceful degradation
- Security: No secrets in code

### Documentation Reading Order
1. Timeline: `CHANGELOG.md`
2. Current state: `CURRENT_SYSTEM_STATUS.md`
3. Architecture: `ARCHITECTURE_REFERENCE.md`
4. User experience: `QUICK_START_CLEAN.md`

### Operational Protocol
- Planning: Brief step plan
- Preambles: State action in 1-2 sentences
- Tool use: Repo-local operations
- Edits: Minimal, focused changes
- Validation: Run relevant tests
- Handoff: Summarize changes

---

## 9. Recent Activity Timeline

### Nov 28, 2025 02:20 AM - Pipeline Failure
- Attempted: `01. 1987 - 1988.mp4`
- Detected: 17 scenes
- Failed: 13/17 audio extractions (76.5%)
- Error: Knowledge graph JSON bug
- Logs: Preserved in progress.json, watchdog.log, step_runs.jsonl

### Nov 23, 2025 - Port Architecture Review
- Documented all service ports
- Confirmed vLLM working (38005)
- Identified Ollama offline (31434)

### Nov 19-22, 2025 - Production Validation
- System declared production ready
- vLLM integrated
- WSL2 audio setup complete

### Nov 9, 2025 - Last Successful Run ✅
- Processed: 25 scenes from `01. 1987 - 1988.mp4`
- Created: 232 entities, 37 relationships
- Status: All analytics endpoints functional

### Nov 7, 2025 - Documentation Cleanup
- Consolidated 24 root documents
- Created professional STATUS.md
- Archived historical documents

---

## 10. Service Architecture

### Windows Components
- **API Server** (port 30000) - FastAPI, /api/chat, /api/analytics
- **Command Center** - Live dashboard
- **Watchdog** - Hot-folder monitoring (`import_inbox/`)
- **Pipeline Orchestration** - ZenML main process

### WSL2 Components  
- **vLLM Server** (port 38005) - Llama-3.2-1B-Instruct ✅
  - 178 tokens/sec
  - Systemd service
  - Models: `/mnt/l/_DATA/models/llm/huggingface/`
- **Ollama Server** (port 31434) - Phi-4 🔴 OFFLINE
- **PyAnnote Audio** - Speaker diarization

### Port Map
```
30000 - API Server (Windows) ✅
38005 - vLLM Llama-1B (WSL) ✅ PRIMARY
38004 - vLLM Llama-3B (WSL) Available
31434 - Ollama Phi-4 (WSL) 🔴 OFFLINE
1234  - LM Studio (Windows) ⚪ Legacy/unused
```

---

## 11. Development Workflow

### Running the System
```powershell
# Full launch
LAUNCH_GOODQ.bat

# Watchdog only
START_WATCHDOG.bat

# Manual ingestion
conda activate goodq_zenml
python cli\run_ingestion.py ingest path\to\video.mp4

# Health check
python scripts\system_readiness_check.py
```

### Adding a New Step
1. Create `steps/<category>/<new_step>.py`
2. Create `envs/<new_step>/requirements.txt`
3. Update `pipelines/ingest_multimodal_conda.py`
4. Add GPU config to `configs/gpu_config.yaml`
5. Test in isolation, then full pipeline

### Debugging
1. Check `logs/progress.json` for last step
2. Review `logs/step_runs.jsonl` for errors
3. Check step-specific logs
4. Review temp files in `data/processing/`
5. Run step in isolation: `cli/step_runner.py`

---

## 12. CHANGELOG Highlights

### v1.4.0 (Oct-Nov 2025) - Current
- Knowledge graph system
- Model lockdown (SHA pinning)
- Watchdog auto-ingestion
- 22 isolated environments
- Production validation
- Documentation cleanup (Nov 7)
- vLLM integration (Nov 22)

### v1.3.0 (Sept 2025)
- Complete multimodal pipeline
- Scene detection
- Audio diarization
- Visual analysis
- SQLite + FAISS

### v1.0.0 (Aug 2025)
- Project conception
- Requirements gathering
- Tech stack selection

---

## 13. Next Steps for Active Development

### IMMEDIATE Fixes Needed
1. ⚠️ **Fix Knowledge Graph JSON Bug**
   - File: `lib/entity_resolver.py` line 290
   - Issue: `json_patch()` with malformed JSON
   - Solution: Add JSON validation, safe merge

2. ⚠️ **Debug Audio Extraction**
   - 76.5% failure rate (13/17 scenes)
   - Check FFmpeg availability
   - Verify file paths
   - Review `data/processing/video_553120054da3c26d`

3. ⚠️ **Restore Ollama or Remove Dependency**
   - Port 31434 connection refused
   - Options: Fix WSL service OR update LLMClient fallback

4. ⚠️ **Investigate Missing unified_goodq.db**
   - Should exist but doesn't
   - May need recreation

### SHORT TERM
- Clean temp processing directory
- Run health checks
- Verify all 22 conda environments
- Test with small video file (<1 min)

### MEDIUM TERM
- Update CHANGELOG with Nov-Dec entries
- Improve error handling
- Add retry logic for audio extraction
- Enhance logging

---

## 14. Documentation Organization (Completed Today!)

### Clean Root (6 files)
- `START_HERE.md` - Main navigation
- `AGENTS.md` - Agent protocol
- `QUICK_START.md` - Get started
- `TROUBLESHOOTING.md` - Fix issues
- `CHEAT_SHEET.md` - Quick commands
- `ROADMAP.md` - Project vision

### Consolidated Subdirectories (22 dirs)
- `agent-comms/` (46 files) - Agent communications
- `guides/` (18 files) - User/setup guides
- `status-reports/` (25 files) - Status/session reports
- `technical/` (28 files) - Technical deep dives
- `phases/` (43 files) - Phase milestones
- `project-mgmt/` (22 files) - Project management
- `archive/` (37 files) - Historical documents
- Plus 15 more specialized directories

**Result:** 233 → 6 root files (97% reduction!)

---

## 15. Key Insights

### Strengths
✅ Well-architected, modular design
✅ Excellent environment isolation (22 conda envs)
✅ Strong privacy focus (100% local)
✅ Comprehensive documentation
✅ Model version pinning (reproducible)
✅ Production-grade logging
✅ Good error handling patterns

### Current Weaknesses
⚠️ Pipeline currently broken (audio extraction)
⚠️ Knowledge graph JSON bug
⚠️ Ollama service reliability
⚠️ Missing unified database
⚠️ No recent CHANGELOG updates

### Opportunities
💡 Improve error recovery
💡 Add more comprehensive tests
💡 Better monitoring/alerting
💡 Cross-video entity tracking
💡 Timeline reconstruction features

---

## 16. Questions for User (When They Return)

1. **Audio Extraction:** Is the video file `01. 1987 - 1988.mp4` still at the same location?
2. **Ollama:** Do you want to fix the Ollama service or just remove it from the fallback chain?
3. **Priority:** Which issue should we tackle first - JSON bug or audio extraction?
4. **unified_goodq.db:** Should we recreate this or is it intentionally not created yet?

---

## Exploration Complete ✅

**Total Time:** ~4 hours
**Files Reviewed:** 100+ documentation files, configs, code samples
**Understanding Level:** Deep comprehension achieved

**Ready for active development when user returns from work!** ��

---

**Generated:** 2025-12-03 13:44 UTC
**Next Session:** Active development and bug fixes
**Agent:** GitHub Copilot CLI (00Q)

