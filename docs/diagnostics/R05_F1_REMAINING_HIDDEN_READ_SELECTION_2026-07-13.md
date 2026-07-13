<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Remaining Hidden-Read Selection

## Outcome

The next bounded R-05-F1 implementation seam is the passive summary video-job
status reader.

`GET /api/summary/video/{video_hash}/status` must project existing action-job
records without constructing the writer-oriented ledger, acquiring its file
lock, creating a transient lock file, or creating the job root. The existing
`ActionJobLedger` retains exclusive ownership of creation, locking, lifecycle
transitions, and atomic writes.

This was a read-only selection audit. No production code, live endpoint,
configured data root, SQLite database, Qdrant service, model, cache, ingestion
path, WSL distribution, or active process was changed or exercised.

## No-Repeat Boundary

The following R-05-F1 repairs remain closed unless contradictory focused
evidence appears:

- Qdrant query-side collection creation;
- ingest-status constructor directory creation;
- governed ingest request staging; and
- the mounted route-effect/client boundary.

The four retrieval operations remain `automatic_mutation` while their
telemetry, model/cache, and SQLite effects remain open. This selection does not
reclassify them or recreate any completed retrieval or ingestion work.

## Fresh Candidate Reconciliation

| Candidate | Mounted effect | Exact owner and rollback boundary | Disposition |
|---|---|---|---|
| Summary job status | A latest-job GET enters the writer ledger lock and creates `.action-jobs.lock` transiently | One passive action-job record reader and one summary GET | Selected |
| Summary SQLite projections | Four passive projections open write-capable SQLite handles | Shared SQLite reader across summary route and aggregator code | Separate after live-WAL semantics are explicit |
| Retrieval telemetry | Successful hits create schema/rows or append fallback JSONL | Retrieval-event persistence policy plus Qdrant and memory-store callers | Intentional governed-observability seam |
| Retrieval model/cache | Text and visual loaders pass Hub identifiers without a preseeded local-only contract | Two loaders plus a currently write-logging model provisioner | Separate offline-model seam |
| Retrieval SQLite reads | FTS and provenance/KG projections open write-capable handles | Shared retrieval SQLite reader | Separate with the SQLite/WAL policy |

The selected status seam is the only remaining candidate that is both
registered `passive_read` and freshly proven to perform a persistent-filesystem
operation on its ordinary latest-record path. It also has one exact owner,
rollback boundary, and deterministic mutation oracle.

## Exact Status Trace

`api/routes/summary.py::get_summary_status()` correctly short-circuits when the
configured job root is absent. When the root exists:

- an exact `job_id` calls `ActionJobLedger.load()` and does not acquire the
  ledger lock; but
- the ordinary no-`job_id` projection calls `ActionJobLedger.latest()`, which
  delegates to `list_records()` and enters `self._lock`.

`ActionJobLedger.__init__()` is writer-oriented: it ensures the root exists and
binds a `FileLock` at `.action-jobs.lock`. On Windows, the latest-record read
creates that lock file while the lock is held and removes it after release.
A final-tree-only test therefore misses the mutation.

## Seeded Temporary Evidence

A seeded temporary action-job ledger and lock spy produced this exact evidence:

```text
before=false
entered=1
during=true
after=false
job_match=true
```

The same bounded audit established the independent candidate effects:

- emitting one retrieval event against an absent temporary database created
  the SQLite database and one row;
- forcing SQLite lock contention appended one
  `retrieval_events.jsonl` fallback row;
- fake text and visual model loaders received only the remote identifiers
  `all-MiniLM-L6-v2` and `openai/clip-vit-large-patch14`; neither call supplied
  a local snapshot path or local-only control; and
- an ordinary temporary SQLite handle persisted DDL, while a `mode=ro` URI
  rejected the same operation.

These witnesses prove the candidates are real, but they do not share the
summary status lock owner's rollback boundary.

## Why the Other Candidates Are Not Bundled

### SQLite projections

Dashboard, entity, video-summary, knowledge-graph fallback, FTS, and retrieval
provenance reads use ordinary SQLite handles. Their repair needs one deliberate
policy for live WAL visibility. `immutable=1` must not be added reflexively
because it can ignore uncheckpointed WAL content. The future seam must choose
and test the required live-read semantics before changing connections.

### Retrieval telemetry

Retrieval-event rows and JSONL fallback are intentional durable observability,
not an accidental constructor side effect. Removing, staging, or retaining
them changes the observability contract and route classification. That decision
requires its own policy and rollback gate.

### Retrieval models and cache

Audio retrieval already demonstrates the desired preseeded-local behavior.
Text and visual retrieval do not. The existing model provisioner cannot simply
be called in offline mode from a nominal read because cache hits and misses both
write download-event logs. This seam therefore needs a pure cache inspector or
resolver before the loaders can be made local-only without importing another
hidden write.

## Selected Implementation Contract

1. Add a non-creating, lock-free passive action-job record reader that reuses
   the current job-ID and persisted-record validation contract.
2. Use that reader for both exact-ID and latest matching video-summary status
   projections.
3. Preserve the absent-root `not_started`/404 behavior without constructing a
   ledger or creating a directory.
4. Preserve response shape, scope filtering, operation filtering, sort order,
   and error behavior.
5. Keep `ActionJobLedger`, its lock, atomic writes, lifecycle transitions,
   startup reconciliation, and all process/curated routes unchanged.
6. Keep the mounted route classified `passive_read`; all route census totals
   remain unchanged.

## Exact Scope and Verification Gate

Expected production scope:

- `api/utils/action_jobs.py`;
- `api/routes/summary.py`.

Focused verification scope:

- summary video-status route tests; and
- action-job reader/ledger tests needed to prove the authority split.

The implementation gate must prove:

- absent root: no directory or file is created;
- exact-ID and latest-record status: no file-lock acquisition occurs and no
  transient lock file appears;
- existing paths, bytes, sizes, and modification times remain unchanged;
- operation and scope filtering still reject unrelated jobs;
- an atomic-replace race yields only a complete old or new JSON record, never
  a partial projection;
- writer operations still acquire the ledger lock and persist atomically; and
- the route-effect census remains 69 operations: 41 passive, 1 staging, 10
  automatic mutation, 8 curated mutation, and 9 process execution.

The mutation-sensitive RED oracle is lock entry itself, not merely the final
directory snapshot. The current implementation must fail because the ordinary
latest-record route enters the writer lock once.

## Selection Verification

Fresh checkpoint gates passed:

- independent read-only traces for the summary/job and retrieval candidates;
- four temporary-only witnesses covering transient action-job locking,
  retrieval-event SQLite/JSONL persistence, text/visual loader arguments, and
  ordinary-versus-read-only SQLite capability;
- documentation authority and generated-index verification;
- documentation drift across 309 active files with zero active path,
  drive-root, ghost-path, snapshot-authority, or corruption findings;
- banned-token and dependency-drift gates;
- all 109 focused documentation-authority and route-effect tests; and
- staged/unstaged whitespace checks plus a changed-doc literal-drive scan.

The repository contained no production-code change during selection. The
implementation mission begins only after this evidence checkpoint is reviewed
and committed.

## Explicit Exclusions

This seam must not change:

- retrieval-event persistence or JSONL fallback;
- model registry, provisioning, cache roots, dependency versions, or model
  loading;
- SQLite connection policy for summary, FTS, provenance, identity, or runtime;
- Qdrant, ingestion, identity, temporal-summary, or action-job lifecycle
  behavior;
- configured data, active services, browser code, LAN bindings, or public
  release state.
