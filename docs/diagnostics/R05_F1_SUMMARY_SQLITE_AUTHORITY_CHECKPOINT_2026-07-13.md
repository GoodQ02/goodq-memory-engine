<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Summary SQLite Read-Authority Checkpoint

## Outcome

The four summary-owned SQLite projections now open only an existing database
through one bounded read primitive. They preserve visibility of committed rows
that remain in a live WAL while denying main-database writes, schema changes,
temporary schema changes, attached databases, external database copies, and
read-only-policy downgrade.

Private implementation checkpoint:

```text
f5456d33 fix: bound summary sqlite read authority
```

This checkpoint closes summary SQLite authority only. Retrieval SQLite and
intentional retrieval telemetry remain open under R-05-F1. Route effects,
responses, retrieval, collection writers, and summary action-job lifecycle did
not change.

## Exact Authority Boundary

`lib/summary_aggregator.py` owns `open_summary_read_connection()`. The helper:

- resolves one exact existing file and rejects an absent or non-file path;
- opens the canonical file URI with `mode=ro`;
- enables and verifies `PRAGMA query_only=ON`;
- installs a SQLite authorizer that denies `ATTACH`, `DETACH`, DML, DDL,
  virtual-table changes, `REINDEX`, `ANALYZE`, and PRAGMA assignments; and
- closes the connection if read-policy setup fails.

The exact four migrated readers are:

1. cumulative summary dashboard projection;
2. entity-profile projection;
3. persisted video-summary projection; and
4. knowledge-graph video-existence fallback.

Each caller owns a `finally` close boundary. Summary collection writers and the
video-summary process route remain outside this read helper and retain their
existing authority.

## Why URI Read-Only Plus `query_only` Was Not Enough

The first implementation used `mode=ro` and `PRAGMA query_only=ON`. It correctly
rejected main-database DML/DDL and preserved committed WAL visibility, but
independent review found a capability escape:

- `ATTACH DATABASE <absent path>` created a new external database;
- `VACUUM INTO <absent path>` created the target before failing read-only; and
- `PRAGMA query_only=OFF` revoked the connection-level policy.

These are capability-contract failures even though the four current routes use
fixed SQL and expose no demonstrated injection path. The authorizer closes the
SQL authority itself instead of relying on the current callers to remain
benign.

## Mutation-Sensitive Evidence

The initial RED produced five intended failures: the read helper did not exist,
and ordinary dashboard/entity connects created missing database files. The
first implementation made those oracles green.

The review-driven RED then reproduced external database creation and policy
downgrade. The corrected focused witnesses prove:

- a missing main database, WAL, and shared-memory file remain absent;
- committed uncheckpointed WAL rows remain visible;
- main `INSERT` and `CREATE TABLE` are denied;
- parameterized `ATTACH` is denied and leaves its target absent;
- `VACUUM INTO` is denied and leaves its target absent;
- `PRAGMA query_only=OFF` is denied and `query_only` remains `1`;
- all four projections use the shared bounded helper; and
- every returned connection is closed after its caller completes.

The adjacent regression gate also caught and corrected one accidental cursor
interaction change before checkpoint. The persisted-summary query retains its
prior separate `execute()` then `fetchall()` sequence and response behavior.

## Fresh Verification

The post-review gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Focused summary SQLite authority | 8 passed |
| Summary, route, console, temporal, ingest-summary, and route-effect union | 372 passed |
| Independent focused rereview | CLEAN; 293 tests passed |

Additional gates:

- all four changed Python files parsed successfully;
- staged and working-tree diff checks passed;
- the mounted route census remained 69 operations: 41 passive reads, 1 request
  staging, 10 automatic mutations, 8 curated mutations, and 9 process
  executions;
- no targeted reader retains a direct write-capable `sqlite3.connect()`; and
- independent adversarial probes denied literal and parameterized attachment,
  external copy, query-only downgrade, temporary DDL, and main DML while
  preserving committed WAL reads.

No live endpoint, configured database, Qdrant service, model, cache, configured
data root, ingestion, identity surface, WSL distribution, public checkout, or
mixed main checkout was exercised.

## Current Library Contract

The implementation follows the current Python SQLite authorizer contract:

- [Python `sqlite3.Connection.set_authorizer`](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.set_authorizer)
  receives SQLite action codes and permits a callback to return
  `SQLITE_OK`, `SQLITE_DENY`, or `SQLITE_IGNORE`.
- [SQLite read-only WAL guidance](https://www.sqlite.org/wal.html#read_only_databases)
  explains why a read-only client may need existing WAL coordination state.
- [SQLite URI filenames](https://www.sqlite.org/uri.html)
  define `mode=ro`; it prevents opening the main database read-write but does
  not replace operation-level authorization.

## Residual Boundary

There is a local path-replacement race between strict path resolution and
SQLite open. It could change which existing file is observed, but the opened
main database remains URI read-only and the authorizer denies creation/write
authority. The database path is trusted local configuration, so this is not an
actionable expansion of the current seam.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- the completed Windows `mode=ro` versus `immutable=1` WAL comparison;
- summary reads through ordinary write-capable connects;
- summary SQLite attachment or external-copy capability;
- the four-reader migration and close boundary; or
- summary/retrieval route reclassification from this checkpoint alone.

## Next Bounded Mission

Run a fresh read-only selection between the remaining retrieval SQLite effect
and intentional retrieval telemetry. Select one exact owner, mutation oracle,
and rollback boundary before another production edit. Qdrant query authority,
ingest status, summary status, model-cache authority, and summary SQLite are
closed checkpoints and must remain frozen.
