<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-03 Lifecycle Transition Checkpoint Evidence

## Invariant

Each UCF lifecycle status mutation must record exact, scoped transition
evidence in the same SQLite transaction. A failed audit insert must leave no
status mutation or delivery obligation. Promotion must hold the same write lock
across its staged-frame gate, exact frame capture, status update, transition
record, and Qdrant delivery outbox enqueue.

## Checkpoint Lineage

- Branch: `codex/r03-transition-audit`
- R-02 evidence base: `5a9e9c7c`
- R-03 code checkpoint: `b9ae79f4 fix: make UCF lifecycle transitions atomic`
- R-03 status: independently reviewed, verified, and privately checkpointed

## Included R-03 Surface

- atomic validation, rejection, and supersession transitions
- exact frame IDs grouped by their true pre-transition status
- deterministic promotion frame evidence ordered by frame ID
- promotion transition insertion in the existing R-02 transaction
- staged-frame gate under `BEGIN IMMEDIATE`
- promotion status, transition, and delivery outbox rollback as one SQLite unit
- dematerialization only after active-view writes have begun
- exact `video_hash` and `epoch_id` materialization retained from R-02

## Explicit Boundaries

- No historical lifecycle event was synthesized or backfilled.
- This checkpoint proves atomic UCF status, transition, and outbox state. It
  does not claim atomicity across SQLite, active memory projections, and the
  knowledge graph.
- Post-write compensation remains video-scoped and best-effort; the focused
  test proves compensation dispatch after a real active-view write begins.
- Qdrant delivery remains post-commit through the durable R-02 outbox.
- The mixed main checkout was not staged, reset, restored, or cleaned.

## Verification Evidence

Fresh verification completed on 2026-07-11 from isolated temporary
`GOODQ_MINI_AGENT_HOME` directories. Temporary homes were removed after each
run. The two known validator report files were snapshotted and restored because
report isolation belongs to R-18.

- 8 focused transaction-boundary tests passed.
- 114 lifecycle, MiniAgent, WAL stress, multi-source, regression,
  materialization, and governance tests passed in 31.29 seconds.
- 136 R-02 non-regression plus R-03 transition tests passed in 54.23 seconds.
- Python compile passed for all four changed Python files.
- `git diff --check` passed.
- Added-line fixed-root and secret-prefix scan passed.
- Production lifecycle callers use the audited default; no
  `log_audit=False` callsite was found.
- Independent seam-only review found no checkpoint blocker.

Focused evidence covers:

- exact frame-to-prior-status mapping without omissions or duplicates
- separate truthful rows for mixed-status rejection and supersession
- idempotent repeated transitions without extra audit rows
- forced audit insert rollback
- promotion transition and R-02 outbox rollback
- a coordinated writer blocked by the promotion write lock
- exact-epoch materialization retention
- pre-materialization failure without false dematerialization
- post-write failure with compensation dispatch

## Live Ledger Preservation

The authoritative July ledger was opened read-only after the test gates. It
still contains 75,094 promoted frames and exactly one historical transition:
`staged -> validated` from `validate_ucf_frames`. It contains no historical
promotion transition. R-03 intentionally leaves that history unchanged; future
transitions use the repaired atomic path.

## Adjacent Evidence Drift

The first expanded run exposed two pre-existing harness issues that were not
imported into R-03:

- legacy integration tests expect a machine-local
  `.agents/skills/ucf-invariant-anchor/scripts/ucf_ledger.py` copy that isolated
  worktrees do not contain; the gate used and removed an ephemeral copy of the
  isolated canonical ledger
- `tests/integration/test_ucf_ingestion.py` resolves a stale 2025 epoch and is
  not a hermetic R-03 test; its authority/config drift remains assigned to
  R-09/R-13

Neither issue changes the R-03 transaction result, and neither was hidden as a
passing live witness.

## Resume

Update the master roadmap in the dedicated foundational-documentation seam,
then continue R-17 extraction of the frozen mixed main checkout. Do not fold
current-state reconstruction or unrelated documentation cleanup into this
checkpoint.
