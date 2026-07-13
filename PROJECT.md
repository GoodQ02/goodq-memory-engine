<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — specify approved manifest authority semantics.

## Outcome

Define the exact path-free membership schema and external-pin trust-root policy
for the operator-approved canonical manifest model before any writer, reader,
observer, projection, or runtime implementation begins.

## Governing evidence

- candidate-plan checkpoint `c870a1cb`
- configuration projection checkpoint `a12ceb18`
- filesystem observer checkpoint `e8961889`
- protected-boundary authority audit checkpoint `f01e03a7`
- duplicate canonical-envelope guard checkpoint `4230a910`
- source-decision checkpoint `8bfa5d27`
- `docs/diagnostics/R07_PROTECTED_BOUNDARY_AUTHORITY_AUDIT_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

The manifest supplies member content; an independently trusted external source
outside every protected member authorizes only the manifest's exact canonical
digest. Neither source may authenticate itself. The manifest cannot authenticate
the pin. The pin cannot supply, discover, infer, or override member content, and
it authenticates no manifest bytes except those matching that exact digest.

## Exact decision scope

- Define the exact eight unresolved role names and their relationship to the ten
  configured roles without modifying the completed v1 configuration projection.
- Define member IDs, ordinary object kinds, cardinality, deterministic ordering,
  required/optional presence, structural-absence rules, and multi-member
  representation.
- Define lexical and canonical duplicate rejection and the later physical-alias
  observer handoff without importing or copying private observer backends.
- Define how the new selection contract accepts or rejects the completed v1
  projection's existing resolved-config provenance without modifying v1.
- Select the external pin's logical source, provenance, effective-access-
  identity, owner, access-control, first-publication, rotation, and recovery
  contract without creating or changing that source.
- Preserve separate operator actions for manifest publication and pin
  authorization.

## Boundaries

- Repository source, tests, contracts, and platform-capability evidence may be
  inspected read-only. No configured or live protected root may be loaded,
  inferred, enumerated, or contacted.
- Documentation and decision evidence only. Do not implement or publish a
  manifest, pin, schema, projection, writer, reader, observer, runnable plan,
  persistence, approval, job/token, MiniAgent, or cleanup behavior.
- Keep the completed configuration, observer, candidate-plan, and duplicate-
  envelope checkpoints closed.

## Completion gate

One exact schema/member contract and one non-circular external-pin trust-root
contract are recorded without live member values. The roadmap names the first
isolated implementation seam, and documentation authority, semantic-drift,
banned-token, dependency, index, and diff gates pass before checkpointing.
