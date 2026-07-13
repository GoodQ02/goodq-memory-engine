<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — define retrieval FAISS store-reference privacy authority.

## Outcome

Create mutation-sensitive RED for the selected retrieval logical `store_ref`
contract, then remove absolute FAISS paths from new retrieval events, seven
warnings, and future legacy-input rollup projections without changing retrieval
or rollup behavior.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_FAISS_STORE_REF_PRIVACY_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Every newly emitted or compatibility-derived FAISS retrieval reference is the
portable logical index filename, never an absolute path. Central event
serialization remains lossless.

## Scope

- Add one isolated RED suite for FAISS event details, all seven warning branches,
  and modern/legacy temporary rollup input.
- Preserve exact FAISS hits, scores, context, failure returns, and safe
  diagnostic fields.
- Preserve rollup precedence, aggregation math, state advancement, and
  idempotency.
- Prove lossless arbitrary-detail serialization remains unchanged.
- Implement only after the suite collects cleanly and fails as intended.

## Boundaries

- Do not change completed query-log, request-context, persistence, SQLite,
  model-cache, Qdrant no-create, status, or summary authorities.
- Do not redact `RetrievalEvent.to_row()` or `to_dict()` centrally.
- Do not clean historical raw/derived rows or bundle ingestion commit-event,
  analytics-question, or derived-intent path/logging candidates.
- Do not change routes, responses, ranking, dependencies, environments,
  configured data, live endpoints, services, identity, ingestion, WSL, public
  checkout, or mixed main checkout.
- Use temporary paths, captured emitters/logs, and in-memory values only.

## Completion gate

The RED suite must collect without infrastructure and fail only the selected
path-privacy contract. It must reject explicit and exception-carried path leaks,
preserve a safe filename reference and every functional edge, protect central
serializer losslessness, and receive independent oracle review before
implementation.
