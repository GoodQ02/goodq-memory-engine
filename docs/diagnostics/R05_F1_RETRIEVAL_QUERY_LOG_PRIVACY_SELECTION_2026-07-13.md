<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Query-Log Privacy Selection

## Decision

Select raw retrieval-query logging as the next bounded repair. Close both
application-log and Uvicorn access-log exposure before changing FAISS event
details or path-bearing warnings.

This ordering follows one rollback boundary: the selected seam controls where
the exact retrieval query crosses into shared ordinary logs. It does not own
retrieval-event persistence, FAISS path metadata, responses, or retrieval
behavior.

## Governing Invariant

`docs/architecture/SYSTEM_MAP_v1.md` states that privacy is binding and raw
queries must not be logged. The repair must therefore keep the exact query in
the functional request path while preventing it from entering shared
application or access logs.

Do not replace the query with a prefix, truncated value, or hash. Personal
queries can be low entropy, and none of those values is required for the
operational evidence retained by this seam.

## Fresh Producer And Sink Trace

### Application logger producers

Four methods in `retrieval/multimodal_search.py` interpolate the entire query at
INFO:

| Method | Current record | Ordinary-log exposure |
|---|---|---|
| `search_text()` | `Searching text: '<query>'` | complete query |
| `search_visual()` | `Searching visual scenes: '<query>'` | complete query |
| `search_audio()` | `Searching audio scenes: '<query>'` | complete query |
| `search_multimodal()` | `Multimodal search: '<query>' across <modalities>` | complete query and safe modality list |

A default multimodal request records the same query in the multimodal, text,
and visual messages. An audio-enabled request can record it four times.

The similar-scene path is especially sensitive. `build_scene_similarity_query()`
can synthesize a query from tags, dialogue topics, keywords, narrative or
activity summaries, audio emotion, object labels, or the first twenty
transcript words. `search_similar_scene()` then sends that text through
`search_multimodal()`, so persisted personal scene content can reach the same
four INFO records without being typed by the current requester.

The API configures ordinary INFO logging, and canonical supervised launch paths
may capture child stdout or stderr. These messages are therefore shared runtime
logs, not an ephemeral response echo.

### Uvicorn access-log producer

The text and visual search GET endpoints accept the query as the `q` query
parameter. Uvicorn's enabled access logger builds its request target from the
path plus query string, so records for these endpoints contain the exact query:

- `/api/search/text?q=<query>`; and
- `/api/search/visual?q=<query>`.

`api/server.py` installs an access-log filter for token-, password-, and
secret-style parameter names, but it does not redact `q`. The server starts
Uvicorn at INFO without disabling access logging. Fixing only the four engine
messages would therefore leave two mounted API paths leaking the same value.

The multimodal POST endpoint does not place its JSON body in the Uvicorn request
target, but its query still reaches the application logger producers above.

### Retrieval-event negative trace

The raw query does not currently enter retrieval-event persistence through the
selected production paths:

- Qdrant receives an embedding vector and the explicit retrieval context, not
  the source query;
- current Qdrant, ephemeral-memory, and FAISS event producers record hit
  identifiers, scene/modality/model/score metadata, and store details; and
- `RetrievalEvent` has no query field.

SQLite `retrieval_events` and locked/busy JSONL fallback therefore do not
receive the raw query from these producers. The generic `details` payload
remains intentionally lossless for its producer, so this conclusion does not
authorize weakening `RetrievalEvent.to_row()` or `to_dict()`.

## Temporary Canary Evidence

An in-process logging witness used a synthetic query, stubbed every encoder and
store boundary, and invoked all four methods. The exact canary appeared in four
captured INFO records. The witness did not load a model, open a database,
contact Qdrant, or access configured data.

A separate fake-Uvicorn witness ran the existing server filter against a
synthetic access record. Its result preserved the route, `top_k`, HTTP version,
status, and existing token redaction, but retained the complete `q` canary.
Uvicorn access logging also remained enabled.

These witnesses prove two independent producers of the same value into the
same ordinary-log class. Both must be inside the selected rollback boundary.

## Selected Production Boundary

The later implementation is limited to two production files.

### `retrieval/multimodal_search.py`

- Replace the four raw-query INFO records with stable operational records.
- Retain operation identity and safe fields such as `top_k`, retrieval context,
  and selected modalities where applicable.
- Never log the query, a substring, or a query hash.
- Do not alter the query passed to encoders, FTS, reranking, nested modality
  calls, or response construction.

### `api/server.py`

- Make access-record query-parameter redaction explicit and directly testable.
- Redact every `q` value, including repeated keys and percent-encoded values,
  while preserving method, route path, status, non-sensitive parameters such
  as `top_k`, and the existing secret-parameter behavior.
- Keep access logging enabled; disabling the audit record is not an acceptable
  privacy repair.
- Redact the log record only. Do not mutate the ASGI scope, routed request,
  request model, or response.

No route, response, retrieval, persistence, telemetry-policy, or request-context
interface belongs to this repair.

## Mutation-Sensitive RED Contract

Add one isolated authority suite under
`tests/unit/test_retrieval_query_log_privacy_authority.py` using only captured
logs, fake Uvicorn modules, stubs, and in-memory values.

The suite must prove:

1. all four search methods exclude an exact raw-query canary from INFO records;
2. each method retains a stable safe operation marker;
3. every applicable propagation edge receives the exact query: text reaches
   both its encoder and FTS, visual and audio reach their encoders, and
   multimodal reaches each selected nested modality unchanged;
4. an AST guard rejects any logger argument in those methods that references
   the local `query` parameter;
5. plain, repeated, mixed-case, and percent-encoded `q` values are redacted in
   access records;
6. route path, method, status, HTTP version, `top_k`, and existing token
   redaction remain observable;
7. access logging is not disabled as a shortcut; and
8. no test contacts a live service, configured database, model, cache, or data
   root.

The suite must collect cleanly before production changes and fail only the
selected contract.

## Preserved Contracts

Frozen outside this seam:

- exact query semantics, ranking, FTS, encoder input, nested multimodal fan-out,
  and response query echo to the initiating requester;
- origin-owned retrieval context and its vocabulary;
- retrieval-event schema, serializers, policy, destination, SQLite authority,
  locked/busy fallback, warnings, retention, and route effects;
- FAISS event details, warnings, and legacy rollup fallback until their separate
  repair is selected;
- API bind, port, proxy-header, and startup behavior; and
- live endpoints, configured data, identity, ingestion, WSL, public checkout,
  and the mixed main checkout.

Interactive CLI echo in the module entry point and the fixed diagnostic queries
in `cli/test_ingestion.py` are requester-visible command output, not the shared
application-log producer selected here. They remain unchanged.

## Separate Recorded Privacy Candidates

The same audit found related but differently owned candidates. They are
recorded so they are not lost or silently bundled:

- `scripts/analytics_query.py` logs the complete analytics question at INFO;
- `cli/nl_query.py` logs a derived intent/entity structure that may contain
  personal terms; and
- FAISS new-event details, seven warning branches, and the legacy observability
  rollup fallback can expose an absolute index path.

The analytics and derived-intent candidates require their own caller and
retention evidence. FAISS path privacy is already bounded as the next retrieval
telemetry mission. Historical log or event cleanup is a retention action and is
not authorized by this selection.

## Completion Gate

After clean RED evidence, the selected implementation must pass the dedicated
privacy suite, existing API server/route-effect tests, retrieval engine and
request-context tests, telemetry serializer/persistence tests, changed-Python
compilation, documentation/static gates, and an independent implementation and
oracle review. The 69-operation route census and four intentional retrieval
`automatic_mutation` classifications must remain unchanged.
