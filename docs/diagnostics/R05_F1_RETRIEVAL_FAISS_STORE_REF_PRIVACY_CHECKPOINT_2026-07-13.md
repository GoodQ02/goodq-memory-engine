<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval FAISS Store-Reference Privacy Checkpoint

## Outcome

New FAISS retrieval references now expose only the portable logical index
filename. Absolute configured paths no longer enter successful retrieval-event
details, the seven selected warning branches, or future daily rollup rows
created from legacy FAISS event input.

Private implementation checkpoint:

```text
cae887d3 fix: redact retrieval faiss store references
```

Supporting evidence checkpoints:

```text
c9054eea test: define retrieval faiss reference privacy
489dfc83 docs: correct faiss privacy witness scope
41d94f3a docs: select retrieval faiss reference privacy
```

This closes only newly emitted and compatibility-derived retrieval references.
It does not rewrite historical raw events, migrate already-derived daily rows,
or change separately owned ingestion and memory-commit artifacts.

## Exact Authority Boundary

`steps/common/memory_stores.py` retains the configured path for actual FAISS
existence checks, locking, reads, and writes. A small output projection derives
the filename only when a retrieval reference leaves that internal boundary.

The successful FAISS event now contains exactly:

- `store_type=faiss`; and
- `store_ref=<index filename>`.

The seven selected warnings retain store, operation, logical `store_ref`, and
the applicable reason, count, or exception-type evidence. They no longer render
the configured path or raw exception text that can repeat it.

`cli/observability_rollup.py` keeps the existing precedence:

1. an explicit `details.store_ref`;
2. a Qdrant `details.collection`; then
3. the legacy FAISS `details.index_path` compatibility branch.

Only the third branch changes. Windows- and POSIX-form legacy strings now
project to their filename before a new `retrieval_events_daily.store_ref` value
is written. Raw input rows and already-derived rows are untouched.

## Preserved Functional Contracts

- FAISS index existence, locking, reading, writing, IDs, hits, ranking,
  provenance, shadow scoring, and failure returns are unchanged.
- Exact query vectors, filters, `top_k`, and origin-owned retrieval context are
  unchanged.
- Retrieval-event policy, existing-database authority, locked/busy fallback,
  and lossless central serializers are unchanged.
- Rollup aggregation keys, hit and score math, state advancement, limits, and
  idempotency are unchanged.
- Qdrant collection fallback and missing-reference behavior are unchanged.
- The mounted route census remains 69 operations: 41 passive reads, 1 request
  staging, 10 automatic mutations, 8 curated mutations, and 9 process
  executions.
- The four intentional retrieval routes remain `automatic_mutation` because
  successful-hit telemetry remains enabled.

## Mutation-Sensitive Evidence

The committed authority suite collects 19 temporary-only tests. Against the
unchanged implementation it produced 12 selected privacy failures and 7
preserved-contract passes:

- the event still contained `index_path`;
- the AST guard found all seven path-bearing warnings and the event-detail key;
- all seven warning witnesses retained their existing return behavior while
  failing the logical-reference privacy assertion;
- Windows and POSIX legacy rows split from their safe modern rollup bucket; and
- the limited second batch advanced state but created the same unsafe split.

Independent review strengthened the oracle before implementation by requiring:

- distinct filenames for every warning producer and the event/rollup witnesses,
  preventing branch-local hardcoding;
- inspection of every captured log message, argument tuple, exception text, and
  traceback, preventing a second unsafe record from escaping;
- explicit global `store_ref` precedence, Qdrant fallback, non-dict details,
  and unknown-store behavior; and
- a bounded `--limit` first batch followed by exact stateful completion.

A separate opaque detail round-trip proves that central serializer redaction
cannot satisfy the suite.

Every witness used temporary paths and SQLite databases, fake FAISS modules,
captured emitters/logs, or in-memory values. No configured database, Qdrant
service, endpoint, model, cache, configured data root, ingestion, identity,
WSL distribution, public checkout, or mixed main checkout was exercised.

## Fresh Verification

The final gate used the explicit `goodq_core` interpreter and passed:

| Gate | Result |
|---|---:|
| Dedicated FAISS store-reference privacy authority | 19 passed |
| FAISS ID/lock plus retrieval context, SQLite, and persistence union | 122 passed |
| Route-effect plus completed query-log privacy union | 83 passed |
| Combined focused regression union | 205 passed |
| Independent implementation reviews | 2 CLEAN; no P1-P2 |
| Independent final oracle reviews | 2 CLEAN; no P1-P2 |

The combined union emitted three inherited warnings: two Pydantic configuration
deprecations and one pre-existing invalid escape warning in audited source.

Additional evidence:

- both changed Python files compiled;
- staged and working-tree diff checks passed;
- documentation authority, documentation drift, banned-token, and dependency
  drift gates passed; and
- the route-effect authority retained the exact 69-operation census.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- absolute `index_path` in new FAISS retrieval-event details;
- configured FAISS paths or raw exception text in the seven selected warnings;
- raw legacy FAISS paths in newly materialized daily `store_ref` rows;
- central `RetrievalEvent.to_row()` or `to_dict()` redaction; or
- historical cleanup as a substitute for producer and projection authority.

Separately recorded path-bearing ingestion/`MemoryCommitEvent` producers,
generic epistemic payload compatibility, analytics-question logging, and
derived-intent logging were not repaired here.

## Next Bounded Mission

Run a fresh read-only no-repeat reconciliation of the remaining recorded
candidates. Classify each against R-05-F1's actual completion gate and its real
producer, sink, consumer, retention, and rollback owner. Then either select one
small coherent seam or close R-05-F1 and route each remaining candidate to its
proper roadmap owner. Do not infer that all previously recorded privacy
candidates belong to this hidden-read item.
