<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — audit the protected-member observer and direct pin-chain
physical-exclusion boundary before implementation.

## Outcome

Perform one read-only no-repeat ownership and contract audit. Select the exact
observer inputs, held-handle lifecycle, physical alias/collision rules, error
taxonomy, and RED oracles. Do not implement the observer, composition, Qdrant
observation, runnable planning, approval, or cleanup in this mission.

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

## Governing invariant

Authenticated configuration and manifest membership describe logical protected
authority; neither proves the physical state of protected members. One future
no-follow observer must retain exact physical evidence for every protected
parent and member and reject every cross-member alias or collision with any
direct pin-chain identity before authenticated composition may return.

Lexical overlap checks and physical alias checks are distinct mandatory gates.
Neither may substitute for the other, and no path, identity detail, descriptor,
or raw member content may enter public evidence, logs, or errors.

## Exact audit seam

1. reconcile the completed held-handle, filesystem, membership, external-pin,
   manifest-reader, locator, and composition contracts;
2. identify the single future production owner and exact shared mechanics it
   may reuse without importing private symbols;
3. select direct inputs, physical identity envelopes, parent/member lifecycle,
   pin-chain exclusion inputs, final race fences, and cleanup precedence;
4. select one closed path-free error taxonomy and the complete RED matrix; and
5. record the decision and roadmap next step without creating production code.

## Governing evidence

- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_RECHECK_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_HELD_HANDLE_EXTRACTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- their closed source/tests; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- This mission is read-only except for its decision evidence, `PROJECT.md`, the
  roadmap entry, and generated documentation indexes.
- Do not modify any completed production module or focused test.
- Do not inspect or mutate live ProgramData, a token, ACL, descriptor,
  configured or protected root, manifest, pin, service, GoodQ data, Qdrant
  store, evidence store, job, MiniAgent, approval, or cleanup target.
- Do not change environment, service, firewall, dependency, enrollment,
  publication, rotation, recovery, or runtime state.

## Completion gate

1. at least two independent read-only ownership/lifecycle traces agree on the
   smallest non-duplicating observer seam;
2. the decision names exact inputs, outputs, physical exclusion, race,
   cleanup/control, error, and RED contracts;
3. no completed authority is reopened or treated as missing;
4. documentation authority, semantic drift, banned-token, dependency, index,
   and diff gates pass; and
5. the decision is checkpointed separately before implementation begins.
