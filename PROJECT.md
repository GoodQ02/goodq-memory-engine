<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select the next hidden-read authority seam.

## Outcome

Run one fresh read-only comparison of the remaining hidden-read candidates and
select the smallest coherent repair by impact, exact owner, rollback boundary,
and deterministic verification cost. Do not edit production code during this
selection mission.

## Governing evidence

- `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_INGEST_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

Reconcile the current code paths and temporary-root evidence for:

- summary dashboard/entity/video/knowledge-graph SQLite reads;
- summary action-job status projection;
- retrieval-event SQLite and JSONL persistence;
- retrieval text/visual model and cache resolution; and
- retrieval FTS/provenance SQLite reads.

For each candidate, identify the mounted operations, persistent effect, exact
write owner, existing test coverage, smallest deterministic RED witness, and
whether one shared repair would cross an authority or rollback boundary.

## Boundaries

- This mission is read-only except for its selection evidence, roadmap entry,
  generated documentation indexes, and the next bounded `PROJECT.md` mission.
- Do not invoke live endpoints, Qdrant, model downloads, ingestion, identity,
  configured data roots, operator data, WSL, or active services.
- Use temporary roots, fakes, and monkeypatches only for bounded evidence.
- Do not modify retrieval, summary, model, SQLite, job-store, route-effect, or
  runtime code until one candidate is selected and checkpointed.
- Do not reopen Qdrant query or ingest-status authority without contradictory
  focused evidence.

## Completion gate

One evidence document compares all remaining candidates against fresh code and
temporary-root witnesses, records completed-work no-repeat boundaries, and
selects exactly one owner/rollback seam. The roadmap and next bounded mission
must agree. Documentation authority, drift, token, dependency, diff, and focused
documentation tests must pass before checkpointing.
