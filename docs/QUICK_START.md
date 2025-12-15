# 🚀 GoodQ4All - Quick Start Card

**Last Updated:** December 14, 2025  
**Status:** ✅ FULLY OPERATIONAL  

> **Role:** High-speed launch card for operators. This reflects the verified operational pipeline as of December 14, 2025. For full setup details, see `docs/guides/general/QUICK_START_CLEAN.md`.

## Launch System (30 seconds)

```batch
1. Double-click: LAUNCH_GOODQ.bat
2. Select: 1 (Launch Complete System)
3. Wait: ~10 seconds for services to start
4. Verify: Services running (see below)
```

**What It Does:**
- ✅ Validates all dependencies & models (auto-healing)
- ✅ Checks API keys (OpenAI, HuggingFace)
- ✅ Starts Qdrant vector database service (port 36335)
- ✅ Launches watchdog on `L:\_DATA\GoodQ_Data\import_inbox`
- ✅ Opens monitoring dashboard with live progress

---

## Verify It's Working (60 seconds)

✅ **Command Window Shows:**
```
[INFO] System health check passed
[INFO] Qdrant service started on port 36335
[INFO] Watchdog monitoring: L:\_DATA\GoodQ_Data\import_inbox
[INFO] Processing pipeline ready
```

✅ **Drop a Video File:**
1. Copy video to: `L:\_DATA\GoodQ_Data\import_inbox\`
2. Watch logs for:
```
[INFO] New file detected: video.mp4
[INFO] Starting scene detection...
[INFO] Scene 1/30 detected (verified operational)
[INFO] Processing audio with WSL2 (GPU-accelerated)
[INFO] Entity extraction active
[INFO] Knowledge graph updated
```

✅ **Verified Components (Dec 14, 2025):**
- Scene detection: 30 scenes processed
- Audio transcription: Whisper large-v3 (GPU)
- Speaker diarization: 52 segments, 2 speakers confirmed
- Entity extraction: Cross-modal resolution active
- Knowledge graph: Real-time insertion operational
- GPU utilization: 85% (RTX 4070 Ti SUPER, 16GB)

---

## Monitor Progress (ongoing)

### **Live Processing Status**
Watch command window for real-time updates:
```
[SCENE] Scene 12/30 - Duration: 45.2s
[VISION] CLIP embeddings generated (512-dim)
[AUDIO] Transcription complete (38KB output)
[AUDIO] Diarization: 52 segments, 2 speakers
[ENTITY] Cross-modal extraction: 15 entities found
[KG] Knowledge graph updated
[GPU] Utilization: 85% (RTX 4070 Ti SUPER)
```

### **What Gets Extracted**
**From Video (Per Scene):**
- ✅ Keyframe extraction
- ✅ Image captioning (BLIP2)
- ✅ Object detection (YOLOv8)
- ✅ Face recognition
- ✅ OCR text (Tesseract)
- ✅ Visual embeddings (CLIP + DINOv2)

**From Audio (WSL2 GPU-Accelerated):**
- ✅ Speech transcription (Whisper large-v3)
- ✅ Speaker diarization (Pyannote 3.1)
- ✅ Emotion classification (Wav2Vec2, 8-class)
- ✅ Audio embeddings (768-dimensional)

**Multimodal Intelligence:**
- ✅ Entity extraction (cross-modal)
- ✅ Knowledge graph building
- ✅ Scene bundle registration
- ✅ Qdrant vector storage

---

## Expected Timeline (Dec 14, 2025 Verified)

| Time | What's Happening | GPU Activity |
|------|------------------|--------------|
| **0-2min** | Scene Detection starting | Low (CPU-bound) |
| **2-20min** | Scene Detection (30 scenes avg) | Moderate |
| **20-40min** | Per-scene processing (vision + audio) | High (85% util) |
| **40-60min** | Entity extraction + Knowledge graph | Moderate |
| **60min+** | Vector embedding + Qdrant storage | High |

**Performance Notes:**
- Scene-first architecture (30 scenes typical for 1hr video)
- GPU-accelerated audio (WSL2, CUDA 12.8)
- Dual audio architecture (queue-based + direct)
- Entity extraction with cross-modal resolution
- Real-time knowledge graph updates

**Total: ~1-2 hours for 1-hour video** (RTX 4070 Ti SUPER)

---

## GPU Activity Check

### **Via Command Line:**
```powershell
# Check GPU utilization
nvidia-smi

# Expected output:
# python.exe using 12-14GB VRAM (RTX 4070 Ti SUPER)
# GPU-Util: 85% (verified Dec 14, 2025)
# CUDA Version: 12.8
```

### **What's Using GPU:**
- Windows (goodq_core): Vision pipeline (CLIP, DINO, YOLO, face embeddings)
- WSL2 (audio service): Whisper large-v3 + Pyannote 3.1 + Emotion classification
- Concurrent processing: 85% utilization confirmed stable

---

## Stop System

### **Method 1: Launcher Menu**
```
1. Run LAUNCH_GOODQ.bat again
2. Select: 5 (Stop All Services)
```

### **Method 2: Close Windows**
- Close "GoodQ API Server" window
- Close "GoodQ Watchdog" window

### **Method 3: Force Kill**
```powershell
Stop-Process -Name python -Force
```

---

## After Processing Completes

✅ **Check Results:**

1. **Memory Database** → `L:\_DATA\GoodQ_Data\memory.db` (scene bundles, metadata)
2. **Knowledge Graph** → `L:\_DATA\GoodQ_Data\knowledge_graph.db` (entity relationships)
3. **Qdrant Vectors** → http://localhost:36335 (goodq_text, goodq_image, goodq_audio)
4. **Scene Artifacts** → `logs/scene_ingest/<video>/` (audio chunks + keyframes)
5. **WSL2 Output** → `\\wsl.localhost\Ubuntu\home\<user>\goodq_audio\output\result.json`

✅ **What's Stored:**
```
L:\_DATA\GoodQ_Data/
  ├── memory.db              # Scene metadata (30 scenes from test video)
  ├── knowledge_graph.db     # Entities + relationships  
  ├── import_inbox/          # Drop videos here
  └── qdrant/                # Vector database storage

logs/scene_ingest/<video>/
  ├── audio/                 # scene_0000.wav to scene_0029.wav
  └── video/                 # scene_0000.jpg to scene_0029.jpg
```

---

## Common Issues

### ❌ "Nothing happens"
**Fix:** Check command window for errors. Should see:
```
[INFO] System health check passed
[INFO] Qdrant service started on port 36335
[INFO] Watchdog monitoring active
```

### ❌ "GPU not showing activity"
**Fix:** This is normal until processing starts. Once scene detection begins, run `nvidia-smi` to verify GPU usage.

### ❌ "Video not detected"
**Fix:** Verify video is in: `L:\_DATA\GoodQ_Data\import_inbox\`  
Check watchdog logs for detection messages.

### ❌ "Processing stuck"
**Fix:**
1. Check `logs/scene_ingest/<video>/` for partial output
2. Review command window for errors
3. Verify WSL2 audio service is running: `wsl ps aux | grep python`
4. Check GPU memory: `nvidia-smi` (should show 12-14GB used)

### ❌ "WSL2 audio errors"
**Fix:**
```bash
# In WSL2, check audio service
ps aux | grep audio_service

# Should show PID (e.g., 177) running
# If not, restart service
cd ~/goodq_audio
python audio_service.py
```

---

## Pro Tips

💡 **First run takes longer** (model loading, ~5-10 min initial setup)  
💡 **Subsequent videos process faster** (models cached in GPU memory)  
💡 **GPU indicators show 85% when active** (RTX 4070 Ti SUPER verified)  
💡 **WSL2 audio service preloads models** (faster per-scene processing)  
💡 **Scene-first architecture** (30 scenes typical = parallel processing friendly)  
💡 **Entity extraction runs per-scene** (cross-modal resolution with transcript + caption + OCR + objects)  
💡 **Knowledge graph updates in real-time** (check `knowledge_graph.db` growth)  
💡 **Qdrant stores all embeddings** (text, image, audio in separate collections)

---

## Key Locations

| Location | Purpose | Verified Status |
|----------|---------|-----------------|
| `L:\_DATA\GoodQ_Data\import_inbox\` | Drop videos here | ✅ Active |
| `L:\_DATA\GoodQ_Data\memory.db` | Scene metadata | ✅ Operational |
| `L:\_DATA\GoodQ_Data\knowledge_graph.db` | Entity relationships | ✅ Operational |
| `http://localhost:36335` | Qdrant vector DB | ✅ Port verified |
| `logs/scene_ingest/<video>/` | Scene artifacts | ✅ Confirmed live |
| `\\wsl.localhost\Ubuntu\home\<user>\goodq_audio\` | WSL2 audio stack | ✅ PID 177 running |

---

## Files To Watch

| File | What It Shows | Updated When |
|------|---------------|--------------|
| `logs/scene_ingest/<video>/audio/*.wav` | Per-scene audio chunks | During audio extraction |
| `logs/scene_ingest/<video>/video/*.jpg` | Per-scene keyframes | During frame extraction |
| `L:\_DATA\GoodQ_Data\memory.db` | Scene bundle count growing | After each scene |
| `L:\_DATA\GoodQ_Data\knowledge_graph.db` | Entity count growing | After entity extraction |
| `\\wsl.localhost\Ubuntu\...\output\result.json` | Latest WSL2 audio output | After each scene audio processing |

---

## Need Help?

1. Check `LAUNCH_INSTRUCTIONS.md` for detailed guide
2. Check `AUDIT_COMPLETE.md` for system status
3. Check Command Center tab for live logs
4. Ask in Chat: "What's the current status?"

---

**Status: ✅ READY TO LAUNCH**

Run `LAUNCH_GOODQ.bat` and select option 1!

🎬 Your home movies → 🧠 Intelligent memory system
