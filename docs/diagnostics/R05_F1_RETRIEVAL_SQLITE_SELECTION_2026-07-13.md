<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval SQLite Authority Selection

## Decision

Select the retrieval SQLite read-authority seam before retrieval telemetry.

Four existing-file projections still open ordinary write-capable SQLite
connections during retrieval:

- FTS and LIKE search over the memory database;
- knowledge-graph context used for multimodal scoring;
- memory-commit provenance attached to successful Qdrant and FAISS hits; and
- optional quantization shadow scoring after a FAISS query.

They require one shared existing-file, live-WAL-aware, no-write connection
authority. Successful-hit retrieval telemetry is a separate, intentional
durable-observability owner and keeps the four retrieval routes classified
`automatic_mutation`.

This was a read-only selection audit. No production code, configured database,
endpoint, Qdrant service, model, cache, ingestion path, identity surface, WSL
distribution, dependency, public checkout, or mixed main checkout was changed
or exercised.

## Governing Invariant

A retrieval projection may observe committed live-WAL truth, but it must not
possess authority to create a database, mutate schema or rows, attach another
database, create an external vacuum target, or weaken its own read-only policy.
Telemetry may write only through its explicit telemetry owner and policy.

## No-Repeat Boundary

The following R-05-F1 work remains checkpointed closed:

- Qdrant query-side collection no-create authority;
- ingest-status constructor and lookup no-create authority;
- summary video-status lock-free projection;
- text and CLIP exact local-only model resolution; and
- summary SQLite read authority.

The retrieval repair will reuse the proven summary capability contract without
reimplementing or behaviorally reopening the completed summary projections.

## Mounted Route and Effect Reconciliation

| Route | Retrieval projections | Intentional durable effect |
|---|---|---|
| `POST /api/search/multimodal` | FTS, Qdrant provenance, and KG scoring for text; Qdrant provenance for requested vector modalities | retrieval-event persistence after successful Qdrant hits |
| `GET /api/search/text` | FTS plus semantic-Qdrant provenance | retrieval-event persistence after successful Qdrant hits |
| `GET /api/search/visual` | Qdrant provenance after local CLIP encoding | retrieval-event persistence after successful Qdrant hits |
| `GET /api/videos/{video_id}/scenes/{scene_id}/similar` | delegates text, visual, and audio retrieval and therefore inherits FTS, provenance, and KG scoring | retrieval-event persistence after successful Qdrant hits |

`POST /api/search/temporal` is the passive control. Its SQLite reads already use
existing-file `mode=ro` URIs and see committed live-WAL rows while rejecting
writes and missing database creation.

## Exact SQLite Owners

### FTS memory projection

`retrieval/multimodal_search.py::search_fts()` checks that the configured memory
database exists, then opens it with ordinary `sqlite3.connect()`. It performs
FTS5 or LIKE reads. The missing-path guard preserves the current empty result,
and failures after a connection opens preserve the current logged empty/partial
fallback. Connection opening currently occurs outside that fallback boundary;
the repair must preserve propagation of an open-time race or failure rather than
silently changing route behavior. An existing handle still possesses DML, DDL,
ATTACH, VACUUM, and PRAGMA-downgrade capability.

### Knowledge-graph scoring projection

`retrieval/multimodal_search.py::_load_kg_scene_context()` checks that the
configured graph database is an existing file, then opens it with ordinary
`sqlite3.connect()`. Failure degrades to zero KG bonus. The returned projection
feeds multimodal metadata reranking.

### Hit-provenance projection

`steps/common/memory_provenance.py::attach_provenance_to_hits()` checks that the
memory database exists, then opens it with an ordinary connection using its
bounded timeout and cross-thread setting. It is best effort and never suppresses
successful hits, but the connection is capability-unbounded.

The provenance reader currently uses `PRAGMA table_info(...)` to detect an
optional column. The proven summary authorizer correctly rejects parameterized
PRAGMAs because the same authorization shape can alter connection policy. The
retrieval repair must replace that schema probe with a normal zero-row `SELECT`
whose cursor description supplies column names; it must not broaden the common
authorizer to permit arbitrary parameterized PRAGMAs.

### FAISS shadow-scoring projection

`steps/common/memory_stores.py::FaissMemory.query()` invokes the shared
provenance annotator after successful FAISS hits, so the provenance migration
also changes this non-mounted caller and must test it explicitly. The same
method optionally opens the memory database with ordinary `sqlite3.connect()`
to read quantization sidecars for shadow scoring. That read shares the exact
database capability, rollback boundary, and best-effort query lifecycle, so it
is included in this seam rather than left as an unnamed caller.

FAISS retrieval-event persistence remains a separate intentional telemetry
effect. This checkpoint does not claim that the four mounted API routes traverse
FAISS; it closes the shared read capability wherever the selected owner is used.

## Temporary Mutation Evidence

Seeded temporary databases and instrumented connection factories established:

```text
FTS write capability proved: true
KG write capability proved: true
provenance write capability proved: true
FAISS shadow-scoring write capability traced: true
missing guarded readers created files: false
mode=ro saw committed-in-WAL row: true
mode=ro rejected INSERT and DDL: true
mode=ro missing path stayed absent: true
```

The required live-WAL coordination behavior remains permitted. `immutable=1`
must not replace `mode=ro`, because it can miss committed rows still resident in
the WAL.

## Telemetry Is Deliberately Separate

`QdrantClient.query()` constructs retrieval events after successful hits and
`steps/common/retrieval_events.py::emit_retrieval_events()` creates schema and
indexes, inserts rows, and may append JSONL when SQLite is locked. This is
intentional best-effort audit observability, not an incidental read capability.
Removing it or silently suppressing it would change the product policy and make
the route-effect register untruthful.

The fresh trace also recorded four telemetry-policy gaps for the later
telemetry checkpoint:

- `MultimodalSearchEngine` does not propagate the configured log directory or
  complete retrieval-event policy into `QdrantClient`;
- a configured disabled JSONL fallback can therefore be ignored and locked-DB
  fallback can land beside the database;
- retrieval context is sourced from process-global `GOODQ_RETRIEVAL_CONTEXT`
  rather than request-scoped authority;
- raw query text is separately logged at INFO, while shared FAISS telemetry can
  include an absolute index path.

These findings belong to one explicit telemetry-policy seam. They do not widen
the retrieval SQLite repair, remove telemetry, or reclassify the routes.

## Shared Authority Decision

Do not copy the summary authorizer into a retrieval-specific module. Promote the
already-proven connection capability into one neutral common module, while
preserving `lib.summary_aggregator.open_summary_read_connection()` as a thin
compatibility wrapper with identical error, timeout, connection, and live-WAL
behavior.

The common primitive must support the provenance reader's existing bounded
timeout and `check_same_thread` choice without weakening the authorization
contract. This extraction and the four retrieval migrations share one
authority, rollback boundary, and verification gate; unrelated SQLite readers
remain outside scope.

## Exact Implementation Boundary

Expected production scope:

- `steps/common/sqlite_read_authority.py`: neutral existing-file read
  connection capability;
- `lib/summary_aggregator.py`: compatibility wrapper delegation only;
- `retrieval/multimodal_search.py`: FTS and KG readers;
- `steps/common/memory_provenance.py`: shared Qdrant/FAISS provenance reader and
  its zero-row schema projection; and
- `steps/common/memory_stores.py`: FAISS shadow-scoring reader only.

Focused tests may add one retrieval authority module and extend the completed
summary authority tests only where necessary to prove wrapper equivalence.

Frozen outside this rollback boundary:

- retrieval-event SQLite/JSONL persistence and policy;
- Qdrant collection/query authority;
- model registry, cache inspection, provisioning, and loaders;
- route responses and effect classifications;
- temporal retrieval, identity, ingest status, summary behavior, and all other
  SQLite callers;
- dependencies, active environments, configured data, services, and public
  release state.

## Mutation-Sensitive RED

Tests must fail against the current write-capable readers and prove:

1. an absent database, attached-database target, or vacuum target remains
   absent;
2. committed rows resident in a live WAL are visible;
3. `INSERT`, `UPDATE`, `DELETE`, DDL, `ATTACH`, `DETACH`, `VACUUM INTO`, and
   `PRAGMA query_only=OFF` are denied;
4. FTS, KG scoring, provenance, and FAISS shadow scoring all receive the common
   bounded connection and close it on success and failure;
5. provenance preserves its timeout, row mapping, optional-confidence-column,
   and best-effort behavior without a parameterized PRAGMA;
6. the FAISS caller preserves provenance annotation, quantization shadow
   behavior, and retrieval-event ownership;
7. the FTS missing-path and post-open fallback behavior remain unchanged, while
   an open-time race or failure continues to propagate;
8. replacing the bounded helper with ordinary `sqlite3.connect(path)` makes a
   seeded DDL/write oracle persist a marker and fail the suite; and
9. the completed summary readers retain their exact behavior through the
   compatibility wrapper.

## Verification Gate

Before the implementation checkpoint:

- run the focused retrieval and summary SQLite authority tests;
- run adjacent FTS, multimodal, provenance, FAISS ID-mapping/shadow, Qdrant-query,
  summary, route, and temporal regressions;
- prove absent-path purity and committed live-WAL visibility using temporary
  databases only;
- run Python compilation, diff, documentation authority/drift, banned-token,
  dependency-drift, and portable-path gates;
- confirm the mounted census remains 69 operations: 41 passive, 1 staging, 10
  automatic mutation, 8 curated mutation, and 9 process execution; and
- obtain independent implementation and evidence review before checkpointing.

## Selection Checkpoint Verification

Fresh selection gates passed:

- two independent read-only traces reconciled all four mounted retrieval routes,
  the shared Qdrant/FAISS provenance caller, FAISS shadow scoring, and explicit
  retrieval telemetry;
- temporary-only witnesses proved ordinary FTS, KG, provenance, and FAISS
  shadow-scoring write capability, existing missing-path purity, committed
  live-WAL visibility, and `mode=ro` write rejection;
- independent review found and closed the previously unnamed FAISS caller and an
  overstated FTS fallback boundary, then returned clean on rereview;
- documentation authority verification passed;
- documentation drift scanned 314 active files with zero active drive-root,
  path, ghost-path, snapshot-authority, corruption, or CUDA-policy findings;
- banned-token and dependency-drift gates passed;
- all 35 documentation-authority tests passed;
- all 74 route-effect authority tests passed and preserved the 69-operation
  census; and
- working-tree whitespace and changed-document literal-drive checks passed.

Only this evidence document, the sole roadmap, and the active bounded mission
changed during selection. No production implementation began before the clean
review and this checkpoint.

The telemetry-policy seam becomes the next R-05-F1 selection only after this
reader authority is checkpointed. No route becomes passive merely because its
incidental read capability is removed.
