<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows Same-Handle Security Capability Decision

## Decision

Select a detached, immutable, self-relative security-descriptor copy as the one
new shared capability. Keep descriptor parsing, effective-token ownership,
`DuplicateTokenEx`, `MapGenericMask`, and `AccessCheck` inside the future
external-pin reader.

The shared backend gains exactly these public changes:

```python
WindowsHeldHandleBackend(*, access_profile: str = "observation")

def read_security_descriptor(self, handle: object) -> bytes:
    ...
```

`access_profile` accepts only `"observation"` and `"security_read"`. Any other
value raises the constant, path-free programmer error
`ValueError("Unsupported Windows held-handle access profile")` before native
initialization. The default preserves the completed observer byte for byte.

This is the smallest coherent boundary that satisfies the already-fixed reader
evidence contract. The reader must canonicalize owner, primary group,
descriptor control, DACL revision, ordered ACE records, raw ACE masks, and
denied-access decisions. A boolean-only backend decision would discard required
evidence. Returning a policy-shaped object from the shared backend would instead
embed external-pin projection policy into a projection-neutral filesystem
primitive.

## No-Repeat Result

Keep these checkpoints closed:

- shared held-handle extraction and observer parity;
- opaque backend-issued token ownership and reverse-order cleanup;
- physical identity and same-handle snapshot/hash behavior;
- exact 1-through-66-byte bounded reads;
- protected-membership projection;
- ProgramData source selection, reader token policy, ACL policy, evidence
  schema, and finite external-pin error table; and
- every completed approval, job, configuration, and candidate-plan authority.

This decision does not implement the external-pin reader, enrollment,
publication, rotation, recovery, authenticated composition, cleanup, or any
mutation.

## Why Detached Self-Relative Bytes Win

Microsoft documents that functions returning a security descriptor return the
self-relative form except `MakeAbsoluteSD`. A self-relative descriptor is one
contiguous block whose internal components are offsets, so an exact byte copy
is detached from the native allocation without reconstructing its semantics.
The shared backend can therefore:

1. call `GetSecurityInfo` on the exact already-held object handle;
2. validate the returned descriptor before measuring it;
3. copy the complete contiguous descriptor into immutable Python `bytes`; and
4. release the native allocation before returning.

No raw handle, pointer, borrowed buffer, callback, mutable view, pathname, token,
or cleanup responsibility crosses the boundary. The future reader pins an exact
byte-for-byte buffer copy for both its parser and `AccessCheck`; it does not
construct a new descriptor. Its already-required before/after descriptor and
token rechecks detect concurrent change.

Official contracts used by this decision:

- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- [Absolute and self-relative security descriptors](https://learn.microsoft.com/en-us/windows/win32/secauthz/absolute-and-self-relative-security-descriptors)
- [IsValidSecurityDescriptor](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-isvalidsecuritydescriptor)
- [GetSecurityDescriptorLength](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptorlength)
- [GetSecurityDescriptorControl](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptorcontrol)
- [AccessCheck](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- [DuplicateTokenEx](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-duplicatetokenex)
- [File security and access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)
- [MapGenericMask](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-mapgenericmask)
- [LocalFree](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-localfree)

Context7 resolved the official Win32 reference as
`/websites/learn_microsoft_en-us_windows_win32_api`; direct Microsoft Learn
checks agreed.

## Rejected Alternatives

### Backend-owned boolean access decision

Reject. A boolean can prove only one requested access result. It cannot preserve
the owner, group, descriptor control, DACL revision, ordered ACEs, or raw masks
required by `security_policy_sha256`. Adding those projections to the shared
backend would make it an external-pin policy engine rather than a reusable
held-handle primitive.

### Backend-owned policy facts plus fixed decisions

Reject. This retains native ownership but duplicates the future reader's policy
parser and token snapshot authority inside the filesystem backend. It also
requires an opaque cross-capability token join or a second token snapshot,
creating a larger rollback boundary and an avoidable equality problem.

### Raw descriptor pointer, handle lease, callback, or caller mask

Reject. These transfer native lifetime or authorization choices to consumers,
weaken token opacity, and make cleanup or same-handle provenance unverifiable.

### Absolute or reconstructed descriptor

Reject. The returned self-relative bytes are copied exactly. Neither the shared
backend nor the reader may rebuild owner, group, or ACL structures before the
access decision.

## Access Profile And Handle Rights

The profile is selected once per backend instance, not per open. Consumers
cannot supply a native mask.

### `observation`

This remains the default. `CreateFileW` and `OpenFileById` access, share, and
flag values remain exactly as checkpointed. Security-specific DLLs and exports
are not required or loaded for this profile.

### `security_read`

The drive-root handle remains the traversal/volume handle and retains its exact
existing access mask `FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES` (`0x81`). It
is not security-readable and `read_security_descriptor()` rejects it before a
security native call.

Every descendant opened by `open_by_id()` adds only `READ_CONTROL`
(`0x00020000`) to its existing access. Directory and file descendants therefore
both request `0x00020081`. Share modes and open flags remain unchanged. The
private backend token records whether that specific handle was opened with the
security capability; the raw handle remains inaccessible.

This asymmetry is intentional least authority. The future reader inspects the
ProgramData anchor and its selected descendants, not the volume-root traversal
handle.

## Descriptor Native Contract

Only a live, same-instance, security-readable opaque token is accepted.
Validation occurs before any descriptor call.

The operation is exactly:

```text
GetSecurityInfo(
    held_raw_handle,
    SE_FILE_OBJECT,
    OWNER_SECURITY_INFORMATION |
        GROUP_SECURITY_INFORMATION |
        DACL_SECURITY_INFORMATION,
    NULL,
    NULL,
    NULL,
    NULL,
    &descriptor,
)
```

No SACL is requested and no privilege is enabled. A nonzero return code is a
native operation failure; it is not read through `GetLastError`.

The security profile alone loads Advapi32 and binds these pointer-width exact
ABIs; `DWORD` is `c_uint32`, `WORD` is `c_uint16`, `BOOL` is `c_int32`, and every
handle/security-descriptor/output pointer is represented with `c_void_p` or a
pointer to that exact scalar:

| Export | Arguments | Result |
| --- | --- | --- |
| `GetSecurityInfo` | `HANDLE, c_int32, DWORD, POINTER(c_void_p)` for each optional component output and the final descriptor output | `DWORD` |
| `IsValidSecurityDescriptor` | `c_void_p` | `BOOL` |
| `GetSecurityDescriptorControl` | `c_void_p, POINTER(WORD), POINTER(DWORD)` | `BOOL` |
| `GetSecurityDescriptorLength` | `c_void_p` | `DWORD` |
| `LocalFree` | `c_void_p` | `c_void_p` |

The four optional component outputs are passed as null even though their pointer
types are bound; only the final descriptor output is provided. A missing DLL or
partial/missing export rejects `security_read` construction before any handle
can be opened. The default profile does not load or require Advapi32 or
`LocalFree`.

For a successful non-null descriptor, validation order is fixed:

1. `IsValidSecurityDescriptor` must return true. That function supplies no
   extended error and `GetLastError` is not consulted on false.
2. `GetSecurityDescriptorControl` must succeed, report
   `SECURITY_DESCRIPTOR_REVISION == 1`, and include `SE_SELF_RELATIVE`
   (`0x8000`).
3. Only after structural validation may `GetSecurityDescriptorLength` be
   called. The length must be from `SECURITY_DESCRIPTOR_MIN_LENGTH` (`20`)
   through `131072` bytes inclusive. The upper bound safely contains the one
   requested DACL, whose documented maximum is 64 KiB, plus descriptor and SID
   components while refusing an unbounded fake/native copy.
4. Exactly that many bytes are copied once into immutable `bytes`.

The shared capability does not claim that required components or ACL/ACE policy
are semantically valid. The reader performs bounded component, SID, ACL, ACE,
duplicate, order, flag, and policy validation over the detached bytes before
using them.

## Native Allocation Ownership And Failure Precedence

`GetSecurityInfo` documents the returned descriptor only on success. The
backend initializes the output slot to null, treats every output as undefined
when the function returns a nonzero error, and neither dereferences nor frees an
error-path value. On `ERROR_SUCCESS`, the backend requires a non-null descriptor,
owns that returned allocation, and calls `LocalFree` exactly once.

- `LocalFree(NULL)` is never called, and an error-path output is never treated
  as an owned allocation.
- A null `LocalFree` result is success.
- A non-null result is a cleanup failure; its error is captured immediately.
- If descriptor work otherwise succeeded, cleanup failure prevents return and
  becomes path-free `observation_failed`.
- If descriptor work already failed, that primary failure is preserved. The
  first cleanup failure becomes its cause only when no cause exists; otherwise
  it becomes context. Cleanup never replaces the primary failure.
- No cleanup is retried, and no bytes are returned after cleanup failure.

The operation never closes the held file token; normal backend ownership remains
unchanged.

## Reader-Owned Token And Access Decision

The future reader already owns canonical effective-token snapshots, so it also
owns the temporary `AccessCheck` token. The shared filesystem backend never
opens, accepts, or returns a Windows access token.

The fixed sequence remains:

1. `OpenThreadToken(TOKEN_QUERY, OpenAsSelf=TRUE)`; only `ERROR_NO_TOKEN` may
   fall back.
2. Any discovered thread token is rejected as `untrusted_reader` and closed.
3. `OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE)` is the
   only accepted source.
4. Canonical process-token state is captured and validated.
5. Between equal process-token snapshots, `DuplicateTokenEx` creates one
   `TokenImpersonation` token at `SecurityImpersonation` with only
   `TOKEN_QUERY`.
6. The duplicate is never installed on a thread and is closed before the next
   process-token snapshot.
7. The accepted process-token handle is closed after all required snapshots and
   decisions; the process pseudo-handle is never closed.

The prior `SecurityImpersonation` selection remains closed. Although
`AccessCheck` can accept an identification-level impersonation token, changing
that already-checkpointed reader identity contract is not required by this
shared capability and would mix decisions.

The duplicate output slot is initialized to null. The output is defined and
owned only when `DuplicateTokenEx` returns success with a non-null handle. A
success/null combination is `observation_failed` and owns nothing. On failure,
the output is undefined and is neither inspected nor closed, even if a fake
native implementation writes a non-null sentinel. Every successfully acquired
duplicate is closed exactly once.

## Fixed File Generic Mapping And Rights

The reader defines exactly one file-object `GENERIC_MAPPING`:

| Field | Value |
| --- | --- |
| `GenericRead` | `0x00120089` |
| `GenericWrite` | `0x00120116` |
| `GenericExecute` | `0x001200a0` |
| `GenericAll` | `0x001f01ff` |

Every raw ACE mask is preserved for evidence. A separate checking copy is passed
through `MapGenericMask` before policy inspection. Every fixed desired access
mask is also copied and mapped before `AccessCheck`; no generic bit may reach
that call.

The reader accepts no caller-selected mask. It checks only:

- directory: `FILE_DELETE_CHILD`, `WRITE_DAC`, and `WRITE_OWNER`;
- pin file: `DELETE`, `FILE_WRITE_DATA`, `FILE_APPEND_DATA`,
  `FILE_WRITE_EA`, `FILE_WRITE_ATTRIBUTES`, `WRITE_DAC`, and `WRITE_OWNER`.

Each right is checked separately. `MAXIMUM_ALLOWED`, combined caller masks, SACL
rights, and mutation rights are forbidden.

## `AccessCheck` Output And Privilege Buffer

The exact detached descriptor bytes are copied once into a pinned ctypes byte
array. The parser and every `AccessCheck` receive that same buffer; there is no
second descriptor conversion.

The privilege-set buffer capacity is derived from the validated
`TokenPrivileges` count. V1 accepts at most 4096 token privileges. With the
required ABI sizes—an 8-byte `PRIVILEGE_SET` header and 12-byte
`LUID_AND_ATTRIBUTES` records—the allocation is exactly
`8 + 12 * max(1, privilege_count)` bytes and never exceeds 49160 bytes.
Multiplication and addition are checked only after the absolute count bound.
Zero, one, 4096, 4097, and an integer-overflow-shaped input are separate
oracles. A returned count or length beyond the allocation is malformed.
`ERROR_INSUFFICIENT_BUFFER` fails closed and is never used as an undocumented
sizing probe.

`AccessCheck` has two independent outputs:

- native `BOOL == 0` means the call failed. Capture its error immediately and
  ignore `GrantedAccess` and `AccessStatus`;
- native `BOOL != 0` with `AccessStatus == FALSE` and `GrantedAccess == 0` is a
  successful denial;
- native `BOOL != 0` with `AccessStatus == TRUE` and the desired bit granted is
  a valid observation of forbidden authority and therefore
  `security_policy_mismatch`;
- inconsistent status/grant combinations or out-of-bounds privilege output are
  `observation_failed`.

Cleanup of duplicate and process-token handles is reverse-acquisition, exactly
once, and attempts every close. Primary-versus-cleanup precedence matches the
descriptor rule. A cleanup failure prevents evidence return.

## Error Translation

The shared backend retains its existing eight finite
`WindowsHeldHandleError` codes.

| Condition | Shared result | Future reader result |
| --- | --- | --- |
| Non-Windows default construction | `unsupported_platform` | `unsupported_platform` |
| Security ABI/export unavailable on Windows | `unsupported_platform` | `unsupported_security` |
| Invalid profile | constant `ValueError` | programmer error; unreachable in production |
| Default/root/foreign/closed token passed to descriptor method | `observation_failed` | `observation_failed` |
| `GetSecurityInfo` or descriptor-validation failure | `observation_failed` | `observation_failed` |
| Descriptor cleanup failure | `observation_failed` | `observation_failed` |
| Required owner/group/DACL missing or unsupported ACE form | not shared policy | `unsupported_security` |
| Effective token rejected | not shared policy | `untrusted_reader` |
| ACL shape or forbidden access grant | not shared policy | `security_policy_mismatch` |

A missing required descriptor component is an unsupported security structure,
as fixed by the external-pin boundary audit. A component that is present and
structurally supported but has the wrong owner, group, DACL shape, ACE, or
effective-access result is instead `security_policy_mismatch`.

Raw paths, native details, SIDs, descriptor bytes, and access-token details never
enter serialized error messages.

## Hermetic And Native Verification Matrix

The next shared-capability seam modifies only:

- `steps/common/windows_held_handle.py`; and
- `tests/unit/test_windows_held_handle.py`.

RED/GREEN evidence must prove:

1. exact constructor and method signatures, exact two-profile validation, exact
   four-symbol module export, and only one added public method;
2. default profile access values and native dependency surface are unchanged;
   the security profile binds exact pointer-width `argtypes`/`restype` for
   every required Advapi32/Kernel32 export, and missing/partial exports fail
   before a usable backend exists;
3. security profile leaves the root at `0x81`, opens descendants at `0x20081`,
   and changes no share or flag;
4. root/default/foreign/closed/post-context tokens fail before a security native
   call;
5. `GetSecurityInfo` receives the exact raw handle behind the accepted token and
   the exact object/security-information constants;
6. the returned descriptor equals independently scripted bytes exactly,
   including embedded NUL and tail bytes, and remains equal after `LocalFree`
   poisons the source allocation; every successful non-null output is freed
   exactly once, and error-path output is ignored;
7. invalid descriptor, invalid revision/control, null success pointer,
   below/above-bound length, native error, and malformed copy all fail closed in
   the selected order;
8. `GetSecurityDescriptorControl` captures its error before cleanup can change
   thread error state; `LocalFree` success/failure and primary-versus-cleanup
   precedence are covered on every result quadrant;
9. existing observer/backend suites remain unchanged and green; and
10. one Windows-native temporary-file witness opens only a test-created
    descendant through enumeration and `OpenFileById`, obtains a descriptor,
    validates its detached form, and changes no ACL.

No native process-token or live trust-root witness belongs in this two-file
seam. Token and access-decision semantics remain hermetic until the later reader
source/test seam.

## Boundaries And Handoff

This decision used repository source/tests and current official Win32 contracts.
It did not resolve or inspect live ProgramData, a pin, token, ACL, configured
root, service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup
target.

After this document is checkpointed, implement only the two-file shared
descriptor capability through RED/GREEN/refactor and the focused matrix above.
Do not begin the external-pin reader until that capability has its own verified
checkpoint.
