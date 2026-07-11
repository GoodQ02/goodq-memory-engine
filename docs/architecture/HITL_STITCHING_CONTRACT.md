<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# HITL Stitching Contract

**Purpose:** Define the mutation, persistence, and evaluation contracts for human-in-the-loop (HITL) identity stitching in GoodQ.
**Scope:** Manual mapping structures, status transitions, preview/confirmation logic, and safe read-model rebuilds.
**Non-goals:** Ingestion pipelines, scene or timeline file rewrites, Qdrant updates, or automated routing policies.

---

## Core Invariants

1. **Additive Evidence Only (No Destructive Merges):**
   * Manual mappings are treated as operator-provided evidence edges in the Knowledge Graph, never as destructive node merges.
   * Original anonymous nodes (`speaker`, `face`, `speaker_pattern`) and original `person` nodes must never be deleted, renamed, or collapsed.
   * The structural timeline and scene records are immutable raw source signals.

2. **Conflict Visibility:**
   * Manual mappings may dominate read-model resolution (e.g., in ledger summaries), but they must not erase or delete underlying conflicts.
   * Modality contradictions and name mismatches must remain queryable in the raw graph database.

3. **Reversibility (`status=revoked`):**
   * Manual mappings must never be deleted from the persistent record.
   * To reverse a mapping, its status field in the persistent mapping JSON must be transitioned to `"revoked"`.
   * The ledger re-application engine must ignore any mapping with a status of `"revoked"`.

4. **Identity Stability:**
   * Names are display labels and subject to cleanup. Mappings must bind stable, unique structural node IDs (e.g., node names/IDs) and target `person` node names/IDs.

5. **Mutation Safeguards:**
   * All operator writes require a two-stage transaction:
     1. **Preview (`confirm=false`):** Simulates the mapping addition, checks for existing conflicts, and lists the affected scenes and episodes.
     2. **Commit (`confirm=true`):** Persists the mapping, updates the SQLite graph database, and triggers ledger updates.
   * The Retro Console and Operator Console v1 remain strictly read-only.
   * Any mutation UI or stitching features must reside in a clearly separate Identity Stitching workbench.

6. **Rebuild Boundaries:**
   * A rebuild action triggered by manual stitching is strictly limited to refreshing the identity ledger (`identity_ledger.py`) and the SQLite database read-model.
   * Rebuilds must never trigger fresh media ingestion, Qdrant vector store updates, or timeline/scene JSON file rewrites.

---

## Schema Specification

Manual mappings will be persisted in a versioned JSON document located in the epoch data directory:
`<GOODQ_DATA_ROOT>/epochs/<epoch_id>/manual_identity_mappings.json`

### Mapping Entry Schema

```json
{
  "version": 1,
  "mappings": [
    {
      "mapping_id": "map_2026_05_24_0001",
      "source_node_type": "speaker_pattern",
      "source_node_name": "voice_pattern_02_1988_1989_speaker_1",
      "target_person_name": "Joe",
      "status": "active",
      "history": [
        {
          "status": "active",
          "timestamp_utc": "2026-05-24T17:00:00Z",
          "operator_note": "Identified speaker as Joe via scene 3 diaper scene"
        }
      ]
    }
  ]
}
```

---

## API Lifecycle

### 1. `GET /api/system/identity/unstitched`
* Scan the knowledge graph database for `speaker_pattern` nodes that lack any active `identity_supported` or `identity_evidence` mappings.
* Return list of unstitched patterns with duration, segment counts, and sample transcript excerpts.

### 2. `POST /api/system/identity/stitch/preview`
* Accept mapping parameters: `{ "source_node_name": str, "target_person_name": str }`.
* Perform dry-run evaluation:
  - Find the source node in SQLite.
  - Resolve the target `person` node.
  - Scan the graph for existing mappings to the same source.
  - Return: `{ "success": bool, "affects": { "scenes": int, "episodes": int }, "conflicts": [...] }`.

### 3. `POST /api/system/identity/stitch`
* Accept same mapping parameters as preview plus: `{ "confirm": bool, "operator_note": str }`.
* Reject immediately if `confirm != true`.
* Update `manual_identity_mappings.json` with the new entry (or update an existing one if it was previously revoked).
* Insert an `identity_evidence` edge in `knowledge_graph.db` with properties `{"source": "operator_manual_override", "weight": 1.0}`.
* Re-run `identity_ledger.py` evaluation to refresh read-model metrics.
