<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-15 -->

# Active bounded mission

Roadmap item: R-07 — implement the protected-boundary observer and direct
pin-chain physical-exclusion authority.

## Outcome

Use TDD to add the exact Windows protected-boundary observer selected in
`docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CONTRACT_DECISION_2026-07-15.md`.
Observe only injected synthetic/temporary membership in tests. Do not implement
composition, Qdrant observation, runnable planning, approval, or cleanup.

## Completed work — do not repeat

- Configuration projection, candidate planning, cleanup-target filesystem
  observation, protected-manifest validation, protected-membership projection,
  held-handle traversal and bounded reads, Windows security mechanics, reader
  identity, external-pin reading, and authenticated protected-manifest reading
  are checkpointed.
- `66ee4f47` checkpoints the authenticated protected-manifest reader and its
  exhaustive two-file regression authority.
- `f93ae143` checkpoints the shared Windows ProgramData locator and exact
  external-reader extraction parity.
- Final locator verification passed 53 direct tests, the frozen 499-test
  external suite, 148 protected-manifest reader tests, the 737-test adjacent
  authority gate, the exact 1,422-test frozen union, and the 1,623-test expanded
  authority gate.
- Independent contract and extraction-parity reviews returned `PASS`.
- Locator checkpoint evidence is recorded in
  `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_CHECKPOINT_2026-07-14.md`.
- The earlier composition audit already proved that target filesystem evidence
  is cleanup-plan pre-state, not protected-membership authentication input.
- Three independent ownership/lifecycle/contract traces selected the exact
  protected-boundary observer source/test pair, direct inputs, output carrier,
  held-handle lifecycle, physical exclusions, error taxonomy, and RED matrix.

## Governing invariant

Authenticated configuration and manifest membership describe logical protected
authority; neither proves the physical state of protected members. One future
no-follow observer must retain exact physical evidence for every protected
parent and member and reject every cross-member alias or collision with any
direct pin-chain identity before authenticated composition may return.

Lexical overlap checks and physical alias checks are distinct mandatory gates.
Neither may substitute for the other. Selected canonical path-free identities
may exist only inside the candidate-plan authority; paths, raw/native identity
detail, descriptors, names, and member content may not enter public display,
logs, representations, or errors.

## Exact implementation seam

1. add `tests/unit/test_clean_memory_protected_boundary.py` and witness the exact
   public contract and behavior fail before production code;
2. add `cli/clean_memory_protected_boundary.py` with exactly the selected three
   exports and direct-input-only signature;
3. reuse only the public held-handle backend and existing public evidence types;
4. return exactly 18 atomic canonical `ProtectedBoundaryEvidence` values; and
5. preserve every completed module and focused test unchanged.

## Governing evidence

- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_RECHECK_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_HELD_HANDLE_EXTRACTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CONTRACT_DECISION_2026-07-15.md`;
- their closed source/tests; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- Touch only the exact new source/test pair until its source checkpoint passes.
- Do not modify any completed production module or focused test, including the
  membership, pin, manifest, locator, held-handle, filesystem, or plan seams.
- Do not inspect or mutate live ProgramData, a token, ACL, descriptor,
  configured or protected root, manifest, pin, service, GoodQ data, Qdrant
  store, evidence store, job, MiniAgent, approval, or cleanup target.
- Do not change environment, service, firewall, dependency, enrollment,
  publication, rotation, recovery, or runtime state.

## Completion gate

1. the focused tests fail for the absent authority before production code;
2. focused and frozen adjacent/union gates pass through `goodq_core`;
3. exact API, import purity, direct-input, physical alias, five-pin exclusion,
   stable-absence, final-fence, no-partial, privacy, and cleanup oracles pass;
4. the staged source diff contains exactly two new files and no private import
   or duplicate completed authority;
5. at least two independent current-byte reviews are clean; and
6. source and documentation are checkpointed separately.
