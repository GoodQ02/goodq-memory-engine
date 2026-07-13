<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Telemetry Persistence Authority Checkpoint

## Outcome

Retrieval-event persistence now has one immutable resolved policy propagated
through Qdrant, ephemeral-memory, and FAISS hit emitters. Intentional
successful-hit audit events remain best-effort durable observability. Disabled
telemetry and unavailable primary storage cannot create or relocate artifacts.
Non-lock SQLite failure does not authorize JSONL fallback, and unavailable
fallback storage does not authorize relocation. Intentional schema writes
inside an existing primary remain allowed, and a failed append may leave a
partial file only at the exact authorized fallback path.

Private implementation checkpoint:

```text
b91210ac fix: govern retrieval telemetry persistence
```

Supporting evidence checkpoints:

```text
aa58ece1 docs: include telemetry health sampler boundary
577447d4 test: define retrieval telemetry persistence authority
```

This checkpoint closes retrieval-event persistence and configuration authority
only. The four mounted retrieval routes remain `automatic_mutation`. Request
context and raw-query/FAISS-detail privacy remain separate unresolved seams.

## Exact Policy Authority

`steps/common/retrieval_events.py` owns the frozen `RetrievalEventPolicy` and
its resolver. The policy contains:

- event persistence enablement;
- locked/busy JSONL fallback enablement; and
- one exact existing log directory, or an explicit unavailable destination.

Canonical configuration is `observability.retrieval_events`. Its strict,
frozen schema accepts `enabled` and `jsonl_fallback`; `paths.log_dir` remains
the destination authority. Environment overrides retain exact precedence
through `GOODQ_RETRIEVAL_EVENTS` and `GOODQ_RETRIEVAL_EVENTS_JSONL`.
`memory.retrieval_events` is rejected as a competing policy and is never used
by resolution, while unrelated legacy `memory.*` projection remains unchanged.

The policy resolves once per builder or search-engine authority and the same
object is carried to Qdrant, ephemeral-memory, and FAISS emitters. The emitter
no longer accepts full configuration, an independent enabled boolean, or an
independent log directory.

## Exact Persistence Boundary

Enabled telemetry may add its stable audit table, four indexes, and event rows
only inside an existing regular primary database. The writer:

- refuses an absent or non-file primary instead of creating it;
- opens the existing primary with a short-timeout read/write URI;
- checks and repairs table/index readiness on each write, so atomic replacement
  at the same path cannot inherit stale pathname-only readiness;
- treats only SQLite BUSY/LOCKED codes or exact canonical locked/busy messages
  as fallback-eligible;
- appends JSONL only beneath the exact existing resolved log directory;
- never creates a fallback directory or relocates beside the database; and
- preserves retrieval hits while emitting a bounded query-free, path-free
  structured warning when persistence cannot complete.

Arbitrary exception text containing fragments such as `busy` or `locked` is
not fallback authority. The final classifier is code-first when SQLite exposes
an extended error code and otherwise accepts only bounded canonical messages.

## Preserved Caller Contracts

- `MultimodalSearchEngine` freezes one policy at construction and reuses it
  across cached clients.
- The generic Qdrant builder accepts an injected policy and resolves only when
  no policy is supplied.
- The shared text-store builder passes one object identity to ephemeral, FAISS,
  and Qdrant stores.
- Qdrant, ephemeral-memory, and FAISS telemetry failure never suppresses or
  changes successful hits.
- The read-only observability-health provenance sample injects an explicit
  disabled policy; it no longer relies on an environment toggle applied after
  client construction.
- Event row shape, retention, health projections, route responses, and route
  classification remain unchanged.

## Mutation-Sensitive Evidence

The first RED run produced 30 intended failures against the previous
implementation. Its oracles proved policy loss, fallback relocation,
missing-primary creation, stale same-path schema readiness, and health-sampler
construction-order authority before production implementation began.

Independent adversarial review later demonstrated that a broad substring
classifier treated unrelated `OperationalError` text containing `busywork` and
`locked-file-label` as fallback authority. A new failing regression reproduced
that defect before the classifier was narrowed. The completed witness proves
the same text creates no JSONL file and emits only sanitized `sqlite_error`
visibility.

The completed witnesses also prove:

- disabled policy is a true no-op with no SQLite, WAL, shared-memory, schema,
  row, JSONL, or directory artifact;
- missing, disappearing, and non-file primaries are refused;
- an existing primary receives the stable schema and event rows;
- partial schema and same-path database replacement are repaired before the
  next event;
- exact locked/busy failure alone may use the exact frozen fallback;
- missing or deleted fallback destinations are not recreated or relocated;
- concurrent first writers preserve every event; and
- an empty event batch is a silent no-op.

## Fresh Verification

The post-review gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Focused retrieval telemetry persistence authority | 33 passed |
| Adjacent config, retrieval, observability, Qdrant, memory, route, and identity union | 193 passed, 8 skipped |
| Independent implementation rereview | CLEAN; no P1/P2 |
| Independent adversarial rereview | CLEAN; original witness creates no fallback |

The eight skips are the inherited isolated-profile `live_runtime` skips in
`tests/identity/test_retrieval_regression.py`; they are not new telemetry
failures. The inherited Pydantic warnings concern pre-existing class-based
`Config` blocks outside the new observability models and were not expanded into
this seam.

Additional evidence:

- all changed Python modules and tests compiled;
- staged and working-tree diff checks passed;
- documentation authority, documentation drift, banned-token, and dependency
  drift gates passed;
- the authority census found no selected production legacy split-policy call;
- the mounted route census remained 69 operations: 41 passive reads, 1 request
  staging, 10 automatic mutations, 8 curated mutations, and 9 process
  executions; and
- the generated agent file index includes the new authority test.

Three pre-existing search-route test modules remain excluded because their
dynamic-loader harness executes the route dataclass before placing the module
in `sys.modules`, causing collection failure before a retrieval test can run:

- `tests/unit/test_search_route_audio.py`;
- `tests/unit/test_search_route_enrichment.py`; and
- `tests/unit/test_search_route_sentiment.py`.

That known harness defect is unrelated to this authority seam and was not
patched here.

No live endpoint, configured database, Qdrant service, model, cache, configured
data root, ingestion, identity surface, WSL distribution, public checkout, or
mixed main checkout was exercised.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- split event enablement, fallback, or destination arguments;
- ambient policy reparsing after builder or engine construction;
- creation of a missing primary database by retrieval telemetry;
- pathname-only schema readiness;
- fallback beside the database or creation of a missing log directory;
- substring-based SQLite lock classification;
- the observability-health post-construction environment toggle; or
- route reclassification while successful-hit telemetry remains intentional.

## Residual Seams

`GOODQ_RETRIEVAL_CONTEXT` remains process-global query-time state. The repository
has no origin-owned setter, ordinary events therefore fall back to `unknown`,
and ambient state can mislabel concurrent requests. This requires an explicit
origin/context propagation contract and an interleaving oracle.

Search methods also retain raw query text at INFO, while FAISS event/error
details can contain an absolute index path. That requires a separate
log/event-redaction and canary gate. It does not share the context-propagation
owner or rollback boundary.

## Next Bounded Mission

Run a fresh read-only selection between request-context authority and telemetry
privacy/detail redaction. Trace each origin, propagation path, sink, and current
test oracle; then select one coherent owner and rollback gate. Do not bundle the
two merely because both affect retrieval events, and do not reopen the completed
persistence/configuration authority.
