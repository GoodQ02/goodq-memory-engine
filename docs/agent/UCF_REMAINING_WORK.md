# UCF Remaining Work & Closure Plan

**Last Verified Date**: 2026-06-15  
**Document Path**: docs/agent/UCF_REMAINING_WORK.md  
**Primary Focus**: Prioritized Closure Plan for UCF Integration  

---

## 1. Overview & Context

This document outlines the prioritized closure plan to harden the Unified Context Frame (UCF) staging architecture. In alignment with the **staged-only UCF doctrine**, the UCF ledger remains a staged-only event store and must not be described or utilized as canonical promoted memory. Canonical query interfaces must only access sqlite memory projections (`memory.db`), knowledge graph nodes, and finalized Qdrant/FAISS vector databases.

The remaining work items are structured below in order of execution priority.

---

## 2. Prioritized Roadmap Items

### Item 1: Strict Promotion State Gating (blocking)
- **Goal**: Block promotion execution if any context frame records in the active epoch are in a raw `staged` state rather than a fully verified `validated` state.
- **Description**: Currently, the promotion route updates all `staged` records directly. This task implements a strict validation pre-check. The `MiniAgentClient` middleware will query the `ucf_ledger.db` for the target epoch and verify that all records have a `promotion_status` of `'validated'`. If any rows remain in `'staged'` state, the client will block the transaction and return a fatal validation error.
- **Verification Method**: Add a unit test to `tests/e2e/test_staged_ingestion_harness.py` that inserts raw staged records, triggers promotion, and asserts that it fails unless the validator has run and marked them as `'validated'`.

### Item 2: Physical Database Index Verification (hardening)
- **Goal**: Verify the physical integrity, read-safety, and ID parity of vector indexes on disk instead of relying purely on metadata table audits.
- **Description**: Expand `scripts/ucf/validate_ucf_epoch.py` to physically load FAISS index files (using the `faiss` library) and verify that the number of internal IDs, dimension metrics, and structural formats match the SQLite sidecar maps.
- **Verification Method**: Add an integration test in `tests/integration/test_ucf_vector_integrity.py` that writes a corrupted or empty index file, runs the validator in strict mode, and asserts that it registers a physical index failure.

### Item 3: Staged-to-Validated State Writer (stretch)
- **Goal**: Transition context frame database rows from `'staged'` to `'validated'` status automatically upon successful validator execution.
- **Description**: Evolve the validator runner (`validate_ucf_epoch.py`) so that when all validation rules (Raw Ref, Scene Overlap, Vector Closure) pass, the script writes a database update modifying the `promotion_status` of the corresponding `context_frames` from `'staged'` to `'validated'`.
- **Verification Method**: Run `run_validation()` on a mock database and query the table to assert that the status columns have transitioned to `'validated'`.

### Item 4: WAL Concurrency Stress under Multi-Agent Writes (hardening)
- **Goal**: Hardening of the SQLite database writes under high-concurrency multi-agent environments.
- **Description**: Build a stress harness simulating concurrent write actions from multiple perception workers. Ensure that the SQLite Write-Ahead Logging (WAL) configuration and `PRAGMA busy_timeout=5000` queueing behave deterministically without throwing `database is locked` exceptions.
- **Verification Method**: Run a multi-threaded stress-test script writing 1000 concurrent records across 10 simulation threads, asserting that 0 lock failures are recorded.
