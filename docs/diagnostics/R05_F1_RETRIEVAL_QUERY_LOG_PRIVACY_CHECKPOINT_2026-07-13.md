<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Query-Log Privacy Checkpoint

## Outcome

Exact retrieval queries remain functional request data but no longer enter the
selected shared application or Uvicorn access logs. The repair preserves
retrieval inputs, results, responses, access logging, route effects, and the
existing secret-parameter behavior.

Private implementation checkpoint:

```text
003ec8c6 fix: redact retrieval queries from shared logs
```

Supporting evidence checkpoints:

```text
d9dd93fe test: define retrieval query log privacy authority
45feedd8 docs: select retrieval query log privacy
```

This checkpoint closes raw-query exposure at the four selected retrieval
engine records and the API server's Uvicorn access-record boundary only. FAISS
absolute-path event details, warnings, and legacy rollup compatibility remain
a separate producer-owned privacy seam.

## Exact Privacy Boundary

`retrieval/multimodal_search.py` now emits stable allowlisted records for text,
visual, audio, and multimodal search. The records retain operation identity,
`top_k`, and allowlisted selected modality names where applicable. They contain
no query value, query fragment, or query hash, and do not log caller-controlled
retrieval context.

`api/server.py` now redacts sensitive query-string fields in log-record values
without changing the request target used by ASGI routing. The boundary:

- matches `q` case-insensitively;
- replaces every repeated, bare, mixed-case, or percent-encoded-key value;
- preserves raw formatting and ordering for non-sensitive fields such as
  `top_k`;
- retains the existing protection for `token`, `session_token`, `api_key`,
  `auth_token`, `password`, and `secret`; and
- leaves Uvicorn access logging enabled with proxy-header rewriting disabled.

## Preserved Functional Contracts

- text search forwards the exact query to both its encoder and FTS;
- visual and audio search forward the exact query to their encoders;
- multimodal search forwards the exact query and retrieval context to every
  selected nested modality;
- ranking, filtering, fusion, responses, telemetry persistence, and event
  serialization are unchanged;
- the mounted route census remains 69 operations: 41 passive reads, 1 request
  staging, 10 automatic mutations, 8 curated mutations, and 9 process
  executions; and
- text, visual, multimodal, and similar-scene retrieval remain the same four
  intentional `automatic_mutation` routes while successful-hit telemetry is
  enabled.

## Mutation-Sensitive Evidence

The committed authority suite collected nine tests before production changed.
Its first execution failed all nine for only the selected behavior: four logger
references to `query`, four runtime application-log canaries, and four
parameterized Uvicorn access-record cases under one test function.

The completed suite proves:

- an AST guard rejects direct query references from the four selected logger
  calls;
- exact functional propagation reaches every encoder, FTS, and nested-modality
  edge before privacy is asserted;
- plain, percent-encoded, repeated, and mixed-case `q` values are absent from
  rendered access records;
- exact route, method, HTTP version, status, and `top_k` remain visible;
- all six pre-existing secret keys retain `REDACTED` values; and
- disabling access logging cannot satisfy the oracle.

Every witness used captured logs, fake Uvicorn modules, stubs, or in-memory
values. No live endpoint, configured database, Qdrant service, model, cache,
configured data root, ingestion, identity surface, WSL distribution, public
checkout, or mixed main checkout was exercised.

## Fresh Verification

The final gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Dedicated query-log privacy authority | 9 passed |
| API server interaction plus privacy authority | 10 passed |
| Retrieval request-context authority | 34 passed |
| Multimodal audio and similar-scene behavior | 10 passed |
| Retrieval persistence, model-cache, and SQLite authority | 64 passed |
| API route-effect authority | 74 passed |
| Combined focused regression union | 196 passed, 8 skipped |
| Independent implementation review | CLEAN; no P0-P2 |
| Independent oracle review | CLEAN; no P0-P2 |

The eight skips are inherited isolated-profile `live_runtime` skips in the
identity retrieval-regression suite. The three warnings are inherited Pydantic
configuration deprecations and one pre-existing invalid escape warning in the
audited source census.

Additional evidence:

- all changed Python compiled;
- staged and working-tree diff checks passed;
- documentation authority, documentation drift, banned-token, and dependency
  drift gates passed; and
- no selected legacy raw-query message remains.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- raw-query INFO records in the four selected engine methods;
- access-log `q` values on the text or visual GET routes;
- query truncation or hashing as a substitute for removal;
- access-log disabling as a privacy shortcut;
- client-selected retrieval context or ambient request attribution; or
- central retrieval-event serializer redaction for a producer-owned field.

Historical log cleanup is a retention action and was not authorized here.
Interactive requester-visible CLI output and fixed diagnostic query output were
not shared-log producers and remain unchanged.

## Next Bounded Mission

Run a fresh read-only selection of FAISS absolute-path privacy. Trace the new
event-detail producer, all path-bearing warning branches, and the legacy
observability-rollup fallback through their actual sinks and consumers. Select
one producer-owned boundary and mutation-sensitive canary set before changing
production. Keep analytics-question and derived-intent logging as separately
owned candidates.
