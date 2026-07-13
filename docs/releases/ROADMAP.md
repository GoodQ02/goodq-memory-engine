<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_ROADMAP -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

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
- Repair: keep Qdrant, GoodQ API, OpenViking, Ollama, and model internals
  loopback-only; disable or rebind default Ollama 11434; remove broad inbound
  firewall authority; reserve 8900 for one remote Nanobot tunnel; audit auth,
  redaction, rate limits, and retention for the 8901 monitor; design one future
  authenticated household gateway instead of exposing raw services.
- Completion gate: port/listener and firewall witnesses prove raw services are
  unreachable from LAN devices; key-name parity passes; focused API/UI oracles
  prove mounted household-facing projections expose logical references rather
  than local paths. Destructive plaintext secret-backup removal remains a
  separate approval gate.
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

### R-25 — Private integrated verification gate

- Priority: P0
- Status: OPEN
- Repair: run focused seam tests first, then the approved private integrated
  suite covering configuration, privacy, fixed roots, secrets, documentation,
  cold start, LAN boundaries, memory, identity, retrieval, and browser behavior.
- Completion gate: private `dev` is a clean descendant containing every approved
  repair. Public release remains R-16 and a separate approval gate.

## Carried-Forward Verification Items

These items preserve unfinished intent from the plans this roadmap replaces.

### V-01 — Portable follower witness

- Status: DEFERRED
- Re-entry gate: follower laptop access and an approved installer build.
- Completion: install, one-scene ingest, retrieval, and report pass without
  workstation-specific paths.

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
