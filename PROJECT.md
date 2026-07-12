<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# Active bounded mission

Roadmap item: R-05 — govern video-summary generation as one durable confirmed
job.

## Outcome

Replace process-local video-summary dispatch/status with one exact-scope,
single-use confirmed job whose durable lifecycle and generic audit evidence make
worker success, failure, duplication, and restart recovery truthful to the API
and Summary Console.

## Scope

- Extend the verified MiniAgent authorization-only boundary for one normalized
  video-summary generation operation; do not create another token store.
- Add one generic locked, atomic action-job ledger, exercised only by video
  summary in this seam, and create a pending-confirmation record before token
  issuance.
- Record external worker outcomes through the existing generic tool-audit
  authority; do not create a second audit log.
- Narrow scene-summary and provenance inputs to the confirmed video and preserve
  truthful LLM-versus-template outcome metadata.
- Make generate/status responses use a durable job identifier and explicit
  lifecycle states.
- Align Summary Console confirmation, dispatch, polling, success, failure, and
  recovered/stale copy with the durable record.
- Add focused route, worker, authority, recovery, redaction, audit, and UI
  contract tests before broader verification.

## Governing invariants

- Exact operation and complete normalized scope are confirmed once and consumed
  once before the job enters `queued` or any worker side effect occurs.
- The pending-confirmation job exists before token issuance and is lifecycle
  state only; MiniAgent remains the decision/execution audit authority.
- Confirmed target-video scope bounds every scene-summary and provenance input.
- Missing process-local state never implies success. Only durable `succeeded`
  state may be shown as successful.
- Duplicate dispatch, worker failure, process restart, persistence failure, and
  audit failure remain visible and deterministic.
- The mounted route remains `process_execution` and the completed common
  loopback/client boundary remains fail-closed.

## Boundaries

- Do not change temporal summarization, identity routes or storage, passive
  status probes, ingestion, supervision, LAN/gateway policy, or live data.
- Do not call the live generation route, start a model or job, or exercise a
  real media hash.
- Use isolated temporary roots and injected workers/authorities in tests.
- Do not reopen completed staging, route-effect, common client-boundary,
  handler-truth, or documentation-authority seams without contradictory
  evidence.
- Preserve the frozen mixed checkout, public checkout, services, and data stores.

## Resume authority

Use `docs/releases/ROADMAP.md` as the sole long-running register and
`docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md` as the
selection evidence for this one implementation seam.
