<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R22 Hermes Branch Triage — 2026-07-29

## Objective

Determine whether `codex/r22-hermes-goodq` contains a safe, missing Hermes
runtime improvement and whether it may be merged directly.

## Findings

| Claim | Evidence | Status |
|---|---|---|
| The branch can be merged directly | It is 69 commits behind and 24 ahead; 20 candidate-only commits are inherited R-08 identity work. Merge simulation has 12 changed-or-added-on-both-sides paths. | Rejected |
| Hermes routing behavior is already in `dev` | Four commits are Hermes-only and current `dev` does not yet provide their model selection and request-options behavior. | Selective transfer candidate |
| The Hermes delta can be mechanically applied to `dev` | The reduced four-commit patch applies with `git apply --check`. | Mechanically ready, unproven on `dev` |
| Relevant behavior has a test surface | Candidate suite passed 30 tests; current `dev` LLM and temporal guard suite passed 127 tests with two existing Pydantic warnings. | Evidence available |

## Decision

Do **not** merge or cherry-pick the historical branch as a whole. The only
candidate for future work is the four-commit Hermes-only delta:

- `ed72aacd`
- `38551ba2`
- `b89d3c5c`
- `547ffcbd`

Port that delta into a fresh dev-native seam, review it as one routing contract,
and run both the candidate's 30 tests and current `dev` guards before seeking a
merge decision. This triage does not change Hermes configuration or runtime
selection.

## Exact Resume Seam

Open a bounded Hermes routing implementation task. First compare the reduced
patch with the current LLM contract, then write or adapt focused tests on a
fresh branch. Do not use the R22 branch as a merge vehicle.
