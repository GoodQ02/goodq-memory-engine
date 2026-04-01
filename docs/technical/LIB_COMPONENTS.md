<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-01 -->

# Core Library Components (`lib/`)

**Last Updated:** April 1, 2026  
**Status:** ✅ Current active library surface  
**Purpose:** Reference for the shared runtime modules that remain active in `lib/`

---

## Overview

`lib/` is no longer a catch-all for every historical subsystem. The active surface is smaller and more focused:

- knowledge graph persistence
- realtime KG integration during ingestion
- identity ledger rebuilds
- shared logging and naming helpers
- unified LLM helper surface

This document describes the current active `lib/` modules only. Historical or retired modules belong in archive or historical notes, not in the active component map.

---

## Active Modules

### `knowledge_graph.py`

**Purpose**
- SQLite-backed graph manager for nodes, edges, media links, and events

**Used By**
- `lib/kg_realtime_integration.py`
- offline ledger/control rebuilds
- local query and diagnostics surfaces

**Current Truth**
- works against epoch-scoped `knowledge_graph.db`
- stores stitching-era node and edge types such as `speaker_pattern`, `voice_pattern_match`, `identity_candidate`, `identity_supported`, and `identity_evidence`

---

### `kg_realtime_integration.py`

**Purpose**
- canonical realtime KG insertion/update layer during ingestion

**Used By**
- `cli/run_ingestion.py`

**Current Truth**
- consumes fresh scene bundles
- inserts nodes and edges scene by scene
- respects structural anonymity for speaker/face placeholders
- emits the current identity ladder:
  - `voice_pattern_match`
  - `identity_candidate`
  - `identity_supported`
  - `identity_evidence`

This is the active identity-formation runtime seam.

---

### `identity_ledger.py`

**Purpose**
- rebuild and summarize identity formation evidence from persisted manifests and KG edges

**Used By**
- `scripts/build_identity_ledger.py`
- control-ledger audits and witness summaries

**Current Truth**
- reports candidate/support/evidence totals
- preserves scene-level `supporting_evidence`
- is the canonical reporting surface for stitching-era identity accumulation

---

### `llm_client.py`

**Purpose**
- shared LLM helper layer for places where the runtime still needs a unified client abstraction

**Current Truth**
- still active as a shared helper surface
- not the owner of orchestration
- should be treated as a library dependency, not as a separate control plane

This doc intentionally does not freeze provider/model combinations; those may evolve faster than the active library contract.

---

### `goodq_logger.py`

**Purpose**
- shared logging helpers and mission-styled log presentation

**Used By**
- runtime steps and helper surfaces that want a common logger

**Current Truth**
- operational helper only
- does not define observability policy by itself

---

### `mission_components.py`

**Purpose**
- maps internal step names to consistent display names

**Current Truth**
- active presentation helper
- safe to use for user-facing labels and logs

---

### `run_narrative.py`

**Purpose**
- helper surface for narrative-oriented reporting around runs

**Current Truth**
- auxiliary, not canonical orchestration
- does not replace `cli/run_ingestion.py`

---

## Supporting Package Surface

### `lib/observability/`

**Purpose**
- shared observability helpers used by runtime-facing code

**Current Truth**
- active support package
- complements CLI/operator surfaces such as `cli/system_status.py`, `cli/monitor_ingestion.py`, and rollups

---

## What Is Not Part Of The Active `lib/` Truth Surface

These were previously described as active in older docs, but they are not part of the current active library map:

- `unified_knowledge_graph.py` as an active runtime owner
- `cross_video_entity_resolver.py` as an active runtime owner
- `timeline_builder.py` as an active runtime owner
- `graph_query.py` as an active `lib/` module
- legacy process-manager surfaces
- old FAISS-first storage narratives

If those concepts still matter historically, they should live in archive or design/backlog documentation, not in the active component reference.

---

## Integration Map

### Primary Callers

| Module | Primary Caller | Role |
|---|---|---|
| `knowledge_graph.py` | `kg_realtime_integration.py` | graph persistence |
| `kg_realtime_integration.py` | `cli/run_ingestion.py` | realtime scene insertion |
| `identity_ledger.py` | `scripts/build_identity_ledger.py` | stitching-era reporting |
| `llm_client.py` | selected runtime helpers | shared LLM access |
| `goodq_logger.py` | runtime helpers and steps | shared logging |
| `mission_components.py` | runtime helpers and presentation surfaces | shared labels |

---

## Storage Truth

The active `lib/` modules operate against epoch-scoped storage:

- `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db`
- `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db`
- `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json`

They should not assume:
- root-level DBs outside the epoch tree
- `logs/scene_ingest` as canonical runtime storage
- hidden service-owned state outside the documented storage contract

---

## Verification Checklist

When validating `lib/` truth:

1. `cli/run_ingestion.py` is still the runtime owner and calls into `kg_realtime_integration.py`.
2. Fresh witnesses write stitching-era edges into the epoch KG.
3. `identity_ledger.py` can rebuild candidate/support/evidence totals from persisted artifacts.
4. No active docs describe retired `lib/` modules as the current runtime path.

---

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)
- [ARCHITECTURE_REFERENCE.md](../architecture/ARCHITECTURE_REFERENCE.md)
- [MEMORY_STORAGE.md](../architecture/MEMORY_STORAGE.md)
- [IDENTITY_STITCHING_CONTRACT.md](../architecture/IDENTITY_STITCHING_CONTRACT.md)

---

## Summary

The active `lib/` surface is now compact and deliberate. It is centered on:
- graph persistence
- realtime KG updates
- identity-ledger rebuilds
- shared helper layers

Anything outside that set should be treated as historical, auxiliary, or retired unless the runtime and canonical docs explicitly promote it back into the active surface.
