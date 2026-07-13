<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Request-Context Authority Selection

## Decision

Select origin-owned retrieval request-context propagation as the next bounded
seam. Do not combine raw-query or FAISS-detail privacy redaction.

The completed retrieval-event policy controls whether and where events persist;
it does not identify the request that caused a hit. Qdrant, ephemeral-memory,
and FAISS currently read one process-global environment value at query time.
No production origin sets that value. Ordinary audit rows are therefore
`unknown`, while ambient state can misattribute concurrent requests.

This was a read-only code/configuration audit plus one file-free, in-process
concurrency witness. No production code or canonical configuration changed. No
configured database, endpoint, Qdrant service, model, cache, ingestion path,
identity surface, WSL distribution, dependency, public checkout, or mixed main
checkout was exercised.

## Governing Invariant

Every telemetry-writing retrieval query receives its context explicitly from
the request or command origin. Cached clients and shared stores may carry
persistence policy, but they may not infer request identity from process-global
state. Interleaved calls must retain their own normalized labels without
changing hits, ranking, persistence policy, or route effects.

## Current Authority Defect

The only production reads of `GOODQ_RETRIEVAL_CONTEXT` are inside successful-hit
emitters:

- `steps/common/qdrant_client.py` in `QdrantClient.query()`;
- `steps/common/memory_stores.py` in `EphemeralMemory.query()`; and
- `steps/common/memory_stores.py` in `FaissMemory.query()`.

The repository has no production setter. `.env.template` nevertheless
advertises the variable as if one static process value could describe all
queries. This is a competing ambient authority, not a request contract.

The cached API search engine makes the defect more consequential. One engine
and its Qdrant clients are reused across requests, so constructor state cannot
truthfully represent per-call origin either. Reading the environment later
does not solve that problem because environment state is shared by the entire
process.

## Deterministic Concurrency Witness

A single in-memory `EphemeralMemory` store was instrumented so event emission
was captured in-process and no file writer ran. Two threads used the same store:

1. request A set `human.ui.search` and paused;
2. request B set `agent.reasoning`, queried, and released A; and
3. request A then queried.

Observed attribution:

```text
request-b -> agent.reasoning
request-a -> agent.reasoning
```

The witness used no temporary file or live resource and restored the module
hook and process environment before exit. It proves an explicit UI origin can
be overwritten by an unrelated interleaved request before the store reads the
ambient value.

## Origin And Interface Census

### Explicit origins

- API multimodal, text, and visual search routes in `api/routes/search.py`;
- similar-scene search in `api/routes/scenes.py`;
- the MiniAgent Qdrant search tool in `agents/mini_agent_client.py`;
- the direct Qdrant path in `cli/retrieve.py`;
- the callable and command-line entry points in
  `retrieval/multimodal_search.py`;
- the diagnostic retrieval loop in `cli/test_ingestion.py`;
- the UCF birth-certificate/promotion witness in
  `scripts/ucf/generate_birth_certificate.py`; and
- the read-only provenance sample in `cli/observability_health.py`, whose event
  policy remains explicitly disabled.

### Propagation interfaces

- `MultimodalSearchEngine.search_text()`;
- `MultimodalSearchEngine.search_visual()`;
- `MultimodalSearchEngine.search_audio()`;
- `MultimodalSearchEngine.search_multimodal()`;
- `MultimodalSearchEngine.search_similar_scene()`;
- `MemoryRouter.query()` and the `MemoryStore` protocol;
- `QdrantClient.query()`;
- `QdrantMemory.query()`;
- `EphemeralMemory.query()`; and
- `FaissMemory.query()`.

The multimodal method calls its modality methods internally, and the similar-
scene method calls multimodal search. The same explicit context must flow
through those nested calls without being replaced by a default or reread from
ambient state.

## Selected Authority Shape

Add one required keyword-only `retrieval_context` argument to every selected
telemetry-writing query interface. Origins provide the label; intermediate
engine/router/store layers forward it unchanged; the existing
`normalize_retrieval_context()` remains the single vocabulary normalizer at
event construction.

Use the existing vocabulary rather than inventing a second context model:

- user-facing API search origins use `human.ui.search`;
- command-line retrieval uses `human.cli.retrieve`;
- bounded diagnostic, promotion-witness, and health retrieval uses
  `system.healthcheck`; and
- agent callers use `agent.reasoning` when that origin is explicitly known.

Generic programmatic interfaces must require the caller to choose a label. An
explicit invalid or deliberately unknown label may normalize to `unknown`, but
omission and process environment must not silently become authority.

Remove `GOODQ_RETRIEVAL_CONTEXT` from `.env.template` and remove all production
reads. Do not mutate the user's environment or treat an existing user value as
configuration authority. Request context is not part of the frozen persistence
policy because it changes per call.

## Caller Continuity

- API route signatures and response bodies remain unchanged; routes inject the
  origin label when calling the engine.
- The MiniAgent Qdrant search tool supplies `agent.reasoning` without accepting
  ambient attribution.
- Multimodal fan-out passes one label to text, visual, and audio queries.
- Similar-scene search passes its origin through its nested multimodal call.
- The shared memory router forwards one label to whichever tier produces the
  first hit.
- Direct Qdrant CLI retrieval supplies its command-line origin.
- The observability-health sample supplies `system.healthcheck` while retaining
  its explicit disabled event policy, so it remains non-writing.
- Retrieval hits, scores, filters, promotion behavior, event row shape,
  persistence/fallback behavior, and route classification do not change.

## Existing Test Gap

Current tests prove synthetic event persistence and formatter output for a
literal `human.ui.search` value, but none proves that a production origin reaches
Qdrant, ephemeral-memory, or FAISS. No test covers conflicting ambient state,
nested multimodal propagation, a shared cached engine, or concurrent isolation.

## Mutation-Sensitive RED

Before implementation, focused tests must fail against the current code and
prove:

1. API multimodal, text, visual, and similar-scene origins provide the expected
   explicit context without accepting a client-controlled context field;
2. MiniAgent, CLI, diagnostic, promotion-witness, and health origins provide
   their exact labels;
3. individual engine methods pass the label to Qdrant;
4. multimodal and similar-scene nested calls preserve one label across every
   selected modality;
5. `MemoryRouter` passes the label to ephemeral, FAISS, and Qdrant tiers;
6. direct Qdrant, ephemeral-memory, FAISS, and the Qdrant wrapper construct
   events from the explicit argument;
7. a conflicting `GOODQ_RETRIEVAL_CONTEXT` value cannot change attribution;
8. two interleaved calls through one cached/shared object preserve distinct
   labels;
9. omission is rejected at the selected query interfaces rather than silently
   using ambient state;
10. invalid explicit context retains the existing normalization-to-`unknown`
    behavior;
11. health remains telemetry-disabled and non-writing; and
12. hits, ranking, filters, promotion behavior, persistence policy, and the
    69-operation route census remain unchanged.

A caller/interface census must also prove there is no selected production read
of `GOODQ_RETRIEVAL_CONTEXT` and no selected query call missing the explicit
keyword.

## Deliberately Separate Privacy Seam

Privacy evidence remains valid but has a different owner and gate:

- four multimodal search methods log raw query text at INFO;
- FAISS event details include the absolute `index_path` as well as a safe
  basename `store_ref`;
- FAISS error logs repeat the absolute path; and
- the observability rollup can fall back from `store_ref` to `index_path`.

`RetrievalEvent.to_row()` and `to_dict()` intentionally preserve arbitrary
detail payloads, and the completed persistence test proves a canary detail
survives. Central serializer redaction would therefore reopen or broaden the
completed persistence contract. The later privacy repair should start at the
producing log/event callers and use SQLite, JSONL, and `caplog` canaries. It does
not require changing query-context interfaces.

Request-context authority comes first because truthful attribution is control
and correctness debt. It also establishes trustworthy labels for later privacy
canaries. This ordering does not defer any newly discovered secret exposure;
the known privacy outputs remain recorded in the sole roadmap and active
mission boundary.

## Exact Implementation Boundary

Expected production/configuration scope:

- `.env.template` — remove the competing ambient request-context control;
- `steps/common/memory_store.py` — explicit query protocol;
- `steps/common/memory_stores.py` — ephemeral, FAISS, and Qdrant-wrapper
  propagation;
- `steps/common/memory_router.py` — tier propagation;
- `steps/common/qdrant_client.py` — explicit Qdrant event attribution;
- `retrieval/multimodal_search.py` — individual, fan-out, similar-scene,
  callable, and CLI propagation;
- `api/routes/search.py` and `api/routes/scenes.py` — fixed origin labels;
- `agents/mini_agent_client.py` — fixed agent-tool origin label;
- `cli/retrieve.py` and `cli/test_ingestion.py` — command/diagnostic labels;
- `scripts/ucf/generate_birth_certificate.py` — fixed promotion-witness label;
  and
- `cli/observability_health.py` — explicit health label with telemetry still
  disabled.

Expected tests:

- add one focused request-context authority module with the interface,
  conflicting-environment, nested-call, and concurrency oracles;
- extend existing route, MiniAgent Qdrant-tool, engine, memory-router/store,
  Qdrant, and health tests only for caller continuity; and
- preserve the completed telemetry persistence and route-effect suites as
  frozen regression gates.

Frozen outside this seam:

- persistence policy resolution, destination authority, schema readiness,
  locked/busy fallback, warnings, event schema, retention, and rollups;
- raw-query logging and FAISS detail/path redaction;
- Qdrant query no-create, retrieval SQLite, model/cache, summary, status,
  identity, ingestion, MiniAgent confirmation/execution, and lifecycle
  behavior;
- response contracts and route classifications; and
- active environments, dependencies, configured data, live services, WSL,
  public release state, and the mixed main checkout.

## Selection Verification

Before production implementation:

- two independent read-only traces agreed that context and privacy have
  separate owners and selected context correctness first;
- the main caller census added the diagnostic retrieval loop, and final reviews
  added the UCF promotion witness plus MiniAgent's Qdrant search tool,
  preventing an incomplete interface migration;
- a deterministic in-process interleaving witness reproduced cross-request
  misattribution without writing a file or touching a live resource;
- the repository census found three production environment reads and no
  production setter; and
- the telemetry persistence checkpoint was committed with a clean worktree
  before this selection began.

The next implementation must begin with mutation-sensitive RED. It must not
remove successful-hit telemetry, change its persistence authority, or bundle
the later privacy repair.
