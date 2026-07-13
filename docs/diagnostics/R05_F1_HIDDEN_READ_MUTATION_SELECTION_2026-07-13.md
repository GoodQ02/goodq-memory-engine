<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Hidden-Read Mutation Selection

## Outcome

The first bounded R-05-F1 implementation seam is Qdrant query no-create
authority in `steps/common/qdrant_client.py`.

`QdrantClient.query()` must require an existing collection through read-only
existence checks. It must never create a collection on the initial query or a
retry. Collection creation remains an explicit write-path responsibility used
by operations such as `upsert()`.

This was a read-only selection audit. No endpoint, configured data root,
Qdrant service, model, cache, ingestion path, operator data, WSL distribution,
or active process was exercised.

## No-Repeat Boundary

The following verified work remains closed unless contradictory evidence is
found:

- governed ingest request staging;
- the exhaustive route-effect registry and common loopback client boundary;
- MiniAgent confirmation/audit authority;
- action-job, summary-collection, video-summary, and temporal-summary
  checkpoints.

R-08 identity persistence/recovery and R-14 passive runtime status remain open
under their own roadmap owners. They are excluded from this seam, not claimed
complete.

This selection does not recreate any of those authorities and does not change
the completed July corpus or its promoted state.

## Exact Mounted Scope

R-05-F1 currently accounts for four registered retrieval operations and one
ingest-status operation that are classified `automatic_mutation`, plus six
summary reads whose passive implementation evidence required reconciliation:

- `POST /api/search/multimodal`;
- `GET /api/search/text`;
- `GET /api/search/visual`;
- `GET /api/videos/{video_id}/scenes/{scene_id}/similar`;
- `GET /api/ingest/status/{request_id}`; and
- the six mounted `/api/summary` GET projections.

The mounted operation census remains 69 operations: 40 passive reads, 1
request staging operation, 11 automatic mutations, 8 curated mutations, and 9
process executions. This selection changes no classification.

## Fresh Side-Effect Trace

### Retrieval

All four retrieval operations delegate to `MultimodalSearchEngine`, whose
Qdrant clients use `steps/common/qdrant_client.py`. The current query path calls
`ensure_collection()`. A missing-collection GET therefore falls through to a
PUT that creates the collection before the search POST. The retry path can
repeat the same create behavior.

The same routes retain other separately owned effects:

- successful hits can create or update retrieval-event SQLite schema/rows;
- a locked event database can append `retrieval_events.jsonl`;
- text and visual model loaders accept remote model identifiers without an
  enforced preseeded local-only contract; and
- FTS and provenance reads use ordinary write-capable SQLite connections.

These effects do not share the Qdrant collection owner's rollback boundary and
must not be bundled into the first repair.

### Ingest status

`GET /api/ingest/status/{request_id}` constructs
`IngestRequestLedger` before validating or loading the request. The constructor
unconditionally creates the request directory and missing parents. Existing
status tests precreate every runtime directory, so they cannot detect this
effect. Once the constructor behavior is removed, existing governed prepare,
confirm, cancel, lock, and atomic-write paths can retain explicit storage
creation.

### Summary reads

- collections and capabilities are already persistently passive;
- dashboard, entity, video-summary, and knowledge-graph fallback reads use
  ordinary write-capable SQLite connections and lack a shared read-only
  connection authority;
- video-summary status enters the writer-oriented action-job ledger and its
  lock boundary when the job root exists.

The SQLite projections require one shared WAL-aware read policy. Summary-job
status requires a separate passive record reader with its own atomic-replace
concurrency oracle. Neither belongs in the Qdrant transport change.

## Seeded RED Evidence

Temporary-root and fake-transport witnesses reproduced the retained effects
without live systems:

1. A fake missing Qdrant collection caused the current query path to issue
   `GET collection -> PUT collection -> POST search`.
2. One retrieval event against an absent temporary database created the SQLite
   database.
3. Constructing `IngestRequestLedger` against an absent temporary root created
   that directory.
4. The summary status path uses the writer ledger/lock API even when its
   projection is nominally read-only; a simple after-return directory snapshot
   did not retain a lock artifact, which is insufficient to prove that no
   transient create/lock operation occurred.

The Qdrant witness is the selected RED oracle: a query-side PUT is an external
mutation and must fail the new test immediately.

## Candidate Comparison

| Candidate | Owner and rollback boundary | Current impact | Selection |
|---|---|---|---|
| Qdrant query no-create | One query transport in `steps/common/qdrant_client.py` | External collection mutation shared by four routes | Selected first |
| Ingest-status no-create | One ledger constructor | Empty local directory creation on one GET | Next small local seam |
| Summary SQLite reads | One new shared SQLite read authority | Three projections and one fallback retain write-capable handles | Separate after WAL policy is explicit |
| Summary job status | Passive action-job record reader | Writer-ledger/lock boundary on one GET | Separate generic ledger seam |
| Retrieval telemetry | Event SQLite and JSONL persistence policy | Durable observability writes on successful hits | Separate governed-observability seam |
| Retrieval model/cache | Text and visual local model resolution | Possible cache population or download | Separate offline-model seam |
| Retrieval SQLite reads | FTS and provenance connections | Write-capable handles/sidecar risk | Separate shared read authority |

Qdrant is selected before the lower-risk ingest directory fix because it is the
highest-impact external mutation, affects all four retrieval operations, and
still has one exact owner and rollback boundary. This ordering removes the
most consequential authority error without widening scope.

## Selected Implementation Contract

1. Split collection inspection from collection creation inside
   `QdrantClient`.
2. `query()` uses only the inspection path. A missing collection returns the
   existing unavailable/empty query outcome without a PUT.
3. Query retry may recheck collection existence but may not create it.
4. `upsert()` retains the explicit ensure/create path and its current write
   behavior.
5. Existing-collection query behavior, payload filtering, response mapping,
   and retrieval-event behavior remain unchanged in this seam.
6. The four retrieval routes remain `automatic_mutation`; do not reclassify
   them until every remaining retrieval effect passes its own no-write oracle.

## Exact Owner and Verification Files

Production scope is limited to:

- `steps/common/qdrant_client.py`

Focused test scope is:

- a dedicated unit test for Qdrant read/write collection authority; and
- only directly affected existing Qdrant client tests if their current oracle
  proves stale.

The implementation gate must prove:

- initial missing collection: GET occurs, PUT never occurs, search POST never
  occurs, and the query returns the defined unavailable result;
- failed search followed by a missing collection: retry may GET but never PUT;
- existing collection: query POST and response projection remain unchanged;
- upsert against a missing collection still performs the explicit create and
  write path;
- a mutation-sensitive control using the current create-on-query behavior
  fails the no-PUT oracle; and
- the route-effect census and all unrelated route classifications remain
  unchanged.

No live Qdrant process or configured collection is required. Use fake HTTP
responses only.

## Selection Verification

Fresh checkpoint evidence passed:

- three independent read-only traces covering retrieval, ingest status, and
  all six summary projections;
- a temporary fake-transport RED witness that observed query-side
  `GET -> PUT -> POST` against a missing collection;
- all 75 route-effect authority tests;
- all 35 documentation-authority unit tests;
- documentation authority and generated-index verification;
- documentation drift across 306 active files with zero active path,
  drive-root, ghost-path, snapshot-authority, or corruption findings;
- banned-token and dependency-drift gates; and
- whitespace/diff validation.

Independent review found one status-wording defect that described the open
R-08 and R-14 owners as completed. The wording was corrected, and focused
re-review returned clean.

## Explicit Exclusions

This seam must not change:

- retrieval-event persistence or JSONL fallback;
- model provisioning, model registry, cache roots, or dependency versions;
- FTS, provenance, summary, identity, or ingest-status SQLite behavior;
- ingest request ledgers or configured runtime directories;
- routes, response models, browser code, client locality, LAN bindings, or
  active services; or
- route-effect classifications.
