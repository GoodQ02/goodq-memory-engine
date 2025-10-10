# GoodQ Project Structure

## 📁 Directory Organization

### L:\ Drive Layout

```
L:\
├── goodq4all\              # Main project (GitHub repo)
├── _DATA\                    # Runtime data (NOT in GitHub)
├── _ARCHIVE\                 # Legacy/deprecated files
├── models\                   # Pretrained model files
└── tools\                    # Standalone utilities
```

---

## 🎯 goodq4all\ (Project Root)

**Purpose**: Source code, configuration, and documentation (tracked in GitHub)

```
goodq4all\
├── api\                      # FastAPI REST server
│   ├── main.py              # API entry point
│   ├── server.py            # Server configuration
│   └── routes\              # API endpoints
│
├── configs\                  # Configuration files
│   ├── paths.py             # ⭐ Central path configuration
│   ├── models_pinned.json   # Locked model versions
│   └── datasets_pinned.json # Locked dataset versions
│
├── docs\                     # Documentation
│   ├── README.md            # Project overview
│   ├── AGENTS.md            # AI agent instructions
│   ├── PROJECT_STRUCTURE.md # This file
│   ├── HISTORY.md           # Development history
│   └── diagrams\            # Architecture diagrams
│
├── envs\                     # Conda environment definitions
│   ├── goodq_zenml.yml      # Main pipeline environment
│   ├── audio_emotion.yml    # Audio processing environment
│   └── [other_envs].yml     # Isolated step environments
│
├── pipelines\                # ZenML pipeline definitions
│   ├── ingest_multimodal.py # Main ingestion pipeline
│   └── goodq_chat.py        # Chat/retrieval pipeline
│
├── scripts\                  # Utility scripts
│   ├── system_readiness_check.py  # Verify system setup
│   ├── check_production_status.py # Monitor ingestion
│   ├── watchdog_ingest.py         # File watcher
│   ├── command_center.ps1         # Dashboard
│   └── [various_utilities].py/ps1
│
├── steps\                    # ZenML pipeline steps
│   ├── common\              # Shared utilities
│   │   ├── config_loader.py
│   │   ├── memory.py
│   │   └── memory_writer.py
│   ├── video_ingest\        # Video processing
│   ├── audio_transcribe\    # Audio processing
│   ├── image_caption\       # Image analysis
│   ├── sentiment\           # Sentiment analysis
│   ├── knowledge_graph\     # Graph construction
│   └── [other_steps]\       # Additional processing steps
│
├── import_inbox\            # 📥 Drop folder for new media
│   └── [user_drops_files_here]
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 💾 _DATA\GoodQ_Data\ (Runtime Data)

**Purpose**: All runtime data, outputs, and artifacts (NOT tracked in GitHub)

```
_DATA\GoodQ_Data\
├── databases\               # SQLite databases
│   ├── memory.db           # Scene metadata & embeddings
│   └── knowledge_graph.db  # Semantic relationships
│
├── cache\                   # Model & library caches
│   ├── huggingface\        # HF_HOME
│   └── torch\              # TORCH_HOME
│
├── faiss_indices\           # Vector search indices
│   ├── text\               # Text embeddings
│   ├── audio\              # Audio embeddings
│   ├── dino\               # Visual embeddings (DINOv2)
│   └── clip\               # Multimodal embeddings
│
├── processing\              # Active ingestion workspace
│   └── [video_name]\
│       ├── frames\         # Extracted keyframes
│       ├── audio\          # Audio segments
│       └── metadata\       # Processing metadata
│
├── completed\               # Finished ingestions
│   ├── 1987_1988_run1\     # Example: completed video
│   ├── st_thomas_lost_tapes\
│   └── [other_videos]\
│
├── exports\                 # Final output exports
│   └── [export_packages]\
│
└── logs\                    # Centralized logging
    ├── step_runs.jsonl     # Step execution log
    ├── watchdog.log        # File watcher log
    ├── pipeline.log        # Pipeline execution log
    └── overnight_monitor.jsonl
```

---

## 🗄️ _ARCHIVE\ (Legacy Files)

**Purpose**: Deprecated code and old test runs (for reference only)

```
_ARCHIVE\
├── old_tests\               # Legacy test folders
│   ├── dedupe_test\
│   ├── ingest_lite*\
│   └── [various_old_runs]\
│
└── deprecated_scripts\      # Old/unused scripts
```

---

## 🤖 models\ (Pretrained Models)

**Purpose**: Local copies of pretrained models for offline use

```
models\
├── whisper\
├── sentiment\
└── [other_models]\
```

---

## 🔧 tools\ (Standalone Utilities)

**Purpose**: External tools and utilities

```
tools\
└── [various_utilities]\
```

---

## 🔑 Key Design Principles

### 1. **Single Source of Truth**
- All paths defined in `goodq4all/configs/paths.py`
- Import and use centralized paths: `from configs.paths import DATABASE_DIR`

### 2. **Separation of Concerns**
- **Code** (goodq4all): Version controlled in GitHub
- **Data** (_DATA): Local only, not in GitHub
- **Archive** (_ARCHIVE): Historical reference only

### 3. **Environment Isolation**
- Each step has its own conda environment when needed
- Strict isolation flags prevent dependency bleed:
  - `PYTHONNOUSERSITE=1`
  - `PIP_NO_CACHE_DIR=1`
  - `--no-user --isolated --no-cache-dir`

### 4. **Data Flow**

```
import_inbox/           # User drops files here
     ↓
processing/            # Active processing
     ↓
databases/            # Metadata storage
faiss_indices/        # Vector storage
     ↓
completed/            # Archived results
     ↓
exports/              # Final outputs
```

### 5. **Logging Strategy**
- All logs in `_DATA/GoodQ_Data/logs/`
- JSONL format for structured logs
- Easy to parse and analyze
- Not buried in deep folder hierarchies

---

## 🚀 Quick Reference

### Find a Path
```python
from configs.paths import (
    MEMORY_DB,              # Database file
    PROCESSING_DIR,         # Active workspace
    IMPORT_INBOX,           # User drop folder
    LOGS_DIR,               # Centralized logs
    get_processing_dir('video_name')  # Video workspace
)
```

### Check System Status
```powershell
# Run readiness check
conda run -n goodq_zenml python scripts/system_readiness_check.py

# Check production status
conda run -n goodq_zenml python scripts/check_production_status.py

# View dashboard
.\scripts\command_center.ps1
```

### Start Services
```batch
LAUNCH_GOODQ.bat        # Start command center + API
START_WATCHDOG.bat      # Start file watcher
CHECK_WATCHDOG.bat      # Check watcher status
STOP_GOODQ.bat          # Stop all services
```

---

## 📊 Data Lifecycle

### Ingestion Workflow
1. User drops file in `import_inbox/`
2. Watchdog detects file
3. Processing begins in `processing/[video_name]/`
4. Metadata stored in `databases/memory.db`
5. Embeddings stored in `faiss_indices/`
6. Knowledge graph built in `databases/knowledge_graph.db`
7. Completed files moved to `completed/[video_name]/`
8. Exports created in `exports/`

### Log Tracking
- Real-time: `logs/step_runs.jsonl` (append-only)
- Watchdog: `logs/watchdog.log`
- Pipeline: `logs/pipeline.log`
- Monitoring: `logs/overnight_monitor.jsonl`

---

## 🔒 Locked Versions

### Package Versions
- Locked in `envs/[env_name].yml`
- Pinned with exact versions or hashes
- Verified by `system_readiness_check.py`

### Model Versions
- Defined in `configs/models_pinned.json`
- Includes revision hashes
- Prevents automatic updates

### Dataset Versions
- Defined in `configs/datasets_pinned.json`
- Includes commit hashes
- Ensures reproducibility

---

## 🆘 Troubleshooting

### Path Issues
- **Problem**: Script can't find files
- **Solution**: Check `configs/paths.py` and ensure `ensure_directories()` was called

### Import Errors
- **Problem**: Module not found
- **Solution**: Verify conda environment is activated and `PYTHONPATH` if needed

### Data Not Showing
- **Problem**: Dashboard shows no data
- **Solution**: Check `_DATA/GoodQ_Data/databases/` and `processing/` folders

### Logs Missing
- **Problem**: Can't find logs
- **Solution**: All logs now in `_DATA/GoodQ_Data/logs/` (not project root)

---

## 📈 Future Expansion

This structure is designed to grow:
- New steps: Add to `steps/`
- New pipelines: Add to `pipelines/`
- New models: Update `configs/models_pinned.json`
- New data types: Extend `processing/` structure

The modular design ensures each component can evolve independently while maintaining system coherence.
