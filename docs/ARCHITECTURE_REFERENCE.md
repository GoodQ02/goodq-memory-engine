# 🏗️ GoodQ4All Architecture Reference
**Last Updated:** 2025-10-15  
**Purpose:** Definitive reference for data structures, conventions, and storage patterns

---

## Table of Contents
1. [Database Schema](#database-schema)
2. [FAISS Index Architecture](#faiss-index-architecture)
3. [Embedding Storage Conventions](#embedding-storage-conventions)
4. [ID Map Architecture](#id-map-architecture)
5. [Knowledge Graph Schema](#knowledge-graph-schema)
6. [File System Layout](#file-system-layout)

---

## Database Schema

### Primary Database: `memory.db`

**Location:** `L:\goodq4all\data\memory.db`

#### Tables

**1. embeddings**
```sql
CREATE TABLE embeddings (
    hash TEXT PRIMARY KEY,          -- Content fingerprint (SHA256)
    faiss_id INTEGER,                -- ID in FAISS index (can be NULL)
    source_path TEXT,                -- Original file path
    modality TEXT,                   -- 'image', 'audio', 'frame_text', 'audio_transcript'
    scene_id TEXT,                   -- Optional reference to scenes table
    created_at TEXT,                 -- ISO timestamp
    sentiment_label TEXT,            -- Optional sentiment label
    sentiment_score REAL,            -- Optional sentiment score
    emotions_json TEXT               -- Optional JSON emotions data
);
```

**Key Points:**
- `hash` is SHA256 of content (stable across runs)
- `modality` groups embeddings by type (see conventions below)
- `faiss_id` links to vector in FAISS index
- Can have multiple embeddings for same source_path with different modalities

**2. scenes**
```sql
CREATE TABLE scenes (
    id TEXT PRIMARY KEY,             -- Scene hash
    video_hash TEXT,                 -- Parent video hash
    start REAL,                      -- Start time in seconds
    end REAL,                        -- End time in seconds
    meta TEXT,                       -- JSON metadata
    created_at TEXT                  -- ISO timestamp
);
```

**Meta JSON Structure:**
```json
{
  "index": 0,
  "duration": 2.0,
  "confidence": 0.5,
  "detection": {...},
  "caption": "a woman sitting at a table",
  "caption_meta": {...},
  "objects": [{...}],
  "keyframe": {...},
  "audio": {...},
  "diarization": [{...}],
  "transcript_meta": {...}
}
```

**3. segments**
```sql
CREATE TABLE segments (
    id TEXT PRIMARY KEY,             -- Segment hash
    video_hash TEXT,                 -- Parent video hash
    start REAL,                      -- Start time in seconds
    end REAL,                        -- End time in seconds
    speaker TEXT,                    -- Speaker ID (e.g., "SPEAKER_00")
    meta TEXT,                       -- JSON metadata
    created_at TEXT                  -- ISO timestamp
);
```

**Purpose:** Audio diarization segments (who spoke when)

**4. links**
```sql
CREATE TABLE links (
    parent_hash TEXT,                -- Source hash
    child_hash TEXT,                 -- Target hash
    relation TEXT,                   -- Relationship type
    timestamp REAL,                  -- When created
    meta TEXT,                       -- JSON metadata
    created_at TEXT                  -- ISO timestamp
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

## FAISS Index Architecture

### Index Locations

```
L:\goodq4all\data\faiss_indices\
├── text\
│   └── faiss_text.index          # Sentence embeddings
├── audio\
│   └── faiss_audio.index         # CLAP audio embeddings
├── clip\
│   └── (index location TBD)      # CLIP image embeddings
└── dino\
    └── faiss_dino.index          # DINO image embeddings
```

### Index Types

**1. Text Index** (`faiss_text.index`)
- **Model:** sentence-transformers/all-MiniLM-L6-v2
- **Dimensions:** 384
- **Index Type:** HNSW (Hierarchical Navigable Small World)
- **Sources:** OCR text, captions, transcripts

**2. Audio Index** (`faiss_audio.index`)
- **Model:** laion/clap-htsat-unfused
- **Dimensions:** 512
- **Index Type:** HNSW
- **Sources:** Audio clips from scenes

**3. DINO Index** (`faiss_dino.index`)
- **Model:** facebook/dinov2-base
- **Dimensions:** 768
- **Index Type:** HNSW
- **Sources:** Keyframe images

**4. CLIP Index** (location TBD)
- **Model:** openai/clip-vit-base-patch16
- **Dimensions:** 512
- **Expected:** May share DINO index or separate location
- **Investigation needed**

### FAISS ID Assignment

IDs are generated in two ways:

**Method 1: Content-Based (Stable)**
```python
# Generate stable ID from content hash
uid = np.array([int(hash[:16], 16) % (2**63 - 1)], dtype='int64')
index.add_with_ids(embedding, uid)
```

**Method 2: Sequential (Auto-increment)**
```python
# Let FAISS assign next ID
index.add(embedding)
faiss_id = index.ntotal - 1
```

---

## Embedding Storage Conventions

### Modality Types

**Critical Convention:** Modalities group embeddings by semantic type, NOT by model.

| Modality | Description | Models | Source |
|----------|-------------|---------|--------|
| `image` | Visual embeddings | CLIP, DINO | Keyframe images |
| `audio` | Audio embeddings | CLAP | Scene audio clips |
| `frame_text` | Text from frames | Sentence transformer | OCR text |
| `audio_transcript` | Speech text | Sentence transformer | Transcripts |

### IMPORTANT: DINO/CLIP Share `modality="image"`

**This is by design, not a bug!**

Both DINO and CLIP embeddings are stored with `modality="image"` because:
1. They represent the same semantic concept (visual content)
2. Can be queried together for image similarity
3. Different models provide complementary views of same content

**How to distinguish:**
- Check the FAISS index file used
- Check the ID map database (dino_id_map.sqlite vs clip_id_map.sqlite)
- Check metadata in `embeddings.meta` JSON field (if present)

**Example Query:**
```sql
-- All visual embeddings (both CLIP and DINO)
SELECT * FROM embeddings WHERE modality='image';

-- DINO embeddings specifically
SELECT e.* FROM embeddings e
JOIN dino_id_map_db.dino_id_map d ON e.hash = d.hash;
```

---

## ID Map Architecture

### Overview

ID maps provide bidirectional lookups between:
- Content hash (SHA256)
- FAISS ID (integer)
- Source path (file location)

### Storage: SQLite, Not JSON

**Location:** `L:\goodq4all\data\databases\`

```
databases\
├── clap_id_map.sqlite     # Audio (CLAP) ID map
├── dino_id_map.sqlite     # Image (DINO) ID map
└── (clip_id_map TBD)      # Image (CLIP) ID map (if separate)
```

**Schema:**
```sql
CREATE TABLE {model}_id_map (
    faiss_id INTEGER PRIMARY KEY,
    hash TEXT,
    source_path TEXT,
    created_at TEXT
);
```

**Example:**
```sql
-- Look up FAISS ID from hash
SELECT faiss_id FROM dino_id_map WHERE hash='abc123...';

-- Look up source file from FAISS ID
SELECT source_path FROM clap_id_map WHERE faiss_id=42;

-- Count total embeddings
SELECT COUNT(*) FROM dino_id_map;
```

### Why SQLite Instead of JSON?

1. **Fast lookups** - Indexed queries vs full file scan
2. **Concurrent access** - Multiple processes can read
3. **Atomic updates** - No corruption from partial writes
4. **Queryable** - Standard SQL instead of custom parsing
5. **Scalable** - Handles millions of entries efficiently

### ID Map Usage Pattern

```python
# Store embedding
hash = sha256(content)
faiss_id = index.ntotal
index.add(embedding)

# Record in ID map
conn = sqlite3.connect('databases/dino_id_map.sqlite')
conn.execute(
    "INSERT INTO dino_id_map (faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
    (faiss_id, hash, path, datetime.now().isoformat())
)

# Also store in main database
conn2 = sqlite3.connect('data/memory.db')
conn2.execute(
    "INSERT INTO embeddings (hash, faiss_id, source_path, modality) VALUES (?,?,?,?)",
    (hash, faiss_id, path, 'image')
)
```

**Note:** Data is stored in BOTH locations for redundancy and different access patterns.

---

## Knowledge Graph Schema

### Database: `knowledge_graph.db`

**Location:** `L:\goodq4all\data\knowledge_graph.db`

#### Tables

**1. nodes** - Entities extracted from content
```sql
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text TEXT,               -- Entity name/text
    entity_type TEXT,               -- PERSON, LOCATION, DATE, etc.
    confidence REAL,                -- Extraction confidence
    created_at TEXT
);
```

**2. edges** - Relationships between entities
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_node_id INTEGER,         -- Foreign key to nodes
    target_node_id INTEGER,         -- Foreign key to nodes
    relation_type TEXT,             -- Relationship type
    confidence REAL,
    created_at TEXT
);
```

**3. media_nodes** - Scenes/segments as graph nodes
```sql
CREATE TABLE media_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id TEXT,                  -- Reference to scenes table
    media_type TEXT,                -- 'scene', 'segment', etc.
    timestamp REAL,                 -- Time in video
    created_at TEXT
);
```

**4. node_media** - Links entities to media
```sql
CREATE TABLE node_media (
    node_id INTEGER,                -- Foreign key to nodes
    media_node_id INTEGER,          -- Foreign key to media_nodes
    created_at TEXT
);
```

**5. temporal_events** - Time-based events
```sql
CREATE TABLE temporal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,                -- Event type
    timestamp REAL,                 -- When it occurred
    scene_id TEXT,                  -- Reference to scene
    metadata TEXT,                  -- JSON additional data
    created_at TEXT
);
```

### Graph Query Patterns

**Find all entities in a scene:**
```sql
SELECT n.* FROM nodes n
JOIN node_media nm ON n.id = nm.node_id
JOIN media_nodes mn ON nm.media_node_id = mn.id
WHERE mn.scene_id = 'scene_hash';
```

**Find scenes mentioning an entity:**
```sql
SELECT mn.scene_id FROM media_nodes mn
JOIN node_media nm ON mn.id = nm.media_node_id
JOIN nodes n ON nm.node_id = n.id
WHERE n.entity_text = 'John';
```

**Find co-occurring entities:**
```sql
SELECT n1.entity_text, n2.entity_text, COUNT(*) as co_occurrences
FROM nodes n1
JOIN node_media nm1 ON n1.id = nm1.node_id
JOIN node_media nm2 ON nm1.media_node_id = nm2.media_node_id
JOIN nodes n2 ON nm2.node_id = n2.id
WHERE n1.id < n2.id
GROUP BY n1.id, n2.id
ORDER BY co_occurrences DESC;
```

---

## File System Layout

### Directory Structure

```
L:\goodq4all\
├── data\                          # All persistent data
│   ├── memory.db                  # Main database
│   ├── knowledge_graph.db         # Knowledge graph
│   ├── databases\                 # ID map SQLite files
│   │   ├── clap_id_map.sqlite
│   │   └── dino_id_map.sqlite
│   ├── faiss_indices\             # Vector indices
│   │   ├── text\
│   │   ├── audio\
│   │   ├── clip\
│   │   └── dino\
│   ├── processing\                # Temp processing area
│   ├── processed\                 # Completed videos
│   └── backups\                   # Database backups
├── logs\                          # All logging
│   ├── watchdog.log               # Main log
│   ├── step_runs.jsonl            # Step execution log
│   └── watchdog_YYYYMMDD_HHMMSS\  # Per-run workspaces
├── steps\                         # Processing steps
│   ├── audio_transcribe\
│   ├── image_caption\
│   ├── object_detect\
│   └── ...
├── import_inbox\                  # Drop videos here
└── config.yaml                    # Main configuration
```

### Workspace Pattern

Each processing run creates a workspace:

```
logs/watchdog_20251014_024332/
└── 1987_1988/                     # Video name (sanitized)
    ├── frames/                    # Extracted keyframes
    │   ├── scene_0000.jpg
    │   ├── scene_0001.jpg
    │   └── ...
    └── audio/                     # Extracted audio
        ├── scene_0000.wav
        ├── scene_0001.wav
        └── ...
```

**Cleanup:** Workspaces are kept for debugging but can be cleared.

---

## Data Flow Diagram

```
Video File (import_inbox/)
    ↓
[Scene Detection]
    ↓
├─→ Frames (workspace/frames/)
│     ↓
│   [Image Processing]
│     ├─→ Captions → memory.db
│     ├─→ Objects → memory.db
│     ├─→ OCR → memory.db
│     ├─→ CLIP → faiss_indices/clip/ + databases/clip_id_map.sqlite + memory.db
│     └─→ DINO → faiss_indices/dino/ + databases/dino_id_map.sqlite + memory.db
│
└─→ Audio (workspace/audio/)
      ↓
    [Audio Processing]
      ├─→ Diarization → segments table
      ├─→ Transcription → scenes.meta
      ├─→ Emotions → scenes.meta
      └─→ CLAP → faiss_indices/audio/ + databases/clap_id_map.sqlite + memory.db
            ↓
    [Knowledge Graph]
      └─→ Entities & Relations → knowledge_graph.db
```

---

## Configuration Conventions

### Tool Paths

External tools are configured explicitly in `config.yaml`:

```yaml
config:
  tools:
    whisper_cli: L:/Tools/whisper/whisper-cli.exe
    whisper_ggml_model: L:/Tools/whisper/ggml-large-v3.bin
    ffmpeg: L:/Tools/ffmpeg/bin/ffmpeg.exe
    tesseract: L:/Tools/tesseract/tesseract.exe
```

**Why explicit paths?**
- No ambiguity about which binary is used
- Portable across machines
- Auditable and verifiable
- No PATH pollution

### Model Paths

Models are cached at:
- **Hugging Face:** `L:/models/hub/`
- **Custom models:** `L:/models/{model_type}/`

Set via environment variables:
```bash
HF_HOME=L:/models
TORCH_HOME=L:/models
```

---

## Performance Characteristics

### Database Sizes (Typical)

| Database | Size per Hour | Notes |
|----------|---------------|-------|
| memory.db | ~10-50 KB | Metadata only, no embeddings |
| knowledge_graph.db | ~5-20 KB | Entities and relations |
| FAISS indices | ~1-5 MB | Actual vector data |
| ID map SQLite | ~100-500 KB | Lookup tables |
| Workspace files | ~1-2 MB | Temporary, can be cleared |

### Query Performance

| Operation | Time | Notes |
|-----------|------|-------|
| FAISS k-NN search (k=10) | ~10-50ms | HNSW index |
| SQLite scene lookup | ~1-5ms | Indexed |
| Knowledge graph query | ~10-100ms | Depends on complexity |
| Full text search | ~50-200ms | No full-text index yet |

---

## Best Practices

### 1. Content Hashing
Always use SHA256 for content fingerprints:
```python
import hashlib
hash = hashlib.sha256(content).hexdigest()
```

### 2. Modality Naming
Use semantic names, not model names:
- ✅ `modality='image'` for visual content
- ❌ `modality='dino'` or `modality='clip'`

### 3. ID Map Updates
Always update both memory.db and ID map SQLite:
```python
# Update ID map
conn1.execute("INSERT INTO dino_id_map ...")
# Update main database
conn2.execute("INSERT INTO embeddings ...")
```

### 4. FAISS Index Management
- Use HNSW for datasets > 10K vectors
- Set `efConstruction=200` for quality
- Set `efSearch=50` for balance
- Rebuild index if size doubles

### 5. Database Backups
Backup before major operations:
```bash
cp data/memory.db data/backups/memory_$(date +%Y%m%d).db
```

---

## Troubleshooting

### "DINO embeddings missing"
- Check `databases/dino_id_map.sqlite`
- Query with JOIN, not direct modality filter
- DINO uses `modality='image'`, not `modality='dino'`

### "FAISS index not found"
- Check index file exists in `data/faiss_indices/{type}/`
- Verify file is not 0 bytes
- Check index was written with `faiss.write_index()`

### "Duplicate entries"
- Content hash should be unique per modality
- Check if same file processed twice
- Use `INSERT OR REPLACE` for idempotency

---

## Future Enhancements

### Planned
- [ ] CLIP/DINO index consolidation
- [ ] Full-text search with FTS5
- [ ] Graph query language (Cypher-like)
- [ ] Index compression for storage
- [ ] Distributed index sharding

### Under Consideration
- [ ] PostgreSQL migration for scale
- [ ] Redis cache layer
- [ ] Time-series database for metrics
- [ ] Neo4j for knowledge graph

---

**Last Updated:** 2025-10-15  
**Maintainer:** GoodQ Development Team  
**Status:** Living Document (update as architecture evolves)
