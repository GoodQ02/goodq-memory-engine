<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Request-Context Authority Checkpoint

## Outcome

Retrieval request context is now owned by the request or command origin and
propagated explicitly through every selected query interface. Shared engines,
routers, stores, and cached Qdrant clients no longer infer per-request identity
from process-global state, so interleaved calls retain truthful attribution.

Private implementation checkpoint:

```text
9cc40c04 fix: make retrieval context origin owned
```

Supporting evidence checkpoints:

```text
d0a5bc0a test: define retrieval request context authority
fc459133 docs: select retrieval request context authority
```

This checkpoint closes request-context authority only. Successful-hit retrieval
telemetry remains intentional best-effort durable observability, so the four
mounted retrieval routes remain `automatic_mutation`. Raw-query logging and
FAISS path/detail privacy remain a separate producer-side seam.

## Exact Authority Boundary

The following twelve interfaces now require a keyword-only
`retrieval_context` argument:

1. `MemoryStore.query()`;
2. `MemoryRouter.query()`;
3. `EphemeralMemory.query()`;
4. `FaissMemory.query()`;
5. `QdrantMemory.query()`;
6. `QdrantClient.query()`;
7. `MultimodalSearchEngine.search_text()`;
8. `MultimodalSearchEngine.search_visual()`;
9. `MultimodalSearchEngine.search_audio()`;
10. `MultimodalSearchEngine.search_multimodal()`;
11. `MultimodalSearchEngine.search_similar_scene()`; and
12. the public `multimodal_search()` callable.

Origins choose the label, intermediate layers forward it unchanged, and the
existing `normalize_retrieval_context()` remains the single vocabulary
normalizer at event construction. No selected class stores request context on
the instance.

Fixed origins are:

- API multimodal, text, visual, and similar-scene search:
  `human.ui.search`;
- MiniAgent Qdrant retrieval: `agent.reasoning`;
- direct retrieval CLI and multimodal-search CLI: `human.cli.retrieve`; and
- diagnostic retrieval, UCF birth-certificate witness, and observability
  sampling: `system.healthcheck`.

The observability-health sampler still receives an explicitly disabled event
policy. Supplying its origin therefore does not grant write authority.

## Removed Competing Authority

`GOODQ_RETRIEVAL_CONTEXT` was removed from the active environment template and
all production reads were removed. An existing user or process value is now
irrelevant to retrieval attribution and was not modified by this repair.

The API request model does not expose a context field. A client-supplied
`retrieval_context` extra is not represented in the validated request, and the
route supplies `human.ui.search` itself.

## Preserved Caller Contracts

- multimodal fan-out sends one exact label to text, visual, and audio search;
- similar-scene search sends the caller label through its nested multimodal
  call;
- the memory router sends the same vector, `top_k`, filter, and context through
  every attempted tier until the first hit;
- the Qdrant wrapper preserves vector, `top_k`, payload filter, and context;
- Qdrant, ephemeral-memory, and FAISS normalize invalid explicit labels to the
  existing `unknown` value;
- hits, ranking, filtering, promotion, response bodies, persistence policy,
  fallback behavior, event schema, retention, and warnings are unchanged; and
- the mounted route census remains 69 operations: 41 passive reads, 1 request
  staging, 10 automatic mutations, 8 curated mutations, and 9 process
  executions.

## Mutation-Sensitive Evidence

The committed RED suite first collected cleanly with 34 intended failures. It
proved missing required interfaces and origins, ambient authority, incomplete
nested propagation, and missing event attribution before production changed.

The completed witnesses prove:

- all twelve selected interfaces reject omission;
- all fixed production origins supply their exact label;
- API clients cannot select their own label;
- individual engine methods reach Qdrant with the exact context;
- multimodal and similar-scene nesting preserve one label;
- the router traverses ephemeral, FAISS, and Qdrant without changing vector,
  `top_k`, filter, or context;
- Qdrant, ephemeral-memory, and FAISS events use explicit context and preserve
  invalid-label normalization;
- one conflicting ambient value cannot affect explicit attribution; and
- two truly overlapping calls through one shared store retain distinct labels
  while one call is paused inside the store and the other completes.

All storage and transport witnesses used temporary files, in-memory stores,
fake modules, captured emitters, or `.invalid` hosts. No configured runtime was
contacted.

## Fresh Verification

The final gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Dedicated retrieval-context authority | 34 passed |
| Combined engine, route, store, Qdrant, telemetry, config, identity, and route-effect union | 253 passed, 8 skipped |
| MiniAgent Qdrant dispatch continuity | 8 passed |
| Independent production review | CLEAN; no P1/P2 |
| Independent oracle review | CLEAN; no P1/P2 |
| Independent caller/interface census | CLEAN; 12 interfaces and 22 production calls reconciled |

The eight skips are the inherited isolated-profile `live_runtime` skips in
`tests/identity/test_retrieval_regression.py`. The warnings are inherited
Pydantic class-based configuration deprecations and one pre-existing invalid
escape warning in the audited source census.

Additional evidence:

- all changed Python compiled;
- staged and working-tree diff checks passed;
- documentation authority, generated index, documentation drift, banned-token,
  and dependency-drift gates passed;
- active documentation contains zero drive-root or ghost-path violations;
- no selected production caller omits context; and
- no selected production environment read or active template assignment
  remains.

Three pre-existing search-route test modules remain excluded because their
dynamic-loader harness executes the route dataclass before registering the
module in `sys.modules`, causing collection failure before a route test runs:

- `tests/unit/test_search_route_audio.py`;
- `tests/unit/test_search_route_enrichment.py`; and
- `tests/unit/test_search_route_sentiment.py`.

That known harness defect is unrelated to request-context authority and was not
patched here.

No live endpoint, configured database, Qdrant service, model, cache, configured
data root, ingestion, identity surface, WSL distribution, public checkout, or
mixed main checkout was exercised.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- ambient request attribution through `GOODQ_RETRIEVAL_CONTEXT`;
- optional/default context on the selected generic interfaces;
- request context stored on cached engines, clients, routers, or stores;
- client-controlled context on API request models;
- separate normalization vocabularies at different tiers;
- the completed telemetry persistence policy or fallback authority; or
- route reclassification while successful-hit telemetry remains enabled.

## Next Bounded Mission

Run a fresh read-only selection of the remaining retrieval telemetry privacy
surface. Trace the raw-query INFO producers, FAISS event detail producer,
path-bearing FAISS error logs, and observability rollup fallback; select one
producer-owned redaction boundary and mutation-sensitive canary set. Do not
change central event serialization, persistence policy, request-context
authority, or route classification merely because the outputs share telemetry.
