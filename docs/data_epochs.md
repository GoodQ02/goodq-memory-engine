# GoodQ Data Epochs (Legacy Preservation + Clean Starts)

This document marks existing data stores as **legacy** (preserved) and defines how to start a **new, empty epoch** for a clean first ingestion on the hardened system.

## Definitions

- **Epoch**: A fully isolated set of stores used by runtime ingestion and retrieval:
  - SQLite: `memory.db` + `knowledge_graph.db`
  - Qdrant collections (per modality)
  - FAISS index files (where enabled)
  - Processing root (scene manifests, derived artifacts)
- **Non-goal**: deleting or truncating legacy data. Legacy stores remain intact for audit/comparison.

## Epoch: `legacy_pre_epoch_2025_12_21` (Preserved)

**Status:** LEGACY (do not write; preserved for comparison)

- **SQLite (memory):** `<GOODQ_DATA_ROOT>/GoodQ_Data/memory.db`
- **SQLite (knowledge graph):** `<GOODQ_DATA_ROOT>/GoodQ_Data/knowledge_graph.db`
- **Processing root:** `<GOODQ_DATA_ROOT>/GoodQ_Data/processing`
- **FAISS (audio):** `<GOODQ_DATA_ROOT>/GoodQ_Data/faiss/goodq_audio.index`
- **Qdrant collections:**
  - `clip`: `goodq_clip`
  - `dino`: `goodq_dino`
  - `text`: `goodq_text`
  - `audio`: `goodq_audio`

## Epoch: `epoch_2025_12_21` (Preserved)

**Status:** LEGACY (preserved; do not write)

**Notes:**
- This epoch predates the WSL2 audio wrapper hardening and may be missing some audio-derived signals (see tag `wsl2-audio-bridge-v1.0.1`).

**Epoch root:**
- `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_21`

**Stores (authoritative targets for runtime):**
- **SQLite (memory):** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_21/memory.db`
- **SQLite (knowledge graph):** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_21/knowledge_graph.db`
- **Processing root:** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_21/processing`
- **FAISS directory:** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_21/faiss`
- **FAISS (audio):** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_21/faiss/goodq_audio_epoch_2025_12_21.index`
- **Qdrant collections (epoch-suffixed):**
  - `clip`: `goodq_clip_epoch_2025_12_21`
  - `dino`: `goodq_dino_epoch_2025_12_21`
  - `text`: `goodq_text_epoch_2025_12_21`
  - `audio`: `goodq_audio_epoch_2025_12_21`

## Epoch: `epoch_2025_12_22` (Clean)

**Status:** ACTIVE (clean; intended for the first ingestion after WSL2 audio hardening)

**Epoch root:**
- `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22`

**Stores (authoritative targets for runtime):**
- **SQLite (memory):** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/memory.db`
- **SQLite (knowledge graph):** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/knowledge_graph.db`
- **Processing root:** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/processing`
- **FAISS directory:** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/faiss`
- **FAISS (audio):** `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2025_12_22/faiss/goodq_audio_epoch_2025_12_22.index`
- **Qdrant collections (epoch-suffixed):**
  - `clip`: `goodq_clip_epoch_2025_12_22`
  - `dino`: `goodq_dino_epoch_2025_12_22`
  - `text`: `goodq_text_epoch_2025_12_22`
  - `audio`: `goodq_audio_epoch_2025_12_22`

## Canonical Manifest Path (Per Video)

Per `docs/architecture/CONFIG_LOADING_CONTRACT.md`, scene manifests must be written/read at:

- `<cfg['paths']['processing']>/<video_id>/video/scene_manifest.json`

This implies each epoch must use a distinct `cfg['paths']['processing']` to avoid cross-epoch contamination.

## How Epoch Switching Works

Epoch selection is performed by updating the canonical configuration:

- `configs/config.yaml`:
  - `paths.db_path`
  - `paths.knowledge_graph_db`
  - `paths.processing`
  - `paths.faiss_dir`
  - `paths.faiss_audio_path`
  - `qdrant.collections.*`
  - `phase6.clip_collection`
  - `phase6.dino_collection`

No legacy data is deleted or rewritten when switching epochs.

## Launcher Overrides (Optional)

`LAUNCH_GOODQ.ps1` loads `configs/config.yaml` (best-effort) and also supports explicit env overrides for the launcher process and its child processes:

- `GOODQ_WSL_DISTRO` (default: `Ubuntu`)
- `GOODQ_DB_PATH`
- `GOODQ_KG_DB_PATH`
- `GOODQ_PROCESSING_ROOT`
- `GOODQ_FAISS_DIR`
- `GOODQ_FAISS_AUDIO_PATH`
- `GOODQ_QDRANT_URL`

The launcher propagates these values to child processes as environment variables.

## Dry-Run Checklist (No Ingestion)

1) **Confirm you are in the clean epoch**
- `python -m cli.print_config` and verify the paths/collections match `epoch_2025_12_22` above.

2) **Create/verify directories and DB files**
- `python -m cli.goodq_doctor`
  - Expected: `load_configs() succeeded`
  - Expected: `cfg['paths']['processing'] exists and is writable`

3) **Confirm Qdrant collections exist and are empty**
- Visit: `http://127.0.0.1:6333/collections`
- Expected: epoch-suffixed collections listed
- Expected for each: `points_count = 0`

4) **Verify launch script safety**
- Run: `powershell -ExecutionPolicy Bypass -File .\\LAUNCH_GOODQ.ps1 -DryRun`
  - Expected: services/health checks only
  - Expected: no ingestion process started
  - Note: ingestion is now **opt-in** (`-StartIngestion`)

5) **Explicit confirmation**
- No ingestion occurred if:
  - no new video folders appear under `cfg['paths']['processing']`
  - no new points are added to epoch-suffixed Qdrant collections
  - no new rows appear in `memory_commit_events` in the epoch `memory.db`
