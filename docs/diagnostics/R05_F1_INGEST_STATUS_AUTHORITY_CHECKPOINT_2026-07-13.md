<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Ingest-Status Authority Checkpoint

## Outcome

Ingest-status lookup is now persistently passive. `IngestRequestLedger`
construction binds a path without creating it, so an invalid or unknown request
cannot create the request root or missing parents before returning 400 or 404.

Explicit mutation retains storage authority:

- `create_record()` creates its missing parent through the atomic JSON writer;
- prepare creates the ledger, lock, and pending-file storage it needs; and
- confirm creates the governed inbox destination before staging the file.

No request schema, response model, confirmation scope, cleanup policy, route,
configured path, ingestion execution, or live runtime changed in this seam.

## Authority Boundary

Ledger construction and record lookup are reads. Record creation, transition,
locking, pending-file preparation, and inbox staging are writes owned by the
existing governed submit path.

The status route may:

- validate one exact request ID;
- read an existing request record;
- inspect Watchdog state and file existence; and
- return the existing redacted public projection.

It may not initialize storage, acquire a write lock, persist an observation, or
create a missing path.

## Checkpoint Commit

| Commit | Evidence seam |
|---|---|
| `7a1a38b9` | Made ledger construction passive, preserved cold-start staging, and reclassified only ingest status |

## TDD Evidence

The corrected RED run produced exactly three expected failures:

- a valid unknown request returned 404 but created the request root and parent;
- an invalid request ID returned 400 but created the same paths; and
- constructor-only setup created the root before explicit `create_record()`.

The existing-record witness already reached its expected response without
changing the seeded tree. After removing the constructor `mkdir`, all ten
focused status and ledger tests passed.

The wider regression then exposed one test fixture that had seeded raw ledger
files without explicitly creating its test directory. The fixture was corrected
to own that setup. A cold-start prepare/confirm control was added with every
runtime root absent. It proves prepare returns 201 with a durable record and
pending file, confirm returns 202, and exactly one inbox file is staged.

## Immutable-Read Evidence

Temporary-root witnesses prove:

- valid missing status leaves an absent tree absent;
- invalid status leaves an absent tree absent; and
- an existing request plus Watchdog completion projection leaves every relative
  path, file byte, file size, and file/directory modification time unchanged.

The prior constructor is mutation-sensitive to the first two witnesses and the
constructor-only write control.

## Fresh Verification

Fresh verification passed:

- 10 focused status and ledger tests after the minimal production change;
- the cold-start prepare/confirm control;
- 112 status, ledger, submit, staging-convergence, and route-authority tests;
- Python compilation for all six changed Python files;
- whitespace/diff validation; and
- independent implementation review with no findings.

No live endpoint, Qdrant process, configured collection, model, cache,
configured data root, ingestion job, identity surface, WSL distribution,
operator data, public checkout, or frozen mixed checkout was exercised.

## Route-Effect Truth

Only `GET /api/ingest/status/{request_id}` changed classification. The mounted
operation census is now:

| Effect | Count |
|---|---:|
| `passive_read` | 41 |
| `request_staging` | 1 |
| `automatic_mutation` | 10 |
| `curated_mutation` | 8 |
| `process_execution` | 9 |
| **Mounted method/path operations** | **69** |

The four retrieval routes remain `automatic_mutation`. Their event persistence,
model/cache resolution, and write-capable SQLite effects remain open. Summary
SQLite projections and summary-job status also retain separate unproven read
boundaries.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- constructor-side request-root creation;
- valid-missing and invalid status no-create witnesses;
- existing request byte/size/mtime immutability;
- explicit create-on-record authority; or
- cold-start prepare/confirm storage creation.

## Next Bounded Mission

Run a fresh read-only comparison of the remaining R-05-F1 candidates: summary
SQLite reads, summary-job status, retrieval telemetry, retrieval model/cache
resolution, and retrieval SQLite reads. Select one exact owner and rollback
boundary before any further production edit. Do not infer the next seam solely
from the older selection order.
