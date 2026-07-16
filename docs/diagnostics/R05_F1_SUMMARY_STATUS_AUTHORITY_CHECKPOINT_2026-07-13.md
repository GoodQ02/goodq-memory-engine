<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Summary-Status Authority Checkpoint

## Outcome

Summary video-job status is now persistently passive. Exact-ID and latest-job
projections use a reader that binds only the configured path and never creates
the action-job root, constructs or acquires the writer lock, or changes a job
record.

The Windows concurrency witness also closed the sharing boundary discovered by
the first RED run:

- passive reads open action-job records with read, write, and delete sharing;
- action-job writers use an opt-in replacement helper compatible with those
  readers; and
- the generic atomic JSON writer and every unrelated caller retain their prior
  `os.replace()` behavior.

No response, route, route-effect classification, action-job lifecycle edge,
retrieval, model, SQLite, ingestion, identity, runtime, or configured-data
behavior changed in this seam.

## Authority Boundary

`PassiveActionJobReader` owns read-only action-job projection. It may:

- read one validated job ID;
- select the latest record for one exact operation and normalized scope; and
- tolerate the bounded replacement window while returning only a complete old
  or new record.

It may not initialize storage, construct or acquire `FileLock`, persist an
observation, or alter a job.

`ActionJobLedger` remains the sole lifecycle writer. All five current
persistence sites still run under the existing ledger lock and use the scoped
concurrent-reader replacement helper. Transitions, reconciliation, ownership,
ordering, validation, and public redaction are unchanged.

## Checkpoint Commits

| Commit | Evidence seam |
|---|---|
| `542fa6d0` | Selected summary status as the smallest remaining hidden-read effect |
| `782aa0bc` | Corrected the Windows reader/writer concurrency rollback boundary |
| `102283e7` | Added the passive reader and compatible action-job replacement path |

## TDD Evidence

The first RED run failed on the intended boundary:

- the passive reader did not exist;
- latest summary status entered the writer lock; and
- the existing writer control still acquired its lock.

The first minimal lock-free reader then exposed a deeper Windows failure: a
normal Python read could make the concurrent `os.replace()` writer fail with
`PermissionError`. Opening the reader with delete sharing alone did not repair
that writer failure. A bounded `ReplaceFileW` control succeeded, so the roadmap
and bounded mission were corrected before implementation continued.

The final tests prove absent-root no-create behavior, exact/latest no-lock
behavior, operation/scope filtering, writer-lock retention, scoped replacement,
and complete-record concurrency. Both exact and latest concurrency witnesses
passed ten consecutive stress repetitions.

## Fresh Verification

Fresh verification passed:

- 103 action-job tests;
- 128 summary-route tests;
- 119 generic-atomic, route-authority, Qdrant-query, and governed-ingest
  regression tests;
- 10 consecutive repetitions of both Windows concurrency witnesses;
- the 69-operation route census with 41 passive reads, 1 request staging,
  10 automatic mutations, 8 curated mutations, and 9 process executions;
- Python compilation for all five changed Python files;
- staged and unstaged whitespace/diff checks; and
- independent implementation review with no actionable findings.

The reviewer recorded one non-blocking consistency boundary: after 50 ms of
continuous writer activity, latest-record projection falls back to a lock-free
scan and may observe a complete transient cross-record view. Individual records
remain atomic, exact reads remain complete, and the status surface remains
eventually consistent.

No live endpoint, Qdrant process, configured collection, model, cache,
configured data root, ingestion job, identity surface, WSL distribution,
operator data, public checkout, or frozen mixed checkout was exercised.

## Route-Effect Truth

No route classification changed. The mounted operation census remains:

| Effect | Count |
|---|---:|
| `passive_read` | 41 |
| `request_staging` | 1 |
| `automatic_mutation` | 10 |
| `curated_mutation` | 8 |
| `process_execution` | 9 |
| **Mounted method/path operations** | **69** |

The four retrieval routes remain `automatic_mutation`. Retrieval telemetry,
text/visual model and cache resolution, retrieval SQLite reads, and summary
SQLite projection policy remain open under R-05-F1.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- constructor-side action-job root or lock creation in status reads;
- exact/latest summary status through the writer ledger;
- ordinary Python reads of concurrently replaced action-job records;
- genericizing the action-job-only replacement helper; or
- weakening the complete-record concurrency or writer-lock controls.

## Next Bounded Mission

Run a fresh read-only comparison of the remaining R-05-F1 effects: retrieval
telemetry, text/visual local-only model resolution, retrieval SQLite reads, and
summary SQLite projections. Select one exact owner and rollback boundary before
another production edit. Do not infer the next seam solely from an older order.
