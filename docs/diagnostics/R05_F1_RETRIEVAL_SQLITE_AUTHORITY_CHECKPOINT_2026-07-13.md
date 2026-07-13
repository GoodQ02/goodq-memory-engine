<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval SQLite Read-Authority Checkpoint

## Outcome

The selected retrieval SQLite projections now share one existing-file,
live-WAL-aware read capability. The capability preserves each caller's prior
success and failure boundary while denying database creation, row and schema
mutation, attached-database authority, external vacuum targets, and read-policy
downgrade.

Private implementation checkpoint:

```text
38498c38 fix: bound retrieval sqlite read authority
```

This checkpoint closes retrieval SQLite authority only. Successful-hit
retrieval telemetry remains intentional best-effort durable observability, so
the four mounted retrieval routes remain `automatic_mutation`. No telemetry,
route, response, model, Qdrant, provisioning, or configured-runtime behavior
changed.

## Exact Authority Boundary

`steps/common/sqlite_read_authority.py` owns the neutral connection primitive.
It:

- resolves one exact existing regular file and rejects an absent path;
- opens the resolved file URI with `mode=ro`;
- enables and verifies `PRAGMA query_only=ON`;
- installs an operation authorizer that denies `ATTACH`, `DETACH`, DML, DDL,
  temporary and virtual schema changes, `ALTER`, `REINDEX`, `ANALYZE`, and
  PRAGMA assignments;
- preserves caller-selected timeout and thread-affinity settings; and
- closes the connection if policy setup fails.

The exact migrated readers are:

1. FTS5 or LIKE search over the memory database;
2. knowledge-graph context used for multimodal scoring;
3. shared memory-commit provenance attached to Qdrant and FAISS hits; and
4. optional FAISS quantization shadow scoring.

`lib.summary_aggregator.open_summary_read_connection()` remains the summary
compatibility API and delegates to the same neutral primitive with its existing
unavailable-database message, timeout, thread policy, and caller failure
boundaries. The rare query-only setup failure now uses the common helper's
generic policy message; no caller contract or fallback boundary depends on that
text. Summary callers were not otherwise behaviorally reopened.

## Preserved Caller Contracts

- FTS still returns an empty result when its guarded database path is absent,
  retains real FTS5 `MATCH` and hidden-rank behavior, closes after success or a
  post-open query failure, and still propagates an open-time race or failure.
- Knowledge-graph scoring remains best effort, caches an error after failure,
  and degrades to no KG bonus.
- Provenance retains its short timeout, cross-thread setting, `sqlite3.Row`
  mapping, optional `confidence_json` support, and never suppresses successful
  hits.
- Provenance schema discovery now uses a zero-row normal projection and cursor
  description instead of a parameterized PRAGMA; the common policy was not
  weakened for schema inspection.
- FAISS retains hit provenance, quantization shadow scoring, failure fallback,
  and telemetry emission. The shadow connection now closes in a `finally`
  boundary when sidecar reads fail.

## Mutation-Sensitive Evidence

The initial RED instrumented each ordinary connection so that retaining a
write-capable direct connect persisted a forbidden marker. FTS, KG,
provenance, and FAISS shadow scoring all failed that oracle before the repair.

The completed witnesses prove:

- missing databases, WAL files, shared-memory files, attach targets, and vacuum
  targets remain absent;
- committed rows resident in a live WAL remain visible;
- `INSERT`, `UPDATE`, `DELETE`, main and temporary DDL, `ALTER`, `DROP`,
  `ATTACH`, `DETACH`, `VACUUM INTO`, and `PRAGMA query_only=OFF` are denied;
- real FTS5 `MATCH` and rank projection remain authorized;
- paths containing spaces, `#`, and `%` are encoded as working file URIs;
- the actual `sqlite3.connect` call is pinned to the resolved URI plus
  `?mode=ro`, `uri=True`, and the requested timeout/thread settings;
- setup failure and every selected caller success/failure path close the
  connection; and
- replacing any selected caller with ordinary `sqlite3.connect(path)` makes its
  marker oracle fail.

## Fresh Verification

The post-review gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Focused retrieval SQLite authority | 24 passed |
| Adjacent retrieval, FAISS, Qdrant, summary, temporal, ingest-summary, and route-effect union | 448 passed |
| Independent implementation rereview | CLEAN; targeted 3 passed |
| Independent adversarial SQLite review | CLEAN; no actionable finding |

Additional evidence:

- all six changed Python files compiled;
- staged and working-tree diff checks passed;
- the mounted route census remained 69 operations: 41 passive reads, 1 request
  staging, 10 automatic mutations, 8 curated mutations, and 9 process
  executions;
- the only direct `sqlite3.connect()` in the selected production surface is
  inside the common authority primitive; and
- adversarial temporary-only probes preserved live-WAL and FTS5 reads while
  denying main, temporary, attached, vacuum, and policy mutations without
  changing an existing attached target or leaving an external target behind.

Three pre-existing search-route test modules remain excluded from this adjacent
union because their dynamic loader executes the route dataclass before placing
the module in `sys.modules`, causing collection failure before any retrieval
test runs. The same harness defect was already recorded during model-cache
selection. It is unrelated to this authority seam and was not patched here.

No live endpoint, configured database, Qdrant service, model, cache, configured
data root, ingestion, identity surface, WSL distribution, public checkout, or
mixed main checkout was exercised.

## Residual Trust Boundary

The helper constrains SQL issued through the returned connection. Trusted
in-process Python could deliberately remove its own authorizer through the
connection API, but none of the selected fixed-SQL readers exposes that control
or user-supplied SQL. Expanding this seam into a wrapper for hostile in-process
code is not justified by current evidence.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- ordinary write-capable SQLite handles in the four selected readers;
- the completed summary compatibility wrapper;
- provenance schema inspection through parameterized PRAGMA authority;
- the FAISS shadow connection leak on query failure;
- live-WAL versus `immutable=1` evaluation; or
- route reclassification while intentional telemetry remains enabled.

## Next Bounded Mission

Run a fresh read-only selection of the intentional retrieval telemetry-policy
seam. Reconcile destination and JSONL-fallback policy propagation,
request-scoped context authority, raw-query log privacy, and FAISS detail
redaction before selecting one owner and mutation oracle. Do not remove the
durable audit effect or reclassify the routes merely because incidental SQLite
write capability is now closed.
