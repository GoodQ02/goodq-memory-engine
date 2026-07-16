<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05 Temporal-Summary Authority Checkpoint

## Outcome

Temporal-summary generation no longer executes synchronously from an ordinary
Retro Console request. One explicit operator confirmation now authorizes one
exact normalized request, one private persistent job, one verified execution
policy, and one exact-job result. The API exposes only passive status/result
projection after confirmation; it never silently reruns inference during
recovery.

This checkpoint closes the last directly owned local-operator authority seam
under R-05. It does not relabel the remaining retrieval, identity, or status
effects as repaired or passive. Those effects remain truthfully classified,
remotely denied, and assigned to their existing roadmap owners.

## Authority Model

- The accepted request is normalized to exactly `entities`, `start_date`,
  `end_date`, `time_hint`, `source_file`, `modality`, `max_results`, `grouping`,
  and `summary_style` before hashing or authorization.
- The persistent job scope contains the epoch, canonical request digest, and
  sanitized execution-policy digest. MiniAgent confirmation additionally binds
  the exact job ID.
- Raw request content remains an immutable in-memory worker input. It is not
  copied into the action ledger, MiniAgent scope, external audit, or public job
  projection.
- One verified configuration snapshot supplies the epoch, retrieval engine,
  summarizer, model candidates, loopback endpoints, explicit activation policy,
  and environment-proxy policy.
- Temporal execution disables ambient environment proxies and permits model
  activation only when the confirmed policy explicitly allows it.
- Results are stored under the configured private data authority in a locked,
  atomic, exact-job receipt bound to job, request, epoch, and policy digests.

## Lifecycle and Recovery Invariants

- Prepare persists `pending_confirmation` before issuing a single-use token and
  performs no retrieval, client construction, health probe, activation, or
  inference.
- Confirm must resubmit the complete normalized request and pass the exact
  MiniAgent scope before the worker may claim execution.
- The worker revalidates authorization evidence, request digest, job root,
  epoch, and execution policy before any model work.
- Success ordering is result receipt, then generic external audit, then terminal
  job transition. Receipt persistence failure stays nonterminal rather than
  fabricating success or failure truth.
- Startup reconciliation adopts only exact, valid evidence. A valid receipt can
  reconcile a prior queued/running owner without replay; a missing receipt
  interrupts prior execution; malformed or misbound evidence fails visibly.
- Passive exact-job GET creates no job or directory. Succeeded jobs require a
  valid receipt; explicitly enumerated pre-execution failures may project without
  one.
- Generic audit append is not claimed exactly once across a crash window.
  Potential duplicates remain correlatable by authorization request ID and
  target; generic audit idempotency remains outside this checkpoint.

## Retro Console Contract

- Native operator confirmation occurs before server prepare.
- Prepare and confirm send the complete explicit nine-field request.
- The confirmation token is kept only in local flow state and is cleared in a
  `finally` boundary.
- Polling is limited to the exact encoded job and validates job, scope, and
  receipt binding before success.
- A generation nonce prevents an older asynchronous request from overwriting a
  newer operator action.
- Confirm-time conflicts recover exact bound state: expired, failed,
  interrupted, pending, running, success, and audit-warning outcomes remain
  distinct.
- Rendered browser/viewport verification remains deferred to the integrated
  browser gate; this checkpoint proves the static UI contract and JavaScript
  syntax only.

## Checkpoint Commits

| Commit | Evidence seam |
|---|---|
| `8fe22b48` | Selected temporal summarization as the last eligible direct R-05 seam |
| `a6292888` | Added private locked exact-job result authority |
| `fa5599d6` | Registered exact-scope MiniAgent authorization and audit evidence |
| `366512b3` | Bound retrieval and summarization to one verified runtime snapshot |
| `0ff34af5` | Enforced explicit model activation and proxy policy |
| `1c5e05f6` | Added governed prepare/confirm/worker/result/recovery routes |
| `578abcc4` | Migrated Retro Console to confirmation and durable polling |

## Review Findings Closed

Independent read-only reviews identified and verified closure of:

- ambient proxy inheritance outside the confirmed execution policy;
- receipt-persistence failure being terminalized before durable truth existed;
- overlapping Retro requests permitting stale asynchronous output; and
- confirm-time conflicts collapsing expired or failed job truth.

The generic append-only audit crash window was retained as an explicit
limitation rather than incorrectly promoted to exactly-once delivery.

## Fresh Integrated Evidence

The final private R-05 regression union was derived from every test file changed
since the verified MiniAgent authority foundation. It covers ingest staging,
route effects, action jobs, video summary, summary collections, temporal
summary, MiniAgent audit, API harness truth, and both operator UI contracts:

```text
798 passed in 48.02s
```

Additional fresh gates passed:

- 382 temporal/MiniAgent/route/UI tests before the inherited union;
- the independent mounted registry and OpenAPI projection oracles (`2 passed`);
- Python compilation for every Python file changed by the temporal commit range;
- JavaScript syntax validation for Retro Console;
- branch-range whitespace/diff validation;
- documentation authority, index, drift, banned-token, secret-surface, and
  portable-path gates after checkpoint publication.

The executable route census is now:

| Effect | Count |
|---|---:|
| `passive_read` | 40 |
| `request_staging` | 1 |
| `automatic_mutation` | 11 |
| `curated_mutation` | 8 |
| `process_execution` | 9 |
| **Mounted method/path operations** | **69** |

Sixty-seven operations are OpenAPI-published; `/docs` and `/redoc` account for
the other two. The total route-object count is 77 after `/openapi.json` and the
seven static mounts are included.

## Boundary Accounting

No live endpoint, model, WSL process, service, configured data root, Qdrant
collection, ingestion state, identity state, source media, operator data, public
checkout, or frozen mixed checkout was exercised or changed. Tests used
temporary roots and mocked model/process boundaries.

Temporal result cleanup and retention remain with the corpus/retention roadmap
owner. Live inference, service rollback, and model shutdown were not exercised
and are not claimed by this checkpoint.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory focused evidence:

- temporal request normalization, hashing, or exact confirmation scope;
- the private exact-job result store or result-before-terminal ordering;
- runtime snapshot, loopback endpoint, activation, or proxy-policy binding;
- prepare/confirm/worker/passive-result route authority;
- deterministic receipt/no-replay startup reconciliation; or
- Retro confirmation, token disposal, generation nonce, exact polling, and
  terminal-state rendering.

## R-05 Disposition and Remaining Owners

R-05's directly owned local-operator authority seams are verified. Remaining
effectful operations stay truthfully classified and remotely denied under:

- R-05-F1 for hidden retrieval, ingest-status, and summary-read mutation;
- R-08 for identity read/write/process authority and durable recovery;
- R-14 for passive status probing; and
- R-23 for temporal result retention and cleanup policy.
