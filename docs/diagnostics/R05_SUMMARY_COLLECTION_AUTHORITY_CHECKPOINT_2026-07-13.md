<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05 Summary-Collection Authority Checkpoint

## Outcome

Summary Console collection create and soft-delete now cross one governed
operator boundary instead of mutating the overlay directly. Both actions require
explicit browser confirmation, an overlay-write-free server prepare, exact-scope
MiniAgent confirmation, durable redacted outcome evidence, and a validated
confirmed response before the UI reports success. Create prepare establishes
authority evidence; delete prepare additionally persists its pending
control-ledger job. Neither prepare mutates the collection overlay.

The collection overlay now has one strict store owner with cross-process
serialization and atomic replacement. Soft-delete additionally has persistent
job truth and exact crash reconciliation. SQLite core memory, Qdrant, scene
manifests, temporal indexes, ingestion outputs, identity state, source media,
models, and services remain outside this seam.

This checkpoint closes the selected summary-collection seam. It does not close
all of R-05.

## Authority Model

### Create

- MiniAgent authorization-only operation: `create_summary_collection`.
- Confirmed scope: exactly `action_id`, `epoch_id`, and the canonical
  `payload_sha256`.
- Raw collection names, descriptions, scene text, paths, and bearer tokens do
  not enter the authorization or external-audit scope.
- Prepare is write-free. Confirm revalidates and rehashes the same collection
  payload before the overlay mutation.
- The create history entry persists the immutable action ID, canonical payload
  digest, and authorization request ID. The public projection omits private
  authorization evidence.
- Reused-token recovery accepts only exact persisted create evidence and never
  replays the mutation.

### Soft-delete

- Durable job operation: `summary_collection.delete`.
- MiniAgent authorization-only operation: `delete_summary_collection`.
- Confirmed scope: exactly `job_id`, `epoch_id`, `collection_id`, and the
  expected canonical record digest.
- Ledger states used by this synchronous destructive action are
  `pending_confirmation`, `authorizing`, `queued`, `running`, `succeeded`,
  `failed`, `interrupted`, and `expired`.
- The active collection and its record digest are rechecked after confirmation
  and under the store lock before soft-delete.
- The record is preserved with `status=deleted`; its history persists the job
  ID, expected record digest, and authorization request ID.
- Startup reconciliation uses exact ledger, authorization, collection, digest,
  state, and history evidence. It never fabricates an event or silently retries
  a mutation.

### Shared audit and outward truth

- Both actions reuse `goodq.tool-audit.v1`; no second token or audit authority
  was introduced.
- A pre-effect authority failure blocks the overlay write.
- A post-effect audit failure preserves committed mutation truth and returns
  `audit_status=failed` rather than pretending the mutation failed.
- Public responses exclude bearer tokens after prepare, request IDs, token
  fingerprints, owner instances, paths, and raw exception details.
- Both mounted operations remain `curated_mutation` behind the verified common
  loopback client boundary.

## Store and Recovery Invariants

1. Strict load and schema validation fail closed on malformed existing bytes.
2. One cross-process lock spans load, validation, mutation, replacement, and
   post-write inspection.
3. Writes use a unique same-directory temporary file, flush, file sync, atomic
   replacement, and directory sync where the platform supports it.
4. The writer strict-loads and compares both the flushed candidate and the
   replaced authoritative file. Failed post-replace inspection restores the
   prior bytes or removes a failed first write before returning failure.
5. A failed restoration raises a distinct manual-recovery error and never
   reports silent success. When prior bytes existed, their unique fsynced
   rollback artifact is retained; a failed first-write cleanup has no prior
   rollback artifact.
6. Flush, replace, inspection, lock, and schema failures preserve authoritative
   truth and surface the failure.
7. Collection IDs are collision-safe under concurrent creation.
8. Concurrent create/create and create/delete operations lose no update.
9. Delete is idempotent only for the exact persisted action evidence; it never
   physically removes a collection record.
10. Legacy valid overlays without private correlation fields remain readable;
   new confirmed mutations always add the required evidence.

## Summary Console Contract

- Native confirmation occurs before either prepare request, so cancellation
  issues no bearer token.
- Create resubmits exactly the prepared action, epoch, digest, token, and
  original collection payload.
- Delete resubmits exactly the prepared job, epoch, record digest, and token.
- Tokens exist only in the narrow action function. The parsed response copy and
  local variable are cleared before and after the confirm attempt.
- Create success requires the exact action, epoch, public collection, and audit
  result. Delete success requires the exact job/scope, terminal `succeeded`, and
  `collection_deleted` outcome.
- `collection_finalization_pending` is never rendered as success and is accepted
  as pending only for the exact job, epoch, record digest, and `running` state.
- Audit failure is distinguished from a fully recorded success while preserving
  the committed collection result.
- Operator-controlled collection text is no longer interpolated into the new
  success toast. The pre-existing broader `innerHTML` rendering concern remains
  outside this authority seam and is not silently treated as fixed.

## Checkpoint Commits

| Commit | Evidence seam |
|---|---|
| `835c3d69`, `b4ea87e9` | Strict atomic overlay owner and passive collection reads |
| `d4a50993`, `1f0713de` | Exact MiniAgent operations, audit scope, and rejected-scope redaction |
| `a533dd04` | Immutable create/delete mutation evidence and exact recovery finders |
| `3b5effa4` | Write-free create prepare and exact confirmed mutation |
| `da4135a9` | Persistent soft-delete request/job lifecycle |
| `7d736aaa` | Deterministic startup reconciliation without replay |
| `6c6f1d67` | Exact Summary Console prepare/confirm and terminal-only success |
| `be2e0e79` | Candidate/authoritative readback and failure-safe replacement recovery |

Each implementation task used focused RED/GREEN tests and an independent
read-only acceptance review. Review findings were corrected and re-reviewed
before checkpointing.

## Fresh Integrated Evidence

The final isolated verification invocation covered Summary Console static
contracts, summary routes, the strict collection store, full MiniAgent client
and audit files, and route-effect authority:

```text
505 passed in 37.51s
```

Additional gates passed:

- Python compilation for every changed Python source and test file.
- JavaScript syntax validation for Summary Console.
- documentation authority, links, indexes, semantic parity, and banned-token
  checks.
- branch-range whitespace/diff validation.
- bounded added-line review for secret material and literal drive roots; matches
  are limited to synthetic negative-test fixtures and rejection vocabulary.
- both routes remain `curated_mutation`, and common remote denial remains green.

No live endpoint, model, worker, service, configured data root, collection,
SQLite core table, Qdrant store, source-media artifact, or operator data was
exercised.

## No-Repeat Boundary

Do not recreate or reopen, without contradictory evidence:

- strict collection-overlay locking and durable replacement;
- collection ID collision prevention and concurrent update serialization;
- create/delete MiniAgent operation registration or common audit authority;
- create action evidence, delete job correlation, or exact receipt recovery;
- soft-delete startup reconciliation;
- Summary Console create/delete confirmation and token handling; or
- the completed video-summary authority seam.

Rendered browser/viewport QA remains with the later integrated browser gate, as
required by the selection evidence. Its absence is not evidence that the static
contract failed.

## Remaining R-05 Surface

R-05 remains `IN_PROGRESS`. Temporal summarization remains a known candidate,
but it has a distinct model-activation and durable-result boundary and is not
selected by inertia. Identity actions remain coupled to R-08 persistence and
recovery; passive-status effects remain R-14-owned; nominal read mutations
remain R-05-F1-owned.

The next bounded mission is a fresh read-only selection among the remaining
mounted curated-mutation and process-execution authorities. That selection must
name exact ownership, rollback, and verification boundaries before any new
implementation begins.
