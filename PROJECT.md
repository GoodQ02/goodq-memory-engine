<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select the retrieval telemetry privacy producer boundary.

## Outcome

Select one exact producer-owned repair for remaining raw-query and FAISS-path
privacy exposure without changing central event serialization, persistence
authority, request-context truth, or route effects.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Privacy repair belongs at the narrowest producer that possesses the sensitive
value. It must remove raw queries and absolute local paths from logs and event
details without weakening durable audit evidence or changing retrieval results.

## Scope

- Trace the four raw-query INFO producers, FAISS event detail construction,
  path-bearing FAISS error logs, and observability rollup fallback.
- Identify which values reach SQLite, JSONL, ordinary logs, and health output.
- Select one coherent producer owner and rollback boundary.
- Define mutation-sensitive canaries for raw query text and absolute local paths.
- Produce selection evidence only; do not change production in this mission.

## Boundaries

- Do not change the completed persistence, request-context, SQLite, model-cache,
  Qdrant no-create, status, or summary authorities.
- Do not weaken or replace `RetrievalEvent.to_row()` or `to_dict()` merely to
  hide a producer defect.
- Do not change retrieval results, response contracts, route classifications,
  dependencies, active environments, configured data, live endpoints,
  services, identity, ingestion, WSL, public checkout, or mixed main checkout.
- Use source traces and temporary/in-memory canaries only.

## Completion gate

The selection must enumerate every sensitive producer and sink, prove current
exposure with file-free or temporary canaries, choose one smallest coherent
repair boundary, preserve the completed no-repeat contracts, and receive an
independent read-only review before mutation-sensitive RED begins.
