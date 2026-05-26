<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

# Memory & Storage Architecture

**Last Updated:** May 21, 2026
**Status:** ✅ Operational, with epoch-scoped SQLite + Qdrant as the active storage contract

---

## Overview

GoodQ4All uses a layered memory architecture:
- epoch-scoped SQLite for canonical relational storage
- Qdrant for canonical vector retrieval
- optional FAISS parity/fallback where configured
- scene manifests and temporal indexes as durable artifact truth

This document describes the current storage contract, not historical storage experiments.

---

## Canonical Storage Roots

### Unified Data Root

```text
${GOODQ_DATA_ROOT}/GoodQ_Data
```

### Epoch Root

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>
```

### WSL Worker Root

```text
${GOODQ_WSL_WORKSPACE}
```

The WSL workspace is a compute extension root, not the canonical persistence root.

---

## Active Storage Systems

### 1. `memory.db`

**Location**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db
```

**Purpose**
- scene bundles
- segment rows
- embedding identity and routing metadata
- links
- summaries
- commit observability

**Core Tables**
- `scenes`
- `segments`
- `embeddings`
- `links`
- `summaries`
- `memory_commit_events`

### 2. `knowledge_graph.db`

**Location**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
```

**Purpose**
- entities and relationships
- structural speaker/face nodes
- scene/media linkage
- temporal events
- identity formation edges

**Core Tables**
- `nodes`
- `edges`
- `media_nodes`
- `node_media`
- `events`
- `event_nodes`

### 3. Qdrant

**Endpoint**

```text
http://localhost:6333
```

**Storage Root**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/qdrant_storage
```

**Canonical Collections**
- `goodq_text_epoch_<epoch>`
- `goodq_audio_epoch_<epoch>`
- `goodq_clip_epoch_<epoch>`
- `goodq_dino_epoch_<epoch>`

Qdrant is the canonical vector retrieval surface.

### 4. FAISS (Optional)

FAISS remains optional as:
- local parity
- offline fallback
- secondary vector surface where configured

It is not the canonical first-class retrieval truth.

Configured FAISS paths are epoch-scoped:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/faiss/
├── text/faiss_text.index
├── clip/faiss_clip.index
├── dino/faiss_dino.index
├── audio/clap_id_map.sqlite
├── clip/clip_id_map.sqlite
├── dino/dino_id_map.sqlite
└── goodq_audio_<epoch>.index
```

FAISS commits must use explicit stable IDs. New HNSW indexes are wrapped in
`IndexIDMap2`, and writers must not silently downgrade from `add_with_ids` to
position-based `add`. A legacy non-IDMap FAISS file is historical evidence, not
a valid target for new strict FAISS parity writes.

---

## Artifact Storage

### Scene Bundle Artifacts

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/
├── audio/
├── video/
│   └── scene_manifest.json
└── temporal_index.json
```

### Run Summary

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/output/scene_ingest_results.json
```

These files are part of the memory system, not just debug byproducts.

---

## Memory Integrity Doctrine

### Confidence Is Not Policy

Confidence values are metadata only. They must not silently become retrieval or memory-policy decisions without an explicit, approved policy layer.

### Audit Absence Is Not Evidence

`memory_commit_events` and retrieval observability tables are best-effort audit surfaces. Missing rows do not prove the underlying event never happened.

### Provenance Is Traceability

Provenance fields help trace a result back to storage, but they do not replace the canonical artifact or DB truth.

### Identity Must Remain Stable

Storage identity must remain deterministic. Changes to embedding identity, point identity, or stitching identity semantics risk corrupting memory continuity.

### Per-Target Commit Truth Matters

Write success must be interpreted per store. A row-level success flag is not permission to assume every possible store contains the same memory.

### Explicit FAISS IDs Are Required

When FAISS is configured, a successful FAISS commit means the vector was written
with a deterministic explicit ID and any configured SQLite ID map was updated.
Sequential FAISS row positions are not stable provenance. If an existing FAISS
index cannot accept explicit IDs, the writer must fail visibly for that FAISS
target rather than reporting a best-effort success.

### Audio Vector Success Requires Run Provenance

For CLAP audio vectors, current-run success is not proven by scene-id presence
in Qdrant. A scene counts as current-run audio-vector covered only when the
scene payload has `clap_meta.status == ok` and the Qdrant audio payload has the
same `run_id` plus required provenance fields.

Legacy audio points with missing `run_id`, stale points from another `run_id`,
and `clap_meta.status == skipped` or `error` are not current-run success.
Consumers should expose narrower states such as
`provenance_unverified_audio_vector_exists`, `legacy_audio_vector_present`,
`audio_vector_skipped`, or `audio_vector_error`.

See `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`.

---

## Identity-Aware Storage Truth

The current storage layer now includes identity formation artifacts.

### Manifest-Level Inputs

Fresh scene manifests may include:
- `speaker_transcript`
- `speaker_voice_signatures`
- `speaker_voice_signature_meta`

### KG-Level Outputs

The KG may include:
- `speaker_pattern` nodes
- `voice_pattern_match` edges
- `identity_candidate` edges
- `identity_supported` edges
- `identity_evidence` edges

Those are now part of memory truth. They should not be treated as optional commentary.

---

## Conduits And Observability

### Observability Tables

Current write/read observability surfaces include:
- `memory_commit_events`
- `retrieval_events`

These are integrity and audit tools, not reinforcement learning surfaces.

### UI-Safe Derived Conduits

Derived conduit tables remain additive and sanitized. They may expose:
- hashes and ids
- timestamps and durations
- booleans and counts
- store names
- media reference tokens

They must not expose:
- raw vectors
- absolute paths
- raw transcript payloads by default
- basement-only raw event tables

---

## Query And Routing Truth

### Read Priority

Current retrieval should treat Qdrant as the canonical vector surface, with optional FAISS fallback where configured.

### Write Targets

Ingestion writes to:
- SQLite scene/KG surfaces
- Qdrant vector collections
- FAISS only when configured as an additional target

For audio retrieval health, count Qdrant audio payloads by matching `run_id`,
not by `scene_id` alone. The supported CLAP audio provenance marker includes
`run_id`, `embedding_id`, `component`, `step`, `model`, `created_at`, and
`commit_ts_utc` when available.

### Important Constraint

Storage docs must not describe a FAISS-first world or a root-level DB world as if it were current runtime truth.

---

## Backup And Recovery

Backups should be taken from the epoch-scoped roots:

- `memory.db`
- `knowledge_graph.db`
- Qdrant snapshots

The backup target itself is operationally configurable, but the source of truth is the epoch tree.

---

## Verification Checklist

The storage contract is healthy when:

1. `memory.db` and `knowledge_graph.db` exist under the current epoch.
2. `scene_manifest.json` exists under the epoch processing tree.
3. `scene_ingest_results.json` exists under the epoch output tree.
4. successful witnesses show `qdrant_ok = true`.
5. current-run CLAP audio coverage equals scenes where `clap_meta.status == ok`
   and Qdrant audio payloads have matching `run_id` provenance.
6. fresh stitching-era runs can persist speaker voice signatures and pattern edges without breaking the scene bundle contract.

---

## Deprecated Or Non-Canonical Narratives

These should not be treated as active truth:
- root-level DB assumptions outside the epoch tree
- ChromaDB as a primary integrated store
- internal legacy `chroma` naming as proof that the runtime still depends on a real ChromaDB tier
- FAISS as the primary retrieval truth
- older `logs/scene_ingest` artifact roots
- docs that present old service-era storage assumptions as current

Historical notes can keep those details, but active operator docs should not.

---

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- [ARCHITECTURE_REFERENCE.md](ARCHITECTURE_REFERENCE.md)
- [SCENE_MANIFEST_SPECIFICATION.md](../SCENE_MANIFEST_SPECIFICATION.md)
- [IDENTITY_STITCHING_CONTRACT.md](IDENTITY_STITCHING_CONTRACT.md)

---

## Summary

The current memory system is:
- epoch-scoped
- scene-centric
- SQLite-backed for relational memory and graph truth
- Qdrant-backed for canonical vector retrieval
- stitching-aware through persisted manifest and KG identity surfaces

That is the storage contract active operators and agents should reason from.
