# UCF Coverage Gap Report

**Last Verified Date**: 2026-06-15
**Last Updated**: 2026-06-15 (Phase 0.8 sync)
**Document Path**: docs/agent/UCF_COVERAGE_GAP_REPORT.md
**Primary Focus**: Unified Context Frame (UCF) Test Coverage Audit

---

## 1. Executive Summary & Staged-Only Doctrine

The Unified Context Frame (UCF) is a **staged multimodal evidence ledger** that logs raw
worker observations (timestamps, bounding boxes, OCR, transcripts) in an isolated,
epoch-scoped database.

In strict adherence to the **staged-only UCF doctrine**:
- The UCF ledger is **not** the canonical promoted memory of the system.
- Searchable, queryable memories must live exclusively in canonical targets: SQLite
  (`memory.db` / `knowledge_graph.db`), Qdrant multimodal collections, and FAISS indices.
- Staged records must be validated and explicitly promoted via an authorized gatekeeper
  (`MiniAgentClient`) before their data is committed to canonical memory structures.
- `validate_ucf_epoch.py` is and must remain **strictly read-only**. It never writes
  promotion_status or any other column.

**Confirmed full lifecycle (Phase 0.8):**
```
ingestion   → staged
             → [validate_ucf_frames, HITL-confirmed]  → validated
             → [promote_ucf_to_memory, HITL-confirmed] → promoted

re-ingestion → [supersede_ucf_frames, HITL-confirmed] → superseded (old epoch)
             → staged (new epoch) → validated → promoted

explicit rejection → [reject_ucf_frames, HITL-confirmed] → rejected
```

---

## 2. Test File Mapping (9 Files)

### 1. `tests/integration/test_ucf_audio_logging.py`
- **Scope**: Verifies raw audio transcript segment data and diarized speaker turns are
  logged correctly to the UCF database.
- **Verification Details**: Tests `_log_audio_to_ucf_ledger` and `_load_ucf_ledger` for
  schema version, timestamp shifts, flat-serialized payloads, and raw file writes.

### 2. `tests/integration/test_ucf_ingestion.py`
- **Scope**: Database-level media source registration and basic context frame range queries.
- **Verification Details**: Tests database setup in the active epoch folder, queries
  `media_sources`, and validates `UCFLedgerClient` range overlap queries.

### 3. `tests/integration/test_ucf_multi_source.py`
- **Scope**: Validator behavior with multi-source media in the same epoch.
- **Verification Details**: Distinct scene hashes for identical time bounds across
  colliding scene IDs; path hygiene controls blocking duplicate databases.

### 4. `tests/integration/test_ucf_stress.py`
- **Scope**: Range overlap query stress tests AND WAL concurrency tests (Phase 0.7 + 0.8).
- **Verification Details**: 11 query boundary overlap scenarios; `TestUCFWALConcurrency`
  proves 8-thread × 10-frame no-data-loss (exact 80-row count) and 8-client retry
  contention (exact 8-row count, zero `OperationalError` escape) — commit `7ea42b98`.

### 5. `tests/integration/test_ucf_validator.py`
- **Scope**: Integration tests for `validate_ucf_epoch.py`.
- **Verification Details**: Raw Ref Gate, Scene Overlap Gate, Absolute Timestamps, Raw
  Reconciliation gates, and discretized transcript coverage metrics.

### 6. `tests/integration/test_ucf_vector_integrity.py`
- **Scope**: Phase 0.7 Vector Reference Integrity Gate.
- **Verification Details**: SHA-256 vs UUID vector key rules, Qdrant payload schema,
  FAISS sidecar mapping, scoped orphan vector detection.

### 7. `tests/integration/test_ucf_visual_logging.py`
- **Scope**: Visual modality logging.
- **Verification Details**: Coordinate normalization, multi-object rows, BLIP/OCR
  logging, DINOv2 (1024-d) and CLIP (768-d) vector registry population.

### 8. `tests/e2e/test_staged_ingestion_harness.py`
- **Scope**: End-to-end tests for Agent-Gated Ingestion Harness.
- **Verification Details**: `MiniAgentClient` policy profiles, HITL confirmation token
  handshake (expiration, reuse blocks, operation mismatches), envelope path sanitization.

### 9. `tests/agents/test_mini_agent_client.py`
- **Scope**: Unit + lifecycle tests for `MiniAgentClient` (Phase 0.7 + 0.8).
- **Verification Details**: Policy gating (safe/offline/unrestricted), native tool
  dispatch, HITL confirmation flow, fallback determinism, traceback sanitization,
  complete staged → validated → promoted lifecycle with DB verification and idempotency,
  rejected/superseded terminal states, promotion exclusion of terminal frames,
  re-ingest supersession flow, tool registry completeness matrix, offline fallback
  denial tests for subprocess-only tools.

---

## 3. Coverage Analysis vs. Architecture Roadmap

| Contract | Coverage | Notes |
|---|---|---|
| Gating middleware (safe/offline/unrestricted profiles) | ✅ High | E2E + unit tests |
| HITL confirmation token (expiry, reuse, mismatch) | ✅ High | E2E tests |
| Envelope path sanitization | ✅ High | E2E tests |
| Vector reference integrity (Qdrant + FAISS) | ✅ High | Integration tests |
| WAL concurrency — no data loss | ✅ High | Stress tests (Phase 0.7) |
| staged → validated → promoted lifecycle | ✅ High | Unit tests + DB verify (Phase 0.7) |
| rejected / superseded terminal states | ✅ High | Unit tests + DB verify (Phase 0.8) |
| Promotion exclusion of rejected/superseded | ✅ High | Unit tests (Phase 0.8) |
| Audit trail for all status transitions | ✅ High | Unit tests (Phase 0.8) |
| Tool registry completeness | ✅ High | Matrix test (Phase 0.8) |
| Offline fallback denial for subprocess tools | ✅ Medium | Unit tests (Phase 0.8) |

---

## 4. Identified Verification Gaps — Status

### Gap A: Physical Database Index Verification ✅ RESOLVED (Phase 0.7)
- **Resolution**: `validate_ucf_epoch.py` lines 798–818 now physically loads FAISS index
  via `faiss.read_index()` and verifies the ID map. WAL concurrency proved by
  `TestUCFWALConcurrency` in `test_ucf_stress.py`.
- **Evidence**: `tests/integration/test_ucf_vector_integrity.py` (PASS), commit `7ea42b98`.

### Gap B: Promotion Status State Machine Enforcement ✅ RESOLVED (Phase 0.7 + 0.8)
- **Resolution**:
  - Phase 0.7 (`7ea42b98`): `validate_ucf_frames` tool (HITL-gated) transitions
    `staged → validated`. `promote_ucf_to_memory` pre-check blocks if any staged frames
    remain. Promotion SQL corrected to `validated → promoted`.
  - Phase 0.8: `reject_ucf_frames` and `supersede_ucf_frames` tools implement terminal
    state transitions. Rejected/superseded frames are excluded from promotion scope.
    All transitions logged to `ucf_status_transitions` audit table.
- **Evidence**: `tests/agents/test_mini_agent_client.py` lifecycle tests (all PASS).

---

## 5. Open Coverage Items (Phase 0.8+)

### Gap C: VECTOR_REGISTRY Covers Only 2 of ~8 Worker Types (hardening)
- **Description**: `validate_ucf_epoch.py` `VECTOR_REGISTRY` is hard-coded to
  `image_embed_dino` and `image_embed_clip`. Workers like `audio_embed_clap`,
  `text_embed`, `face_embed` with vector keys are classified as unregistered errors
  rather than contract-validated with typed dimension and collection checks.
- **Risk**: Medium — vector integrity gate is weaker for audio and text modalities.
- **Remediation**: Extend `VECTOR_REGISTRY` to cover all vector-producing workers.

### Gap D: Offline Fallback Tests for Subprocess-Only Tools (hardening)
- **Description**: Only `home_assistant_call_service` has an offline fallback denial
  test. Tools like `kg_write`, `faiss_write`, `config_write` are declared in
  `MUTATING_DENY_ON_AGENT_FAILURE` but have no test verifying denial when agent offline.
- **Risk**: Low — the policy machinery is shared, but coverage is asymmetric.
- **Status**: Partially resolved in Phase 0.8 (`kg_write`, `faiss_write`, `config_write`
  offline denial tests added). `watchdog_trigger`, `process_start`, `process_stop` remain.

### Gap E: Search Blending / Hybrid Search (informational)
- **Status**: Completely absent — no implementation in `lib/` or `scripts/`.
  Single-modality Qdrant query and single-index FAISS search only.
- **Risk**: Informational only — not a current production requirement.
