<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Remaining-Candidate Reconciliation

## Decision

Close this item as verified. Fresh code, caller, sink, consumer, and route-effect
traces found no remaining hidden mutation in the mounted retrieval or
ingest-status paths. The four retrieval operations still write governed
retrieval telemetry intentionally and therefore remain `automatic_mutation`.
The ingest-status operation remains a passive read.

The separately recorded candidates are real, but they are output-redaction,
diagnostic-logging, retention, migration, or inactive compatibility concerns.
They do not share this item's hidden-read invariant, rollback boundary, or
verification oracle and must not keep this item open by association.

## Governing Invariant

A candidate belongs to this item only when a nominal mounted retrieval or
ingest-status read can create or modify directories, databases, SQLite
sidecars, schema, Qdrant collections, retrieval-event persistence, fallback
JSONL, or model/cache state without its declared effect accounting for that
mutation.

Privacy-sensitive output from an explicit ingestion write, a passive read
projection, a standalone operator CLI, or historical artifact retention is not
a hidden-read mutation. Those concerns remain actionable under their actual
roadmap owners.

## Completed Authorities Kept Closed

The reconciliation found no contradictory evidence against the focused
checkpoints for:

- Qdrant query no-create authority;
- ingest-status constructor and ledger no-create authority;
- summary status and summary SQLite read authority;
- local-only retrieval model/cache resolution;
- retrieval SQLite read authority;
- retrieval telemetry policy, persistence, and fallback authority;
- explicit origin-owned retrieval request context;
- raw retrieval-query log privacy; and
- FAISS logical store-reference privacy for new retrieval events, warnings, and
  future legacy-input rollup projection.

The current mounted census remains 69 operations: 41 passive reads, 1 request
staging operation, 10 automatic mutations, 8 curated mutations, and 9 process
executions. The four retrieval routes retain their intentional telemetry
effect; `GET /api/ingest/status/{request_id}` remains passive.

## Fresh Remaining-Candidate Trace

### Standalone analytics question and derived intent

`scripts/analytics_query.py` logs the complete operator question at INFO.
Its callers are standalone analytics CLIs; the mounted legacy analytics routes
are retired. `cli/nl_query.py` similarly logs an LLM-derived intent dictionary
that can contain personal entity or location terms, but its only caller is its
own standalone interactive entry point.

Neither module installs a handler or defines retention. Ordinary direct
execution suppresses the INFO records unless a parent process configures the
root logger; if enabled, the sink and retention are inherited. Neither producer
is mounted in the API or participates in retrieval-event telemetry.

Disposition: R-23 owns a later operator-query logging and retention census.
That census must prove whether canonical launch paths retain the records and
whether the utilities remain active before changing their producers. Stale
operator-CLI documentation, if found, belongs to R-13.

### Ingestion and MemoryCommitEvent references

Explicit ingestion/materialization producers preserve full internal references
in commit truth:

- `steps/text_embed/step.py` records FAISS and SQLite references plus
  `details.source_path`;
- `steps/common/memory.py` records summary-vector FAISS and SQLite references;
- `steps/audio_embed_clap/step.py` records FAISS, map-database, SQLite, and
  source references and persists `clap_meta.index_path`;
- `steps/video/scene_visual_embeddings.py` returns/logs CLIP and DINO index
  paths and records them in commit-event targets; and
- `steps/common/memory_commit_events.py` persists arbitrary target/detail JSON
  to authoritative SQLite and a default-on append-only JSONL mirror.

These producers run during intentional ingestion or materialization writes, not
nominal retrieval/status reads. Internal configured paths must remain available
for actual I/O and integrity checks, so central serializer redaction would be
the wrong repair boundary.

Disposition: R-23 owns the retention manifest, producer/privacy policy, and any
approved historical migration. R-15 owns bounded warning/error-message seams
that expose full local paths or exception text while preserving fallback
behavior. If a future repair changes the semantic meaning of
`MemoryCommitEvent.targets[*].ref` or scene artifact metadata, it must consult
the verified R-10 materialization contracts rather than silently redefining
commit truth.

### Read-model and mounted output compatibility

`steps/common/epistemic_formatter.py` is a pure formatter that can fall back
from a payload `index_path` to `store_ref` and returns payload/provenance
losslessly. It has no mounted production caller today; only unit smoke coverage
uses it. The architecture contract nevertheless defines `store_ref` as a
logical store identity and the payload as sanitized, so the fallback is a
future contract footgun rather than a current mutation.

Two mounted passive output boundaries are independently actionable:

- `/api/read/envelope` returns a precomputed envelope verbatim; and
- scene/timeline projections pass persisted `clap_meta` through unchanged,
  while the search projection already recursively replaces local paths and has
  a direct CLAP regression oracle.

Disposition: R-20 owns mounted API/UI output trust and local-path redaction
before any household gateway exposure. R-23 owns retained historical artifact
fields and any migration. Neither issue changes the operations' passive or
explicit effect truth.

The roadmap completion gates now bind those routed owners: R-20 cannot verify
without focused logical-reference/local-path output oracles, and R-23 cannot
verify until query-log sinks and retained path stores are classified with
explicit producer/reference, retention, and migration decisions.

## Completion-Gate Reconciliation

| Required witness | Current evidence |
|---|---|
| Qdrant reads do not create collections | Dedicated no-create checkpoint remains verified. |
| Status reads do not create ledger paths or records | Ingest-status checkpoint remains verified. |
| Summary and retrieval SQLite reads do not create databases, unauthorized sidecars, or DDL | Both SQLite authority checkpoints remain verified; explicit live-WAL policy is preserved. |
| Retrieval reads do not download or write model cache | Local-only model/cache checkpoint remains verified. |
| Retrieval telemetry writes are declared and bounded | Four routes remain `automatic_mutation`; policy, destination, fallback, and origin context are checkpointed. |
| Retrieval logs/events do not expose raw queries or FAISS paths | Producer-side query and FAISS logical-reference checkpoints remain verified. |
| A write-capable implementation fails the focused oracles | Existing RED-derived authority suites retain seeded temporary-only mutation witnesses. |

No remaining candidate contradicts those witnesses. Closing the item does not
claim that all repository logs, artifacts, API outputs, or historical records
are path-free.

## Fresh Verification

The explicit `goodq_core` interpreter passed a 347-test temporary-only union
covering Qdrant query no-create, ingest status, summary routes and SQLite reads,
retrieval model-cache and SQLite reads, telemetry persistence, request context,
query-log privacy, FAISS store-reference privacy, and the exact route-effect
census. The run emitted only the three inherited warnings already recorded by
the FAISS checkpoint: two Pydantic configuration deprecations and one invalid
escape deprecation in audited source.

Documentation authority, documentation drift, banned-token, dependency-drift,
and diff checks passed. The documentation drift gate found no active literal
drive-root or ghost-path violations. All regression witnesses used temporary
paths, temporary databases, fakes, captured logs, or in-memory values; no live
endpoint, configured data root, service, model, identity, ingestion, WSL,
public checkout, or mixed main checkout was exercised.

## Independent Read-Only Review

Three bounded independent traces reviewed separate candidate families:

1. standalone analytics-question and derived-intent producers/callers/sinks;
2. ingestion, scene metadata, and `MemoryCommitEvent` producers/consumers; and
3. generic epistemic compatibility plus mounted read-envelope and scene/timeline
   output boundaries.

All three concluded that no candidate blocks closure. Their ownership decisions
agree on R-20 for mounted output redaction and R-23 for retention/migration;
the ingestion trace additionally assigns unsafe diagnostic warnings to R-15.
No reviewer changed files or used configured data, endpoints, services, models,
identity, ingestion, WSL, the public checkout, or the mixed main checkout.

## No-Repeat Boundary

Do not reopen this item or repeat its ten completed authority/privacy seams
without contradictory focused evidence. In particular, do not:

- reclassify the four intentional retrieval telemetry routes as passive;
- redact arbitrary central serializers and thereby weaken internal evidence;
- clean or migrate historical artifacts as a substitute for producer/output
  policy; or
- bundle R-15, R-20, R-23, or R-13 work into a hidden-read repair.

The next ordered roadmap item is R-07. It begins with a read-only audit of the
existing clean-memory instructions and cleanup utilities; it does not authorize
deletion or configured-data access.
