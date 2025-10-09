# 🚀 GoodQ Quick Start Guide
**Updated:** 2025-10-08  
**Status:** Production Ready ✅

---

## 🎬 Get Started in 3 Steps

### Step 1: Launch the System
Double-click the batch file or run from command line:
```batch
L:\GoodQ_4_All\LAUNCH_GOODQ.bat
```

**This automatically starts:**
- 🖥️ **Command Center Dashboard** - Live system monitoring
- 🌐 **API Server** - Running on http://localhost:8000
- 📚 **API Documentation** - Opens in your browser at http://localhost:8000/docs

**Three PowerShell windows will open:**
1. **Launcher Window** - Confirms startup (can be closed after launch)
2. **API Server** - Shows API activity and requests
3. **Command Center** - Real-time dashboard with metrics

---

### Step 2: Drop Files to Process

#### Option A: Automatic Watchdog (Recommended)
1. Start the watchdog service:
   ```batch
   L:\GoodQ_4_All\START_WATCHDOG.bat
   ```
2. Drop video files into: `L:\GoodQ_4_All\import_inbox\`
3. Files are automatically processed in queue
4. Processed files are renamed with `_INGESTED` suffix

#### Option B: Manual Ingestion
```bash
# Activate environment
conda activate goodq_zenml

# Process a single video
cd L:\GoodQ_4_All
python cli\run_ingestion.py --video "L:\GoodQ_4_All\import_inbox\your_video.mp4"
```

---

### Step 3: Monitor Progress

#### Watch the Command Center Dashboard
The Command Center shows real-time status:
- 🎮 **GPU Usage** - VRAM and temperature
- 💾 **Database Stats** - Scenes, embeddings, graph nodes
- 📊 **Processing Status** - Current step runs
- 🔍 **Recent Activity** - Latest processed scenes
- 🎯 **Memory Snapshots** - Quality and metadata

#### Check Processing Logs
```bash
# View live step execution
Get-Content L:\_DATA\GoodQ_Data\logs\step_runs.jsonl -Wait

# Check ingestion status
cd L:\GoodQ_4_All
conda run -n goodq_zenml python scripts\check_production_status.py
```

#### Monitor Watchdog (if using automatic mode)
```bash
# Check watchdog status
cd L:\GoodQ_4_All
pwsh scripts\watchdog_status.ps1

# View watchdog logs
Get-Content L:\GoodQ_4_All\logs\watchdog.log -Tail 50
```

---

## 📂 Where Everything Lives

### Project Code (Version Controlled)
```
L:\GoodQ_4_All\              ← Main project (GitHub synced)
├── api\                     ← FastAPI server
├── cli\                     ← Command-line tools
├── pipelines\               ← ZenML pipelines
├── steps\                   ← Processing steps
├── scripts\                 ← Utility scripts
├── docs\                    ← Documentation
├── import_inbox\            ← Drop files here for processing
└── *.bat                    ← Quick launchers
```

### Runtime Data (Not in Git)
```
L:\_DATA\GoodQ_Data\         ← All output and databases
├── databases\
│   ├── memory.db            ← Scene metadata & embeddings
│   └── knowledge_graph.db   ← Entity relationships
├── logs\
│   ├── step_runs.jsonl      ← Processing history
│   └── workspace\           ← Per-video processing logs
├── faiss\                   ← Vector search indexes
└── exports\                 ← Processed data exports

L:\_DATA\models\             ← AI model files (HuggingFace cache)
L:\_TOOLS\                   ← External tools (FFmpeg, etc.)
L:\_ARCHIVE\                 ← Legacy files & backups
```

---

## 🔧 Common Commands

### System Health Checks
```bash
# Full environment verification (run first!)
cd L:\GoodQ_4_All
pwsh scripts\verify_project_readiness.ps1

# Check current processing status
conda run -n goodq_zenml python scripts\check_production_status.py

# View Command Center dashboard
pwsh scripts\command_center.ps1
```

### Processing Operations
```bash
# Start automatic file monitoring
START_WATCHDOG.bat

# Process specific video with full logging
conda activate goodq_zenml
python cli\run_ingestion.py --video "path\to\video.mp4" --verbose

# Check what''s in the inbox
python cli\list_inbox.py

# Query the knowledge graph
python cli\graph_query.py --query "people wearing blue"
```

### Database & Retrieval
```bash
# Test retrieval system
python cli\retrieve.py --query "people laughing" --top 5

# View memory database
python cli\memory.py --list-scenes

# Export scene data
python cli\memory.py --export --output "export.json"
```

### Stop Services
```batch
# Stop all GoodQ services
L:\GoodQ_4_All\STOP_GOODQ.bat

# Or just close the PowerShell windows
```

---

## 🌐 API Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### Retrieve Similar Content
```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d ''{"query": "people playing outside", "top_k": 5}''
```

### Interactive API Documentation
Open in browser: http://localhost:8000/docs

---

## 🎯 Supported File Types

### Video (Automatic scene detection)
`.mp4` `.avi` `.mov` `.mkv` `.wmv` `.flv` `.webm` `.m4v`

### Audio (Transcription & analysis)
`.mp3` `.wav` `.flac` `.m4a` `.aac` `.ogg` `.wma`

### Images (OCR, captioning, object detection)
`.jpg` `.jpeg` `.png` `.bmp` `.gif` `.tiff` `.webp`

### Documents (Future support)
`.pdf` `.txt` `.md` `.doc` `.docx`

---

## 🔍 What Gets Extracted

For each video scene, GoodQ extracts:

### 🎬 Visual Data
- **Scene Detection** - Automatic boundary detection
- **Frame Extraction** - Key frames saved
- **Object Detection** - People, objects, locations
- **Face Embeddings** - Face recognition & clustering
- **Image Captions** - Natural language descriptions
- **OCR** - Text visible in frames

### �� Audio Data
- **Transcription** - Speech-to-text (Whisper)
- **Speaker Diarization** - Who spoke when
- **Emotion Analysis** - Vocal emotion detection
- **Music Detection** - Background music events
- **Audio Embeddings** - Semantic audio vectors

### 🧠 Semantic Data
- **Sentiment Analysis** - Emotional tone
- **Entity Extraction** - People, places, things
- **Relationship Mapping** - Knowledge graph connections
- **Tags & Categories** - Automatic tagging
- **Multimodal Embeddings** - Cross-modal search

### 📊 Metadata
- **Timestamps** - Frame-accurate timing
- **Quality Metrics** - Clarity, confidence scores
- **Technical Data** - Resolution, bitrate, codec
- **Processing History** - Full audit trail

---

## 🔄 Environment Isolation

GoodQ uses **strictly isolated** conda environments to prevent dependency conflicts:

- ✅ No shared user packages (`PYTHONNOUSERSITE=1`)
- ✅ No cache sharing (`PIP_NO_CACHE_DIR=1`)
- ✅ Isolated pip configs (`--isolated`)
- ✅ Exact version pinning (locked dependencies)
- ✅ Model version locking (HuggingFace revision hashes)

### Active Environments
- `goodq_zenml` - Main orchestration & ingestion
- `goodq_image` - Image processing (BLIP, YOLO, DinoV2)
- `goodq_text` - NLP & embeddings (transformers)
- `goodq_audio` - Audio processing (Whisper, CLAP)
- Plus 40+ specialized environments for specific models

---

## 📖 Full Documentation

### Essential Guides
- 📘 **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Command cheatsheet
- 🔧 **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues
- 🏗️ **[architecture/](architecture/)** - System design
- 🧠 **[knowledge_graph.md](knowledge_graph.md)** - Graph structure
- 👁️ **[WATCHDOG_GUIDE.md](WATCHDOG_GUIDE.md)** - Auto-processing setup

### Advanced Topics
- 🔐 **[MODEL_LOCKDOWN.md](MODEL_LOCKDOWN.md)** - Version pinning
- 🐙 **[GITHUB_SETUP_GUIDE.md](GITHUB_SETUP_GUIDE.md)** - Git workflow
- 🎯 **[AGENTS.md](AGENTS.md)** - AI agent instructions
- 📐 **[System-Blueprint.txt](System-Blueprint.txt)** - Complete architecture

---

## 🎓 Example Workflow: Processing a Home Movie

```bash
# 1. Start the system
LAUNCH_GOODQ.bat

# 2. Start automatic watchdog (in new window)
START_WATCHDOG.bat

# 3. Drop your video into import_inbox
#    Copy: family_vacation_1987.mp4 → L:\GoodQ_4_All\import_inbox\

# 4. Watch processing in Command Center
#    - Scenes detected
#    - Frames extracted  
#    - Objects detected
#    - Audio transcribed
#    - Embeddings created
#    - Graph updated

# 5. File renamed when complete
#    family_vacation_1987_INGESTED.mp4

# 6. Query your memories!
python cli\retrieve.py --query "kids playing at the beach"
python cli\graph_query.py --entity "beach"
```

**Processing Time Estimates:**
- 10 min video: ~5-15 minutes
- 1 hour video: ~30-60 minutes  
- 2 hour video: ~1-2 hours
- 8GB home movie: ~2-4 hours

*Depends on hardware (GPU), scene count, and audio length*

---

## ⚠️ Before First Run

### Run System Verification
```bash
cd L:\GoodQ_4_All
pwsh scripts\verify_project_readiness.ps1
```

**Should show:**
✅ All environments created  
✅ No dependency conflicts  
✅ All models accessible  
✅ Database initialized  
✅ FFmpeg available  

### Check GPU
```bash
nvidia-smi
```
Should show your GPU with available VRAM.

### Ensure Services Available
- 🤖 **LM Studio** - Running on localhost:1234 (for local LLM)
- 🦙 **Ollama** - Running on localhost:11434 (alternative LLM)
- ⚡ **FFmpeg** - Installed at L:\_TOOLS\ffmpeg\bin\

---

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
pwsh -Command "Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
```

### Environment Issues
```bash
# Rebuild environments
cd L:\GoodQ_4_All\envs
pwsh create_all_envs.ps1
```

### Database Locked
```bash
# Close all Python processes, then restart
# Check: tasklist | findstr python
```

### Watchdog Not Processing
```bash
# Check watchdog logs
Get-Content L:\GoodQ_4_All\logs\watchdog.log -Tail 50

# Restart watchdog
# Close existing window, run START_WATCHDOG.bat again
```

For more help, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**

---

## 🎯 Next Steps After Setup

1. ✅ **Run verification script** - Ensure everything is ready
2. 🎬 **Process a test video** - Use sample.mp4 in import_inbox
3. 🔍 **Explore the data** - Check Command Center & databases
4. 🧪 **Test retrieval** - Query for content semantically
5. 📊 **Review knowledge graph** - See entity relationships
6. 🚀 **Process real content** - Import your home movies!

---

## 💡 Pro Tips

- 📦 **Batch Processing**: Drop multiple files into import_inbox - watchdog queues them
- 🎯 **Monitor VRAM**: Keep an eye on GPU memory in Command Center
- 📝 **Check Logs**: If something seems stuck, check step_runs.jsonl
- 🔄 **Restart Fresh**: If errors accumulate, restart LAUNCH_GOODQ.bat
- 💾 **Backup Before Big Runs**: Copy L:\_DATA\GoodQ_Data\databases\ folder
- 🧹 **Clean Inbox**: Remove _INGESTED files periodically to save space

---

## 📞 Getting Help

1. Check **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** first
2. Review logs: `L:\_DATA\GoodQ_Data\logs\step_runs.jsonl`
3. Check Command Center dashboard for errors
4. Verify environment health: `verify_project_readiness.ps1`
5. Review API errors: Check API Server PowerShell window

---

**Repository:** https://github.com/JoesDomingo/GoodQ_4_All  
**License:** See LICENSE file  
**Status:** Production Ready ✅

---

*Last Updated: 2025-10-08*  
*Version: 1.0.0*
