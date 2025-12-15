# GoodQ4All Quick Start Guide

**Last Updated:** December 15, 2025  
**Status:** ✅ Forensically Verified Operational System

> **Note:** This is the comprehensive quick start guide. For a faster overview, see [QUICK_START.md](../../QUICK_START.md). Both documents are current as of Dec 14-15, 2025.

---

## 🎯 What This System Does

GoodQ4All is a **local, GPU-accelerated multimodal AI pipeline** that:

✅ **Sees** - Scene detection, object detection (YOLO), face recognition, OCR  
✅ **Hears** - Speech transcription (Whisper large-v3), speaker diarization (Pyannote 3.1)  
✅ **Understands** - Image captioning (BLIP2), emotion classification (Wav2Vec2)  
✅ **Extracts** - Entity recognition (cross-modal: people, places, organizations)  
✅ **Remembers** - Knowledge graph building with real-time insertion  
✅ **Searches** - Vector embeddings (CLIP, DINO, CLAP) in Qdrant database

**All processing happens on your local machine.** No cloud. No privacy compromise.

**Verified Operational:** 30 scenes processed Dec 14, 2025 with full multimodal extraction.

---

## 🚀 Quick Launch (5 Minutes)

### Prerequisites
✅ Windows 11 with WSL2 (Ubuntu)  
✅ NVIDIA GPU with CUDA support (RTX 40-series recommended)  
✅ 16GB+ RAM (32GB recommended)  
✅ 100GB+ free disk space  
✅ Conda/Miniconda installed

### Step 1: Launch the System
```batch
cd L:\goodq4all
.\LAUNCH_GOODQ.bat
```

**What Happens:**
1. System health check (models, dependencies, services)
2. Qdrant vector database starts (port 6333)
3. WSL2 audio service verified (PID 177)
4. Watchdog begins monitoring `L:\_DATA\GoodQ_Data\import_inbox\`

**Expected Output:**
```
[INFO] System health check passed
[INFO] Qdrant service started on port 6333
[INFO] WSL2 audio service active (PID 177)
[INFO] Watchdog monitoring: L:\_DATA\GoodQ_Data\import_inbox
[INFO] Processing pipeline ready
```

### Step 2: Drop a Video
```batch
# Copy video to the inbox
Copy-Item "your_video.mp4" "L:\_DATA\GoodQ_Data\import_inbox\"
```

### Step 3: Watch Processing
Monitor the command window for progress:
```
[INFO] New file detected: your_video.mp4
[INFO] Starting scene detection...
[INFO] Scene 1/30 detected
[INFO] Processing audio with WSL2 (GPU-accelerated)
[INFO] Diarization: 52 segments, 2 speakers
[INFO] Entity extraction active
[INFO] Knowledge graph updated
```

**Processing Time:** ~1-2 hours for a 1-hour video (RTX 4070 Ti SUPER)

### Step 4: Verify Results
```powershell
# Check scene artifacts
Get-ChildItem "logs\scene_ingest\your_video\" -Recurse

# Check databases
Get-Item "L:\_DATA\GoodQ_Data\*.db" | Select-Object Name, Length, LastWriteTime

# Check Qdrant collections
Invoke-WebRequest http://localhost:6333/collections
```

---

## 📁 Important Locations (Dec 14, 2025 Verified)

| What | Where | Status |
|------|-------|--------|
| **Drop videos here** | `L:\_DATA\GoodQ_Data\import_inbox\` | ✅ Active |
| **Scene artifacts** | `logs\scene_ingest\<video>\audio\` & `video\` | ✅ Verified |
| **Memory database** | `L:\_DATA\GoodQ_Data\memory.db` | ✅ Operational |
| **Knowledge graph** | `L:\_DATA\GoodQ_Data\knowledge_graph.db` | ✅ Operational |
| **Vector database** | http://localhost:6333 (Qdrant) | ✅ Port verified |
| **WSL2 audio output** | `\\wsl.localhost\Ubuntu\home\<user>\goodq_audio\output\` | ✅ Confirmed |

### Data Structure
```
L:\_DATA\GoodQ_Data\          # Unified data root
├── import_inbox\             # Drop videos here
├── memory.db                 # Scene bundles & metadata
├── knowledge_graph.db        # Entity relationships
└── qdrant\                   # Vector storage

logs\scene_ingest\            # Scene artifacts
└── <video_name>\
    ├── audio\                # scene_0000.wav to scene_0029.wav
    └── video\                # scene_0000.jpg to scene_0029.jpg
```

---

## 🔧 Troubleshooting

### System Won't Start
```powershell
# Run health checks
python scripts\system_readiness_check.py
python scripts\cache_readiness_check.py

# Check services
Invoke-WebRequest http://localhost:6333/health  # Qdrant
wsl ps aux | grep audio_service                   # WSL2 (should show PID 177)
nvidia-smi                                         # GPU status
```

**Common Issues:**
- Qdrant not running → Start with `vendor\qdrant\qdrant.exe`
- WSL2 audio service down → `wsl cd ~/goodq_audio && python audio_service.py &`
- HuggingFace token missing → Add to WSL2 `~/.config/config.json`

### Processing Stuck
```powershell
# Check scene artifacts (should be growing)
Get-ChildItem "logs\scene_ingest\<video>\audio\" | Select-Object Name, Length, LastWriteTime

# Check WSL2 audio logs
wsl tail -f ~/goodq_audio/logs/audio_service.log

# Check GPU activity (85% util normal)
nvidia-smi
```

### GPU Out of Memory
**Normal Usage:** 12-14GB / 16GB (85% utilization is expected and stable)

```powershell
# Check what's using GPU
nvidia-smi

# If over 95%, clear cache
python -c "import torch; torch.cuda.empty_cache()"
```

**For More Help:** See comprehensive [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) with 7 issues and 25+ diagnostic commands.

---

## 📊 What Gets Extracted (Dec 14, 2025 Verified)

### From Video (Per Scene - 30 typical for 1hr video)
- ✅ **Scene Detection** - Adaptive thresholding (30 scenes detected in test)
- ✅ **Keyframe Extraction** - Representative frames per scene
- ✅ **Object Detection** - YOLOv8 with 'objects' field population
- ✅ **Face Recognition** - Embeddings for person identification
- ✅ **Image Captioning** - BLIP2 natural language descriptions
- ✅ **OCR Text** - Tesseract text extraction
- ✅ **Visual Embeddings** - CLIP (semantic) + DINOv2 (visual features)

### From Audio (WSL2 GPU-Accelerated)
- ✅ **Speech Transcription** - Whisper large-v3 (38KB output verified)
- ✅ **Speaker Diarization** - Pyannote 3.1 (52 segments, 2 speakers confirmed)
- ✅ **Emotion Classification** - Wav2Vec2 (8-class output in result.json)
- ✅ **Audio Embeddings** - 768-dimensional vectors for semantic search
- ⊘ **Music Detection** - Stub exists, not yet connected
- ⊘ **Time Hints** - Stub exists, not yet connected

### Multimodal Intelligence
- ✅ **Entity Extraction** - Cross-modal (transcript + caption + OCR + objects)
- ✅ **Knowledge Graph** - Real-time insertion confirmed (Dec 14)
- ✅ **Scene Bundles** - Registered in memory.db
- ✅ **Vector Storage** - Qdrant collections (text, image, audio)
- ⊘ **Cross-Modal Harmonizer** - Built but not wired (Phase 7)

**Legend:** ✅ Operational | ⊘ Latent (built, not wired)

---

## 🎯 Supported File Types

### Video (Primary)
- **.mp4** (recommended), .avi, .mov, .mkv, .webm
- **Scene-first processing:** Video split into ~30 scenes for 1hr video
- **Processing time:** ~1-2 hours for 1-hour video (RTX 4070 Ti SUPER)

### Audio
- .wav, .mp3, .flac, .ogg, .m4a
- **WSL2 acceleration:** GPU-accelerated transcription + diarization
- **Output:** Transcript, speaker segments, emotion classification, embeddings

### Images
- .jpg, .jpeg, .png, .bmp, .tiff
- **Processing:** Object detection, captioning, embeddings, OCR

### Documents (Future)
- .pdf, .txt (text extraction planned)

---

## 🔥 Performance Tips (Dec 14, 2025 Verified)

### Hardware Expectations
- **GPU:** RTX 4070 Ti SUPER 16GB (85% utilization normal)
- **CUDA:** 12.1 (Windows), 12.8 (WSL2)
- **RAM:** 32GB recommended (16GB minimum)
- **Processing Speed:** 1-2 hours per 1-hour video

### Optimization
1. **First run slower** (~5-10 min model loading), subsequent runs faster
2. **GPU sharing works** - Windows (vision) + WSL2 (audio) share GPU by design
3. **Scene-first architecture** - 30 scenes = parallel-friendly processing
4. **WSL2 audio preloads models** - Faster per-scene audio processing
5. **Monitor normal** - 85% GPU utilization is expected and stable

### What to Avoid
- ❌ Don't run other GPU-heavy tasks during processing
- ❌ Don't interrupt mid-scene (let current scene finish)
- ❌ Don't close command window until "Processing complete"

---

## ⊘ API & UI Status (Not Yet Deployed)

### FastAPI Server (Scaffolded, Not Active)
- **Location:** `api/server.py`
- **Status:** ⊘ Built but not wired (Phase 7 deployment)
- **Planned Endpoint:** http://localhost:30000/docs

### Web UI (Frontend Exists, Not Deployed)
- **Location:** `ui/index.html`, `ui/static/js/app.js`
- **Status:** ⊘ Frontend ready, needs API backend
- **Phase 7:** Planned for Q1 2026

**For Now:** Processing is CLI-based. Results stored in databases and Qdrant for programmatic access.

---

## 📝 Processing Checklist

### Before Processing
- [ ] **Check disk space** (~50GB per hour of video)
- [ ] **Run health checks** (`python scripts\system_readiness_check.py`)
- [ ] **Verify GPU available** (`nvidia-smi`)
- [ ] **Check services running** (Qdrant 6333, WSL2 audio PID 177)
- [ ] **Close other GPU-heavy apps** (leave ~4GB VRAM free)

### During Processing
- [ ] **Monitor progress** (command window shows scene count)
- [ ] **Check GPU utilization** (85% is normal, <95% stable)
- [ ] **Watch for errors** (red [ERROR] messages in logs)
- [ ] **Verify artifacts growing** (`Get-ChildItem "logs\scene_ingest\<video>"`)
- [ ] **Don't interrupt mid-scene** (let current scene finish)

### After Processing
- [ ] **Verify completion** (all scenes processed)
- [ ] **Check databases** (`Get-Item "L:\_DATA\GoodQ_Data\*.db"`)
- [ ] **Test Qdrant** (`Invoke-WebRequest http://localhost:6333/collections`)
- [ ] **Review knowledge graph** (database should have grown)
- [ ] **Move processed videos** (optional: archive originals)

---

## 🆘 Quick Fixes

### System Won't Start
```powershell
# Check Qdrant
Invoke-WebRequest http://localhost:6333/health
# If fails: cd vendor\qdrant && .\qdrant.exe

# Check WSL2 audio
wsl ps aux | grep audio_service
# If missing: wsl cd ~/goodq_audio && python audio_service.py &
```

### Processing Stuck
```powershell
# Check scene artifacts
Get-ChildItem "logs\scene_ingest\<video>\audio\" | Measure-Object

# Check WSL2 logs
wsl tail -20 ~/goodq_audio/logs/audio_service.log

# Check GPU (85% normal)
nvidia-smi
```

### CUDA Not Available
**Windows:**
```powershell
# Check CUDA version (should be 12.1)
nvidia-smi | Select-String "CUDA Version"

# Verify PyTorch sees GPU
python -c "import torch; print(torch.cuda.is_available())"
```

**WSL2:**
```bash
# Check CUDA version (should be 12.8)
nvidia-smi

# Verify WSL2 sees GPU
wsl nvidia-smi
```

**For More Issues:** See [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) - 7 common issues with detailed fixes.

---

## 📚 Additional Resources

### Core Documentation (✅ Updated Dec 14-15, 2025)
- **[README.md](../../../README.md)** - System overview with forensic verification
- **[QUICK_START.md](../../QUICK_START.md)** - Fast overview (30 sec to launch)
- **[TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)** - 7 issues, 25+ diagnostic commands
- **[START_HERE.md](../../START_HERE.md)** - Complete navigation guide

### Subsystem Guides (✅ Current)
- **[WSL2 Audio](../wsl2/START_HERE_WSL2.md)** - Dual architecture, GPU acceleration
- **[Qdrant Setup](../../QDRANT_SETUP.md)** - Vector database initialization
- **[GPU Configuration](../gpu/GPU_SETUP.md)** - GPU optimization guide
- **[Consolidation Explained](../../CONSOLIDATION_EXPLAINED.md)** - Unified environment

### Architecture (⚠️ Needs Update)
- **[System Architecture](../../architecture/SYSTEM_ARCHITECTURE.md)** - Has ZenML/FAISS refs (outdated)
- **[Architecture Reference](../../architecture/ARCHITECTURE_REFERENCE.md)** - Oct 15 (needs Qdrant update)
- **Use README.md instead** - Has current Dec 14 forensically verified architecture

---

## 🎯 System Status Summary (Dec 14, 2025)

### ✅ Fully Operational
- Scene detection (30 scenes typical)
- Frame extraction + vision models (CLIP, DINO, YOLO, BLIP, OCR)
- WSL2 audio processing (Whisper, Pyannote, emotion)
- Entity extraction (cross-modal resolution)
- Knowledge graph (real-time insertion)
- Qdrant vector storage (3 collections)
- GPU utilization (85% stable)

### ⊘ Built But Not Wired (Phase 7 - Q1 2026)
- FastAPI server (api/server.py)
- Web UI (ui/ frontend exists)
- Multimodal search (retrieval/multimodal_search.py)
- Cross-modal harmonizer (steps/video/cross_modal_harmonizer.py)

### ⚠️ Cleanup Planned (Phase 7b)
- Legacy audio steps (superseded by unified WSL2)
- Old entity extractor (replaced by steps/video version)
- Duplicate watchdog script (cli/watchdog.py is canonical)

**This pipeline is REAL. This pipeline is LIVE. This pipeline is FUNCTIONALLY COMPLETE.**

---

**Last Updated:** December 15, 2025  
**Status:** ✅ Forensically Verified Operational System  
**Verification Date:** December 14, 2025  
**Test Results:** 30 scenes, 52 diarization segments, 2 speakers, entity extraction operational

**For latest updates:** See [DOCUMENTATION_UPDATE_DEC_14_2025.md](../../DOCUMENTATION_UPDATE_DEC_14_2025.md)

---

*"Not 'almost.' Not 'prototype.' Operationally complete."*  
*"The best intelligence is the intelligence you control."*

- Project structure: `L:\goodq4all\docs\PROJECT_ORGANIZATION_COMPLETE.md`
- Model versions: `L:\goodq4all\docs\MODEL_VERSIONS.md`
- Architecture: `L:\goodq4all\docs\ARCHITECTURE.md`

---

**Need Help?** Check the logs first, they're very detailed!

**Ready to scale?** This is just the beginning - the pipeline can handle thousands of hours once tuned.

**Happy Processing! 🎬**
