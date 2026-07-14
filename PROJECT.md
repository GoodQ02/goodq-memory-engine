<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — implement the audited read-only Windows external-pin
reader after its shared same-handle prerequisites were privately checkpointed.

## Outcome

Implement only the no-argument Windows external-pin reader and its focused
tests. It must consume the public held-handle backend, resolve ProgramData
without creation or fallback, bind one accepted process-token identity to the
fixed security policy, read exactly one held-handle pin payload, recheck every
authority, and return only immutable path-free evidence.

## Completed work — do not repeat

- `0f567557` extracted the projection-neutral Windows held-handle backend.
- `4aa0aaad` corrected the reader prerequisite order after the capability-gap
  audit.
- `73430481` added and verified exact 1-through-66-byte bounded reads on the
  existing opaque held token.
- `docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md`
  selected detached self-relative descriptor bytes, descendant-only
  `READ_CONTROL`, and reader-owned token/`AccessCheck` authority.
- `882dc70` implemented and verified the opt-in same-handle descriptor-copy
  capability without changing observer-default rights or dependencies.
- `docs/diagnostics/R07_WINDOWS_SECURITY_DESCRIPTOR_CHECKPOINT_2026-07-13.md`
  records the closed contract, reviewed hashes, and fresh verification.
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_IMPLEMENTATION_DECISION_2026-07-13.md`
  freezes the reader evidence object, pure parser, bounded token snapshots,
  two-stage enrollment binding, per-object `AccessCheck` lifecycle, exact
  operation order, and edge-error precedence before RED.
- The filesystem observer contract, same-handle identity/hash mechanics,
  four-symbol module export, bounded-read semantics, and descriptor primitive
  are closed unless new focused evidence contradicts them.

## Governing evidence

- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_READER_CAPABILITY_GAP_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_DESCRIPTOR_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_IMPLEMENTATION_DECISION_2026-07-13.md`;
- official Microsoft Win32 documentation for file security, access tokens,
  generic mappings, `GetSecurityInfo`, and `AccessCheck`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The reader may trust only evidence obtained from one fixed drive root and
opaque held descendants, one accepted process-token snapshot sequence, and the
exact audited static security policy. It accepts no path, SID, digest,
configuration, environment, backend, manifest bytes, or prior evidence.
Neither raw native state nor sensitive identity/security material may leave the
reader; only detached canonical evidence and finite path-free errors may cross
its public boundary.

## Exact implementation seam

Create only:

- `cli/clean_memory_external_pin.py`; and
- `tests/unit/test_clean_memory_external_pin.py`.

The exact public module surface is:

```text
EXTERNAL_PIN_EVIDENCE_SCHEMA
ExternalPinReaderError
ExternalPinEvidence
read_external_pin
```

`read_external_pin()` accepts no arguments. Dependency injection is private and
test-only. Windows v1 owns Known Folder lookup, effective-token snapshot and
recheck, descriptor parsing, fixed file-object generic mapping, per-right
`AccessCheck`, exact 65-byte pin validation through the bounded-read primitive,
and final descriptor/object/membership rechecks. POSIX returns the fixed
`unsupported_platform` result. The implementation decision fixes all remaining
buffer caps, parser consumption, token fences, enrollment precedence, duplicate
ownership, privilege-output bounds, evidence keys, and cleanup ordering; code
must not infer a different contract.

## Boundaries

- Do not touch any production or test file outside the exact two-file seam.
- Do not modify the completed held-handle backend or observer.
- Do not add enrollment, publication, rotation, recovery, authenticated
  composition, protected-member observation, Qdrant observation, runnable
  planning, or cleanup execution.
- Do not weaken handle opacity, expose paths/SIDs/token or ACL material, install
  an impersonation token on a thread, duplicate traversal, or reopen
  descendants by pathname.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Demonstrate RED for the exact public surface, no-argument boundary, token and
security ABI, fixed policy, evidence projection, read/recheck sequence, finite
errors, and cleanup precedence before implementation. Then pass the focused
reader suite, completed shared-backend/observer suites, the approved authority
union, compilation, import-purity, documentation, banned-token, dependency,
and diff gates. Obtain three independent current-byte reviews and checkpoint
the two-file reader before any enrollment or authenticated-composition seam.
