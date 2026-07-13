<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# Active bounded mission

Roadmap item: R-05 — select the next remaining local-operator authority seam.

## Outcome

Use fresh mounted-code evidence to choose the smallest coherent unfinished
curated-mutation or process-execution repair after the verified video-summary
checkpoint. Record the selection and its ownership boundary before any new
implementation begins.

## Governing evidence

- `docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md`
- `docs/diagnostics/R05_VIDEO_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-12.md`
- `docs/releases/ROADMAP.md`

## Scope

- Re-probe only the remaining roadmap-owned curated mutations and process
  executions against current mounted code and verified MiniAgent authority.
- Name completed work first and exclude the checkpointed video-summary seam.
- Distinguish common confirmation/audit ownership from the identity
  persistence/recovery owner and the passive-status repair owner.
- Compare the remaining candidates by authority boundary, rollback/recovery
  model, UI caller, and focused verification cost.
- Update the sole roadmap if fresh evidence changes the expected order.

## Boundaries

- Read-only selection only; no route, UI, ledger, MiniAgent, identity, temporal,
  service, configuration, or data mutation.
- Do not invoke live endpoints, models, jobs, WSL, Qdrant, ingestion, or identity
  actions.
- Do not reopen governed ingest staging, route-effect/client boundaries,
  video-summary authority, or other completed checkpoints without contradictory
  evidence.
- Preserve the frozen mixed checkout, public checkout, active services, and data
  stores.

## Completion gate

One evidence-backed next seam is named with exact owner files, authority and
rollback boundary, tests required before implementation, and explicit excluded
owners. Only then may `PROJECT.md` move to that implementation mission.
