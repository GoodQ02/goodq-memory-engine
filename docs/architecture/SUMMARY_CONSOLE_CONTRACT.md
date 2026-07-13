<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# SUMMARY_CONSOLE_CONTRACT

**Purpose:** Define the data structure, safety constraints, persistence schema, and validation rules for the GoodQ Summary Console and Saved Collections system.
**Scope:** Cumulative dash statistics, entity profiles, built-in highlights, and the operator collection overlay.
**Non-goals:** Ingestion pipelines, scene/timeline JSON file rewrites, Qdrant database writes, SQLite schema changes, or identity ledger mutations.

---

## 1. Safety & Mutability Boundaries

### Read-Only Dashboard
Summary Console dashboard, profile, highlight, video, and collection-list reads
are strictly read-only relative to core memory. The operator can view
consolidated profiles and recurring patterns but cannot modify original media
assets, scene records, Qdrant vectors, or the SQLite database. Reading an epoch
with no collection overlay returns an in-memory empty v1 projection and must not
create the overlay, lock, or temporary artifacts.

### Collection Overlay System
Custom collections created by operators are overlays. 
Creating or soft-deleting a collection must **never** mutate:
* Ingestion outputs or logs
* Scene manifests (`scene_manifest.json`)
* Temporal indexes (`temporal_index.json`)
* Qdrant vector store collections
* SQLite core tables (`nodes`, `edges`, `media_nodes`, `node_media`, `events`, `event_nodes`)
* Identity mappings (`manual_identity_mappings.json`) or ledger state.

Collection create and soft-delete are intentional `curated_mutation` actions,
not read-only operations. They require explicit operator confirmation before a
server prepare, then one exact-scope single-use MiniAgent confirm. Create prepare
establishes authority evidence; delete prepare additionally persists its pending
control-ledger job. Neither prepare mutates the collection overlay. Both actions
reuse the generic external-outcome audit authority; no browser-only, boolean, or
second token authority is valid.

---

## 2. Saved Collections JSON Schema

All user-saved collections are stored in `saved_collections.json` next to the knowledge graph SQLite database:
`<GOODQ_DATA_ROOT>/epochs/<epoch_id>/saved_collections.json`

The store owner must strictly validate schema v1 and fail closed without
rewriting malformed existing bytes. One cross-process sibling lock spans the
full load, validation, mutation, and replacement boundary. Writes use a unique
same-directory temporary file, flush and file-sync it, atomically replace the
authoritative file, and attempt directory sync where supported. The writer
strict-loads and compares the flushed candidate before replacement and the
authoritative file after replacement. A failed write, flush, file sync,
replacement, or inspection restores prior bytes (or removes a failed first
write), surfaces failure, and removes only the current writer's temporary
artifacts. If restoration itself fails, a distinct manual-recovery error is
raised. When prior authoritative bytes existed, their unique fsynced rollback
artifact is retained; a failed first-write cleanup has no prior rollback artifact.

The durable file conforms to the following schema. Governed correlation fields
in history are private persistence evidence and are removed from public API
projections:

```json
{
  "schema_version": 1,
  "collections": [
    {
      "collection_id": "col_20260524_192200_7f4a1b2c3d4e",
      "name": "Holiday 1988 Dinner",
      "description": "Family dinner in the dining room with Grandma during Christmas 1988",
      "status": "active",
      "collection_type": "manual_playlist",
      "query_params": {
        "entity_id": "person:Joe",
        "location": "Dining Room"
      },
      "scene_refs": [
        {
          "video_id": "02. 1988 - 1989",
          "scene_id": "scene_0003"
        }
      ],
      "source_epoch": "epoch_2026_05_22_family_full_01",
      "created_at_utc": "2026-05-24T19:22:00Z",
      "created_by": "operator",
      "updated_at_utc": "2026-05-24T19:22:00Z",
      "deleted_at_utc": null,
      "history": [
        {
          "action": "create",
          "timestamp_utc": "2026-05-24T19:22:00Z",
          "operator_note": "Initial creation",
          "action_id": "action_0123456789abcdef0123456789abcdef",
          "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "authorization_request_id": "request-create-example"
        }
      ]
    }
  ]
}
```

### Soft-Delete Behavior
* `DELETE /api/summary/collections/{collection_id}` performs a **soft-delete** only after exact prepare/confirm authority succeeds.
* Soft-deletion transitions `status` to `"deleted"`, sets `deleted_at_utc` to the current timestamp, and appends a history entry.
* Delete confirmation binds the exact epoch, collection ID, canonical record digest, and persistent job ID.
* Delete history privately persists `job_id`, `expected_record_sha256`, and `authorization_request_id` for exact crash recovery.
* Startup reconciliation may terminalize only from matching ledger, authorization, collection, digest, status, and history evidence; it must never replay or invent a past mutation.
* Deleted collections must be filtered out of public list endpoints.
* They are not physically removed from the JSON store.

---

## 3. Governed Collection Actions

### Create

`POST /api/summary/collections` accepts only:

1. `prepare` with one collection payload. It revalidates and canonically hashes
   the payload, issues one token bound to `action_id`, `epoch_id`, and
   `payload_sha256`, and performs no overlay write.
2. `confirm` with the same payload and exact prepared action, epoch, digest, and
   bearer token. The server rederives the digest before claiming authority.

The create response exposes the public collection, exact action ID, and
`audit_status`. A reused token is recoverable only from exact persisted create
history and must not repeat the write.

### Delete

`DELETE /api/summary/collections/{collection_id}` accepts only:

1. `prepare`, which validates the active epoch record, persists a
   `pending_confirmation` job, binds its canonical record digest, then issues
   one exact token.
2. `confirm` with the exact job, epoch, record digest, and token. The durable job
   moves through `authorizing`, `queued`, and `running` before terminal truth is
   recorded.

Only terminal `succeeded` with outcome `collection_deleted` is deletion success.
If the overlay committed but terminal ledger finalization is pending, the API
returns `collection_finalization_pending`; the UI must not claim success.

### Public and audit boundary

- Raw names, descriptions, transcripts, paths, and bearer tokens do not enter
  authorization or audit scope; canonical digests represent private payloads.
- Public responses exclude token fingerprints, authorization request IDs,
  owner instances, paths, and raw exceptions.
- Pre-effect authority failure blocks mutation. Post-effect audit failure keeps
  committed truth and returns `audit_status=failed`.
- The UI confirms before prepare, clears both parsed and local token references,
  resubmits exact scope, and reports success only after validating the confirmed
  durable response.

---

## 4. Stable Entity Identity

To prevent dependency on raw SQLite integer auto-increment values (which can change when a database is rebuilt from source manifests), a stable string `entity_id` is used.

### ID Generation Rule
The `entity_id` is defined as:
`entity_id = f"{node_type}:{name}"`

* **Example:** `person:Joe`, `location:Living Room`, `concept:Speech`
* Since `node_type` and `name` are a unique index constraint in the SQLite database, this guarantees uniqueness and structural stability across rebuilds.
* All endpoints (dashboard, entity profiles, collections query parameters) must use or resolve to this format.

---

## 5. Scope Metadata Requirements

Dashboard, entity-profile, highlight, and other cumulative read responses must
include or inherit a `scope_metadata` section containing:
* `epoch`: String ID of the active epoch (e.g., `epoch_2026_05_22_family_full_01`).
* `db_path`: A redacted/safe database label or filename (e.g., `knowledge_graph.db`).
* `video_count`: Number of processed videos in the current epoch.
* `scene_count`: Number of scenes in the current epoch.
* `temporal_index_count`: Count of active temporal indices loaded.
* `generated_at_utc`: ISO 8601 UTC timestamp of calculation.
* `source_surfaces_used`: Array of data sources processed (e.g., `["sqlite_knowledge_graph", "temporal_index_json"]`).

Governed action responses instead expose their exact safe action/job scope and
outcome projection as defined above. They must not add database paths merely to
satisfy the read-response metadata contract.
