<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — select the projection-neutral same-handle security
decision capability required by the future Windows external-pin reader.

## Outcome

Perform a read-only authority decision for the remaining opaque-token,
security-descriptor, process-token, and `AccessCheck` join. Produce one exact,
testable shared-backend contract before any security capability or external-pin
reader code is written.

## Completed work — do not repeat

- `0f567557` extracted the projection-neutral Windows held-handle backend.
- `4aa0aaad` corrected the reader prerequisite order after the capability-gap
  audit.
- `73430481` added and verified exact 1-through-66-byte bounded reads on the
  existing opaque held token.
- The filesystem observer contract, same-handle identity/hash mechanics,
  four-symbol module export, and bounded-read semantics are closed unless new
  focused evidence contradicts them.

## Governing evidence

- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_READER_CAPABILITY_GAP_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CHECKPOINT_2026-07-13.md`;
- official Microsoft Win32 documentation for file security, access tokens,
  generic mappings, `GetSecurityInfo`, and `AccessCheck`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The shared backend owns every raw Windows handle, descriptor allocation, token,
and native cleanup. Consumers may receive only detached immutable evidence or a
finite path-free decision. They may never receive a raw handle, pointer,
borrowed native buffer, cleanup callback, private token field, or pathname
reopen capability.

## Questions this decision must close

1. Whether the shared capability returns detached self-relative descriptor
   bytes for a reader-owned `AccessCheck`, or keeps `AccessCheck` entirely inside
   the backend and returns a finite immutable access decision.
2. Which existing opens require `READ_CONTROL`, whether root and descendant
   rights differ, and how unsupported or denied descriptor access maps to the
   existing finite error contract.
3. How an impersonation token suitable for `AccessCheck` is obtained, owned,
   duplicated when required, and closed on every success and failure path.
4. The exact requested file access mask and file-object `GENERIC_MAPPING`,
   including when `MapGenericMask` is required.
5. The exact immutable return schema, malformed native-output handling,
   `AccessCheck` call-success versus access-status distinction, and cleanup-error
   precedence.
6. The smallest hermetic fake/native test matrix proving same-handle security,
   token/descriptor cleanup, denial, malformed output, and no live trust-root
   access.

## Boundaries

- Read and document only. Do not modify production source or tests in this
  decision seam.
- Do not implement the external-pin reader, enrollment, publication, rotation,
  recovery, authenticated composition, protected-member observation, Qdrant
  observation, runnable planning, or cleanup execution.
- Do not weaken handle opacity, return native pointers, access private token
  fields, duplicate traversal, or reopen descendants by pathname.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Create one decision record that selects an exact public capability and rejects
the alternatives with code traces and current official Win32 evidence. Define
its signature, rights, native ABI, ownership, cleanup, finite errors, negative
capabilities, test matrix, and next isolated source/test seam. Run documentation
authority, generated-index, semantic-drift, banned-token, dependency, and diff
gates; obtain three independent current-byte reviews; then checkpoint the
decision before implementation begins.
