<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select retrieval-event persistence/config authority.

## Outcome

Reconcile the intentional retrieval-event write path from canonical
configuration through Qdrant, ephemeral, and FAISS emitters. Select the
smallest owner, rollback boundary, and mutation-sensitive verification gate
that makes event enablement, locked-database JSONL fallback, and fallback
destination explicit without removing durable observability or reclassifying
the four mounted retrieval routes.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Intentional retrieval observability may mutate only through one explicit,
canonical policy. A disabled fallback must stay disabled, an enabled fallback
must use its exact governed destination, and no emitter may silently recover a
discarded configuration from unrelated ambient defaults.

## Scope

- Audit the canonical configuration schema and default configuration for an
  actual retrieval-event policy owner.
- Trace policy propagation through every production call to
  `emit_retrieval_events()` and every builder that constructs Qdrant,
  ephemeral, or FAISS retrieval stores.
- Prove the current locked-database fallback behavior using temporary roots and
  fake/instrumented SQLite connections only.
- Name one exact implementation boundary and RED suite before production code
  changes.

## Boundaries

- Do not implement policy propagation during this selection checkpoint.
- Keep retrieval context propagation separate; process-global context and
  request concurrency require a different interface and verification gate.
- Keep raw-query logging and FAISS path redaction separate; they are privacy
  output contracts, not persistence destination authority.
- Do not alter event schema, successful-hit semantics, best-effort failure
  behavior, route responses, route effects, retention, rollups, model/Qdrant
  authority, configured data, live endpoints, services, or dependencies.
- Do not reopen the completed Qdrant, ingest-status, summary-status,
  model-cache, summary SQLite, or retrieval SQLite checkpoints.

## Completion gate

Two independent read-only traces must reconcile all production emitters,
builders, canonical schema/defaults, environment precedence, and fallback
destinations. Temporary-only witnesses must demonstrate the current policy
loss. The selection evidence must define exact RED oracles, frozen behavior,
route classification, and a seam-only production/test file set before any
implementation begins.
