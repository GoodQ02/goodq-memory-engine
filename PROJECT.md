<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — reassess the frozen reader-identity v1 policy seam.

## Outcome

Perform one read-only no-repeat ownership audit before authorizing any
protected-manifest reader code. Determine whether the frozen reader-identity v1
projection/digest remains external-pin private or belongs in a separate shared
clean-memory policy seam, and identify the smallest coherent consumer boundary.

Do not implement the manifest reader or move policy during this audit. End with
one evidence-backed selection, exact files, RED oracles, rollback boundary, and
verification gate—or record why no extraction is justified.

## Completed work — do not repeat

- Configuration, filesystem observation, structural membership, held-handle
  traversal, bounded reads, external-pin authority, canonical manifest
  validation, and protected-manifest security policy are checkpointed.
- `6b40d8e8` checkpoints label-aware held-handle transport while preserving
  exact existing profiles.
- `ae4d35bc` establishes the projection-neutral Windows security ABI.
- `0827193a` extracts token, descriptor, mapping, duplication, access, and
  cleanup mechanics into one shared authority while preserving external-pin
  policy and output exactly.
- Fresh extraction verification passed 254 shared tests, 499 external tests,
  the historical 167 held-handle baseline, 46 filesystem tests, and the 1,357-
  test clean-memory authority union. Two independent final reviews returned
  `READY`.
- The held-handle backend, frozen reader-identity v1 policy, and protected-
  manifest reader were deliberately excluded from the extraction checkpoint.

## Governing evidence

- `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`;
- `cli/clean_memory_external_pin.py`;
- `steps/common/windows_security_mechanics.py`;
- `cli/clean_memory_protected_manifest_validator.py`;
- `tests/unit/test_clean_memory_external_pin.py`;
- `tests/unit/test_windows_security_mechanics.py`; and
- `docs/releases/ROADMAP.md`.

## Governing invariant

Projection-neutral native mechanics and GoodQ identity policy are separate
authorities. Reuse must not make the shared mechanics module know consumer
roles, trusted SIDs, accepted token values, evidence schemas, or outward errors.
The external-pin v1 bytes/digest remain frozen until a separate policy decision
proves an exact shared owner and byte-for-byte consumer parity.

## Exact audit questions

1. Which current consumers need the reader-identity v1 projection/digest?
2. Is the projection generic clean-memory policy or external-pin evidence
   policy?
3. Which inputs are projection-neutral shared observations and which are
   consumer acceptance decisions?
4. Can one import-pure policy surface serve both consumers without reversing
   dependency direction or exposing private capability owners?
5. What exact public API, frozen bytes, errors, and precedence would remain?
6. What RED oracles prove absence, parity, no duplicate authority, and no live
   capability acquisition?
7. Does the smallest coherent seam include only policy, or must the manifest
   reader remain closed until another prerequisite is proven?

## Boundaries

- Read repository source, tests, and checkpoint evidence only.
- Do not inspect or mutate any live token, ACL, descriptor, configured or
  protected root, manifest, pin, service, GoodQ data, Qdrant store, evidence
  store, job, MiniAgent, or cleanup target.
- Do not modify the shared mechanics, external-pin reader, manifest validator,
  held-handle backend, or tests during the audit.
- Do not create a manifest reader, identity helper, enrollment/publication
  mechanism, compatibility shim, or second projection authority.
- Do not broaden into planning, approval, execution, retention, LAN, service,
  dependency, or release work.

## Completion gate

Checkpoint the audit only when current call graphs and byte-level contracts
identify one ownership decision, every completed authority is named, rejected
alternatives are explicit, exact implementation/test files are selected, and
at least two independent read-only reviews agree that the next seam does not
repeat completed work or mix mechanics with policy.

The protected-manifest reader remains closed.
