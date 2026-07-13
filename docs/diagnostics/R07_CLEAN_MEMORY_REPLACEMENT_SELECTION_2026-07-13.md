<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Clean-Memory Replacement Selection

## Decision

Replace the manual clean-memory procedure with one manifest-governed operator
CLI, `python -m cli.clean_memory`, backed by a pure, dependency-injected core in
`steps/common/clean_memory.py`.

The selected command surface is `plan`, `approve`, `apply`, `reconcile`, and
`status`. Planning is the default behavior. Only `apply` may remove a planned
target, and it may do so only after exact configuration and target
revalidation, an R-23-compliant disposition and rollback proof, one R-11
MiniAgent exact-scope authorization, and an R-05 action-job transition to
execution. `reconcile` may repair evidence/job state after interruption but may
never perform or resume target deletion.

This selection does not authorize cleanup of configured data. Implementation
and tests remain hermetic. `plan` remains the manifest-first read-only dry run:
it can inventory one exact configured epoch and produce an unapproved candidate
plan without a job or token. The production approval registry contains no
enabled disposition or rollback schema until an R-23 checkpoint supplies it.
Therefore production `approve` and `apply` return
`r23_authority_unavailable` before artifact resolution, job creation, MiniAgent
construction, or mutation until that separate authority lands.

## Governing Invariant

A clean-memory action is valid only when all of the following are true:

- operator input identifies one exact configured epoch, never a path pattern;
- resolved configuration derives every destructive target;
- an immutable candidate plan binds the exact targets, pre-state,
  configuration, and execution order;
- the approved action scope binds that plan plus exact disposable and
  restorable evidence, and approval is single-use;
- apply rejects drift and boundary ambiguity before its first mutation;
- execution stops on the first failure and records what was not attempted; and
- plan-bound post-action evidence reports actual state without claiming
  transactional rollback for irreversible deletion.

The configured source tree, source/import/processed media, control and recovery
databases, models, caches, reports, Qdrant storage root, unrelated epochs, and
promoted or otherwise retained memory are protected. A transient current-state
document is not sufficient authority to declare a corpus disposable.

## No-Repeat Result

Fresh instruction, script, test, configuration, authorization, and job-ledger
traces found no existing safe cleanup executor to finish or wrap. The proven
parts are lower-level authorities only:

- `load_configs()` plus `get_runtime_paths()` for configured path resolution;
- `atomic_write_json()` for same-directory atomic evidence writes;
- the repository's canonical JSON SHA-256 pattern;
- MiniAgent's operation-bound, exact-argument, expiring, atomic single-use
  authorization and external execution audit; and
- `ActionJobLedger` for one active logical action and durable lifecycle state,
  extended only by the focused generic owner-and-state compare-and-swap that
  the current split `adopt_owner()` / `transition()` methods cannot provide.

R-05 and R-11 are already verified. The replacement must reuse those
authorities rather than add a third token, boolean confirmation, break-glass
path, or independent job ledger.

## Active Instruction Census

### Destructive authority

`docs/agent/workflows/CLEAN_MEMORY_START.md` is the active destructive
procedure. Its embedded commands can remove:

- every Qdrant collection whose name starts with `goodq_`;
- configured memory and knowledge-graph databases plus SQLite sidecars;
- global control, recovery, and checkpoint databases;
- a working-directory-relative legacy knowledge-graph database;
- every file recursively beneath the configured FAISS directory; and
- watchdog state and broad processing-directory content.

It then initializes collections as a separate mutation while continuing across
several deletion failures. Its pre-manifest is not consumed as execution
authority, and its post-manifest is a best-effort report rather than an oracle.

### Operator-skill copies

Both repository copies direct agents to the workflow, but their summaries
disagree. `.agents/skills/goodq4all-operator/SKILL.md` names watchdog,
processing, and post-manifest work; the copy under
`docs/agent/skills/goodq4all-operator/SKILL.md` omits them. Neither copy names
the full database, sidecar, FAISS, control, recovery, or legacy-file scope.

### Active redirects and semantic-drift surfaces

`docs/guides/CLEAN_MEMORY_START.md` is an active indexed guide. It contains no
inline deletion block, but it delegates to the unsafe workflow and promises
generic cleanup scripts and fresh collection initialization. It must describe
and link only the verified replacement after implementation.

`docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md` separately permits an
approved prefix-wide `goodq_` reset. Its semantic meaning must be aligned so it
cannot reauthorize broad deletion after the primary workflow is repaired.

`docs/agent/README.md`, the root `README.md`, and active `SUPPORT.md` are
navigation pointers. They must continue to resolve to the single verified
workflow and must not become a second procedure. `SUPPORT.md` must also stop
presenting generic reset help as though governed memory disposition were an
ordinary first-install repair.

`SUPPORT.md` currently also makes the archived uninstall guide operationally
reachable from its reset path. That sealed historical guide contains manual
environment, Qdrant, and whole-data-root deletion. R-07 does not rewrite the
archive; implementation removes the active link from `SUPPORT.md`. Reference
discovery must follow active links transitively and reject any active path that
re-exposes an archived destructive procedure.

The remaining active/index references are `AGENTS.md`,
`docs/bootstrap/doc_authority_map.md`,
`docs/reference/indexes/AGENT_COMMS_INDEX.md`,
`docs/reference/indexes/AGENT_FILE_INDEX.md`, and
`docs/codebase_index/README.md`. The first three retain the workflow in the
instruction/authority graph. The generated file and codebase indexes must be
regenerated after the new CLI is added and the legacy executors are removed so
they cannot continue classifying deleted scripts as active tooling.

## Unsafe Existing Utilities

### `scripts/qdrant/prepare_clean_slate.py`

Do not reuse this as an executor. It contains hard-coded historical epoch and
WSL assumptions, can stop processes outside its dry-run state, selects Qdrant
collections by substring, writes an unbound non-atomic manifest, continues
after failures, and has no behavioral authority suite. After the replacement
passes and all active references are replaced, delete it. Git history and this
selection preserve the audit evidence; a compatibility executor would retain a
second authority.

### `scripts/generate_post_manifest.py`

Do not invoke or import it as verification authority. It resolves configured
state, probes services, creates directories, and writes a dated report at
module import; it catches Qdrant failures and still succeeds. Its sole test
checks only that the file exists. After replacement verification, delete it and
replace its stale existence assertion with behavioral tests for the plan-bound
`status` and receipt verifier.

### Separate retention utilities

`scripts/clean_old_processing.py` and `scripts/rotate_logs.py` are not R-07
executors. They use broad age-based retention behavior, default to mutation,
and continue after failures. Their classification, retirement, or replacement
belongs to R-23. R-07 must not absorb global processing or log retention.

## Selected Production Boundary

### Pure core: `steps/common/clean_memory.py`

The core owns only deterministic planning, validation, ordered execution
through injected filesystem/Qdrant adapters, and receipt reconciliation. It
must be import-pure: no configuration load, network call, directory creation,
process probe, service start, or report write at import time.

The core must expose typed logical records for:

- resolved cleanup scope;
- immutable plan and canonical digest;
- preconditions and bounded protected-boundary identities;
- per-target execution result; and
- final or partial receipt.

### Operator CLI: `cli/clean_memory.py`

The CLI is the sole orchestration entry point:

- `plan` resolves configuration, inventories exact targets read-only, and writes
  one job-independent immutable candidate plan atomically; it resolves no
  disposition/rollback artifact and creates no job or token;
- `approve` first requires the registered production disposition, rollback, and
  exclusive-quiescence authorities; only then does it resolve logical artifact
  IDs, validate their exact coverage against the existing plan, create or find
  one action job from the stable approval scope, request MiniAgent confirmation,
  and atomically persist the authorization fingerprint;
- `apply` claims the single-use token, revalidates every bound precondition,
  durably journals and executes the exact plan, records the external outcome,
  and terminalizes the job truthfully;
- `reconcile` is cleanup-target-read-only but control-evidence-mutating: it
  probes only exact planned targets and may append receipt/audit evidence or
  transition an already-authorized nonterminal job after interruption; it never
  deletes, resumes, or converts a terminal failed job to success; and
- `status` uses the existing passive action-job reader and reads existing plan
  and receipt evidence without constructing `ActionJobLedger`, creating
  directories, or contacting target services.

No API or UI route is added. No service is started or stopped. Collection
initialization and ingestion remain separate later operator actions.

## Exact Target Contract

For `plan`, the operator may choose only the exact configured `epoch_id`. For
`approve`, the operator may add logical R-23 disposition and rollback artifact
IDs with expected SHA-256 values; both artifacts must reference the candidate
`plan_sha256`. The registered production verifier resolves those IDs inside its
configured authority. The CLI accepts no artifact path. Arbitrary
destructive/evidence paths, glob patterns, collection prefixes, alternate
endpoints, and custom deletion lists are not accepted.

Configuration derives these candidate targets for the exact epoch only:

1. the configured memory database and its planned `-wal` and `-shm` sidecars;
2. the configured knowledge-graph database and its planned sidecars;
3. regular files enumerated beneath the configured epoch-scoped FAISS root; and
4. the exact four configured epoch collection names for text, CLIP, DINO, and
   audio vectors.

The plan never targets the epoch directory itself. Already-absent targets are
recorded and later reconcile as `skipped_absent`; a target that existed during
planning but disappears or changes before apply is drift and blocks all
mutation.

Every filesystem target must resolve beneath the exact configured epoch root.
The allowed root, each ancestor, each target, the plan/report location, and the
disposition/rollback evidence must reject symlinks, junctions, and other
reparse-point redirection. The epoch root itself, foreign roots, `..` escapes,
and case/normalization aliases that change identity are rejected.

The following remain outside the target set even if an old instruction named
them:

- global control/recovery/checkpoint databases;
- configured source, import, processing, processed, and failed media roots;
- watchdog/process state and running processes;
- model and download caches;
- Qdrant's storage root and service logs;
- report, backup, archive, repository, and public-checkout content; and
- any other epoch or collection.

## Disposition And Rollback Gate

R-07 owns safe mechanism, not retention decisions. An approved action scope is
valid only when it binds the immutable candidate plan plus both:

- `disposition_sha256`: an R-23-governed artifact proving the exact epoch and
  exact collections are authorized disposable; and
- `rollback_sha256`: a verified artifact outside every target proving the
  operator's approved recovery source and integrity.

The production disposition verifier must accept only an R-23-registered schema
whose decision is exactly `disposable` and which binds the exact epoch,
candidate plan digest, configuration-scope digest, exact collection set,
target-scope digest, issuing authority/checkpoint, and lifecycle evidence.
`retained`, `promoted`, `active`, `unknown`, expired, conflicting, or
incompletely classified evidence is a hard refusal before action-job creation.
Durable lifecycle/promotion evidence that conflicts with a disposable claim
also fails closed.

The production rollback verifier must accept only an R-23-registered restore
schema/version. It must prove coverage of every present planned regular file
and every exact Qdrant collection, including collection configuration, point
count, exact point-ID digest, snapshot identity/checksum, backup creation time,
and a supported restore procedure. The backup must predate the plan, pass
integrity validation, and reside outside destructive ancestry. Its recovery
payload may reside only in the registered protected backup authority. Missing
one file/collection, stale or mismatched snapshots, unsupported restore
formats, or non-restorable evidence blocks approval before job/token creation;
it never blocks candidate planning.

Both control-plane evidence records must be regular, non-reparse files outside
the destructive scope, bind the same candidate plan, epoch, and target identity,
and pass hash verification. A recovery payload may live inside an explicitly
protected backup authority, but never inside deletion ancestry; its protected
root identity and content checksum must remain unchanged through apply. Until
R-23 registers production verifiers, `approve`/`apply` refuse before resolving
artifacts or creating job/token evidence. Tests inject fixture verifiers
directly into the pure core; no CLI flag, environment variable, fallback schema,
or test-mode switch may register them in production.

No hard-coded disposable-epoch allowlist is introduced. Current-state prose
may inform an audit but cannot replace durable disposition authority. The
currently promoted July corpus remains protected and is not a test target.

## Immutable Plan Contract

The plan schema is `goodq.clean-memory-plan.v1`. Its `authority` object is
independent of creation time, random IDs, and action-job identity. The canonical
`plan_sha256` is SHA-256 over that object using compact UTF-8 JSON, sorted keys,
and `allow_nan=False`. `plan_id` is derived from the digest; observational
creation metadata sits outside the hashed authority and the plan never contains
an action-job ID. This removes circular identity and gives unchanged concurrent
planning one stable scope.

The authoritative object binds at least:

- schema and policy versions;
- operation `clean_memory.apply` and exact epoch ID;
- normalized configuration-scope digest;
- exact epoch-root logical identity, never exposed in MiniAgent audit targets;
- ordered logical filesystem targets with type, existence, size, mtime,
  platform file identity, and mandatory SHA-256 for every present regular file;
- the canonical configured loopback Qdrant endpoint with redirects disabled,
  exact equality between the configured four-name map and the plan target set,
  and per-collection canonical configuration, point count, authoritative
  generation token or full canonical point-state digest including IDs,
  payloads, and vectors. This pre-state is collected read-only and is
  independent of the later rollback artifact. Unrelated and
  prefix-similar collections are protected canaries, not members of that set
  and not blockers merely because they exist;
- protected-boundary identities and quiescence preconditions. This is a bounded
  structural-exclusion/root-identity oracle, not a claim that entire protected
  corpora were byte-hashed;
- deterministic execution order.

The candidate plan is intentionally unapproved. R-23 disposition and rollback
records consume and bind its `plan_sha256`; `approve` binds their IDs/digests
with the plan in the action-job/MiniAgent scope without rewriting the plan.

Production evidence lives only under a configured control root derived as
`<data_root>/control/clean_memory`, sibling to the established action-job root.
The CLI accepts no arbitrary production report root. The control root and all
ancestors must be outside the epoch, rollback, and protected target scopes and
must be non-reparse. Tests inject a temporary evidence root directly into the
core.

The first successful writer atomically persists `plan_<plan_sha256>.json`.
Repeated or concurrent plans with the same authority verify and return that
existing immutable file rather than replacing it with new timestamps. A digest
collision with different authority is fatal. Planning writes no action job,
mutates no target, and stops no process.

## Existing Authorization And Job Authority

Add one authorization-only MiniAgent contract named `clean_memory.apply`.
There is no native deletion handler. The exact logical authorization arguments
are:

```text
job_id
epoch_id
plan_sha256
config_scope_sha256
disposition_sha256
rollback_sha256
```

Registration is deterministic across every existing authority: the JSON tool
contract, `MUTATING_DENY_ON_AGENT_FAILURE`,
`LOCAL_CONFIRMATION_REQUIRED_TOOLS`, `LOCAL_AUTHORIZATION_ONLY_ACTIONS`,
`LOCAL_NATIVE_VALIDATION_BYPASS_TOOLS`, and
`AUTHORIZATION_SCOPE_VALIDATORS` all contain the new operation exactly once.
The exact scope validator accepts only the six named logical fields with strict
job/epoch/digest formats, and external-outcome validation requires exactly
`clean-memory:<job_id>` as its sole audit target. A focused matrix test rejects
a missing classification, extra scope field, wrong target, ordinary native
dispatch, fallback execution, or any `_execute_clean_memory` handler. External
execution remains owned solely by the manifest-aware CLI.

Detailed paths stay in the private plan. MiniAgent audit uses one logical
target, `clean-memory:<job_id>`, rather than one target per file. This preserves
the external audit target cap while the plan and receipt retain the complete
ordered ledger.

`ActionJobLedger` remains the single durable lifecycle authority with operation
`clean_memory.apply`. `approve` creates or finds the job using the stable scope
`{epoch_id, plan_sha256, config_scope_sha256, disposition_sha256,
rollback_sha256}`; the allocated `job_id` then participates in the MiniAgent
authorization arguments but never changes the plan digest. Repeated and
concurrent planning/approval therefore converge on one immutable plan and one
active job. Each CLI invocation uses a unique safe owner such as
`clean_memory.cli.v1:<uuid>`; every later command deliberately adopts only the
expected exact nonterminal state under the ledger lock.

The present ledger cannot make owner adoption and lifecycle transition one
decision: `adopt_owner()` and `transition()` acquire the lock separately, and
`transition()` does not compare owner. R-07 therefore adds one generic
`adopt_and_transition()` primitive to `ActionJobLedger`. Under one existing
ledger lock it must compare the expected state and owner, validate the permitted
transition and metadata update, then persist the replacement owner, new state,
and updates in one atomic record replacement. Every R-07 lifecycle transition
uses this primitive whether the owner changes or remains the same; the cleanup
CLI must not compose `adopt_owner()` and `transition()` itself. Existing callers
and lifecycle edges remain unchanged.

MiniAgent currently expires confirmation tokens 600 seconds after issuance but
does not return or persist an absolute expiry in the action job. R-07 makes that
existing duration one named MiniAgent constant and adds an opt-in challenge
binding that is mandatory only for `clean_memory.apply`: the caller supplies a
validated authorization request ID and future absolute expiry, MiniAgent rejects
a deadline later than its 600-second maximum, stores the exact validated
deadline with the token, fails closed on missing/malformed expiry metadata for
that operation, and echoes the request ID/deadline as non-secret challenge
metadata. Token claim for `clean_memory.apply` must receive and compare that same
request ID/deadline in addition to operation and exact arguments. Existing
MiniAgent operations that omit these optional parameters retain their current
timestamp-based token contract and call signature.
`ActionJobLedger` accepts the normalized UTC
`authorization_expires_at_utc` metadata field; no token value is ever stored in
the job.

The state protocol is fixed:

1. `approve` generates one authorization request ID and absolute deadline before
   job preparation. A focused optional-initial-metadata extension to
   `prepare_or_find_active_with_status()` validates and writes those fields in
   the newly created `pending_confirmation` record under the same ledger lock;
   an existing job is returned without metadata overwrite. Only after the
   complete pending record exists may `approve` construct MiniAgent and request
   a challenge bound to that exact request ID/deadline. It persists the returned
   token fingerprint before returning the token. A second approval sees
   `active_job_exists` and does not issue a token.
2. `apply` validates complete authorization metadata, acquires the registered
   exclusive writer-honored cleanup lease nonblocking, and only while holding it
   atomically adopts `pending_confirmation` and transitions it to `authorizing`
   through `adopt_and_transition()`. A failed claim releases the lease. Its
   MiniAgent claim supplies the persisted request ID/deadline and refuses any
   challenge-metadata mismatch.
3. The lease-holding winner completes whole-plan preflight, claims the token,
   and transitions `authorizing -> queued -> running`; target adapters may run
   only in `running`.
4. A pre-token failure revokes the pending token where possible and transitions
   `authorizing -> failed`. A crash or `token_already_used` while authorizing is
   reconciled as failed; no target call can have occurred. A crashed `queued`
   job becomes `interrupted`.
5. `reconcile` may adopt `authorizing`, `queued`, or `running` only after it
   acquires the same exclusive cleanup lease nonblocking and validates complete
   persisted plan/auth/journal evidence while holding it. If a live `apply`
   holds the lease, reconciliation returns `cleanup_active` without changing
   job, journal, receipt, or audit evidence. A `running` job follows journal
   truth; terminal states are immutable. It handles `pending_confirmation` only
   under the fail-closed approval-recovery rules below, without acquiring the
   lease because target authority has not begun.

Approval recovery is exact and does not infer process liveness:

- the current protocol can never create an R-07 pending job without its request
  ID/deadline. Missing, partial, or malformed initial authorization metadata is
  `malformed_authorization_job`, never evidence of a crash; `apply` refuses it
  and `reconcile` may only atomically terminalize it as failed without invoking
  MiniAgent or touching target/recovery evidence;
- once request ID/deadline metadata is persisted, the job is treated as if a
  token may exist even when its fingerprint is absent; neither `approve` nor
  `reconcile` reissues, reveals, or searches for that token;
- before the stored deadline, incomplete or undelivered authorization remains
  `pending_confirmation` and returns `pending_authorization_unresolved`;
- at or after the stored deadline, `apply` or `reconcile` atomically adopts the
  exact pending owner/state and transitions it to `expired`; only then may a new
  approval job be created; and
- complete metadata means request ID, exact absolute expiry, and a valid token
  fingerprint. `apply` refuses any partial combination.

This covers a crash before job creation (no record exists), after atomic job and
metadata creation/before token issuance, after token issuance/before fingerprint
persistence, and after fingerprint persistence/before token delivery. The
stored deadline is authoritative because MiniAgent is prohibited from issuing a
cleanup token beyond it.

If MiniAgent construction fails before the issuance call begins, `approve`
terminalizes the pending job so a new attempt can be created. Once issuance is
attempted, an exception or ambiguous response may terminalize immediately only
with verified no-token or successful exact-token revocation evidence; otherwise
the job remains blocked until its deadline. If issuance succeeds but fingerprint
persistence fails, the CLI revokes that exact token before returning and
terminalizes the job. Revocation failure is durably reported as
`authorization_orphaned`, the token is never returned, incomplete job evidence
makes `apply` refuse, and reconciliation may only fail/expire the job—not execute
it. An abrupt crash uses the deadline recovery above rather than assuming
whether issuance occurred.

R-07 does not invent process-ownership heuristics. Quiescence is an injected
exclusive capability honored by every GoodQ filesystem and Qdrant writer.
`apply` acquires it before the pending-to-authorizing owner/state claim and holds
it through post-state/audit/job finalization; non-pending `reconcile` must hold
the same lease before owner adoption or any recovery-evidence write.
Production has no enabled capability until the canonical supervisor authority
registers one; missing, malformed, or nonexclusive evidence returns
`quiescence_authority_unavailable` before job/token creation. If the Qdrant
adapter cannot preserve a verified generation identity through deletion while
that lease is held, production Qdrant apply remains disabled. The cleanup CLI
never starts WSL, probes a side-effecting status route, matches arbitrary
process-name substrings, or stops a process.

Owner recovery, terminal immutability, authorization fingerprint persistence,
and stale-transition rejection reuse the existing ledger contract. A third job
or confirmation mechanism is forbidden.

## Apply, Failure, And Receipt Contract

Before claiming `authorizing`, `apply` acquires the registered exclusive cleanup
lease nonblocking and holds it through post-state, external audit, and job
finalization. Every GoodQ writer must honor that lease; otherwise production
apply is unavailable. While holding it, `apply` revalidates in one fail-closed
whole-plan pass:

- plan digest, schema, operation, epoch, configuration digest, evidence hashes,
  and exact token scope;
- registered R-23 verifier identity plus exact disposable and restorable results,
  with no conflicting retained/promoted/active lifecycle evidence;
- evidence-root, rollback, root-containment, and every reparse/link boundary;
- complete filesystem and Qdrant pre-state fingerprints;
- bounded protected-root/file identities and structural exclusions;
- absence of active GoodQ/ingestion/watchdog workers; and
- action-job ownership and confirmable state.

Active workers cause refusal; this tool never stops them. Any missing, added,
changed, redirected, or unavailable target blocks the entire apply before
mutation. Same-size/same-mtime file substitution; a missing, added, or
prefix-substituted member in the exact configured four-name target map;
non-loopback Qdrant configuration; HTTP redirect; or a target collection
delete/recreate identity change is drift. An unrelated or prefix-similar server
collection remains a nonblocking protected canary solely by existing.

Whole-plan preflight is not sufficient by itself. Immediately before every
filesystem mutation, the adapter must repeat no-follow `lstat`/platform file-ID
and ancestor reparse checks and bind deletion to that verified identity. If the
platform cannot preserve the verified identity through deletion, it refuses.
Immediately before each Qdrant deletion, the adapter must re-probe the exact
collection and compare the complete bound fingerprint with redirects disabled.
A mid-run junction/reparse swap or collection recreation stops before the next
target and leaves outside canaries untouched. The complete fingerprint uses an
authoritative collection generation token or a canonical digest of point IDs,
payloads, and vectors; same-ID content updates are drift. If Qdrant provides no
lease-honoring conditional delete or generation identity that remains bound
through the delete call, the adapter refuses rather than sample-and-delete.

Execution follows the immutable order. Before each target call, the tool
atomically writes and flushes a `goodq.clean-memory-execution-journal.v1` entry
with `intent_recorded`; immediately after the call it atomically records the
bounded observed result. An already-absent target that was absent in the plan
is journaled as `skipped_absent` without mutation. The first deletion or
identity-check error stops the run; later targets remain `unattempted`.

The journal is the crash boundary. An interruption after intent but before a
result never becomes success from later absence alone; it becomes
`indeterminate_side_effect`, sets `side_effects_may_have_occurred=true`, and
prevents remaining deletion. The used token is never reused and the same apply
does not resume. Any later destructive continuation requires a new plan, job,
and approval against the new state.

After execution or failure, the tool atomically writes a
`goodq.clean-memory-receipt.v1` receipt containing:

- plan/job/authorization identity and plan digest;
- per-target `completed`, `skipped_absent`, `failed`,
  `indeterminate_side_effect`, or `unattempted` status;
- the first bounded failure code without raw local path or exception leakage;
- exact-target post-state plus bounded protected-boundary identity comparison;
- disposition and rollback references; and
- `side_effects_may_have_occurred=true` whenever finalization cannot prove a
  clean terminal outcome.

The tool records MiniAgent external execution audit before terminalizing the
job. Audit/finalization failure after a mutation is itself a failed job and may
not be blindly retried. After acquiring the exact same cleanup lease
nonblocking, `reconcile` may adopt a prior-owner nonterminal job, inspect the
exact journal/plan/receipt, record a missing external execution audit, and
terminalize the existing job from already-proven evidence. Lease contention
returns `cleanup_active` with byte-for-byte unchanged recovery evidence. It
never changes a terminal job, never upgrades an indeterminate or failed
mutation to success, and never executes an unattempted target. Crash points
before a target call, after side effect/before result persistence, after
receipt/before audit, and after audit/before job terminalization all have
explicit outcomes.
Any receipt containing `failed` terminalizes the job as `failed`; any receipt
containing `indeterminate_side_effect` terminalizes it as `interrupted` with
`side_effects_may_have_occurred=true`. Neither outcome can later become
`succeeded`.

## Mutation-Sensitive RED Contract

Create temporary-root authority tests before production implementation. The
suite must prove:

1. import purity and read-only candidate `plan` operation without a production
   approval registry, job, token, or target mutation;
2. production `approve` and `apply` reject valid-looking fixture artifacts with
   `r23_authority_unavailable` before artifact resolution, job creation,
   MiniAgent construction, or mutation; test verifiers are core-only injections
   with no CLI/env fallback; when verifiers are registered, incomplete rollback
   coverage is checked only against the persisted exact plan and refuses before
   job/token creation;
3. deterministic job-independent authority hashing and one stable plan file
   under repeated and concurrent identical planning;
4. repeated/concurrent approval converges on one active exact-scope job;
   pre-token failure terminalizes it for retry, post-token persistence failure
   revokes the token, and revocation failure is durably fail-closed with no
   returned or usable apply path; an approve-versus-reconcile interleaving proves
   the pending record is never visible without complete initial authorization
   metadata; crash witnesses cover before atomic job creation, after atomic job
   creation/before issuance, issuance before fingerprint persistence, and
   fingerprint persistence before delivery; unresolved challenges block until
   their bound MiniAgent deadline, then one atomic pending-to-expired winner
   permits a new attempt;
5. exact configuration/epoch derivation with no arbitrary delete or report
   path;
6. control-evidence-root containment and rejection when it is under the epoch,
   under a recovery payload/protected-data ancestry, or redirected by a
   junction/reparse point;
7. root, `..`, symlink, junction, and reparse rejection while outside canaries
   remain byte-for-byte unchanged;
8. a mid-execution ancestor swap to a junction/reparse point stops before target
   N and preserves the outside canary;
9. exclusion of source media, processing, models, reports, controls, Qdrant
   storage, other epochs, and repository content using bounded structural/root
   identity evidence rather than an unperformed whole-corpus hash;
10. disposition schema/hash/scope equality plus hard rejection of retained,
    promoted, active, unknown, expired, or conflicting lifecycle evidence;
11. rollback coverage for every present file and exact collection, supported
    restore schema, pre-plan snapshot time, snapshot integrity, and rejection
    for one missing file/collection, stale/mismatched snapshot, unsupported
    restore format, a control record inside destructive ancestry, or a recovery
    payload outside the registered protected backup authority;
12. exact equality of the configured four-name map and plan target set, URL
    encoding, canonical loopback-only endpoint, redirect rejection, missing or
    extra configured-target rejection, full point-state/generation/config/
    snapshot fingerprinting, and fake/in-memory failure/absence behavior;
    unrelated and prefix-similar server collections remain untouched canaries;
13. mandatory regular-file content digests catch same-size/same-mtime
    substitution, and immediate Qdrant revalidation catches delete/recreate
    drift before deletion;
14. dry-run/plan cannot stop processes or mutate targets;
15. changed configuration or target state blocks before the first deletion;
16. absent/malformed/nonexclusive production quiescence authority and
    active-worker evidence refuse without WSL/status side effects, process-name
    heuristics, or termination; writer-start-after-preflight,
    recreate-after-reprobe, and same-ID payload/vector update cases cannot cross
    the held lease or otherwise keep Qdrant apply enabled; a live apply versus
    reconcile witness proves lease contention permits no owner adoption or
    job/journal/receipt/audit evidence change;
17. exact MiniAgent registration matrix and operation/scope, no native handler,
    token mismatch, bounded absolute expiry, missing/malformed/overlong expiry
    rejection, exact echoed request-ID/deadline equality,
    wrong-request-ID/wrong-deadline claim rejection, reuse, revocation, atomic
    claim, logical audit target, external outcome recording, and unchanged
    behavior for existing callers that omit the optional cleanup-only binding;
18. one active action job and one apply winner under concurrent unique-owner CLI
    processes; one-lock expected-owner plus expected-state transition behavior
    for pending, authorizing, queued, and running states; an interleaving witness
    that would fail under separate owner adoption/state transition;
    crash-after-token-claim recovery; stale-transition rejection; and terminal
    immutability;
19. idempotent handling only for targets planned absent;
20. injected failure at target N stops immediately and leaves N+1 unchanged;
21. per-target journal/partial receipt distinguishes `completed`,
    `skipped_absent`, `failed`, `indeterminate_side_effect`, and `unattempted`
    targets with the required failed/interrupted terminal outcome;
22. crash witnesses cover before call, after side effect/before result write,
    after receipt/before audit, and after audit/before job terminalization;
23. `reconcile` performs no deletion, never reuses a token, acquires the same
    exclusive lease before non-pending recovery, finalizes only already-proven
    nonterminal state, and never changes a terminal failed job;
24. post-state is bound to the plan and proves only the bounded protected
    identities/canaries actually observed;
25. audit or receipt-finalization failure preserves observed side-effect truth;
26. an explicit active-cleanup-surface allowlist covers the workflow, guide,
    both skill copies, evidence-first workflow, `SUPPORT.md`, both README pointers,
    `AGENTS.md`, authority map, communications index, file index, and codebase
    index; reference discovery follows active links and fails on any additional
    inbound pointer or transitive route to archived destructive guidance;
27. executable blocks in those active instruction surfaces allow only the
    verified `python -m cli.clean_memory` commands and contain no manual
    filesystem deletion, Qdrant collection deletion, prefix matching, process
    stopping, or superseded executor invocation; generated indexes contain no
    retired-script entry; and
28. tests never resolve configured data, live Qdrant, services, models, WSL,
    identity, source media, the public checkout, or operator reports.

Focused files are expected to include:

- `tests/unit/test_clean_memory_authority.py`;
- `tests/unit/test_clean_memory_cli.py`;
- focused additions to MiniAgent authorization/audit tests; and
- documentation authority/reference-discovery tests proving every active
  cleanup surface allows only the verified CLI and preventing any manual,
  prefix-wide, or superseded-executor procedure from returning.

## Implementation And Documentation Scope

The implementation seam may touch only:

- new `steps/common/clean_memory.py` and `cli/clean_memory.py`;
- the MiniAgent contract/client registration required for the authorization-only
  `clean_memory.apply` operation and the generic bounded-expiry challenge
  metadata described above;
- the focused generic `ActionJobLedger.adopt_and_transition()` primitive,
  optional atomic initial metadata, validated authorization-expiry metadata,
  and their unit tests;
- focused temp-root, authority, audit, and documentation tests;
- removal of the two superseded clean-slate scripts and their stale existence
  assertion after the new behavioral suite passes; and
- the active workflow, both operator-skill copies, active guide, evidence-first
  workflow, removal of the archived uninstall link from `SUPPORT.md`, both
  README pointers, `AGENTS.md`, the authority/communications
  maps, and the generated file/codebase indexes.

The current source trace already proves the missing generic lifecycle invariant:
owner adoption and state transition are separate locked writes. No other
`api/utils/action_jobs.py` behavior may change. API/UI routes, process launchers,
collection initialization, ingestion, identity, promotion, architecture,
dependencies, live services, configured data, mixed main, public checkout, and
R-23 retention utilities remain outside this seam.

## Replacement Sequence

1. Checkpoint this reviewed selection before code begins.
2. Add the temp-root RED authority suite and prove the intended failures.
3. Implement the pure core and CLI minimally.
4. Add/reuse MiniAgent authorization-only and action-job evidence.
5. Pass focused tests and static gates without configured/live access.
6. Retire the two competing legacy clean-slate scripts.
7. Replace manual guidance in the workflow and both skill copies; align the
   active guide and evidence-first semantic rule; verify navigation pointers.
8. Run independent implementation and documentation reviews.
9. Checkpoint R-07 only after every completion gate is fresh and green.

No real cleanup, collection initialization, re-ingestion, or retention action
is an R-07 verification step.

## Independent Review Closure

Three independent read-only review lanes reread the final selection, bounded
mission, and roadmap block and returned clean current-byte verdicts:

- instruction/reference review proved every direct active cleanup surface and
  the transitive `SUPPORT.md` route to archived uninstall guidance are covered;
- lifecycle/census review closed candidate-plan versus retention-evidence
  separation, exact Qdrant canaries, atomic owner/state transition, and
  apply/reconcile lease fencing; and
- approval/RED review closed atomic initial authorization metadata, every token
  issuance/delivery crash window, exact deadline recovery, cleanup-only
  MiniAgent binding, and legacy-caller compatibility.

The reviews required corrections before accepting the selection. No reviewer
edited repository files, and no implementation began during review.

## Evidence Boundary

This selection used source, tests, configuration declarations, current
authoritative documentation, and three independent read-only audits. No
configured data root, database, Qdrant endpoint, model, cache, service, process,
identity store, WSL distribution, mixed main tree, or public checkout was read
or mutated.
