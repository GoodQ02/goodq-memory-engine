<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — implement the non-authoritative protected-membership
projection.

## Outcome

Add one import-pure projection that validates canonical manifest structure,
merges it with the closed v1 configured-role projection, and produces the exact
detached `goodq.clean-memory-protected-membership.v1` digest selected by the
completed semantics decision.

This seam proves structural consistency only. It does not authenticate the
manifest, read the external pin, or authorize candidate planning.

## Governing evidence

- candidate-plan checkpoint `c870a1cb`
- configuration projection checkpoint `a12ceb18`
- filesystem observer checkpoint `e8961889`
- protected-boundary authority audit checkpoint `f01e03a7`
- duplicate canonical-envelope guard checkpoint `4230a910`
- source/trust decision checkpoints `8bfa5d27` and `69f4a91e`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Resolved configuration is locator/routing scope, not protected-member
authorization. Canonical membership projection is not trust-root evidence.
Only later production orchestration that directly owns the approved pin and
manifest readers may authenticate membership.

## Exact code scope

- `cli/clean_memory_protected_membership.py`
- `tests/unit/test_clean_memory_protected_membership.py`

Start with RED tests for the selected exact schema, eight manifest roles,
18-role merged order, configured positional IDs, presence/kind table, canonical
bytes, limits, lexical aliases/overlap, detached immutability, digest binding,
input-race rejection, and public API/import purity.

The implementation may accept only:

- the exact completed `ResolvedPlanConfiguration` object; and
- already-supplied canonical manifest bytes for structural validation.

It must not accept pin evidence, a trust/provenance label, a prebuilt membership
mapping, configuration/caller overrides, or an alternate manifest location.

## Boundaries

- Do not modify the completed v1 configuration projection, candidate plan,
  filesystem observer, action-job authority, MiniAgent, or approval contracts.
- Do not load configuration or inspect a manifest path. No filesystem, network,
  process, persistence, service, Qdrant, job/token, plan, or cleanup operation.
- Do not create or change a live manifest, external pin, trust-root directory,
  ACL, service, configured root, or member value.
- Do not implement the Windows enrollment/reader, pin writer, manifest reader,
  authenticated selection, shared no-follow backend, protected observer,
  Qdrant observer, runnable planning, or executor in this seam.

## Completion gate

The focused RED oracle fails for the missing behavior, then the smallest source
change passes the focused suite and the approved configuration/candidate/
filesystem authority union. Compilation, import-purity, documentation authority,
semantic-drift, banned-token, dependency, index, diff, and three independent
current-byte review gates pass before checkpointing. No live/configured member
or trust-root source is touched.
