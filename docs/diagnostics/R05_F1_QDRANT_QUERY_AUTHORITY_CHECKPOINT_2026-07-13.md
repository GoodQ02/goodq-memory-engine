<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Qdrant Query Authority Checkpoint

## Outcome

Qdrant queries can no longer create a missing collection. The shared client now
separates GET-only collection inspection from explicit collection creation:

- `QdrantClient.query()` uses `collection_exists()` on its initial and retry
  paths;
- a definite missing-collection response returns an empty/unavailable query
  result immediately;
- indeterminate inspection failures receive one bounded GET-only retry; and
- `ensure_collection()` remains unchanged for explicit write paths such as
  `upsert()`.

No route, response, browser, model, telemetry, SQLite, ingest, identity, client
locality, or route-effect classification changed in this seam.

## Authority Boundary

Collection existence inspection is now a read operation. Collection creation
remains a write operation.

The query boundary permits:

- `GET /collections/{collection}` to inspect availability; and
- `POST /collections/{collection}/points/search` only after availability is
  established.

It never permits query-side PUT. Search failure clears the cached availability
flag; the bounded recheck remains GET-only. A missing collection therefore
cannot be created by any caller that reaches `QdrantClient.query()`.

The explicit write boundary remains:

- `ensure_collection()` may create a missing collection; and
- `upsert()` may call that authority before writing points.

## Checkpoint Commits

| Commit | Evidence seam |
|---|---|
| `e49b86b8` | Selected Qdrant query no-create as the first R-05-F1 repair |
| `d16e7fdb` | Split GET-only query inspection from write-path creation |

## TDD Evidence

The first RED run produced exactly two expected failures:

- initial missing collection issued `GET -> PUT -> POST`; and
- retry after collection disappearance issued `GET -> POST -> GET -> PUT -> POST`.

The existing-collection query and missing-collection upsert controls passed in
that same run. After the minimal inspection split, all four tests passed.

Independent review then found that the first implementation had reduced the
former bounded availability retry to one GET. A new transient-failure test was
added first and failed with one observed GET. The implementation was corrected
to retry indeterminate inspection failure once using GET only; the focused file
then passed all five tests. A definite 404 remains immediate and noncreating.

The directly affected payload-invariant test was updated to use the read-only
inspection hook. Its optional live-Qdrant sweep was removed because a
best-effort live probe is neither deterministic evidence nor permitted by this
temporary/fake-transport seam.

## Fresh Verification

Fresh verification passed:

- 5 focused query-authority tests;
- 6 query-authority plus payload-invariant tests;
- 283 adjacent Qdrant, UCF retrieval, hybrid-search, MiniAgent, payload, and
  route-effect tests;
- Python compilation for all three changed Python files;
- whitespace/diff validation; and
- independent implementation re-review after the retry finding was closed.

No live endpoint, Qdrant process, configured collection, model, cache,
configured data root, ingestion path, identity surface, WSL distribution,
operator data, public checkout, or frozen mixed checkout was exercised.

## Route-Effect Truth

The mounted operation census remains:

| Effect | Count |
|---|---:|
| `passive_read` | 40 |
| `request_staging` | 1 |
| `automatic_mutation` | 11 |
| `curated_mutation` | 8 |
| `process_execution` | 9 |
| **Mounted method/path operations** | **69** |

The four retrieval routes remain `automatic_mutation`. Query-side collection
creation is closed, but retrieval-event SQLite/JSONL persistence, text and
visual model/cache resolution, and write-capable FTS/provenance SQLite reads
remain open under R-05-F1.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- query-side collection creation or a query policy that permits PUT;
- the GET-only initial and bounded retry inspection oracles;
- explicit create-on-upsert authority; or
- deterministic payload-invariant coverage without a live Qdrant probe.

## Next Bounded Mission

The next R-05-F1 seam is ingest-status no-create authority. The prior
three-way audit already proved that `IngestRequestLedger.__init__()` is the
single persistent write owner: it creates the request root before request-ID
validation or record loading. The next seam must make construction passive,
preserve explicit storage creation in governed mutating paths, prove immutable
status reads, and reclassify only that GET after its oracle passes.
