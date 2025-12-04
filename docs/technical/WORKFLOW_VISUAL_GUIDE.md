# GoodQ Processing Flow - Visual Guide
Last Updated: 2025-10-08

═══════════════════════════════════════════════════════════════════════
                        SYSTEM STARTUP FLOW
═══════════════════════════════════════════════════════════════════════

┌─────────────────────┐
│  Double-Click       │
│ LAUNCH_GOODQ.bat    │
└──────────┬──────────┘
           │
           ├──────────────────────────────────────┐
           │                                      │
           ▼                                      ▼
    ┌─────────────┐                      ┌──────────────┐
    │  API Server │                      │   Command    │
    │  Port 8000  │                      │   Center     │
    │             │                      │  Dashboard   │
    │ FastAPI     │                      │              │
    │ /docs       │                      │ GPU Monitor  │
    │ /retrieve   │                      │ DB Stats     │
    │ /health     │                      │ Live Logs    │
    └─────────────┘                      └──────────────┘

═══════════════════════════════════════════════════════════════════════
                     FILE INGESTION FLOW
═══════════════════════════════════════════════════════════════════════

Option A: AUTOMATIC (Recommended)
────────────────────────────────────

┌─────────────────────┐
│  Double-Click       │
│ START_WATCHDOG.bat  │
└──────────┬──────────┘
           │
           ▼
    ┌─────────────┐
    │  Watchdog   │
    │  Service    │
    │  Running    │
    └──────┬──────┘
           │
           │  Monitors every 2 seconds
           │
           ▼
    ┌─────────────────────┐
    │  import_inbox/      │
    │                     │
    │  [Drop files here]  │
    │                     │
    │  - video.mp4        │
    │  - audio.mp3        │
    │  - photo.jpg        │
    └──────────┬──────────┘
               │
               │  File detected
               │
               ▼
        ┌──────────┐
        │ Queued   │
        └─────┬────┘
              │
              ▼
        ┌──────────────┐
        │ Processing   │
        │ (See below)  │
        └──────┬───────┘
               │
               ▼
        ┌──────────────────┐
        │  Rename file to  │
        │  *_INGESTED.mp4  │
        └──────────────────┘


Option B: MANUAL
────────────────

┌────────────────────────────────────┐
│  conda activate goodq_zenml        │
│  cd L:\goodq4all                 │
│  python cli\run_ingestion.py \    │
│    --video "path\to\video.mp4"     │
└────────────┬───────────────────────┘
             │
             ▼
      [Direct to Processing]

═══════════════════════════════════════════════════════════════════════
                    VIDEO PROCESSING PIPELINE
═══════════════════════════════════════════════════════════════════════

┌────────────────┐
│  Video File    │
│  (MP4/AVI/MKV) │
└───────┬────────┘
        │
        ▼
┌─────────────────────┐
│ 1. Scene Detection  │  ← Detect cuts/transitions
│    (PySceneDetect)  │
└──────────┬──────────┘
           │
           ├────────────────────────────┐
           │                            │
           ▼                            ▼
    ┌─────────────┐            ┌──────────────┐
    │ 2a. Frame   │            │ 2b. Audio    │
    │   Extract   │            │   Extract    │
    │             │            │              │
    │ Key frames  │            │ scene_*.wav  │
    │ scene_*.jpg │            │              │
    └──────┬──────┘            └──────┬───────┘
           │                          │
           ▼                          ▼
    ┌─────────────────────┐   ┌─────────────────────┐
    │ IMAGE PIPELINE      │   │ AUDIO PIPELINE      │
    │ ─────────────────── │   │ ─────────────────── │
    │ • OCR (text)        │   │ • Transcribe        │
    │ • Caption (BLIP)    │   │   (Whisper)         │
    │ • Objects (YOLO)    │   │ • Diarization       │
    │ • Faces (RetinaFace)│   │   (speakers)        │
    │ • Image Embeddings  │   │ • Music events      │
    │   - CLIP            │   │ • Emotion analysis  │
    │   - DinoV2          │   │ • Audio embeddings  │
    │ • Tags              │   │   (CLAP)            │
    └──────────┬──────────┘   └──────────┬──────────┘
               │                         │
               └──────────┬──────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ TEXT        │
                   │ PROCESSING  │
                   │ ──────────  │
                   │ • Sentiment │
                   │ • Entities  │
                   │ • Embeddings│
                   └──────┬──────┘
                          │
                          ▼
               ┌────────────────────┐
               │ 3. KNOWLEDGE GRAPH │
               │    INTEGRATION     │
               │ ────────────────── │
               │ • Entity nodes     │
               │ • Relationships    │
               │ • Temporal links   │
               │ • Co-occurrence    │
               └──────────┬─────────┘
                          │
                          ▼
               ┌────────────────────┐
               │ 4. MEMORY DATABASE │
               │ ────────────────── │
               │ • Scene metadata   │
               │ • Embeddings       │
               │ • Quality scores   │
               │ • Timestamps       │
               └──────────┬─────────┘
                          │
                          ▼
               ┌────────────────────┐
               │ 5. FAISS INDEXES   │
               │ ────────────────── │
               │ • Text vectors     │
               │ • Image vectors    │
               │ • Audio vectors    │
               │ • Face vectors     │
               └────────────────────┘

═══════════════════════════════════════════════════════════════════════
                        DATA STORAGE LAYOUT
═══════════════════════════════════════════════════════════════════════

L:\_DATA\GoodQ_Data\
│
├── databases/
│   ├── memory.db              ← SQLite: Scenes, metadata, embeddings
│   └── knowledge_graph.db     ← Neo4j-style: Entities & relationships
│
├── faiss/
│   ├── text_index.faiss       ← Text embedding search
│   ├── dino_index.faiss       ← Image embedding search
│   ├── clip_index.faiss       ← CLIP embedding search
│   └── audio_index.faiss      ← Audio embedding search
│
├── logs/
│   ├── step_runs.jsonl        ← Processing history (append-only)
│   └── workspace/
│       └── video_name_DATE/   ← Per-video processing logs
│           ├── frames/        ← Extracted key frames
│           ├── audio/         ← Extracted audio clips
│           └── metadata/      ← JSON results per step
│
└── exports/
    └── DATE_video_export.zip  ← User-exportable packages

═══════════════════════════════════════════════════════════════════════
                        RETRIEVAL FLOW
═══════════════════════════════════════════════════════════════════════

┌─────────────────────┐
│  User Query         │
│  "kids at beach"    │
└──────────┬──────────┘
           │
           ▼
    ┌─────────────┐
    │ Text        │
    │ Embedding   │
    │ (CLIP/BERT) │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────┐
    │ FAISS Search    │
    │ Multi-modal     │
    │ ─────────────── │
    │ • Text index    │
    │ • Image index   │
    │ • Audio index   │
    └──────┬──────────┘
           │
           ▼
    ┌─────────────────┐
    │ Knowledge Graph │
    │ Expansion       │
    │ ─────────────── │
    │ • Related ents  │
    │ • Context       │
    └──────┬──────────┘
           │
           ▼
    ┌─────────────────┐
    │ Re-rank Results │
    │ ─────────────── │
    │ • Relevance     │
    │ • Quality       │
    │ • Recency       │
    └──────┬──────────┘
           │
           ▼
    ┌─────────────────┐
    │ Return Scenes   │
    │ with metadata   │
    │ ─────────────── │
    │ • Thumbnail     │
    │ • Timestamp     │
    │ • Transcript    │
    │ • Confidence    │
    └─────────────────┘

═══════════════════════════════════════════════════════════════════════
                    MONITORING & DEBUGGING
═══════════════════════════════════════════════════════════════════════

Command Center Dashboard (Real-time)
────────────────────────────────────
┌─────────────────────────────────────┐
│ == GPU ==                           │
│ NVIDIA RTX 4070 Ti SUPER            │
│ Memory: 2190 MB / 16376 MB          │
│ Temperature: 45°C                   │
│                                     │
│ == Database ==                      │
│ Scenes: 47                          │
│ Embeddings: 245                     │
│ Graph Nodes: 138                    │
│                                     │
│ == Latest Processing ==             │
│ 14:23:45 video_scene_detect OK      │
│ 14:24:12 image_caption OK           │
│ 14:24:18 object_detect OK           │
│ 14:24:25 audio_transcribe OK        │
│                                     │
│ == Recent Scenes ==                 │
│ Scene 12.3-45.7s                    │
│   Tags: outdoor, people, smiling    │
│   Objects: person(3), tree(2)       │
│   Transcript: "Look at the camera!" │
└─────────────────────────────────────┘

Log Files (Detailed History)
────────────────────────────
📄 step_runs.jsonl
   Each line = one step execution
   Format: timestamp, step_name, duration, status, metadata

📄 watchdog.log
   File monitoring events
   Processing queue status

📄 workspace/VIDEO_NAME/metadata/*.json
   Detailed results per processing step

═══════════════════════════════════════════════════════════════════════
                    ENVIRONMENT ARCHITECTURE
═══════════════════════════════════════════════════════════════════════

Conda Base Environment
  │
  ├─► goodq_zenml ────► Main orchestration
  │                      - ZenML
  │                      - Typer CLI
  │                      - SQLite
  │                      - FastAPI
  │
  ├─► goodq_image ────► Image processing
  │                      - transformers (BLIP)
  │                      - torch
  │                      - ultralytics (YOLO)
  │                      - opencv
  │
  ├─► goodq_text ─────► NLP tasks
  │                      - transformers
  │                      - sentence-transformers
  │                      - spacy
  │
  ├─► goodq_audio ────► Audio processing
  │                      - openai-whisper
  │                      - pyannote.audio
  │                      - librosa
  │
  └─► [40+ specialized envs for specific models]

Each environment:
  ✓ Completely isolated
  ✓ No shared packages
  ✓ Pinned dependencies
  ✓ Locked model versions

═══════════════════════════════════════════════════════════════════════
                        KEY FILE PATHS
═══════════════════════════════════════════════════════════════════════

🚀 Launchers
   L:\goodq4all\LAUNCH_GOODQ.bat       - Start everything
   L:\goodq4all\START_WATCHDOG.bat     - Auto-processing
   L:\goodq4all\STOP_GOODQ.bat         - Stop services

📥 Input
   L:\goodq4all\import_inbox\          - Drop files here

🔧 Scripts
   L:\goodq4all\scripts\
      command_center.ps1                 - Dashboard
      verify_project_readiness.ps1       - Health check
      check_production_status.py         - Status report

💾 Databases
   L:\_DATA\GoodQ_Data\databases\
      memory.db                          - Main database
      knowledge_graph.db                 - Graph database

📊 Logs
   L:\_DATA\GoodQ_Data\logs\
      step_runs.jsonl                    - Processing log
      watchdog.log                       - File monitor log

═══════════════════════════════════════════════════════════════════════
                    TYPICAL PROCESSING TIMES
═══════════════════════════════════════════════════════════════════════

Hardware: NVIDIA RTX 4070 Ti SUPER (16GB VRAM)

Video Length │ Scenes │ Frames │ Processing Time │ Output Size
─────────────┼────────┼────────┼─────────────────┼─────────────
5 minutes    │  ~5-10 │  5-10  │  2-5 minutes    │  ~50 MB
30 minutes   │ ~20-40 │ 20-40  │ 10-20 minutes   │ ~200 MB
1 hour       │ ~40-80 │ 40-80  │ 30-60 minutes   │ ~500 MB
2 hours      │~80-160 │ 80-160 │  1-2 hours      │  ~1 GB
Home movie   │varies  │varies  │  2-4 hours      │  ~2 GB
(8GB file)

Factors affecting speed:
  • Number of scenes detected
  • Audio length and clarity
  • Number of objects/faces per frame
  • Transcript length
  • Available VRAM

═══════════════════════════════════════════════════════════════════════

For detailed steps, see QUICK_START.md
For troubleshooting, see docs/TROUBLESHOOTING.md
For API usage, see http://localhost:30000/docs

═══════════════════════════════════════════════════════════════════════
