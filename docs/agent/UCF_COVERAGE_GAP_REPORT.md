# UCF Coverage Gap Report

**Last Verified Date**: 2026-06-15  
**Document Path**: docs/agent/UCF_COVERAGE_GAP_REPORT.md  
**Primary Focus**: Unified Context Frame (UCF) Test Coverage Audit  

---

## 1. Executive Summary & Staged-Only Doctrine

The Unified Context Frame (UCF) is a **staged-only timeline event ledger** designed to log raw worker observations (such as timestamps, bounding boxes, OCR, and transcripts) in an isolated, epoch-scoped database. 

In strict adherence to the **staged-only UCF doctrine**:
- The UCF ledger is **not** the canonical promoted memory of the system.
- Searchable, queryable memories and semantic records must live exclusively in the canonical database targets: SQLite (`memory.db` / `knowledge_graph.db`), Qdrant multimodal collections, and FAISS vector indices.
- Staged records within the UCF ledger must be validated and explicitly promoted via an authorized gatekeeper (`MiniAgentClient`) before their data is committed to the canonical memory structures.

---

## 2. Test File Mapping (8 Files)

This section details the scope and verification logic of the 8 test files associated with the UCF.

### 1. `tests/integration/test_ucf_audio_logging.py`
- **Scope**: Verifies that raw audio transcript segment data and diarized speaker turns are logged correctly to the UCF database.
- **Verification Details**: Tests `_log_audio_to_ucf_ledger` and `_load_ucf_ledger` to confirm they write the standard schema version (`ucf.v0.1`), apply relative timestamp shifts, flat-serialize payloads, and write expected files.

### 2. `tests/integration/test_ucf_ingestion.py`
- **Scope**: Verifies database-level media source registration and basic context frame range query overlaps.
- **Verification Details**: Tests database setup in the active epoch folder, queries `media_sources` for target files (e.g. the Marine Biologist clip), and validates that the `UCFLedgerClient` queries overlapping ranges correctly.

### 3. `tests/integration/test_ucf_multi_source.py`
- **Scope**: Verifies that the validator handles multi-source media partitioning in the same epoch.
- **Verification Details**: Verifies distinct scene hashes are generated for identical time bounds across colliding scene IDs (like `scene_0000` in multiple videos). It also verifies path hygiene controls, blocking duplicate databases in the dirty staging directory.

### 4. `tests/integration/test_ucf_stress.py`
- **Scope**: Stress tests range overlap query boundary conditions and edge cases.
- **Verification Details**: Tests 11 distinct query boundary overlap scenarios (before, touching, containing, strictly inside, equal, meeting at start/end) for standard interval spans, point events (zero duration), and modality filtering.

### 5. `tests/integration/test_ucf_validator.py`
- **Scope**: Integration tests for the epoch-level validator script (`validate_ucf_epoch.py`).
- **Verification Details**: Asserts the correct functioning of validator gates (Raw Ref Gate, Scene Overlap Gate, Absolute Timestamps, Raw Reconciliation) and discretized transcript coverage report metrics (calculating silence percentage, speech detection classifications, and orphan segment detection).

### 6. `tests/integration/test_ucf_vector_integrity.py`
- **Scope**: Verifies the Phase 0.7 Vector Reference Integrity Gate.
- **Verification Details**: Asserts vector key format rules (SHA-256 vs UUID), live Qdrant payload schema validation, FAISS sidecar SQLite mapping database matching, and scoped orphan vector detection (distinguishing in-scope orphans from irrelevant historical ones).

### 7. `tests/integration/test_ucf_visual_logging.py`
- **Scope**: Integration tests for visual modality logging.
- **Verification Details**: Tests coordinate normalization standard (translating absolute pixel boundaries into `[ymin, xmin, ymax, xmax]` normalized coordinates), separate row creation for multiple objects/faces, BLIP caption/OCR logging, and DINOv2 (1024-d) / CLIP (768-d) vector registry population.

### 8. `tests/e2e/test_staged_ingestion_harness.py`
- **Scope**: End-to-end tests for the Agent-Gated Ingestion Harness.
- **Verification Details**: Exercises the `MiniAgentClient` middleware gating policies across runtime profiles (`safe`, `offline`, `unrestricted`), enforces the staged-to-promoted human-in-the-loop validation handshake (using confirmation tokens, checking expiration, reuse blocks, and operation mismatches), and verifies path sanitization on envelopes (redacting Windows drives, UNC shares, and WSL mounts).

---

## 3. Coverage Analysis vs. Architecture Roadmap

The test coverage matches major milestones described in `PROJECT.md` and related system documents:
- **Gating Middleware**: Well-covered by E2E tests validating profiles and tool blocks.
- **Envelope Sanitization**: High-density test coverage in E2E tests checking path redactions.
- **Vector Reference Integrity**: Rigorous tests for Qdrant payload parity and FAISS ID mappings.
- **Temporal Alignment**: Validated under stress range queries and overlap checks.

---

## 4. Identified Verification Gaps

While the test suites verify standard operations, two primary coverage and verification gaps have been identified:

### Gap A: Physical Database Index Verification
- **Description**: The validator checks whether FAISS vector keys and Qdrant IDs exist in the relational ledger and SQLite sidecar maps. However, it does not physically load and query the underlying FAISS index files (e.g., verifying index file readability, serialization corruption, or index format mismatches on disk) nor does it stress-test physical SQLite WAL (Write-Ahead Logging) concurrency under multiple concurrent write agents.
- **Risk**: A corrupted FAISS index or a locked relational database file under concurrent writes could pass the validator's metadata checks but fail during runtime reads.
- **Remediation**: Implement a physical index reader validator and lock-concurrency harness under simulated multi-agent write stress.

### Gap B: Promotion Status State Machine Enforcement
- **Description**: The skill documentation defines a multi-state lifecycle for context frames (`staged` -> `validated` -> `promoted`, with alternate states like `rejected` and `superseded`). However, the active runtime implementation collapses this into a binary `staged` and `promoted` transition. There is no strict state machine enforcing that only `validated` records are promoted, and there is no logic verifying transitions to `superseded` when a media range is re-ingested.
- **Risk**: Non-validated records could be promoted, and legacy runs could pollute memory instead of being marked `superseded`.
- **Remediation**: Build state gating rules in `MiniAgentClient` to block promotion of non-validated records and implement a reconciliation worker to mark old runs as `superseded`.
