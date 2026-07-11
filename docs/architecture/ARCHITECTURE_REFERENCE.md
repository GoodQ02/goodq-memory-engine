<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# GoodQ4All Architecture Reference

**Last Updated:** 2026-07-11
**Status:** ✅ Updated with epoch-scoped storage and stitching-era verification  
**Purpose:** Definitive reference for current storage surfaces, core runtime entry points, and canonical architecture components

> This document is intentionally narrower than `SYSTEM_ARCHITECTURE.md`. It exists to freeze the active operator truth, not to preserve every historical implementation detail.

---

## Core Runtime Truth

- **Canonical ingest owner:** `cli/run_ingestion.py`
- **Canonical artifact/epoch root:** `${GOODQ_DATA_ROOT}/GoodQ_Data`
- **Canonical vector store:** Qdrant
- **Canonical relational memory:** epoch-scoped SQLite
- **Canonical per-video artifact evidence:** epoch-scoped `scene_manifest.json`
- **Canonical lifecycle/evidence ledger:** epoch-scoped `ucf/ucf_ledger.db`
- **Canonical audio acceleration path:** direct unified WSL worker
- **Canonical identity ladder:** `speaker_pattern -> voice_pattern_match -> identity_candidate -> identity_supported -> identity_evidence`

Desktop remains the source of truth. WSL is a compute extension, not a peer control plane.

---

## Storage Surfaces

### `memory.db`

**Location**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db
```

**Purpose**

- scene bundles
- segment rows
- summary rows
- embedding routing metadata
- memory commit observability

### `knowledge_graph.db`

**Location**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
```

**Purpose**

- nodes and edges for entities, concepts, locations, speakers, faces, and voice patterns
- media linkage
- temporal events
- identity formation edges

### Qdrant

**Endpoint**

```text
http://localhost:6333
```

**Storage Root**

```text
${GOODQ_DATA_ROOT}/qdrant_storage
```

For canonical desktop/config authority, this Qdrant root is a sibling of
`GoodQ_Data`. It does not claim that the packaged installer's ProgramData layout
is identical; installer/package path reconciliation remains a separate release
concern.

**Canonical Collections**

- `goodq_text_epoch_<epoch>`
- `goodq_audio_epoch_<epoch>`
- `goodq_clip_epoch_<epoch>`
- `goodq_dino_epoch_<epoch>`

FAISS remains optional parity or fallback only. It is not the current operator truth for retrieval.

For CLAP audio coverage, current-run vector success requires
`clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and
required provenance fields. A matching `scene_id` alone is not proof. See
`AUDIO_VECTOR_PROVENANCE_CONTRACT.md`.

---

## Governed Materialization Lifecycle

When `ingestion_isolation: true`, `scene_manifest.json` and the per-video
temporal index are artifact evidence. The epoch ledger is `ucf/ucf_ledger.db`.
`ucf_ledger.db` is the lifecycle and evidence authority. Isolated ingest stages
UCF rows and Qdrant points with
`ucf_promotion_status = staged`; it does not directly materialize active
`memory.db` or `knowledge_graph.db`.

The required path is staged ingest, explicit `validate_ucf_frames`, then a
separately approved human-gated `promote_ucf_to_memory` operation for one exact
`video_hash` plus `epoch_id` scope. Promotion materializes active `memory.db`
and `knowledge_graph.db`.

The UCF status change, transition audit, and durable Qdrant outbox enqueue are
one immediate SQLite transaction in `ucf_ledger.db`. Active-view cleanup is
compensating/recoverable work; there is no cross-store ACID claim. Post-commit
Qdrant status delivery and reconciliation are separate durable, recoverable
obligations. `promotion_committed_sync_pending` means the active materialization
and UCF commit succeeded while durable Qdrant status delivery remains pending.

Default active retrieval exposes only promoted evidence. Explicit raw audit queries
may inspect other lifecycle states without promoting them.

---

## Knowledge Graph Schema

### Core Tables

- `nodes`
- `edges`
- `media_nodes`
- `node_media`
- `events`
- `event_nodes`

### Live Identity / Pattern Edge Types

- `voice_pattern_match`
- `identity_candidate`
- `identity_supported`
- `identity_evidence`

### Important Node Types

- `person`
- `location`
- `object`
- `concept`
- `speaker`
- `face`
- `speaker_pattern`

Anonymous speaker and face nodes remain structural until the identity ladder has enough evidence to support promotion.

---

## File System Layout

```text
${GOODQ_DATA_ROOT}/
├── GoodQ_Data/
│   ├── import_inbox/
│   └── epochs/<epoch>/
│       ├── memory.db
│       ├── knowledge_graph.db
│       ├── ucf/ucf_ledger.db
│       ├── output/
│       │   └── scene_ingest_results.json
│       └── processing/<video_name>/
│           ├── audio/
│           ├── video/
│           │   └── scene_manifest.json
│           └── temporal_index.json
└── qdrant_storage/
```

WSL worker assets are anchored at:

```text
${GOODQ_WSL_WORKSPACE}
```

That workspace contains the direct unified worker and its helper scripts.

---

## Runtime Entry Points

### CLI

- `python -m cli.run_ingestion`
- `python -m cli.watchdog`
- `python -m cli.monitor_ingestion`
- `python -m cli.system_status`
- `python -m cli.print_config`
- `python -m cli.list_inbox`
- `python -m cli.retrieve`
- `python -m cli.nl_query`

### WSL Audio

The canonical accelerated path is the direct unified worker under `${GOODQ_WSL_WORKSPACE}`. The old service-style queue model is not the current runtime truth.

See [WSL_AUDIO_RUNTIME.md](../reference/WSL_AUDIO_RUNTIME.md).

---

## Active Components

### CLI Surface

- `cli/run_ingestion.py` - orchestration owner
- `cli/watchdog.py` - canonical watchdog
- `cli/system_status.py` - runtime/operator checks
- `cli/monitor_ingestion.py` - live run monitoring
- `cli/retrieve.py` - vector search surface
- `cli/nl_query.py` - natural-language KG/query helper

### `lib/`

- `knowledge_graph.py`
- `kg_realtime_integration.py`
- `identity_ledger.py`
- `llm_client.py`
- `goodq_logger.py`
- `mission_components.py`

### Phase 6

- `steps/video/scene_visual_embeddings.py`
- `steps/video/cross_modal_harmonizer.py`

### WSL Audio

- `wsl2_audio/process_audio.py`
- `steps/audio/audio_wsl2_bridge.py`
- `scripts/wsl2_audio_bridge.py`

---

## Deprecated Or Historical Surfaces

These may still appear in archived docs or compatibility notes, but they are not the active operator truth:

- `logs/scene_ingest` as the primary artifact root
- service-style WSL queue orchestration as the canonical audio path
- root-level DB assumptions outside the epoch tree
- “Phase 6 is latent” language
- old FAISS-first retrieval descriptions
- old cross-video graph modules described as active runtime owners

Historical docs may still mention them; canonical active docs should not.

---

## Verification Checklist

When validating runtime truth, confirm:

1. Scene bundles exist under the epoch processing tree.
2. `scene_ingest_results.json` exists under the epoch output tree.
3. `phase6_complete = true` and `qdrant_ok = true` on successful witnesses.
4. `audio_backend_effective` truth matches the actual backend used.
5. `speaker_voice_signatures` and stitching-era fields appear in fresh manifests when the runtime has enough voiced speech.
6. Active retrieval scopes show promoted UCF/Qdrant state; artifact completion
   alone is not promotion proof.

---

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- [MEMORY_STORAGE.md](MEMORY_STORAGE.md)
- [INGEST_ORCHESTRATION_CONTRACT.md](INGEST_ORCHESTRATION_CONTRACT.md)
- [IDENTITY_STITCHING_CONTRACT.md](IDENTITY_STITCHING_CONTRACT.md)
- [WSL_AUDIO_RUNTIME.md](../reference/WSL_AUDIO_RUNTIME.md)

---

## Summary

GoodQ4All is now an epoch-scoped, scene-centric memory system with:
- Qdrant as the canonical vector store
- SQLite as canonical memory and graph persistence
- direct unified WSL audio acceleration
- operational Phase 6 multimodal fusion
- governed staged-to-promoted materialization
- a conservative identity formation ladder built on persisted speaker and voice-pattern evidence
