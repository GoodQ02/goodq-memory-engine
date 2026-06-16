# UCF Qdrant Status Backfill Plan

This document details the operational scope, identified data gaps, and backfill plan for the UCF Retrieval Bridge.

## 1. Scope of the UCF Retrieval Bridge (Forward-Sync Only)
The UCF Retrieval Bridge implements real-time, event-driven forward synchronization of Unified Context Frame (UCF) promotion statuses to the Qdrant vector database.
When a user or system agent performs a lifecycle status transition (`promote`, `reject`, or `supersede`) via the `MiniAgentClient` tools, the bridge queries the ledger SQLite database for the target frames, filters those matching `vector_backend = 'qdrant'`, and performs a PUT payload update to Qdrant to record the new `ucf_promotion_status` payload field on those points.

This ensures that all newly processed and lifecycle-managed context frames are instantly synchronized with the vector search index.

## 2. Excluded Operations (No Backfill of Pre-Bridge Rows)
The UCF Retrieval Bridge does NOT retroactively scan, compute, or update Qdrant point payloads for context frames that were processed or promoted prior to the deployment of this bridge.
The following operations are outside the scope of the real-time bridge:
- Querying Qdrant to find points missing the `ucf_promotion_status` field.
- Matching legacy Qdrant points back to `context_frames` records.
- In-place bulk payload corrections on existing Qdrant collections.

## 3. The Sync Gap (Pre-Bridge Frames)
Because the bridge is forward-sync only, legacy points created before this implementation do not have a `ucf_promotion_status` key in their payloads.
Under the default search doctrine:
- A query with `ucf_include_terminal = False` and no `ucf_status_filter` will exclude points where `ucf_promotion_status` is explicitly `"rejected"` or `"superseded"` using a `must_not` clause.
- However, because legacy pre-bridge points entirely lack the `ucf_promotion_status` field, they are not excluded by the `must_not` check and will still appear in query results.
This is expected behavior during the transition phase, ensuring that historical, un-managed data is not silently hidden or lost until a formal backfill has occurred.

## 4. Recommended Backfill Approach
To close the historical gap, we recommend introducing a dedicated, human-in-the-loop (HITL) gated tool named `backfill_ucf_qdrant_payloads`.

The tool will execute the following procedure:
1. **Ledger Alignment**: Scan the `context_frames` table in `ucf_ledger.db` for all records with `vector_backend = 'qdrant'` and a non-NULL `vector_key`.
2. **Batch Ingestion**: Query Qdrant for each unique collection/point to fetch current payloads, or construct payload updates directly if the ledger status is assumed authoritative.
3. **Chunked Updates**: Perform chunked PUT requests to Qdrant's `/collections/{collection}/points/payload` endpoint, updating the `ucf_promotion_status` field of legacy points to match their current database promotion status (`staged`, `validated`, `promoted`, `rejected`, or `superseded`).
4. **Audit and Verification**: Emit an execution report outlining the number of points backfilled, collections affected, and any failed points.
