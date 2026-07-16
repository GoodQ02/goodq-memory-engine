<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# R-05 Route-Effect and Client-Boundary Audit

## Question

After the verified ingest-staging convergence, what effects do the currently
mounted API operations actually have, and what common client boundary can deny
remote effects without misclassifying hidden writes as passive reads?

## Authority and No-Repeat Boundary

This audit was performed in the clean `codex/r05-api-authority` worktree at
`04724ac1`. It uses mounted code and transitive call traces rather than endpoint
names, HTTP verbs, old inventories, or intended UI copy.

The completed ingest-staging seam is not reopened. The superseded ingest token
and direct upload routes remain deleted. The frozen mixed checkout, live API,
current ingestion, memory stores, identity data, public checkout, listeners, and
firewall were not changed or exercised.

This seam also does not reopen the verified R-11 confirmation/audit authority,
the R-18-F1 synthetic-router harness repair, R-08 identity persistence, R-14
status probing, R-19 supervision, or R-20 listener/firewall/gateway work.

## Mounted Surface Census

Importing the application without calling a route and enumerating
`fastapi.routing.APIRoute` objects produced:

| Surface | Count |
|---|---:|
| Application route objects | 76 |
| `APIRoute` objects | 68 |
| Method plus route-template operations | 68 |
| OpenAPI operations | 66 |
| OpenAPI operations already carrying `x-goodq-effect` | 0 |
| Out-of-schema application operations (`/docs`, `/redoc`) | 2 |
| Non-`APIRoute` objects (`/openapi.json` plus static mounts) | 8 |

The prior clean inventory contained 70 operations. The reduction is exactly the
completed deletion of `GET /api/ingest/token` and
`POST /api/ingest/upload`; it is not a missing-router defect.

## Truthful Effect Model

Four classes are insufficient. Eleven routes named or presented as a query,
read, preview, or status operation can currently write through a transitive
dependency. Calling them passive would make the registry itself false.

| Effect class | Meaning at this checkpoint | Count |
|---|---|---:|
| `passive_read` | No proved persistent, process, model-provisioning, or remote-store mutation on the traced route path | 39 |
| `request_staging` | Creates or advances one governed ingest request without starting ingestion | 1 |
| `automatic_mutation` | The request automatically writes or may create state without an explicit curated-write action | 11 |
| `curated_mutation` | An explicit operator action intentionally changes durable application state | 8 |
| `process_execution` | Starts work or performs a deep probe that may start WSL, models, or subprocesses | 9 |
| **Total** |  | **68** |

`automatic_mutation` is a truth label, not permission to keep an accidental
write. Its hidden-write seams are assigned below for focused repair.

Classification is exclusive and uses this precedence:

1. `process_execution` for an explicit subprocess, background/generative job,
   or deep probe, even when that work also writes;
2. `request_staging` for the governed ingest-request lifecycle that does not
   meet the process rule;
3. `curated_mutation` for another explicit operator durable-state change that
   does not meet the process rule;
4. `automatic_mutation` for an incidental or hidden write on an otherwise
   query/read/preview action; and
5. `passive_read` only when none of the preceding rules applies.

This ordering prevents a lower-level write common to several implementations
from assigning more than one class to the mounted operation.

## Complete Operation Register

### Passive read — 39

| Method | Route template |
|---|---|
| GET | `/` |
| GET | `/api` |
| POST | `/api/search/temporal` |
| GET | `/api/videos/{video_id}/scenes` |
| GET | `/api/videos/{video_id}/scenes/{scene_id}` |
| GET | `/api/videos/{video_id}/timeline` |
| GET | `/api/videos/{video_id}/timeline/full` |
| GET | `/api/media/video/{video_id}/scene/{scene_id}/frame/{frame_index}` |
| GET | `/api/media/audio/{video_id}/{chunk_id}.wav` |
| GET | `/api/media/video/{video_id}/frame/{frame_name}` |
| GET | `/api/system/videos` |
| POST | `/api/system/ingest` |
| POST | `/api/system/reindex` |
| POST | `/api/system/reload` |
| GET | `/api/system/identity/mappings` |
| GET | `/api/summary/dashboard` |
| GET | `/api/summary/entity/{entity_id:path}` |
| GET | `/api/summary/collections` |
| GET | `/api/summary/capabilities` |
| GET | `/api/summary/video/{video_hash}` |
| GET | `/api/summary/video/{video_hash}/status` |
| GET | `/api/health/summary` |
| GET | `/api/engines` |
| GET | `/api/queue` |
| GET | `/api/storage/summary` |
| GET | `/api/models` |
| GET | `/api/runs/latest/preview` |
| GET | `/api/runs/latest/evidence` |
| GET | `/api/runs/audio-proof/latest` |
| GET | `/api/memory/stats` |
| GET | `/api/read/envelope` |
| GET | `/api/control-recurrence/reports` |
| GET | `/api/control-recurrence/reports/latest` |
| GET | `/api/control-recurrence/reports/trend` |
| GET | `/api/control-recurrence/reports/{report_id}` |
| GET | `/api/control-recurrence/reports/{report_id}/recommendations` |
| GET | `/api/control-recurrence/reports/{report_id}/markdown` |
| GET | `/docs` |
| GET | `/redoc` |

The three disabled system POST declarations return fail-closed responses and do
not perform their named mutation. Summary reads still use ordinary writable
SQLite connections; that is an adjacent purity risk to audit, not evidence of
executed DML in the traced functions.

### Request staging — 1

| Method | Route template |
|---|---|
| POST | `/api/ingest/submit` |

### Automatic mutation — 11

| Method | Route template | Proved transitive effect |
|---|---|---|
| POST | `/api/search/multimodal` | Qdrant collection creation if missing; retrieval-event SQLite or JSONL writes; model cache population may occur on first load |
| GET | `/api/search/text` | Same query-client and retrieval-event write path |
| GET | `/api/search/visual` | Same query-client and retrieval-event write path; first-load model cache may populate |
| GET | `/api/videos/{video_id}/scenes/{scene_id}/similar` | Same multimodal query-client and retrieval-event write path |
| GET | `/api/system/identity/unstitched` | After the route proves the database exists, `KnowledgeGraph` opens writable SQLite, enables WAL, can create sidecars, can run schema/index DDL, and commits |
| POST | `/api/system/identity/stitch/preview` | Same writable `KnowledgeGraph` constructor against the existing graph before preview queries |
| GET | `/api/ingest/status/{request_id}` | Ledger construction creates the requests directory before reading a record |
| GET | `/api/identity/face-clusters` | `_data_path()` creates the identity directory before reading |
| GET | `/api/identity/speaker-clusters` | `_data_path()` creates the identity directory before reading |
| GET | `/api/identity/name-mentions` | `_data_path()` creates the identity directory before reading |
| GET | `/api/identity/roster` | `_data_path()` creates the identity directory before reading |

The search trace is
`api/routes/search.py` or `api/routes/scenes.py` ->
`retrieval/multimodal_search.py` -> `steps/common/qdrant_client.py`.
`QdrantClient.query()` calls `ensure_collection()`, whose missing-collection
branch issues a PUT. Successful queries call
`steps/common/retrieval_events.py::emit_retrieval_events()`, which ensures a
SQLite schema and inserts rows, with an append-only JSONL fallback.

The system identity routes first require the graph database to exist, then enter
`lib/knowledge_graph.py::KnowledgeGraph`, whose constructor opens a normal
writable SQLite connection, enables WAL, can create sidecars, can execute
`CREATE TABLE IF NOT EXISTS` and index statements, and commits. The identity
route trace enters `api/routes/identity.py::_data_path()`, which unconditionally
calls `mkdir`. The ingest-status trace constructs
`api/utils/ingest_requests.py::IngestRequestLedger`, whose constructor also
unconditionally calls `mkdir`.

### Curated mutation — 8

| Method | Route template |
|---|---|
| POST | `/api/system/identity/stitch` |
| POST | `/api/system/identity/stitch/revoke` |
| POST | `/api/summary/collections` |
| DELETE | `/api/summary/collections/{collection_id}` |
| POST | `/api/identity/face-clusters/label` |
| POST | `/api/identity/speaker-clusters/confirm` |
| POST | `/api/identity/roster/save` |
| POST | `/api/identity/roster/export` |

### Process execution — 9

| Method | Route template | Owner note |
|---|---|---|
| POST | `/api/search/temporal/summarize` | R-05 process authority |
| POST | `/api/summary/video/{video_hash}/generate` | R-05 process authority |
| POST | `/api/identity/rebuild-face-clusters` | R-08 identity recovery |
| POST | `/api/identity/roster/validate` | R-08 identity recovery |
| GET | `/api/system/status` | R-14 passive-status repair |
| HEAD | `/api/status` | R-14 passive-status repair |
| GET | `/api/status` | R-14 passive-status repair |
| GET | `/api/gpu/stats` | R-14 passive-status repair |
| GET | `/api/wsl2-status` | R-14 passive-status repair |

The five status operations remain classified by their actual current effects
until R-14 proves that they are passive. An HTTP method does not determine an
effect class.

## Common Client-Boundary Design

The next R-05 implementation seam must:

1. define one exhaustive `(method, route template) -> effect` registry;
2. fail application startup if a mounted operation is missing, extra,
   duplicated, stale, or attached to an unexpected mount;
3. publish `x-goodq-effect` on all 66 OpenAPI operations;
4. use pure ASGI middleware and Starlette route matching, accepting the first
   `Match.FULL` result rather than treating `Match.PARTIAL` as the selected
   operation;
5. deny all four non-passive classes for a non-loopback client before reading a
   request body or invoking downstream code;
6. determine locality only from the raw ASGI `scope["client"]` address parsed by
   `ipaddress`, allowing IPv4 loopback, IPv6 loopback, and IPv4-mapped loopback;
7. treat a missing, malformed, hostname, unspecified, private-LAN, or public
   client address as non-local, denying only non-passive operations, and ignore
   Host, Origin, Referer, Forwarded, and X-Forwarded-* headers;
8. preserve framework-owned 404, 405, redirect, CORS preflight, OpenAPI, docs,
   ReDoc, and expected static behavior; and
9. call `uvicorn.run(..., proxy_headers=False)` so ambient
   `FORWARDED_ALLOW_IPS` cannot replace the raw peer address used by policy.

This boundary treats a non-loopback household LAN client as remote to the raw
API. That does not declare the operator-trusted LAN unsafe. It preserves the
separate R-20 decision that any household access is introduced deliberately
through a controlled gateway rather than by accidental raw-service binding.

After the common guard is proven, the route-local ingest loopback check becomes
a duplicate authority and should be removed in the same guarded seam. Exact
operation/scope confirmation remains an independent authorization layer and is
not replaced by client locality.

## Follow-Up Ownership

### R-05

- exhaustive effect registry, OpenAPI projection, startup reconciliation, and
  common remote-effect denial;
- removal of the duplicate route-local ingest client check after the common
  guard covers the route; and
- later common authority for explicit curated writes and process jobs.

### R-05-F1

- remove query-time Qdrant collection creation or make missing collections fail
  read-only;
- make retrieval-event persistence an explicit governed observability contract
  rather than a hidden side effect;
- require preseeded offline model resolution and prove retrieval cannot download
  or populate model caches before passive reclassification;
- make ingest-status lookup non-creating; and
- audit summary read connections for read-only URI use and sidecar creation.

### R-08

- make the two system identity reads/previews and four identity GETs
  non-creating and read-only;
- retain ownership of identity authority, atomicity, temporary-root testing,
  redaction, process identity, and stale-job recovery.

### R-14, R-19, and R-20

- R-14 makes status probes passive and accurate.
- R-19 owns the fixed-port supervisor, collision behavior, child ownership, and
  restart/backoff; this seam does not repair port fallback.
- R-20 owns listeners, firewall rules, LAN gateway design, rate limits,
  authentication, redaction, and retention; this seam changes no binding.

## Required Test Evidence Before Implementation Can Close

- an explicit independent expected map covers all 68 operations with counts
  `39/1/11/8/9`;
- seeded missing, extra, and misclassified entries fail with the named defect;
- adding an unclassified mounted route fails startup validation;
- every one of the 66 OpenAPI operations exposes `x-goodq-effect`;
- all 29 non-passive operations are denied to a remote ASGI client before body
  receive and downstream execution;
- remote passive GET and POST operations remain available;
- spoofed forwarding headers cannot bypass denial;
- a server-launch wiring oracle proves `proxy_headers=False` remains explicit
  even when `FORWARDED_ALLOW_IPS` is permissive;
- loopback IPv4, IPv6, and IPv4-mapped IPv6 are accepted;
- same-template GET/POST partial matching cannot select the GET classification
  for a POST request;
- parameterized routes, unknown paths, wrong methods, redirects, CORS preflight,
  docs, ReDoc, OpenAPI, and static mounts preserve framework behavior; and
- the five existing route-test fixtures that exercise effectful operations use
  explicit loopback clients rather than relying on a test-client default.

## Audit Safety

- No API endpoint was called.
- No request body, ingestion, identity, memory, Qdrant, model, process,
  listener, firewall, or data-root state was mutated.
- Only import-time application inventory and static call traces were used.
- The frozen mixed checkout and public checkout were not changed.

## Exact Resume Seam

1. Checkpoint this corrected audit, `PROJECT.md`, and `ROADMAP.md` after the
   documentation and generated-index gates pass.
2. Write the independent 68-operation expected map and seeded failure oracles.
3. Observe the registry, OpenAPI, and remote-boundary tests fail for the intended
   missing implementation.
4. Implement only the exhaustive registry, pure-ASGI client guard, OpenAPI
   projection, Uvicorn proxy-header boundary, and duplicate ingest-locality
   removal needed to make those tests pass.
5. Run focused route fixtures and independent specification/security review
   before creating the next private checkpoint.
