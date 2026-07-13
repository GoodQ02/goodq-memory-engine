<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — bound retrieval SQLite read authority.

## Outcome

Remove write capability from the FTS, knowledge-graph scoring, shared
hit-provenance, and FAISS shadow-scoring SQLite projections while preserving
existing-file behavior, committed live-WAL truth, each caller's exact failure
boundary, and the completed summary read contract. Intentional retrieval
telemetry remains unchanged and keeps the four retrieval routes classified
`automatic_mutation`.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_SUMMARY_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_MODEL_CACHE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

A retrieval projection may observe committed live-WAL truth, but it must not
possess database creation, DML, DDL, ATTACH/DETACH, external vacuum-target, or
read-policy-downgrade authority. Only the explicit retrieval telemetry owner may
perform its currently governed durable audit effect.

## Scope

- Add one neutral common existing-file SQLite read connection primitive using
  URI `mode=ro`, verified `query_only`, and operation-level authorization.
- Preserve `open_summary_read_connection()` as a behaviorally equivalent
  compatibility wrapper over the common primitive.
- Migrate only retrieval FTS, KG scoring, shared Qdrant/FAISS memory-commit
  provenance, and FAISS quantization shadow-scoring reads.
- Replace the provenance parameterized PRAGMA with a normal zero-row schema
  projection compatible with the bounded authorizer.
- Add mutation-sensitive tests before production implementation.

## Boundaries

- Do not change retrieval telemetry, JSONL fallback, context policy, raw-query
  logging, FAISS details, route effects, or response contracts in this seam.
- Do not reopen completed Qdrant, ingest-status, summary-status, model-cache, or
  summary reader behavior.
- Do not change unrelated SQLite callers, dependencies, runtime packages,
  configured data, live endpoints, Qdrant, models, ingestion, identity, WSL,
  public checkout, or the mixed main checkout.
- Use temporary SQLite databases, fake clients, and monkeypatched loaders only.

## Completion gate

The current write-capable implementation must first fail the seeded mutation
oracle. The repaired readers must reject DML, DDL, ATTACH/DETACH, external
vacuum targets, and query-only downgrade; preserve committed live-WAL reads,
fallback behavior, connection closure, and the completed summary wrapper; pass
focused and adjacent regressions, including the FAISS caller, plus
static/documentation gates; preserve the
69-operation route census; and receive independent review before checkpointing.
