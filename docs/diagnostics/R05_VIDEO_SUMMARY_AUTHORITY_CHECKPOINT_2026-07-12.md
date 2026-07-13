<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# R-05 Video-Summary Authority Checkpoint

## Outcome

Video-summary generation is no longer authorized or judged by process-local
state. One exact video and one durable job now move through the verified
MiniAgent confirmation authority, an atomic job ledger, an audited worker, and
explicit terminal states. Summary Console shows success only from durable
`succeeded` evidence.

This checkpoint closes the selected video-summary seam. It does not close all
of R-05.

## Authority Model

- Ledger operation: `video_summary.generate`.
- MiniAgent authorization-only operation: `generate_video_summary`.
- Confirmed scope: exactly `job_id` and `video_hash`.
- Ledger states: `pending_confirmation`, `authorizing`, `queued`, `running`,
  `succeeded`, `failed`, `interrupted`, and `expired`.
- Persisted confirmation evidence: SHA-256 token fingerprint and authorization
  request ID. The bearer token is returned once and is never persisted.
- Execution evidence: the existing `goodq.tool-audit.v1` decision/execution
  authority. No second token store or audit log was introduced.
- Public status: a safe projection of the exact durable job. Owner instance,
  token fingerprint, authorization request ID, paths, raw model output, and
  exception detail remain private.

## Lifecycle and Recovery Invariants

1. The pending job exists before token issuance.
2. Exact scope, owner, token fingerprint, and nonterminal state are checked
   before authorization can enter `queued`.
3. Atomic preparation and owner adoption permit exactly one creator or recovery
   winner under concurrency.
4. The worker must claim `queued -> running` before execution.
5. Only `result["success"] is True` is success. Returned failure and exception
   both persist `failed`.
6. External execution audit is attempted before the terminal transition. An
   audit failure never changes observed side-effect truth.
7. On restart, prior-owner queued/running work is audited and interrupted; it is
   never silently rerun. Incomplete authorization attempts fail visibly.
8. A complete prior pending/authorizing attempt may be explicitly recovered.
   `token_already_used` is accepted only for an adopted prior-authorizing job.
9. Status GET is passive and never creates, expires, adopts, reconciles, or
   transitions a job.
10. Summary Console polls one encoded job ID. Top-level status must agree with
    the returned job state, and only `succeeded` can display success or reload
    the generated summary.

## Worker-Input Truth

- Canonical scene IDs include the target video hash and are globally unique in
  the scene store.
- Caller-supplied and loaded scene-summary records are revalidated against the
  target video's canonical scene IDs.
- Whitespace-only summaries are unusable.
- Prompt and provenance share the same bounded record set.
- Template fallback is labeled `template`; only an actual model result is
  labeled `llm`.

## Checkpoint Commits

| Commit | Evidence seam |
|---|---|
| `cc67ebc7`, `4a1700f2` | Durable atomic action-job ledger and metadata hardening |
| `24fd860c`, `7ce93dab` | Exact external authorization and generic execution audit |
| `060aef3e`, `482e9f1b` | Target-video input, provenance, whitespace, and method truth |
| `c9228976` | Atomic preparation result and exact owner-adoption CAS |
| `d052e903`, `e2c15012` | Prepare/confirm/worker/status lifecycle and compensated authority failures |
| `0736f74e` | Complete deterministic prior-owner enumeration |
| `9c2ad4ba` | Startup reconciliation and prior-owner confirmation recovery |
| `23f32457`, `b81606ca` | Durable Summary Console polling and malformed-state rejection |

Every implementation task used focused RED/GREEN tests and an independent
read-only acceptance review. Review findings were corrected and re-reviewed
before the next mutating seam began.

## Fresh Integrated Evidence

The final isolated verification invocation covered the action-job ledger, full
MiniAgent client and audit files, video summarizer, summary routes, Summary
Console static contract, and route-effect authority:

```text
415 passed in 33.71s
```

Additional gates passed:

- Python compilation for every changed Python source/test file.
- JavaScript syntax validation for Summary Console.
- branch-range whitespace/diff validation.
- bounded added-line review for secret material and literal drive roots; matches
  were limited to rejection vocabulary and synthetic negative-test fixtures.
- the route remains classified `process_execution` and the common loopback
  boundary tests remain green.

No live endpoint, model, worker, media hash, service, Qdrant collection, memory
store, or configured data-root artifact was exercised.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory evidence:

- the generic action-job schema or state machine;
- video-summary MiniAgent registration, token flow, or execution audit;
- target-scene/provenance filtering and template-versus-LLM truth;
- video-summary prepare/confirm/status routes;
- prior-owner interruption and authorization recovery;
- Summary Console durable polling or the removal of `idle == success`.

Rendered browser/viewport QA remains a later integrated/browser gate; its
absence is not evidence that the static contract failed.

## Remaining R-05 Surface

R-05 remains `IN_PROGRESS`. The audit register still contains:

- temporal summarization, whose synchronous result and model-activation boundary
  require a separate design;
- summary collection create/delete and other curated mutations that still lack
  exact-scope common authority;
- identity operations whose shared confirmation/audit boundary is R-05-owned
  but whose persistence/recovery remains R-08-owned;
- passive-status effects owned by R-14; and
- nominal read mutations recorded under R-05-F1.

The next bounded mission is read-only selection of the smallest coherent
remaining R-05 authority seam from fresh mounted-code evidence. This checkpoint
does not choose that seam by inertia.
