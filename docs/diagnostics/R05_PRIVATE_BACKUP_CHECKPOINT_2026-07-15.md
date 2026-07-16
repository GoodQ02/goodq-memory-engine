<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-15 -->

# R-05 Private Backup Checkpoint

## Purpose

This document freezes the known private backup point for the R-05 authority
lineage before any gate-repair work. It is evidence, not an approval to merge
into `dev`.

## Exact checkpoint

| Field | Value |
|---|---|
| Branch | `codex/r05-api-authority` |
| Checkpoint commit before this document | `d7033600dc04ab8a8605ae7d990b37e8711c8dbe` |
| Private remote | `origin` (`JoesDomingo/goodq4all`) |
| Remote backup ref | `origin/codex/r05-api-authority` |
| Private `dev` baseline | `origin/dev` at `b29390b6ef2886ddbbf4ed414bef0e7bb21dc1e7` |
| Relationship | `origin/dev` is an ancestor; R-05 is 185 commits ahead |

After this document is committed, the annotated tag
`checkpoints/r05-api-authority-2026-07-15` will identify the documented
checkpoint commit. The tag and branch are private backup surfaces; neither is a
release authority.

## Git metadata repair evidence

- `refs/remotes/origin/HEAD` was repaired from the nonexistent `origin/public`
  to `origin/dev`.
- The shared commit graph was rebuilt with reachable commits and changed-path
  data.
- `git commit-graph verify` passed.
- `git fsck --connectivity-only --no-dangling HEAD origin/dev` passed.
- Graph-disabled connectivity verification also passed.
- Reachable-object enumeration reported zero missing objects.
- The R-05 worktree was clean before documentation was added.

## Private integrated-gate evidence at checkpoint

Passed:

- Focused agent/API-authority/retrieval/summary/temporal/governance suite:
  `3794 passed, 1 skipped`.
- Integration suite: `87 passed, 5 skipped`.
- Python compilation for the covered source and test tree.
- JavaScript syntax checks for three changed JavaScript files.
- Documentation drift lint.
- Banned-token lint.
- Dependency-drift lint.
- Runtime-path authority audit.

Not green yet:

- Deterministic failure in
  `tests/unit/test_ucf_promotion_cli.py::test_concurrent_execute_processes_claim_confirmation_token_once`.
- Full collection reports three dynamic-import errors in the search-route test
  modules.
- `scripts/docs/doc_authority_lint.py verify` reports one index drift in
  `docs/reference/indexes/AGENT_FILE_INDEX.md`.
- Branch-range diff checking reports four trailing-whitespace lines in
  `tests/agents/test_mini_agent_client.py`.
- Browser/UI audit fails when the live search witness does not produce a
  `.scene-card.matched` result for the fixed query.

Therefore R-25 remains open and this checkpoint is **no-merge** evidence.

## Preservation rules

- Do not reset, clean, or broad-stage the mixed main checkout.
- Do not re-run completed ingestion, promotion, or R-05 implementation work.
- Do not mutate this tag after it is pushed.
- Perform gate repairs in a new isolated worktree derived from this checkpoint.
- Update `docs/releases/ROADMAP.md` only when a stated gate has fresh evidence.
- Merge into private `dev` only after the private integrated gate is green.

## Exact resume seam

Create a fresh repair worktree from this tag and address the gate blockers one
at a time, beginning with the deterministic UCF promotion concurrency failure.
Re-run the focused gate, then the full private gate, before any merge decision.
