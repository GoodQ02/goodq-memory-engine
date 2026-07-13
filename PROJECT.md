<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — make Qdrant query transport no-create.

## Outcome

Make `QdrantClient.query()` require an existing collection without issuing a
collection-creating PUT. Preserve explicit collection creation for write paths
such as `upsert()`.

## Governing evidence

- `docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_AUDIT_2026-07-12.md`
- `docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Split read-only collection inspection from collection creation inside
  `steps/common/qdrant_client.py`.
- Prove initial-missing and retry-missing queries never issue PUT.
- Preserve existing-collection query behavior and missing-collection upsert
  creation through focused fake-transport tests.
- Keep the mounted route-effect census and classifications unchanged.

## Boundaries

- Production scope is limited to `steps/common/qdrant_client.py` and dedicated
  focused tests after the selection-evidence checkpoint.
- Do not invoke live endpoints, Qdrant, model downloads, ingestion, identity,
  configured data roots, operator data, WSL, or active services.
- Do not change retrieval telemetry, model/cache resolution, SQLite reads,
  ingest status, summary reads, routes, response models, or route-effect
  classifications in this seam.
- Do not reopen governed staging, route/client denial, action-job, summary,
  temporal, or MiniAgent checkpoints without contradictory evidence.
- Preserve the frozen mixed checkout, public checkout, live runtime, and data
  stores.

## Completion gate

Fake-transport RED/GREEN evidence proves query-side collection creation is
impossible on initial and retry paths, existing collections still query
normally, and missing-collection upsert still creates and writes. Focused
tests, directly affected regressions, Python compilation, diff checks,
documentation gates, and independent review must pass before checkpointing.
