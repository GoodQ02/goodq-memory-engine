# GoodQ4All System - Launch and Operations Guide

## ⚡ Quick Start

### Starting the System
```bash
# Windows - Double click or run:
L:\goodq4all\LAUNCH_GOODQ.bat

# Then select option 1 for complete system
```

### What Gets Launched
1. **API Server** - http://localhost:3000
2. **Watchdog** - Auto-ingestion from import_inbox
3. **Web UI** - Opens automatically in browser

## 🎯 Current System State

### ✅ What's Working
- ✓ Single unified launcher (LAUNCH_GOODQ.bat)
- ✓ Process conflict detection
- ✓ Scene detection with proper lengths (300 sec min)
- ✓ Full ingestion pipeline
- ✓ Database storage (SQLite + FAISS)
- ✓ Real-time UI with live command center logs
- ✓ Progress tracking
- ✓ LLM integration with LM Studio
- ✓ Automatic file deduplication
- ✓ Multi-environment orchestration

### 📊 Current Data
- **25 scenes** processed
- **3,168 segments** analyzed
- **69 embeddings** generated
- **6,462 knowledge graph links**
- **8 summaries** created

## 🔧 System Components

### 1. Master Launcher (`LAUNCH_GOODQ.bat`)
**Single source of truth for all system launches**

Options:
- `1` - Launch Complete System (API + Watchdog + UI)
- `2` - Launch API Server Only
- `3` - Launch Watchdog Only  
- `4` - View System Status
- `5` - Stop All Services
- `6` - Exit

**Features:**
- Detects running processes
- Prevents duplicate launches
- Clean shutdown capability
- Window titles for easy identification

### 2. API Server (`api_server.py`)
**Production-grade FastAPI server**

- Port: 3000
- Endpoints: `/api/*`
- WebSocket support for real-time updates
- Integrated LLM client
- Real data streams (no placeholders)

**Key Endpoints:**
```
GET  /api/status           - System status
GET  /api/scenes           - List all scenes
GET  /api/scene/{id}       - Scene details
GET  /api/entities         - Entity list
GET  /api/knowledge-graph  - Graph data
GET  /api/progress         - Current processing progress
GET  /api/command-center   - Live logs (last 50 lines)
POST /api/chat             - LLM chat interface
POST /api/command          - Execute commands
```

### 3. Watchdog (`scripts/watchdog_ingest.py`)
**Automatic file monitor and ingestion trigger**

- Monitors: `L:\goodq4all\import_inbox`
- Poll interval: 2 seconds
- Stability wait: 3 seconds
- Lock file prevents duplicates: `data/.watchdog.lock`

**Supported Formats:**
- Video: mp4, avi, mov, mkv, wmv, flv, webm, m4v
- Audio: mp3, wav, flac, m4a, aac, ogg, wma
- Image: jpg, jpeg, png, bmp, gif, tiff, webp
- Document: pdf, txt, md, doc, docx

### 4. Web UI (`index.html`)
**Modern, real-time interface**

**Pages:**
- 💬 Chat - Interactive LLM conversation
- 🎬 Scenes - Browse processed scenes
- 🧠 Knowledge Graph - Visualize relationships
- 📊 Analytics - Statistics and charts
- 🎛️ Command Center - Live pipeline logs
- ⚙️ Process Control - Start/stop services
- 📥 Ingestion Status - Current processing
- ⚡ Settings - System configuration

## 📁 Directory Structure

```
L:\goodq4all\
├── LAUNCH_GOODQ.bat              # ⭐ Main launcher
├── FULL_SYSTEM_TEST.bat          # System validation
├── VALIDATE_PYTHON_PATHS.bat     # Path verification
│
├── api_server.py                  # API server
├── index.html                     # Web UI
├── llm_client.py                  # LLM integration
│
├── import_inbox/                  # 📥 Drop videos here
├── data/
│   ├── memory.db                 # Scene & segment data
│   ├── knowledge_graph.db        # Relationships
│   ├── unified_goodq.db          # Consolidated database
│   ├── faiss_indices/            # Vector embeddings
│   │   ├── text.index
│   │   ├── clip.index
│   │   ├── dino.index
│   │   └── audio.index
│   ├── processing/               # Temp processing area
│   ├── processed/                # Completed files
│   └── failed/                   # Failed files
│
├── logs/
│   ├── watchdog.log              # Watchdog activity
│   ├── command_center.log        # Pipeline output
│   ├── progress.json             # Current progress
│   └── *.log                     # Agent logs
│
├── output/                        # Analysis results
├── scripts/                       # Pipeline scripts
│   └── watchdog_ingest.py
├── steps/                         # ZenML pipeline steps
├── pipelines/                     # ZenML pipeline definitions
├── envs/                          # Multi-environment configs
├── agents/                        # Agent configurations
├── docs/                          # Documentation
└── tests/                         # Test files
```

## 🚀 Usage Workflows

### Basic Video Processing
1. Run `LAUNCH_GOODQ.bat` → Option 1
2. Drop video in `import_inbox/`
3. Watchdog detects → Pipeline starts
4. Monitor at http://localhost:3000
5. Results appear in UI as processing completes

### Manual Processing (No Watchdog)
1. Run `LAUNCH_GOODQ.bat` → Option 2 (API only)
2. Open http://localhost:3000
3. Use UI to manually trigger ingestion
4. Monitor progress in real-time

### Status Checking
1. Run `LAUNCH_GOODQ.bat` → Option 4
2. Or visit http://localhost:3000/api/status
3. Or check logs in `logs/` directory

### Clean Shutdown
1. Run `LAUNCH_GOODQ.bat` → Option 5
2. Or close "GoodQ API Server" and "GoodQ Watchdog" windows
3. Or press Ctrl+C in each window

## 🔍 Troubleshooting

### "Watchdog already running" Error
**Cause:** Multiple instances attempted to start

**Fix:**
```bash
# Option A: Use launcher
LAUNCH_GOODQ.bat → Option 5 (Stop All)

# Option B: Manual cleanup
taskkill /FI "WINDOWTITLE eq GoodQ*" /F
del L:\goodq4all\data\.watchdog.lock
```

### "Process cannot access file" Error
**Cause:** File locked by another process (usually duplicate watchdog)

**Fix:** Stop all services and restart with single launcher

### API Not Responding
**Check:**
```bash
curl http://localhost:3000/api/status
```

**Fix:**
- Ensure API Server window is open
- Check no port conflicts on 3000
- Review api_server logs in console

### Videos Not Processing
**Checklist:**
1. ✓ Watchdog running? (Check window or use Option 4)
2. ✓ File in import_inbox?
3. ✓ Check `logs/watchdog.log` for errors
4. ✓ Sufficient disk space?
5. ✓ File format supported?

### Scene Detection Stalling
**Previous Issue:** Scenes were 2 seconds (too short)
**Solution:** Updated `min_scene_length` to 300 seconds in `config.yaml`

**Verify:**
```yaml
# config.yaml
visual_intel:
  scene_detection:
    min_scene_length: 300  # ← Should be 300, not 2
```

## 📊 Monitoring

### Real-Time UI
- **Command Center**: Live pipeline logs (auto-scrolls to bottom)
- **Ingestion Status**: Current file and progress percentage
- **Scenes Explorer**: Browse completed scenes
- **Analytics**: Database statistics and charts

### Log Files
```bash
# Watchdog activity
tail -f logs/watchdog.log

# Pipeline output
tail -f logs/command_center.log

# Current progress
cat logs/progress.json
```

### API Queries
```bash
# System status
curl http://localhost:3000/api/status | python -m json.tool

# Scene count
curl http://localhost:3000/api/scenes | python -m json.tool

# Progress
curl http://localhost:3000/api/progress | python -m json.tool
```

## 🔧 Configuration

### Scene Detection
`config.yaml` → `visual_intel.scene_detection`
- `min_scene_length`: 300 (5 minutes)
- `threshold`: 30.0

### Watchdog
`scripts/watchdog_ingest.py`
- `POLL_INTERVAL`: 2.0 seconds
- `STABILITY_WAIT`: 3.0 seconds
- `MAX_WORKERS`: 1

### API Server
`api_server.py`
- Port: 3000
- CORS: Enabled for all origins
- WebSocket: Enabled

### LLM Client
`.env.local`
```env
LLM_PROVIDER=lmstudio
LLM_API_BASE=http://localhost:1234/v1
LLM_MODEL=qwen/qwen3-vl-4b
```

## 🎯 Best Practices

### ✅ DO
- Use `LAUNCH_GOODQ.bat` for all launches
- Check status before starting (Option 4)
- Monitor logs during processing
- Stop cleanly (Option 5)
- Keep import_inbox clean (watchdog moves processed files)

### ❌ DON'T
- Don't run multiple launchers
- Don't manually start `api_server.py` or `watchdog_ingest.py`
- Don't edit files in `import_inbox` while processing
- Don't delete from `data/processing` while running
- Don't modify databases while pipeline active

## 🔄 Recent Changes

### November 2025 - v2.0
- ✅ Created single master launcher
- ✅ Added process conflict detection  
- ✅ Fixed scene detection (2s → 300s)
- ✅ Archived duplicate batch files
- ✅ Integrated all functionality
- ✅ Added comprehensive testing
- ✅ Updated documentation
- ✅ Fixed Python path issues
- ✅ Added real-time command center logs to UI
- ✅ Cleaned up project structure

### Files Archived
- `LAUNCH_GOODQ_PRODUCTION.bat` → Replaced by `LAUNCH_GOODQ.bat`
- `LAUNCH_GOODQ_SYSTEM.bat` → Replaced by `LAUNCH_GOODQ.bat`
- `ANALYTICS_LAUNCHER.bat` → Integrated into main launcher
- `TEST_PROGRESS_TRACKING.bat` → Replaced by `FULL_SYSTEM_TEST.bat`

Archived to: `L:\_ARCHIVE\old_launchers_[timestamp]`

## 📚 Documentation

- `docs/LAUNCH_SYSTEM_GUIDE.md` - Detailed launch guide
- `docs/PYTHON_PATH_CONFIGURATION.md` - Python path setup
- `docs/SCENE_ANALYSIS_REPORT.md` - Scene detection details
- `docs/agent-communications/` - Agent architecture
- `QUICK_START_GUIDE.md` - Quick reference
- `README.md` - This file

## 🆘 Support

### Getting Help
1. Check logs: `logs/watchdog.log`, `logs/command_center.log`
2. Run diagnostics: `FULL_SYSTEM_TEST.bat`
3. Check system status: `LAUNCH_GOODQ.bat` → Option 4
4. Review documentation in `docs/`

### Reporting Issues
Include:
- Error message
- Log files
- System status output
- Steps to reproduce

---

**Last Updated:** November 10, 2025
**Version:** 2.0
**Status:** Production Ready ✅
