<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05 — govern temporal-summary execution and durable result truth.

## Outcome

Replace the direct synchronous temporal-summary process execution with one
strictly scoped MiniAgent-confirmed job, private exact-job result authority,
deterministic restart truth, passive result retrieval, and truthful Retro
Console polling.

## Governing evidence

- `docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md`
- `docs/diagnostics/R05_VIDEO_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-12.md`
- `docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Strictly normalize and digest every accepted request field; bind confirmation
  to job, epoch, request digest, and sanitized execution-policy digest.
- Persist `pending_confirmation` before token issue and permit no retrieval,
  client construction, health probe, service activation, or model call before
  exact confirmation is claimed.
- Require confirm to resubmit the complete normalized request, pass one
  immutable request copy to the worker, and revalidate epoch plus execution
  policy from one shared configuration snapshot before retrieval.
- Execute asynchronously through the existing action-job lifecycle and persist
  one locked atomic exact-job result under the configured private data root
  before terminal ledger truth.
- Add passive exact-job result projection and deterministic startup
  reconciliation without silent inference retry.
- Migrate Retro Console to explicit confirm, exact resubmission, token clearing,
  and durable terminal-state polling.
- Implement by TDD against temporary roots and mocked model/process boundaries.

## Boundaries

- Production ownership is limited to `agents/mini_agent_client.py`,
  `api/routes/search.py`, `retrieval/narrative_summarizer.py`, the narrow
  verified-snapshot seam in `retrieval/temporal_reasoning.py`, new
  `api/utils/temporal_summary_results.py`,
  `ui/retro_console_v1/static/js/retro.js`, and the new passive operation in
  `api/route_effects.py`.
- Reuse `api/utils/action_jobs.py` unchanged unless a failing regression proves
  a generic defect. Treat `lib/llm_client.py` as inspect-only unless the caller
  cannot enforce the confirmed execution policy.
- Do not invoke live endpoints, models, jobs, WSL, Qdrant, ingestion, identity,
  operator data, or the configured data root. Tests use temporary roots and
  mocked process/model boundaries only.
- Do not reopen completed checkpoints without contradictory evidence.
- Preserve the frozen mixed checkout, public checkout, active services, and data
  stores.

## Completion gate

Focused tests prove exact confirmation, no pre-confirm execution, atomic result
integrity, truthful audit/terminal ordering, deterministic restart recovery,
passive exact-job reads, UI token disposal and durable-state rendering, outward
redaction, and unchanged common route/client authority. Then the inherited
integrated authority, compilation, JavaScript, route-effect, secret, path, diff, and
documentation gates pass before a private checkpoint.
