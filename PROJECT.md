<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — implement the shared Windows ProgramData locator authority
with exact external-reader extraction parity.

## Outcome

Use TDD to add the exact import-pure shared locator module and adapt the existing
external-pin reader without changing its public behavior. Remove the reader's
private duplicate locator authority in the same four-file rollback boundary.
Do not implement later composition or protected-member observation.

## Completed work — do not repeat

- Configuration projection, external-pin reading, canonical manifest
  validation, protected-membership projection, held-handle traversal and reads,
  label-aware descriptor transport, Windows security mechanics, shared reader
  identity, and the protected-manifest security policy are checkpointed.
- `66ee4f47` checkpoints the authenticated protected-manifest reader and its
  exhaustive two-file regression suite.
- Fresh verification passed 148 focused reader tests, the zero-drop 1,422-test
  pre-reader authority union, and the 1,570-test combined authority gate.
- Three independent current-byte reviews found no unresolved critical, major,
  or minor issue.
- Checkpoint evidence is recorded in
  `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`.
- The earlier composition audit already proved that target filesystem evidence
  is cleanup-plan pre-state, not membership-authentication input.
- Three locator audits selected shared extraction parity and fixed its exact
  five-export surface, lifecycle, error, RED, and verification contracts in
  `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_RECHECK_DECISION_2026-07-14.md`.

## Governing invariant

Ambient environment, configuration, current directory, caller input, or a
second guessed path cannot locate the ProgramData pin chain. One shared native
authority must invoke the actual fixed Known Folder API and retain its exact
result only in-process without logging or serialization.

The pin reader and protected-manifest reader remain closed four-export
authorities. The implementation may add no private-symbol import,
caller-supplied path, duplicate locator, or duplicate physical reader.

## Exact implementation seam

1. add `steps/common/clean_memory_windows_program_data_locator.py`;
2. add `tests/unit/test_clean_memory_windows_program_data_locator.py` and watch
   the exact contract fail before production code;
3. adapt `cli/clean_memory_external_pin.py`; and
4. adapt `tests/unit/test_clean_memory_external_pin.py` for zero-drop parity.

The new shared module has exactly the five exports selected in the decision
document. The external reader must preserve its exact four exports, thirteen
errors, no-argument API, evidence bytes, native order, token brackets,
held-handle traversal, and cleanup/control-flow precedence.

## Governing evidence

- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_RECHECK_DECISION_2026-07-14.md`;
- `cli/clean_memory_external_pin.py`;
- `cli/clean_memory_protected_manifest.py`;
- their focused tests; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- Touch only the exact four-file implementation seam above until its source
  checkpoint is complete.
- Do not create protected-observer, composition, Qdrant, planning, approval, or
  cleanup code.
- Do not modify the protected-manifest reader or its tests.
- Do not inspect or mutate live ProgramData, a token, ACL, descriptor,
  configured or protected root, manifest, pin, service, GoodQ data, Qdrant
  store, evidence store, job, MiniAgent, approval, or cleanup target.
- Do not change environment, service, firewall, dependency, enrollment,
  publication, rotation, recovery, or runtime state.

## Completion gate

1. the direct locator tests fail for the absent authority before implementation;
2. direct tests and all frozen parity gates pass through `goodq_core`;
3. the staged source diff contains exactly four files and no duplicate/private
   locator authority;
4. at least two independent current-byte reviews are clean; and
5. implementation and documentation are checkpointed separately.
