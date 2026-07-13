<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — make summary video status a lock-free passive read.

## Outcome

Split passive action-job record inspection from the writer-oriented ledger so
`GET /api/summary/video/{video_hash}/status` cannot acquire or create a lock,
create its root, or mutate persisted job state.

## Governing evidence

- `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_INGEST_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_REMAINING_HIDDEN_READ_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Add a non-creating, lock-free passive action-job reader.
- Use it for exact-ID and latest video-summary status projections.
- Preserve operation/scope filtering, ordering, response shape, and errors.
- Prove atomic-replace concurrency returns only complete old/new records.
- Retain the writer ledger, lock, transitions, reconciliation, and atomic write
  paths unchanged.

## Boundaries

- Production changes are limited to the passive action-job reader and summary
  video-status projection plus their focused tests.
- Do not invoke live endpoints, Qdrant, model downloads, ingestion, identity,
  configured data roots, operator data, WSL, or active services.
- Use temporary roots, fakes, and monkeypatches only for bounded evidence.
- Do not modify retrieval, model, SQLite, route-effect, runtime, or writer
  action-job lifecycle code.
- Do not reopen Qdrant query or ingest-status authority without contradictory
  focused evidence.

## Completion gate

Focused tests must fail first on writer-lock entry, then prove exact/latest
status reads never enter the lock or change the temp tree. Absent-root,
scope/operation filtering, atomic-replace concurrency, writer-lock controls,
route census, compilation, diff, and independent review must pass before the
implementation checkpoint.
