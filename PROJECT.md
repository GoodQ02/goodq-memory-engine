<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — reject duplicate protected identity envelopes.

## Outcome

Close one proven candidate-plan validation gap: two different protected roles
must not carry byte-identical canonical identity JSON envelopes. Add the smallest
RED oracle and validation change without resolving paths, observing a
filesystem, or altering the protected-boundary evidence type.

## Governing evidence

- candidate-plan checkpoint `c870a1cb`
- protected-boundary audit checkpoint recorded in
  `docs/diagnostics/R07_PROTECTED_BOUNDARY_AUTHORITY_AUDIT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Every protected role and logical ID is unique, and distinct roles cannot carry
the same canonical identity JSON envelope. Candidate-plan construction rejects
that exact duplicate before producing authority output; later observation still
owns physical-alias detection across different envelopes.

## Exact implementation scope

- Add one focused test that assigns one role's valid canonical identity JSON to
  a different role while keeping roles and logical IDs distinct.
- Require `build_candidate_plan()` to reject that scope before returning a plan.
- Preserve existing valid construction and round-trip behavior.
- Run the focused authority suite and the established candidate-plan union.

## Boundaries

- Touch only `steps/common/clean_memory.py`,
  `tests/unit/test_clean_memory_authority.py`, and checkpoint documentation.
- Do not change `ProtectedBoundaryEvidence`, public APIs, schemas, configuration,
  filesystem observers, manifest authority, Qdrant, persistence, jobs, tokens,
  MiniAgent, or cleanup execution.
- Do not inspect configured/live roots or services.
- Do not combine the later protected-authority manifest projection into this
  seam.

## Completion gate

The focused duplicate-envelope RED turns green; existing valid authority and
round-trip tests remain green; compilation, import-purity, documentation,
semantic-drift, banned-token, dependency, and diff gates pass; independent
current-byte review finds no broader change. Checkpoint separately before any
explicitly approved protected-authority implementation begins.
