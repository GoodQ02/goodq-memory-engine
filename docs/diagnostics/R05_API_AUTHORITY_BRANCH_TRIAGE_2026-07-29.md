<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R05 API Authority Branch Triage — 2026-07-29

## Objective

Decide whether `codex/r05-api-authority` contributes an unintegrated, safe
change to private `dev`, without altering its dirty worktree or runtime data.

## Authority Surfaces Checked

- Current private authority: `dev` at `8f874fb3`, clean and synchronized with
  `origin/dev`.
- Candidate: `codex/r05-api-authority` at `4e1275fb`; common base
  `ed04bcaa`.
- Candidate commit series, candidate local diff, `git merge-tree`, and
  whitespace diagnostics.
- Current identity integration commit `2ff63b75` and the focused current
  identity test surface.

## Separate Findings

| Claim | Evidence | Status |
|---|---|---|
| Branch commits are already represented by current development | The candidate's seven R-08 seams are included and extended by `2ff63b75` and later `dev` work. | Superseded |
| Direct merge is mechanically unsafe | Merge simulation reports 55 conflict hunks across `api/routes/identity.py`, `tests/conftest.py`, the roadmap, and generated file index; seven paths changed on both sides. | Blocked |
| Candidate local UI changes are safe to transfer | Three changed UI assets predate the current confirmation, epoch-authority, ownership, and evidence contracts; the JS issues direct mutation calls and omits required scoped confirmation handling. | Rejected |
| Candidate helper scripts are product tooling | `check_ids.py` checks only DOM identifier presence; `patch.py` performs broad non-idempotent string and regex rewrites. | Rejected |

## Local Worktree Boundary

The candidate worktree has five uncommitted files: three Identity Workbench UI
assets and `check_ids.py` plus `patch.py`. They were inspected read-only and
remain untouched. They are historical scratch, not approval to reset, delete,
archive, stage, or merge the worktree.

## Decision

Do **not** merge or cherry-pick `codex/r05-api-authority`, including its local
UI changes. Current `dev` is the verified superset and is the only product
authority. This decision does not retire the branch or remove its worktree;
that is a separate, explicit retention decision after its local changes have
been preserved or otherwise dispositioned by the operator.

## Current Verification Evidence

The branch-oriented current-`dev` identity gate passed 69 tests. A selected
MiniAgent identity-and-stitch gate passed 65 tests with 202 intentionally
deselected. These prove the current contract; they do not make the historical
branch a merge candidate.

## Do Not Repeat

- Do not re-run the R-08 implementation or attempt a trial merge to establish
  equivalence.
- Do not use `patch.py` to regenerate the UI.
- Do not delete or reset the candidate worktree as part of this triage.

## Exact Resume Seam

Apply the same read-only triage to the remaining preserved worktrees. Any
candidate that appears useful must first identify a concrete missing invariant
in current `dev`; only that invariant may be transferred with a current test.
