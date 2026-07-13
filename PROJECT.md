<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — establish the governed clean-memory approval authority.

## Outcome

Implement only the shared authorization foundation selected and checkpointed at
`8ed29592`: atomic initial action-job metadata, one-lock owner/state transition,
and an operation-scoped MiniAgent request-ID/deadline binding for
`clean_memory.apply`. Prove the intended failures before changing production
code, then restore the focused suites to green without beginning cleanup CLI or
target-adapter implementation.

## Governing evidence

- `docs/diagnostics/R07_CLEAN_MEMORY_REPLACEMENT_SELECTION_2026-07-13.md`
- `api/utils/action_jobs.py`
- `agents/mini_agent_client.py`
- the active MiniAgent tool contract consumed by that client
- `tests/unit/test_action_jobs.py`
- `tests/agents/test_mini_agent_client.py`
- `docs/releases/ROADMAP.md`

## Governing invariant

One cleanup approval may exist for one exact immutable scope. Its initial
request ID and absolute deadline are born atomically with the pending job; every
lifecycle claim compares expected owner and state under one ledger lock; and
MiniAgent binds that request ID/deadline only for `clean_memory.apply` without
changing existing callers. No authorization value is stored in the action job,
and no cleanup target can be reached in this seam.

## Scope

- Add focused RED witnesses for atomic initial metadata, approve/reconcile
  interleaving, expected-owner/expected-state transition, and legacy ledger
  callers.
- Add focused RED witnesses for the exact cleanup authorization registration,
  bounded absolute expiry, echoed request/deadline equality, mismatch refusal,
  token claim/reuse/expiry, and unchanged legacy MiniAgent callers.
- Implement only the generic ledger primitives and cleanup-only MiniAgent
  contract required to make those witnesses green.
- Run the focused existing action-job and MiniAgent suites plus static gates.

## Boundaries

- Touch only `PROJECT.md`, the two named production authority modules, the
  active MiniAgent tool contract if its registration is required, the two named
  focused test modules, and the roadmap checkpoint line after verification.
- Do not add `cli.clean_memory`, `steps/common/clean_memory.py`, target adapters,
  documentation replacements, script retirement, or retention verifiers yet.
- Do not read or mutate configured data, Qdrant, databases, epochs, FAISS,
  services, models, ingestion, identity, WSL, public checkout, or mixed main.
- Do not change dependencies, API/UI routes, runtime launchers, or existing
  authorization behavior outside the opt-in cleanup operation.

## Completion gate

The new tests must first fail for the selected missing authority, then pass after
the smallest implementation. Existing action-job transitions and MiniAgent
callers remain green; concurrent preparation exposes no partial pending record;
only one owner/state claimant wins; cleanup token issuance and claim bind the
same request ID/deadline; malformed, expired, mismatched, or reused challenges
fail closed; and no cleanup target, configured runtime, or live service is
accessed. Checkpoint only after staged-diff and independent review gates pass.
