<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — define retrieval raw-query log privacy authority.

## Outcome

Create mutation-sensitive RED for the selected application-log and Uvicorn
access-log boundary, then remove exact retrieval queries from shared logs
without changing the functional query, responses, access logging, telemetry,
or route effects.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_QUERY_LOG_PRIVACY_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

The exact query remains functional request data but never enters shared
application or access logs. Operational evidence stays visible through safe
operation, route, status, context, count, and modality fields.

## Scope

- Add one isolated RED suite for all four engine log producers and the Uvicorn
  GET-query access-log producer.
- Prove the exact query still reaches encoder, FTS, and nested search callers.
- Preserve safe operational log fields and existing secret-parameter redaction.
- Reject disabling access logs as a privacy shortcut.
- Implement only after the RED suite collects cleanly and fails as intended.

## Boundaries

- Do not change the completed persistence, request-context, SQLite, model-cache,
  Qdrant no-create, status, or summary authorities.
- Do not change `RetrievalEvent`, FAISS event details/warnings, or observability
  rollup fallback; absolute-path privacy is the next separate rollback boundary.
- Do not change retrieval results, response contracts, route classifications,
  dependencies, active environments, configured data, live endpoints,
  services, identity, ingestion, WSL, public checkout, or mixed main checkout.
- Use captured logs, fake Uvicorn modules, stubs, and in-memory canaries only.

## Completion gate

The RED suite must collect without infrastructure, fail only the selected
privacy contract, reject logger references to the local query value, cover
plain and encoded access-log values, preserve functional query propagation and
safe audit fields, and receive independent oracle review before implementation.
