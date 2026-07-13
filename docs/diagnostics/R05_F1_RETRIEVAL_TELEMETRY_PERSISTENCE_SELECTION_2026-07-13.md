<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Telemetry Persistence Selection

## Decision

Select retrieval-event persistence and configuration authority as the next
bounded seam. Do not combine request-context propagation or privacy redaction.

The four mounted retrieval routes intentionally emit successful-hit audit
events and therefore remain `automatic_mutation`. The repair must make that
effect explicit and deterministic: one canonical immutable policy, one exact
fallback destination, one propagation contract, and no creation of an absent
primary memory database.

This was a read-only code/configuration audit plus temporary-only failure
witnesses against the existing production modules. No production code or
canonical configuration changed. No configured database, endpoint, Qdrant
service, model, cache, ingestion path, identity surface, WSL distribution,
dependency, public checkout, or mixed main checkout changed or was exercised.

## Governing Invariant

Retrieval observability may mutate only through one explicit policy. Disabled
telemetry or fallback cannot write. Enabled SQLite telemetry may add its audit
schema and rows only to an existing primary database. Locked-database fallback
may append only to the exact configured log destination and may not silently
relocate beside the database. Retrieval results remain best effort and cannot
be suppressed by telemetry failure.

## No-Repeat Boundary

The following follow-up repairs are checkpointed closed and remain frozen:

- Qdrant query-side collection no-create authority;
- ingest-status constructor and lookup no-create authority;
- summary video-status lock-free projection;
- exact local-only text and CLIP model resolution;
- summary SQLite read authority; and
- retrieval FTS/KG/provenance/FAISS SQLite read authority.

The common SQLite read helper is not the telemetry writer. This seam governs
the explicit observability mutation and must not route event writes through the
read capability.

## Current Persistence Authority Is Split

`steps/common/retrieval_events.py` recognizes environment overrides plus two
raw-dictionary locations:

- `observability.retrieval_events`; and
- `memory.retrieval_events`.

Neither is canonical configuration authority today. `GoodQConfig` has no
`observability` field. `MemoryConfigSection` declares only `routing`, and its
nested model uses Pydantic's default extra-field behavior, so a supplied
`memory.retrieval_events` object is silently discarded from the validated
projection. The default configuration declares no retrieval-event policy.

Current Pydantic documentation confirms that models ignore extra input by
default and that each model requiring rejection must declare
`ConfigDict(extra="forbid")`; a parent model's policy is not a substitute for
an explicit nested-model contract:

- [Pydantic model configuration](https://docs.pydantic.dev/latest/concepts/models/#extra-data)
- [Pydantic validation error for forbidden extras](https://docs.pydantic.dev/latest/errors/validation_errors/#extra_forbidden)

Environment toggles are therefore the only current practical policy controls,
while the code advertises YAML controls that validation does not preserve.

## Every Production Emitter Drops Policy

The emitter accepts a complete `cfg` argument and uses it for enablement and
JSONL fallback decisions, but every production call omits it:

- Qdrant successful-hit emission;
- ephemeral-memory hit emission; and
- FAISS successful-hit emission.

The generic Qdrant and text-store builders separately reduce configuration to
an enabled boolean and log directory. `MultimodalSearchEngine` reduces it
further: its cached Qdrant client receives the enabled boolean but not the
configured log directory. This creates three authorities—raw config, a boolean,
and an optional path—while the sink reparses ambient defaults without the
original policy.

On SQLite lock/busy, `_fallback_log_dir()` prefers an existing explicit path,
then a config path, then silently falls back to the database parent. Because the
engine drops both config and log directory, its fallback lands beside the
database even when the caller attempted to disable JSONL or select a log root.

## Additional Persistence Defects In The Same Owner

The selection audit found two deeper persistence failures in the same module,
rollback boundary, and verification gate:

1. `sqlite3.connect(db_path)` creates an absent primary memory database before
   the event schema is installed. A nominal query can therefore mask missing
   primary-memory authority with a telemetry-only database.
2. schema initialization is cached only by pathname. After atomic replacement
   of the database at the same path, the cache skips initialization and the
   first event against the replacement is silently lost.

Most non-lock SQLite failures and JSONL append failures are silently swallowed.
The retrieval response must remain best effort, but audit loss must become
visible through bounded structured logging that contains no query text or
absolute path.

## Temporary Failure Witnesses

Temporary roots, fake Qdrant responses, and an instrumented locked connection
proved the current behavior:

```text
engine hits preserved: 1
engine Qdrant log_dir propagated: false
engine configured JSONL disable ignored: true
engine fallback used configured log root: false
ephemeral configured JSONL disable ignored: true
missing primary database created: true
event lost after same-path database replacement: true
```

The same witness showed that no configured/live service was required. All
artifacts were deleted with their temporary directories.

## Selected Authority Shape

### Canonical configuration

Add one `observability.retrieval_events` schema with exactly:

- `enabled`;
- `jsonl_fallback`; and
- the existing canonical `paths.log_dir` as its destination authority.

Both the new observability model and its nested retrieval-event policy must use
explicit `ConfigDict(extra="forbid", frozen=True)` contracts. Do not make the
whole legacy `MemoryConfigSection` strict: production consumers still read
undeclared `memory.*` fields, and changing their current validation/projection
behavior is outside this seam.

Use one targeted root/model validator to report `memory.retrieval_events` as a
competing policy key. The generic config loader currently falls back to raw
configuration after any validation error, so schema rejection alone is not a
fail-closed policy boundary: the resolved policy must also ignore
`memory.retrieval_events` unconditionally. Preserve exact environment-over-
config precedence for `GOODQ_RETRIEVAL_EVENTS` and
`GOODQ_RETRIEVAL_EVENTS_JSONL`. Add defaults matching the current
enabled/locked-fallback behavior. Do not change the generic validation-fallback
contract in this seam.

### Resolved policy

`steps/common/retrieval_events.py` should expose one frozen resolved policy
containing:

- event persistence enabled state;
- JSONL locked-fallback enabled state; and
- exact validated log destination, or an explicit unavailable state.

Resolve the policy once per builder/engine authority and pass that object
through Qdrant, ephemeral, and FAISS emitters. Do not pass or reparse arbitrary
full configuration at the sink.

### SQLite and fallback lifecycle

- Refuse an absent or non-file primary database without creating it.
- Preserve intentional schema/index creation inside an existing database.
- Make schema readiness replacement-aware rather than caching only a pathname.
- Preserve successful event-row semantics and the short best-effort timeout.
- Use JSONL only for locked/busy SQLite failures, matching current semantics.
- When JSONL is enabled, append only under the exact existing configured log
  directory; never create a directory or fall back to the database parent.
- When persistence or fallback cannot occur, preserve hits and emit a bounded
  path-free/query-free warning instead of failing silently.

## Deliberately Separate Follow-Ups

### Request-context authority

Qdrant, ephemeral, and FAISS read `GOODQ_RETRIEVAL_CONTEXT` at query time. The
repository has no setter, so normal events become `unknown`, while any ambient
value can mislabel concurrent requests. Fixing that requires origin-owned query
interfaces and an interleaving/concurrency gate across API, CLI, and shared
store callers. It does not share the persistence-policy rollback boundary.

### Privacy and detail redaction

Four search methods log raw query text at INFO. FAISS event details and related
error logs include an absolute index path even though the vault-token contract
forbids absolute paths in retrieval events and user-facing logs. These require
log/event redaction and canary gates. They do not require changing fallback
destination or schema readiness.

Independent traces agreed on the persistence defect but differed on whether to
bundle these later concerns. Applying the one-time-right authority rule selects
the narrower persistence/config seam because context and privacy have different
origin owners, rollback boundaries, and verification gates.

## Exact Implementation Boundary

Expected production/configuration scope:

- `steps/common/retrieval_events.py` — immutable resolved policy, existing-file
  event-store boundary, replacement-safe schema readiness, exact fallback, and
  visible failure reporting;
- `steps/common/qdrant_client.py` — policy carrier and generic builder;
- `steps/common/memory_stores.py` — ephemeral/FAISS policy carrier and shared
  builder;
- `retrieval/multimodal_search.py` — cached-engine Qdrant policy propagation;
- `scripts/config_schema.py` — strict/frozen observability models plus a
  targeted competing-key validator that does not globally tighten legacy
  memory configuration; and
- `configs/config.yaml` — generic defaults matching current enabled behavior.

Expected tests:

- add `tests/unit/test_retrieval_telemetry_persistence_authority.py`;
- extend Qdrant query authority and ephemeral truth only for caller continuity;
- extend configuration validation for accepted canonical policy, rejected
  competing/unknown keys, raw-fallback refusal of the competing policy,
  unchanged unrelated legacy `memory.*` behavior, and default parity; and
- retain the retrieval SQLite FAISS telemetry controls as frozen regressions.

Frozen outside this seam:

- request-context parameters and environment fallback;
- raw query and FAISS-path redaction;
- event table/row schema and retention;
- rollups, health projections, route responses, and route classifications;
- Qdrant query/no-create, FAISS scoring, provenance, model/cache, summary,
  status, identity, ingestion, and MiniAgent behavior;
- runtime dependencies, active environments, configured data, services, and
  public release state.

## Mutation-Sensitive RED

Tests must fail against the current implementation and prove:

1. a canonical config with `jsonl_fallback=false` survives engine, generic
   Qdrant, ephemeral, and FAISS construction; forced lock creates no JSONL;
2. enabled fallback writes only under the exact configured log directory and
   never beside the database;
3. environment overrides preserve documented precedence over canonical config;
4. canonical validation rejects unknown observability-policy keys and diagnoses
   the competing memory key, while unrelated legacy memory input retains its
   current behavior and raw-loader fallback cannot make the competing key
   authoritative;
5. disabled telemetry creates no SQLite, WAL, shared-memory, schema, row, or
   JSONL artifact;
6. enabled telemetry refuses to create an absent primary database;
7. an existing database may receive the stable event schema and event rows;
8. atomic same-path database replacement re-establishes schema readiness and
   preserves the next event;
9. locked/busy alone invokes JSONL; other failures preserve hits, create no
   fallback, and produce a sanitized structured warning;
10. a missing/invalid fallback directory is not created and does not cause
   database-parent relocation;
11. event and fallback failures never suppress or alter Qdrant, ephemeral, or
    FAISS hits; and
12. the 69-operation census remains 41 passive, 1 staging, 10 automatic, 8
    curated, and 9 process operations.

## Selection Verification

Before production implementation:

- two independent read-only traces reconciled all emitters, builders, config
  projections, fallback destinations, context sources, and privacy outputs;
- temporary-only witnesses reproduced policy loss, destination relocation,
  missing-database creation, and same-path replacement event loss;
- current Pydantic documentation confirmed nested models require their own
  explicit extra-field and immutability policy;
- the completed retrieval SQLite implementation and evidence checkpoints were
  clean before this selection began; and
- no production/configuration edit began before this evidence was recorded.

No route becomes passive when this seam closes. Context authority and privacy
redaction remain explicit later selections under the same roadmap item.
