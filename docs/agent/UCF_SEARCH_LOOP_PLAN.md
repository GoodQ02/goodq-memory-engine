# UCF Search-Loop Visibility & Hardening Plan

This document outlines the detailed technical answers regarding the searchability posture of Unified Context Frame (UCF) records upon promotion, the architectural gaps in the current retrieval layer, and the proposed verification test shape.

---

## Q1 — Does promotion make a frame searchable?

### Code Path Trace
Tracing the execution path of the promotion tool from the entry point `MiniAgentClient.execute_tool(tool_name="promote_ucf_to_memory")` inside `agents/mini_agent_client.py`:
1. The client invokes `self._execute_promote_ucf_to_memory(tool_args)`.
2. A connection is established to the isolated ledger database file at the path:
   `relative/path/to/epochs/<epoch_id>/ucf/ucf_ledger.db`
3. A query pre-check verifies that no frames remain in the `'staged'` status within the scope (`video_hash` and `epoch_id`).
4. An orphan vector check validates that all attempted vectors exist inside the ledger's context frames.
5. The client executes the SQL update command:
   ```sql
   UPDATE context_frames 
   SET promotion_status = 'promoted' 
   WHERE promotion_status = 'validated' 
     AND video_hash = ? 
     AND epoch_id = ?
   ```
6. The transaction is committed to `ucf_ledger.db`, and the connection is closed.

### Assessment
The promotion tool **only** updates the `promotion_status` column of the `context_frames` table inside the isolated SQLite ledger (`ucf_ledger.db`). The method does **NOT** write to Qdrant, local FAISS indices, the SQLite Knowledge Graph (`knowledge_graph.db`), or the primary database (`memory.db`) during promotion.

---

## Q2 — What is the gap?

There is currently a logical disconnect between the isolated UCF ledger and the canonical retrieval layers of the system.

### Missing Updates & Touched Indices
1. **Relational and Graph Memory**: No tables in `memory.db` or `knowledge_graph.db` are updated or populated when a frame is promoted.
2. **Search Indices**: Neither the Qdrant collections nor the FAISS index files on disk are touched, updated, or synced during the promotion step.
3. **Retrieval Queries**: Any standard retrieval query targeting the system's active search endpoints (such as `POST /api/search/multimodal` or search tools in `lib/`) would **NOT** return a newly promoted frame. This is because these endpoints query the canonical `memory.db` and the main Qdrant/FAISS indices, which do not read from `ucf_ledger.db`.

### Crucial Distinction
- **Ingestion Run Vector Extraction**: Vector embeddings for context frames are generated and pushed to Qdrant or FAISS during the *ingestion phase* (`run_ingestion` / perception worker run), long before validation or human-in-the-loop promotion. The vector already exists on the vector database.
- **Searchable UCF Metadata**: The promotion step changes the frame's `promotion_status` to `'promoted'` in `ucf_ledger.db`. However, because the main retrieval layer only queries the canonical relational and vector target memory databases, the status change to `'promoted'` does not sync or make the metadata searchable in active chat/retrieval loops.

---

## Q3 — What is the minimum test shape?

To verify retrieval visibility of promoted UCF frames, we propose the following test shape:

1. **Ingest**: Call `run_ingestion` to write a test context frame containing specific visual/text metadata (e.g., `"modality": "text"`, `"payload": {"transcript": "unique_verification_token"}`) and its corresponding vector. The frame is stored with status `'staged'`.
2. **Validate**: Call `validate_ucf_frames` with HITL confirmation to transition the frame to `'validated'`.
3. **Promote**: Call `promote_ucf_to_memory` with HITL confirmation to transition the frame to `'promoted'`.
4. **Query**: Invoke the retrieval endpoint (e.g. `POST /api/search/multimodal` or calling `memory_search` with the query string `"unique_verification_token"`).
5. **Assert**: Verify that the returned search matches contains the promoted frame payload, and assert that the frame is correctly retrieved.

### Code Change Requirement
A code change is required to implement the sync/copy logic that materializes promoted UCF ledger frames into the canonical `memory.db`/`knowledge_graph.db` memory targets and registers them in the active search loop retrieval paths.
