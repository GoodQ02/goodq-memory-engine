# UCF Remaining Work & Closure Plan

**Last Verified Date**: 2026-06-15
**Last Updated**: 2026-06-15 (post-sprint update)
**Document Path**: docs/agent/UCF_REMAINING_WORK.md
**Primary Focus**: Prioritized Closure Plan for UCF Integration

---

## 1. Overview & Context

This document outlines the prioritized closure plan to harden the Unified Context Frame (UCF) staging architecture. In alignment with the **staged-only UCF doctrine**, the UCF ledger remains a staged multimodal evidence store. Canonical query interfaces must only access sqlite memory projections (`memory.db`), knowledge graph nodes, and finalized Qdrant/FAISS vector databases.

The full confirmed lifecycle as of 2026-06-15 sprint:

```
ingestion → staged
          → [validate_ucf_frames, HITL-confirmed] → validated
          → [promote_ucf_to_memory, HITL-confirmed] → promoted
```

`validate_ucf_epoch.py` remains read-only. No bypass lever exists.

---

## 2. Prioritized Roadmap Items

### Item 1: Strict Promotion State Gating ✅ COMPLETED (2026-06-15)
- **Goal**: Block promotion if any in-scope frames remain in `staged` status.
- **Implementation**: `agents/mini_agent_client.py` — `_execute_promote_ucf_to_memory()` now performs a pre-check that counts `staged` frames in scope. Any `staged` frames block the operation with `reason: promotion_blocked_unvalidated_frames`. Promotion SQL corrected from `staged → promoted` to `validated → promoted`.
- **Evidence**: `tests/agents/test_mini_agent_client.py::test_promote_ucf_blocked_when_frames_staged` (PASS), `test_promote_ucf_succeeds_when_frames_validated` (PASS). 728/728 suite.
- **Commit**: `7ea42b98`

### Item 2: Physical Database Index Verification ✅ COMPLETED (prior sprint)
- **Goal**: Verify physical integrity of FAISS index files on disk.
- **Implementation**: `scripts/ucf/validate_ucf_epoch.py` lines 798–818 — physically loads FAISS index via `faiss.read_index()` and verifies ID map. `validate_ucf_epoch.py` remains strictly read-only.
- **Evidence**: `tests/integration/test_ucf_vector_integrity.py` (PASS).

### Item 3: Staged-to-Validated State Writer ✅ COMPLETED (2026-06-15)
- **Goal**: Provide a deliberate, gated write path from `staged` to `validated`.
- **Implementation**: `scripts/ucf/ucf_ledger.py` — `mark_frames_validated(video_hash, epoch_id)` method added. `agents/mini_agent_client.py` — `validate_ucf_frames` tool registered with HITL confirmation gate at the same level as `promote_ucf_to_memory`. `validate_ucf_epoch.py` was **not** modified — it remains read-only. The state write is an explicit separate tool call, not automatic.
- **Design decision**: The validator does not auto-mutate statuses. The `validate_ucf_frames` tool is the deliberate confirmation step between validation and promotion.
- **Evidence**: `tests/agents/test_mini_agent_client.py::test_validate_ucf_frames_transitions_staged_to_validated` (PASS, includes idempotency check).
- **Commit**: `7ea42b98`

### Item 4: WAL Concurrency Stress under Multi-Agent Writes ✅ COMPLETED (2026-06-15)
- **Goal**: Prove SQLite WAL handles simultaneous multi-agent writes without data loss.
- **Implementation**: `tests/integration/test_ucf_stress.py` — `TestUCFWALConcurrency` class with two tests: 8-thread × 10-frame no-data-loss (exact 80-row count assertion) and 8-client retry contention (exact 8-row count, zero `OperationalError` escape).
- **Evidence**: Both tests PASS. Real bug caught during implementation: shared `sqlite3` connections cannot cross thread boundaries — each worker must own its connection, which the tests now document and enforce.
- **Commit**: `7ea42b98`

---

## 3. Remaining Open Items

### Item 5: `rejected` and `superseded` Status Write Paths (hardening)
- **Goal**: Provide write paths for the `rejected` and `superseded` promotion statuses defined in the UCF schema.
- **Status**: Defined in schema (`context_frames.promotion_status` allows `rejected`, `superseded`) but no write method exists in `UCFLedgerClient` and no production code sets these values.
- **Risk**: Medium — re-ingestion of a previously promoted scene has no way to mark prior frames as `superseded`, creating ambiguous state.
- **Recommended next action**: Add `mark_frames_rejected(reason, video_hash, epoch_id)` and `mark_frames_superseded(video_hash, epoch_id)` to `UCFLedgerClient`. Gate via `MiniAgentClient` tools. Add tests.
- **Acceptance criteria**: Both states are settable via confirmed tool calls. A test asserts that re-ingesting an already-promoted epoch transitions the old frames to `superseded` before the new frames are staged.

### Item 6: Laptop Follower / Portable Validation (pending)
- **Goal**: Validate that the installer and pipeline run correctly on the secondary laptop host.
- **Status**: Pending — no evidence of a completed laptop test run found.
- **Risk**: Low urgency, high value for mobility.
- **Recommended next action**: Run `scripts/install_pipeline_wsl.py` on laptop and verify `conda run -n goodq_core pytest -q` passes.

### Item 7: Watchdog Progressive Chunk Validation (pending — documented only)
- **Goal**: Watchdog validates ingestion progressively per chunk rather than only at epoch boundary.
- **Status**: Described in `docs/systems/WATCHDOG_SYSTEM.md` — implementation status needs evidence verification.
- **Risk**: Medium — if absent, epoch-boundary-only validation misses mid-run failures.
- **Recommended next action**: Audit `lib/watchdog/` for progressive chunk trigger logic. If absent, file as a hardening item.

### Item 8: Search Blending / Hybrid Search Validation (pending — unknown)
- **Status**: No evidence of implementation found in `lib/` or `scripts/`. Appears to be a planned feature.
- **Risk**: Low — retrieval works via Qdrant single-modality today.
- **Recommended next action**: Confirm intended design in architecture docs; mark as stretch if not yet designed.
