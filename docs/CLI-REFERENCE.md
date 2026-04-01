<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-01 -->

# GoodQ CLI Reference

**Last Updated:** April 1, 2026  
**Status:** Runtime-conditional (verify with current run artifacts and health checks)

Complete command-line interface reference for GoodQ multimodal processing system.

---

## Table of Contents

1. [Core Processing Commands](#core-processing-commands)
2. [Monitoring & Status](#monitoring--status)
3. [Query & Retrieval](#query--retrieval)
4. [Memory Management](#memory-management)
5. [Utilities](#utilities)

---

## Core Processing Commands

### `run_ingestion` - Main Video Processing Pipeline

**Purpose:** Process video files through the complete multimodal pipeline.

**Usage:**
```bash
python -m cli.run_ingestion --input-dir <path> [OPTIONS]
```

**Key Options:**
- `--input-dir`: Path to directory containing video files
- `--output`: Path to write run-level JSON results (default: resolved epoch output directory + `scene_ingest_results.json`)
- `--workspace`: Workspace directory for config snapshots and auxiliary run artifacts (default: resolved processing root + `_workspace/scene_ingest`)
- `--max-videos`: Maximum number of videos to process (`0` = all)
- `--max-scenes`: Maximum number of scenes per video (`0` = all)
- `--scene-threshold`: Override scene detection threshold
- `--min-scene-seconds`: Override minimum scene length
- `--force` / `--force-reprocess`: Reprocess even if already completed
- `--verbose`: Emit per-step progress messages
- `--step-timeout`: Abort a step if it exceeds N seconds

**What It Does:**
1. **Scene Detection** - Splits video into semantic scenes (PySceneDetect)
2. **Per-Scene Processing:**
   - **Visual:** Keyframe extraction, OCR, object detection (YOLO), captioning (BLIP), face embedding, DINO/CLIP embeddings, tagging
   - **Audio:** Transcription (Whisper large-v3), diarization (Pyannote 3.1), emotion detection, CLAP embeddings
   - **Entities:** Cross-modal entity extraction and resolution
   - **Memory:** Knowledge graph updates, scene bundle registration, vector storage
3. **Artifact Generation:**
   - Keyframes: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video>/video/scene_XXXX.jpg`
   - Audio chunks: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video>/audio/scene_XXXX.wav`
   - Metadata: epoch-scoped SQLite + Qdrant vectors

**Example:**
```bash
# Process all videos in inbox
python -m cli.run_ingestion --input-dir samples/ingestion

# Reprocess with force flag
python -m cli.run_ingestion --input-dir samples/ingestion --force-reprocess
```

**Output Locations:**
- **Scene artifacts:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/`
- **Memory database:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db`
- **Knowledge graph:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db`
- **Vector store:** Qdrant at `localhost:6333`

---

### `watchdog` - Automated Inbox Monitor

**Purpose:** Continuously monitor inbox directory and automatically process new files.

**Usage:**
```bash
python -m cli.watchdog
```

**Key Options:**
- Current implementation starts with resolved config defaults and does not expose CLI flags for inbox/poll interval/agent mode.
- Inbox and processing roots are resolved from `configs/config.yaml` and environment (`GOODQ_DATA_ROOT`).

**What It Does:**
1. Watches configured inbox directory (default: `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox`)
2. Detects new video files (mp4, avi, mkv, mov, webm, flv)
3. Calculates file hash to avoid duplicates
4. Automatically triggers `run_ingestion` for new files
5. Records explicit control-plane state in run context; Control Agent remains disabled unless explicitly integrated with an injected `llm_client`.

**Control Plane Note:**
- The watchdog runs deterministically without auto-initializing ControlAgent by default.
- ControlAgent state is persisted as `disabled_no_llm_client` when no injected client is provided.

**Example:**
```bash
# Start watchdog with defaults
python -m cli.watchdog
```

**Logs:** `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\watchdog.log`

---

## Monitoring & Status

### `system_status` - System Health Dashboard

**Purpose:** Quick diagnostic check of all system components.

**Usage:**
```bash
python -m cli.system_status
```

**Checks Performed:**
1. **Environment:**
   - Python version
   - Critical dependencies (torch, transformers, cv2, PIL, yaml)
   - GPU availability (CUDA)

2. **Configuration:**
   - Config file validity
   - Path accessibility
   - Database connections

3. **Services:**
   - Qdrant vector store (localhost:6333)
   - vLLM inference (WSL2 systemd)
   - Audio processing service (WSL2)

4. **Storage:**
   - Database sizes
   - Disk space availability
   - Artifact directories

**Example Output:**
```
================================================================================
ENVIRONMENT STATUS
================================================================================
Python: 3.11.9
Repo Root: <project_root>
Python Path Includes Repo: True

Critical Dependencies:
  ✅ torch
  ✅ transformers
  ✅ cv2
  ✅ PIL
  ✅ yaml
  ✅ pydantic

================================================================================
CONFIGURATION STATUS
================================================================================
Config file: <project_root>\configs\config.yaml
  ✅ Valid YAML
  ✅ Schema validated
...
```

---

### `monitor_ingestion` - Live Processing Monitor

**Purpose:** Real-time view of ingestion pipeline progress.

**Usage:**
```bash
python -m cli.monitor_ingestion
```

**Displays:**
- Current video being processed
- Scene progress (e.g., "Scene 24/30")
- Active processing steps
- ETA and throughput
- GPU/CPU utilization
- Recent errors/warnings

**Refresh Rate:** 1 second

---

## Query & Retrieval

### `nl_query` - Natural Language Knowledge Graph Query

**Purpose:** Query the knowledge graph using natural language powered by LLM.

**Usage:**
```bash
python -m cli.nl_query "<your question>"
```

**What It Does:**
1. Accepts natural language question
2. Uses LLM to generate optimized graph query
3. Executes against the epoch-scoped knowledge graph database
4. Returns structured results with context

**Examples:**
```bash
# Find entity relationships
python -m cli.nl_query "Who appears with John in video scenes?"

# Time-based queries
python -m cli.nl_query "What topics were discussed after 5:30?"

# Cross-modal queries
python -m cli.nl_query "When did the speaker mention 'innovation' while showing charts?"
```

**Configuration:**
- LLM endpoint: `llm.api_url` in `configs/config.yaml`
- Default: `http://localhost:1234/v1/chat/completions` (vLLM on WSL2)

---

### `retrieve` - Vector Similarity Search

**Purpose:** Semantic search across processed content using embeddings.

**Usage:**
```bash
python -m cli.retrieve "<search query>" [OPTIONS]
```

**Key Options:**
- `--top-k`: Number of results to return (default: 10)
- `--modality`: Filter by modality (text/image/audio/all)
- `--threshold`: Minimum similarity score (0.0-1.0)

**What It Does:**
1. Embeds query text using all-MiniLM-L6-v2
2. Searches Qdrant vector store
3. Returns ranked results with:
   - Source video/scene
   - Modality
   - Similarity score
   - Context snippet

**Examples:**
```bash
# General search
python -m cli.retrieve "artificial intelligence discussion"

# Top 20 results
python -m cli.retrieve "climate change" --top-k 20

# Only transcript/audio results
python -m cli.retrieve "speaker emotion" --modality audio

# High precision (threshold 0.8)
python -m cli.retrieve "product launch" --threshold 0.8
```

---

### `graph_query` - Direct SQL Graph Queries

**Purpose:** Execute raw SQL queries against knowledge graph database.

**Usage:**
```bash
python -m cli.graph_query "<SQL query>"
```

**Example:**
```bash
python -m cli.graph_query "SELECT label, node_type, occurrence_count FROM nodes ORDER BY occurrence_count DESC LIMIT 10"
```

⚠️ **Advanced Users Only** - Requires knowledge of database schema.

---

## Memory Management

### `memory health-check` - Memory Database Diagnostics

**Purpose:** Comprehensive health check of the active epoch `memory.db`.

**Usage:**
```bash
python -m cli.memory health-check [--output-file report.json]
```

**Checks:**
- Table integrity
- Index health
- Foreign key consistency
- Orphaned records
- Schema version
- Disk corruption

**Exit Codes:**
- `0` - All checks passed
- `1` - Warnings or errors detected

---

### `memory backup` - Create Memory Backup

**Purpose:** Create timestamped backup of the active epoch `memory.db` and `knowledge_graph.db`.

**Usage:**
```bash
python -m cli.memory backup
```

**Output:**
```json
{
  "backup_dir": "<project_root>\\logs\\backups\\memory_backup_20251215_033900"
}
```

**Includes:**
- memory.db
- knowledge_graph.db
- metadata.json (backup info)

---

### `memory verify-schema` - Schema Validation

**Purpose:** Verify database schema matches expected structure.

**Usage:**
```bash
python -m cli.memory verify-schema
```

**What It Does:**
- Compares current schema to canonical definition
- Detects missing tables/columns
- Identifies type mismatches
- Checks index presence

---

### `memory migrate` - Database Migration

**Purpose:** Migrate the active epoch `memory.db` to the latest schema version.

**Usage:**
```bash
python -m cli.memory migrate [--dry-run]
```

**Options:**
- `--dry-run`: Preview changes without applying

⚠️ **Automatic backup created before migration**

---

## Utilities

### `print_config` - Display Current Configuration

**Purpose:** Print resolved configuration with all defaults applied.

**Usage:**
```bash
python -m cli.print_config [--format json|yaml]
```

**Output:** Complete configuration tree showing:
- Loaded values from `configs/config.yaml`
- Applied defaults
- Resolved paths
- Service endpoints

---

### `list_inbox` - List Inbox Contents

**Purpose:** Show all files in configured inbox with processing status.

**Usage:**
```bash
python -m cli.list_inbox
```

**Output:**
```
Files in inbox: <GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox

✅ interview.mp4 (processed: 2025-12-14 15:23:45)
⏳ lecture.mp4 (pending)
✅ presentation.mkv (processed: 2025-12-13 08:12:01)
❌ corrupted.avi (failed: 2025-12-14 10:05:22)
```

---

### `test_ingestion` - Pipeline Smoke Test

**Purpose:** Quick validation that ingestion pipeline is functional.

**Usage:**
```bash
python -m cli.test_ingestion
```

**What It Does:**
1. Uses minimal test video (5 seconds)
2. Runs through full pipeline
3. Validates all outputs
4. Reports success/failure

**Exit Codes:**
- `0` - Pipeline functional
- `1` - Pipeline broken (see logs)

---

### `step_runner` - Execute Individual Processing Step

**Purpose:** Run single processing step in isolation (debugging/testing).

**Usage:**
```bash
python -m cli.step_runner <step_name> --input <path> [OPTIONS]
```

**Examples:**
```bash
# Test OCR on single image
python -m cli.step_runner image_ocr --input frame_001.jpg

# Test transcription on audio file
python -m cli.step_runner audio_unified_wsl2 --input scene_0024.wav

# Test entity extraction on scene data
python -m cli.step_runner entity_extractor --input scene_data.json
```

---

## Configuration

All CLI commands respect settings in `configs/config.yaml`. Key paths:

```yaml
paths:
  import_inbox: "<GOODQ_DATA_ROOT>/GoodQ_Data/import_inbox"
  processed: "<GOODQ_DATA_ROOT>/GoodQ_Data/processed"
  failed: "<GOODQ_DATA_ROOT>/GoodQ_Data/failed"
  db_path: "<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/memory.db"
  knowledge_graph_db: "<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/knowledge_graph.db"
  processing: "<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/processing"
  log_dir: "<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/logs"
  watchdog_state_file: "<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/logs/watchdog_state.json"

qdrant:
  host: "localhost"
  port: 6333
  enabled: true

llm:
  api_url: "http://localhost:1234/v1/chat/completions"
```

---

## Exit Codes

Standard exit code conventions:
- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Dependency missing
- `4` - Service unavailable

---

## Getting Help

For any command:
```bash
python -m cli.<command> --help
```

For system-wide help:
```bash
python -m cli.system_status
```

---

## Related Documentation

- [Installation Guide](guides/install/INSTALL.md)
- [Architecture Overview](architecture/SYSTEM_ARCHITECTURE.md)
- [WSL2 Audio Setup](guides/wsl2/START_HERE_WSL2.md)
- [vLLM Configuration](guides/llm/VLLM_SYSTEMD_SETUP.md)
- [Knowledge Graph Schema](technical/KNOWLEDGE_GRAPH_IMPLEMENTATION.md)
