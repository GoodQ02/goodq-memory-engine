# GoodQ4All Project Structure

Last Updated: 2025-11-12

## Directory Organization

```
goodq4all/
│
├── 📄 Core Files (Root Directory)
│   ├── INSTALL.bat              # Windows installer launcher
│   ├── INSTALL.md               # Installation guide
│   ├── LAUNCH_GOODQ.bat         # Main system launcher
│   ├── README.md                # Project overview
│   ├── LICENSE                  # License file
│   ├── config.yaml              # Main configuration
│   ├── .gitignore               # Git ignore rules
│   ├── .env.local               # Local environment variables (not in git)
│   ├── .env.local.template      # Environment template
│   ├── .env.agents              # Agent configurations
│   ├── .env.model_cache         # Model cache settings
│   │
│   ├── api_server.py            # FastAPI backend server
│   ├── index.html               # Main web interface
│   ├── analytics_dashboard.py   # Analytics engine
│   ├── analytics_engine.py      # Analytics processing
│   ├── analytics_cli.py         # Analytics CLI
│   └── analytics_query.py       # Analytics queries
│
├── 📁 agents/                   # AI Agent Definitions
│   ├── agent_definitions.py     # Agent classes and configurations
│   ├── agent_tools.py           # Agent tool implementations
│   └── coordinator.py           # Multi-agent coordinator
│
├── 📁 api/                      # API Components
│   ├── routes/                  # API route handlers
│   ├── models/                  # Pydantic models
│   └── middleware/              # API middleware
│
├── 📁 cli/                      # Command Line Interface
│   └── commands/                # CLI command implementations
│
├── 📁 common/                   # Shared Utilities
│   ├── constants.py             # Global constants
│   ├── exceptions.py            # Custom exceptions
│   └── utils.py                 # Utility functions
│
├── 📁 config/                   # Configuration Files
│   ├── config.yaml.backup_*     # Configuration backups
│   └── settings/                # Environment-specific settings
│
├── 📁 data/                     # Data Storage
│   ├── videos.db                # Main SQLite database
│   ├── processing/              # Temporary processing files
│   │   └── video_*/             # Per-video processing directories
│   ├── embeddings/              # FAISS index storage
│   │   ├── text_embeddings/
│   │   ├── clip_embeddings/
│   │   ├── dino_embeddings/
│   │   └── audio_embeddings/
│   ├── faces/                   # Face detection outputs
│   └── clips/                   # Video clip extractions
│
├── 📁 docs/                     # Documentation
│   ├── INSTALL.md               # Installation guide
│   ├── QUICK_START_GUIDE.md     # Quick start guide
│   ├── ARCHITECTURE.md          # System architecture
│   ├── GPU_QUICK_START.md       # GPU configuration
│   ├── SCENE_ANALYSIS_REPORT.md # Scene analysis documentation
│   ├── agent-communications/    # Agent communication logs
│   └── Phase Reports/           # Development phase documentation
│
├── 📁 envs/                     # Conda Environments
│   ├── goodq_zenml.yaml         # Main environment spec
│   ├── vision_env.yaml          # Vision processing environment
│   ├── audio_env.yaml           # Audio processing environment
│   └── graph_env.yaml           # Graph processing environment
│
├── 📁 import_inbox/             # Video Import Directory
│   └── (drop videos here for automatic processing)
│
├── 📁 logs/                     # Application Logs
│   ├── api_server.log           # API server logs
│   ├── watchdog.log             # Watchdog logs
│   ├── pipeline_*.log           # Pipeline execution logs
│   └── analytics.log            # Analytics logs
│
├── 📁 output/                   # Processed Outputs
│   ├── scenes/                  # Extracted scene data
│   ├── transcripts/             # Transcription outputs
│   ├── summaries/               # Generated summaries
│   └── knowledge_graphs/        # Knowledge graph exports
│
├── 📁 pipelines/                # ZenML Pipeline Definitions
│   ├── video_ingestion_pipeline.py      # Main ingestion pipeline
│   ├── scene_detection_pipeline.py      # Scene detection
│   ├── audio_processing_pipeline.py     # Audio processing
│   ├── vision_processing_pipeline.py    # Vision processing
│   └── knowledge_graph_pipeline.py      # Knowledge graph building
│
├── 📁 scripts/                  # Utility Scripts
│   ├── backup/                  # Backup files
│   ├── diagnostics/             # Diagnostic Tools
│   ├── setup/                   # Setup Scripts
│   └── utilities/               # Utility Scripts
│
├── 📁 smoke_inbox/              # Test Video Directory
│   └── sample.mp4               # Sample test video
│
├── 📁 steps/                    # ZenML Pipeline Steps
│   ├── video_scout.py           # Initial video analysis
│   ├── scene_detect.py          # Scene detection
│   ├── audio_extract.py         # Audio extraction
│   ├── audio_diarize.py         # Speaker diarization
│   ├── audio_transcribe.py      # Transcription
│   ├── frame_extract.py         # Frame extraction
│   ├── vision_analyze.py        # Vision analysis
│   ├── face_detect.py           # Face detection
│   ├── embed_*.py               # Various embedding steps
│   ├── entity_extract.py        # Entity extraction
│   ├── knowledge_graph.py       # Knowledge graph building
│   └── sentiment_analysis.py   # Sentiment analysis
│
├── 📁 tests/                    # Test Files
│   └── test_*.py                # Unit and integration tests
│
├── 📁 web/                      # Web Interface Components
│   ├── backup/                  # UI backups
│   ├── static/                  # Static assets
│   └── templates/               # HTML templates
│
└── 📁 zenml_store/              # ZenML Metadata Store
```

## Key Files and Their Purpose

### Core System Files

- **LAUNCH_GOODQ.bat**: Main entry point - starts API server, watchdog, and opens UI
- **api_server.py**: FastAPI backend serving the web interface and processing APIs
- **index.html**: Main web UI with chat, analytics, and visualization
- **config.yaml**: Central configuration for all system components

### Configuration Files

- **.env.local**: Local environment variables (paths, API keys, etc.)
- **.env.agents**: Agent-specific configuration
- **.env.model_cache**: Model caching settings
- **config.yaml**: Main YAML configuration

### Data Flow

1. **import_inbox/** → Videos dropped here are detected by watchdog
2. **data/processing/** → Temporary processing workspace
3. **data/videos.db** → SQLite database with all metadata
4. **data/embeddings/** → FAISS vector indices
5. **output/** → Final processed outputs

## Cleanup Guidelines

### Regular Maintenance

Run monthly:
```bash
python scripts/utilities/QUICK_CLEAN.py
```

This will:
- Archive old backups
- Clean temporary processing files
- Rotate logs
- Remove orphaned data
