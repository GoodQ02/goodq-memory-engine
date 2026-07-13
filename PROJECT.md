<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — isolate summary SQLite read authority.

## Outcome

Make summary dashboard/entity/video projections incapable of creating a missing
database or executing DDL/DML while preserving truthful visibility of committed
rows that still reside in a live WAL.

## Governing evidence

- `docs/diagnostics/R05_F1_SUMMARY_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_MODEL_CACHE_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_MODEL_CACHE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Live committed WAL truth outranks byte-identical SQLite sidecar purity. A
read-only projection may participate in SQLite's required WAL coordination, but
it must not create an absent database or possess DDL/DML capability.

## Scope

- Trace only summary SQLite projections and their mounted summary callers.
- Add mutation-sensitive temporary SQLite witnesses before production changes.
- Require absent-path no-create, URI read-only mode, `PRAGMA query_only=ON`,
  rejected DDL/DML, and visibility of committed uncheckpointed WAL rows.
- Reuse one narrowly owned summary read primitive only where the focused trace
  proves the same contract.

## Boundaries

- Do not repeat the completed Windows SQLite comparison or model-cache repair.
- Do not change retrieval SQLite, retrieval telemetry, Qdrant, action-job
  lifecycle, route effects, response contracts, dependencies, or runtime
  packages.
- Do not invoke configured databases, live endpoints, Qdrant, models, ingestion,
  identity, WSL, public checkout, or the mixed main checkout.
- Use temporary SQLite databases and focused tests only.

## Completion gate

The current write-capable summary connection must fail the focused RED. The
corrected reader must prove absent-path no-create, live-WAL visibility, DDL/DML
rejection, bounded close behavior, unchanged response semantics, focused route
regressions, diff checks, and independent review before checkpoint.
