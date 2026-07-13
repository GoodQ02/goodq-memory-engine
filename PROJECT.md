<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — select the passive clean-memory `plan` orchestration seam.

## Outcome

Run one read-only no-repeat audit of the production authorities needed to turn
an exact configured epoch into injected `ResolvedCleanupScope` evidence for the
completed immutable-plan core at checkpoint `c870a1cb`. Select the smallest next
implementation seam only after proving which existing configuration, path,
filesystem-identity, Qdrant-fingerprint, and evidence-root helpers are reusable
and which invariants are still absent.

## Governing evidence

- `docs/diagnostics/R07_CLEAN_MEMORY_REPLACEMENT_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`
- `steps/common/clean_memory.py`
- `tests/unit/test_clean_memory_authority.py`
- private candidate-plan checkpoint `c870a1cb`

## Governing invariant

`plan` accepts one exact configured epoch, derives every target from canonical
configuration, performs only passive exact-scope observation, and supplies the
completed core with explicit evidence. It creates no action job or token,
resolves no disposition or rollback artifact, starts or stops no process,
follows no redirect or reparse point, and mutates no cleanup target.

## Scope

- Reconcile existing configuration and runtime-path loaders, exact epoch and
  four-collection naming, control-evidence-root ownership, filesystem platform
  identity and digest helpers, Qdrant configuration/generation or complete
  point-state fingerprint helpers, and established CLI orchestration patterns.
- Prove which helpers are import-pure, passive, exact-scope, redirect-safe, and
  suitable for reuse without weakening `c870a1cb`.
- Record the no-repeat result, missing contracts, proposed next file/test
  allowlist, and one smallest coherent implementation seam.
- Update the roadmap only if the fresh evidence changes dependency order or
  closes the audit selection.

## Boundaries

- This mission is read-only except for `PROJECT.md`, one focused clean-memory diagnostic
  evidence document, and a roadmap checkpoint after independent review.
- Do not implement `cli.clean_memory`, a production adapter, or any
  approve/apply/reconcile/status behavior during this audit.
- Do not read configured data, databases, FAISS content, Qdrant state, services,
  models, ingestion, identity, WSL, public checkout, or mixed main.
- Do not create evidence roots, action jobs, tokens, reports, receipts, leases,
  or temporary production configuration.
- Do not reopen the candidate-plan, MiniAgent, or action-job checkpoints unless
  contradictory evidence proves one of their stated invariants false.

## Completion gate

A focused diagnostic names every required passive `plan` input, the existing
authority (or proven gap) for each, the exact next implementation boundary, and
the tests that will prove no configured/live access. A fresh source/test trace
and independent read-only review must agree that the selected seam neither
duplicates completed work nor crosses into authorization, execution, retention,
or service ownership.
