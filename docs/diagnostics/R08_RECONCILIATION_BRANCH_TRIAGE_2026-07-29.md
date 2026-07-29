<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R08 Reconciliation Branch Triage — 2026-07-29

## Objective

Determine whether `codex/r08-reconciliation` can be integrated into current
private `dev` without repeating superseded identity work or discarding a
separate witness capability.

## Findings

| Claim | Evidence | Status |
|---|---|---|
| The branch can be merged directly | Divergence is 69 `dev` commits to 56 candidate commits; merge simulation reports 13 conflicted paths across identity, ingestion, documentation, and test surfaces. | Blocked |
| The branch's older R-08 identity lineage is missing from `dev` | The identity integration is superseded by current verified `dev` contracts. | Superseded |
| The R24 golden-witness harness is already in `dev` | The branch contains a separate golden-witness capability absent from current `dev`. | Unintegrated |
| Dirty worktree material is disposable cache | Fourteen modified files implement unpublished R24 follow-up behavior, and approximately 300 untracked witness artifacts occupy nine run roots. | Retention pending |

## Boundary

The dirty follow-up includes production-fidelity Qdrant profiles, shared
model-cache and host-tool preflight, run identifiers in evidence payloads, and
FAISS dimension corrections. These are substantive claims that require their
own contract review; they are not safe to copy, delete, or fold into the
identity branch decision.

## Decision

Do **not** merge or cherry-pick `codex/r08-reconciliation`. Preserve its
branch, dirty worktree, and witness artifacts. Reconstruct the R24
golden-witness capability as a new, dev-native bounded mission only after its
contract and artifact authority are reviewed. Do not retire this worktree.

## Exact Resume Seam

Read the R24 witness contracts and classify the fourteen dirty files one by one
against current `dev`; establish a fresh, isolated implementation branch only
for a proven missing invariant.
