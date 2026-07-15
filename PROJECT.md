<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — select the protected-manifest reader public contract and
exact input/error fence.

## Outcome

Perform one read-only no-repeat audit. Determine the smallest coherent public
reader boundary before any protected-manifest reader source or test file is
authorized.

The audit must reconcile completed authorities instead of redesigning or
reimplementing them.

## Completed work — do not repeat

- Configuration projection, candidate-plan authority, filesystem observation,
  protected-membership projection, held-handle traversal and bounded reads,
  canonical protected-manifest validation, external-pin reading, label-aware
  descriptor transport, projection-neutral security mechanics, and the
  protected-manifest security policy are checkpointed.
- `ae4d35bc` and `0827193a` checkpoint the shared Windows security mechanics.
- `ac5691a6` selects the shared reader-identity ownership and exact public API.
- `02530486` implements that shared policy and adapts the external reader.
- Fresh controller verification passed 65 direct policy tests, the zero-drop
  499-test external baseline, and the 1,422-test clean-memory authority union.
- Independent current-byte reviews returned `APPROVED` and `READY`.
- Checkpoint evidence is recorded in
  `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_CHECKPOINT_2026-07-14.md`.

## Governing invariant

The future reader may authenticate only the exact complete canonical manifest
bytes obtained from one held no-follow file handle and authorized by direct
external-pin evidence. It must use completed shared mechanics, validation, and
identity policy without copying their private logic or widening their public
surfaces.

Reader input types do not prove production provenance by themselves. The later
production planning edge must directly invoke both physical readers. The reader
may observe and return bounded immutable evidence; it may not enroll, publish,
rotate, recover, compose, plan, approve, or clean.

## Audit questions

Select and document exactly:

1. the module and finite public export set;
2. the reader function signature and exact-type input fences;
3. the immutable path-free evidence boundary and digest bindings;
4. the finite stable path-free error taxonomy;
5. first-failure precedence across input, platform, capability, token, route,
   descriptor, content digest, canonical validation, race, and cleanup;
6. the precise reuse boundary for configuration, external-pin evidence,
   protected-manifest validation, held handles, security mechanics, and shared
   reader identity;
7. the source/test file census for the later RED/GREEN checkpoint; and
8. the focused parity and lifecycle verification gate required before reader
   implementation can be authorized.

Do not freeze a convenient surface without tracing every required field and
failure to existing code and tests.

## Governing evidence

- `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- `cli/clean_memory.py`;
- `cli/clean_memory_external_pin.py`;
- `cli/clean_memory_protected_membership.py`;
- `steps/common/clean_memory_protected_manifest.py`;
- `steps/common/clean_memory_windows_reader_identity.py`;
- `steps/common/windows_held_handle.py`;
- `steps/common/windows_security_mechanics.py`;
- their focused unit tests; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- Read repository source, tests, contracts, and checkpoint evidence only.
- Use bounded independent read-only audits where they improve confidence.
- Do not create or edit protected-manifest reader source or tests during this
  decision audit.
- Do not inspect or mutate a live token, ACL, descriptor, configured or
  protected root, manifest, pin, service, GoodQ data, Qdrant store, evidence
  store, job, MiniAgent, or cleanup target.
- Do not change enrollment, publication, rotation, recovery, composition,
  Qdrant observation, planning, approval, or cleanup authority.
- Do not stage unrelated files or reopen completed checkpoints without
  contradictory focused evidence.

## Decision gate

Before authorizing reader implementation:

1. at least three independent read-only traces reconcile API/ownership,
   lifecycle/error precedence, and evidence/digest parity;
2. one decision document names the exact public contract, dependency graph,
   file census, RED matrix, and verification gate;
3. no duplicate parser, policy, projection, or native capability is selected;
4. every unresolved field or failure remains explicitly closed rather than
   guessed; and
5. documentation authority, semantic-drift, banned-token, dependency, index,
   and committed-diff gates pass in a separate checkpoint.
