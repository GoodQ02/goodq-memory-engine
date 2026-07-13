<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — make ingest-status lookup noncreating.

## Outcome

Make `IngestRequestLedger` construction side-effect-free so
`GET /api/ingest/status/{request_id}` cannot create a request directory or
missing parents. Preserve explicit storage creation in governed mutating paths.

## Governing evidence

- `docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_AUDIT_2026-07-12.md`
- `docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Remove implicit directory creation from
  `api/utils/ingest_requests.py::IngestRequestLedger.__init__`.
- Prove valid-missing and invalid request status leave an absent ledger root
  absent.
- Prove an existing seeded request and optional Watchdog projection leave the
  complete temporary tree byte-for-byte unchanged.
- Preserve governed prepare/confirm/cancel storage creation and reclassify only
  the ingest-status GET after every oracle passes.

## Boundaries

- Production scope is limited to `api/utils/ingest_requests.py`, the exact
  ingest-status registry entry in `api/route_effects.py`, and focused status or
  ledger tests.
- Do not invoke live endpoints, Qdrant, model downloads, ingestion, identity,
  configured data roots, operator data, WSL, or active services.
- Do not change governed ingest staging routes, request schemas, response
  models, cleanup policy, configured paths, retrieval, summary, identity, or
  runtime status in this seam.
- Do not reopen governed staging, route/client denial, action-job, summary,
  temporal, or MiniAgent checkpoints without contradictory evidence.
- Preserve the frozen mixed checkout, public checkout, live runtime, and data
  stores.

## Completion gate

Temporary-root RED/GREEN evidence proves valid-missing and invalid status reads
cannot create the ledger root, existing status projection changes no path,
bytes, size, or modification time, and governed request staging still creates
its durable storage. The exact GET becomes `passive_read`; the mounted census
becomes 41 passive reads and 10 automatic mutations. Focused regressions,
Python compilation, route-effect, diff, documentation, and independent review
gates must pass before checkpointing.
