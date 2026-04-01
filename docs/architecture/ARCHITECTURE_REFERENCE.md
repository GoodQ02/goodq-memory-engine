# 🏗️ GoodQ4All Architecture Reference

**Last Updated:** April 1, 2026  
**Status:** ✅ Updated with epoch-scoped storage and stitching-era verification  
**Purpose:** Definitive reference for data structures, storage patterns, and operational architecture

> **Note:** This document reflects the current operational system. Qdrant is canonical, FAISS remains optional parity/fallback, and `goodq_core` is the orchestration/base environment while specialized step envs still back several image/audio/video workloads. The local API is an explicit helper surface, while the old browser UI/dashboard scaffold is experimental only. For full system narrative, see [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). For canonical ingest authority and engine cutover rules, see [INGEST_ORCHESTRATION_CONTRACT.md](INGEST_ORCHESTRATION_CONTRACT.md). For the identity formation ladder, see [IDENTITY_STITCHING_CONTRACT.md](IDENTITY_STITCHING_CONTRACT.md).

---

## Table of Contents
1. [Database Schema](#database-schema) - memory.db, knowledge_graph.db
2. [Qdrant Vector Storage](#qdrant-vector-storage) - Replaces FAISS
3. [Storage Conventions](#storage-conventions) - Paths, artifacts, WSL2
4. [Knowledge Graph Schema](#knowledge-graph-schema) - Entity relationships
5. [File System Layout](#file-system-layout) - Current verified paths
6. [Deprecated Components](#deprecated-components) - FAISS, legacy orchestration, old envs

---

## Database Schema (Live Runtime Summary)

### Primary Database: `memory.db`

**Location:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db` ✅ Verified  
**Purpose:** Scene bundles, temporal segments, embedding routing metadata, summaries, and memory commit observability

#### Core Tables

- `scenes`
- `segments`
- `embeddings`
- `links`
- `summaries`
- `memory_commit_events`

**Key Points:**
- Scene bundle registration remains owned by `cli/run_ingestion.py`
- Scene and segment rows are tied to epoch-scoped ingest artifacts
- Artifact references are anchored in the epoch processing tree
- Qdrant remains canonical for vector search; SQLite tracks routing identity and commit observability

### Secondary Database: `knowledge_graph.db`

**Location:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db` ✅ Verified  
**Purpose:** Entity relationships, media linkage, temporal events, and identity formation edges

#### Core Tables

- `nodes`
- `edges`
- `media_nodes`
- `node_media`
- `events`
- `event_nodes`

**Integration:**
- Real-time insertion via `lib/kg_realtime_integration.py`
- Cross-modal resolution from transcript + caption + OCR + objects
- Identity formation ladder documented in [IDENTITY_STITCHING_CONTRACT.md](IDENTITY_STITCHING_CONTRACT.md)

**Live Edge Types Include:**
- `voice_pattern_match`
- `identity_candidate`
- `identity_supported`
- `identity_evidence`

---

## Qdrant Vector Storage

**Replaces:** FAISS indices (deprecated Oct 2025)

### Connection Details
- **URL:** http://localhost:6333
- **Status:** ✅ Operational (Dec 14 verified)
- **Storage:** `${GOODQ_DATA_ROOT}/qdrant_storage/`

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

**2. Phase 6 image collections**
```python
{
    "name": "goodq_clip_epoch_<epoch> / goodq_dino_epoch_<epoch>",
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
**Models:** CLIP (512-d) and DINO (768-d) in separate epoch-scoped collections  
**Status:** Operational in Phase 6a

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
Invoke-WebRequest http://localhost:6333/health
```

**List Collections:**
```powershell
Invoke-WebRequest http://localhost:6333/collections
```

**Query Example (Python):**
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Search text embeddings
results = client.search(
    collection_name="goodq_text",
    query_vector=embed_text("person with dog"),
    limit=10
)

# Search CLIP scene embeddings
results = client.search(
    collection_name="goodq_clip_epoch_2025_12_22",
    query_vector=embed_image("image.jpg"),
    limit=10
)
```

---

## Storage Conventions

### Artifact Locations

**Scene Artifacts (Verified in stitching-era witnesses):**
```
<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\processing\<video_name>\
├── audio\
│   ├── scene_0000.wav
│   ├── scene_0001.wav
│   └── scene_00NN.wav
├── video\
│   ├── scene_0000.jpg
│   ├── scene_0001.jpg
│   └── scene_manifest.json
└── temporal_index.json
```

**Status:** The epoch processing tree is canonical. Older layouts may still exist for compatibility, but are not the current operator truth.

**WSL2 Audio Output:**
```
\\wsl.localhost\Ubuntu\home\<user>\goodq_audio\
├── output\
│   └── result.json
├── process_audio.py            # Direct unified worker
└── setup_cuda_env.sh
```

**Data Root:**
```
<GOODQ_DATA_ROOT>\GoodQ_Data\
├── import_inbox\               # Drop videos here
├── epochs\<epoch>\
│   ├── memory.db
│   ├── knowledge_graph.db
│   ├── output\
│   └── processing\
└── qdrant_storage\             # Vector storage
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

## File System Layout

```
<project_root>\                   # Project root
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
│   ├── process_audio.py        # Direct unified worker
│   ├── setup_cuda_env.sh
│   └── output\
├── vendor\                     # ✅ Vendored dependencies for bootstrap
│   ├── qdrant\                 # Qdrant Windows service binary
│   ├── huggingface_hub\        # Offline model downloads
│   ├── requests\               # HTTP client
│   ├── pyyaml\                 # Config parsing
│   └── ...                     # Supporting libs (tqdm, certifi, etc.)
├── api\                        # ✅ Explicit local API surface
├── ui\
│   └── justification_v1\      # ⊘ Experimental UI scaffold only
└── retrieval\                  # ⊘ Multimodal search (built, not wired)

<GOODQ_DATA_ROOT>\GoodQ_Data\            # ✅ Unified data root
├── import_inbox\               # ✅ Drop videos here
├── epochs\<epoch>\
│   ├── memory.db               # ✅ Scene bundles
│   ├── knowledge_graph.db      # ✅ Entity relationships
│   └── processing\<video>\     # ✅ Scene artifacts
└── qdrant_storage\             # ✅ Vector storage
```

**Legend:** ✅ Operational | ⊘ Latent (built, not wired) | ⚠️ Cleanup planned

---

## Deprecated Components

### ⚠️ No Longer Used (Dec 2025)

**FAISS Indices:**
- **Replaced by:** Qdrant vector database
- **Migration:** Complete (Oct 2025)
- **Old Location:** `<project_root>\data\faiss_indices\`
- **Note:** May still exist on disk but not actively used

**legacy orchestration Orchestration:**
- **Replaced by:** Direct invocation via `cli/run_ingestion.py`
- **Removal Date:** Nov 2025
- **Note:** References may exist in old docs

**Single-Env Consolidation Narrative:**
- **Historical phase:** Dec 2025 image/text consolidation work
- **Current truth:** `goodq_core` is the orchestration/base env, and the
  supported runtime still provisions a specialized step-env pack for active
  image, audio, text, and scene-detection workloads that retain dependency
  boundaries
- **See:** `docs/reference/indexes/ENVIRONMENT_INDEX.md`

**Old Data Paths:**
- **Deprecated:** `<project_root>\data\`, `<GOODQ_DATA_ROOT>\GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)\`
- **Current:** `<GOODQ_DATA_ROOT>\GoodQ_Data\` (unified root)

---

## Quick Reference

### Diagnostic Commands

**Check Databases:**
```powershell
Get-Item "<GOODQ_DATA_ROOT>\GoodQ_Data\*.db" | Select-Object Name, Length, LastWriteTime
```

**Check Qdrant:**
```powershell
Invoke-WebRequest http://localhost:6333/health
Invoke-WebRequest http://localhost:6333/collections
```

**Check Scene Artifacts:**
```powershell
Get-ChildItem "<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\*\processing" -Directory
Get-ChildItem "<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\*\processing\<video>\audio\" | Measure-Object
```

**Check WSL2 Audio:**
```powershell
wsl -d <distro> -- bash -lc 'test -f "$GOODQ_WSL_WORKSPACE/process_audio.py" && echo worker_ready'
wsl -d <distro> -- bash -lc 'ls -lah "$GOODQ_WSL_WORKSPACE/output"'
```

### Common Queries

**SQLite (memory.db):**
```sql
-- Count scenes
SELECT COUNT(*) FROM scenes;

-- Recent scenes
SELECT scene_id, modality, created_at
FROM embeddings
ORDER BY created_at DESC
LIMIT 10;
```

**SQLite (knowledge_graph.db):**
```sql
-- Node counts by type
SELECT node_type, COUNT(*)
FROM nodes
GROUP BY node_type;

-- Top recurring labels
SELECT label, occurrence_count
FROM nodes
ORDER BY occurrence_count DESC
LIMIT 10;
```

**Qdrant (HTTP API):**
```powershell
# Collection stats
Invoke-WebRequest http://localhost:6333/collections/goodq_text | ConvertFrom-Json
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
