<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select the next remaining hidden-effect repair.

## Outcome

Reconcile the remaining retrieval and summary SQLite effects using fresh
read-only evidence, then select one exact owner, rollback boundary, and
mutation-sensitive RED oracle before another production edit.

## Governing evidence

- `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_INGEST_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_REMAINING_HIDDEN_READ_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_SUMMARY_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Compare retrieval telemetry, text/visual model and cache resolution,
  retrieval SQLite reads, and summary SQLite projections.
- Re-probe each candidate with temporary roots, fakes, and monkeypatches only.
- Name the exact persistent or external effect, owner, rollback boundary, and
  smallest deterministic RED witness for each candidate.
- Select one seam using current authority, risk, and dependency evidence.
- Checkpoint the selection before production implementation begins.

## Boundaries

- This mission is read-only except for its selection evidence, roadmap entry,
  active bounded mission, and regenerated documentation indexes.
- Do not invoke live endpoints, Qdrant, model downloads, ingestion, identity,
  configured data roots, operator data, WSL, or active services.
- Use temporary roots, fakes, and monkeypatches only for bounded evidence.
- Do not modify retrieval, model, SQLite, route-effect, runtime, action-job,
  ingestion, identity, or configuration production code during selection.
- Do not reopen Qdrant query, ingest-status, or summary-status authority without
  contradictory focused evidence.

## Completion gate

The selection must include current code traces, mutation-sensitive temporary
witnesses, a no-repeat comparison against completed authority checkpoints, one
exact chosen owner and rollback boundary, documentation authority/drift gates,
the frozen route census, diff checks, and independent read-only review.
