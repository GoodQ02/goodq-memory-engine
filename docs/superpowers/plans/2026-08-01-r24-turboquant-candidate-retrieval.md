<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: HISTORICAL_REFERENCE -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# R-24 TurboQuant Candidate Retrieval Implementation Plan

> **Execution status (2026-08-02):** Historical experiment record. The
> candidate did not meet the performance gate; it is not enabled for active
> retrieval or authorized for corpus re-ingestion.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Prove a non-promoting TurboQuant retrieval route is baseline-equivalent before another family-media ingest.

**Architecture:** Normal `FaissMemory.query` remains authoritative. Only a sealed R-24 candidate may use its own SQLite sidecars to choose a candidate pool, then exactly rerank that pool from the same candidate's full vectors. Any incomplete sidecar, database problem, or comparison error falls back to normal FAISS.

**Tech Stack:** Python, SQLite read-only authority, NumPy, FAISS, pytest.

## Constraints

- No new media ingestion during implementation or benchmark work.
- Candidate activation requires isolation, promotion disabled, an explicit active-retrieval flag, and database containment under the witness root.
- The control epoch stays unchanged. No source media, transcript, embedding, or raw query text is written to Git or benchmark receipts.
- A pass requires exact final top-K IDs and scores within floating-point tolerance, zero fallback, and median active latency no slower than baseline.

## Task 1: Gate active retrieval to a sealed candidate

**Files:**
- Modify: `steps/common/memory_stores.py`
- Test: `tests/unit/test_retrieval_sqlite_read_authority.py`

- [ ] Add a failing test proving active TurboQuant is refused unless all four conditions are true: `ingestion_isolation`, `promotion_enabled is False`, `allow_turboquant_active_retrieval`, and a candidate SQLite database contained below `artifact_root`.
- [ ] Run `pytest tests/unit/test_retrieval_sqlite_read_authority.py -q` and confirm RED.
- [ ] Add `_turboquant_active_allowed(cfg, db_path)` to enforce that exact allowlist and reject malformed paths without raising into normal retrieval.
- [ ] Run the same test and confirm GREEN.

## Task 2: Candidate-side approximate pool with exact rerank

**Files:**
- Modify: `steps/common/memory_stores.py`
- Test: `tests/unit/test_retrieval_sqlite_read_authority.py`

- [ ] Add failing tests for three cases: exact candidate final ranking equals baseline, an incomplete sidecar causes a normal FAISS fallback, and malformed candidate SQLite causes a normal FAISS fallback.
- [ ] Run `pytest tests/unit/test_retrieval_sqlite_read_authority.py -q` and confirm RED.
- [ ] Implement a private candidate query path that opens only `memory.db` in SQLite read-only mode, reads same-dimension complete sidecars, estimates a pool of at least `top_k`, and exactly reranks that pool using authoritative full vectors from the same database.
- [ ] Preserve existing result semantics and attach only non-sensitive route provenance for the benchmark. Catch every active-route failure, emit one warning, and call the unchanged FAISS path.
- [ ] Run `pytest tests/unit/test_retrieval_sqlite_read_authority.py tests/unit/test_turboquant.py -q` and confirm GREEN.

## Task 3: Fixed query-pack A/B benchmark and existing-scene receipt

**Files:**
- Create: `cli/turboquant_candidate_benchmark.py`
- Create: `tests/unit/test_turboquant_candidate_benchmark.py`
- Modify: `cli/golden_witness.py`

- [ ] Add failing benchmark tests that build queries from candidate vectors only: one self-query per stored vector and one cross-vector query for each modality with at least two vectors. Tests must reject raw query strings and canonical paths.
- [ ] Run `pytest tests/unit/test_turboquant_candidate_benchmark.py -q` and confirm RED.
- [ ] Implement a receipt-only benchmark that runs baseline FAISS and the gated active route over the fixed pack, stores aggregate counts, latency summaries, ID/score agreement, fallback count, and pass/fail under the existing witness root.
- [ ] Extend the sealed candidate snapshot with `witness.allow_turboquant_active_retrieval: true`; do not enable active retrieval for normal runs.
- [ ] Run `pytest tests/unit/test_turboquant_candidate_benchmark.py tests/unit/test_retrieval_sqlite_read_authority.py tests/unit/test_turboquant.py -q` and confirm GREEN.
- [ ] Run the benchmark once against the completed isolated scene root. Do not create collections, ingest media, or modify the control epoch.

## Final verification

- [ ] Run `git diff --check` and `git status --short`.
- [ ] Verify the receipt is under the candidate witness root and contains aggregate evidence only.
- [ ] Report the gate outcome: pass means the one-scene active route is eligible for the next separately approved movie; fail means stop with the control epoch preserved.
