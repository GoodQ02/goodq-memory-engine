<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval FAISS Store-Reference Privacy Selection

## Decision

Select one retrieval logical `store_ref` privacy contract spanning the
`FaissMemory` event/log producer and the observability rollup's legacy-input
compatibility projection.

The selected seam governs every new output in this retrieval path that derives
an external reference from the configured FAISS index path. New retrieval
events, warnings, and daily rollup rows may carry the established logical index
name, but never the absolute local path.

This is not a historical cleanup or a repository-wide path-redaction pass.
Existing raw event rows, already-derived daily rows, ingestion commit events,
and scene artifacts remain under separate owners and approval boundaries.

## Governing Invariant

Canonical architecture requires retrieval events and user-safe logs to exclude
absolute paths. The epistemic read model defines `store_ref` as a logical store
identity such as a FAISS index name. `FaissMemory` already computes that name as
the index basename, so no current retrieval consumer requires the redundant
absolute path.

Central retrieval-event serializers remain intentionally lossless. Privacy
must be enforced where the FAISS path becomes a retrieval reference, not by
weakening arbitrary `details` serialization for every event producer.

## Fresh Producer, Sink, And Consumer Trace

### Configured origin and event producer

The shared text-store builder passes the configured `paths.faiss_index_path`
into `FaissMemory`. On every successful FAISS hit, `FaissMemory.query()` emits
one `RetrievalEvent` containing:

- `store_type=faiss`;
- safe `store_ref=<index basename>`; and
- redundant `index_path=<absolute configured path>`.

`RetrievalEvent.to_row()` serializes arbitrary details into SQLite
`details_json`; `to_dict()` preserves the same object for locked/busy JSONL
fallback. The absolute path therefore reaches both authorized persistence
sinks when those paths are used. Existing persistence tests deliberately prove
that arbitrary details survive unchanged, so those serializers are frozen.

### Seven warning producers

Seven `FaissMemory` warning branches interpolate `self.index_path` directly:

1. insert rejects missing explicit IDs;
2. insert raises or fails;
3. query provenance attachment fails;
4. query score parsing fails;
5. retrieval-event emission fails;
6. the outer query path fails; and
7. stats inspection fails.

Six of those records also interpolate raw exception text. An exception can
repeat the same absolute path even after the explicit `index_path` field is
removed. The repair must therefore retain bounded operation, exception type,
reason, and count evidence while excluding both explicit and exception-carried
paths.

### Compatibility projection

`cli/observability_rollup.py` projects raw retrieval events into
`retrieval_events_daily`. Its `_store_ref()` precedence is:

1. existing `details.store_ref`;
2. Qdrant `details.collection`; then
3. legacy FAISS `details.index_path`.

Current FAISS events already take the first safe branch. A historical FAISS row
without `store_ref`, however, copies the complete path into the newly written
daily table. The repository has no other reader of `retrieval_events_daily`,
so this projection needs a stable logical bucket identity, not filesystem
location.

The compatibility branch shares the selected output contract because it is
another point where the same FAISS path becomes a newly materialized retrieval
reference. Leaving it raw would allow unprocessed historical input to create a
new path-bearing derived row after the producer repair.

## Temporary Canary Evidence

One temporary nested index path, fake FAISS index, captured emitter, and
in-memory logger proved:

```text
hits_preserved=1
event_store_ref=memory.index
event_absolute_path_exposed=true
warning_absolute_path_occurrences=2
legacy_rollup_absolute_path_exposed=true
```

A separate temporary SQLite witness inserted one legacy FAISS retrieval event
and ran the real rollup code against only that temporary database:

```text
derived_absolute_path_exposed=true
hits_preserved=1
score_count_preserved=1
score_sum_preserved=0.25
```

No configured database, endpoint, Qdrant service, model, cache, data root, or
live process was contacted.

## Selected Production Boundary

### `steps/common/memory_stores.py`

- Retain one portable logical FAISS reference derived from the index filename.
- Emit FAISS retrieval details with `store_type` and `store_ref` only; remove
  the redundant `index_path` field.
- Replace the seven warning fields with `store_ref`.
- Do not render raw exception text in those seven records. Preserve operation,
  `exc_type`, reason codes, and applicable vector/ID counts.
- Do not alter internal `self.index_path` use for file existence, locking,
  reading, writing, or configured store construction.

### `cli/observability_rollup.py`

- Preserve the existing `store_ref`-first and Qdrant-collection precedence.
- Convert only the legacy FAISS `index_path` fallback to the same portable
  logical filename, accepting both Windows and POSIX separator forms.
- Preserve aggregation keys, hit/score math, state advancement, limits, and
  idempotency.
- Do not rewrite raw retrieval events, migrate already-derived daily rows, or
  infer a stronger globally unique identity.

These two files share one rollback and verification gate: no newly emitted log,
event, or compatibility-derived row may contain the parent-path canary, while
all retrieval and rollup behavior remains unchanged.

## Mutation-Sensitive RED Contract

Add one isolated authority suite under
`tests/unit/test_retrieval_faiss_store_ref_privacy_authority.py` using temporary
paths/databases, fake FAISS modules, captured emitters/logs, and in-memory
values only.

The suite must prove:

1. a successful FAISS query returns the same hit and exact score/context while
   its event contains only `store_type=faiss` and the safe filename
   `store_ref`;
2. the parent-directory canary is absent from the event's `to_row()` and
   `to_dict()` projections;
3. a separate opaque non-path detail still round-trips unchanged, preventing
   central serializer redaction from satisfying the oracle;
4. an AST guard rejects `self.index_path` in the seven selected logger calls
   and rejects a literal `index_path` key in the selected FAISS event details;
5. all seven warning branches exclude the parent-directory canary and injected
   path-bearing exception text while preserving store, operation, safe
   `store_ref`, `exc_type`, and applicable reason/count evidence;
6. insert, query, telemetry-failure, and stats return behavior remains
   unchanged under every warning witness;
7. modern and legacy temporary retrieval rows aggregate under the same safe
   filename with exact hit/score totals and rollup state advancement;
8. a second rollup run is idempotent;
9. Windows- and POSIX-form legacy path strings both project to the same safe
   filename; and
10. Qdrant collection fallback and missing-reference behavior remain unchanged.

Place the canary only in the parent directory. The filename is the permitted
logical reference, so a global ban on the whole input string would create a
false oracle.

## Preserved Contracts

Frozen outside this seam:

- FAISS index existence, locking, reading, writing, IDs, hits, ranking,
  provenance attachment, and shadow scoring;
- exact query vectors, filters, `top_k`, and explicit retrieval context;
- immutable retrieval-event policy, existing-primary SQLite authority,
  replacement-safe schema, exact locked/busy fallback, and destination rules;
- lossless `RetrievalEvent.to_row()` and `to_dict()` behavior;
- route responses and the 69-operation route-effect census, including all four
  intentional retrieval `automatic_mutation` routes;
- historical raw-event cleanup and already-derived-row migration; and
- configured data, live services, identity, ingestion, WSL, public checkout,
  and the mixed main checkout.

## Separate Recorded Path-Privacy Candidates

The wider census found additional path-bearing producers with different event
schemas, lifecycle owners, and verification gates:

- summary and text-embedding FAISS diagnostics and `MemoryCommitEvent` targets;
- audio-embedding FAISS commit targets;
- scene visual-embedding FAISS warnings, result metadata, and commit targets;
- other source/database references inside ingestion commit-event details;
- generic epistemic hit payload fallback for `index_path`; and
- historical scene artifacts whose compatibility contracts explicitly mention
  `index_path`.

These are ingestion, commit-truth, or read-model seams rather than retrieval
event `store_ref` projection. Record them for later privacy evidence; do not
bundle them into this repair.

Analytics-question and derived-intent logging also remain separately owned
candidates from the prior query-log audit.

## Completion Gate

After clean RED evidence, the implementation must pass the dedicated authority
suite, existing FAISS ID/lock and retrieval SQLite/context/persistence suites,
observability rollup regressions, changed-Python compilation,
documentation/static gates, and independent implementation and oracle review.
The route census and retrieval classifications must remain unchanged.

Completion may claim that new retrieval FAISS references are path-free. It must
not claim that historical raw rows, already-derived rows, ingestion commit
events, or the full repository path surface have been cleaned.
