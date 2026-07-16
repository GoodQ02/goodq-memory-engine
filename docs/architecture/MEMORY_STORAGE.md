<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Memory & Storage Architecture

**Last Updated:** 2026-07-11
**Status:** ✅ Operational, with epoch-scoped SQLite + Qdrant as the active storage contract

---

## Overview

GoodQ4All uses a layered memory architecture:
- epoch-scoped SQLite for canonical relational storage
- Qdrant for canonical vector retrieval
- optional FAISS parity/fallback where configured
- scene manifests and temporal indexes as durable artifact evidence, distinct
  from active memory under isolation

This document describes the current storage contract, not historical storage experiments.

---

## Canonical Storage Roots

### Artifact and Epoch Root

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
${GOODQ_DATA_ROOT}/qdrant_storage
```

For the canonical desktop/config authority, Qdrant storage is a sibling of
`GoodQ_Data`. This does not equate that root with the packaged installer's
ProgramData layout; installer/package path reconciliation remains a separate
release concern.

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

These files are durable evidence in the memory system, not just debug
byproducts. Their presence does not by itself make their contents active or
promoted memory.

---

## Governed Materialization Lifecycle

With `ingestion_isolation: true`, `scene_manifest.json` is per-video artifact
evidence. The epoch ledger is `ucf/ucf_ledger.db`. `ucf_ledger.db` is the
lifecycle and evidence authority. Isolated ingest stages UCF context frames
there and Qdrant points with exact
`ucf_promotion_status = staged`. Ingest does not directly populate active
`memory.db` or `knowledge_graph.db` in this mode.

Promotion is explicit and scope-bound:

1. Explicit `validate_ucf_frames` validation must occur first.
2. A human-gated `promote_ucf_to_memory` operation then acts on one exact
   `video_hash` plus `epoch_id` scope.
3. Promotion materializes active `memory.db` and `knowledge_graph.db` from the
   governed evidence.

Within `ucf_ledger.db`, the status mutation, transition audit, and durable
Qdrant outbox enqueue share one immediate SQLite transaction. That transaction
does not make the active SQLite stores and Qdrant one cross-store ACID unit.
Active-view cleanup after a materialization failure is compensating and
recoverable. Post-commit Qdrant status delivery and reconciliation are separate
durable, recoverable obligations.
`promotion_committed_sync_pending` therefore means the active materialization
and UCF commit succeeded while durable Qdrant status delivery is still pending.

Default active retrieval admits only promoted evidence. Explicit raw audit
queries may inspect other UCF lifecycle states without making them active.

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

### Separate Identity-Workflow Outputs

The KG may include:
- `speaker_pattern` nodes
- `voice_pattern_match` edges
- `identity_candidate` edges
- `identity_supported` edges
- `identity_evidence` edges

Governed UCF promotion materializes active video, scene, segment, and evidence
KG projections. It does not by itself prove or materialize the speaker-pattern
or identity edges listed above. Manifest identity fields remain inputs to the
separate governed identity-ledger and stitching workflows; their outputs become
active identity truth only when those workflows execute and persist them.

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

Non-isolated ingestion may write active SQLite scene/KG surfaces directly.
Under `ingestion_isolation: true`, ingestion instead stages UCF and Qdrant
evidence; the governed promotion operation owns active SQLite materialization.
FAISS remains an additional target only when configured.

For audio retrieval health, count Qdrant audio payloads by matching `run_id`,
not by `scene_id` alone. The supported CLAP audio provenance marker includes
`run_id`, `embedding_id`, `component`, `step`, `model`, `created_at`, and
`commit_ts_utc` when available.

### Important Constraint

Storage docs must not describe a FAISS-first world or a root-level DB world as if it were current runtime truth.

---

## Backup And Recovery

Backups should cover the configured canonical roots:

- `memory.db`
- `knowledge_graph.db`
- Qdrant snapshots

The backup target itself is operationally configurable. Epoch SQLite/artifact
truth lives under `GoodQ_Data`, while canonical desktop/config Qdrant storage
lives at the sibling root defined above.

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
- [SCENE_MANIFEST_SPECIFICATION.md](SCENE_MANIFEST_SPECIFICATION.md)
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
