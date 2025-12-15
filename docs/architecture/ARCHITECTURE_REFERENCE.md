# 🏗️ GoodQ4All Architecture Reference

**Last Updated:** December 15, 2025  
**Status:** ✅ Updated with Dec 14, 2025 Forensic Verification  
**Purpose:** Definitive reference for data structures, storage patterns, and operational architecture

> **Note:** This document reflects the current operational system. FAISS has been replaced by Qdrant. ZenML orchestration removed. Unified `goodq_core` environment now standard. For full system narrative, see [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md).

---

## Table of Contents
1. [Database Schema](#database-schema) - memory.db, knowledge_graph.db
2. [Qdrant Vector Storage](#qdrant-vector-storage) - Replaces FAISS
3. [Storage Conventions](#storage-conventions) - Paths, artifacts, WSL2
4. [Knowledge Graph Schema](#knowledge-graph-schema) - Entity relationships
5. [File System Layout](#file-system-layout) - Current verified paths
6. [Deprecated Components](#deprecated-components) - FAISS, ZenML, old envs

---

## Database Schema (Dec 14, 2025)

### Primary Database: `memory.db`

**Location:** `L:\_DATA\GoodQ_Data\memory.db` ✅ Verified  
**Purpose:** Scene bundles, metadata, processing state

#### Core Tables

**1. scene_bundles**
```sql
CREATE TABLE scene_bundles (
    scene_id TEXT PRIMARY KEY,          -- Unique scene identifier
    video_name TEXT,                    -- Source video filename
    scene_index INTEGER,                -- Scene number (0-29 typical)
    start_time REAL,                    -- Start timestamp in seconds
    end_time REAL,                      -- End timestamp in seconds
    duration REAL,                      -- Scene duration
    keyframe_path TEXT,                 -- logs/scene_ingest/<video>/video/scene_XXXX.jpg
    audio_path TEXT,                    -- logs/scene_ingest/<video>/audio/scene_XXXX.wav
    transcript TEXT,                    -- Whisper transcription
    caption TEXT,                       -- BLIP2 image caption
    ocr_text TEXT,                      -- Tesseract OCR output
    objects TEXT,                       -- JSON list of detected objects (YOLO)
    metadata_json TEXT,                 -- Extended metadata
    created_at TEXT,                    -- ISO timestamp
    processed BOOLEAN DEFAULT 0         -- Processing completion flag
);
```

**Key Points:**
- Registered via `register_scene_bundle()` in `cli/run_ingestion.py`
- Each scene (0-29) gets one bundle entry
- Artifact paths point to `logs/scene_ingest/`
- Status: ✅ Operational (Dec 14 verified)

**2. embeddings** (if still used)
```sql
CREATE TABLE embeddings (
    hash TEXT PRIMARY KEY,              -- Content fingerprint (SHA256)
    scene_id TEXT,                      -- Reference to scene_bundles
    modality TEXT,                      -- 'clip', 'dino', 'clap', 'text'
    embedding_type TEXT,                -- Model used (e.g., 'clip-vit-base')
    dimensions INTEGER,                 -- Vector dimensionality
    created_at TEXT                     -- ISO timestamp
);
```

**Note:** Embeddings primarily stored in Qdrant now, this may be legacy/backup.

---
);
```

**Purpose:** Knowledge graph edges, relationships between embeddings

**5. summaries**
```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_type TEXT,               -- Type of summary
    category TEXT,                   -- Category
    content TEXT,                    -- Summary text
    created_at TEXT                  -- ISO timestamp
);
```

**Purpose:** Generated summaries (currently unused)

---

### Secondary Database: `knowledge_graph.db`

**Location:** `L:\_DATA\GoodQ_Data\knowledge_graph.db` ✅ Verified  
**Purpose:** Entity relationships, cross-modal resolution

#### Core Tables

**1. entities**
```sql
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,         -- Unique entity identifier
    entity_type TEXT,                   -- 'person', 'place', 'organization'
    name TEXT,                          -- Canonical entity name
    confidence REAL,                    -- Extraction confidence (0-1)
    first_seen TEXT,                    -- ISO timestamp
    last_seen TEXT,                     -- ISO timestamp
    mention_count INTEGER DEFAULT 1,    -- Number of mentions
    metadata_json TEXT                  -- Extended attributes
);
```

**2. mentions**
```sql
CREATE TABLE mentions (
    mention_id TEXT PRIMARY KEY,        -- Unique mention identifier
    entity_id TEXT,                     -- Foreign key to entities
    scene_id TEXT,                      -- Scene where mentioned
    source TEXT,                        -- 'transcript', 'caption', 'ocr', 'objects'
    timestamp REAL,                     -- Scene timestamp
    context TEXT,                       -- Surrounding text/context
    created_at TEXT,                    -- ISO timestamp
    FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
);
```

**3. relationships**
```sql
CREATE TABLE relationships (
    relationship_id TEXT PRIMARY KEY,   -- Unique relationship identifier
    entity_a_id TEXT,                   -- First entity
    entity_b_id TEXT,                   -- Second entity
    relationship_type TEXT,             -- 'co-occurs', 'mentions', 'related'
    strength REAL,                      -- Relationship strength (0-1)
    first_seen TEXT,                    -- ISO timestamp
    scenes_json TEXT,                   -- JSON list of scene_ids
    FOREIGN KEY (entity_a_id) REFERENCES entities(entity_id),
    FOREIGN KEY (entity_b_id) REFERENCES entities(entity_id)
);
```

**Integration:**
- Real-time insertion via `lib/kg_realtime_integration.py:109`
- Entity extraction from `steps/video/entity_extractor.py:370`
- Cross-modal resolution: transcript + caption + OCR + objects
- Status: ✅ Operational (Dec 14 verified)

---

## Qdrant Vector Storage (Dec 14, 2025)

**Replaces:** FAISS indices (deprecated Oct 2025)

### Connection Details
- **URL:** http://localhost:36335
- **Status:** ✅ Operational (Dec 14 verified)
- **Storage:** `L:\_DATA\GoodQ_Data\qdrant\`

### Collections

**1. goodq_text**
```python
{
    "name": "goodq_text",
    "vectors": {
        "size": 384,                    # SBERT all-MiniLM-L6-v2
        "distance": "Cosine"
    },
    "payload_schema": {
        "scene_id": "keyword",
        "source": "keyword",            # 'transcript', 'ocr', 'caption'
        "text": "text",
        "timestamp": "float",
        "video_name": "keyword"
    }
}
```

**Sources:** Transcripts, OCR text, captions  
**Model:** sentence-transformers/all-MiniLM-L6-v2  
**Dimensions:** 384

**2. goodq_image**
```python
{
    "name": "goodq_image",
    "vectors": {
        "clip": {
            "size": 512,                # CLIP ViT-B/16
            "distance": "Cosine"
        },
        "dino": {
            "size": 768,                # DINOv2-base
            "distance": "Cosine"
        }
    },
    "payload_schema": {
        "scene_id": "keyword",
        "keyframe_path": "keyword",
        "caption": "text",
        "objects": "keyword[]",
        "timestamp": "float",
        "video_name": "keyword"
    }
}
```

**Sources:** Keyframe images  
**Models:** CLIP (512-d) + DINO (768-d) as named vectors  
**Status:** Multi-vector support for dual embeddings

**3. goodq_audio**
```python
{
    "name": "goodq_audio",
    "vectors": {
        "size": 512,                    # CLAP
        "distance": "Cosine"
    },
    "payload_schema": {
        "scene_id": "keyword",
        "audio_path": "keyword",
        "transcript": "text",
        "speaker": "keyword",
        "emotion": "keyword",
        "timestamp": "float",
        "video_name": "keyword"
    }
}
```

**Sources:** Scene audio clips  
**Model:** laion/clap-htsat-unfused  
**Dimensions:** 512

### Querying Qdrant

**Health Check:**
```powershell
Invoke-WebRequest http://localhost:36335/health
```

**List Collections:**
```powershell
Invoke-WebRequest http://localhost:36335/collections
```

**Query Example (Python):**
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:36335")

# Search text embeddings
results = client.search(
    collection_name="goodq_text",
    query_vector=embed_text("person with dog"),
    limit=10
)

# Search images with CLIP
results = client.search(
    collection_name="goodq_image",
    query_vector=embed_image("image.jpg"),
    using="clip",
    limit=10
)
```

---

## Storage Conventions (Dec 14, 2025)

### Artifact Locations

**Scene Artifacts (Verified Dec 14):**
```
logs\scene_ingest\<video_name>\
├── audio\
│   ├── scene_0000.wav
│   ├── scene_0001.wav
│   └── scene_0029.wav          # 30 scenes typical
└── video\
    ├── scene_0000.jpg
    ├── scene_0001.jpg
    └── scene_0029.jpg
```

**⚠️ Config Drift:** Config specifies `processing/` but actual location is `logs/scene_ingest/`  
**Status:** Documented, not a bug - artifacts reliably land in `logs/scene_ingest/`

**WSL2 Audio Output:**
```
\\wsl.localhost\Ubuntu\home\<user>\goodq_audio\
├── output\
│   └── result.json             # 38KB verified Dec 14
├── queue_in\                   # Service input
├── queue_out\                  # Service output
└── logs\
    └── audio_service.log       # Service daemon logs
```

**Data Root:**
```
L:\_DATA\GoodQ_Data\
├── import_inbox\               # Drop videos here
├── memory.db                   # Scene bundles
├── knowledge_graph.db          # Entity relationships
└── qdrant\                     # Vector storage
```

### File Naming Conventions

**Scene Files:**
- Pattern: `scene_XXXX.{wav,jpg}` where XXXX is zero-padded scene index
- Example: `scene_0000.wav`, `scene_0029.jpg`

**Video Names:**
- Source filename becomes video identifier
- Spaces preserved in artifact paths
- Hash used for DB lookups

---

## File System Layout (Dec 14, 2025 Verified)

```
L:\goodq4all\                   # Project root
├── cli\
│   ├── run_ingestion.py        # ✅ PRIMARY ENTRY POINT (1541 lines)
│   └── watchdog.py             # ✅ Canonical watchdog
├── steps\
│   ├── audio\                  # Legacy audio steps (⚠️ cleanup planned)
│   ├── video\
│   │   └── entity_extractor.py # ✅ Entity extraction (line 370)
│   ├── image\                  # Vision models
│   └── common\                 # Shared utilities
├── lib\
│   ├── kg_realtime_integration.py  # ✅ KG updates (line 109)
│   └── knowledge_graph.py      # Graph manager
├── wsl2_audio\                 # ✅ WSL2 audio stack
│   ├── audio_service.py        # Daemon (PID 177)
│   ├── process_audio.py        # Direct invocation
│   ├── queue_in\
│   ├── queue_out\
│   └── output\
├── vendor\                     # ✅ Vendored dependencies for bootstrap
│   ├── qdrant\                 # Qdrant Windows service binary
│   ├── huggingface_hub\        # Offline model downloads
│   ├── requests\               # HTTP client
│   ├── pyyaml\                 # Config parsing
│   └── ...                     # Supporting libs (tqdm, certifi, etc.)
├── api\                        # ⊘ FastAPI (scaffolded, not deployed)
├── ui\                         # ⊘ Web UI (frontend exists)
└── retrieval\                  # ⊘ Multimodal search (built, not wired)

L:\_DATA\GoodQ_Data\            # ✅ Unified data root
├── import_inbox\               # ✅ Drop videos here
├── memory.db                   # ✅ Scene bundles
├── knowledge_graph.db          # ✅ Entity relationships
└── qdrant\                     # ✅ Vector storage

logs\scene_ingest\              # ✅ Scene artifacts
└── <video_name>\
    ├── audio\                  # scene_XXXX.wav
    └── video\                  # scene_XXXX.jpg
```

**Legend:** ✅ Operational | ⊘ Latent (built, not wired) | ⚠️ Cleanup planned

---

## Deprecated Components

### ⚠️ No Longer Used (Dec 2025)

**FAISS Indices:**
- **Replaced by:** Qdrant vector database
- **Migration:** Complete (Oct 2025)
- **Old Location:** `L:\goodq4all\data\faiss_indices\`
- **Note:** May still exist on disk but not actively used

**ZenML Orchestration:**
- **Replaced by:** Direct invocation via `cli/run_ingestion.py`
- **Removal Date:** Nov 2025
- **Note:** References may exist in old docs

**Multiple Conda Environments:**
- **Replaced by:** Unified `goodq_core` environment
- **Old Envs:** goodq_image_caption, goodq_object_detect, goodq_ocr, goodq_audio_*
- **Consolidation Date:** Dec 2025
- **Savings:** ~30GB disk space

**Old Data Paths:**
- **Deprecated:** `L:\goodq4all\data\`, `L:\GoodQ_Data\`
- **Current:** `L:\_DATA\GoodQ_Data\` (unified root)

---

## Quick Reference

### Diagnostic Commands

**Check Databases:**
```powershell
Get-Item "L:\_DATA\GoodQ_Data\*.db" | Select-Object Name, Length, LastWriteTime
```

**Check Qdrant:**
```powershell
Invoke-WebRequest http://localhost:36335/health
Invoke-WebRequest http://localhost:36335/collections
```

**Check Scene Artifacts:**
```powershell
Get-ChildItem "logs\scene_ingest\" -Directory
Get-ChildItem "logs\scene_ingest\<video>\audio\" | Measure-Object
```

**Check WSL2 Audio:**
```powershell
wsl ps aux | grep audio_service                   # Should show PID 177
wsl tail -f ~/goodq_audio/logs/audio_service.log
```

### Common Queries

**SQLite (memory.db):**
```sql
-- Count scenes
SELECT COUNT(*) FROM scene_bundles;

-- Recent scenes
SELECT scene_id, video_name, created_at 
FROM scene_bundles 
ORDER BY created_at DESC 
LIMIT 10;
```

**SQLite (knowledge_graph.db):**
```sql
-- Entity counts by type
SELECT entity_type, COUNT(*) 
FROM entities 
GROUP BY entity_type;

-- Top mentioned entities
SELECT name, mention_count 
FROM entities 
ORDER BY mention_count DESC 
LIMIT 10;
```

**Qdrant (HTTP API):**
```powershell
# Collection stats
Invoke-WebRequest http://localhost:36335/collections/goodq_text | ConvertFrom-Json
```

---

## Related Documentation

**Core Documentation (✅ Updated Dec 14-15, 2025):**
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - System design, pipeline flow
- [README.md](../../README.md) - System overview with forensic verification
- [QUICK_START.md](../QUICK_START.md) - Fast launch guide
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - 7 issues, 25+ commands

**Subsystem Guides:**
- [Qdrant Setup](../guides/QDRANT_SETUP.md) - Vector database initialization
- [WSL2 Audio](../guides/wsl2/START_HERE_WSL2.md) - Dual architecture details
- [GPU Configuration](../guides/gpu/GPU_SETUP.md) - GPU optimization

---

**Last Updated:** December 15, 2025  
**Status:** ✅ Forensically Verified (Dec 14, 2025)  
**Architecture Version:** 2.0 (Qdrant, Unified Env, Dual Audio)

---

*"The architecture is the map. The code is the territory. Both must be true."*
