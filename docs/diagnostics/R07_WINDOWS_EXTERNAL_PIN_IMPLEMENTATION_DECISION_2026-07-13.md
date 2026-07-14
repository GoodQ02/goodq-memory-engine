<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows External-Pin Implementation Decision

## Decision

Freeze the remaining reader-owned Windows ABI, parser, token-lifecycle,
security-policy, race, evidence, and error rules before RED. The future reader
remains exactly one no-argument, read-only production operation in
`cli/clean_memory_external_pin.py`, with focused tests only in
`tests/unit/test_clean_memory_external_pin.py`.

This checkpoint resolves ambiguities found by three independent read-only
implementation traces after the shared bounded-read and same-handle security-
descriptor capabilities were checkpointed. It adds no production or test code,
does not inspect a live token or trust root, and does not reopen any completed
seam.

## Governing Invariant

The reader may return evidence only when one internally consistent process-
primary token, one fixed Known Folder chain, one held physical-object chain,
one exact supported security policy, and one exact pin payload remain equal
through all selected fences. Native output that is unbounded, structurally
ambiguous, partially consumed, or not attributable to the held object fails
closed. No path, SID, token record, descriptor, ACL, payload duplicate, native
error, or caller assertion may leave the reader.

## No-Repeat Result

Keep these completed contracts closed:

- protected-membership projection and candidate-plan authority;
- the four-symbol held-handle backend export and opaque token lifecycle;
- root-only pathname opening and descendant `OpenFileById` traversal;
- physical identity, object snapshot, stream, membership, and race semantics;
- exact 1-through-66-byte same-handle bounded reads;
- the opt-in `security_read` profile and detached self-relative descriptor
  copy; and
- the external-pin source, fixed chain, static security policy, thirteen-code
  failure table, and separation from enrollment, publication, composition,
  planning, and execution.

The reader must consume those public capabilities. It must not import backend
private symbols, inspect opaque-token fields, duplicate traversal, reopen a
descendant by pathname, or reconstruct a descriptor.

## Exact Public Result Contract

The module export remains exactly:

```python
__all__ = (
    "EXTERNAL_PIN_EVIDENCE_SCHEMA",
    "ExternalPinReaderError",
    "ExternalPinEvidence",
    "read_external_pin",
)
```

`EXTERNAL_PIN_EVIDENCE_SCHEMA` is exactly
`goodq.clean-memory-external-pin-evidence.v1`.

`ExternalPinReaderError` follows the completed immutable-code error pattern:
it is a `RuntimeError`, accepts only one of the thirteen closed codes, exposes
one immutable `.code`, and serializes only the fixed path-free message.

`ExternalPinEvidence` follows the completed projection-object pattern:

- `@dataclass(frozen=True, init=False)`;
- private canonical compact sorted-key UTF-8 JSON storage;
- private classmethod `_from_projection(...)` as the only constructor;
- a `.projection` property that returns a newly detached mapping on every
  access; and
- immutable `external_pin_evidence_sha256`, computed from the exact private
  canonical projection bytes.

The canonical projection has exactly ten top-level keys. The displayed object
in the boundary audit is authoritative; any reference to nine fields is a
counting error, not permission to omit a key:

```text
anchor_identity
dedicated_directory_identities
enrolled_reader_identity_sha256
manifest_sha256
pin_file_identity
platform
schema
security_policy_sha256
source_id
source_schema
```

No public constructor, raw projection text, parsed native record, or private
dependency-injection surface is exported.

## Native Availability Boundary

All reader-owned Windows DLLs and required security exports are bound lazily
with `ctypes.WinDLL(..., use_last_error=True)` before any observation or handle
acquisition. The reader then constructs
`WindowsHeldHandleBackend(access_profile="security_read")`, without opening a
handle, so the backend binds its own base file/volume/enumeration/open-by-ID
surface. V1 binds only the fixed Known Folder, token, mapping, access-check,
memory-release, handle-close, and shared-backend surface selected by the
audits.

Classification is exact:

- non-Windows, missing Known Folder locator support, or missing base held-
  handle/file/volume/enumeration/open-by-ID support is
  `unsupported_platform`;
- missing token, duplication, descriptor, ACL, mapping, or access-check support
  is `unsupported_security`; and
- a native call that is present but fails is `observation_failed` unless a
  more specific closed code applies.

Before that construction, the reader verifies availability of the security-
only exports the backend requires. This closes the backend's intentionally
coarser `unsupported_platform` constructor result without bypassing the backend
or calling its security functions independently. After that preflight, a
backend construction failure retains its base `unsupported_platform`
classification.

The reader never binds or calls `IsTokenRestricted`, never queries reserved
`TokenIsRestricted`, and never installs an impersonation token on a thread.

## Known Folder And Chain Selection

The source remains the actual `FOLDERID_ProgramData` value returned by:

```text
SHGetKnownFolderPath(FOLDERID_ProgramData, KF_FLAG_DEFAULT, NULL, &path)
```

The output slot starts null. As required by the Known Folder contract, every
non-null returned buffer is owned and released exactly once with
`CoTaskMemFree`, whether the HRESULT succeeds or fails. A failure result is
never dereferenced. Success with a null output is `observation_failed`.
`CoTaskMemFree` has no result value; an exception while invoking the bound
release function follows the common cleanup-precedence rule and prevents
evidence.

The returned text must already be NFC, contain at most 32767 UTF-16 code units
and at most 64 non-root components, and satisfy the complete local-drive
lexical contract from the boundary audit. Any noncanonical, redirected,
environment-shaped, relative, root-only, or otherwise invalid lexical form is
`redirected_boundary`; a failing locator call is `observation_failed`.

Only the drive root is opened by pathname. Every ProgramData and fixed child
component is first sought through one complete held-parent probe enumeration.
Comparison uses NFC casefold keys. More than one entry with the same comparison
key, including canonically distinct spellings, is `duplicate_identity`. One
expected entry is opened by physical ID and immediately snapshotted. The
selected entry retains its complete detached `WindowsDirectoryEntry`, parent
snapshot, and full probe tuple for final recheck.

Stable absence is proven, not inferred. The probe may discover possible
absence, but it never authorizes `pin_missing`. When a required component or pin
is absent from the probe, the reader performs this exact bracket on the same
held parent:

1. pre-operation transient effective-token snapshot;
2. complete probe entry tuple;
3. parent object snapshot;
4. first fresh complete proof entry tuple;
5. second fresh complete proof entry tuple;
6. parent object snapshot; and
7. equal post-operation transient effective-token snapshot.

Only identical token snapshots, parent snapshots, and all three complete entry
tuples, with the expected comparison key absent from every tuple, permit
`pin_missing`. Any difference or proof-pass appearance is
`observation_raced`. A proof-pass appearance is never promoted into present
selection. No partial or name-only membership comparison is sufficient.

## Pure Security-Descriptor Parser

V1 uses a private bounded byte parser. It does not add
`ConvertSidToStringSidW`, ACL helper calls, or another native allocation and
cleanup surface. The parser and every `AccessCheck` consume one pinned ctypes
copy of the exact detached bytes returned by the held-handle backend.

### SID form

A supported SID has revision 1, at most 15 subauthorities, exact size
`8 + 4 * SubAuthorityCount`, a six-byte big-endian identifier authority, and
little-endian unsigned DWORD subauthorities. Its numeric form is derived only
from those bytes as `S-1-<authority>-<subauthority>...`, using ordinary decimal
integers without leading zeroes. Binary SID bytes are the equality and sorting
authority; rendered text is derived evidence input only.

Every SID pointer inside a token-information buffer must address a complete SID
wholly within that same returned buffer. A pointer escape, malformed SID, or
partial binary alias is `observation_failed`.

### Self-relative descriptor form

The exact self-relative header is `<BBHIIII>` and 20 bytes. Revision is 1,
`Sbz1` is zero, `SE_SELF_RELATIVE` is set, owner/group/DACL offsets are nonzero
and four-byte aligned, and the unrequested SACL offset is zero. Owner, primary
group, and DACL components must be complete and in bounds.

Component intervals may not partially overlap. Exact owner/group SID interval
aliasing is accepted only when their parsed binary SIDs are identical. No DACL
or other alias is accepted. Bytes not consumed by the header or a parsed
component must be zero. Nonzero gaps or trailing bytes are malformed native
output.

The ACL header is `<BBHHH>` and eight bytes. Reserved fields are zero, ACE count
is at most 4096, and each ACE prefix is `<BBHI>`. A supported ordinary allow or
deny ACE has exact size `8 + sid_size`; internal trailing bytes are forbidden.
The ACE sequence may leave only zero ACL padding. Every ACL byte is therefore
either structurally interpreted or required to be zero.

ACL revisions 2 and 4 are structurally supported. Other well-formed revisions,
a requested component that is absent, a nonzero SACL, or an unsupported ACE
type is `unsupported_security`. Truncation, impossible offsets, partial
overlap, invalid reserved values, invalid SID/ACE/ACL lengths, nonzero unbound
bytes, or count/size disagreement is `observation_failed`. A structurally
supported descriptor that violates the fixed owner, group, DACL, ACE, mask,
order, flag, or access policy is `security_policy_mismatch`.

### ACE flags and inheritance

Anchor ordinary allow/deny ACEs accept only the defined inheritance flags
`OBJECT_INHERIT_ACE`, `CONTAINER_INHERIT_ACE`,
`NO_PROPAGATE_INHERIT_ACE`, `INHERIT_ONLY_ACE`, and `INHERITED_ACE`
(`0x1f` combined mask). Any other flag bit is `unsupported_security`. An anchor
ACE applies to the anchor itself exactly when `INHERIT_ONLY_ACE` (`0x08`) is
clear. The completed conservative dangerous-allow rule is evaluated only for
those self-applicable ACEs; every ACE still remains in original-order policy
evidence.

Dedicated directories and the pin require flags zero. In addition to the
already-selected control bits, `SE_DACL_AUTO_INHERITED` must be clear. Thus
dedicated inheritance is both protected and not requested, inherited, or
defaulted.

## Token ABI And Bounded Snapshot

### Fixed ABI and caps

V1 is an exact Win64 ABI. `ctypes.sizeof(ctypes.c_void_p)` must equal eight;
another Windows pointer width is `unsupported_security`. Scalar bindings are:

```text
BOOL and enum:       c_int32
DWORD:               c_uint32
LONG / HRESULT:      c_int32
WORD:                c_uint16
BYTE:                c_ubyte
HANDLE / PSID / PVOID: c_void_p
LARGE_INTEGER:       c_int64
```

Required structures and Win64 layouts are exact:

| Structure | Size and required offsets |
| --- | --- |
| `GUID` | 16 bytes: DWORD, WORD, WORD, BYTE[8] |
| `LUID` | 8 bytes |
| `LUID_AND_ATTRIBUTES` | 12 bytes |
| `SID_AND_ATTRIBUTES` | 16 bytes; `Attributes` at offset 8 |
| `TOKEN_USER` | 16 bytes |
| `TOKEN_GROUPS` | `GroupCount` at 0; first group at offset 8 |
| `TOKEN_PRIVILEGES` | `PrivilegeCount` at 0; first privilege at offset 4 |
| `TOKEN_MANDATORY_LABEL` | 16 bytes |
| `TOKEN_ELEVATION` | 4 bytes |
| `TOKEN_STATISTICS` | 56 bytes; group/privilege counts at 40/44 and `ModifiedId` at 48 |
| `GENERIC_MAPPING` | 16 bytes |
| `PRIVILEGE_SET` | 8-byte header; 12 bytes per privilege record |

Function bindings are exact:

| DLL/export | `argtypes` | `restype` |
| --- | --- | --- |
| Kernel32 `GetCurrentThread` | `[]` | `HANDLE` |
| Kernel32 `GetCurrentProcess` | `[]` | `HANDLE` |
| Kernel32 `CloseHandle` | `[HANDLE]` | `BOOL` |
| Shell32 `SHGetKnownFolderPath` | `[POINTER(GUID), DWORD, HANDLE, POINTER(PVOID)]` | `HRESULT` |
| Ole32 `CoTaskMemFree` | `[PVOID]` | `None` |
| Advapi32 `OpenThreadToken` | `[HANDLE, DWORD, BOOL, POINTER(HANDLE)]` | `BOOL` |
| Advapi32 `OpenProcessToken` | `[HANDLE, DWORD, POINTER(HANDLE)]` | `BOOL` |
| Advapi32 `GetTokenInformation` | `[HANDLE, enum, PVOID, DWORD, POINTER(DWORD)]` | `BOOL` |
| Advapi32 `LookupPrivilegeValueW` | `[c_wchar_p, c_wchar_p, POINTER(LUID)]` | `BOOL` |
| Advapi32 `DuplicateTokenEx` | `[HANDLE, DWORD, PVOID, enum, enum, POINTER(HANDLE)]` | `BOOL` |
| Advapi32 `MapGenericMask` | `[POINTER(DWORD), POINTER(GENERIC_MAPPING)]` | `None` |
| Advapi32 `AccessCheck` | `[PVOID, HANDLE, DWORD, POINTER(GENERIC_MAPPING), PVOID, POINTER(DWORD), POINTER(DWORD), POINTER(BOOL)]` | `BOOL` |

Token-information classes are exactly `TokenUser=1`, `TokenGroups=2`,
`TokenPrivileges=3`, `TokenStatistics=10`, `TokenRestrictedSids=11`,
`TokenElevationType=18`, `TokenElevation=20`, `TokenHasRestrictions=21`,
`TokenIntegrityLevel=25`, `TokenUIAccess=26`, and
`TokenIsAppContainer=29`. Token/source/impersonation constants remain
`TokenPrimary=1`, `TokenImpersonation=2`, and
`SecurityImpersonation=2`. `TOKEN_DUPLICATE=0x0002`,
`TOKEN_QUERY=0x0008`, `ERROR_INSUFFICIENT_BUFFER=122`, and
`ERROR_NO_TOKEN=1008`.

Every native count is converted only after its enclosing buffer is bounded.
Private caps are exact:

```text
maximum token-information buffer: 1048576 bytes
maximum groups:                    4096
maximum restricted SIDs:           4096
maximum privileges:                4096
maximum SID subauthorities:           15
maximum SID bytes:                    68
```

Each `TokenStatistics` query is one 56-byte call. Each fixed
`TokenElevationType`, `TokenElevation`, `TokenHasRestrictions`,
`TokenUIAccess`, and `TokenIsAppContainer` query is one four-byte call. Before
each fixed call, its output is initialized deterministically and
`ReturnLength` is `0xffffffff`. Required semantic fields use whole-field out-of-
domain sentinels: enum/BOOL values are `-1`, while the statistics token type,
group count, and privilege count are likewise initialized outside their accepted
domains. The complete statistics buffer is initialized deterministically, but
`ImpersonationLevel` is unspecified when `TokenType == TokenPrimary`; that DWORD
is never validated, canonicalized, digested, or compared. Success requires the
exact expected `ReturnLength` and fully valid defined semantic fields. Failure
captures last error immediately and ignores every output. A success that leaves
a required defined semantic field at its sentinel, reports a short/long length,
or returns an out-of-domain enum/BOOL is `observation_failed`.

Variable `TokenUser`, `TokenGroups`, `TokenPrivileges`,
`TokenRestrictedSids`, and `TokenIntegrityLevel` queries use one null/zero
sizing call, require `ERROR_INSUFFICIENT_BUFFER`, reject zero or over-capacity
requirements, allocate exactly once with every byte set to `0xa5`, reset
`ReturnLength` to `0xffffffff`, and require a successful fill whose reported
length equals the sizing result. Failure captures last error immediately and
ignores every output. The byte fill is deterministic initialization only:
padding/slack is ignored, and a legitimate SID, LUID, pointer, timestamp, or
other payload byte equal to `0xa5` is never rejected by byte occurrence. Only
`ReturnLength` and required parsed pointer/count/record fields are validated.
Any size change, count beyond the fixed cap, pointer escape, incomplete record,
or semantically invalid required field is `observation_failed`.

The canonical medium integrity SID is exactly `S-1-16-8192`, not merely any
SID whose last subauthority happens to be `0x2000`.

### Internal query order

Each full token snapshot has an internal statistics fence and this exact order:

1. `TokenStatistics` before;
2. `TokenUser`;
3. `TokenGroups`;
4. `TokenPrivileges`;
5. `TokenRestrictedSids`;
6. `TokenElevationType`;
7. `TokenElevation`;
8. `TokenHasRestrictions`;
9. `TokenIntegrityLevel`;
10. `TokenUIAccess`;
11. `TokenIsAppContainer`; and
12. `TokenStatistics` after.

This is semantic information-class order. In the native-call trace, each
variable query (`TokenUser`, `TokenGroups`, `TokenPrivileges`,
`TokenRestrictedSids`, and `TokenIntegrityLevel`) appears twice in place: first
for its null/zero sizing call and then for its fill call. The fixed-size and
statistics queries appear once. Tests preserve all 17 native calls rather than
compressing the trace.

```text
(10, 1, 1, 2, 2, 3, 3, 11, 11, 18, 20, 21, 25, 25, 26, 29, 10)
```

The two statistics records must have equal canonical primary-token projections:
`TokenId`, `AuthenticationId`, `ExpirationTime`, `TokenType`, `DynamicCharged`,
`DynamicAvailable`, `GroupCount`, `PrivilegeCount`, and `ModifiedId`.
`ImpersonationLevel` is excluded. Group and privilege counts must equal the
statistics projection. Every canonical field is parsed before the snapshot can
be compared. A changed, well-formed defined field at an outer fence is
`observation_raced`; malformed output or an inconsistent internal snapshot is
`observation_failed`.

`LookupPrivilegeValueW(NULL, "SeChangeNotifyPrivilege", ...)` is resolved once
after ABI binding and before accepting the baseline token. Only that exact LUID
may be enabled. Lookup failure is `observation_failed`.

## Token Ownership And Fence Cadence

The reader owns one retained baseline process-token handle:

1. initialize thread output null and call
   `OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, ...)`;
2. only failure with `ERROR_NO_TOKEN` permits fallback;
3. a successful non-null thread token records `untrusted_reader` as the primary
   result, then attempts its one close;
4. call `OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE,
   ...)`; and
5. retain that successful non-null process token for the baseline snapshot and
   as the sole `DuplicateTokenEx` source.

For both open functions, success/null is `observation_failed` and owns nothing;
failure output is undefined and is never inspected or closed, even when a fake
native implementation writes a sentinel. Pseudo-handles are never closed.

Every later comparison opens a prompt transient process token with only
`TOKEN_QUERY`, takes one full snapshot, and closes it before continuing. A
newly discovered thread token during comparison records `observation_raced` as
the primary result, then attempts its one close. Any failed close captures last
error immediately and adds only the sanitized cleanup result under the common
precedence rule; it never replaces the recorded primary. The retained baseline
handle is never replaced by a comparison handle.

Outer token pairs bracket:

- Known Folder resolution;
- drive-root acquisition, filesystem proof, and initial snapshot;
- every individual chain-component selection;
- every individual descriptor observation/static-policy check;
- every individual object effective-access check;
- the pin read and same-handle object comparison; and
- the aggregate final descriptor/object/stream/parent recheck.

Every snapshot must equal the accepted baseline projection exactly.

## Two-Stage Enrollment Binding

Initial token acceptance is intrinsic. It validates token source/type,
elevation, integrity, restrictions, AppContainer/UIAccess, group attributes,
privileges, counts, and duplicate records, but it does not yet claim that
`TokenUser` is enrolled. An intrinsic violation is `untrusted_reader`.

After the ProgramData anchor and three dedicated directories are held:

1. parse and validate their static descriptors;
2. require the third ACE SID of `GoodQ`, `authority`, and `clean-memory` to be
   byte-identical;
3. call that common SID the enrolled reader;
4. compare it with baseline `TokenUser`; and
5. reject a mismatch as `untrusted_reader`.

Disagreement among the three dedicated directory DACLs is
`security_policy_mismatch`. After the pin is selected, its third ACE SID must
equal the already-bound enrolled SID or it is likewise
`security_policy_mismatch`.

This order distinguishes a valid but unenrolled process token from a malformed
or inconsistent enrolled policy without trusting either one prematurely.

## Effective-Access Checks

Static descriptor parsing completes before any pin content read. The fixed
file-object `GENERIC_MAPPING`, raw-mask preservation, desired rights, and check
order remain exactly as checkpointed.

Each of the five security objects—ProgramData anchor, three dedicated
directories, and pin—gets one separate effective-access phase:

1. equal transient process-token snapshot;
2. `DuplicateTokenEx` from the retained baseline handle with exactly
   `TOKEN_QUERY`, null attributes, `SecurityImpersonation`, and
   `TokenImpersonation`;
3. all fixed per-right `AccessCheck` calls for that one object using the same
   duplicate and same pinned descriptor copy;
4. close the duplicate exactly once; and
5. equal transient process-token snapshot.

At most one duplicate is live. It is never installed on a thread. Success/null
owns nothing and is `observation_failed`; failure output is undefined and is
never inspected or closed; success/non-null is owned until the one close.

### Fresh per-right outputs and privilege set

Every right gets fresh output storage. Before every `AccessCheck`, the privilege
buffer is newly zeroed, `PrivilegeSetLength` is reset to capacity,
`AccessStatus` is initialized to the out-of-domain signed-BOOL value `-1`, and
`GrantedAccess` is initialized to `0xffffffff`. Success requires
`AccessStatus` to become exactly `0` or `1`. These non-result sentinels prevent
an omitted native write or a stale prior result from masquerading as a
successful denial or grant.

The capacity remains
`8 + 12 * max(1, accepted_privilege_count)`, bounded by 49160 bytes. No null
sizing probe is used. `PrivilegeSetLength` starts at capacity.

Microsoft documents the parameter as input/output size but does not promise
that a successful call rewrites it to one canonical used length. Therefore a
successful result accepts a returned length only from 8 through capacity. The
reported `PrivilegeCount` must fit both that length and the accepted-token count
and may not exceed 4096. Parsed records must be complete; any reported trailing
bytes must remain zero. `Control` may contain only
`PRIVILEGE_SET_ALL_NECESSARY`.

After privilege-output validation, the successful result matrix is disjoint:

- `AccessStatus == FALSE` and `GrantedAccess == 0`, with zero
  `PrivilegeCount` and zero `Control`, is the required denial;
- `AccessStatus == TRUE` and `GrantedAccess` exactly equal to the one mapped
  desired mask is `security_policy_mismatch`; and
- every other successful status/grant form is `observation_failed`, including
  true with extra/missing bits or false with nonzero grant.

Native failure captures last error immediately, ignores all output values, and
is `observation_failed`; `ERROR_INSUFFICIENT_BUFFER` never triggers a retry.

Official contracts:

- [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
- [OpenThreadToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openthreadtoken)
- [OpenProcessToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken)
- [DuplicateTokenEx](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-duplicatetokenex)
- [AccessCheck](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- [PRIVILEGE_SET](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-privilege_set)

## Exact Operation Order

The implementation and trace oracle use this one order:

1. reject non-Windows; bind/preflight every reader/security ABI and construct
   the handle-free `security_read` backend so its base ABI is also bound;
2. resolve the one permitted privilege LUID;
3. acquire, intrinsically validate, and retain the baseline process token;
4. bracket, resolve, validate, copy, and release the Known Folder result;
5. in one token bracket, use the preconstructed backend to open only the drive
   root by path, prove fixed NTFS/ReFS/open-by-ID support, and retain
   `snapshot(root, filesystem=filesystem, expected=None,
   object_kind="directory", require_stream_contract=True)`;
6. bracket each actual ProgramData component probe-or-prove selection;
   immediately snapshot every successfully opened expected directory with
   `snapshot(child, filesystem=filesystem, expected=entry,
   object_kind="directory", require_stream_contract=True)`, prove same-volume
   identity, and retain its complete snapshot plus every held-parent tuple; the
   final component is the anchor;
7. bracket `GoodQ`, `authority`, and `clean-memory` probe-or-prove selection;
   immediately snapshot each expected directory, prove same-volume identity,
   and retain the complete snapshots;
8. bracket descriptor/static-policy observation for the anchor and three
   directories, bind the common enrolled reader, and compare `TokenUser`;
9. run one bracketed effective-access phase for the anchor and each directory;
10. bracket exact pin-leaf probe-or-prove selection without reading content;
    immediately call
    `snapshot(..., expected=pin_entry, object_kind="regular_file",
    require_stream_contract=True)`, prove same-volume identity, ordinary-file,
    no-reparse/device, link-count-one, exact unnamed-stream, and size-65 state,
    and retain that complete snapshot;
11. only after the pin snapshot succeeds, bracket its descriptor/static-policy
    observation, require the bound reader SID, and run its one bracketed
    effective-access phase;
12. bracket exactly one `read_file_bounded(pin, maximum_bytes=66)` call and a
    repeated same-handle snapshot; require the complete snapshot to equal the
    retained selection snapshot, 65 bytes, explicit EOF, and exactly 64
    lowercase hexadecimal bytes plus LF;
13. in one final token bracket, re-read every descriptor byte-for-byte, repeat
    the same root/directory/pin snapshot calls and compare every complete
    snapshot, and re-enumerate every retained parent to the complete original
    entry tuple;
14. build the exact ten-key detached evidence candidate from the retained
    shared identity projections;
15. close backend-held resources, then the retained process token, attempting
    every reverse-order cleanup; and
16. return evidence only if operation and cleanup both succeeded.

No partial evidence is returned. The manifest digest is the parsed 64-byte pin
text, not a second hash or a manifest read.

## Cleanup And Error Precedence

Every owned resource is closed once in reverse acquisition order. Immediate
resources—Known Folder buffers, transient comparison tokens, and duplicate
tokens—are released at their fixed fence. Backend-held descendants and root are
closed before the retained baseline process token.

A primary operation failure remains primary. The first cleanup failure becomes
its cause only when no cause exists; otherwise it becomes context. Both nodes
are sanitized `ExternalPinReaderError` values with only fixed codes/messages.
Additional cleanup attempts still run. Cleanup failure without a primary
failure becomes `observation_failed` and prevents evidence. No cleanup is
retried.

The closed thirteen-code table remains unchanged. This checkpoint adds these
exact edge classifications:

- invalid Known Folder lexical form: `redirected_boundary`;
- stable, fully bracketed chain or pin absence: `pin_missing`;
- supported descriptor with wrong policy: `security_policy_mismatch`;
- well-formed but unsupported security structure: `unsupported_security`;
- malformed native buffer or impossible cross-field output:
  `observation_failed`;
- intrinsic token or enrolled-reader mismatch: `untrusted_reader`; and
- any equal-authority fence change: `observation_raced`.

Raw native exceptions and details may be used transiently inside private
translation logic but are suppressed before the public boundary. Every
caller-visible `__cause__`/`__context__` node, when present for cleanup
precedence, must itself be a fixed path-free `ExternalPinReaderError`; no
`OSError`, HRESULT, Win32 message/code, ctypes error, path, SID, descriptor, or
token detail may escape. This deliberately narrows the earlier boundary-audit
allowance for raw detail in chained causes because Python exception chains are
caller-visible. RED walks the complete public exception chain.

## Focused RED Gate

Before GREEN, the two-file seam must demonstrate RED for:

1. exact four-export/no-argument/import-pure public contract and detached
   ten-key evidence;
2. lazy DLL/export classification and exact pointer-width signatures;
3. Known Folder ownership, lexical bounds, root-only opening, component
   collision, one probe plus two fresh proof enumerations when absent, stable
   absence, and no fallback;
4. every SID/descriptor/ACL/ACE boundary, accepted zero padding, component
   overlap rule, anchor flags, and dedicated inheritance bit;
5. every token-buffer bound, internal query-order fence, intrinsic acceptance,
   canonical digest, whole-field sentinel rule, valid `0xa5` payload/padding
   cases, acceptance of two valid primary-token statistics records that differ
   only in undefined `ImpersonationLevel`, handle-output quadrant, and cleanup
   order;
6. two-stage reader enrollment and its exact error precedence;
7. one duplicate per object, fixed right order, generic mapping, privilege-
   output bounds, omitted-output sentinels, every `AccessCheck` result quadrant,
   and duplicate cleanup;
8. security-before-content, the single bounded read, exact payload, and every
   descriptor/object/stream/membership/token recheck mutation;
9. all thirteen constant error code/message pairs, complete sanitized exception-
   chain privacy, cleanup precedence, and no partial evidence; and
10. static containment: no membership composition, configuration, manifest
    read, Qdrant, planning, job, token-publication, cleanup, private backend
    symbol, or descendant-path reopen.

Then pass the completed backend/observer suites, approved R-07 authority union,
compilation, import-purity, documentation, banned-token, dependency, and diff
gates before any checkpoint.

## Boundaries And Handoff

This decision used only repository source, tests, prior R-07 evidence, three
independent read-only traces, and current official Win32 documentation. It did
not read or change live ProgramData, a pin, a token, an ACL, a configured root,
a service, GoodQ data, Qdrant, an evidence store, a job, MiniAgent, or a cleanup
target.

The next bounded seam is exactly the reader source/test pair through
RED/GREEN/refactor. Enrollment, publication, rotation, recovery, authenticated
membership composition, protected-member observation, Qdrant observation,
runnable planning, cleanup execution, and live trust-root verification remain
closed.
