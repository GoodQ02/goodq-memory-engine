# SUMMARY_CONSOLE_CONTRACT

**Purpose:** Define the data structure, safety constraints, persistence schema, and validation rules for the GoodQ Summary Console and Saved Collections system.
**Scope:** Cumulative dash statistics, entity profiles, built-in highlights, and the operator collection overlay.
**Non-goals:** Ingestion pipelines, scene/timeline JSON file rewrites, Qdrant database writes, SQLite schema changes, or identity ledger mutations.

---

## 1. Safety & Mutability Boundaries

### Read-Only Dashboard
The Summary Console (`/ui/summary_console/`) and its corresponding endpoints are strictly read-only relative to core memory. 
The operator can view consolidated profiles and recurring patterns but cannot modify original media assets, scene records, Qdrant vectors, or the SQLite database.

### Collection Overlay System
Custom collections created by operators are overlays. 
Saving, updating, or deleting a collection must **never** mutate:
* Ingestion outputs or logs
* Scene manifests (`scene_manifest.json`)
* Temporal indexes (`temporal_index.json`)
* Qdrant vector store collections
* SQLite core tables (`nodes`, `edges`, `media_nodes`, `node_media`, `events`, `event_nodes`)
* Identity mappings (`manual_identity_mappings.json`) or ledger state.

---

## 2. Saved Collections JSON Schema

All user-saved collections are stored in `saved_collections.json` next to the knowledge graph SQLite database:
`<GOODQ_DATA_ROOT>/epochs/<epoch_id>/saved_collections.json`

The file must be written atomically (write to `.tmp` first, then rename) and conform to the following schema:

```json
{
  "schema_version": 1,
  "collections": [
    {
      "collection_id": "col_20260524_192200_0001",
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
          "operator_note": "Initial creation"
        }
      ]
    }
  ]
}
```

### Soft-Delete Behavior
* `DELETE /api/summary/collections/{collection_id}` must perform a **soft-delete** by default.
* Soft-deletion transitions `status` to `"deleted"`, sets `deleted_at_utc` to the current timestamp, and appends a history entry.
* Deleted collections must be filtered out of public list endpoints.
* They are not physically removed from the JSON store.

---

## 3. Stable Entity Identity

To prevent dependency on raw SQLite integer auto-increment values (which can change when a database is rebuilt from source manifests), a stable string `entity_id` is used.

### ID Generation Rule
The `entity_id` is defined as:
`entity_id = f"{node_type}:{name}"`

* **Example:** `person:Joe`, `location:Living Room`, `concept:Speech`
* Since `node_type` and `name` are a unique index constraint in the SQLite database, this guarantees uniqueness and structural stability across rebuilds.
* All endpoints (dashboard, entity profiles, collections query parameters) must use or resolve to this format.

---

## 4. Scope Metadata Requirements

Every summary API response must include a `scope_metadata` section containing:
* `epoch`: String ID of the active epoch (e.g., `epoch_2026_05_22_family_full_01`).
* `db_path`: A redacted/safe database label or filename (e.g., `knowledge_graph.db`).
* `video_count`: Number of processed videos in the current epoch.
* `scene_count`: Number of scenes in the current epoch.
* `temporal_index_count`: Count of active temporal indices loaded.
* `generated_at_utc`: ISO 8601 UTC timestamp of calculation.
* `source_surfaces_used`: Array of data sources processed (e.g., `["sqlite_knowledge_graph", "temporal_index_json"]`).
