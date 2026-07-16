<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# R-05 Summary-Collection Authority Selection

## Outcome

The next bounded R-05 implementation seam is Summary Console collection create
and soft-delete:

- `POST /api/summary/collections`
- `DELETE /api/summary/collections/{collection_id}`

The two operations share one router, one JSON overlay, one browser surface, and
one intended store-owner replacement boundary. They can reuse the verified MiniAgent
confirmation/audit authority without introducing a model-result store or
crossing into identity persistence and recovery.

This was a read-only selection audit. No endpoint, model, job, service, data
store, configured data root, or runtime process was exercised.

## No-Repeat Boundary

The following completed work remains closed unless contradictory evidence is
found:

- the exhaustive route-effect registry and common loopback client boundary;
- governed ingest staging;
- the generic MiniAgent exact-scope token and external-outcome audit authority;
- the generic action-job ledger;
- video-summary authorization, job recovery, worker-input truth, and Summary
  Console polling.

The selected seam extends those authorities; it does not recreate them.

## Fresh Mounted Evidence

### Current route and UI truth

- Both routes remain correctly classified `curated_mutation` in
  `api/route_effects.py`.
- `api/routes/summary.py::create_collection()` calls
  `lib.summary_aggregator.add_collection()` immediately after ordinary request
  validation.
- `api/routes/summary.py::delete_collection()` calls
  `lib.summary_aggregator.soft_delete_collection()` immediately. The browser
  `confirm()` in `ui/summary_console/static/js/summary.js` is presentation, not
  server authority.
- Neither route uses MiniAgent exact-scope confirmation or the generic durable
  execution audit.
- Both routes currently return raw exception text through HTTP detail.

### Persistence truth

`saved_collections.json` is a separate operator overlay; the canonical Summary
Console contract prohibits these operations from changing SQLite core tables,
Qdrant, scene manifests, temporal indexes, ingestion outputs, or identity
state.

The current store does not yet satisfy its own atomicity claim:

- malformed JSON is converted to an empty store, so a later write can overwrite
  evidence instead of failing closed;
- create and delete perform unlocked load-modify-save cycles;
- every writer shares one fixed temporary filename;
- the writer does not explicitly flush or fsync and unlinks the authoritative
  file before rename;
- timestamp-plus-list-length collection IDs can collide under concurrent
  creates.

The repair must therefore treat strict load, validation, mutation, durable
replace, and post-write inspection as one store-owned boundary.

## Candidate Comparison

| Candidate | Shared authority and rollback boundary | Verification cost | Selection result |
|---|---|---:|---|
| Summary collection create + soft-delete | One JSON overlay, one router, one UI, synchronous file replacement | Medium-low | Selected |
| Temporal summarization | Requires confirmed model activation, durable result storage, exact-job retrieval, restart truth, and Retro Console migration | Medium-high | Defer |
| Identity curated/process actions | Cross multi-sink persistence, subprocess identity, crash recovery, and redaction owned by the identity repair | High and owner-coupled | Exclude |
| Nominal status executions | Must lose side effects under the passive-status repair rather than gain confirmation/jobs | Separate owner | Exclude |

Temporal summarization remains a valid later R-05 seam, but selecting it now
would require a new durable result/retrieval contract. Adding common authority to
identity routes before their atomic persistence and recovery owner is ready
would certify an unsafe write boundary rather than repair it.

## Selected Authority Boundary

### Shared rules

1. Register explicit authorization-only actions for collection create and
   collection soft-delete under the existing MiniAgent authority.
2. Bind confirmation to privacy-safe exact scope. Canonical digests may stand
   for operator text and scene-reference payloads; raw names, descriptions,
   transcripts, paths, and bearer tokens must not enter token or audit scope.
3. Perform no write before exact confirmation succeeds.
4. Record the observed mutation result through the existing
   `goodq.tool-audit.v1` external-outcome path. A pre-effect authority failure
   blocks the write; a post-effect audit failure preserves committed truth and
   exposes failed audit status.
5. Replace raw exception responses with stable sanitized outward errors.

### Store rules

1. One cross-process lock spans strict load, schema validation, mutation, and
   replacement.
2. Malformed or schema-invalid existing data fails closed without changing the
   authoritative bytes.
3. Write through a unique same-directory temporary file, flush and fsync it,
   then use atomic replacement. Failure preserves the previous authoritative
   bytes.
4. Collection IDs are collision-safe.
5. Soft-delete preserves the record and appends history; it never physically
   removes the collection.

### Durable action truth

Create is a synchronous curated write. Soft-delete is a destructive operator
action even though it is reversible at the overlay level, so it must use the
existing persistent action-job record in addition to exact confirmation. A
crash between durable replacement and terminal ledger update must be resolved
from exact collection-state evidence, never guessed or silently repeated. Each
confirmed mutation must therefore persist its immutable action/job correlation
identifier, or an equivalently unique marker, in the affected collection
history so restart reconciliation can prove whether that exact action committed.

## Exact Owner Files

- `agents/mini_agent_client.py`
- `api/routes/summary.py`
- `api/utils/action_jobs.py` only if a generic primitive is demonstrably
  missing; do not specialize the ledger for collections
- `api/utils/response_models.py`
- `lib/summary_aggregator.py`
- `ui/summary_console/static/js/summary.js`

Focused tests belong in:

- `tests/agents/test_mini_agent_client.py`
- `tests/agents/test_mini_agent_audit.py`
- `tests/unit/test_summary_routes.py`
- `tests/unit/test_summary_console.py`
- `tests/unit/test_summary_console_static.py`
- `tests/unit/test_api_route_effect_authority.py`

## Required Implementation Evidence

Before checkpointing, focused tests must prove:

- prepare is write-free and invalid/extra scope is rejected before token issue;
- missing, changed, wrong-operation, expired, and reused confirmations fail
  before the overlay write;
- raw request material, bearer tokens, paths, and exception details are absent
  from token, ledger, audit, response, and UI surfaces;
- malformed existing storage fails closed;
- create/create and create/delete concurrency loses no update and produces no ID
  collision;
- simulated flush, replace, and post-effect audit failures preserve truthful
  bytes and outward outcome state;
- soft-delete preserves the record and history and has deterministic crash
  reconciliation without silent retry;
- SQLite core tables and all excluded memory surfaces remain unchanged;
- the UI confirms before prepare, resubmits exact scope, clears raw token
  material, and shows success only from confirmed durable outcome;
- both operations remain `curated_mutation` and the common remote denial remains
  green.

Python compilation, JavaScript syntax, diff, secret-surface, portable-path, and
documentation gates remain required. Rendered browser verification stays with
the later integrated browser gate.

## Explicit Exclusions

This seam must not change:

- temporal summarization, model activation, or narrative result retention;
- video-summary jobs, routes, recovery, worker, or UI polling;
- identity routes, files, subprocesses, persistence, or recovery;
- runtime status, WSL, GPU, or passive-probe behavior;
- ingest staging, SQLite core data, Qdrant, manifests, source media, or active
  services.

An adjacent UI concern exists because stored collection text is rendered with
`innerHTML`. Record that for the later UI/security hardening owner; do not widen
this authority seam around it.
