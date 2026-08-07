<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_ROADMAP -->
<!-- DOC_LAST_VERIFIED: 2026-08-06 -->

# GoodQ4All Lifetime Roadmap and Repair Register

## Purpose

GoodQ4All exists to ingest private media into durable, explainable memory that
remains trustworthy across years of code evolution and future computers. This
roadmap tracks the work required to preserve that foundation. It does not
simplify GoodQ4All into a conventional stateless application.

The non-negotiable architecture remains local-first, Windows-canonical,
scene-centric, multimodal, persistent, auditable, and resilient. UCF remains
durable evidence. Validation and promotion remain explicit. SQLite, the
knowledge graph, Qdrant, manifests, and provenance remain truth surfaces.
Optional enrichments may degrade visibly but must not corrupt ingestion truth.

## Planning Authority

GoodQ4All uses one planning surface per purpose:

| Surface | Purpose | Lifecycle |
|---|---|---|
| docs/releases/ROADMAP.md | Global priorities, audit findings, dispositions, and completion gates | Persistent and updated in place |
| PROJECT.md | Current bounded implementation mission | Replaced when the active mission changes |
| PLAN.md | Rules for executable implementation plans | Persistent protocol |
| docs/superpowers/plans/ | Approved plan for active bounded work | Archive after completion |
| docs/agent/CURRENT_STATE.md and current_state.json | Verified runtime and handoff state | Updated from fresh evidence |
| Canonical subsystem contracts | Runtime behavior and invariants | Updated before dependent operational docs |

Completed, resolved, or invalidated plans must leave the active documentation
tree. Historical evidence belongs under docs/archive/ with a pointer back to
this roadmap or the current canonical contract.

## Repository and Release Authority

1. JoesDomingo/goodq4all is the private development authority. Its canonical
   product branch is dev.
2. GoodQ02/goodq4all is the downstream public release mirror. Its canonical
   product branch is main.
3. Every functional correction must exist in private development before public
   release. A correction discovered publicly is repaired in private first.
4. The public checkout has no independent preservation priority. A verified,
   sanitized private release may replace it.
5. gh-pages and temporary dependency-update branches are allowed
   infrastructure branches, not product-development authorities.
6. Public release is always second: private repair, private verification,
   sanitization, public update, independent public verification.

## Lifetime Portability Gate

Tracked active runtime and documentation surfaces must not depend on literal
drive roots, checkout locations, a Windows user profile, a hardcoded active
epoch, a workstation-only LAN address, a temporary directory, private identity
details, secrets, or tokens.

Paths resolve through configuration authority, environment abstractions,
platform helpers, or explicit operator input. Public examples are generic and
redacted. A repair is not complete if it works only on the present machine.

## Status Vocabulary

- OPEN: evidence confirms work remains.
- DECISION_REQUIRED: implementation waits on an architecture choice.
- IN_PROGRESS: an approved repair seam is active.
- VERIFIED: the completion gate has fresh, directly relevant evidence.
- DEFERRED: intentionally postponed with a reason and re-entry gate.

No item becomes VERIFIED because a plan exists, an unrelated suite passes, or
the failure is not currently visible.

## Repair Register

### R-01 — Align the promotion tool contract and implementation

- Priority: P0
- Status: VERIFIED
- Finding: the declared contract, native validation path, accepted scope, and
  returned result do not describe one interface.
- Repair: define and enforce one explicit schema; reject ambiguous scope.
- Completion gate: contract tests reject missing, extra, ambiguous, and
  mismatched scope; focused lifecycle tests pass through MiniAgentClient.
- Public impact: RELEASE_REQUIRED
- Evidence (2026-07-10): the contract and native implementation now require
  exactly non-empty `video_hash` and `epoch_id` values, reject aliases and
  extra fields before confirmation, bind confirmation tokens to the exact
  scope, and describe both blocked and completed results. Automatic scope
  inference and caller-supplied vector injection were removed. Fresh focused
  verification passed: 59 MiniAgent tests, 7 governance-validator tests, and
  19 UCF retrieval-bridge tests.

### R-02 — Replace the dated self-confirming promotion runner

- Priority: P0
- Status: VERIFIED
- Finding: the runner embeds a specific epoch and storage location, obtains its
  own confirmation token, and immediately consumes it.
- Repair: replace it with a portable inspect -> approve -> execute command and
  remove the old runner after replacement verification.
- Completion gate: a temporary epoch proves the separated workflow and
  fixed-root scanning finds no machine-specific path.
- Public impact: RELEASE_REQUIRED
- Checkpoint evidence (2026-07-11): commits `c0e9099f`, `3fc79f94`, and
  `5a9e9c7c` isolate the corrected contract, portable promotion delivery, and
  evidence record. A fresh temporary-agent-home run passed 129 tests. Compile,
  JSON, fixed-root, secret-prefix, retired-runner, and diff gates passed. The
  checkpoint excludes R-03 implementation.

### R-03 — Complete the UCF lifecycle transition audit trail

- Priority: P0
- Status: VERIFIED
- Finding: live promoted frames have validation transitions but no matching
  promotion transition record.
- Repair: log promotion in the same transactional boundary as status mutation.
- Completion gate: validation, promotion, rejection, and supersession each
  produce scoped transition evidence; rollback leaves no false transition.
- Public impact: RELEASE_REQUIRED
- Checkpoint evidence (2026-07-11): commits `b9ae79f4` and `45c741e1`
  isolate atomic exact-frame lifecycle transitions and their evidence record.
  The expanded lifecycle gate passed 114 tests and the R-02 non-regression gate
  passed 136 tests. The live July ledger was opened read-only and still contains
  one historical validation transition and no historical promotion row; no
  retroactive event was fabricated.

### R-04 — Sanitize tracked configuration without changing private runtime

- Priority: P0
- Status: VERIFIED
- Finding: tracked configuration contains private identity fields and dated
  machine-specific defaults inherited by the public release.
- Repair: preserve private values in ignored local authority and replace tracked
  values with generic portable defaults.
- Completion gate: a redacted pre/post comparison proves equivalent private
  runtime resolution; privacy and fixed-root scans pass; no-overlay startup
  resolves to a portable baseline.
- Public impact: SANITIZE
- Prior evidence (2026-07-10): moved the ten private operator-identity fields and
  eight machine-description fields into the existing ignored local overlay,
  then replaced tracked values with generic schema-valid defaults. Replaced 18
  dated epoch defaults with `GOODQ_EPOCH_ID` resolution, removed the remaining
  literal drive roots from tracked configuration and platform lookup helpers,
  and updated the existing local template and loading contract in place. Five
  redacted pre/post SHA-256 comparisons proved the complete private resolved
  config, identity, system description, migration scope, and runtime routing
  unchanged. The no-overlay baseline resolves the platform data root and
  generic `default` collections. Fresh verification passed 24 focused tests;
  all 17 tracked config files had zero private-value, dated-epoch, or drive-root
  hits; compile, JSON, documentation-drift, forbidden-token, and diff gates
  were reported as passing.
- Reopened evidence (2026-07-11): isolated checkpoint review found remaining
  tracked workstation/location descriptors and a private RFC1918 Home Assistant
  endpoint in `configs/config.yaml`. The focused tests did not detect those
  values, and the loading contract says they belong in ignored local authority.
  R-04 is not checkpoint-ready until those fields are genericized or moved,
  equivalent private runtime resolution is re-proved, and regression scans cover
  local network addresses and the remaining local-authority sections.
- Checkpoint evidence (2026-07-11): the reopened fields now use generic tracked
  defaults, the local template covers every displaced topology, voice, and
  household-service field, and regression tests reject RFC1918 literals and
  non-generic local authority. The redacted in-memory comparison proved the
  complete private runtime and all named authority sections unchanged. Fresh
  verification passed 25 focused tests plus Python, YAML, diff, portability,
  and independent seam-review gates. Private checkpoint: `84c1d22d`; evidence:
  `docs/diagnostics/R04_CONFIG_PORTABILITY_CHECKPOINT_2026-07-11.md`.

### R-05 — Define API and Command Center execution authority

- Priority: P0
- Status: VERIFIED
- Finding: doctrine calls the API and console read-only while the identity
  branch adds roster writes and background process launch.
- Repair: adopt the loopback-only local-operator API model; classify every
  mounted method/path operation as passive read, request staging, automatic
  mutation, curated mutation, or process execution;
  converge staging on one ledgered path; make curated writes atomic,
  scope-constrained, and audited; use one single-use scope-bound confirmation
  plus persistent job record for process/destructive actions; deny remote
  non-passive effects by default; remove duplicate upload/token/boolean/route
  authorities.
- Completion gate: API contract, routes, UI copy, and authority tests agree.
- Public impact: RELEASE_REQUIRED
- Decision evidence (2026-07-10): the live mounted surface has 78 operations.
  Effect-based tracing finds 54 passive/read-only operations, 4 request-staging
  operations, 10 curated mutations, and 10 process-executing operations. Four
  of the process-executing operations are nominally read-only status routes
  (`/api/status`, `/api/gpu/stats`, `/api/wsl2-status`, and
  `/api/system/status`); their passive-probe correction remains R-14 rather than
  being folded into this authority seam. The default
  API bind is loopback, but there is no common mutation/execution gate. Active
  identity routes directly rewrite cluster and roster artifacts; identity
  rebuild, roster validation, candidate generation, and video summarization run
  code; system reindex/reload remain disabled. `POST /api/ingest/upload` stages
  media without the request ledger, policy profile, or confirmation contract
  used by `/api/ingest/submit`. The Retro Console's Upload Pad calls that
  unledgered upload route, so it is also a control surface despite active docs
  calling it read-only. The Command Center itself is read-mostly but its
  candidate-generation button calls `/api/identity/run-phases`. Identity
  Workbench, Stitching Workbench, and Summary Console also invoke curated writes
  or background work, while active API/current-state docs still broadly describe
  operator surfaces as read-only. The 2026-07-10 Identity Workbench walkthrough
  confirms that its curated roster and cluster writes are intentional product
  behavior; it does not settle authority for the other control surfaces.
- Original authority trace (2026-07-10): two independent confirmation mechanisms
  existed. The ingest facade used a self-issued in-memory token that was neither
  operation/scope-bound nor durable. `MiniAgentClient` had a persistent token
  store and policy contracts, but only promotion tokens were scope-bound; its
  native bypass permitted `run_ingestion` and `file_delete` without the required
  confirmation, and native result envelopes lacked generic durable audit
  evidence. R-11 has now repaired the MiniAgent authority. The ingest mechanism
  remains superseded, and a third gate must not be layered beside them.
- Approved direction (2026-07-11): Retro Console, Command Center, Identity
  Workbench, Stitching Workbench, and Summary Console are explicit loopback-only
  local-operator control surfaces. Request staging converges on one ledgered
  path; curated writes are
  scope-constrained, atomic, and durably audited; destructive/process actions use
  one single-use scope-bound confirmation and persistent job record; and remote
  binding denies mutation by default. The superseded upload, token, boolean-confirm,
  and duplicate route authorities must be removed rather than retained as
  compatibility layers. R-08 remains responsible for durable identity process
  recovery after this authority choice. Verified R-11 MiniAgent authority is now
  the prerequisite common confirmation/audit foundation for this seam.
- Fresh audit evidence (2026-07-11): after the verified R-11 checkpoint, the
  clean R-05 worktree mounts 70 API operations: 49 passive, 4 staging, 8 curated
  mutations, and 9 process executions. The earlier 78-operation inventory is
  reconciled exactly by eight frozen R-08-only identity prototype routes; the
  coincidental clean `app.routes` count of 78 includes `/openapi.json` and seven
  static mounts and is not an operation count. MiniAgent now supplies the
  repaired persistent exact-scope authority, but the API still uses its
  superseded process-local ingest token and no common route-effect/client guard.
  Retro Console still calls the unledgered upload bypass and overstates staging
  as ingestion. The first bounded repair is therefore staging convergence;
  identity prototypes remain frozen under R-08 and status side effects remain
  R-14-owned. Evidence:
  `docs/diagnostics/R05_API_AUTHORITY_AUDIT_2026-07-11.md`.
- First-seam checkpoint evidence (2026-07-11): `b69803af` removed the duplicate
  token/upload authorities and converged local-path and multipart preparation,
  exact-scope confirmation/cancellation, durable request state, bounded private
  staging, recovery, and Retro Console truth on one loopback-only submit route.
  Fresh verification passed 167 focused tests plus compilation,
  documentation/configuration/static gates, and independent specification and
  security reviews. R-05 remains `IN_PROGRESS`; route-effect classification,
  common remote-mutation denial, and the other mutation/process authorities are
  not closed. Evidence:
  `docs/diagnostics/R05_INGEST_STAGING_CHECKPOINT_2026-07-11.md`.
- Post-staging route-effect audit evidence (2026-07-12): the mounted surface
  contains 68 method/path operations. Transitive-effect tracing classifies 39
  as passive reads, 1 as request staging, 11 as automatic mutations, 8 as
  curated mutations, and 9 as process executions. Sixty-six operations are
  OpenAPI-published; `/docs` and `/redoc` account for the other two.
  Separately, `/openapi.json` and seven static mounts produce 76 route objects.
  The prior 70-operation census is reconciled by removal of the ingest
  token/upload routes, reclassification of disabled `/api/system/ingest` as
  passive, and recognition of eleven nominal reads/previews that create or
  persist state. The route registry must preserve those current effects until
  their owning repair gates pass. Evidence:
  `docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_AUDIT_2026-07-12.md`.
- Route/client-boundary checkpoint evidence (2026-07-12): `31344a9f` adds the
  exhaustive five-class registry, 66-operation OpenAPI projection, fail-closed
  startup reconciliation, raw-peer loopback policy, common pre-body remote
  denial, explicit proxy-header boundary, and removal of the duplicate ingest
  locality guard. A final review found and TDD closed duplicate-mount and
  same-operation lifespan-replacement gaps. Fresh verification passed 184
  focused/adjacent tests, compilation, exact-scope and diff gates, plus clean
  independent re-review. R-05 remains `IN_PROGRESS`; the next bounded seam is a
  read-only audit of the eight curated mutations and nine process executions
  against the verified R-11 confirmation/audit authority. Evidence:
  `docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_CHECKPOINT_2026-07-12.md`.
- Mutation/execution authority audit evidence (2026-07-12): all eight curated
  mutations and nine process executions remain correctly effect-classified and
  remotely denied, but none uses the verified MiniAgent exact-scope authority.
  The identity and passive-status subsets remain with their existing owners.
  Within this explicit curated/process register, the smallest coherent next
  seam is video-summary generation because its process-local background marker
  loses failure/restart truth and Summary Console equates `idle` with success.
  Temporal summarization remains separate because it is synchronous and has a
  different result/recovery boundary.
  Evidence:
  `docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md`.
- Video-summary authority checkpoint evidence (2026-07-12): the selected
  process-execution seam now uses one exact-scope MiniAgent confirmation, a
  locked atomic durable job ledger, generic external execution audit,
  target-video worker/provenance truth, startup interruption/recovery, passive
  job status, and Summary Console durable-state polling. Failure-boundary and
  malformed-status review findings were closed before checkpointing. Fresh
  integrated verification passed 415 tests plus Python compilation, JavaScript
  syntax, diff, secret-surface, and route-effect gates. R-05 remains
  `IN_PROGRESS`; the next bounded mission is a fresh read-only selection among
  the remaining curated/process authorities, not automatic continuation into
  temporal summarization.
  Evidence:
  `docs/diagnostics/R05_VIDEO_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-12.md`.
- Next-seam selection evidence (2026-07-12): fresh mounted-code comparison chose
  Summary Console collection create plus soft-delete. The pair shares one JSON
  overlay, router, UI, and intended store-owner replacement boundary; it can reuse verified
  exact-scope and audit primitives without the temporal-summary result-job
  migration or identity persistence/recovery coupling. The repair must fail
  closed on malformed storage, serialize the full load-modify-replace boundary,
  preserve authoritative bytes on failure, and use persistent action truth for
  destructive soft-delete, including an immutable overlay correlation marker
  for exact crash reconciliation. No runtime or data action was invoked. R-05 remains
  `IN_PROGRESS`.
  Evidence:
  `docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_SELECTION_2026-07-12.md`.
- Summary-collection authority checkpoint evidence (2026-07-13): the selected
  overlay seam now uses strict locked atomic persistence, collision-safe IDs,
  exact-scope MiniAgent create/delete confirmation, generic external outcome
  audit, immutable create/job correlation evidence, persistent soft-delete job
  truth, deterministic startup reconciliation, and Summary Console
  prepare/confirm flows with terminal-only success. Independent review findings
  for correlation rebinding, source-epoch authority, reconciliation request-ID
  equality, token retention, finalization-pending scope, and post-replace
  inspection/rollback were closed before checkpointing. Fresh isolated
  verification passed 505 tests plus Python
  compilation, JavaScript syntax, documentation, diff, secret-surface,
  portable-path, and route-effect gates. R-05 remains `IN_PROGRESS`; the next
  bounded mission is a fresh read-only selection among the remaining mounted
  curated/process authorities, not automatic continuation into temporal
  summarization. Evidence:
  `docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Temporal-summary selection evidence (2026-07-13): fresh mounted-code
  comparison found the six remaining curated mutations and two identity
  subprocesses are R-08-owned, while the five nominal status executions are
  R-14-owned. Temporal summarization is therefore the only currently eligible
  R-05 process seam. It requires exact request and execution-policy authority,
  a private atomic exact-job result store, result-before-terminal recovery,
  passive job/result retrieval, and Retro Console confirmation/polling. The
  result remains private with its job until R-23 defines retention; inference
  is never silently rerun or treated as rollback-capable. No endpoint, model,
  process, service, configured data root, or operator data was exercised. R-05
  remains `IN_PROGRESS`.
  Evidence:
  `docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_SELECTION_2026-07-13.md`.
- Temporal-summary authority checkpoint evidence (2026-07-13): the final
  directly owned R-05 process seam now uses one exact nine-field request,
  exact-scope MiniAgent confirmation, one verified epoch/model-policy snapshot,
  explicit activation and environment-proxy policy, a private locked atomic
  exact-job result receipt, result-before-terminal recovery, passive exact-job
  projection, and Retro Console durable polling. Fresh verification passed the
  full 798-test inherited R-05 regression union plus Python compilation,
  JavaScript syntax, route census, documentation, diff, secret-surface, and
  portable-path gates. The mounted surface is now 69 operations: 40 passive,
  1 staging, 11 automatic mutation, 8 curated mutation, and 9 process
  execution; 67 are OpenAPI-published. This verifies directly owned
  local-operator authority without claiming the separately owned hidden-read,
  identity, status, browser, or retention work complete. Evidence:
  `docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-13.md`.

### R-05-F1 — Remove hidden mutation from nominal retrieval and ingest-status reads

- Priority: P0
- Status: VERIFIED
- Finding: four retrieval operations intentionally persist retrieval events and
  therefore remain automatic mutations. Their incidental query-side Qdrant
  creation, model-cache resolution, write-capable SQLite projections, and the
  ingest-status constructor mutation are checkpointed closed. Summary SQLite
  projection authority is also checkpointed closed.
- Repair: separate read-only retrieval/status inspection from collection,
  retrieval-event, model-provisioning, and ledger initialization; make every
  intentional write an explicit governed effect; require preseeded offline model
  resolution for read-only retrieval; and audit summary projections with
  read-only connections or equivalent no-write evidence.
- Completion gate: seeded temporary-root and immutable-store witnesses prove
  that nominal reads cannot create directories, SQLite databases, unauthorized
  sidecars, DDL, Qdrant collections, retrieval-event rows, fallback JSONL
  output, or model downloads/cache writes. Required SQLite WAL coordination
  sidecars are permitted only under an explicit live-WAL truth policy. A seeded
  write-capable implementation must make the oracle fail. Any operation that
  retains an intentional write remains `automatic_mutation` and governed as
  such.
- Public impact: RELEASE_REQUIRED
- Boundary: this follow-up does not reopen governed ingest staging, the common
  R-05 route/client guard, R-08 identity recovery, or R-14 status probing.
- First-seam selection evidence (2026-07-13): independent read-only traces of
  retrieval, ingest-status, and summary projections selected Qdrant query
  no-create authority as the first repair. `QdrantClient.query()` currently
  turns a missing-collection GET into a collection-creating PUT on both initial
  and retry paths. The repair is limited to the shared query transport;
  explicit write paths retain creation authority. The four retrieval routes
  remain `automatic_mutation` while telemetry, model/cache, and SQLite effects
  remain open. Evidence:
  `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`.
- Qdrant query authority checkpoint evidence (2026-07-13):
  `QdrantClient.query()` now performs GET-only collection inspection on both
  initial and retry paths. A definite missing collection fails read-only;
  indeterminate inspection receives one bounded GET-only retry. Explicit
  `ensure_collection()`/`upsert()` creation remains unchanged. Fresh verification
  passed 283 adjacent tests, Python compilation, diff checks, and independent
  re-review. The four retrieval routes remain `automatic_mutation` because
  telemetry, model/cache, and SQLite effects remain open. The next bounded seam
  is the already-audited ingest-status constructor no-create repair. Evidence:
  `docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Ingest-status authority checkpoint evidence (2026-07-13): ledger construction
  is now assignment-only. Valid-missing and invalid status requests leave an
  absent tree absent; an existing request plus Watchdog projection leaves paths,
  bytes, sizes, and modification times unchanged. Explicit `create_record()`
  and cold-start prepare/confirm controls preserve governed storage creation.
  Fresh verification passed 112 focused regressions, Python compilation, diff
  checks, and independent review with no findings. Only the status GET changed
  to `passive_read`; the 69-operation census is now 41 passive, 1 staging, 10
  automatic mutation, 8 curated mutation, and 9 process execution. R-05-F1
  remains `IN_PROGRESS`; the next bounded mission is a fresh read-only selection
  among the remaining summary and retrieval effects. Evidence:
  `docs/diagnostics/R05_F1_INGEST_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Remaining-effect selection evidence (2026-07-13): fresh code traces and
  temporary-root witnesses selected the summary video-status passive reader as
  the next exact seam. Its ordinary latest-job projection enters the
  writer-oriented action-job lock and creates `.action-jobs.lock` transiently;
  a final-tree snapshot therefore misses the mutation. Retrieval telemetry is
  intentional durable observability, text/visual local-only resolution spans a
  write-logging provisioner, and summary/retrieval SQLite repair needs an
  explicit live-WAL policy, so those owners remain separate. The next repair is
  limited to a non-creating, lock-free action-job reader plus the one summary
  status route; writer lifecycle behavior and the route census remain frozen.
  Evidence:
  `docs/diagnostics/R05_F1_REMAINING_HIDDEN_READ_SELECTION_2026-07-13.md`.
- First-RED scope correction (2026-07-13): a Windows concurrency witness proved
  that a lock-free Python reader can make the current action-job `os.replace()`
  writer fail with `PermissionError`. A share-delete read handle alone did not
  cure that replacement failure, while a bounded `ReplaceFileW` control did.
  The selected status seam remains correct, but its coherent rollback boundary
  now includes an opt-in action-job atomic replacement helper. Generic atomic
  writes, action-job state transitions, and unrelated callers remain frozen;
  the concurrency oracle must not be weakened to preserve the narrower plan.
- Summary-status authority checkpoint evidence (2026-07-13): exact and latest
  video-summary status now use a non-creating reader that never constructs or
  acquires the writer lock. Action-job writers retain the existing lifecycle
  lock and use an action-job-only Windows replacement helper compatible with
  share-delete readers; generic atomic writes remain unchanged. Fresh
  verification passed 103 action-job tests, 128 summary-route tests, 119
  regression tests, ten repetitions of both concurrency witnesses, compilation,
  the unchanged 69-operation census, diff checks, and independent review with
  no actionable findings. R-05-F1 remains `IN_PROGRESS`; the next bounded
  mission is a fresh read-only selection among the remaining retrieval and
  summary SQLite effects. Evidence:
  `docs/diagnostics/R05_F1_SUMMARY_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Model-cache selection evidence (2026-07-13): fresh fake-loader and temporary
  witnesses selected text/visual local-only cache resolution as the next exact
  seam. Current text and CLIP retrieval pass remote identifiers without pinned
  local paths or local-only flags; registry revisions and an existing CLAP
  pattern supply the target contract. Existing offline provisioning is not a
  passive substitute because cached hits and misses write the download log.
  Telemetry remains an intentional policy seam, while summary/retrieval SQLite
  requires a separate live-WAL contract. The implementation boundary is one
  pure exact-snapshot inspector plus the two retrieval loaders and focused
  tests. Routes remain `automatic_mutation`; dependencies and all other effects
  stay frozen. Evidence:
  `docs/diagnostics/R05_F1_MODEL_CACHE_SELECTION_2026-07-13.md`.
- Model-cache authority checkpoint evidence (2026-07-13): text and CLIP query
  encoders now resolve only exact registry-pinned local snapshots before model
  libraries are imported. Missing, incomplete, unpinned, and redirected
  snapshot directories degrade without loader calls or cache creation. An
  independent P1 review found and closed a junction/symlink redirect bypass
  before checkpoint. Fresh verification passed 165 tests with 8 inherited
  skips, preserved the unchanged 69-operation route census and frozen
  provisioner/registry/dependency surfaces, and received a clean independent
  re-review. R-05-F1 remains `IN_PROGRESS`; the next bounded seam is summary-only
  SQLite read authority using the already-proven live-WAL contract. Retrieval
  SQLite and telemetry remain separate. Evidence:
  `docs/diagnostics/R05_F1_MODEL_CACHE_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Summary SQLite authority checkpoint evidence (2026-07-13): the dashboard,
  entity-profile, persisted video-summary, and knowledge-graph fallback readers
  now share one existing-file URI read primitive with `mode=ro`, verified
  `query_only`, and a SQLite authorizer. Independent review found and closed a
  P1 capability gap where `ATTACH`, `VACUUM INTO`, and query-only downgrade
  escaped the initial read-only policy. Fresh verification passed the focused
  authority witnesses and a 372-test adjacent union, preserved committed WAL
  visibility and the unchanged 69-operation route census, and received a clean
  independent rereview. R-05-F1 remains `IN_PROGRESS`; the next bounded mission
  is a fresh selection between retrieval SQLite and intentional retrieval
  telemetry. Evidence:
  `docs/diagnostics/R05_F1_SUMMARY_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Retrieval SQLite selection evidence (2026-07-13): fresh independent route and
  effect traces selected the four existing-file retrieval projections before
  intentional telemetry. FTS, KG scoring, shared Qdrant/FAISS hit provenance,
  and FAISS quantization shadow scoring retain ordinary write-capable SQLite
  handles despite read-only intent. The repair will promote
  the proven summary capability into one neutral common existing-file,
  live-WAL-aware, operation-authorized reader while preserving the completed
  summary API as a compatibility wrapper. Telemetry remains enabled,
  best-effort, durable observability and keeps all four retrieval routes
  `automatic_mutation`. Its later policy checkpoint must address dropped log
  destination/JSONL policy, process-global context, raw-query INFO logging, and
  absolute FAISS path detail without deleting the audit effect. R-05-F1 remains
  `IN_PROGRESS`; the next bounded mission is the mutation-sensitive retrieval
  SQLite implementation. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_SELECTION_2026-07-13.md`.
- Retrieval SQLite authority checkpoint evidence (2026-07-13): FTS/LIKE, KG
  scoring, shared Qdrant/FAISS provenance, and FAISS shadow scoring now share
  one existing-file `mode=ro`, verified-query-only, operation-authorized
  connection capability. The completed summary API delegates through the same
  primitive while retaining its unavailable-path, timeout, thread, and caller
  failure boundaries. Independent review found and closed one
  missing connect-contract oracle, then returned clean; a separate adversarial
  review found no actionable capability defect. Fresh verification passed 24
  focused tests and a 448-test adjacent union, compiled all changed Python,
  preserved live-WAL and FTS5 reads, and retained the 69-operation route census.
  R-05-F1 remains `IN_PROGRESS`; intentional retrieval telemetry is the next
  read-only selection, and the four retrieval routes remain
  `automatic_mutation`. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Retrieval telemetry persistence selection evidence (2026-07-13): fresh
  independent traces and temporary-only witnesses selected one canonical
  immutable event policy before request-context or privacy work. Every
  production emitter currently drops full configuration; the engine also drops
  the log destination, so configured JSONL disable is ignored and fallback can
  relocate beside the database. Canonical validation exposes no retained YAML
  policy. The same owner creates an absent primary database and loses the first
  event after same-path replacement because schema readiness is cached only by
  pathname. The repair is limited to canonical schema/defaults, exact policy
  propagation, existing-database-only event writes, replacement-safe schema
  readiness, exact locked/busy fallback destination, and sanitized failure
  visibility. Context authority and raw-query/FAISS-path redaction remain
  separate later selections. A final caller census also found that the
  read-only observability-health sample disables telemetry only after client
  construction; implementation must inject an explicit disabled policy there
  so resolve-once semantics cannot turn the health probe into an event writer.
  R-05-F1 remains `IN_PROGRESS`; the next bounded mission is mutation-sensitive
  persistence/config implementation. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_SELECTION_2026-07-13.md`.
- Retrieval telemetry persistence authority checkpoint evidence (2026-07-13):
  one frozen canonical policy now reaches Qdrant, ephemeral-memory, and FAISS
  emitters. Event writes require an existing primary database; schema readiness
  survives same-path replacement; JSONL is limited to exact SQLite locked/busy
  failure under the exact existing configured log destination; and failure
  visibility contains no query text or absolute path. Independent adversarial
  review found and closed a broad lock-substring classifier before returning
  clean. Fresh verification passed 33 focused tests and 193 adjacent tests with
  8 inherited live-runtime skips, preserved the 69-operation route
  census, and left all four retrieval routes as `automatic_mutation`. R-05-F1
  remains `IN_PROGRESS`; the next bounded mission is a fresh read-only selection
  between request-context authority and privacy/detail redaction. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_CHECKPOINT_2026-07-13.md`.
- Retrieval request-context selection evidence (2026-07-13): two independent
  read-only traces selected origin-owned context propagation before privacy
  redaction. Qdrant, ephemeral-memory, and FAISS read one process-global
  `GOODQ_RETRIEVAL_CONTEXT` value at query time, while the repository has no
  production setter. A deterministic in-process witness proved one interleaved
  request can misattribute another on a shared store. The repair is limited to
  required keyword-only context through API, MiniAgent, CLI, engine, router,
  store, and Qdrant query interfaces plus removal of the ambient template
  control. Raw query INFO logs and FAISS path-bearing details remain a separate
  producer-side privacy seam. R-05-F1 remains `IN_PROGRESS`; the next bounded
  mission is
  mutation-sensitive request-context RED and implementation. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_SELECTION_2026-07-13.md`.
- Retrieval request-context authority checkpoint evidence (2026-07-13): all
  twelve selected query interfaces now require origin-owned keyword-only
  context, all 22 production calls supply or forward the exact label, and API
  clients cannot choose their own retrieval origin. Qdrant, ephemeral-memory,
  and FAISS normalize only the explicit argument; the ambient environment
  control and production reads are gone. A deterministic overlapping-call
  oracle proves one shared store preserves distinct contexts. Fresh verification
  passed 253 tests with 8 inherited live-runtime skips plus 8 MiniAgent dispatch
  tests, compilation, documentation/static gates, and three clean independent
  reviews. The 69-operation route census is unchanged and all four retrieval
  routes remain `automatic_mutation`. R-05-F1 remains `IN_PROGRESS`; the next
  bounded mission is a fresh producer-side privacy/detail selection. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_CHECKPOINT_2026-07-13.md`.
- Retrieval query-log privacy selection evidence (2026-07-13): temporary-only
  witnesses proved the exact query enters four application INFO records and the
  text/visual GET endpoints' Uvicorn access targets. A similar-scene query can
  include persisted transcript and scene-summary material, and one multimodal
  request can repeat it up to four times. The selected repair owns only these
  shared-log producers in `retrieval/multimodal_search.py` and `api/server.py`;
  it preserves the functional query, responses, access logging, telemetry,
  route effects, and existing secret redaction. FAISS absolute-path event/log
  propagation remains the next independent privacy boundary. The same census
  recorded separate analytics-question and derived-intent logging candidates
  for later evidence rather than silently bundling them. R-05-F1 remains
  `IN_PROGRESS`; the next mission is mutation-sensitive raw-query privacy RED.
  Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_QUERY_LOG_PRIVACY_SELECTION_2026-07-13.md`.
- Retrieval query-log privacy checkpoint evidence (2026-07-13): the four
  selected engine records now retain only allowlisted operation, `top_k`, and
  modality evidence, while the Uvicorn record filter redacts every `q` value
  without changing ASGI request data or disabling access logs. Exact encoder,
  FTS, and nested-modality query propagation is preserved, as are all six
  existing secret-key redactions. Fresh verification passed 9 dedicated tests,
  a 196-test focused union with 8 inherited live-runtime skips, compilation,
  documentation/static gates, and two clean independent reviews. The
  69-operation route census and all four retrieval `automatic_mutation`
  classifications are unchanged. R-05-F1 remains `IN_PROGRESS`; the next
  bounded mission is a fresh FAISS absolute-path privacy selection. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_QUERY_LOG_PRIVACY_CHECKPOINT_2026-07-13.md`.
- Retrieval FAISS store-reference privacy selection evidence (2026-07-13): a
  temporary producer witness proved the absolute configured index path reaches
  new FAISS retrieval-event details plus explicit and exception-carried warning
  output. Static source tracing identified seven affected warning branches; the
  selected RED suite will execute each branch dynamically. A temporary SQLite
  witness proved the legacy rollup fallback newly materializes the same path in
  `retrieval_events_daily.store_ref`. The selected contract spans these new
  retrieval-reference outputs while preserving safe basename `store_ref`,
  lossless central serialization, FAISS behavior, rollup math/state, and route
  effects. Historical cleanup, already-derived-row migration, and the separately
  discovered ingestion/MemoryCommitEvent path producers remain outside. R-05-F1
  remains `IN_PROGRESS`; the next mission is mutation-sensitive FAISS
  store-reference privacy RED. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_FAISS_STORE_REF_PRIVACY_SELECTION_2026-07-13.md`.
- Retrieval FAISS store-reference privacy checkpoint evidence (2026-07-13):
  new FAISS events and seven selected warnings now expose only the logical index
  filename, and the legacy-input rollup fallback normalizes Windows/POSIX paths
  before creating future daily `store_ref` rows. Internal FAISS I/O, lossless
  event serializers, raw history, aggregation math/state/limits, Qdrant
  precedence, and the 69-operation route census remain unchanged. Fresh
  verification passed the 19-test authority suite, a 205-test focused union,
  static/documentation gates, and two clean independent implementation reviews.
  A final read-only no-repeat reconciliation then traced every separately
  recorded candidate against its current producer, caller, sink, consumer,
  retention, and rollback owner. None is a nominal retrieval/status hidden
  mutation: mounted output redaction belongs to R-20, durable query/path
  retention and migration belong to R-23, and unsafe diagnostic warning text
  belongs to R-15. Three independent candidate-family reviews agreed that this
  item's completion gate is satisfied without further implementation. Fresh
  closure verification passed a 347-test temporary-only authority union plus
  documentation, drift, banned-token, dependency, and diff gates. Evidence:
  `docs/diagnostics/R05_F1_RETRIEVAL_FAISS_STORE_REF_PRIVACY_CHECKPOINT_2026-07-13.md`.
  Closure evidence:
  `docs/diagnostics/R05_F1_REMAINING_CANDIDATE_RECONCILIATION_2026-07-13.md`.

### R-06 — Make isolated-ingestion checkpoints truthful

- Priority: P0
- Status: VERIFIED
- Finding: checkpoints may report database and graph commits when isolation
  deliberately suppresses those writes.
- Repair: record committed, not_applicable, or failed per persistence target.
- Completion gate: isolation and resume tests prove checkpoint values match
  actual SQLite, graph, vector, manifest, and temporal-index state.
- Public impact: RELEASE_REQUIRED
- Evidence (2026-07-10): replaced the last-window boolean checkpoint with one
  schema-v2 per-window map and exact `committed`, `not_applicable`, or `failed`
  status for all five persistence targets. SQLite and graph use read-only scene
  probes; vector truth comes from persisted Phase 6/Qdrant manifest evidence;
  manifest and temporal-index probes require the window scene IDs. Resume
  re-probes current persistence, rejects stale or legacy records, retries failed
  windows even when later windows committed, and restores timeline order.
  Isolated resume reads the manifest without opening or creating `memory.db`.
  Fresh verification passed 41 tests with 1 intentional skip, Python compile,
  JSON parsing, documentation drift, forbidden-token, fixed-root, legacy-flag,
  and diff checks.
- Reopened evidence (2026-07-11): isolated extraction review found that final
  cleanup deletes the schema-v2 checkpoint whenever scene Qdrant status makes
  `phase6_complete` true, even if memory DB, knowledge graph, scene-manifest,
  or temporal-index evidence recorded a failed target. R-06 remains open until
  cleanup requires every current window to have an exact five-target committed
  record and a regression proves a Qdrant-complete run retains the checkpoint
  when any other target failed.
- Checkpoint evidence (2026-07-11): final cleanup now requires Phase 6
  completion plus equality between every current window and the freshly
  re-probed exact five-target committed set. A Qdrant-complete video with any
  failed target retains its checkpoint. Fresh verification passed 42 hermetic
  tests, 29 expanded persistence tests, compile, diff, banned-token,
  fixed-root, legacy-flag, and two independent review gates. Private checkpoint:
  `ffc2b841`; evidence:
  `docs/diagnostics/R06_PROGRESSIVE_CHECKPOINT_EVIDENCE_2026-07-11.md`.

### R-07 — Replace the unsafe clean-memory workflow

- Priority: P0
- Status: IN_PROGRESS
- Finding: the runbook mixes incompatible shell syntax, dated locations, broad
  deletion, unaudited process stopping, non-binding manifests, and
  continue-after-failure behavior; the two operator-skill copies disagree, the
  active guide delegates to the unsafe procedure, and the evidence-first
  workflow can independently reauthorize prefix-wide collection deletion.
- Repair: replace manual deletion blocks with one portable, manifest-first,
  dry-run-capable, exact-scope, stop-on-failure CLI backed by a pure core; reuse
  the verified MiniAgent exact-scope authorization and `ActionJobLedger` rather
  than creating a third gate; retire the competing clean-slate executors and
  replace old instructions.
- Completion gate: temporary-root tests prove boundary rejection, idempotency,
  production R-23 verifier default denial, disposition/rollback coverage,
  stable concurrent plan/job convergence, pre-apply and immediate per-target
  drift/reparse refusal, passive quiescence-authority default denial, token/job
  authority, one-lock expected-owner/expected-state transitions, bounded token
  expiry and approval-crash recovery, live-apply/reconcile lease exclusion,
  stop-on-first-failure, crash-safe per-target journaling/reconciliation,
  bounded protected-target evidence, and
  plan-bound post-clean receipts; the active workflow, guide,
  evidence-first workflow, both repository operator-skill copies, and their
  discovered active references and generated indexes agree on the verified
  tool and contain no manual, competing, legacy-executor, prefix-wide, or
  active-to-archive destructive procedure. Configured-data apply remains fail-closed until an
  R-23-governed disposition/rollback artifact authorizes the exact epoch and a
  canonical supervisor supplies an exclusive lease honored by every writer.
- Selection evidence (2026-07-13): three independent read-only traces found no
  reusable safe cleanup executor and selected `cli.clean_memory` plus a pure
  `steps/common/clean_memory.py` core. Operator input names one exact configured
  epoch; configuration derives the exact database, sidecar, FAISS, and four
  collection targets; immutable plan and receipt evidence bind the existing
  R-05/R-11 authorization and action-job authorities. Process stopping,
  initialization, re-ingestion, broad retention cleanup, API/UI work, and live
  configured-data verification remain outside the seam. Evidence:
  `docs/diagnostics/R07_CLEAN_MEMORY_REPLACEMENT_SELECTION_2026-07-13.md`.
- Approval-authority foundation checkpoint (2026-07-13): private checkpoint
  `248bbd33` adds complete atomic initial metadata and one-lock
  expected-owner/expected-state transitions to the shared action-job authority,
  then registers `clean_memory.apply` as authorization-only MiniAgent work with
  the exact six-field scope, request-ID/absolute-deadline binding, no native
  executor, and bounded logical audit target. The isolated authority union
  passed 375 tests plus compilation, JSON, documentation-authority, semantic
  drift, banned-token, dependency, and diff gates; two independent current-byte
  reviews returned clean. No cleanup executor, target adapter, configured data,
  Qdrant, runtime, service, or retention authority was added or exercised.
  R-07 remains `IN_PROGRESS`; the next bounded seam is the import-pure,
  job-independent immutable candidate-plan authority using injected temporary
  inventories only.
- Immutable candidate-plan checkpoint (2026-07-13): private checkpoint
  `c870a1cb` adds the import-pure `goodq.clean-memory-plan.v1` authority and an
  immutable first-writer evidence store. The authority binds exact regular-file
  pre-state, the exact four configured Qdrant roles, canonical loopback endpoint
  identity, and the complete protected-boundary role set without binding jobs,
  approval, time, or random identity into its digest. Root/ancestor reparse and
  non-directory boundaries, Windows path aliases, duplicate physical-file
  identities, foreign first-writer evidence, and foreign temporary-path
  replacements fail closed or remain preserved for recovery. The 54-test
  temporary-only suite passed ten consecutive concurrency stress rounds plus
  compilation, import-purity, documentation-authority, semantic-drift,
  banned-token, dependency, and diff gates; three independent current-byte
  reviews returned clean. No configured data, target adapter, Qdrant service,
  action job, token, cleanup executor, or retention authority was read, added,
  or exercised. R-07 remains `IN_PROGRESS`; the next bounded seam is a
  read-only no-repeat audit of the passive `plan` orchestration boundary before
  any production adapter or CLI implementation.
- Passive plan-orchestration audit checkpoint (2026-07-13): three independent
  read-only source traces and a current Requests documentation check found no
  reusable exact configuration resolver, no complete no-follow filesystem
  observer, and no complete fail-closed Qdrant fingerprint observer. The
  reviewed sequence is strict configuration projection, filesystem observation,
  Qdrant observation, then runnable `plan` orchestration; each remains a
  separate checkpoint. The next bounded seam is only a deterministic,
  secret-free configuration projection in new `cli/clean_memory.py` with RED
  coverage in new `tests/unit/test_clean_memory_cli.py`. It performs no config
  load at import, filesystem or service observation, evidence-root creation,
  plan persistence, job/token work, or cleanup mutation. Evidence:
  `docs/diagnostics/R07_PASSIVE_PLAN_ORCHESTRATION_AUDIT_2026-07-13.md`.
- Configuration-projection checkpoint (2026-07-13): private checkpoint
  `a12ceb18` adds the import-pure, explicit three-symbol
  `goodq.clean-memory-configuration.v1` authority. It binds one exact configured
  epoch; database, sidecar, FAISS, and evidence-root topology; explicit enabled
  loopback Qdrant authority; exact four collection names; configured protected
  roots; deterministic unresolved roles; and a canonical secret-free SHA-256.
  Valid configured processing/model/Qdrant/archive/watchdog root overrides are
  bound into the digest, while cleanup/evidence overlap, protected aliases,
  Windows ambiguity, unknown FAISS authority, and declared FAISS aliases fail
  closed. Fresh verification passed 131 tests ten consecutive times, the
  185-test projection/candidate-plan union, compilation, documentation
  authority/drift, banned-token, dependency, index, and diff gates; three
  independent current-byte review lanes returned clean after correction. No
  configuration load, configured data, filesystem observation, Qdrant contact,
  evidence creation, job/token work, or cleanup mutation occurred. R-07 remains
  `IN_PROGRESS`; the next bounded mission is a read-only no-repeat audit of the
  filesystem-observer boundary before implementation.
- Filesystem-observer boundary audit checkpoint (2026-07-13): private
  checkpoint `f3ce0920` records that repository and platform traces found no
  reusable helper satisfying exact no-follow, same-handle identity/hash,
  complete FAISS enumeration, and fail-closed race evidence. The reviewed next
  seam is exactly `cli/clean_memory_filesystem.py` with focused coverage in
  `tests/unit/test_clean_memory_filesystem.py`. Windows observation is
  fixed-volume-bound and uses held-directory restart enumeration plus
  `OpenFileById`, with no descendant-path fallback; POSIX observation opens only
  `/` by path and then remains descriptor-relative and no-follow. The audit also
  corrected the remaining order: target filesystem observation, a separate
  protected-boundary authority audit/checkpoint, fail-closed Qdrant observation,
  then runnable planning only when every protected role is exact. No configured
  data, protected root, service, Qdrant, evidence store, job, token, or cleanup
  authority was read or exercised. Evidence:
  `docs/diagnostics/R07_FILESYSTEM_OBSERVER_BOUNDARY_AUDIT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the exact
  filesystem-observer source/test pair.
- Filesystem-observer implementation checkpoint (2026-07-13): private
  checkpoint `e8961889` adds the exact import-pure
  `goodq.clean-memory-filesystem-observation.v1` authority. Windows uses a fixed
  local volume handle, held directory handles, restart enumeration, and
  `OpenFileById` without descendant-path fallback; POSIX opens only `/` by path
  and remains descriptor-relative and no-follow. Present files bind physical
  identity, size, modification time, stream/link state, and SHA-256 to one held
  handle; stable absence is distinguished from inaccessible, redirected,
  irregular, ambiguous, unsupported, or changing state, and the complete FAISS
  tree is deterministic. Fresh verification passed 47 focused tests ten
  consecutive times (470 total), the 232-test configuration/candidate/filesystem
  authority union, compilation, exact public-API import, documentation authority
  and semantic-drift, banned-token, dependency, and staged-diff gates. Three
  independent current-byte reviews returned clean. No configured data,
  protected root, service, Qdrant, evidence store, job, token, MiniAgent, or
  cleanup authority was read or exercised. R-07 remains `IN_PROGRESS`; the next
  bounded mission is only a read-only no-repeat audit of protected-boundary
  authority before any implementation.
- Protected-boundary authority audit checkpoint (2026-07-13): three independent
  read-only traces confirmed that all eight unresolved roles lack one canonical
  repository source; producer defaults, environment/CWD discovery, sibling
  checkout inference, and live-ledger reconstruction are not authority. The
  strongest candidate for a future source is a versioned machine-local manifest
  at a fixed location derived from `candidate_evidence_root`, but that new
  authority/bootstrap architecture is not approved or implemented by this
  audit. The candidate would supply only the eight unresolved roles and could
  not override the ten configured roles. A later observer must use deterministic
  multi-member, path-free physical evidence and may reuse the completed platform
  backend only after an extraction-only parity checkpoint; it must not import or
  copy private observer symbols. The audit also proved that candidate-plan
  construction rejects duplicate protected logical IDs but not byte-identical canonical
  identity envelopes across roles; full physical-alias rejection remains later
  observer work. No configured or live root, service, data, Qdrant, evidence
  store, job, token, MiniAgent, or cleanup authority was read
  or exercised. Evidence:
  `docs/diagnostics/R07_PROTECTED_BOUNDARY_AUTHORITY_AUDIT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the focused
  candidate-plan duplicate canonical-envelope guard and its RED oracle.
- Duplicate protected-envelope guard checkpoint (2026-07-13): private
  checkpoint `4230a910` adds one candidate-plan validation that rejects
  byte-identical canonical protected identity envelopes across distinct roles
  and logical IDs. The focused oracle first failed because no exception was
  raised, then passed after the minimal guard; fresh verification passed the
  55-test authority suite, the 233-test configuration/candidate/filesystem
  authority union, compilation, import purity, documentation authority and
  semantic drift, banned-token, dependency, and diff gates. Three independent
  current-byte reviews returned clean. Valid authority bytes, round-trip
  behavior, schemas, public APIs, configuration, persistence, observers, and
  runtime behavior remain unchanged. The guard does not claim physical-alias
  detection across different envelopes. No configured or live root, service,
  data, Qdrant, evidence store, job, token, MiniAgent, or cleanup authority was
  read or exercised. R-07 remains `IN_PROGRESS`; the next bounded gate is an
  explicit operator decision on one protected-authority source and its
  non-circular authoring/trust bootstrap, not implementation.
- Protected-authority source decision evidence (2026-07-13): three independent
  read-only audits found no existing repository source capable of authorizing
  all eight unresolved protected roles. Tracked defaults, environment or caller
  injection, runtime state, discovery, producer roots, live ledgers, reports,
  and self-hashes remain non-authoritative. The operator approved one fixed
  machine-local canonical manifest beneath `candidate_evidence_root` with its
  expected SHA-256 held by an independently trusted external pin source. The
  manifest supplies member content; the external pin alone authorizes its exact
  canonical bytes, and the two publications remain separate actions. A
  strict typed full mapping in ignored local configuration is also viable and
  simpler, but was not selected because it couples content and authorization to
  the merged loader and a repository-local trust root. The approved model uses
  a separate pure selection projection and leaves the completed v1 projection
  closed. Existing resolved-config provenance/no-override policy, exact pin
  location and provenance, trusted effective-access-token, owner and access-
  control policy, authoring, reader, shared no-follow backend, member semantics,
  and rotation/recovery remain later decisions or seams. The
  source/trust model is approved but not implemented. No live configuration,
  root, service, data, Qdrant, evidence store, job, token, MiniAgent, or cleanup
  authority was read or exercised. Evidence:
  `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded gate defines exact path-free
  member semantics and the external-pin trust-root contract before code.
- Protected-authority semantics decision checkpoint (2026-07-13): the exact
  canonical eight-role manifest and merged 18-role membership contracts are now
  selected, including bounded member/path limits, configured positional IDs,
  explicit kind/presence policy, lexical duplicate/overlap rejection, one
  path-free composite envelope per role, stable-absence bytes, and volume-scoped
  physical-alias handoff. The approved external pin is one Windows v1 source
  beneath the actual ProgramData Known Folder, on fixed NTFS/ReFS with open-by-ID
  support, a separately enrolled administrator-owned protected DACL, an exact
  65-byte digest payload, no-replace first publication, and fail-closed
  unsupported rotation/recovery. POSIX remains unsupported pending its own
  capability audit. Three independent current-byte reviews closed routing-
  provenance, injected-evidence, bootstrap, schema, absence-preimage, and
  physical-disjointness contradictions. The corrected order first implements a
  non-authoritative pure membership projection; authenticated selection remains
  closed until production-owned Windows reader/enrollment evidence is separately
  audited and implemented. No live configuration, protected root/member,
  manifest, pin, ACL, service, data, Qdrant, evidence store, job, token,
  MiniAgent, or cleanup authority was read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly
  `cli/clean_memory_protected_membership.py` with RED coverage in
  `tests/unit/test_clean_memory_protected_membership.py`.
- Protected-membership projection checkpoint (2026-07-13): private checkpoint
  `81aafce1` adds the selected import-pure
  `goodq.clean-memory-protected-membership.v1` structural envelope. It validates
  exact canonical manifest bytes, the eight-role manifest census, the closed v1
  configured-role compatibility table, the canonical 18-role merge, lexical
  duplicates/aliases and destructive-scope overlap, and detached digest
  binding while retaining no filesystem, reader, pin, trust, planning, or
  cleanup capability. Mutation-sensitive RED cycles closed forged configured
  topology, byte-gate ordering, Windows device aliases, recursive JSON, Unicode
  controls, and parameter-expansion cases. Fresh verification passed 98 focused
  tests, the 331-test configuration/candidate/filesystem/membership authority
  union, compilation, staged-diff, documentation authority/index, semantic-
  drift, banned-token, and dependency gates. Three independent current-byte
  reviews returned clean. No configured or live root, manifest, pin, ACL,
  service, data, Qdrant store, evidence store, job, token, MiniAgent, or cleanup
  authority was read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only
  Windows external-pin boundary audit before any reader, enrollment,
  publication, or authenticated-selection implementation.
- Windows external-pin boundary audit checkpoint (2026-07-13): three
  independent read-only traces and current official Win32 documentation agree
  that the completed held-handle observer provides the only viable no-follow,
  open-by-ID foundation, but its implementation is private and no repository
  token, owner/DACL, Known Folder, or exact pin-reader authority exists. The
  reviewed next seam is only an extraction-parity checkpoint adding
  `steps/common/windows_held_handle.py` and its focused test while adapting the
  existing filesystem observer/test; no reader or new security capability is
  included. The audit selects the future no-argument Windows reader API, exact
  path-free evidence projection/digest, effective-token acceptance and digest
  preimage, owner/DACL/anchor security preimage, Known Folder flags, exact
  65-byte read/recheck order, and closed 13-code reader failure taxonomy. POSIX,
  enrollment, publication, rotation, authenticated composition, protected
  observation, Qdrant observation, planning, and execution remain closed. Three
  independent current-byte reviews found and closed shared identity ownership,
  handle lifecycle, token duplication/restriction, descriptor, ACE-mask, and
  digest-preimage ambiguities before returning clean. No live ProgramData, pin,
  token, ACL, configured root, service, data, Qdrant,
  evidence, job, MiniAgent, or cleanup authority was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the four-file
  extraction-parity checkpoint selected by that audit.
- Windows held-handle extraction-parity checkpoint (2026-07-13): private
  checkpoint `0f567557` moves the already-proven no-follow Win32 traversal,
  opaque handle ownership, NTFS/ReFS open-by-ID mechanics, stable physical
  snapshot, canonical identity renderer, stream contract, and same-handle hash
  into `steps/common/windows_held_handle.py`. The filesystem observer now uses
  only the exact shared public boundary while retaining its public API, outward
  errors/evidence, role traversal, POSIX behavior, and native drive-root-only
  path rule. Independent current-byte reviews found and closed exact-message,
  leaked-ABI, missing capability binding, close-chain parity, import-gate,
  opaque-test-handle, and duplicate sharing-oracle gaps. Fresh verification
  passed 92 focused tests, two native Windows witnesses, the 376-test approved
  authority union, compilation, and staged-diff checks; all three final reviews
  returned clean. No live ProgramData, pin, token, ACL, configured root,
  service, GoodQ data, Qdrant store, evidence store, job, MiniAgent, or cleanup
  authority was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_HELD_HANDLE_EXTRACTION_CHECKPOINT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the audited
  read-only Windows external-pin reader source/test pair, with no enrollment,
  publication, rotation, authenticated composition, planning, or cleanup.
- Windows reader capability-gap audit (2026-07-13): the reader-only preflight
  found that the exact shared opaque-handle boundary cannot satisfy the audited
  same-handle security and payload contract. Descendant handles do not request
  `READ_CONTROL`, raw handles are intentionally private, no public security-
  descriptor operation exists, and `hash_file()` returns no payload bytes.
  Implementing the reader now would require a private-handle escape, duplicated
  Win32 traversal, descendant pathname reopen, or weakened proof; all are
  rejected. The corrected order first checkpoints one exact same-handle
  `read_file_bounded(..., maximum_bytes=...) -> (prefix, eof_observed)` method,
  then separately selects and implements the opaque token/descriptor/
  `AccessCheck` join, and only then implements the reader. No live ProgramData,
  pin, token, ACL, configured root, service, GoodQ data, Qdrant, evidence, job,
  MiniAgent, or cleanup target was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_READER_CAPABILITY_GAP_AUDIT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the shared backend
  bounded-read source/test pair.
- Windows bounded-read checkpoint (2026-07-13): private checkpoint `73430481`
  adds the exact 1-through-66-byte same-handle read capability without exposing
  a raw handle, pointer, pathname reopen, private token field, or new module
  export. Exact 65-byte EOF, exact/over-cap 66-byte behavior, empty/short reads,
  strict type/range rejection, token lifecycle, impossible native counts,
  error translation, and `hash_file()` interoperability are proven. Independent
  review found and closed an over-specified chunk-schedule oracle before all
  three final reviewers returned clean. Fresh verification passed 114 focused
  tests, three native temporary-only witnesses, the 398-test approved authority
  union, compilation, documentation authority/drift, banned-token, dependency,
  and staged-diff gates. No live ProgramData, pin, token, ACL, configured root,
  service, GoodQ data, Qdrant, evidence, job, MiniAgent, or cleanup target was
  read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CHECKPOINT_2026-07-13.md`. R-07
  remains `IN_PROGRESS`; the next bounded seam is only a read-only decision on
  the opaque-token/security-descriptor/process-token/`AccessCheck` boundary.
- Windows same-handle security-capability decision (2026-07-13): selected an
  opt-in `security_read` backend profile and one immutable detached
  self-relative descriptor-copy method. The volume-root traversal handle keeps
  its exact existing rights; only `open_by_id()` descendants add `READ_CONTROL`,
  and only those opaque tokens may retrieve owner/group/DACL descriptor bytes
  from the same held handle. The backend always validates and frees the native
  descriptor allocation before return. Descriptor parsing, effective-token
  snapshots, `DuplicateTokenEx`, fixed file-object generic mapping, and
  per-right `AccessCheck` remain reader-owned because they must bind to the
  already-fixed reader identity and security-policy evidence. Boolean-only and
  policy-shaped backend alternatives were rejected because they either discard
  required owner/group/control/ordered-ACE evidence or embed external-pin policy
  in a projection-neutral filesystem primitive. Evidence:
  `docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the two-file shared
  descriptor capability source/test checkpoint.
- Windows security-descriptor capability checkpoint (2026-07-13): private
  checkpoint `882dc70` adds the exact opt-in `security_read` profile and one
  same-handle detached self-relative descriptor-copy method. Observation mode
  retains its prior rights and native dependency surface; the volume root stays
  at `0x81`, and only `open_by_id()` descendants add `READ_CONTROL`. Every
  successful non-null native allocation is validated, copied exactly, and
  freed once; error-path output remains undefined and untouched, and cleanup
  failure cannot produce evidence. Independent oracle review found and closed
  loader-error-state, pointer-provenance, share/security-attribute parity,
  cleanup-precedence, inclusive-length, native-witness, returned-error-code,
  causeless-validation, and observation-dependency gaps before all three final
  current-byte reviews returned clean. Fresh verification passed 101 backend
  tests, 46 observer tests, the 431-test approved authority union, compilation,
  documentation authority/drift, banned-token, dependency, and staged-diff
  gates. No live ProgramData, pin, token, ACL, configured root, service, GoodQ
  data, Qdrant, evidence, job, MiniAgent, or cleanup authority was read or
  changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_SECURITY_DESCRIPTOR_CHECKPOINT_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the audited
  two-file, no-argument Windows external-pin reader and its focused tests.
- Windows external-pin implementation decision (2026-07-13): three independent
  read-only implementation traces found that the closed boundary audit did not
  uniquely select token-buffer caps and query fences, SID/descriptor parsing,
  ACE padding/flags, stable-absence bracketing, enrollment precedence,
  duplicate-token cadence, privilege-output validation, or the evidence
  object's construction pattern. The operator selected the safest long-term
  route: freeze those choices before RED rather than encode them silently. The
  checkpoint selects one pure bounded parser, one retained baseline token plus
  short-lived comparison handles, one duplicate per security object, a
  two-stage token/DACL binding, complete parent/snapshot absence proof, exact
  ten-key detached evidence, and finite edge-error precedence. Current official
  Win32 documentation confirms the token ownership, buffer, Known Folder, and
  `AccessCheck` boundaries but does not promise a canonical successful
  `PrivilegeSetLength`, so the decision accepts only bounded internally
  consistent zero-initialized output. No reader/test code or live ProgramData,
  pin, token, ACL, configured root, service, GoodQ data, Qdrant, evidence, job,
  MiniAgent, or cleanup authority was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_IMPLEMENTATION_DECISION_2026-07-13.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly the two-file,
  no-argument reader through RED/GREEN/refactor.
- Windows external-pin reader checkpoint (2026-07-14): private test checkpoint
  `a82cd743` and source checkpoint `017f0f64` implement the audited no-argument,
  path-free Windows trust-root observer. The reader owns exact Known Folder and
  open-by-ID traversal, effective-token comparison, enrollment and security-
  policy validation, one bounded pin read, full authority rechecks, detached
  ten-key evidence, and complete public-error sanitization. The shared backend
  now reserves ledger ownership before native acquisition and drains exactly in
  place across every cleanup failure. Independent review closed startup-
  allocation, cyclic/over-depth graph, exact-cap, public-cycle, snapshot-
  allocation, ledger-order, and dynamic-import oracle gaps before all three
  exact-byte receipts returned clean. Fresh verification passed the 616-test
  reader/backend pair, the 946-test approved authority union, 35 documentation
  tests, compilation, exact import/export, documentation authority/drift,
  banned-token, dependency, and diff gates. No live ProgramData, production pin,
  token, ACL, configured root, service, GoodQ data, Qdrant, evidence store, job,
  MiniAgent, or cleanup authority was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only
  no-repeat audit of authenticated protected-membership composition before
  Qdrant observation or runnable planning.
- Authenticated protected-membership composition audit checkpoint
  (2026-07-14): the production call graph and three independent read-only
  reviews found no manifest reader, protected-member observer, ProgramData
  lexical-locator handoff, or authenticated composition authority. The prior
  next-mission wording incorrectly included cleanup-target
  `FilesystemObservation`; that evidence belongs only to later
  `ResolvedCleanupScope` assembly and cannot authenticate manifest bytes or
  protected members. The future `plan` edge must call the external-pin reader,
  fixed-child manifest reader, membership projection, and protected observer
  itself; authenticate the same held manifest bytes before parsing; reject
  lexical and physical pin/member overlap; and only then observe cleanup targets
  and Qdrant. No live ProgramData, pin, manifest, token, ACL, configured or
  protected root, service, GoodQ data, Qdrant, evidence store, job, MiniAgent,
  or cleanup authority was read or changed. Evidence:
  `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is a read-only boundary
  audit selecting only the fixed-child manifest reader, preserving its frozen
  direct-pin digest comparison and mismatch-before-parser ownership. The
  ProgramData locator/recheck remains a separate later audit before protected
  observation or composition.
- Protected-manifest reader capability-gap audit checkpoint (2026-07-14): three
  independent read-only source/lifecycle/API reviews found no equivalent reader
  and proved it cannot safely be created yet. The shared same-handle reader
  rejects every cap above 66 although maximum-size manifest EOF needs
  `4_194_305`; the one exact canonical manifest validator remains private to
  structural membership; and the source contract requires manifest-chain owner
  and effective-write validation although the manifest-specific policy and the
  shared projection-neutral token, descriptor-parsing, and effective-access
  mechanics needed beyond the existing detached descriptor read remain
  unselected or unavailable. The exact first
  prerequisite is only the two-file shared-backend capacity extension, keeping
  the existing method/public surface and external-pin caller's exact 66-byte
  request. Canonical-validator extraction/parity and manifest security-policy
  selection/mechanics remain separate prerequisites before reader RED. No live
  ProgramData, pin, manifest, token, ACL, configured or protected root, service,
  GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup authority was
  read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is only the existing shared
  held-handle method and focused test, widening its accepted ceiling to exact
  `4_194_305` without adding a second API or changing 66-byte pin behavior.
- Windows bounded-read capacity extension checkpoint (2026-07-14): private
  checkpoint `617cd32a` widens only the existing shared same-handle reader's
  accepted exact-integer ceiling from 66 to `4_194_305`. The method/signature,
  zero-byte EOF witness, exact-cap no-probe behavior, token ownership, rewind,
  native-error translation, cleanup, module exports, and backend public surface
  remain unchanged; the external-pin reader still makes exactly one 66-byte
  request. Focused TDD first produced two expected ceiling failures, then 24
  bounded-read tests passed. Fresh verification passed 141 held-handle, 477
  external-pin, and 46 filesystem-adapter tests (664 total), compilation, and
  diff gates; independent task review returned spec PASS and Approved with no
  findings, and a second bounded oracle review returned clean. No live
  ProgramData, pin, manifest, token, ACL, configured or
  protected root, service, GoodQ data, Qdrant, evidence store, job, MiniAgent,
  or cleanup authority was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CAPACITY_EXTENSION_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only no-
  repeat audit selecting one pure canonical protected-manifest validator and
  exact membership extraction/parity seam before any parser or reader code.
- Protected-manifest validator extraction decision (2026-07-14): repository
  census and three independent read-only reviews found no equivalent public
  validator. The binding completed-membership no-repeat rule resolved an
  initial four-file/six-file disagreement: do not reopen configuration-v1
  merely to share private helpers. The selected four-file seam adds one
  standard-library-only shared validator/test and adapts membership/test. Its
  exact six-symbol API includes immutable schema, child, maximum-byte, and
  eight-role constants, a frozen init-disabled path-free-repr result with a
  detached manifest view and exact-byte SHA-256, and one keyword-only-flavor
  validator. Membership preserves its public API, outer byte/size ordering
  fence, configuration validation, combined-scope rules, canonical output,
  digest, and final mutation recheck while relinquishing all manifest parsing.
  Exact error-message, accepted/rejected corpus, import-purity, delegation,
  capability, and output parity are frozen by the selected RED matrix. Manifest
  security policy remains an independent mandatory blocker before reader RED.
  No live ProgramData, pin, manifest, token, ACL, configured or protected root,
  service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup
  authority was read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_DECISION_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly the reviewed
  four-file validator extraction through RED/GREEN/refactor and independent
  current-byte review, with no physical reader or security-policy code.
- Protected-manifest validator extraction checkpoint (2026-07-14): private
  checkpoint `41e56c74` adds the exact standard-library-only canonical validator
  and adapts structural membership to consume it once with the original bytes
  and resolved flavor. Membership preserves its public API, outer byte/size and
  configuration precedence, combined 18-role alias/overlap authority,
  projection bytes/digests, and final mutation recheck while relinquishing all
  manifest parsing. Focused TDD first proved the absent API, deliberate
  unimplemented behavior, and unadapted membership ownership. Fresh controller
  verification passed 103 validator tests, 102 membership tests, the 205-test
  pair, the 437-test approved authority union, exact four-file compilation, and
  diff gates. Independent current-byte review returned `READY` with no findings
  after total-count, opaque-delegation, multi-fault precedence, signature/ID,
  structural-ownership, and capability-audit oracles were strengthened. No live
  ProgramData, pin, manifest, token, ACL, configured or protected root, service,
  GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup authority was
  read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only the decision-
  only, read-only manifest security-policy audit. No shared security-mechanics
  extraction or protected-manifest reader code is authorized yet.
- Protected-manifest security-policy decision (2026-07-14): repository and
  official-platform evidence select exact policy only for the fixed
  `candidate_evidence_root` and direct `protected-boundaries.json`; broader data
  and control ancestors remain writer-compatible held identity/race anchors.
  The candidate root and manifest use exact administrator-owned protected DACL
  envelopes with the enrolled ordinary reader, medium mandatory label, and
  object-specific mutation denials. The existing external pin remains the sole
  content authority. Owner/group/DACL/label transport (`0x17`) is explicitly a
  filtered descriptor: detached `AccessCheck` is only a bounded mutation-denial
  oracle, while real kernel opens and same-handle reads prove positive access.
  The policy does not claim permanent first-publication provenance; that would
  require separately pinned physical enrollment identity. Candidate-plan write
  compatibility and exact native `0xb014` deployment remain later test-owned
  integration witnesses. Two adversarial current-byte reviews returned `READY`.
  No live token, ACL, configured/protected root, manifest, pin, service, GoodQ
  data, Qdrant, evidence store, job, MiniAgent, or cleanup authority was read or
  changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly the two-file TDD
  addition of opt-in held-handle profile `security_read_label` with request mask
  `0x17`, existing-profile parity, and a pytest-owned Windows-native temporary-
  file transport witness. Token, parser, policy, `AccessCheck`, reader,
  publication, and production ACL work remain closed.
- Windows label-security transport checkpoint (2026-07-14): private checkpoint
  `6b40d8e8` adds only exact opt-in held-handle profile
  `security_read_label`. It preserves the existing `observation` and
  `security_read` profiles, root access `0x81`, descendant security-read access
  `0x20081`, public surface, native ABI, validation, bounds, cleanup, and errors.
  Existing `security_read` remains exact `0x7`; label-aware transport requests
  exact `0x17`. A pytest-owned Windows temporary-file witness executed the real
  held-handle native path without ACL mutation. After independent review found
  a test-oracle gap, the full root/foreign/closed-token, structural, native-
  failure, malformed-copy, cleanup, and precedence matrix was run against both
  profiles. Fresh verification passed 167 held-handle tests, 477 external-pin
  tests, the 644-test combined authority set, two-file compilation, and diff
  gates. Two current-byte reviews returned `READY`. The checkpoint proves only
  filtered transport; exact `0xb014` deployment and candidate-plan ACL
  compatibility remain later test-owned integration witnesses. No live token,
  configured or production ACL, configured/protected root, manifest, pin,
  service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup
  authority was read or changed.
  Evidence:
  `docs/diagnostics/R07_WINDOWS_LABEL_SECURITY_TRANSPORT_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only no-
  repeat ownership/parity audit of projection-neutral token snapshots,
  filtered-descriptor parsing, fixed generic mapping, and bounded mutation-
  denial mechanics. No mechanics extraction or manifest-reader code is yet
  authorized.
- Windows security-mechanics extraction decision (2026-07-14): three
  independent read-only audits reconciled parser-first, token-first, and
  combined options. The selected smallest coherent rollback boundary is one
  four-file checkpoint: add `steps/common/windows_security_mechanics.py` and
  its focused test, then adapt the completed external-pin source/test in the
  same checkpoint. Token session ownership, the stable descriptor allocation,
  private duplication, mapping, and bounded `AccessCheck` share one native
  lifetime; splitting them would expose a pointer or adapt the same cleanup
  graph twice. The shared layer owns mechanics only. External-pin policy,
  outward errors/evidence, failure order, base 17-call token profile, and frozen
  reader-identity v1 projection/digest remain exact. A separate mandatory-
  policy profile observes class 27 without entering external-pin v1. The held-
  handle backend and protected-manifest reader remain closed. No live token,
  configured or production ACL/root, manifest, pin, service, GoodQ data,
  Qdrant, evidence store, job, MiniAgent, or cleanup authority was read or
  changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_DECISION_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly that four-file
  extraction through RED/GREEN/refactor and independent current-byte parity
  review. The frozen reader-identity policy remains a separate later seam.
- Windows security-mechanics extraction checkpoint (2026-07-14): private
  checkpoints `ae4d35bc` and `0827193a` establish the exact import-pure ABI and
  extract token observation/ownership, filtered-descriptor parsing, one stable
  parse/access allocation, generic mapping, private duplication, and bounded
  mutation-denial mechanics into one shared module. The external-pin adapter
  preserves its frozen API, thirteen errors, base 17-call profile, v1 identity
  projection/digest, security/evidence bytes, five-duplicate/19-check sequence,
  and failure/cleanup order. Adversarial TDD closed token failure-sentinel and
  exception-graph lifecycle gaps across all three control-flow types. Fresh
  verification passed 254 shared tests, 499 external tests, the historical 167
  held-handle baseline, 46 filesystem tests, the 1,357-test clean-memory
  authority union, compilation, semantic-drift, banned-token, dependency, and
  staged-diff gates. Two independent final current-byte reviews returned
  `READY`. No live security or configured-data surface was read or changed.
  Evidence:
  `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only no-
  repeat reassessment of the separate frozen reader-identity v1 policy seam
  before any protected-manifest reader implementation is authorized.
- Windows reader-identity policy decision (2026-07-14): three independent
  read-only audits selected a separate import-pure GoodQ policy authority below
  `cli`, rather than keeping the v1 digest external-pin-private, moving policy
  into projection-neutral mechanics, or combining extraction with the physical
  manifest reader. Two follow-up reviews returned `READY` on the exact
  three-symbol surface: one fixed path-free policy error, early validation, and
  late digest. The shared layer accepts only exact mechanics snapshots, exact
  base/mandatory profiles, and an exact unsigned-64 change-notify LUID; base
  requires mandatory policy `None`, while mandatory accepts only exact `1` or
  `3`. It owns common ordinary-reader acceptance and the private frozen v1
  canonical bytes, but returns only the 64-lowercase-hex digest. The external
  adapter retains route, enrollment/DACL/access policy, outward errors,
  evidence, race fencing, and cleanup. The future manifest reader retains
  mandatory-profile selection, direct external-evidence comparison,
  descriptor/label/access policy, and its own lifecycle. No live token, ACL,
  descriptor, configured/protected root, manifest, pin, service, GoodQ data,
  Qdrant store, evidence store, job, MiniAgent, or cleanup target was read or
  changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_DECISION_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly the reviewed
  four-file policy extraction/adaptation through RED/GREEN/refactor and
  independent current-byte parity review. The protected-manifest reader remains
  closed.
- Windows reader-identity policy checkpoint (2026-07-14): private checkpoint
  `02530486` adds the exact three-symbol import-pure shared policy and adapts
  the external-pin reader without changing its public API, thirteen errors,
  evidence bytes/digests, base token profile, race fences, or cleanup. The
  shared module preserves the ordinary-reader acceptance domain, base and
  mandatory profile fences, and private frozen v1 bytes while returning only
  validation or lowercase SHA-256. Fresh verification passed 65 direct tests,
  the zero-drop 499-test external baseline, 254 mechanics tests, the historical
  167 held-handle baseline, 46 filesystem tests, 205 validator/membership
  tests, the 1,422-test authority union, compilation, semantic-drift,
  banned-token, dependency, and committed-diff gates. Independent current-byte
  reviews returned `APPROVED` and `READY`. No live security or configured-data
  surface was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only
  decision audit of the protected-manifest reader public contract and exact
  input/error fence. Reader source and tests remain closed.
- Protected-manifest reader contract decision (2026-07-14): three independent
  read-only API, lifecycle, and parity traces selected the exact four-export
  reader surface, sixteen path-free errors, direct configuration and external-
  evidence authentication, same-handle pin-before-parser lifecycle, and
  immutable nine-key evidence projection. Review corrected endpoint-only
  evidence to retain the complete held physical route, then corrected an
  initial fixed-four assumption: if authenticated `storage_root` has `n`
  components, route evidence has exact per-call cardinality `n + 3`, minimum
  four, with no invented reader-only maximum. Existing configuration,
  external-pin, validator, membership, held-handle, security-mechanics, and
  reader-identity authorities remain closed. No live security or configured-
  data surface was read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CONTRACT_DECISION_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly the new reader
  source/test pair through RED/GREEN/refactor and independent current-byte
  review. Composition, observation, Qdrant, planning, approval, and cleanup
  remain closed.
- Protected-manifest reader checkpoint (2026-07-14): private checkpoint
  `66ee4f47` adds the exact four-export authenticated Windows reader and its
  two-file regression authority. The reader authenticates direct configuration
  and external-pin evidence, retains the complete physical route, enforces the
  selected reader/descriptor/access policy, compares the same-handle manifest
  digest before one canonical parse, completes final race fences and cleanup,
  and returns immutable nine-key path-free evidence with repr-hidden retained
  bytes. Fresh verification passed 148 focused tests, the zero-drop 1,422-test
  pre-reader authority union, the 1,570-test reader-first combined gate,
  compilation, documentation, banned-token, dependency, staged-diff, and exact
  two-file census gates. Three independent current-byte reviews found no
  critical, major, or minor issue. Evidence:
  `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only
  ownership/parity audit of the composition-owned ProgramData locator and final
  recheck contract. Protected-member observation, authenticated composition,
  Qdrant observation, planning, approval, and cleanup remain closed.
- Windows ProgramData locator/recheck decision checkpoint (2026-07-14): three
  bounded read-only ownership, lifecycle, and parity traces selected one shared
  extraction-parity authority rather than a composition-local duplicate. The
  exact next source seam adds the five-export import-pure ProgramData locator
  and direct tests, then adapts only the external-pin reader and its tests while
  preserving its exact public API, evidence, native order, traversal, and
  cleanup behavior. Composition retains invocation, direct-output recheck,
  lexical overlap, and race policy; the shared layer owns only the actual
  `FOLDERID_ProgramData` acquisition, fixed child spelling, lexical grammar,
  buffer lifetime, and path-free native failures. Current Microsoft Win32
  documentation confirms the returned Unicode buffer is caller-owned and must
  be released with `CoTaskMemFree`. No live ProgramData, pin, manifest, token,
  ACL, configured/protected root, service, GoodQ data, Qdrant, evidence store,
  job, MiniAgent, approval, or cleanup target was read or changed. Evidence:
  `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_RECHECK_DECISION_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly the four-file
  shared locator TDD extraction/adaptation checkpoint. Protected-member
  observation, composition, Qdrant, planning, approval, and cleanup remain
  closed.
- Windows ProgramData locator checkpoint (2026-07-14): private checkpoint
  `f93ae143` adds the exact five-export import-pure shared locator and adapts the
  external-pin reader with zero-drop parity. Binding retains the exact callable
  Known Folder and free capabilities; resolution validates detached components
  and frees every native buffer; all public values and failure graphs remain
  immutable, redacted, and path-free. Fresh verification passed 53 direct
  locator tests, the frozen 499-test external suite, 148 protected-manifest
  reader tests, the 737-test adjacent authority gate, the exact 1,422-test
  frozen union, and the 1,623-test expanded authority gate, plus compilation,
  documentation, banned-token, dependency, exact four-file staged-census, and
  diff gates. Independent contract and extraction-parity reviews returned
  `PASS`. No live ProgramData or runtime authority was read or changed.
  Evidence:
  `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_CHECKPOINT_2026-07-14.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only
  ownership and contract audit of the protected-member observer and direct
  pin-chain physical-exclusion boundary. Authenticated composition, Qdrant
  observation, runnable planning, approval, and cleanup remain closed.
- Protected-boundary observer contract decision (2026-07-15): three independent
  read-only ownership, lifecycle, and contract traces found no production
  protected-member physical observer and selected one exact two-file seam:
  `cli/clean_memory_protected_boundary.py` plus its focused unit test. The
  observer accepts only exact direct membership and external-pin evidence,
  derives the five pin identities internally, uses only the public Windows
  held-handle backend, retains every parent/member through one global race
  fence, rejects cross-path aliases and pin collisions, proves stable absence
  with two equal complete parent-membership snapshots, and atomically returns
  the existing 18-role `ProtectedBoundaryEvidence` tuple. The decision freezes
  exactly three exports, twelve path-free errors, Windows-only v1 behavior,
  cleanup/control precedence, privacy tiers, and the RED/verification matrix.
  It rejects a second wrapper/digest because every selected composite envelope
  already binds the membership digest and candidate planning directly consumes
  the existing type. No live ProgramData, security, configured-data, service,
  planning, approval, or cleanup surface was read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CONTRACT_DECISION_2026-07-15.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly that new
  two-file observer through RED/GREEN/refactor and independent current-byte
  review. Authenticated composition, Qdrant observation, runnable planning,
  approval, and cleanup remain closed.
- Protected-boundary observer checkpoint (2026-07-15): private source
  checkpoints `9e225655` and `636f4bfd` add the exact three-export Windows-only
  observer and close a final error-code deletion/rebinding bypass. The observer
  authenticates only direct membership and external-pin evidence, derives all
  five pin identities internally, traverses descendants only through retained
  held handles, proves stable absence, rejects aliases and pin collisions, and
  atomically returns the existing 18-role evidence tuple. Fresh verification
  passed 184 focused tests, the 1,155-test bounded authority union, and the
  1,807-test expanded zero-drop gate on an unchanged retry, plus compilation,
  committed two-file census, diff, and independent current-byte review gates.
  The first expanded run retained one known fail-closed synthetic temporary-
  tree `observation_raced` receipt rather than suppressing it. No live
  ProgramData, pin, manifest, protected/configured root, service, data, Qdrant,
  job, approval, or cleanup surface was read or changed. Evidence:
  `docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CHECKPOINT_2026-07-15.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only
  no-repeat ownership and contract re-audit of authenticated protected-
  membership composition. Qdrant observation, runnable planning, approval,
  jobs/tokens, and cleanup remain closed.
- Authenticated protected-membership composition recheck decision (2026-07-15):
  three read-only current-byte traces found one singular acyclic authority graph
  and no production composition caller. The selected next seam modifies only
  existing `cli/clean_memory.py` and `tests/unit/test_clean_memory_cli.py`, keeps
  the three-symbol public API exact, adds one private helper/error, uses only
  function-local public imports, and returns the observer's same exact 18-role
  tuple without a wrapper or digest. The decision freezes Windows-only
  pre-capability configuration authentication, four exact composition-owned
  ProgramData location acquisitions, one call per direct reader/projector/
  observer, immediate authentication before forwarding, complete configuration/
  pin/manifest/membership/boundary digest binding, component-boundary lexical
  pin/member exclusion before physical observation, five private composition
  errors, dependency-owned error precedence, upstream-drift precedence, final
  direct-output rechecks after the fourth location fence, and the RED/negative-
  mutant matrix. No live ProgramData,
  configured data, Qdrant, service, job, approval, or cleanup surface was read
  or changed. Evidence:
  `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_RECHECK_DECISION_2026-07-15.md`.
  R-07 remains `IN_PROGRESS`; the next bounded seam is exactly that existing
  two-file TDD implementation. Cleanup-target observation, Qdrant, scope
  assembly, planning/persistence, command parsing, approval, jobs/tokens,
  process control, and cleanup remain closed.
- Authenticated protected-membership composition checkpoint (2026-07-15):
  private source commit `d20a74ba` implements the selected private composition
  authority in exactly the existing source/test pair while preserving the
  three-symbol public API. Exact Windows configuration and derived paths, four
  ProgramData locator fences, one-call direct reader/projector/observer order,
  digest bindings, component-boundary lexical exclusion, immediate and final
  direct-output authentication, same-object tuple return, upstream-drift
  precedence, and path-free closed errors are now enforced. Review hardening
  also rejects detached separators/control characters, equal-value distinct
  manifest bytes, forged nested location types, dependency-owned raw error
  graphs and arguments, and unknown/non-string/missing public-error codes. Fresh
  verification passed 265 focused tests, the exact 1,941-test zero-drop
  authority union, the 375-test MiniAgent/action-job/shared-authority gate,
  compilation, public/private API census, documentation authority/drift,
  banned-token, dependency, diff, and two independent exact-hash review gates.
  One earlier unrelated passive-latest concurrency receipt passed isolated and
  on unchanged retry; the current exact source later passed the 375-test gate
  directly. No live ProgramData, pin, manifest, configured data, Qdrant,
  service, job, approval, or cleanup surface was read or changed. Evidence:
  `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_CHECKPOINT_2026-07-15.md`.
  R-07 remains `IN_PROGRESS`; the next bounded mission is only a read-only no-
  repeat ownership and contract audit of fail-closed Qdrant observation before
  any scope assembly or runnable planning. Planning/persistence, command
  parsing, approval, jobs/tokens, process control, and cleanup remain closed.
- Fail-closed Qdrant observation boundary audit (2026-07-16): three independent read-only traces determined that no existing helper satisfies the passive, fail-closed, four-collection observer contract. The audit defined loopback HTTP REST transport, `qdrant-client` versioning, and the fail-closed `QdrantObservation` shape for the four canonical collections, with no Qdrant service or configured data contacted or changed. Evidence: `docs/diagnostics/R07_QDRANT_OBSERVATION_BOUNDARY_AUDIT_2026-07-16.md`.
- Fail-closed Qdrant observer seam implementation (2026-07-16): implemented the import-pure, passive, fail-closed Qdrant observer in `cli/clean_memory_qdrant.py` and `tests/unit/test_clean_memory_qdrant.py`. The observer validates configuration digests and limits error codes before querying loopback HTTP REST endpoints for the four collections, mapping unreachable, connection, timeout, 404, or 500 status results to `exists=False` target records. Fingerprints are calculated deterministically by scrolling point payloads and IDs. Passed 7 focused unit tests, 557 clean-memory tests, the full 4018-test private gate, compilation, import purity, and document authority. No live Qdrant, configured data, or cleanup target was modified. Evidence: `docs/diagnostics/R07_QDRANT_OBSERVER_CHECKPOINT_2026-07-16.md`. R-07 remains `IN_PROGRESS`; the next bounded mission is to reconcile identity database tests to temporary roots under R-08.
- Public impact: RELEASE_REQUIRED

### R-08 — Reconcile identity routes and background-job recovery

- Priority: P1
- Status: OPEN
- Finding: the audited identity branch contained duplicate routes and a crashed
  job could leave a permanent running marker; tests can also touch the live
  identity root, YAML and JSON both act as roster authorities, writes are not
  locked/atomic, and API failures can expose paths or subprocess details.
- Repair: redirect every identity test to a temporary root; make YAML the sole
  roster authority with JSON as a derived read projection; use locked atomic
  writes; correct `GOODQ_IDENTITY_PATH` precedence; persist process identity;
  recover stale/dead jobs; require exact-operation/full-scope MiniAgent
  confirmation plus durable generic execution audit for identity mutations and
  processes; and redact path, subprocess, and exception detail.
- Completion gate: live roster checksums remain unchanged by tests; read and
  preview operations leave live and temporary identity/graph roots unchanged;
  route uniqueness, exclusion, synchronization failure, concurrent write,
  exact confirmation, durable audit, persistent process-job ownership, crash,
  restart recovery, and redaction tests pass before the Workbench browser
  witness is rerun.
- Public impact: RELEASE_REQUIRED
- Route-effect evidence (2026-07-12): six nominal identity reads/previews
  currently mutate automatically. After confirming the graph database exists,
  the two system identity projections construct `KnowledgeGraph`, which opens a
  writable connection, enables WAL, can create sidecars, can execute
  schema/index DDL, and commits; four identity GET routes call `_data_path()`,
  which creates the identity root. R-05 must classify these operations as
  `automatic_mutation` until R-08 supplies read-only/no-create constructors and
  temporary-root evidence. R-05 must not repair identity persistence inside the
  common boundary seam. Evidence:
  `docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_AUDIT_2026-07-12.md`.
- Human-curated Phase 5A sub-gate: review face clusters, speaker clusters,
  mentions, and unresolved roster members; create mappings only from confirmed
  human decisions; run roster validation and scene-first identity tests; promote
  only after the evidence gate passes; perform no automatic identity promotion;
  rerun Workbench browser verification against the live API.

### R-09 — Rebuild current-state truth from live evidence

- Priority: P1
- Status: VERIFIED
- Finding: human and JSON state surfaces describe earlier ingestion, promotion,
  service, installer, and toolchain snapshots.
- Repair: capture one fresh evidence snapshot after checkpointing, then generate
  human and JSON state from that same source; correct stale ingestion, model,
  service, RAG context, Hermes verification, and authority-chain claims while
  labeling historical epochs explicitly.
- Completion gate: human and JSON state agree with one live probe and
  verification time; no older epoch is described as active; historical evidence
  is clearly non-authoritative.
- Checkpoint: `docs/diagnostics/R09_CURRENT_STATE_TRUTH_2026-07-11.md` records
  evidence `2923b9a7ca972db2`, deterministic human/JSON/RAG projections, the
  dynamic Hermes prompt contract, focused tests, and independent final reviews.
- Public impact: SANITIZE

### R-10 — Align architecture with governed materialization

- Priority: P1
- Status: VERIFIED
- Finding: older canonical documents still imply ingestion-time active
  SQLite and graph persistence.
- Repair: correct Qdrant storage-root documentation and align staged ingestion,
  governed materialization, promotion, and active-memory projections across
  canonical architecture docs before dependent operational docs.
- Completion gate: focused code traces/tests and docs agree; staged-only and
  promoted-materialization tests demonstrate the written model.
- Public impact: RELEASE_REQUIRED
- Checkpoint evidence (2026-07-11): implementation checkpoint `24edd572`
  corrected the canonical desktop/config Qdrant sibling root, aligned six
  architecture contracts with the governed evidence lifecycle, and added
  structured semantic/tree-topology guards. Fresh verification passed 37
  focused contract tests, 42 lifecycle/retrieval witnesses, the full
  documentation authority/current-state/drift chain, and independent review.
  Evidence: `docs/diagnostics/R10_ARCHITECTURE_CONTRACT_CHECKPOINT_2026-07-11.md`.

### R-11 — Remove Control Agent authority contradictions

- Priority: P1
- Status: VERIFIED
- Finding: active docs mix observer-only operation, bounded healing, autonomous
  mutation, and disabled defaults.
- Repair: remove native confirmation bypasses; bind every approval to operation
  and exact scope; make token persistence atomic; append durable generic audit
  records for decisions/execution; keep the governor MCP preflight-only and
  non-executing; separate dormant capability from production default.
- Completion gate: docs, contracts, configuration, scope-bound token tests,
  audit tests, and disabled-by-default tests name one authority model.
- Public impact: RELEASE_REQUIRED
- Original audit evidence (2026-07-10): the local MiniAgent contract marked
  `run_ingestion` and `file_delete` as confirmation-required, but the in-process
  native bypass returns them as allowed without the contract's HITL exchange
  (`file_delete` checks break-glass only). Scope equality is enforced only for
  promotion tokens, and native result envelopes are returned without a generic
  durable audit append. The contemporaneous claim that token-store writes were
  not atomic was superseded by the completed R-02 checkpoint; R-11 re-audited
  and preserved that authority rather than reimplementing it.
- Checkpoint evidence (2026-07-11): `d2e8f72a` removed native confirmation
  bypasses and bound all seven confirmation-required operations to exact full
  argument scope; `8f0b424d` added locked, redacted, durable generic decision
  and execution audit records with fail-closed decision auditing; `2afa9d69`
  made Control Agent activation exact and disabled by default while requiring
  activation, auto-healing, and non-dry-run state for configuration mutation.
  The live `goodq_governor` MCP remained preflight-only with exactly two
  non-executing tools. Fresh committed-HEAD verification passed 229 focused
  tests, compilation, documentation authority/drift, banned-token,
  dependency-drift, staged-diff, and independent review gates. Evidence:
  `docs/diagnostics/R11_CONTROL_AUTHORITY_CHECKPOINT_2026-07-11.md`.

### R-11-F1 — Make MiniAgent handler outcomes truthful

- Priority: P0
- Status: VERIFIED
- Finding: unchanged base behavior can preserve wrapper success and return code
  zero when a native MiniAgent handler explicitly returns `status=error`.
- Repair: map explicit handler error to a generic outward error envelope and
  nonzero return code while preserving handler output, nonmutation truth, and a
  matching durable execution audit. Keep existing `blocked` semantics intact.
- Completion gate: focused tests prove reasoned and reasonless handler errors
  agree across envelope, return code, side-effect report, and execution audit;
  the full MiniAgent and governed-ingest regression set remains green.
- Public impact: RELEASE_REQUIRED
- Boundary: the verified R-11 confirmation, token, Control Agent, and governor
  checkpoint remains valid. This follow-up does not reopen those mechanisms.
- Checkpoint evidence (2026-07-11): `9661d8db` maps explicit handler error to
  outward error/return code one, preserves generic outward text and
  nonmutation, and aligns the durable execution audit. Mission lint now
  recognizes registered roadmap sub-items. Fresh verification passed 204
  focused tests plus compilation, documentation/static gates, and independent
  specification and security review. Evidence:
  `docs/diagnostics/R11_F1_HANDLER_OUTCOME_TRUTH_CHECKPOINT_2026-07-11.md`.

### R-12 — Reconcile workstation doctrine and follower validation

- Priority: P1
- Status: OPEN
- Finding: shared guidance contains obsolete installer versions, ports, host
  names, model concurrency assumptions, and destructive laptop instructions.
- Repair: update existing _AGENT authority in place, archive obsolete workflows,
  and validate the portable follower path when the laptop is available.
- Completion gate: _AGENT verification passes, active docs contain one port and
  installer contract, and a follower witness proves portability.
- Public impact: NONE

### R-13 — Finish documentation authority consolidation

- Priority: P1
- Status: VERIFIED
- Finding: resolved and historical plans remain active; some docs lack badges,
  contain fixed roots, or point to nonexistent archive locations.
- Repair: use this roadmap as the single global register, archive superseded
  plans, update references, and retain one active authority per purpose.
- Completion gate: link, badge, drift, and authority-map checks pass; searches
  find no superseded active plan path.
- Public impact: RELEASE_REQUIRED
- Prerequisite evidence (2026-07-11): the foundational project orientation and
  instruction chain are already checkpointed. R-13 must not recreate them; it
  owns remaining archive moves, indexes, active-document classification,
  `PROJECT.md`, naming, and semantic drift.
- Checkpoint evidence (2026-07-11): implementation checkpoint `3a78e3c0`
  archived the eight R-17-owned surfaces plus one duplicate witness, classified
  every active root/docs Markdown authority surface, explicitly exempted four
  schema-governed `SKILL.md` files, replaced competing status/mission
  narratives, and generated both repository indexes from tracked-file scope.
  Focused tests report 11 passed; active metadata, links, mission, epoch,
  current-state, index, path-drift, banned-token, and dependency gates pass.
  Evidence: `docs/diagnostics/R13_DOCUMENTATION_AUTHORITY_CHECKPOINT_2026-07-11.md`.
- Closure evidence (2026-07-11): architecture checkpoint `24edd572` resolved the
  Qdrant storage-root conflict and added governed-materialization semantic
  guards. The full R-13 verifier and every supporting drift/current-state gate
  now pass; the contradiction was corrected, not allowlisted.

### R-14 — Make WSL and model status probing passive and accurate

- Priority: P1
- Status: OPEN
- Finding: a status request can start WSL work, time out as frozen, and return
  incorrectly decoded output.
- Repair: separate passive status from explicit deep probes and decode command
  output consistently.
- Completion gate: stopped, running, unavailable, timeout, and malformed-output
  tests pass without side effects; live status matches wsl -l -v.
- Public impact: RELEASE_REQUIRED
- Route-effect evidence (2026-07-12): five mounted operations across four
  nominal status paths remain `process_execution`, including both `GET` and
  `HEAD` on `/api/status`. R-05 records and guards their current effect; only
  R-14 may reclassify them after its no-side-effect witnesses pass. Evidence:
  `docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_AUDIT_2026-07-12.md`.

### R-15 — Triage critical exception suppression

- Priority: P2
- Status: OPEN
- Finding: active code contains bare or silent handlers beyond reviewed
  allowlisted critical cases.
- Repair: classify by criticality and repair one seam at a time with contextual
  logging and preserved fallback behavior.
- Completion gate: the regression guard covers the reviewed critical surface
  and every changed fallback has a focused behavior test.
- Public impact: RELEASE_REQUIRED
- Recorded diagnostic-privacy evidence (2026-07-13): ingestion and vector
  warning branches can include full local `source_path`/`index_path` values or
  raw exception text. These are explicit write-path diagnostics, not R-05-F1
  hidden mutations. Repair them as bounded logging seams while preserving
  fallback behavior; producer retention/migration remains R-23.
- Commit-event observability checkpoint (2026-08-01): SQLite and optional JSONL
  mirror failures now emit contextual warnings while preserving non-blocking
  ingestion. Focused failure-path tests prove both write failures are visible.

### R-16 — Reconcile private development and public release Git state

- Priority: P1
- Status: IN_PROGRESS
- Finding: private-dev/public-main ancestry is correct, but doctrine excludes
  legitimate infrastructure branches and the separate public checkout uses
  stale cached state.
- Repair: update Git governance, compare the public checkout's local commit with
  current history, then replace or fast-forward it from verified private
  authority.
- Completion gate: private dev contains every public functional change; public
  main is a sanitized descendant of the approved private release; both
  checkouts verify cleanly.
- Public impact: RELEASE_REQUIRED
- Evidence (2026-07-10): private `AGENTS.md` now defines private development as
  authoritative, public release as downstream-only, and `gh-pages`, temporary
  Dependabot branches, and short-lived local feature branches as non-product
  branches. Live remote inspection confirmed private `dev` and public `main`
  remain the only product branches and public `main` is an ancestor of private
  `dev`. Public-checkout reconciliation and release verification remain open;
  no public branch or checkout state was changed during this repair.
- Local-hook finding (2026-07-11): a private post-commit hook automatically
  copied/staged `AGENTS.md` in the public checkout during the foundational-docs
  checkpoint. The working-tree side effect was immediately reversed without
  changing public history. R-16 must remove or replace this implicit release
  authority before any approved public reconciliation.

### R-17 — Extract the frozen mixed main checkout

- Priority: P0
- Status: IN_PROGRESS
- Finding: the main checkout contains 85 mixed tracked and untracked entries
  spanning already-checkpointed R-01 through R-03 work, R-04 and R-06 repairs,
  foundational documentation, identity prototypes, Command Center assets,
  generated test residue, and a discarded API-launch prototype.
- Repair: classify every entry by owner, reconstruct each wanted family in its
  own worktree/checkpoint, and leave the original tree frozen until an evidence
  comparison proves no unique wanted content remains.
- Completion gate: every wanted family has an isolated checkpoint or an
  explicit later repair owner; generated/discarded entries are classified; the
  mixed tree is retired only through separate approval.
- Evidence (2026-07-11): R-02, R-03, R-04, and R-06 are checkpointed. Read-only
  inventory found no dirty Qori work,
  separated identity evidence from unsafe R-08 authority prototypes, and marked
  the untracked API restart script as incompatible with R-19.
- Foundational documentation evidence (2026-07-11): the timeless project
  orientation, instruction-first-read alignment, authority-map classification,
  and archived completed plan are checkpointed at `ac4f58f6`. Evidence:
  `docs/diagnostics/FOUNDATIONAL_ORIENTATION_CHECKPOINT_2026-07-11.md`.
- Foundational documentation refinement (2026-07-12): the orientation now
  explains why the repair roadmap exists and requires freshness evidence before
  Context7's downstream public library can support a GoodQ claim. The
  authenticated Context7 metadata probe reported `/goodq02/goodq4all` on public
  `main` as `finalized`, with `lastUpdateDate=2026-07-01T15:47:03.914Z`; private
  code and contracts remain authoritative for later work.
- Frozen-tree inventory evidence (2026-07-11): all 96 expanded status entries
  are classified with zero unknown paths; every wanted family has either an
  isolated checkpoint or an explicit later repair owner. The original checkout
  remains frozen because extraction, evidence comparison, and separate
  retirement approval are still outstanding. Evidence:
  `docs/diagnostics/R17_FROZEN_MAIN_INVENTORY_2026-07-11.md`.

### R-18 — Isolate validator tests and generated reports

- Priority: P0
- Status: VERIFIED
- Finding: validator tests can overwrite operator reports, legacy tests depend
  on a machine-local skill copy, stale lifecycle `xfail` cases remain, and one
  ingestion test resolves an obsolete live epoch.
- Repair: add an explicit report-output directory, redirect tests to temporary
  roots, add a no-operator-report-mutation regression guard, convert lifecycle
  `xfail` cases using existing fixtures, and add a live/golden profile where
  required-service absence fails rather than skips.
- Completion gate: hermetic tests leave operator evidence unchanged and the
  live/golden profile fails truthfully when dependencies are missing.
- Checkpoint evidence (2026-07-11): commit `892976f7` adds explicit report
  ownership, stale-report rejection, exact-scope lifecycle tests, central
  isolated collection, a pinned golden manifest, immutable live-ledger reads,
  and caller-independent OS-temp evidence runners. The guarded validator suite
  passed 122 tests with operator reports unchanged and no residual worktree
  artifacts. R-02/R-06 non-regression packs passed 137, 42, and 29 tests. Four
  read-only July runtime witnesses passed; with the API intentionally stopped,
  the complete golden runner failed only the required API witness instead of
  skipping it. The extracted `absolute_timestamps` correction is explicitly
  owned and verified as a frozen-main validator sub-seam. Evidence:
  `docs/diagnostics/R18_VALIDATOR_EVIDENCE_ISOLATION_2026-07-11.md`.

### R-18-F1 — Keep synthetic API authority tests truthful

- Priority: P0
- Status: VERIFIED
- Finding: two API authority suites maintained duplicated synthetic router
  inventories, so five tests failed during `api.main` import after `identity`
  and `summary` were mounted. Their behavioral assertions never ran.
- Repair: use one explicit test-only router inventory, compare it with the real
  `api.main` import before module execution, and prove the harness names a
  deliberately removed router.
- Completion gate: the oracle catches the seeded missing-router defect, both
  suites execute their original assertions, and no production file changes.
- Checkpoint evidence (2026-07-12): commit `c136861f` replaced the duplicated
  stub lists with one AST-checked harness. The seeded oracle named the missing
  `identity` router, the formerly broken pair passed 13 tests, all three files
  compiled, diff checks passed, and independent review approved the seam.
  Evidence:
  `docs/diagnostics/R18_F1_API_TEST_HARNESS_CHECKPOINT_2026-07-12.md`.

### R-18-F2 — Repair dynamic search-route test loading

- Priority: P1
- Status: OPEN
- Finding: three search-route unit modules execute `api.routes.search` through a
  dynamic loader without registering the module in `sys.modules`; dataclass
  processing therefore fails during collection before behavioral assertions
  run.
- Repair: correct the shared test-loader pattern only; do not change the
  production dataclass to accommodate a broken harness.
- Completion gate: audio, enrichment, and sentiment search-route modules collect
  and execute their original assertions, and a seeded loader regression proves
  module registration occurs before execution.

### R-18-F3 — Restore module identity after import-purity tests

- Priority: P1
- Status: OPEN
- Finding: the external-pin import-purity test removes and reimports
  `cli.clean_memory_external_pin` without restoring the original module object.
  A later protected-manifest exact-type check can therefore bind a replacement
  `ExternalPinEvidence` class while its test fixture retains the original,
  making file order change otherwise valid test results.
- Repair: restore the exact prior `sys.modules` entry after the import-purity
  assertion and add a seeded cross-module exact-type regression. Do not weaken
  production exact-type checks or change either production reader to
  accommodate test-owned module drift.
- Completion gate: both files pass alone and in both combined orders, the
  seeded regression fails when restoration is removed, and no production file
  changes.

### R-19 — Establish one canonical API and Watchdog supervisor

- Priority: P0
- Status: OPEN
- Repair: use `goodq_core`, interpreter bindings, `python -m api.server`, fixed
  loopback port 30000, and `cli.watchdog`; fail visibly on collisions; add
  sustained `/api/status` health, child ownership, restart/backoff, Watchdog
  liveness, and structured logs; install no dependencies during launch.
- Completion gate: cold start, port collision, child crash, backoff, and restart
  acceptance tests pass before startup shortcuts are replaced.
- Environment-drift evidence (2026-07-13): live `goodq_core` reports Sentence
  Transformers `5.6.0` and Transformers `5.12.1`, while both baseline locks pin
  `5.3.0` and `5.4.0`; Hugging Face Hub matches at `1.8.0`. Reconcile the active
  environment to an approved lock in a rollback environment before canonical
  supervisor acceptance. Do not install, downgrade, or rebuild during R-05-F1.

### R-20 — Enforce LAN, port, and secret boundaries

- Priority: P0
- Status: OPEN
- Repair: keep Qdrant, OpenViking, Ollama, and model internals loopback-only;
  permit an explicitly LAN-bound GoodQ API only through its server-side
  authenticated read-only boundary, with the canonical desktop remaining the
  sole writer; disable or rebind default Ollama 11434; remove broad inbound
  firewall authority; reserve 8900 for one remote Nanobot tunnel; audit
  redaction, rate limits, and retention for the 8901 monitor.
- Completion gate: port/listener and firewall witnesses prove raw services
  other than the governed GoodQ API are unreachable from LAN devices;
  unauthenticated LAN reads and every LAN mutation/control/trigger are denied;
  authenticated LAN reads and ordinary loopback writes pass; key-name parity
  passes; focused API/UI oracles prove mounted household-facing projections
  expose logical references rather than local paths. Destructive plaintext
  secret-backup removal remains a separate approval gate.
- Approved LAN API direction (2026-07-31): GOOD-CUBE desktop is canonical and
  the sole writer. Laptops, phones, and Pi nodes may use the GoodQ API and its
  mounted UI from the LAN only with authenticated read-only access. CORS and
  client UI state are not authorization; the common raw-peer route-effect
  boundary must enforce this policy before request bodies or downstream code.
- LAN API hardening checkpoint (2026-07-31): the legacy enabled inbound rule
  with Any profile, address, port, program, and edge traversal was proven to
  defeat the two exact client rules and was disabled. Both approved laptops now
  use separately source-bound, Private-profile rules on the proven ordinary
  Ethernet listener; the alternate 2.5G path was observed matching only a
  Public/Any-profile diagnostic rule despite the adapter reporting Private, so
  that path remains closed. Server authentication misconfiguration now returns
  `503` with a non-sensitive operator error, denied reads and operations are
  logged, wildcard binds are rejected, and exact non-loopback port collisions
  fail rather than falling back. Firewall rules are persistent, while listener
  restart after reboot remains a manual verification gate.
- LAN Retro UI status checkpoint (2026-07-31): authenticated desktop and phone
  Explorer requests reached the mounted UI, passive video/timeline projections,
  and media successfully. `/api/status` remains process-executing because it
  invokes local OS and WSL probes, so remote access stays denied. The Retro UI
  now surfaces that expected LAN read-only state and stops the denied polling
  loop instead of producing repeated opaque `403` traffic.
- Retro scene-context rendering checkpoint (2026-08-01): persisted epistemic
  evidence and arbitration values now render through native DOM text nodes,
  rather than HTML parsing. A focused static regression oracle covers both
  cognitive list paths while preserving their labels and styling.
- Daily Hermes sub-gate: start/check OpenViking by default, support explicit
  `-SkipMemory` and `-RequireMemory`, check GoodQ without starting ingestion,
  and verify model, memory, MCP, and security canary state before Desktop opens.
- Mounted output-redaction evidence (2026-07-13): `/api/read/envelope` returns
  precomputed envelopes verbatim, and passive scene/timeline projections can
  pass retained `clap_meta.index_path` through while search already redacts
  local paths. Before any household gateway exposure, add focused API/UI
  logical-reference and local-path redaction oracles. The dormant generic
  epistemic `index_path` fallback belongs to the same output-trust contract.

### R-21 — Converge portable agent contracts

- Priority: P1
- Status: OPEN
- Repair: with the R-02 authority prerequisite now satisfied, reconcile the embedded contract with
  `goodq_agent`, preserve exact `video_hash`/`epoch_id` promotion scope and
  gated reconciliation, rebuild one unambiguous portable package, verify hashes,
  and update the Hermes adapter.
- Completion gate: desktop verification passes before laptop portability or any
  remote `goodq_agent` update is approved.

### R-22 — Make Hermes and OpenViking maintainable

- Priority: P1
- Status: OPEN
- Repair: split local Hermes changes into MCP startup, memory gate, Raft
  quieting, and voice/delegation patch families; checkpoint focused tests; record
  reproducible OpenViking pins and compatibility patches; rebuild dependencies
  only in a rollback environment and remediate verified OSV findings.
- Completion gate: CLI/Desktop, MCP, governor, voice, memory, and canary gates
  pass without broad restore or active-runtime upgrade.

### R-23 — Govern corpus and storage retention

- Priority: P1
- Status: OPEN
- Repair: make dataset downloads default-deny unless the corpus ledger permits
  them; gate privacy/license-sensitive corpora; inventory incomplete downloads;
  build a retention manifest across media, models, datasets, vector residue,
  logs, backups, and archives; reconcile Qdrant service logs and historical
  storage only after authoritative copies are identified.
- Completion gate: manifests, ownership, rollback, and explicit approval exist
  before any bulk deletion, deduplication, or movement; operator-query logging
  launch/sink behavior and retained path-bearing stores are classified, their
  producer/reference and retention policies are explicit, and every historical
  migration has a documented execute-or-retain decision.
- Recorded retention/privacy evidence (2026-07-13): standalone analytics and
  natural-language query helpers can emit raw questions or derived personal
  intent through inherited INFO logging; ingestion commit events, JSONL mirrors,
  step logs, and scene artifacts can retain full internal paths. First prove
  active launch/sink/retention behavior, define logical-reference policy and
  authoritative copies, then repair producers or migrate history only under the
  existing manifest/rollback/approval gate.

### R-24 — Establish an isolated Golden Witness

- Priority: P1
- Status: VERIFIED
- Repair: provide a read-only preflight and a separately approval-gated,
  one-scene witness through the canonical ingestion interface. The witness must
  keep every generated artifact below one new root, record exact input identity
  and tool/device facts, and disable canonical-memory promotion.
- Completion gate: preflight emits a receipt without creating a witness root;
  a later explicit operator approval is required before one isolated execution;
  the resulting transcript, multimodal artifacts, and factual scene summary are
  reviewed before any follow-on decision.
- Checkpoint evidence (2026-08-01): the initial preflight contract rejects a
  model cache under the proposed artifact root, records supplied-input hashing
  and stream metadata, resolves required tool bindings, and leaves the root
  absent. The first local media preflight was read-only and did not authorize or
  start an ingestion run. The canonical runner now accepts an explicit witness
  snapshot only when every mutable runtime path remains below the declared
  witness root, models remain external, promotion is disabled, and Qdrant is
  either a separate loopback endpoint or the established local endpoint with
  four fresh witness-named collections.
- TurboQuant checkpoint (2026-08-01): the isolated one-scene candidate
  completed with all four supported sidecar dimensions and an aggregate-only
  A/B receipt. The first receipt exposed invalid FAISS `-1` filler IDs in the
  baseline oracle; the corrected valid-hit receipt reached 7/9 exact queries
  with zero fallbacks, but active SQLite sidecar scanning was slower than FAISS
  HNSW and the text index has one FAISS ID without a matching SQLite sidecar.
  Therefore full-movie re-ingestion is blocked. Next gate: separately design a
  complete sidecar/index coverage invariant and a persistent compact candidate
  index or cache that can be compared honestly to FAISS HNSW; do not run a
  second scene or enable active TurboQuant until that gate passes.
- Strict audio and containment checkpoint (2026-08-02): a fresh scene-zero
  witness completed with WSL audio, transcript, visual evidence, CLAP audio
  embedding, isolated UCF frames, FAISS, and four candidate Qdrant collections.
  The first completed receipt exposed a Phase 6 configuration propagation gap:
  scene-level CLIP and DINO parity writes inherited shared default collection
  names despite the sealed candidate collection map. The snapshot now pins the
  Phase 6 names to the candidate map; focused isolation tests and a second
  fresh scene proved the shared default counts unchanged while the candidate
  received 2 CLIP, 2 DINO, 3 text, and 1 audio vector. TurboQuant stayed off.
  The initial leaked default points and failed launch receipt remain preserved
  evidence; they were not cleaned.
- Verified witness evidence (2026-08-02): the operator semantically accepted
  two independently sourced, fresh isolated scene-zero receipts. The second
  witness exercised continuous dialogue across split-screen video calls,
  multiple locations, phone handoffs, and an in-person convergence; it recorded
  three speakers, a usable transcript, 79 isolated UCF frames, and successful
  Phase 5 and Phase 6 completion. It emitted zero legacy scene-metadata
  warnings after the isolation-startup repair, created only fresh candidate
  collections (2 CLIP, 2 DINO, 3 text, 1 audio), and left shared default
  collection counts unchanged. No witness was promoted. This closes R-24's
  preflight, containment, multimodal execution, and human-semantic-review gate;
  future witness runs remain separately approved and isolated.

### R-25 — Private integrated verification gate

- Priority: P0
- Status: VERIFIED
- Repair: run focused seam tests first, then the approved private integrated
  suite covering configuration, privacy, fixed roots, secrets, documentation,
  cold start, LAN boundaries, memory, identity, retrieval, and browser behavior.
- Completion gate: private `dev` is a clean descendant containing every approved
  repair. Public release remains R-16 and a separate approval gate.
- Evidence (2026-07-15): Resolved the five R05/R07 gate blockers, including trailing whitespaces, agent file index drift, UCF concurrency races, dynamic route sys.modules registrations, and console UI theme witness consistency. Verified that the integrated gate test suite is completely green with 4011 passed, 9 skipped, and 0 failed.

## Carried-Forward Verification Items

These items preserve unfinished intent from the plans this roadmap replaces.

### V-01 — Portable follower witness

- Status: VERIFIED
- Verified install evidence (2026-08-04): the offline baseline artifact built
  from private `dev` commit `d83ccb43` passed exact version, commit, asset-set,
  and SHA-256 receipt checks; GR-16 received the four-file set with matching
  transfer hashes, a clean install exited zero, and its installed offline suite
  and restore smoke passed. The package includes pinned LGPL FFmpeg/FFprobe and
  visible first-use model-fetch status.
- Active repair: GR-16 proved that its OpenSSH server ends ordinary detached
  child processes when the client disconnects. The source launcher now uses a
  temporary Windows Task Scheduler task; rebuild and redeploy that repair before
  claiming the remote-witness runner is validated.
- Verified runtime evidence (2026-08-04): the rebuilt `75b5b8f9` artifact was
  clean-installed on GR-16 after a four-of-four hash-verified transfer. Its
  offline suite and Qdrant restore smoke passed, and the scheduler-backed
  scene-zero witness reached `runner_finished` with exit code zero. The sealed
  receipt proves CPU policy, isolation, and promotion disabled.
- Active repair (2026-08-04): the follower receipt exposed two baseline
  packaging seams before a full scene witness could be claimed: CLAP imports
  require `librosa` and `soundfile`, and the remote witness runner must own an
  isolated loopback Qdrant lifecycle. Private `dev` now pins the audio imports
  in the baseline lock and manifest, stages their CPython 3.10 transitive
  closure, and starts/stops the bundled Qdrant under the witness root. The
  stager verifies all artifact hashes and the exact lock closure before build.
- Operator containment (2026-08-04): the desktop offline-build launcher now
  uses an elevation-gated, uniquely named outbound firewall rule in the active
  policy store. It records the pre/post adapter snapshot, removes only that
  rule in `finally`, and probes restored connectivity. Offline preflight uses
  a bounded public TCP egress probe rather than a cacheable DNS lookup. It
  never disables or re-enables Windows network adapters.
- GR-16 rerun evidence (2026-08-05): the current release completed its clean
  install, installed offline suite, and disposable Qdrant restore smoke. A
  fresh, non-promoting scene-zero witness sealed its input, CPU policy, bundled
  FFmpeg, and isolated paths, then stopped before ingestion because the
  connect-based loopback probe timed out even though no Qdrant listener owned
  the port. Private `dev` commit `9daedd1f` replaces that probe with the
  capability the runner actually requires: an exclusive loopback bind, with
  focused witness and installer-contract tests passing. Rebuild and redeploy
  this repair before rerunning the sealed scene from a new root.
- Verified completion (2026-08-06): the managed offline build from private
  `dev` commit `435ee473` passed its exact artifact receipt and restored host
  connectivity after its temporary outbound-containment rule was removed. A
  four-of-four hash-verified transfer was clean-installed on GR-16 after the
  previous program and data roots were removed. The installed offline suite and
  disposable Qdrant restore smoke passed. A new non-promoting scene-zero
  witness then reached `runner_finished` with exit code zero. Its terminal
  audio ledger is `ok` using `hybrid_whisper` on CPU (12 chunks, 48 segments,
  and 1,868 transcript characters); CLAP, Qdrant, FAISS, and SQLite commits
  all completed. The sealed scene manifest reports Windows audio with no
  downgrade and Phase 6 complete. Optional WSL audio and local LLM serving
  remain explicitly outside this BASELINE acceptance scope.
- Active follower deployment (2026-08-06): the managed offline build from
  private `dev` commit `6ef7a94e` passed its four-file receipt and temporary
  outbound-containment cleanup. Its immediate restoration probe was delayed,
  but the exact firewall rule was absent, adapter state was unchanged, and a
  fresh public TCP probe succeeded. GS-32 received a four-of-four
  hash-verified transfer under a new validation root. Before its clean
  replacement, an obsolete silent installer and its wheel-install Python child
  were found holding the prior program tree; their exact process evidence was
  preserved, the obsolete tree was stopped under the approved replacement
  scope, and only the GoodQ program and data roots were removed. The new
  installer then exited zero. Do not claim GS-32 acceptance until its installed
  offline suite, restore smoke, and fresh bounded scene witness are recorded.
- Update handoff (2026-08-06): GS-32's installed offline suite and disposable
  Qdrant restore smoke both passed. The sealed scene-zero witness is active at
  `runner_started` under its fresh validation root, using the installed
  scheduler-backed runner and `--step-timeout 600`. Resume by reading its
  durable status/receipt first; do not relaunch, restage, or clean the witness
  root. Acceptance remains gated on `runner_finished` plus terminal audio
  ledger evidence.
- CPU fallback repair (2026-08-06): GS-32's witness reached `runner_finished`
  with an honest terminal audio failure after `audio_transcribe_local` exceeded
  the 600-second witness bound. This was not an installer drift: installed
  source/config hashes matched private `dev`, the cached medium model loaded in
  16.6 seconds, and direct one-thread CPU inference produced a transcript but
  took 137.0 seconds for ten seconds of audio. The same private-dev contract
  took 19.2 seconds. Private `dev` now retains `num_workers=1` for the Windows
  deadlock guard while using four bounded CTranslate2 CPU inference threads;
  the source benchmark completed the same input in 7.3 seconds. Rebuild from
  the verified private commit, then rerun only the existing GS-32 sealed
  scene-zero witness from a fresh validation root.
- Pause checkpoint (2026-08-06): private `dev` is pushed at `23735149` with
  the Windows CPU transcription repair and its focused regression coverage.
  The managed offline build passed from that exact commit with a four-asset
  receipt, temporary outbound containment removed, unchanged adapter state, and
  restored public connectivity. GOOD-CUBE now has hash-verified SSH aliases
  for GS-32 and GR-16; both followers expose authenticated Codex app-server
  support, share the synced agent-workflow workspace, and have the portable
  operational skills added without replacing any local skill or configuration.
  The only active release gate is to clean-replace GS-32 with this exact asset
  set under a fresh validation root, rerun its installed offline suite and
  restore smoke, then run one newly sealed scene-zero witness. Require a
  terminal transcript ledger and `runner_finished`; do not reuse the earlier
  timed-out witness root or promote any follower evidence.

### V-02 — Watchdog interruption witness

- Status: OPEN
- Completion: interrupt and resume a bounded temporary ingestion; prove
  checkpoint state, UCF scene counts, recovery, and final file movement agree.

### V-03 — Hybrid retrieval witness

- Status: OPEN
- Current evidence: reciprocal-rank fusion and promoted-status filters exist,
  making the former not-implemented statement obsolete.
- Completion: a temporary promoted epoch proves text, visual, audio, Qdrant,
  FAISS, and SQLite FTS blending while excluding unpromoted evidence.

### V-04 — Higher-order memory capabilities

- Status: DEFERRED
- Preserved themes: self-auditing cognition, memory arbitration, and
  episode/season consolidation.
- Re-entry gate: R-01 through R-14 are VERIFIED and a new evidence-backed design
  is approved.

### V-05 — Public first-success and contributor polish

- Status: DEFERRED
- Preserved themes: licensed synthetic fixture, honest first-run loop,
  evidence-backed performance notes, contributor templates, and public examples.
- Re-entry gate: private release and sanitization gates pass.

## Superseded Active Plans

The following documents are replaced by this roadmap and move to docs/archive/
after references are updated:

| Former active document | Disposition |
|---|---|
| docs/agent/UCF_REMAINING_WORK.md | Archive; remaining intent is in R-01 through R-03 and V-01 through V-03 |
| docs/agent/UCF_SEARCH_LOOP_PLAN.md | Archive; missing-materialization claim is obsolete |
| docs/agent/UCF_QDRANT_STATUS_BACKFILL_PLAN.md | Archive; already resolved |
| docs/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md | Archive; future themes are V-04 |
| docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md | Archive; assumptions are not current runtime authority |
| docs/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md | Archive; historical proposal is not current authority |

## Execution Governance

- Stability and authority come first.
- One mutating seam may be active at a time. Parallel agents are read-only.
- Every item requires a fresh audit, no-repeat check, isolated scope/worktree,
  targeted verification, private checkpoint, and roadmap update.
- Preserve the mixed main checkout until every wanted change is extracted.
  Never broad-stage, reset, restore, or clean it.
- `PROJECT.md` holds only the current bounded mission. Current-state documents
  report evidence and do not become future-work backlogs.

## Do-Not-Repeat Register

Do not repeat the completed July home-memory ingestion or promotion; R-01,
R-02, R-03, R-05-F1, or R-06 implementation; Command Center milestones M1 through M5;
project orientation/instruction alignment; Hermes/Ollama/Gemma setup; the GoodQ
RAG bridge, governor MCP, daily launcher, or OpenViking learning gate;
Webwright/Playwright installation; AutoResearch setup, baseline, or recorded
experiments; Codex sandbox/MCP/SSH setup; Google Drive mirror cleanup; existing
audio/text vector-registry work; or historical UCF event reconstruction.

The mixed main checkout is evidence, not a cleanup target. Re-audit before any
new work and compare against private checkpoints so completed work is not
recreated under a new name.

## Deferred Lanes

- Laptop follower witness: after an approved portable package or installer.
- Higher-order memory and self-auditing cognition: after R-01 through R-14.
- Public first-success/contributor polish: after private release gates.
- AutoResearch overnight autonomy: only with GPU budget, iteration cap, stop
  policy, ledger, and morning report.
- Webwright wrapper: only when reproducible browser evidence is required.
- MarkItDown, LiteParse, Understand-Anything, and nanochat: only for a proven
  GoodQ gap.
- Home Assistant: only through the future authenticated household gateway after
  token/environment mapping is corrected.
- Nanobot: remote/fallback lane; do not recreate the completed local setup or
  collide with reserved port 8900.
- Qori/pet work: outside the core repair order until explicitly resumed.

## Acceptance Rules

- A plan, unrelated passing suite, or absent visible failure never closes an
  item. Closure requires the stated focused evidence and a checkpoint.
- Live state is re-probed before execution.
- Destructive operations, public release, large downloads, re-ingestion,
  dependency replacement, and LAN exposure require explicit approval.
- If evidence contradicts this register, stop and update the register before
  implementation. The 2026-07-11 R-04 reopening is the first recorded use of
  this rule.

## Repair Order

1. Recover trustworthy history: completed R-02/R-03 checkpoints, R-17 mixed
   tree extraction, then a separate foundational-documentation checkpoint.
2. Restore truthful evidence: completed R-18, R-09, R-10, and R-13 checkpoints.
3. Establish one control authority: verified R-11, R-11-F1, R-05, and R-05-F1;
   next replace the unsafe clean-memory workflow under R-07.
4. Stabilize runtime and network ownership: R-19, R-14, R-20, and the daily
   Hermes startup contract.
5. Complete identity safely: R-08, then human-curated Phase 5A readiness.
6. Align portable/local agents: R-21 and R-22.
7. Govern data and storage through R-23.
8. Run V-02, V-03, incremental R-15, then R-25.
9. Complete R-16 only after private integrated verification and sanitization.
10. Execute deferred lanes only after their re-entry gates are satisfied.

## Release Gate

The private-to-public flow is one-way:

    private dev
      -> focused repair verification
      -> integrated private verification
      -> privacy and portability scan
      -> public main update
      -> independent public checkout verification

The public gate rejects secrets, personal data, literal workstation paths,
private media references, internal runtime evidence, and public-only functional
changes.

Full ingestion, destructive cleanup, installer rebuild, branch deletion,
tagging, and public push remain separate approval gates.

## Change Log

- 2026-07-16: Checkpointed the R-08 identity GET non-creating routes seam after verifying all 4 routes do not mutatively create folders on disk when files are absent. Isolated the test paths with an autouse fixture in conftest.py, and added focused unit tests in tests/unit/test_identity_routes.py. All 4 focused tests passed, and 3549 tests in the full unit test suite passed. Evidence: docs/diagnostics/R08_IDENTITY_GET_NONCREATING_CHECKPOINT_2026-07-16.md.

- 2026-07-16: Checkpointed the fail-closed R-07 Qdrant observer seam at `ab3622c9` after 7 focused tests, 557 clean-memory tests, the full 4018-test private gate, compilation, import purity, and doc linting. Advanced next to R-08 identity route reconciliation.

- 2026-07-16: Completed the read-only R-07 Qdrant observation boundary audit checkpoint and committed it in docs commit `docs: R-07 Qdrant observation boundary audit checkpoint` to verify endpoint, transport, and fail-closed collection patterns.

- 2026-07-15: Checkpointed the private R-07 authenticated protected-membership
  composition authority at `d20a74ba` after 265 focused and 1,941 zero-drop
  tests, the 375-test shared authority gate, static/documentation gates, and two
  clean independent exact-hash reviews. Advanced only to a read-only Qdrant-
  observation ownership/contract audit; planning, approval, and cleanup remain
- 2026-07-15: Resolved the five R05/R07 gate blockers in the isolated repair worktree, including removing trailing whitespaces, updating doc index references, fixing UCF promotion concurrent barrier races, cleaning dynamic route sys.modules registrations, and updating visual theme switches for console UI tests. Verified that the integrated gate test suite passes cleanly with 4011 passed, 9 skipped, and 0 failed.

- 2026-07-15: Selected the exact private R-07 authenticated protected-
  membership composition seam after the protected observer checkpoint. Frozen
  the existing source/test allowlist, Windows-only preflight, four composition-
  owned locator fences, immediate direct-output authentication, digest chain,
  lexical/physical separation, private error contract, upstream-drift
  precedence, and RED matrix; later planning, approval, and cleanup remain
  closed.

- 2026-07-15: Checkpointed the R-07 protected-boundary observer at `9e225655`
  plus immutability fix `636f4bfd` after 184 focused and 1,807 expanded tests
  and clean independent reviews. Recorded the unrelated external-pin module-
  reload test isolation defect as R-18-F3, then advanced only to a read-only
  authenticated-composition re-audit; Qdrant, planning, approval, and cleanup
  remain closed.

- 2026-07-14: Selected one shared R-07 Windows ProgramData locator authority
  after three ownership/lifecycle/parity audits. Advanced only to the exact
  four-file TDD extraction/adaptation seam; later composition and mutation
  authorities remain closed.

- 2026-07-14: Checkpointed the authenticated R-07 protected-manifest reader at
  `66ee4f47` after 148 focused, 1,422 frozen-authority, and 1,570 combined tests
  plus three clean independent reviews. Advanced only to a read-only
  ProgramData locator/recheck ownership audit; later composition and mutation
  authorities remain closed.

- 2026-07-14: Selected the exact R-07 protected-manifest reader contract after
  three independent audits reconciled API, lifecycle, error, evidence, digest,
  route-cardinality, and no-repeat boundaries. Advanced only to the two-file
  reader TDD seam; authenticated composition and later authorities remain
  closed.

- 2026-07-14: Checkpointed the R-07 shared Windows reader-identity policy at
  `02530486` after the 1,422-test authority union and independent
  `APPROVED`/`READY` reviews. Advanced only to the protected-manifest reader
  public-contract and input/error-fence decision; reader code remains closed.

- 2026-07-14: Selected the exact R-07 import-pure Windows reader-identity
  policy seam after three ownership audits and two final API/timing reviews.
  Advanced only to its four-file TDD extraction/adaptation checkpoint; the
  protected-manifest reader remains closed.

- 2026-07-14: Checkpointed the projection-neutral R-07 Windows security
  mechanics at `0827193a` after 1,357 clean-memory authority tests and two
  independent `READY` reviews. Advanced only to a read-only reassessment of the
  frozen reader-identity v1 policy seam; the protected-manifest reader remains
  closed.

- 2026-07-14: Selected the exact R-07 four-file projection-neutral Windows
  security-mechanics extraction after three independent audits reconciled the
  token, descriptor-allocation, mapping, and bounded-access lifetime. Advanced
  only to its RED/GREEN parity checkpoint; the held-handle backend, frozen v1
  identity policy, and protected-manifest reader remain closed.

- 2026-07-14: Checkpointed R-07 label-aware held-handle descriptor transport at
  `6b40d8e8` with exact `0x7`/`0x17` parity and 644 focused regressions. Advanced
  only to a read-only security-mechanics ownership/parity audit.

- 2026-07-14: Selected the exact R-07 protected-manifest security policy after
  adversarial review narrowed filtered-descriptor authority, positive-access
  proof, and publication provenance. Advanced only to the two-file opt-in
  `security_read_label` transport seam; the physical reader remains closed.

- 2026-07-14: Checkpointed the exact R-07 canonical protected-manifest
  validator extraction at `41e56c74` and advanced only to a decision-only,
  read-only manifest security-policy audit. Shared security mechanics and the
  physical reader remain closed.

- 2026-07-14: Selected the exact R-07 four-file canonical protected-manifest
  validator extraction after the completed membership no-repeat rule resolved
  the generic-helper boundary. Advanced only to its TDD parity checkpoint; the
  physical reader and manifest security policy remain closed.

- 2026-07-14: Checkpointed the exact R-07 held-handle bounded-read capacity
  extension at `617cd32a`, preserving the 66-byte external-pin protocol, and
  advanced only to a read-only canonical-validator extraction/parity audit.

- 2026-07-14: Closed the R-07 protected-manifest reader boundary audit after
  three independent reviews proved capacity, canonical-parser ownership, and
  manifest security-policy blockers. Advanced only to the exact two-file held-
  handle capacity extension; no manifest reader is authorized yet.

- 2026-07-14: Corrected the R-07 authenticated-membership sequence after a
  no-repeat call-graph audit proved target filesystem evidence was not an
  authentication input. Advanced only to a fixed-child manifest-reader boundary
  audit with reader-owned direct-pin digest comparison. ProgramData locator,
  protected observation, composition, Qdrant, planning, enrollment, publication,
  approval, and cleanup remain separate closed seams.

- 2026-07-14: Checkpointed the audited R-07 Windows external-pin reader and
  lifecycle ownership, then advanced only to a read-only authenticated
  protected-membership composition audit. Enrollment, publication, Qdrant,
  planning, approval, and cleanup execution remain closed.

- 2026-07-13: Checkpointed the R-07 opt-in same-handle Windows security-
  descriptor capability and advanced only to the audited no-argument external-
  pin reader source/test seam.

- 2026-07-13: Checkpointed the R-07 same-handle bounded-read prerequisite and
  advanced only to the read-only Windows security-capability decision ahead of
  any external-pin reader implementation.

- 2026-07-13: Corrected the R-07 external-pin reader order after the preflight
  proved the opaque held-handle backend lacks same-handle security inspection
  and bounded payload access; advanced only to the bounded-read extension seam.

- 2026-07-13: Checkpointed the R-07 shared Windows held-handle extraction with
  exact observer parity and advanced only to the audited read-only external-pin
  reader source/test seam.

- 2026-07-13: Closed the R-07 Windows external-pin boundary audit, selected the
  exact future reader evidence/security contract, and advanced only to a shared
  held-handle extraction-parity seam before any reader implementation.

- 2026-07-13: Selected the exact R-07 protected membership and Windows external-
  pin trust-root semantics, corrected the authority order to keep pure
  membership non-authoritative, and advanced only to its isolated import-pure
  source/test seam.

- 2026-07-13: Checkpointed the R-07 duplicate canonical protected-identity
  envelope guard and advanced only to the explicit protected-authority source
  and trust-bootstrap decision gate.

- 2026-07-13: Checkpointed the R-07 passive filesystem observer and advanced
  only to a read-only protected-boundary authority audit.

- 2026-07-13: Closed the R-07 filesystem-observer boundary audit, selected the
  exact observer source/test pair, and inserted protected-boundary authority
  verification ahead of Qdrant observation and runnable planning.

- 2026-07-13: Checkpointed the R-07 import-pure clean-memory configuration
  projection and advanced only to a read-only audit of the filesystem-observer
  boundary.

- 2026-07-13: Closed the R-07 passive plan-orchestration audit and selected
  deterministic configuration projection as the next isolated implementation
  seam, ahead of separate filesystem, Qdrant, and runnable-plan checkpoints.

- 2026-07-13: Checkpointed the R-07 import-pure immutable candidate-plan
  authority and advanced only to a read-only audit of passive `plan`
  orchestration ownership.

- 2026-07-13: Checkpointed the R-07 cleanup approval foundation with atomic
  initial job metadata, one-lock lifecycle claims, and exact cleanup-only
  MiniAgent request/deadline authority. Preserved the no-executor/no-target
  boundary and advanced only to an import-pure immutable candidate-plan seam.

- 2026-07-13: Verified R-05-F1 after a final no-repeat reconciliation found no
  remaining nominal retrieval/status hidden mutation. Routed mounted output
  redaction to R-20, durable query/path retention and migration to R-23, and
  unsafe diagnostic warning text to R-15, then advanced the bounded mission to
  a read-only R-07 audit.

- 2026-07-13: Checkpointed retrieval FAISS logical-reference privacy across new
  event/warning output and future legacy-input rollup projection. Preserved
  internal FAISS I/O, raw history, rollup behavior, central serialization, and
  route effects, then advanced R-05-F1 to a no-repeat remaining-candidate
  reconciliation rather than assuming another implementation seam.
- 2026-07-13: Selected one retrieval FAISS logical-store-reference privacy
  contract across new event/log producers and legacy-input rollup projection.
  Kept historical cleanup, existing derived rows, and ingestion commit-event
  paths under their separate owners.
- 2026-07-13: Checkpointed retrieval query-log privacy across the four selected
  engine records and Uvicorn access-record boundary. Preserved exact functional
  query propagation, access logging, secret redaction, and route effects, then
  advanced R-05-F1 to the separate FAISS absolute-path privacy selection.
- 2026-07-13: Selected one complete retrieval raw-query log boundary after a
  fresh audit found both four engine INFO producers and Uvicorn GET access-log
  exposure. Kept FAISS path privacy, analytics-question logging, and derived
  intent logging as separately owned follow-up evidence.
- 2026-07-13: Checkpointed explicit origin-owned retrieval context across API,
  MiniAgent, CLI, engine, router, Qdrant, ephemeral-memory, and FAISS. Removed
  ambient attribution, preserved telemetry and route effects, and advanced
  R-05-F1 to the separate producer-side privacy/detail selection.
- 2026-07-13: Selected explicit origin-owned retrieval request context after an
  in-process interleaving witness proved process-global attribution crosses
  request boundaries. Kept raw-query and FAISS-path privacy as the next
  separate producer-side seam and froze completed persistence authority.
- 2026-07-13: Checkpointed canonical retrieval telemetry policy and bounded
  persistence/fallback authority after closing an adversarial SQLite lock-text
  classification gap. Advanced R-05-F1 to a fresh selection between
  request-context truth and privacy/detail redaction without reopening event
  persistence or reclassifying retrieval routes.
- 2026-07-13: Selected retrieval-event persistence/config authority after
  proving configuration loss, fallback relocation, missing-primary creation,
  and same-path replacement event loss in temporary roots. Kept request context
  and privacy redaction as separate later seams and retained all four retrieval
  routes as automatic mutations.
- 2026-07-13: Checkpointed shared retrieval SQLite read authority across FTS,
  KG scoring, Qdrant/FAISS provenance, and FAISS shadow scoring while preserving
  committed live-WAL truth, FTS5 behavior, and intentional telemetry. Advanced
  R-05-F1 to a fresh telemetry-policy selection without reclassifying routes.
- 2026-07-13: Selected the shared retrieval SQLite read-authority seam after a
  fresh reconciliation with intentional retrieval telemetry. Recorded the
  telemetry-policy gaps separately and advanced R-05-F1 to mutation-sensitive
  implementation without changing route classification or production code.
- 2026-07-13: Checkpointed summary-only SQLite read authority with existing-file
  URI mode, live-WAL visibility, operation-level authorization, and bounded
  connection ownership. Advanced R-05-F1 to a fresh selection between retrieval
  SQLite and intentional retrieval telemetry without reopening completed seams.
- 2026-07-13: Checkpointed exact local-only text/CLIP retrieval model loading,
  including rejection of incomplete, unpinned, and redirected snapshot
  directories. Advanced R-05-F1 to summary-only live-WAL read authority without
  reopening telemetry, retrieval SQLite, provisioning, or route classification.
- 2026-07-13: Checkpointed the first R-05-F1 repair: all Qdrant query paths now
  require existing collections through bounded GET-only inspection, while
  explicit write paths retain creation authority. Advanced the bounded mission
  to ingest-status constructor no-create without reclassifying retrieval.
- 2026-07-13: Opened R-05-F1 with a three-way hidden-read reconciliation and
  selected Qdrant query no-create authority as the highest-impact single-owner
  repair. Ingest-status directory creation and summary/retrieval SQLite,
  telemetry, model-cache, and ledger effects remain explicitly separate.
- 2026-07-13: Verified R-05 after governing temporal summarization with exact
  confirmation, immutable runtime policy, private durable result truth,
  deterministic no-replay recovery, passive exact-job projection, and truthful
  Retro polling. The full 798-test inherited R-05 union and static/documentation
  gates passed; residual hidden-read, identity, and status effects remain under
  their explicit owners.
- 2026-07-12: Checkpointed the R-05 exhaustive route-effect registry and common
  client boundary after TDD closed duplicate-mount and lifespan route-replacement
  fail-open gaps; retained R-05 as in progress for explicit curated/process
  authority convergence.
- 2026-07-11: Verified R-11-F1 after aligning native handler-declared error
  with the outward envelope, return code, nonmutation report, and durable audit;
  also taught the bounded-mission lint to recognize registered roadmap
  sub-items.
- 2026-07-11: Checkpointed the first R-05 seam after converging ingest
  preparation/confirmation/cancellation on one bounded loopback-only ledgered
  route. Recorded the independently discovered unchanged MiniAgent
  handler-error truth gap as isolated follow-up R-11-F1 rather than mixing it
  into R-05.
- 2026-07-11: Opened R-05 implementation from a fresh mounted-route and UI
  authority audit. Reconciled 70 clean operations against eight frozen
  R-08-only identity routes, preserved the R-08/R-14 boundaries, and selected
  the unledgered Retro upload bypass as the first isolated repair seam.
- 2026-07-11: Verified R-11 after replacing native confirmation bypasses with
  one exact-operation/full-scope authority, adding durable generic decision and
  execution audit evidence, aligning dormant Control Agent activation and
  mutation gates, and proving the governor MCP remains preflight-only. Three
  private checkpoints, 229 focused tests, documentation/static gates, and
  independent reviews passed.
- 2026-07-11: Verified R-09 from one task-neutral evidence snapshot, generated
  human/JSON/RAG state from that source, removed stale active-epoch and runtime
  claims, and replaced the dated Hermes prompt with a dynamic read-only
  contract. Focused tests and three independent final reviews passed.
- 2026-07-11: Verified R-18 after isolating validator outputs, replacing stale
  lifecycle skips with exact-scope evidence, pinning a truthful golden runtime
  profile, proving immutable live-ledger reads, and adding artifact-free
  evidence runners. Fresh R-02/R-06 no-repeat gates passed, and three
  independent final reviews returned READY.
- 2026-07-11: Privately checkpointed R-02 and R-03, opened R-17 through R-23
  and R-25,
  replaced the obsolete repair order with the approved stability-first master
  register, and recorded execution governance, deferred lanes, acceptance rules,
  and the no-repeat register. Reopened R-04 after independent review found
  residual tracked workstation/location and private-LAN authority that its
  passing tests did not detect.
- 2026-07-11: Closed the R-04 reopening after genericizing the remaining
  machine, location, household-LAN, and voice authority; added regression
  coverage; proved private runtime equivalence without printing private values;
  and created the isolated configuration checkpoint.
- 2026-07-11: Reopened R-06 during isolated extraction after review proved the
  final checkpoint cleanup gate could discard failed non-Qdrant persistence
  evidence despite a Qdrant-complete video result.
- 2026-07-11: Closed R-06 after binding final cleanup to fresh exact-window
  five-target evidence, adding the failed-target retention regression, and
  creating the isolated progressive-ingestion checkpoint.
- 2026-07-11: Checkpointed the foundational project orientation and instruction
  chain, archived its completed plan, and recorded the unsafe automatic public
  `AGENTS.md` sync hook under R-16 after reversing its side effect.
- 2026-07-11: Completed the entry-by-entry R-17 inventory of the frozen mixed
  checkout: 96 expanded paths, zero unknowns, and explicit later owners or
  no-repeat dispositions for every entry. Kept R-17 open and the source tree
  frozen pending isolated extraction and separately approved retirement.
- 2026-07-10: Replaced the stale public-preview roadmap with the lifetime
  roadmap and repair register. Consolidated the sixteen audit findings,
  preserved unfinished intent, moved eight superseded plans/reports to the
  archive, updated active references, and verified link and drift gates.
- 2026-07-10: Verified R-01 after replacing the mismatched promotion contract,
  ambiguous native scope handling, and stale output declaration with one
  explicit, scope-bound interface and focused lifecycle tests.
- 2026-07-10: Reopened R-02 before checkpoint after post-commit Qdrant failure
  analysis found that acknowledgement-only delivery was neither exact-scope nor
  recoverable. Added a transactional delivery outbox, verification-before-clear,
  and a separately gated reconcile path; final adjacent tests and checkpoint
  remain pending.
- 2026-07-10: Kept R-03 IN_PROGRESS because its atomic transition changes are
  still mixed with the active R-02 working tree and must be isolated and
  reverified after the R-02 checkpoint.
- 2026-07-10: Verified R-06 after replacing boolean progressive checkpoints
  with revalidated per-target persistence truth and proving isolated, stale,
  failed, legacy, and non-contiguous resume behavior.
- 2026-07-10: Verified R-04 after moving private identity and machine state to
  ignored local authority, replacing tracked dated defaults, and proving the
  complete private resolved configuration unchanged.
