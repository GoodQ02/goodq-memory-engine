<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — decide protected-boundary authority source.

## Outcome

Obtain an explicit operator decision on one source of truth for the eight
unresolved protected roles and on its non-circular authoring and trust
bootstrap. Record the decision and exact unresolved-member semantics before any
projection, reader, observer, or runtime implementation begins.

## Governing evidence

- candidate-plan checkpoint `c870a1cb`
- duplicate canonical-envelope guard checkpoint `4230a910`
- protected-boundary authority audit checkpoint `f01e03a7`
- `docs/diagnostics/R07_PROTECTED_BOUNDARY_AUTHORITY_AUDIT_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Protected-boundary authority is explicit, integrity-bound, and independent of
environment variables, the current directory, producer defaults, sibling
checkout inference, live-ledger reconstruction, or historical documentation.
No candidate architecture becomes authority merely because it is the strongest
audited option.

## Exact decision scope

- Present the audited fixed-location machine-local manifest candidate and any
  evidence-backed alternative without implementing either.
- Require the operator to approve or reject one authority source and its
  authoring/trust bootstrap explicitly.
- If a source is approved, specify exact configured/unresolved membership,
  ordering, cardinality, member kinds, logical-ID rules, and structural-absence
  policy in the next isolated checkpoint before code is written.
- If no source is approved, keep runnable planning fail closed and update the
  roadmap with the unresolved decision.

## Boundaries

- Documentation and decision evidence only.
- Do not load configuration, inspect configured/live roots, contact services,
  or infer current protected members.
- Do not implement a manifest, fixed-location reader, shared identity backend,
  protected observer, Qdrant observer, runnable plan, persistence, approval,
  job/token, MiniAgent, or cleanup behavior.
- Do not reopen the completed duplicate-envelope guard.

## Completion gate

The operator's explicit decision and trust-bootstrap choice are recorded
without invented member semantics. The roadmap and bounded mission agree on the
next isolated seam, and documentation authority, semantic-drift, banned-token,
dependency, index, and diff gates pass before a separate checkpoint.
