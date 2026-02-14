<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Core Library Components (`lib/`)

**Last Updated:** December 15, 2025  
**Status:** ✅ Production Ready  
**Purpose:** Shared utilities and infrastructure used across all pipeline steps

---

## Overview

The `lib/` directory contains the foundational components that power GoodQ4All's multimodal processing pipeline. These are production-grade, battle-tested modules handling knowledge graphs, LLM communication, entity resolution, logging, and memory management.

---

## Component Index

### 🧠 Knowledge Graph & Memory

| Component | Purpose | Status | Key Features |
|-----------|---------|--------|--------------|
| `knowledge_graph.py` | Single-video entity graph | ✅ Active | Nodes, edges, temporal events, co-occurrence |
| `unified_knowledge_graph.py` | Cross-video unified graph (Phase 8) | ✅ Active | Video registry, entity merging, timeline building |
| `kg_realtime_integration.py` | Real-time KG updates during ingestion | ✅ Active | Scene-by-scene entity extraction and insertion |
| `entity_resolver.py` | Cross-modal entity merging | ✅ Active | Fuzzy matching, confidence scoring, deduplication |
| `cross_video_entity_resolver.py` | Multi-video entity identity | ✅ Active | Face/voice embeddings, name matching, LLM disambiguation |
| `timeline_builder.py` | Chronological event ordering (Phase 8) | ✅ Active | Date extraction from filenames, temporal analysis |
| `graph_query.py` | High-level KG query interface | ✅ Active | Person search, scene context, concept tracking |

### 🗣️ LLM & Communication

| Component | Purpose | Status | Key Features |
|-----------|---------|--------|--------------|
| `llm_client.py` | Unified LLM interface | ✅ Active | vLLM primary, Ollama fallback, health monitoring, auto-recovery |

**LLM Client Architecture:**
- **Primary Backend:** vLLM (WSL2) on port 38005
- **Fallback Backend:** Ollama (WSL) on port 31434
- **Models Supported:** Llama 3.1 8B (primary), Qwen2.5-7B-Instruct (secondary)
- **Features:** Connection pooling, exponential backoff, automatic failover, comprehensive logging
- **VRAM Management:** 16GB RTX 4070 Ti SUPER shared with audio processing

### 🔧 Utilities & Infrastructure

| Component | Purpose | Status | Key Features |
|-----------|---------|--------|--------------|
| `goodq_logger.py` | Mission-themed logging system | ✅ Active | Q Branch branding, progress bars, mission symbols |
| `process_manager.py` | GPU & process monitoring | ✅ Active | nvidia-smi integration, real-time VRAM tracking |
| `ffmpeg_utils.py` | Audio/video extraction | ✅ Active | Media info, audio extraction, normalization |
| `mission_components.py` | Component name branding | ✅ Active | Maps pipeline steps to Q Branch terminology |

### 💾 Memory Management (`memory_management/`)

| Component | Purpose | Status | Key Features |
|-----------|---------|--------|--------------|
| `schema.py` | Canonical memory.db schema | ✅ Active | Embeddings, links, scenes, segments, summaries tables |
| `utils.py` | Backup and migration tools | ✅ Active | Timestamped backups, manifest generation |
| `diagnostics.py` | Memory health checks | ✅ Active | Integrity validation, orphan detection |
| `migrate.py` | Schema migration utilities | ✅ Active | Version management, safe upgrades |

---

## Detailed Component Documentation

### 1. Knowledge Graph System

#### `knowledge_graph.py`
**Single-Video Knowledge Graph**

```python
from lib.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph("<GOODQ_DATA_ROOT>/GoodQ_Data/knowledge_graph.db")

# Add entity
person_id = kg.add_entity("person", "John Doe", {"confidence": 0.95})

# Add relationship
kg.add_relationship(person_id, object_id, "holding", confidence=0.85)

# Link to media
kg.link_entity_to_media(person_id, scene_id, video_hash, timestamp, confidence=0.90)

# Query
appearances = kg.get_node_media(person_id)
```

**Schema:**
- **nodes**: entity storage (person, object, location, concept, event, emotion)
- **edges**: relationships (co-occurrence, semantic, temporal)
- **media_links**: connects entities to video scenes with timestamps
- **temporal_events**: time-based occurrences with participating entities

**Performance:**
- Indexed on `node_type`, `name`, `timestamp`
- Transaction batching for bulk inserts
- Optimized for graph traversal queries

---

#### `unified_knowledge_graph.py`
**Cross-Video Unified Graph (Phase 8)**

```python
from lib.unified_knowledge_graph import UnifiedKnowledgeGraph

ukg = UnifiedKnowledgeGraph("<GOODQ_DATA_ROOT>/GoodQ_Data/unified_knowledge_graph.db")

# Register video
ukg.register_video(video_hash, path="/path/to/video.mp4", year=1987, duration=300.0)

# Merge entities across videos
ukg.merge_entity_across_videos(
    entity_type="person",
    name="John Doe",
    occurrences=[...],
    resolution_strategy="face_embedding"
)

# Build timeline
timeline = ukg.build_timeline()
```

**Features:**
- **Video Registry**: Central index of all processed videos
- **Global Entities**: Deduplicated entities spanning multiple videos
- **Cross-Video Events**: Temporal events connecting multiple videos
- **Entity Clusters**: Grouped mentions of the same real-world entity

**Use Cases:**
- "Show me all videos where John appears"
- "When did we visit Disneyland?"
- "Track how my kids grew over the years"

---

#### `kg_realtime_integration.py`
**Real-Time Knowledge Graph Updates**

```python
from lib.kg_realtime_integration import update_kg_for_scene

# Called automatically during ingestion
result = update_kg_for_scene(
    scene_data={
        'transcript': '...',
        'caption': '...',
        'ocr_text': '...',
        'objects': [...]
    },
    scene_id="scene_0024",
    video_hash="abc123",
    timestamp=45.2,
    config=config
)
```

**Pipeline Integration:**
- Invoked per-scene in `cli/run_ingestion.py` (line ~1400)
- Extracts entities from all modalities (visual, audio, text)
- Resolves cross-modal duplicates
- Updates knowledge graph atomically

**Last Updated:** December 14, 2025 (entity extraction field fixes)

---

#### `entity_resolver.py`
**Cross-Modal Entity Deduplication**

```python
from lib.entity_resolver import EntityResolver, Entity

resolver = EntityResolver(confidence_threshold=0.7)

entities = [
    Entity("person", "John", 0.9, "visual", "scene_01", 10.0, {}),
    Entity("person", "john", 0.85, "audio", "scene_01", 10.2, {}),
]

merged = resolver.resolve_entities(entities)
# Returns: Single "John" entity with combined confidence
```

**Features:**
- **Fuzzy Matching**: Handles "John"/"john"/"JOHN" variations
- **Confidence Scoring**: Weighted merging based on source reliability
- **Temporal Proximity**: Entities close in time are more likely to merge
- **Type Enforcement**: Only merges same entity types

---

#### `cross_video_entity_resolver.py`
**Multi-Video Identity Resolution (Phase 8)**

```python
from lib.cross_video_entity_resolver import CrossVideoEntityResolver

resolver = CrossVideoEntityResolver(config)

merged = resolver.resolve_entities_across_videos(
    video_hashes=["video1_hash", "video2_hash"],
    individual_kg_paths={"video1_hash": "kg1.db", ...},
    unified_kg=unified_kg_instance
)
```

**Resolution Strategies:**
1. **Face Embeddings**: 512-dim vectors, cosine similarity > 0.85
2. **Voice Signatures**: Speaker embeddings, similarity > 0.80
3. **Name Matching**: Fuzzy string matching with edit distance
4. **LLM Disambiguation**: Uses vLLM when ambiguous

**Example:**
- Video 1987: "Dad" appears
- Video 1990: "John Doe" appears
- System merges via face embeddings → Same person

---

#### `timeline_builder.py`
**Chronological Timeline Construction (Phase 8)**

```python
from lib.timeline_builder import TimelineBuilder

builder = TimelineBuilder(config)

timeline = builder.build_timeline(
    video_registry=[...],
    unified_kg=unified_kg_instance
)
```

**Date Extraction:**
- Filename patterns: `1987_1988.mp4`, `1990_12_christmas.mp4`
- EXIF metadata (when available)
- LLM inference from transcript/captions

**Output:**
```json
{
  "earliest_date": "1987-01-01",
  "latest_date": "2025-12-15",
  "total_videos": 47,
  "life_events": [
    {"event": "Birthday Party", "date": "1990-06-15", "videos": ["vid_123"]}
  ]
}
```

---

#### `graph_query.py`
**High-Level Query Interface**

```python
from lib.graph_query import GraphQuery

query = GraphQuery("<GOODQ_DATA_ROOT>/GoodQ_Data/knowledge_graph.db")

# Find person
appearances = query.find_person_appearances("John Doe")

# Scene context
context = query.get_scene_context(scene_id="scene_0024")

# Related scenes
similar = query.find_related_scenes(scene_id="scene_0024", min_shared_entities=2)
```

**Query Types:**
- Person appearances across all media
- Scene context (all entities present)
- Related scenes (shared entities)
- Concept evolution over time
- Multi-criteria search (objects + emotions + time range)

---

### 2. LLM Client

#### `llm_client.py`
**Production LLM Interface with Failover**

```python
from lib.llm_client import LLMClient

client = LLMClient()

response = client.generate(
    prompt="Summarize this scene: ...",
    model="vllm",  # or "ollama"
    max_tokens=512,
    temperature=0.7
)
```

**Architecture:**

```
┌─────────────────────────────────────────┐
│         LLM Client (lib/llm_client.py)  │
├─────────────────────────────────────────┤
│  Health Monitoring │ Connection Pool    │
│  Auto-Failover     │ Request Caching    │
└──────────┬──────────────────────┬───────┘
           │                      │
           ▼                      ▼
  ┌─────────────────┐   ┌─────────────────┐
  │ vLLM (WSL2)     │   │ Ollama (WSL)    │
  │ Port: 38005     │   │ Port: 31434     │
  │ Llama 3.1 8B    │   │ Qwen 2.5 7B     │
  │ Primary         │   │ Fallback        │
  └─────────────────┘   └─────────────────┘
```

**Features:**
- **Automatic Failover**: vLLM down → Ollama seamlessly
- **Health Checks**: Periodic endpoint monitoring
- **Exponential Backoff**: Smart retry logic
- **Connection Pooling**: Reuses HTTP sessions
- **Comprehensive Logging**: Request/response tracking

**Configuration:**
```yaml
llm:
  primary:
    backend: vllm
    host: localhost
    port: 38005
    model: meta-llama/Llama-3.1-8B-Instruct
  fallback:
    backend: ollama
    host: localhost
    port: 31434
    model: qwen2.5:7b-instruct
```

**Performance:**
- **vLLM**: 40-60 tokens/sec, 16GB VRAM (shared with audio)
- **Ollama**: 20-30 tokens/sec, CPU fallback available

---

### 3. Utilities

#### `goodq_logger.py`
**Mission-Themed Logging System**

```python
from lib.goodq_logger import get_logger

logger = get_logger("video_ingest", log_file="logs/mission.log")

logger.info("Mission briefing: Processing video 1987_christmas.mp4")
logger.gadget("Loading Q Branch tech: YOLO v11")
logger.agent("007 deployed for recon")
logger.success("Mission accomplished!")
```

**Features:**
- **Q Branch Branding**: Mission symbols (007, [MISSION], [INTEL])
- **Color Coding**: Status-based terminal colors
- **Progress Bars**: tqdm integration with mission themes
- **Log Files**: Rotated daily, 30-day retention

**Log Levels:**
- `logger.agent()` - Agent activity (important operations)
- `logger.gadget()` - Q Branch tech (model loading, tools)
- `logger.classified()` - Sensitive operations
- `logger.success()` - Mission objectives completed

---

#### `process_manager.py`
**GPU & Process Monitoring**

```python
from lib.process_manager import GPUMonitor

monitor = GPUMonitor()
info = monitor.get_gpu_info()

# Returns:
{
  "gpu_id": 0,
  "name": "NVIDIA GeForce RTX 4070 Ti SUPER",
  "memory_used": 12288,  # MB
  "memory_total": 16384,  # MB
  "utilization_gpu": 85,  # %
  "utilization_memory": 75,  # %
  "temperature": 68,  # °C
  "power_draw": 220  # W
}
```

**Features:**
- **Real-Time Monitoring**: nvidia-smi integration
- **Process Tracking**: GPU process enumeration
- **VRAM Allocation**: Per-process memory usage
- **Health Checks**: Temperature/power alerts

**Use Cases:**
- Pre-flight checks before ingestion
- Load balancing between vLLM and audio
- Debugging OOM errors

---

#### `ffmpeg_utils.py`
**Audio/Video Processing Utilities**

```python
from lib.ffmpeg_utils import get_media_info, extract_audio

# Get video metadata
info = get_media_info("video.mp4")
# Returns: {duration: 300.5, fps: 29.97, width: 1920, height: 1080, ...}

# Extract audio segment
extract_audio(
    video_path="video.mp4",
    output_path="scene_0024.wav",
    start_time=45.0,
    duration=8.3
)
```

**Features:**
- **FFmpeg Detection**: Auto-finds in PATH or `<project_root>/tools/ffmpeg`
- **Metadata Extraction**: Duration, FPS, resolution, codecs
- **Audio Extraction**: Time-based clips with normalization
- **Format Conversion**: WAV output for audio processing

---

#### `mission_components.py`
**Component Branding Map**

```python
from lib.mission_components import MISSION_COMPONENTS

# Map internal names to Q Branch designations
brand_name = MISSION_COMPONENTS['face_embed']
# Returns: "Facial Recognition"

brand_name = MISSION_COMPONENTS['audio_transcribe']
# Returns: "Comms Decrypt"
```

**Purpose:** User-facing logging and UI display names

---

### 4. Memory Management

#### `memory_management/schema.py`
**Canonical Database Schema**

Defines the structure of `memory.db`:

**Tables:**
- `embeddings` - Vector metadata with FAISS IDs
- `links` - Parent-child relationships between scenes
- `scenes` - Scene boundaries and temporal data
- `segments` - Audio speaker segments
- `summaries` - LLM-generated scene summaries
- `videos` - Video file metadata

**Evidence:** Active since project inception, confirmed in all ingestion runs

---

#### `memory_management/utils.py`
**Backup & Migration Tools**

```python
from lib.memory_management.utils import create_memory_backup

backup_path = create_memory_backup(
    paths_config=config['paths'],
    backup_root_dir="<GOODQ_DATA_ROOT>/backups"
)
# Creates: <GOODQ_DATA_ROOT>/backups/memory_backup_20251215_043000/
```

**Backup Contents:**
- `memory.db` (SQLite database)
- FAISS indices (if configured)
- ID map databases
- Chroma directory (if used)
- `manifest.json` (inventory of backed up files)

---

#### `memory_management/diagnostics.py`
**Health Checks & Validation**

```python
from lib.memory_management.diagnostics import validate_memory_integrity

report = validate_memory_integrity(config)
```

**Checks:**
- Database connectivity
- Schema version compatibility
- Orphaned records detection
- Index health
- Storage quota warnings

---

#### `memory_management/migrate.py`
**Schema Migration System**

```python
from lib.memory_management.migrate import run_migrations

run_migrations(db_path="<GOODQ_DATA_ROOT>/GoodQ_Data/memory.db")
```

**Features:**
- Version tracking in `schema_version` table
- Idempotent migrations (safe to run multiple times)
- Rollback support for failed migrations
- Pre-migration backups

---

## Integration Points

### Where `lib/` Components Are Used

| Component | Primary Caller | Location in Code |
|-----------|---------------|------------------|
| `kg_realtime_integration.py` | Ingestion pipeline | `cli/run_ingestion.py:1400` |
| `llm_client.py` | Entity extraction, summarization | `steps/video/entity_extractor.py:200` |
| `goodq_logger.py` | All modules | Universal import |
| `process_manager.py` | Pre-flight checks | `cli/run_ingestion.py:120` |
| `ffmpeg_utils.py` | Audio extraction | `cli/run_ingestion.py:850` |
| `entity_resolver.py` | KG integration | `lib/kg_realtime_integration.py:50` |

---

## Maintenance Guidelines

### Adding a New Component

1. **Create module** in `lib/`
2. **Add docstring** with purpose and usage
3. **Write tests** in `tests/lib/test_<component>.py`
4. **Update this documentation**
5. **Add to `lib/__init__.py`** for easy imports

### Deprecating a Component

1. **Mark with `@deprecated` decorator**
2. **Add migration guide** in docstring
3. **Move to `archive/` after 2 major releases**

---

## Historical Notes

### Deprecated Components

**None currently** - All components are actively used.

### Legacy Locations

- Old entity extractor (`lib/entity_extractor.py`) superseded by `steps/video/entity_extractor.py` (Dec 2025)
- FAISS-based storage largely replaced by Qdrant (still supported for backcompat)

---

## Performance Benchmarks

**Knowledge Graph Insertion** (30 scenes, 1 video):
- Entity extraction: ~0.5s per scene
- KG insertion: ~0.2s per scene
- Total: ~21s for 30-scene video

**LLM Client** (vLLM):
- Cold start: ~3s (model already loaded in WSL2)
- Request latency: 50-80ms
- Token generation: 40-60 tokens/sec

**Memory Operations**:
- Scene lookup: <10ms
- Embedding search (Qdrant): 20-50ms
- Full video query: 100-200ms

---

## Troubleshooting

### LLM Connection Failures
```bash
# Check vLLM
curl http://localhost:38005/v1/models

# Check Ollama
curl http://localhost:31434/api/tags
```

### Knowledge Graph Locked
```python
# If "database is locked" error
from lib.knowledge_graph import KnowledgeGraph
kg = KnowledgeGraph("kg.db")
kg.conn.isolation_level = None  # Autocommit mode
```

### GPU Not Detected
```bash
# Verify nvidia-smi
nvidia-smi

# Check from Python
python -c "from lib.process_manager import GPUMonitor; print(GPUMonitor().get_gpu_info())"
```

---

## Future Enhancements

### Planned (Not Yet Implemented)

1. **Redis Caching Layer** - Speed up repeated queries
2. **Graph Analytics** - PageRank, community detection
3. **Entity Embeddings** - Graph Neural Network representations
4. **Incremental KG Updates** - Modify existing videos without full rebuild

---

## See Also

- [Knowledge Graph Implementation](./KNOWLEDGE_GRAPH_IMPLEMENTATION.md) - Deep dive into KG system
- [Memory Storage Architecture](../architecture/MEMORY_STORAGE.md) - Database schemas
- [LLM Client Guide](../guides/llm/LLM_CLIENT_GUIDE.md) - vLLM/Ollama configuration
- [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md) - Full pipeline overview

---

**For questions or contributions, see [CONTRIBUTING.md](../../CONTRIBUTING.md)**
