<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — implement the authenticated Windows protected-manifest
reader contract.

## Outcome

Implement the reviewed reader through one isolated two-file
RED/GREEN/refactor checkpoint. The reader must authenticate one fixed canonical
manifest from exact configuration and direct external-pin evidence, using only
completed public mechanics and policies.

## Exact changed-file census

Only these files may change:

1. add `cli/clean_memory_protected_manifest.py`; and
2. add `tests/unit/test_clean_memory_protected_manifest.py`.

Existing production and test files are regression gates only. If implementation
requires another changed file or public surface, stop and return to a decision
audit instead of widening the seam.

## Completed work — do not repeat

- Configuration projection, external-pin reading, canonical manifest
  validation, protected-membership projection, held-handle traversal and reads,
  label-aware descriptor transport, Windows security mechanics, and shared
  reader identity are checkpointed.
- `02530486` and `387fdc5b` checkpoint the shared reader-identity implementation
  and documentation.
- Three independent read-only audits selected the exact public API, evidence,
  sixteen errors, lifecycle, route cardinality, dependency graph, file census,
  RED matrix, and verification gate.
- The binding decision is recorded in
  `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CONTRACT_DECISION_2026-07-14.md`.

## Governing invariant

The reader may return evidence only for the exact complete bytes obtained from
one held no-follow manifest handle after direct external-pin digest comparison,
shared canonical validation of those identical bytes, selected reader/security
policy, complete held-route proof, final race fences, and successful cleanup.

The evidence projection and errors remain path-free. Retained manifest bytes
are an explicit repr-hidden in-process capability for later membership
composition, not a log or report surface.

## TDD order

1. Add focused RED for the exact four-export module and signature.
2. Add RED for direct input authentication and first-failure precedence.
3. Add RED for mandatory reader identity and complete held route.
4. Add RED for candidate/manifest descriptor and denial policy.
5. Add RED for same-handle size-plus-one reading, pin-before-parser order, and
   one identical-byte validator call.
6. Add RED for exact evidence/digest bindings, all sixteen errors, race fences,
   cleanup, control-flow preservation, and static containment.
7. Implement only enough GREEN to satisfy the reviewed contract.
8. Refactor only inside the two-file seam.
9. Run the focused suite, zero-drop 1,422-test authority union plus all new
   reader nodes, compilation, diff/census, dependency, semantic-drift, and
   banned-token gates.
10. Obtain two independent current-byte reviews before checkpointing.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- Use the explicit `goodq_core` Conda runtime sequentially.
- Use synthetic/fake native surfaces and pytest-owned temporary resources only.
- Do not inspect or mutate a live token, ACL, descriptor, configured or
  protected root, manifest, pin, service, GoodQ data, Qdrant store, evidence
  store, job, MiniAgent, approval, or cleanup target.
- Do not change configuration, external-pin, validator, membership, held-
  handle, security-mechanics, identity, filesystem, planning, storage, Qdrant,
  approval, or cleanup code.
- Do not enroll, publish, rotate, recover, compose, observe protected members,
  build a plan, issue approval, or execute cleanup.
- Do not claim the separate native `0xb014` enrollment or candidate-store
  compatibility witness.

## Completion gate

The seam is checkpointable only when:

1. the exact two-file diff implements the decision without copied authority;
2. the focused reader suite and zero-drop authority union pass;
3. all public, lifecycle, parity, static-containment, privacy, and cleanup
   oracles pass;
4. two independent current-byte reviews return ready with no unresolved
   critical, major, or minor finding; and
5. a separate checkpoint document records exact hashes, counts, gates, commit,
   and remaining closed authorities.
