<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R-08 Identity Workbench Branch Reconciliation — 2026-07-29

## Decision

Do not merge or cherry-pick `codex/r08-identity-workbench` into private `dev`.
The branch is historical implementation evidence whose functional work was
absorbed and extended by `2ff63b75` (`feat(identity): integrate verified R-08
identity workbench`) and later `dev` repairs.

## Read-only topology evidence

| Ref | Commit |
| --- | --- |
| `dev` | `79f17658` at review start |
| `codex/r08-identity-workbench` | `43b3a6a5` |
| Merge base | `ed04bcaa` |
| Divergence (`dev...branch`) | 67 / 22 commits |

Neither tip is an ancestor of the other. This reflects aggregate integration,
not an unintegrated branch. The aggregate `dev` integration is larger than the
branch delta and preserves the branch's tested surfaces while adding epoch
authority, ownership guards, durable process jobs, recovery, and stronger UI
coverage.

## Why direct merge is unsafe

The read-only three-way merge simulation produced 64 conflict hunks across 12
files, including `api/routes/identity.py`, identity process/route tests,
Workbench JavaScript, fixtures, roadmap, and generated index material.

Resolving toward the older branch would regress current `dev` behavior by
replacing durable process-job ownership/recovery with synchronous subprocess
paths, losing the epoch-authority projection and mismatch UI, and weakening
exclusive face-cluster ownership protection. The branch-only diagnostic
checkpoints are historical evidence, not missing runtime functionality.

## Fresh validation on `dev`

Focused identity, process, epoch-authority, Workbench, stitching, search,
resolver, promotion, and face-cluster start-gate suites: **194 passed** (two
existing Pydantic deprecation warnings).

Live read-only checks returned `/api/status` plus all four identity GET
projections on `epoch_2026_07_05_home_memory_clean_01` with 1,648 scenes. SHA-
256 checks of the four identity artifacts were unchanged before and after those
GETs.

## Retention action

Retain the clean branch temporarily as historical evidence. A future branch
retirement may remove only its worktree/ref after the eight branch-only July
16 checkpoint documents are either intentionally retained as history or
individually incorporated under current documentation authority. Do not use
this branch as a merge source.
