<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05 — select the next remaining local-operator authority seam.

## Outcome

Use fresh mounted-code evidence to choose the smallest coherent unfinished
curated-mutation or process-execution repair after the verified
summary-collection checkpoint. Record the selection and its ownership boundary
before any new implementation begins.

## Governing evidence

- `docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md`
- `docs/diagnostics/R05_VIDEO_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-12.md`
- `docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Re-probe only the remaining roadmap-owned curated mutations and process
  executions against current mounted code and verified MiniAgent authority.
- Name completed work first and exclude governed ingest staging, the common
  route/client boundary, video-summary authority, and summary-collection
  authority.
- Distinguish common authority ownership from the separate identity-persistence,
  passive-status, and nominal-read-mutation owners.
- Compare remaining candidates by exact effect, durable result/recovery model,
  UI caller, authority boundary, rollback boundary, and focused verification
  cost.
- Update the sole roadmap if fresh evidence changes the expected order.

## Boundaries

- Read-only selection only; no route, UI, ledger, MiniAgent, identity, temporal,
  service, configuration, documentation-authority, or data mutation.
- Do not invoke live endpoints, models, jobs, WSL, Qdrant, ingestion, identity,
  or operator data.
- Do not reopen completed checkpoints without contradictory evidence.
- Preserve the frozen mixed checkout, public checkout, active services, and data
  stores.

## Completion gate

One evidence-backed next seam is named with exact owner files, authority,
durable-result and rollback boundaries, focused tests required before
implementation, and explicit excluded owners. Only then may `PROJECT.md` move
to that implementation mission.
