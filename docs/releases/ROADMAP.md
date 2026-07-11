<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_ROADMAP -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

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
- Status: IN_PROGRESS
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

### R-05 — Define API and Command Center execution authority

- Priority: P0
- Status: OPEN
- Finding: doctrine calls the API and console read-only while the identity
  branch adds roster writes and background process launch.
- Repair: adopt the loopback-only local-operator API model; classify every route
  as passive read, request staging, curated mutation, or process execution;
  converge staging on one ledgered path; make curated writes atomic,
  scope-constrained, and audited; use one single-use scope-bound confirmation
  plus persistent job record for process/destructive actions; deny remote
  mutation by default; remove duplicate upload/token/boolean/route authorities.
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
- Existing-authority trace (2026-07-10): two independent confirmation mechanisms
  already exist. The ingest facade uses a self-issued in-memory token that is
  neither operation/scope-bound nor durable. `MiniAgentClient` uses a persistent
  token store and policy contracts, but only promotion tokens are scope-bound;
  its native bypass currently permits `run_ingestion` and `file_delete` without
  the confirmation required by their contracts, and native result envelopes do
  not themselves create the promised generic durable tool-audit record. Neither
  mechanism is a safe common API authority as implemented, and a third gate must
  not be layered beside them.
- Approved direction (2026-07-11): Retro Console, Command Center, Identity
  Workbench, Stitching Workbench, and Summary Console are explicit loopback-only
  local-operator control surfaces. Request staging converges on one ledgered
  path; curated writes are
  scope-constrained, atomic, and durably audited; destructive/process actions use
  one single-use scope-bound confirmation and persistent job record; and remote
  binding denies mutation by default. The superseded upload, token, boolean-confirm,
  and duplicate route authorities must be removed rather than retained as
  compatibility layers. R-08 remains responsible for durable identity process
  recovery after this authority choice; R-11 owns repair of the MiniAgent policy
  contradictions and must complete before it can serve as the common gate.

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

### R-07 — Replace the unsafe clean-memory workflow

- Priority: P0
- Status: OPEN
- Finding: the runbook mixes incompatible shell syntax, dated locations, broad
  deletion, and continue-after-failure behavior.
- Repair: replace manual deletion blocks with one portable, manifest-first,
  dry-run-capable, exact-scope, stop-on-failure tool; remove old instructions.
- Completion gate: temporary-root tests prove boundary rejection, idempotency,
  partial-failure handling, and post-clean evidence.
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
  recover stale/dead jobs; and redact path, subprocess, and exception detail.
- Completion gate: live roster checksums remain unchanged by tests; route
  uniqueness, exclusion, synchronization failure, concurrent write, crash,
  restart recovery, and redaction tests pass before the Workbench browser
  witness is rerun.
- Public impact: RELEASE_REQUIRED
- Human-curated Phase 5A sub-gate: review face clusters, speaker clusters,
  mentions, and unresolved roster members; create mappings only from confirmed
  human decisions; run roster validation and scene-first identity tests; promote
  only after the evidence gate passes; perform no automatic identity promotion;
  rerun Workbench browser verification against the live API.

### R-09 — Rebuild current-state truth from live evidence

- Priority: P1
- Status: OPEN
- Finding: human and JSON state surfaces describe earlier ingestion, promotion,
  service, installer, and toolchain snapshots.
- Repair: capture one fresh evidence snapshot after checkpointing, then generate
  human and JSON state from that same source; correct stale ingestion, model,
  service, RAG context, Hermes verification, and authority-chain claims while
  labeling historical epochs explicitly.
- Completion gate: human and JSON state agree with one live probe and
  verification time; no older epoch is described as active; historical evidence
  is clearly non-authoritative.
- Public impact: SANITIZE

### R-10 — Align architecture with governed materialization

- Priority: P1
- Status: OPEN
- Finding: older canonical documents still imply ingestion-time active
  SQLite and graph persistence.
- Repair: correct Qdrant storage-root documentation and align staged ingestion,
  governed materialization, promotion, and active-memory projections across
  canonical architecture docs before dependent operational docs.
- Completion gate: focused code traces/tests and docs agree; staged-only and
  promoted-materialization tests demonstrate the written model.
- Public impact: RELEASE_REQUIRED

### R-11 — Remove Control Agent authority contradictions

- Priority: P1
- Status: OPEN
- Finding: active docs mix observer-only operation, bounded healing, autonomous
  mutation, and disabled defaults.
- Repair: remove native confirmation bypasses; bind every approval to operation
  and exact scope; make token persistence atomic; append durable generic audit
  records for decisions/execution; keep the governor MCP preflight-only and
  non-executing; separate dormant capability from production default.
- Completion gate: docs, contracts, configuration, scope-bound token tests,
  audit tests, and disabled-by-default tests name one authority model.
- Public impact: RELEASE_REQUIRED
- Audit evidence (2026-07-10): the local MiniAgent contract marks
  `run_ingestion` and `file_delete` as confirmation-required, but the in-process
  native bypass returns them as allowed without the contract's HITL exchange
  (`file_delete` checks break-glass only). Scope equality is enforced only for
  promotion tokens, token-store writes are not atomic, and native result
  envelopes are returned without a generic durable audit append. Do not route
  API control surfaces through this path until these contradictions are replaced
  and verified.

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
- Status: IN_PROGRESS
- Finding: resolved and historical plans remain active; some docs lack badges,
  contain fixed roots, or point to nonexistent archive locations.
- Repair: use this roadmap as the single global register, archive superseded
  plans, update references, and retain one active authority per purpose.
- Completion gate: link, badge, drift, and authority-map checks pass; searches
  find no superseded active plan path.
- Public impact: RELEASE_REQUIRED
- Cutover evidence (2026-07-10): rebuilt this roadmap in place; moved eight
  superseded plans/reports to the archive; verified 175 active Markdown files,
  695 relative links, zero broken links, zero active drive-root violations, and
  a passing banned-token check.
- Remaining before VERIFIED: classify or badge the 25 active Markdown files
  still missing documentation authority metadata and reconcile the generated
  file index with the post-cutover tree.

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
- Evidence (2026-07-11): R-02 and R-03 are checkpointed. Read-only inventory
  found no dirty Qori work, identified R-04 as previously implemented but
  reopened/uncheckpointed and R-06 as verified-but-unextracted,
  separated identity evidence from unsafe R-08 authority prototypes, and marked
  the untracked API restart script as incompatible with R-19.

### R-18 — Isolate validator tests and generated reports

- Priority: P0
- Status: OPEN
- Finding: validator tests can overwrite operator reports, legacy tests depend
  on a machine-local skill copy, stale lifecycle `xfail` cases remain, and one
  ingestion test resolves an obsolete live epoch.
- Repair: add an explicit report-output directory, redirect tests to temporary
  roots, add a no-operator-report-mutation regression guard, convert lifecycle
  `xfail` cases using existing fixtures, and add a live/golden profile where
  required-service absence fails rather than skips.
- Completion gate: hermetic tests leave operator evidence unchanged and the
  live/golden profile fails truthfully when dependencies are missing.

### R-19 — Establish one canonical API and Watchdog supervisor

- Priority: P0
- Status: OPEN
- Repair: use `goodq_core`, interpreter bindings, `python -m api.server`, fixed
  loopback port 30000, and `cli.watchdog`; fail visibly on collisions; add
  sustained `/api/status` health, child ownership, restart/backoff, Watchdog
  liveness, and structured logs; install no dependencies during launch.
- Completion gate: cold start, port collision, child crash, backoff, and restart
  acceptance tests pass before startup shortcuts are replaced.

### R-20 — Enforce LAN, port, and secret boundaries

- Priority: P0
- Status: OPEN
- Repair: keep Qdrant, GoodQ API, OpenViking, Ollama, and model internals
  loopback-only; disable or rebind default Ollama 11434; remove broad inbound
  firewall authority; reserve 8900 for one remote Nanobot tunnel; audit auth,
  redaction, rate limits, and retention for the 8901 monitor; design one future
  authenticated household gateway instead of exposing raw services.
- Completion gate: port/listener and firewall witnesses prove raw services are
  unreachable from LAN devices; key-name parity passes. Destructive plaintext
  secret-backup removal remains a separate approval gate.
- Daily Hermes sub-gate: start/check OpenViking by default, support explicit
  `-SkipMemory` and `-RequireMemory`, check GoodQ without starting ingestion,
  and verify model, memory, MCP, and security canary state before Desktop opens.

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
  before any bulk deletion, deduplication, or movement.

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
R-02, R-03, or R-06 implementation; Command Center milestones M1 through M5;
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
2. Restore truthful evidence: R-18, R-09, R-13, and R-10.
3. Establish one control authority: R-11, R-05, then R-07.
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

- 2026-07-11: Privately checkpointed R-02 and R-03, opened R-17 through R-23
  and R-25,
  replaced the obsolete repair order with the approved stability-first master
  register, and recorded execution governance, deferred lanes, acceptance rules,
  and the no-repeat register. Reopened R-04 after independent review found
  residual tracked workstation/location and private-LAN authority that its
  passing tests did not detect.
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
