<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — implement the checkpointed projection-neutral same-handle
security-descriptor capability required by the future Windows external-pin
reader.

## Outcome

Implement only the selected opt-in `security_read` profile and immutable
self-relative descriptor-copy method in the existing shared Windows
held-handle backend. Prove the exact access, native allocation, validation,
cleanup, error, and observer-parity contract through focused TDD.

## Completed work — do not repeat

- `0f567557` extracted the projection-neutral Windows held-handle backend.
- `4aa0aaad` corrected the reader prerequisite order after the capability-gap
  audit.
- `73430481` added and verified exact 1-through-66-byte bounded reads on the
  existing opaque held token.
- `docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md`
  selected detached self-relative descriptor bytes, descendant-only
  `READ_CONTROL`, and reader-owned token/`AccessCheck` authority.
- The filesystem observer contract, same-handle identity/hash mechanics,
  four-symbol module export, and bounded-read semantics are closed unless new
  focused evidence contradicts them.

## Governing evidence

- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_READER_CAPABILITY_GAP_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md`;
- official Microsoft Win32 documentation for file security, access tokens,
  generic mappings, `GetSecurityInfo`, and `AccessCheck`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The shared backend owns every raw Windows file handle, backend-issued
held-handle token, descriptor allocation, and corresponding native cleanup.
The future reader separately owns its access-token handles and their cleanup.
Consumers may receive only detached immutable evidence or a finite path-free
decision. They may never receive a raw handle, pointer, borrowed native buffer,
cleanup callback, private token field, or pathname reopen capability.

## Exact implementation seam

Modify only:

- `steps/common/windows_held_handle.py`; and
- `tests/unit/test_windows_held_handle.py`.

The exact public changes are:

```python
WindowsHeldHandleBackend(*, access_profile: str = "observation")

def read_security_descriptor(self, handle: object) -> bytes:
    ...
```

The default observer profile remains byte-for-byte unchanged. The security
profile adds only `READ_CONTROL` to `open_by_id()` descendants, never the
volume-root handle. Only those descendant tokens may retrieve a descriptor.

## Boundaries

- Do not touch any production or test file outside the exact two-file seam.
- Do not implement the external-pin reader, enrollment, publication, rotation,
  recovery, authenticated composition, protected-member observation, Qdrant
  observation, runnable planning, or cleanup execution.
- Do not weaken handle opacity, return native pointers, access private token
  fields, duplicate traversal, or reopen descendants by pathname.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Demonstrate RED for the exact surface and behavior before implementation. Then
pass the focused shared-backend suite, existing observer parity suites, one
temporary-only native descriptor witness, the approved authority union,
compilation, import-purity, documentation, banned-token, dependency, and diff
gates. Obtain three independent current-byte reviews and checkpoint the
two-file capability before beginning the external-pin reader.
