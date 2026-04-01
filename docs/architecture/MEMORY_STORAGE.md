<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-01 -->

# Memory & Storage Architecture

**Last Updated:** April 1, 2026  
**Status:** ✅ Operational (epoch-scoped memory + KG storage)

---

## Overview

GoodQ4All uses a **hybrid memory architecture** combining relational databases (SQLite) and vector databases (Qdrant) with optional FAISS indices for different storage tiers.

---

## Memory Integrity Doctrine (Do Not Break)

- **Confidence is not policy.** Confidence fields are metadata only and must not directly gate, refuse, or rerank retrieval without an explicit policy layer and approval.
- **Audit absence is not evidence.** `memory_commit_events` / `retrieval_events` are best-effort observability; missing rows can mean disabled logging or a non-blocking write failure, not “nothing happened”.
- **Provenance is a pointer.** Provenance on a retrieval hit is a best-effort link back to commit evidence; treat it as traceability, not ground truth.
- **Identity is composite; the ID namespace must never change.** Retrieval correlation relies on `embedding_id` when available, otherwise fallback identity (`scene_id` + `modality` + `model`); the deterministic UUID namespace used for Qdrant point IDs is part of storage identity and changing it risks duplicate/mismatched memories.
- **“Committed” is per-target truth.** `targets_json` is authoritative per store; row-level `committed=true` means **all attempted targets** succeeded, not that every possible store contains the memory.
- **Privacy:** `retrieval_events` must never record raw user queries; `retrieval_context` is an origin label (e.g., `api.search`) and `details_json` must remain sanitized.
- **Sensitive sources are PHI-equivalent.** **Raw content is vault-only.** **Derived conduits only.** Training export requires an explicit vault build manifest + human approval.
- **Basement sealed for chat + wearables.** Only schema + conduit wiring is present; ingestion requires an explicitly approved adapter and must stage out of the vault.
- **Health ingestion blocked by default.** A schema-first adapter exists, but ingestion wiring remains explicitly opt-in and must not ingest per-record exports into memory/KG/conduits by default.

---

## Basement Phase Summary (v1)

- **Memory Integrity v1 complete:** audited writes (`memory_commit_events`), explainable reads (provenance), temporal confidence (read-time), and retrieval observability (`retrieval_events` + rollups).
- **Conduit Pack v1 complete:** UI-safe, whitelisted, path-sanitized derived tables built via `python -m cli.conduits_build`.
- **Sensitive Source Wiring Pack v1 installed:** CME/CHE/CWE schemas + empty public conduit stubs; raw sensitive content remains vault-only by contract.

## Active Storage Systems

### 1. **Memory Database (SQLite)**

**Location:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db`

**Purpose:** Structured scene and video metadata storage

**Tables:**
- `scenes` - Scene bundles and scene-level metadata
- `segments` - Temporal text/audio segments
- `embeddings` - Embedding identity + storage routing metadata
- `links` - Cross-item memory links
- `summaries` - Derived summaries
- `memory_commit_events` - Append-only record of memory write attempts (attempted/committed + per-target details)

**Access Pattern:** Read/write during ingestion, read-heavy during retrieval

**Evidence:** Confirmed in `config.yaml` and active in `cli/run_ingestion.py`

---

## Observability Event System (Integrity-Only)

### `memory_commit_events` (writes)
- **Intent:** auditable record that a memory write was attempted and whether it committed per target store.
- **Committed semantics:** `targets_json` is authoritative per store; row-level `committed=true` means **all attempted targets** succeeded.
- **Non-blocking:** emission is best-effort; failures must not stop ingestion.
- **Fallback mirror:** optional JSONL append at `cfg['paths']['log_dir']/memory_commit_events.jsonl`.

### `retrieval_events` (reads; optional SQLite or JSONL mirror)
- **Intent:** auditable record of hits returned by retrieval (observability only; not reinforcement).
- **Privacy:** never record raw user queries in events; `retrieval_context` is a sanitized origin label.
- **Context taxonomy (conventional):** `human.ui.search`, `human.cli.retrieve`, `system.healthcheck`, `system.dashboard`, `agent.reasoning`, `unknown`.
- **Identity:** `details_json` includes `store_type` and `store_ref` (e.g., Qdrant collection / FAISS index); future joins must use `(store, store_ref, embedding_id)` rather than ID alone.
- **Fallback mirror:** on SQLite lock/busy, best-effort JSONL append at `cfg['paths']['log_dir']/retrieval_events.jsonl`.

### Derived rollups (no history deletion)
- `retrieval_events_daily` and `observability_rollup_state` are additive summaries computed on-demand via `python -m cli.observability_rollup`.
- `memory_commit_events_daily` is an additive daily rollup of `memory_commit_events` computed via `python -m cli.observability_rollup --commits`.

### UI-safe conduits (additive, path-redacted)
- `scene_modality_coverage` is a per-scene boolean coverage table (no raw events) built via `python -m cli.ui_conduits_rollup`.
- `scene_index_public` is a per-scene “spine” table (start/end + minimal Phase 6 flags) built via `python -m cli.ui_conduits_rollup`.
- `scene_index_public.media_refs_json` stores stable media reference tokens (no absolute paths). `rel` is anchored by `video_id` (video hash), e.g. `<video_id>/video/scene_manifest.json`.

## Conduit Pack v1 (UI-Safe, Whitelisted)

**Builder:** `python -m cli.conduits_build`

**Versioning:** `conduit_schema_version` (derived schema version; rebuildable)

### What conduits may expose
- Hash identifiers (`video_id`, `scene_id`, `embedding_id`), timestamps, durations, counts, booleans, and store names (e.g. Qdrant collection).
- Media references as **tokens** only (never absolute paths). Tokens are resolved locally via `cli/media_refs.py::resolve_media_ref()`.

### What conduits must never expose
- Raw embeddings/vectors.
- Absolute filesystem paths (Windows, WSL, UNC).
- Raw transcripts (or transcript segments).
- Full summaries by default (metadata only; optional redacted preview is behind a feature flag).
- Basement-only raw event tables (`memory_commit_events`, `retrieval_events`) or raw logs.

### Memory DB conduits (derived tables)
- `scene_index_public`, `scene_modality_coverage`
- `segment_index_public`, `scene_segment_alignment`
- `embedding_catalog_public`
- `summaries_public` (metadata only; preview gated by `GOODQ_SUMMARIES_PREVIEW=1`)
- `link_summary_public`
- `memory_commit_events_daily` (rollup; no target refs stored)

### Knowledge graph conduits (derived tables)
- `kg_entity_index_public`
- `kg_edge_summary_public`
- `entity_timeline_public`
- `entity_scene_mentions_public` (aggregates only)

### Processing artifact conduits (derived tables)
- `scene_manifest_public` (sanitized scene manifest indexing; no paths/transcripts)
- `temporal_index_public`, `temporal_segments_public` (sanitized; no paths/transcripts)

### Store stats conduits (derived tables)
- `vector_store_stats_public` (counts/dims only)
- `faiss_index_stats_public` (exists/size/ntotal only; no paths)

### Sensitive Source Wiring Pack v1 (schema-only stubs; empty by default)
- `thread_index_public`, `message_activity_daily_public`, `entity_thread_mentions_public`
- `health_activity_daily_public`, `health_trends_public`, `health_anomalies_public`
- `wearable_capture_index_public`, `wearable_timeline_public`, `wearable_entity_mentions_public`
- Contract: `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`

### Smoke checks
- `python -m cli.observability_health`
- `python -m cli.observability_rollup`
- `python -m cli.ui_conduits_rollup`
- `python -m cli.conduits_build`

---

### 2. **Knowledge Graph Database (SQLite)**

**Location:** `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db`

**Purpose:** Entity relationships and cross-modal connections

**Tables:**
- `nodes` - Entities, structural nodes, and identity-layer nodes
- `edges` - Relationships, candidate/support/evidence edges, and modality links
- `media_nodes` - Scene/media linkage
- `node_media` - Node-to-scene/media joins
- `events` - Temporal KG events
- `event_nodes` - Event-to-node joins

**Populated By:** `lib/kg_realtime_integration.py::update_kg_for_scene()`

**Evidence:** Active since December 14, 2025 (entity extraction fixes confirmed)

---

### 3. **Qdrant Vector Database**

**Location:** `<GOODQ_DATA_ROOT>\qdrant_storage`  
**Endpoint:** `http://localhost:6333`  
**Service:** Windows native (no Docker)

**Collections:**

| Collection | Dimension | Model | Purpose |
|-----------|-----------|-------|---------|
| `goodq_clip_epoch_<epoch>` | 512 | CLIP | Phase 6 visual scene embeddings |
| `goodq_dino_epoch_<epoch>` | 768 | DINOv2 | Phase 6 visual scene embeddings (fine-grained) |
| `goodq_text` | 384 | all-MiniLM-L6-v2 | Transcript and caption embeddings |
| `goodq_audio` | 512 | CLAP | Audio embeddings |

**Key Features:**
- **Metadata Filtering** - Filter by `video_id`, `scene_id`, `timestamp`, `speaker`, `emotion`, `objects`
- **Payload Storage** - Scene metadata attached to vectors
- **Multi-constraint Queries** - Combined semantic + metadata search
- **Distance Metrics** - Cosine similarity for all collections

**Management:**
```batch
# Start service
net start GoodQ_Qdrant

# Check health
curl http://localhost:6333/health

# Dashboard
http://localhost:6333/dashboard
```

**Evidence:** Installed December 11, 2025. Config: `qdrant.enabled: true`

---

### 4. **FAISS Indices (Optional)**

**Base Location:** `<GOODQ_DATA_ROOT>\GoodQ_Data\faiss_indices/`

**Indices:**
- `text/faiss_text.index` - Text embeddings (384-dim)
- `clip/faiss_clip.index` - CLIP embeddings (512-dim)
- `dino/faiss_dino.index` - DINO embeddings (768-dim)
- `audio/faiss_audio.index` - Audio embeddings (512-dim)

**Status:** **Enabled but secondary** - FAISS is used as a fallback/local cache when Qdrant is unavailable

**Configuration:**
```yaml
memory:
  routing:
    read_priority: [qdrant, faiss, chroma]  # Qdrant first
    write_targets: [faiss, qdrant]          # Write to both
  tiers:
    faiss:
      enabled: true
```

**Algorithm:** HNSW (Hierarchical Navigable Small World)
- `efConstruction: 200`
- `efSearch: 50`

**Evidence:** Code present in `steps/common/memory_stores.py::FaissMemory`

**Note:** No metadata filtering - returns only vector similarity scores

---

## Deprecated/Unused Systems

### ❌ ChromaDB
**Status:** Never integrated  
**Evidence:** `memory.tiers.chroma.enabled: false` in config  
**Code Artifact:** `steps/common/memory_stores.py::ChromaMemory` class exists but implements **in-memory TTL cache**, not ChromaDB library  
**Clarification:** The name "ChromaMemory" is misleading - it's actually a simple NumPy-based ephemeral cache with 15-minute TTL, not a connection to ChromaDB

### ❌ FAISS as Primary
**Status:** Superseded by Qdrant (Dec 2025)  
**Migration:** `scripts/sync_faiss_to_qdrant.py` available if needed  
**Retained For:** Local fallback, offline operation

---

## Memory Routing

### Read Priority (Retrieval)

1. **Qdrant** - Check for vectors with metadata filtering
2. **FAISS** - Fallback if Qdrant unavailable (no filtering)
3. **ChromaMemory** - In-memory cache (recent queries only)

### Write Targets (Ingestion)

- **Primary:** Qdrant + Memory DB (always)
- **Secondary:** FAISS indices (if enabled)
- **Not Used:** ChromaMemory (read-only cache)

### Code Reference
```python
# steps/common/memory_stores.py
def build_text_stores(cfg):
    stores = {}
    stores["chroma"] = ChromaMemory(dim, ttl_seconds=900)  # In-memory cache
    stores["faiss"] = FaissMemory(faiss_path, dim)         # Local index
    stores["qdrant"] = QdrantMemory(q_client)              # Primary DB
    return stores
```

---

## Storage Locations Summary

```
${GOODQ_DATA_ROOT}/GoodQ_Data/
├── epochs/<epoch>/
│   ├── memory.db
│   ├── knowledge_graph.db
│   ├── output/scene_ingest_results.json
│   └── processing/<video>/
│       ├── video/scene_manifest.json
│       └── temporal_index.json
├── qdrant_storage/
│   ├── collections/
│   │   ├── goodq_clip_epoch_<epoch>/
│   │   ├── goodq_dino_epoch_<epoch>/
│   │   ├── goodq_text/
│   │   └── goodq_audio/
│   ├── wal/
│   └── snapshots/
└── faiss_indices/
    ├── text/
    ├── clip/
    ├── dino/
    └── audio/
```

---

## ID Mapping Databases

For FAISS (which only stores integer IDs), scene ID mappings are stored:

- `<GOODQ_DATA_ROOT>\GoodQ_Data\databases\clip_id_map.sqlite`
- `<GOODQ_DATA_ROOT>\GoodQ_Data\databases\dino_id_map.sqlite`

Qdrant uses string IDs natively, so no mapping needed.

---

## Performance Characteristics

### Memory DB (SQLite)
- **Read Latency:** <1ms (indexed queries)
- **Write Latency:** <5ms (batched inserts)
- **Capacity:** 100K+ scenes tested
- **Backup:** File-based (simple copy)

### Knowledge Graph DB (SQLite)
- **Read Latency:** <5ms (entity lookups)
- **Write Latency:** ~10ms (relationship inserts)
- **Capacity:** Millions of entities (tested to 500K)
- **Indexing:** B-tree on entity names and scene IDs

### Qdrant
- **Search Latency:** 10-50ms (depends on collection size)
- **Index Type:** HNSW
- **Write Throughput:** ~1000 vectors/sec
- **Memory Usage:** ~1GB per 100K vectors (512-dim)
- **Disk Usage:** ~50MB per 100K vectors (with compression)

### FAISS
- **Search Latency:** 5-20ms
- **Index Type:** HNSW
- **Memory Usage:** ~200MB per 100K vectors (in-memory)
- **Limitation:** No metadata filtering

---

## Backup & Recovery

### Daily Operations
```batch
# Backup SQLite databases
copy <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\memory.db <GOODQ_DATA_ROOT>\GoodQ_Data\backups\memory_<epoch>_%DATE%.db
copy <GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\knowledge_graph.db <GOODQ_DATA_ROOT>\GoodQ_Data\backups\kg_<epoch>_%DATE%.db

# Backup Qdrant (snapshot)
curl -X POST http://localhost:6333/snapshots
```

### Disaster Recovery
1. Stop Qdrant service: `net stop GoodQ_Qdrant`
2. Restore SQLite files from backup
3. Restore Qdrant snapshot to `<GOODQ_DATA_ROOT>\qdrant_storage\snapshots\`
4. Restart Qdrant: `net start GoodQ_Qdrant`

---

## Query Examples

### Metadata + Semantic Search (Qdrant Only)
```python
from retrieval.multimodal_search import MultimodalSearchEngine

engine = MultimodalSearchEngine(config)

# Search with video filter
results = engine.search_visual(
    query="birthday celebration",
    filter={"video_id": "a6800419..."}
)

# Search with time range and speaker
results = engine.search_audio(
    query="excited talking",
    filter={
        "timestamp": {"$gte": 300, "$lte": 600},
        "speaker": "SPEAKER_01"
    }
)
```

### Fallback to FAISS (No Metadata)
```python
# If Qdrant unavailable, automatically uses FAISS
results = engine.search_visual("birthday celebration")
# Returns top-K by similarity only
```

---

## Configuration Reference

**File:** `configs/config.yaml`

```yaml
paths:
  db_path: ${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db
  knowledge_graph_db: ${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
  faiss_dir: /mnt/l/<GOODQ_DATA_ROOT>/GoodQ_Data/faiss

qdrant:
  enabled: true
  host: http://localhost:6333

memory:
  routing:
    read_priority: [qdrant, faiss, chroma]
    write_targets: [faiss, qdrant]
  dims:
    text: 384
    audio: 512
    clip: 512
    dino: 768
  tiers:
    chroma:
      enabled: false  # In-memory cache, not ChromaDB
    faiss:
      enabled: true   # Fallback/offline support
    qdrant:
      enabled: true   # Primary vector database
```

---

## Related Documentation

- **Qdrant Setup:** `docs/guides/QDRANT_SETUP.md`
- **Qdrant Quick Reference:** `docs/QDRANT_QUICKREF.md`
- **Knowledge Graph:** `docs/architecture/knowledge_graph_architecture.md`
- **Entity Extraction:** `docs/implementation/ENTITY_EXTRACTION_COMPLETE.md`

---

**Status:** All storage systems operational as of December 15, 2025  
**Next Review:** Q1 2026 (capacity planning for 1M+ scenes)
