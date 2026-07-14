<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows Reader Capability-Gap Audit

## Decision

Do not implement `cli/clean_memory_external_pin.py` against the current shared
held-handle boundary. The audited reader contract cannot be satisfied while
touching only the reader source/test pair.

First add and checkpoint only the exact same-handle bounded-read primitive that
is already fully determined. Then perform a separate read-only decision on the
security-capability join before changing access rights, token ownership,
security-descriptor handling, or `AccessCheck` ownership.

This correction preserves the governing invariant: raw Windows handles remain
opaque, the filesystem observer retains its proven behavior, and no path
fallback or copied held-handle implementation is introduced merely to make the
reader compile.

## Why The Reader-Only Seam Is Not Implementable

The completed `WindowsHeldHandleBackend` deliberately exposes exactly seven
methods. Its backend-issued tokens are private, instance-bound, and unwrap to a
native handle only through a private method.

That boundary is sufficient for the completed filesystem observer, but the
reader additionally requires all of the following on the same held file
handle:

- handles opened with `READ_CONTROL` before `GetSecurityInfo` can retrieve
  owner, primary group, and DACL information;
- a security-descriptor operation that retains native allocation ownership and
  always pairs a non-null `GetSecurityInfo` result with `LocalFree`;
- `MapGenericMask` and `AccessCheck` against the accepted duplicated
  impersonation token; and
- a bounded content read that returns the exact pin bytes and an independently
  observed EOF result.

The current descendant opens request only list/read-data plus read-attributes.
The current `hash_file()` consumes the file internally and returns only its
SHA-256 and size. A reader therefore cannot inspect security or parse the pin
without doing at least one forbidden thing: accessing the backend's private raw
handle, duplicating its Win32 traversal, reopening a descendant by pathname, or
weakening the same-handle proof.

Microsoft's current Win32 contract confirms the access mismatch:
`GetSecurityInfo` requires the object handle to have been opened with
`READ_CONTROL` when owner, group, or DACL information is requested. The
synchronous EOF contract separately requires a successful zero-byte
`ReadFile` result to prove end of file.

## No-Repeat Result

Keep these checkpoints closed:

- the filesystem observer and its outward API/evidence/errors;
- shared opaque-token ownership, reverse-order cleanup, and canonical physical
  identity rendering;
- the protected-membership projection;
- the selected ProgramData source, token policy, security policy, reader
  evidence, and finite reader error table; and
- every completed approval, job, configuration, and candidate-plan authority.

Do not work around the gap with private imports, reflection over token fields,
`DuplicateHandle`, a raw-handle callback, descendant pathname opens, or a
second copy of `OpenFileById` logic.

## Corrected Capability Order

The corrected sequence is:

1. checkpoint one projection-neutral bounded-read method in the existing
   shared backend;
2. audit and select the exact opaque security-capability join, including
   access-profile ownership, token ownership, descriptor representation,
   `AccessCheck` ownership, file-object generic mapping, malformed native
   structure classification, and cleanup-failure precedence;
3. implement and checkpoint that selected security capability; and
4. implement the no-argument external-pin reader only after both shared
   prerequisites are public and verified.

This is not repetition of the held-handle extraction. The extraction preserved
the observer's proven mechanics exactly; this audit identifies two reader-only
capabilities that the extraction explicitly did not add.

## Selected Bounded-Read Contract

Add exactly one public method to `WindowsHeldHandleBackend`:

```python
def read_file_bounded(
    self,
    handle: object,
    *,
    maximum_bytes: int,
) -> tuple[bytes, bool]:
    ...
```

The tuple is `(prefix, eof_observed)`.

- `type(maximum_bytes) is int` and `1 <= maximum_bytes <= 66`; every other
  value fails path-free as `observation_failed` before any native call.
- The method validates the opaque token through the existing owner/liveness
  boundary and rewinds that same native handle with `SetFilePointerEx`.
- It performs only positive-length synchronous `ReadFile` calls, each bounded
  by the remaining capacity.
- A successful zero-byte read sets `eof_observed=True`.
- Reaching `maximum_bytes` first returns the accumulated prefix with
  `eof_observed=False` and performs no read beyond the cap.
- A native byte count larger than the requested remainder is
  `observation_failed`.
- Sharing conflicts and other native failures retain the existing shared error
  classification and chained-cause behavior.
- `hash_file()` remains unchanged; both operations independently rewind before
  reading, so their call order cannot affect the result.

This exact shape lets the future reader call with `maximum_bytes=66`, accept
only 65 bytes with `eof_observed=True`, and reject every longer, truncated, or
non-EOF payload without reading byte 67.

The module's exact four-symbol `__all__` remains unchanged. Its backend method
surface gains only `read_file_bounded` during this checkpoint.

## Bounded-Read Verification Gate

The two-file seam is only:

- `steps/common/windows_held_handle.py`; and
- `tests/unit/test_windows_held_handle.py`.

RED/GREEN evidence must cover:

1. exact method name and keyword-only signature;
2. 65-byte partial reads followed by an observed zero-byte EOF;
3. a 66-byte cap result with no read beyond the cap;
4. empty and short-file EOF behavior;
5. invalid limits and foreign/closed/post-context tokens before native calls;
6. impossible native byte counts;
7. bounded-read/`hash_file` interoperability in both orders;
8. a Windows-native temporary-file witness reached through root enumeration
   and `open_by_id`, never through ProgramData; and
9. the existing shared-backend, observer, authority-union, import, compile,
   documentation, dependency, banned-token, diff, and independent-review gates.

No observer source change is selected or expected.

## Security Boundary Still Requiring A Decision

The stronger security alternatives do not have equivalent authority or
rollback boundaries and must not be selected implicitly while implementing the
bounded read.

One candidate returns an immutable self-relative security-descriptor copy from
the same held handle so the reader-owned token backend can parse it and perform
`AccessCheck`. Another keeps the descriptor and `AccessCheck` inside a
backend-bound security facet and joins it to a separately owned opaque token.
The latter narrows native-data exposure but requires an exact cross-capability
ownership protocol; the former is smaller but makes descriptor representation
part of a public internal boundary.

Before either implementation, the decision must freeze:

- whether descendant access rights are selected per backend instance or per
  open, while preserving the observer's default flags exactly;
- whether raw self-relative descriptor bytes may cross the boundary;
- which component owns the duplicated impersonation-token handle;
- exact file-object `GENERIC_MAPPING` constants;
- `GetSecurityInfo`/`LocalFree` primary-versus-cleanup failure precedence;
- bounds and validation for malformed descriptor, ACL, ACE, SID, and token
  buffers; and
- exact shared-to-reader error translation.

Raw handles, pointer leases, caller callbacks, caller-supplied access masks, and
reconstructed security descriptors are not candidates.

## Verification Boundary

This audit used repository source/tests, completed R-07 decisions, the current
official Win32 reference, and three independent bounded reviews. It did not
resolve or inspect live ProgramData, a pin, token, ACL, configured root,
service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup target.

## Handoff

R-07 remains `IN_PROGRESS`. The next bounded mission is only the two-file
same-handle bounded-read checkpoint above. The security capability, external-
pin reader, enrollment, publication, rotation, authenticated composition,
protected observation, Qdrant observation, planning, and cleanup execution
remain closed.
