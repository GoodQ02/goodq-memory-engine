<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — implement the passive target filesystem observer.

## Outcome

Implement one import-pure, fail-closed filesystem observer and its focused test
oracle. It accepts only a canonical `ResolvedPlanConfiguration` and returns one
immutable `FilesystemObservation` containing exact epoch-root identity and
filesystem-target evidence.

## Governing evidence

- configuration checkpoint `a12ceb18`
- candidate-plan checkpoint `c870a1cb`
- filesystem-observer audit checkpoint `f3ce0920`
- `docs/diagnostics/R07_FILESYSTEM_OBSERVER_BOUNDARY_AUDIT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Observation is passive evidence collection, not configuration, protected-root,
Qdrant, planning, approval, or cleanup authority. Every present file is
identified and hashed through the same verified handle. Redirected, irregular,
unsupported, inaccessible, ambiguous, or changing state fails closed and never
becomes absence or partial evidence.

## Exact implementation seam

Touch only:

- `cli/clean_memory_filesystem.py`;
- `tests/unit/test_clean_memory_filesystem.py`.

The production module exposes exactly:

- `FILESYSTEM_OBSERVATION_SCHEMA`;
- `FilesystemObservationError`;
- `FilesystemObservation`;
- `observe_filesystem`.

Implement the Windows volume-bound held-directory/OpenFileById backend and the
POSIX descriptor-relative no-follow backend defined by the governing audit.
Enumerate the six singleton roles and every regular file below the exact FAISS
root deterministically.

## Boundaries

- Do not modify `cli/clean_memory.py`, `steps/common/clean_memory.py`, or their
  completed tests.
- Do not load configuration or environment values.
- Do not read configured/live data during verification; use temporary fixtures.
- Do not access protected roots, services, Qdrant, evidence stores, jobs,
  tokens, MiniAgent, cleanup execution, or the current working directory as
  authority.
- Do not add a CLI, runnable plan, fallback pathname traversal, or partial-result
  mode.
- Do not begin protected-boundary or Qdrant implementation in this seam.

## Completion gate

Focused tests prove the full deterministic, absence, no-follow, identity,
hashing, enumeration, unsupported-platform, race, composition, and negative-
capability matrix from the governing audit. Compilation, import-purity,
documentation-authority, semantic-drift, banned-token, dependency, and diff
gates pass. At least two independent current-byte reviews return clean.

After the implementation checkpoint, advance only to a read-only audit of
protected-boundary authority. Do not advance directly to Qdrant observation.
