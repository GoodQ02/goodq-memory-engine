<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — extract the frozen Windows reader-identity policy.

## Outcome

Implement one import-pure GoodQ clean-memory Windows reader-identity authority
and adapt the completed external-pin reader in the same checkpoint.

Use strict RED/GREEN/refactor. Preserve exact external behavior and keep the
protected-manifest reader closed.

## Exact implementation seam

Only these four files may change during implementation:

1. add `steps/common/clean_memory_windows_reader_identity.py`;
2. add `tests/unit/test_clean_memory_windows_reader_identity.py`;
3. adapt `cli/clean_memory_external_pin.py`; and
4. adapt `tests/unit/test_clean_memory_external_pin.py`.

Documentation, ROADMAP, PROJECT, and generated indexes belong in a later
separate checkpoint after implementation is committed and freshly verified.

## Completed work — do not repeat

- Configuration, filesystem observation, structural membership, held-handle
  traversal, bounded reads, external-pin authority, canonical manifest
  validation, and protected-manifest security policy are checkpointed.
- `6b40d8e8` checkpoints label-aware held-handle transport while preserving
  exact existing profiles.
- `ae4d35bc` establishes the projection-neutral Windows security ABI.
- `0827193a` extracts shared token, descriptor, mapping, duplication, access,
  and cleanup mechanics while preserving external-pin output and lifecycle.
- `dc7af74b` checkpoints the extraction evidence and advances only to the
  reader-identity ownership audit.
- Three independent read-only audits selected a separate import-pure identity
  policy. Two follow-up reviews returned `READY` on the exact three-symbol API,
  profile fences, early-validation/late-digest timing, and digest-only boundary.
- The frozen v1 preimage/digest, current external acceptance matrix, future
  mandatory-policy requirements, and exact dependency direction are recorded
  in
  `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_DECISION_2026-07-14.md`.

## Governing invariant

Projection-neutral mechanics and GoodQ reader-identity policy are separate
authorities. The new module may interpret an already-detached exact
`WindowsTokenSnapshot`; it may not acquire a token, bind native functions,
inspect a path/DACL/manifest, own a session, grant authorization, or know a
consumer error/evidence schema.

The raw v1 schema, projection, and canonical preimage remain private. Only the
lowercase SHA-256 digest leaves the policy module. Every physical reader still
proves snapshot provenance and race equality through its own retained mechanics
session.

## Exact public surface

The new module exports only:

```python
__all__ = (
    "CleanMemoryWindowsReaderIdentityError",
    "validate_clean_memory_windows_reader_identity",
    "clean_memory_windows_reader_identity_sha256",
)
```

Both functions accept exact `WindowsTokenSnapshot`, keyword-only exact mechanics
profile, and keyword-only exact non-boolean unsigned-64
`change_notify_luid`.

- base profile requires `mandatory_policy is None`;
- mandatory profile requires exact integer `1` or `3`;
- validation returns `None`;
- digest revalidates and returns exactly 64 lowercase hex characters; and
- mandatory policy and profile remain outside the frozen v1 preimage. The
  `change_notify_luid` argument is not independently serialized; accepted
  snapshot privilege LUIDs remain present.

Do not export a schema constant, projection function, canonical bytes, result
class, native capability, or compatibility alias.

## TDD order

1. Add only direct shared-policy RED tests proving the absent module/API,
   argument contract, acceptance matrix, profile fences, golden digests,
   import purity, digest-only boundary, and no native capability.
2. Run the direct file and record expected RED caused only by absent authority.
3. Add adapter RED proving the external source still owns private policy,
   validation is not delegated, and digest timing is not delegated.
4. Run the adapted external file and record expected RED without changing the
   499-node baseline.
5. Implement the smallest shared module.
6. Adapt external pin in place:
   - shared validation immediately after baseline acquisition;
   - all existing storage/race/descriptor/content operations unchanged;
   - shared digest only after `_final_authority_recheck()`;
   - exact existing evidence and cleanup afterward.
7. Remove private production validator/projector/schema ownership from external
   pin with no compatibility alias.
8. Run focused GREEN, then the full verification gate.

## Required parity

Preserve exactly:

- external four-symbol public API and thirteen outward errors;
- base 17-call token profile and absence of class 27;
- current Default/Limited acceptance and every rejection;
- no new rejection based on currently ignored, structurally valid token
  statistics, ordinary SID/group values, integrity attributes, disabled
  privileges, or change-notify presence/enabled state;
- enrolled-reader SID correlation and DACL/access policy;
- v1 canonical fields, ordering, formatting, bytes, and digest;
- complete external evidence bytes and digest;
- 39 token snapshots, five descriptor duplications, and 19 access checks;
- route, descriptor, content, race, failure, and cleanup order; and
- all projection-neutral mechanics and held-handle APIs.

The external suite remains a 499-node zero-drop integration baseline. Direct
shared-policy tests are additive.

## Governing evidence

- `docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`;
- `cli/clean_memory_external_pin.py`;
- `steps/common/windows_security_mechanics.py`;
- `steps/common/clean_memory_protected_manifest.py`;
- `tests/unit/test_clean_memory_external_pin.py`;
- `tests/unit/test_windows_security_mechanics.py`; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- Use sequential `conda run --no-capture-output -n goodq_core ...` commands.
- Do not change Windows security mechanics, held-handle code, manifest
  validator/membership, configuration, planning, storage, services, or data.
- Do not inspect or mutate any live token, ACL, descriptor, configured or
  protected root, manifest, pin, service, GoodQ data, Qdrant store, evidence
  store, job, MiniAgent, or cleanup target.
- Do not create the protected-manifest reader, enrollment/publication,
  composition, compatibility shim, or second policy authority.
- Do not stage unrelated files or broaden the rollback boundary.

## Verification gate

Before implementation checkpoint:

1. direct new policy tests pass;
2. external 499-node baseline remains zero-drop;
3. mechanics 254, held-handle 167, filesystem, canonical-validator, and
   membership suites pass;
4. expanded clean-memory authority union passes;
5. exact four-file compilation and diff containment pass;
6. import/dependency/AST containment and semantic-drift gates pass;
7. at least two independent current-byte reviews return `READY`; and
8. the implementation and evidence documentation are checkpointed separately.

After that checkpoint, advance only to a read-only protected-manifest reader
public-contract and error/input-fence decision. The reader remains closed until
that later audit selects its exact source/test boundary.
