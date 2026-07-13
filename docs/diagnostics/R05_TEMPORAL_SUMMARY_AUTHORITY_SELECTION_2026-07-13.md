<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05 Temporal-Summary Authority Selection

## Outcome

The next bounded R-05 implementation seam is:

- `POST /api/search/temporal/summarize`

Fresh mounted-code comparison found no smaller eligible R-05 mutation or
execution seam. The six remaining curated mutations and two remaining identity
processes are owned by R-08. The five nominal status executions are owned by
R-14. Temporal summarization is therefore selected by current ownership and
dependency evidence, not by automatic continuation from the prior checkpoint.

This was a read-only selection audit. No endpoint, model, process, job, service,
configured data root, or operator data was exercised.

## No-Repeat Boundary

The following verified work remains closed unless contradictory evidence is
found:

- governed ingest staging and the common loopback route/client boundary;
- MiniAgent exact-scope, single-use confirmation and generic external-outcome
  audit;
- the generic action-job lifecycle and startup owner reconciliation;
- video-summary authorization, target-scoped execution, recovery, result truth,
  and Summary Console polling;
- summary-collection strict persistence, confirmation, recovery, and UI flows.

This seam must reuse those authorities. It must not create a second token,
audit, job lifecycle, or remote-client policy.

## Fresh Mounted Evidence

### Current execution truth

- `api/routes/search.py::summarize_temporal()` accepts a loose request and calls
  `retrieval.narrative_summarizer.synthesize_narrative()` synchronously.
- `synthesize_narrative()` performs temporal retrieval, builds prompts,
  constructs `LLMClient`, calls the model, and returns one in-memory dictionary.
- `LLMClient` performs immediate health checks. A failed check may start WSL
  vLLM or the local Ollama launcher before the current route returns.
- The route exposes raw exception detail, and the current result can include
  source paths.
- Retro Console calls the POST directly and retains the result only in the DOM.
  It has no confirmation, job identifier, polling, reload truth, or restart
  recovery.
- `api/route_effects.py` correctly classifies the POST as
  `process_execution`, and the common client boundary already denies remote
  invocation before body consumption.

### Missing durable truth

The current operation has no persistent action record and no private result
record. A dropped response, browser refresh, worker failure, or API restart
therefore loses the only outcome projection. The generic action-job ledger is
not a result store: it intentionally permits only scope, token fingerprint,
authorization request identifier, sanitized outcome, and audit status.

Inference is an external effect and cannot be meaningfully rolled back. The
correct recovery boundary is to persist exact result evidence before terminal
job success, reconcile from that evidence after restart, and never silently
repeat inference.

## Remaining-Authority Comparison

| Candidate | Current owner and dependency | Selection result |
|---|---|---|
| Temporal summarization | R-05 process authority; needs confirmation, durable result truth, restart reconciliation, and Retro migration | Selected |
| Six identity curated mutations | Multi-sink identity writes require R-08 atomic persistence, recovery, path precedence, and redaction first | Exclude until R-08 |
| Face rebuild and roster validation | Identity subprocess identity and crash recovery are inseparable from R-08 | Exclude until R-08 |
| Five nominal status executions | R-14 must remove side effects and prove passive status; adding confirmation would preserve the wrong behavior | Exclude until R-14 |

## Selected Authority Contract

### Strict request and exact scope

1. Replace the loose request boundary with one extra-forbid, bounded,
   deterministic normalized request contract. Every accepted field, including
   summary style, participates in a canonical SHA-256 digest.
2. Raw entities, time hints, source paths, prompts, narrative text, and bearer
   material must not enter the action job, MiniAgent scope, or generic audit.
3. Bind authorization to exactly the generated job identifier, active epoch,
   request digest, and a sanitized execution-policy digest. The policy digest
   covers the resolved local model candidate set and whether local service
   activation is permitted, without persisting endpoints, paths, or secrets.
4. Confirm resubmits the complete normalized request in addition to the exact
   prepared job, epoch, digests, and token. The server recomputes both digests
   from the resubmitted request and current server truth and fails closed on any
   mismatch. The raw request remains request-local and is not persisted in the
   job or audit.

### Prepare and execution ordering

1. Prepare creates `temporal_summary.generate` in `pending_confirmation` before
   MiniAgent token issuance and persists the authorization request identifier
   and token fingerprint before returning the token.
2. Prepare performs no temporal retrieval, `LLMClient` construction, health
   check, service activation, model call, or result-store write.
3. Confirm claims the exact single-use authorization before `queued`, then
   passes one immutable in-memory copy of the validated normalized request to
   the worker. Queued/running work is never replayed after restart, so no second
   durable prepared-input authority is introduced.
4. Immediately before retrieval, the confirmed worker loads one configuration
   snapshot, re-derives active epoch and execution-policy digests, and compares
   them with the job scope. Drift persists a sanitized failed result without
   retrieval, client construction, health checks, or service activation. The
   same verified snapshot supplies the epoch-bound paths and model policy used
   by retrieval and client construction; neither layer reloads ambient config.
5. Only that worker may enter `running`, perform retrieval, construct the
   client, or activate an allowed local model service. Execution is
   asynchronous. The confirm response returns the durable job projection;
   Retro Console polls only the encoded exact job identifier.

### Private result authority

1. Add a dedicated versioned result store below the configured data root at
   `control/temporal_summary_results`. Do not widen the generic job schema to
   hold narrative payloads.
2. One locked, atomic, exact-job record binds schema version, job identifier,
   epoch, request digest, execution-policy digest, timestamps, terminal result
   kind, sanitized narrative result or failure code, source scene identifiers,
   truthful model evidence, and a canonical result digest.
3. The private record must not retain the raw request or source filesystem
   paths. Narrative and scene text remain private derived operator data and must
   never enter generic job or audit projections.
4. Retain each result with its job record. No automatic expiration or cleanup is
   introduced before R-23 defines retention and deletion authority.
5. Add one passive exact-job GET. It validates ledger, scope, and result-digest
   binding and never creates, reconciles, adopts, expires, or retries work.

### Outcome and recovery ordering

1. A worker moves `queued -> running`, observes the model outcome, atomically
   persists the exact-job result receipt, records the generic external outcome,
   then writes the terminal ledger transition.
2. Audit failure after a persisted result must preserve observed result truth
   and terminal state with `audit_status=failed`; it must not erase or rerun the
   result.
3. Startup may recover a complete prior `authorizing` claim using the existing
   R-05 rules. A valid result receipt written before terminal transition is
   reconciled to its recorded terminal result without rerunning inference.
4. Prior-owner `queued` or `running` work without a valid result becomes
   `interrupted`. A terminal success with a missing, malformed, or mismatched
   result fails closed on the passive projection and is never fabricated.
5. Activated model services are shared runtime effects. Recovery must not stop
   or roll them back; it records only this job's observed execution truth.

### Browser truth

Retro Console must:

- obtain explicit native confirmation before prepare;
- resubmit the exact prepared job, epoch, request digest, policy digest,
  complete normalized request, and raw token only for confirm;
- clear every token copy after the confirm attempt;
- poll the exact passive job/result projection;
- show success only for durable `succeeded` plus a validated result receipt;
- distinguish failed, interrupted, expired, audit-failed, and invalid-result
  outcomes without exposing raw exceptions or paths.

The old synchronous success/`llm_unavailable` response is removed rather than
retained as a second compatibility authority.

## Exact Owner Files

Production ownership is limited to:

- `agents/mini_agent_client.py`
- `api/routes/search.py`
- `retrieval/narrative_summarizer.py`
- `retrieval/temporal_reasoning.py` only to consume the worker's verified
  configuration/epoch snapshot instead of reloading ambient config
- new `api/utils/temporal_summary_results.py`
- `ui/retro_console_v1/static/js/retro.js`
- `api/route_effects.py` for the new passive exact-job operation

Reuse `api/utils/action_jobs.py` unchanged unless a generic defect is proven by
a failing regression. Treat `lib/llm_client.py` as inspect-only unless the
confirmed execution-policy contract cannot be enforced at the caller boundary.

Focused test ownership is:

- `tests/agents/test_mini_agent_client.py`
- `tests/agents/test_mini_agent_audit.py`
- `tests/unit/test_narrative_summarization.py`
- new `tests/unit/test_temporal_summary_authority.py`
- new `tests/unit/test_temporal_summary_results.py`
- new `tests/unit/test_retro_console_static.py`
- `tests/unit/test_api_route_effect_authority.py`

## Required Implementation Evidence

Before checkpointing, temporary-root and mocked-process tests must prove:

- extra, malformed, unbounded, or changed request fields fail before token
  issuance or execution;
- missing, expired, reused, wrong-operation, wrong-job, wrong-epoch,
  wrong-request, and wrong-policy confirmation fails before client construction;
- no prepare path constructs `LLMClient`, probes health, starts a service,
  performs retrieval, or writes a result;
- post-confirm/pre-worker epoch or execution-policy drift fails before
  retrieval or client construction, and both retrieval and model construction
  consume the same verified configuration snapshot;
- only one worker may claim an exact active scope under concurrent requests;
- request, token, path, prompt, narrative, exception, and subprocess detail is
  absent from job, audit, error, and public response surfaces;
- result flush, replace, post-write inspection, audit, and terminal-ledger
  failure windows preserve exact observed truth and deterministic recovery;
- restart never silently repeats inference and never invents a successful
  result;
- the exact-job GET is passive under an absent or immutable result root;
- Retro Console confirms, clears tokens, polls, and renders every durable state
  accurately;
- the POST remains `process_execution`, the new GET is `passive_read`, and the
  common remote denial remains green.

Focused tests run before the inherited integrated R-05 gate. Python
compilation, JavaScript syntax, route-effect, secret-surface, portable-path,
diff, and documentation checks remain required. No live model, service, API,
configured data root, or operator data is needed for this seam. Rendered browser
verification remains deferred to the integrated browser gate.

## Explicit Exclusions

This seam must not change:

- identity routes, stores, subprocesses, recovery, redaction, or Workbench UI;
- status, WSL, GPU, or passive-probe behavior;
- video-summary or summary-collection authorities;
- ingest staging, retrieval side-effect follow-up R-05-F1, Qdrant, SQLite core
  data, manifests, source media, active services, or configured data;
- generic job schema, MiniAgent token format, or common remote-client policy
  without a separately proven generic defect.
