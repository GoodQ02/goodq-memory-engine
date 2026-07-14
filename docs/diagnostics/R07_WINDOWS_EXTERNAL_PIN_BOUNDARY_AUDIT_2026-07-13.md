<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows External-Pin Boundary Audit

## Decision

Do not implement the external-pin reader yet. First extract the already-proven
Windows held-handle machinery from `cli/clean_memory_filesystem.py` into one
projection-neutral shared backend and prove exact behavioral parity.

The next implementation seam is one rollback unit with exactly these files:

- add `steps/common/windows_held_handle.py`;
- adapt `cli/clean_memory_filesystem.py`;
- add `tests/unit/test_windows_held_handle.py`; and
- adapt `tests/unit/test_clean_memory_filesystem.py`.

This extraction adds no Known Folder lookup, token or ACL authority, external-
pin parser, reader evidence, enrollment, publication, rotation, protected-
member observation, plan composition, or cleanup behavior. The completed
filesystem observer keeps its exact four-symbol public API and exact outward
errors.

Only after this extraction passes parity may a separate Windows pin-reader seam
add the security-specific APIs selected below. Importing private observer
symbols or copying their implementation is forbidden.

## Governing Invariant

The external pin is the independent authorization source for exact manifest
bytes. Configuration and protected-membership projection provide routing and
structure only. No reader result may exist unless one production-owned
operation proves the fixed source, effective reader, physical chain, security
policy, exact payload, and all final rechecks without pathname fallback.

This audit inspected source, tests, governance documents, and current official
Win32 API contracts only. It did not resolve or inspect the live ProgramData
location, trust-root chain, pin, token, ACL, configuration, service, or GoodQ
data.

## No-Repeat Result

The following work remains closed:

- candidate-plan authority checkpoint `c870a1cb`;
- configuration projection checkpoint `a12ceb18`;
- filesystem observer public contract, outward evidence/errors, POSIX behavior,
  and traversal invariants from checkpoint `e8961889` (only its private Windows
  backend ownership is reopened for extraction);
- protected-boundary audit checkpoint `f01e03a7`;
- duplicate canonical-envelope guard checkpoint `4230a910`;
- source/trust decision checkpoints `8bfa5d27` and `69f4a91e`;
- protected-authority semantics checkpoint `9328e89e`; and
- protected-membership projection checkpoint `81aafce1`.

The July corpus, configured roots, live services, approval/job authority, and
cleanup executor remain outside this seam.

## Three-Trace Reconciliation

### Trace A — current platform capability

The private `_WindowsApi` already proves:

- lazy Win32 ABI binding;
- fixed-volume gating with `DRIVE_FIXED`;
- exact NTFS/ReFS plus `FILE_SUPPORTS_OPEN_BY_FILE_ID` support;
- drive-root-only pathname opening;
- complete held-directory restart enumeration;
- 64-bit NTFS and 128-bit ReFS `OpenFileById` descendant opening;
- no-follow reparse/device/type rejection;
- physical identity, size, timestamps, link count, and stream state from one
  held handle;
- same-handle content hashing; and
- before/after object and parent-membership comparison.

The implementation is concentrated at
`cli/clean_memory_filesystem.py:808-1680`; the held traversal and final parent
rechecks are at `cli/clean_memory_filesystem.py:1680-1841`. Native and hermetic
oracles cover ABI/flags, NTFS/ReFS IDs, enumeration, sharing conflicts,
same-handle state, root-only pathname use, and parent drift in
`tests/unit/test_clean_memory_filesystem.py`.

The repository has no implementation of `SHGetKnownFolderPath`,
`OpenThreadToken`, `OpenProcessToken`, complete `GetTokenInformation` state,
`GetSecurityInfo`, owner/DACL canonicalization, ACE policy validation,
`AccessCheck`, or the exact 65-byte pin read. Environment-derived ProgramData
helpers and boolean administrator tests are not authority.

### Trace B — security and evidence contract

The canonical semantics already fix the source ID, actual ProgramData Known
Folder locator, constant child chain, exact 65-byte payload, effective-token
precedence, administrator-owned protected DACL, ordinary-reader rights,
security-before-content order, same-handle read, and final token/descriptor/
identity/metadata/membership rechecks.

The remaining choices are selected below: the exact evidence JSON, evidence
digest, token preimage and acceptance matrix, security-policy preimage and
anchor oracle, Known Folder flags, reader public API, and finite error table.

### Trace C — ownership alternatives

All three traces rejected:

- reader-local duplication, because it creates two security-critical ABI and
  handle implementations;
- importing or exposing `_WindowsApi`, because it breaks the sealed observer
  API and makes the reader depend upward on cleanup projection policy;
- extending `atomic_io`, because its pathname-based operations do not prove a
  held no-follow chain; and
- combining extraction with new token/ACL/reader behavior, because that mixes
  proven mechanics with unimplemented security authority in one rollback.

The selected shared module preserves the established dependency direction
`cli -> steps.common` and imports no `cli` type.

## Selected Shared Held-Handle Boundary

`steps/common/windows_held_handle.py` will export exactly, in this order:

```text
WindowsHeldHandleError
WindowsDirectoryEntry
WindowsObjectSnapshot
WindowsHeldHandleBackend
```

All Win32 constants, structures, raw calls, and helpers remain private. The
module is standard-library-only and import-pure. `ctypes.WinDLL` is loaded only
when `WindowsHeldHandleBackend()` is instantiated on Windows.

`WindowsDirectoryEntry` is frozen and contains only the enumerated name,
attributes, exact file-ID kind, and exact file ID. It provides no pathname.

`WindowsObjectSnapshot` is frozen and contains the raw state required for
equality plus the one shared canonical physical-identity projection:

```text
volume_serial
file_id_kind
file_id
object_kind
size_bytes
mtime_ns
allocation_size
link_count
attributes
reparse_tag
last_write_ticks
change_ticks
streams
```

Its read-only `identity_projection` property returns a detached object with
exactly `file_id`, `file_id_kind`, `object_kind`, `schema`, and
`volume_serial`; `schema` is `goodq.windows-file-identity.v1`, the volume serial
is 16 lowercase hexadecimal characters, and the file ID is 16 characters for
`ntfs_file_index_64` or 32 for `refs_file_id_128`. Its read-only
`identity_json` property is the canonical compact, sorted-key JSON rendering of
that projection. The shared snapshot is the sole owner of this renderer; the
observer retains only an outward-evidence parity assertion, and the future pin
reader embeds detached projections rather than recreating the schema.

`WindowsHeldHandleBackend` owns every handle it opens and returns an opaque,
private backend-issued token rather than a raw integer handle. A token is valid
only for the backend instance that issued it and only while registered live.
Explicit `close()` first validates ownership/liveness, then atomically marks and
deregisters the token before calling `CloseHandle`. A close failure leaves the
token permanently closed and is never retried. Foreign, repeated, post-context,
or otherwise invalid token use fails `observation_failed`. A failed open is
never registered.

The backend is a context manager. Normal or exceptional exit marks and closes
all retained live tokens in reverse registration order, attempts every close,
and rejects new operations after exit. With no primary exception it raises the
first close failure after attempting the remainder. With a primary exception it
re-raises that same exception with its traceback. If the primary has no existing
cause, the first close failure becomes its cause; otherwise the original cause
is preserved and the close failure becomes context. Its extraction-v1 methods
are exactly:

```text
open_root(root)
volume_filesystem(handle)
enumerate_directory(handle, filesystem)
open_by_id(volume_handle, entry, *, directory)
snapshot(handle, *, filesystem, expected, object_kind,
         require_stream_contract)
hash_file(handle)
close(handle)
```

The extraction preserves existing access/share/flag behavior exactly. It does
not add reader-specific `READ_CONTROL`, Known Folder, token, security
descriptor, bounded 65-byte read, or flush/publication methods. Those require a
later RED security seam after parity.

`WindowsHeldHandleError` has one immutable `.code`, a constant path-free
message, and only these codes:

| Code | Message |
| --- | --- |
| `unsupported_platform` | `Windows held-handle access is unsupported` |
| `unsupported_filesystem` | `Windows held-handle storage is unsupported` |
| `redirected_boundary` | `Windows held-handle boundary is redirected` |
| `unexpected_entry_type` | `Windows held-handle entry type is unsupported` |
| `duplicate_identity` | `Windows held-handle identity is ambiguous` |
| `sharing_conflict` | `Windows held-handle target is not quiescent` |
| `observation_raced` | `Windows held-handle state changed during observation` |
| `observation_failed` | `Windows held-handle observation failed` |

The CLI adapter maps those codes to its already-fixed
`FilesystemObservationError` messages. Raw paths and OS details remain only in
chained causes and are never serialized.

## Selected Future Reader Contract

After extraction parity, the separate reader module is
`cli/clean_memory_external_pin.py`, with focused tests in
`tests/unit/test_clean_memory_external_pin.py`. Its eventual public API is
exactly:

```text
EXTERNAL_PIN_EVIDENCE_SCHEMA
ExternalPinReaderError
ExternalPinEvidence
read_external_pin
```

`read_external_pin()` accepts no arguments. It accepts no path, SID, digest,
configuration, environment, backend, manifest bytes, or prior evidence.
Dependency injection remains private and test-only. POSIX returns
`unsupported_platform` in v1.

### Known Folder resolution

Windows v1 calls:

```text
SHGetKnownFolderPath(FOLDERID_ProgramData, KF_FLAG_DEFAULT, NULL, &path)
```

It does not use `KF_FLAG_CREATE`, `KF_FLAG_DONT_VERIFY`,
`KF_FLAG_DEFAULT_PATH`, an environment value, or a fallback. A returned buffer
is always released with `CoTaskMemFree` when non-null.

The returned text must be one NFC absolute local drive path with an uppercase
drive letter, no device/extended/UNC/volume-GUID prefix, environment syntax,
empty/dot/dot-dot component, control character, trailing separator, or
trailing dot/space component. The reader uses the text only to select the drive
root and component comparison values. It opens only the drive root by path and
then walks every actual ProgramData component and fixed child component by held
enumeration and `OpenFileById`.

Official API contracts used by this selection:

- [SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
- [KNOWN_FOLDER_FLAG](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/ne-shlobj_core-known_folder_flag)
- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- [OpenThreadToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openthreadtoken)
- [DuplicateTokenEx](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-duplicatetokenex)
- [TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)
- [IsTokenRestricted](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-istokenrestricted)
- [AccessCheck](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- [MapGenericMask](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-mapgenericmask)

Context7 resolved the current official Win32 reference as
`/websites/learn_microsoft_en-us_windows_win32_api`; direct Microsoft Learn
checks agreed.

### Effective reader identity

Every token snapshot first calls `OpenThreadToken` with `TOKEN_QUERY` and
`OpenAsSelf=TRUE`. Only `ERROR_NO_TOKEN` permits fallback to
`OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE, ...)`;
every other failure is final. Any discovered thread token is rejected and
closed. The accepted process-token handle is the sole source for both the
canonical snapshot and a later `DuplicateTokenEx` authorization token.

Ordinary reading accepts only:

- a process primary token; any thread impersonation token is
  `untrusted_reader` and never falls back;
- `TokenUser` equal to the one reader SID extracted identically from every
  dedicated DACL;
- `TokenElevation == 0` and the exact elevation type `Default` or `Limited`,
  never `Full`;
- exactly medium integrity RID `0x2000`;
- no restricting SIDs, no AppContainer, and no UIAccess;
- `TokenHasRestrictions == 0` for `Default` or `TokenHasRestrictions == 1` for
  `Limited`; every other pairing is rejected;
- a built-in Administrators group, when present, only as deny-only and not
  enabled; and
- no enabled privilege except `SeChangeNotifyPrivilege`.

`TokenHasRestrictions` means the token has ever been filtered. The reserved
`TokenIsRestricted` information class is never queried, and the
`IsTokenRestricted()` function is not used as a second oracle because it checks
only the restricting-SID list already required to be empty. A filtered UAC
`Limited` token is therefore accepted only with the exact deny-only group and
privilege rules above; a token with restricting SIDs is never accepted.

The implementation resolves the one permitted privilege to its LUID and rejects
every other enabled privilege, including backup, restore, take-ownership,
debug, impersonate, assign-primary-token, TCB, load-driver, manage-volume, and
create-symbolic-link privileges. Disabled privileges remain permitted and are
bound into evidence.

The effective token is reopened and its full canonical snapshot compared before
and after Known Folder resolution, each chain selection/security check, the pin
read, and final parent rechecks. A source-kind, token-ID, modified-ID, user,
group, restriction, integrity, elevation, impersonation, or privilege change is
`observation_raced`.

### Reader-identity digest preimage

`enrolled_reader_identity_sha256` is SHA-256 of canonical UTF-8 JSON with schema
`goodq.clean-memory-windows-reader-identity.v1` and exactly these keys:

```json
{
  "elevation": {"is_elevated": false, "type": "default"},
  "groups": [{"attributes": "<8-lowercase-hex>", "sid": "<numeric SID>"}],
  "has_restrictions": false,
  "impersonation_level": null,
  "integrity_rid": "00002000",
  "integrity_sid": "<numeric SID>",
  "is_app_container": false,
  "privileges": [{"attributes": "<8-lowercase-hex>", "luid": "<16-lowercase-hex>"}],
  "restricted_sids": [],
  "schema": "goodq.clean-memory-windows-reader-identity.v1",
  "token_source": "process",
  "token_statistics": {
    "authentication_id": "<16-lowercase-hex>",
    "expiration_time": "<signed-decimal>",
    "group_count": "<unsigned-decimal>",
    "modified_id": "<16-lowercase-hex>",
    "privilege_count": "<unsigned-decimal>",
    "token_id": "<16-lowercase-hex>"
  },
  "token_type": "primary",
  "ui_access": false,
  "user_sid": "<numeric SID>"
}
```

The shown object is the `Default` form. The only alternate accepted form changes
`elevation.type` to `limited` and `has_restrictions` to `true`; neither value is
normalized or collapsed in the digest.

SID-bearing arrays are sorted by binary SID. Privileges are sorted by unsigned
LUID. Counts must equal `TokenStatistics`; duplicate SID/LUID records fail
closed. The raw preimage never leaves the reader; only its digest is returned.

### Security-policy oracle and preimage

Owner, primary-group, and DACL data come only from `GetSecurityInfo` on already-
held handles, using `SE_FILE_OBJECT`, `OWNER_SECURITY_INFORMATION |
GROUP_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION`, and handles opened
with `READ_CONTROL`. Owner and primary-group SIDs must both be present and
valid, the DACL must be present and non-null, and the returned security-
descriptor buffer is released with `LocalFree`. V1 does not request the SACL or
enable `SeSecurityPrivilege`.

The ProgramData anchor owner and primary-group SIDs must each equal SYSTEM
(`S-1-5-18`) or built-in Administrators (`S-1-5-32-544`). Every ACE is parsed
and recorded in original order. Only ordinary access-allowed and access-denied
ACEs are supported; unknown, callback, conditional, or object ACE types fail
`unsupported_security`. `SE_DACL_PRESENT` must be set and
`SE_OWNER_DEFAULTED`, `SE_GROUP_DEFAULTED`, and `SE_DACL_DEFAULTED` must all be
clear.

For each ACE that applies to the anchor itself, the raw observed mask is copied
and generic bits are expanded in that checking copy with the file-object
mapping. Any non-SYSTEM/non-Administrators allow ACE whose expanded checking
mask contains
`FILE_DELETE_CHILD` (`0x00000040`), `WRITE_DAC` (`0x00040000`), or
`WRITE_OWNER` (`0x00080000`) fails `security_policy_mismatch`, even if a deny ACE
might otherwise reduce access. This conservative rule never infers safety from
complex ACL evaluation. Immediately between equal process-token snapshots,
`DuplicateTokenEx` creates a `SecurityImpersonation`/`TokenImpersonation` token
with `TOKEN_QUERY`; the accepted process-token handle supplies the required
`TOKEN_DUPLICATE`. That duplicate is checked separately with `AccessCheck` for
each of those three rights after `MapGenericMask`; every check must deny it. The
duplicate is never installed on a thread and is closed before the post-check
process-token snapshot.

Each `GoodQ`, `authority`, and `clean-memory` directory and the pin file must
have owner and primary group built-in Administrators, a present non-null
protected DACL,
inheritance disabled, no inherited/unrecognized/duplicate ACE, and exact
explicit allow ACEs in this order with flags zero. `SE_DACL_PRESENT` and
`SE_DACL_PROTECTED` must be set; `SE_OWNER_DEFAULTED`, `SE_GROUP_DEFAULTED`,
`SE_DACL_DEFAULTED`, and `SE_DACL_AUTO_INHERIT_REQ` must be clear:

| Principal | Directory mask | Pin-file mask |
| --- | --- | --- |
| SYSTEM | `001f01ff` | `001f01ff` |
| built-in Administrators | `001f01ff` | `001f01ff` |
| enrolled reader SID | `001200a1` | `00120089` |

No other ACE is accepted. Static DACL equality proves the enrolled reader has no
delete, DACL-write, owner-write, or file-write grant. `AccessCheck` separately
confirms `FILE_DELETE_CHILD`, `WRITE_DAC`, and `WRITE_OWNER` are denied on each
directory. On the pin it separately confirms `DELETE`, `FILE_WRITE_DATA`,
`FILE_APPEND_DATA`, `FILE_WRITE_EA`, `FILE_WRITE_ATTRIBUTES`, `WRITE_DAC`, and
`WRITE_OWNER` are denied.

`security_policy_sha256` is SHA-256 of canonical compact, sorted-key UTF-8 JSON
with this exact schema and key shape:

```json
{
  "anchor": {
    "dacl": [{"flags": "<2-lowercase-hex>", "mask": "<8-lowercase-hex>", "sid": "<numeric SID>", "type": "access_allowed"}],
    "dacl_revision": 2,
    "denied_access_checks": [
      {"denied": true, "mask": "00000040", "name": "file_delete_child"},
      {"denied": true, "mask": "00040000", "name": "write_dac"},
      {"denied": true, "mask": "00080000", "name": "write_owner"}
    ],
    "descriptor_control": "<4-lowercase-hex>",
    "owner_sid": "<numeric SID>",
    "physical_identity": {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "directory", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"},
    "primary_group_sid": "<numeric SID>",
    "role": "program_data_anchor"
  },
  "dedicated_objects": [
    {
      "dacl": [
        {"flags": "00", "mask": "001f01ff", "sid": "S-1-5-18", "type": "access_allowed"},
        {"flags": "00", "mask": "001f01ff", "sid": "S-1-5-32-544", "type": "access_allowed"},
        {"flags": "00", "mask": "001200a1", "sid": "<enrolled-reader-numeric-SID>", "type": "access_allowed"}
      ],
      "dacl_revision": 2,
      "denied_access_checks": [
        {"denied": true, "mask": "00000040", "name": "file_delete_child"},
        {"denied": true, "mask": "00040000", "name": "write_dac"},
        {"denied": true, "mask": "00080000", "name": "write_owner"}
      ],
      "descriptor_control": "<4-lowercase-hex>",
      "owner_sid": "S-1-5-32-544",
      "physical_identity": {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "directory", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"},
      "primary_group_sid": "S-1-5-32-544",
      "role": "goodq_directory"
    }
  ],
  "enrolled_reader_sid": "<numeric SID>",
  "platform": "windows",
  "schema": "goodq.clean-memory-windows-pin-security-policy.v1"
}
```

The `anchor.dacl` array has the complete accepted ACE sequence and may contain
only records whose `type` is `access_allowed` or `access_denied`.
`anchor.dacl_revision` is the observed unsigned integer `2` or `4`; each
dedicated revision is exactly `2`. `descriptor_control` encodes all 16 control
bits, not a selected subset. Every `dacl[].mask` is the eight-character raw
observed ACE mask; generic expansion occurs only in a separate checking copy and
never changes the digest preimage. The four `dedicated_objects` use the exact
same key shape and fixed role order `goodq_directory`, `authority_directory`,
`clean_memory_directory`, `pin_file`. The first three use the displayed
directory masks and three-check array. The pin uses reader mask `00120089`,
`object_kind="regular_file"`, and this fixed check order:
`delete`/`00010000`, `file_write_data`/`00000002`,
`file_append_data`/`00000004`, `file_write_ea`/`00000010`,
`file_write_attributes`/`00000100`, `write_dac`/`00040000`,
`write_owner`/`00080000`. Every `denied` value is exactly `true`.

The example's single dedicated object is one array-element schema, not an
abbreviation of the required four-element array. ACE flags are exactly two
lowercase hexadecimal characters; masks are exactly eight; SIDs are canonical
numeric strings. The preimage contains no path, display name, timestamp, handle,
or raw security-descriptor bytes. Only its digest leaves the reader.

### Exact path-free reader evidence

The canonical evidence projection is exactly:

```json
{
  "anchor_identity": {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "directory", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"},
  "dedicated_directory_identities": [
    {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "directory", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"},
    {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "directory", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"},
    {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "directory", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"}
  ],
  "enrolled_reader_identity_sha256": "<64-lowercase-hex>",
  "manifest_sha256": "<64-lowercase-hex>",
  "pin_file_identity": {"file_id": "<16-or-32-lowercase-hex>", "file_id_kind": "<ntfs_file_index_64|refs_file_id_128>", "object_kind": "regular_file", "schema": "goodq.windows-file-identity.v1", "volume_serial": "<16-lowercase-hex>"},
  "platform": "windows",
  "schema": "goodq.clean-memory-external-pin-evidence.v1",
  "security_policy_sha256": "<64-lowercase-hex>",
  "source_id": "goodq.clean-memory-protected-authority-pin.primary.v1",
  "source_schema": "goodq.clean-memory-external-pin-source.v1"
}
```

Every identity object uses the existing exact path-free Windows physical-
identity schema and kind. The directory array length and order are fixed as
`GoodQ`, `authority`, `clean-memory`; it is never caller supplied.

`ExternalPinEvidence` is frozen, stores canonical projection bytes privately,
returns a detached projection, and exposes
`external_pin_evidence_sha256 = SHA256(canonical_projection_bytes)` as a
separate immutable property. The digest is not self-embedded in the projection.

The evidence contains no path, SID, token record, ACL, display name, timestamp,
status text, OS error, payload duplicate, manifest bytes, or caller assertion.

### Exact read and recheck order

1. snapshot and accept the effective reader;
2. resolve and validate ProgramData without creation;
3. open only the fixed drive root, prove NTFS/ReFS/open-by-ID, and recheck token;
4. walk and hold the actual ProgramData anchor and constant dedicated
   directories by enumeration and ID;
5. verify anchor and dedicated security before selecting pin content;
6. select the exact pin leaf from held-parent enumeration and require one
   ordinary non-reparse regular file, link count one, one unnamed data stream,
   and exact end-of-file 65;
7. read at most 66 bytes from that same handle, require exact EOF at byte 65,
   validate 64 lowercase hexadecimal bytes plus LF, and parse the digest;
8. re-open and compare the effective token; requery every descriptor, object
   snapshot, stream state, and complete held-parent membership; and
9. return evidence only after every comparison is equal.

No partial evidence is returned.

## Closed Reader Failure Taxonomy

`ExternalPinReaderError` is a `RuntimeError` with one immutable `.code`. The
code/message table is exactly:

| Code | Message |
| --- | --- |
| `unsupported_platform` | `Clean-memory external pin reading is unsupported` |
| `unsupported_filesystem` | `Clean-memory external pin storage is unsupported` |
| `unsupported_security` | `Clean-memory external pin security inspection is unsupported` |
| `untrusted_reader` | `Clean-memory external pin reader is not authorized` |
| `security_policy_mismatch` | `Clean-memory external pin security policy is invalid` |
| `pin_missing` | `Clean-memory external pin is missing` |
| `malformed_pin` | `Clean-memory external pin payload is invalid` |
| `redirected_boundary` | `Clean-memory external pin boundary is redirected` |
| `unexpected_entry_type` | `Clean-memory external pin entry type is unsupported` |
| `duplicate_identity` | `Clean-memory external pin identity is ambiguous` |
| `sharing_conflict` | `Clean-memory external pin is not quiescent` |
| `observation_raced` | `Clean-memory external pin changed during observation` |
| `observation_failed` | `Clean-memory external pin observation failed` |

Classification is exact:

- non-Windows or missing held-handle, file/volume, enumeration, open-by-ID, or
  Known Folder locator ABI is `unsupported_platform`;
- non-fixed, non-NTFS/ReFS, or no-open-by-ID storage is
  `unsupported_filesystem`;
- missing token, duplication, security-descriptor, ACL, generic-mapping, or
  effective-access ABI, or an unsupported ACE form, is `unsupported_security`;
- a rejected effective token is `untrusted_reader`;
- an inspected owner/DACL/access policy mismatch is
  `security_policy_mismatch`;
- stable absence of any dedicated chain component or pin is `pin_missing`;
- non-exact 65-byte content is `malformed_pin`;
- reparses, wrong types, duplicate/zero/colliding IDs, incompatible sharing,
  and before/after changes use the matching reused codes; and
- every other locator, access, enumeration, metadata, read, or close failure is
  `observation_failed`.

Raw paths, SIDs, system messages, HRESULTs, Win32 codes, and exception details
remain only as chained causes.

Three independent current-byte reviews challenged the shared identity owner,
handle lifecycle, observer test split, token duplication/restriction semantics,
owner/group/DACL retrieval, ACE-mask representation, descriptor-control bits,
failure classification, and deterministic security-policy preimage. The audit
was corrected at those boundaries and all three final reviews returned clean.

`manual_recovery_required` is not a reader code. It remains reserved for an
uncertain first-publication operation that may have crossed its durable commit
point. Without authoritative publication history, a passive reader cannot
distinguish never-published absence from later loss. Manifest-versus-pin digest
mismatch belongs to later authenticated composition, not this reader.

## Extraction Verification Gate

The extraction checkpoint is complete only when:

1. the shared module has the exact four-symbol API, standard-library-only
   imports, lazy ABI loading, and no import-time capability use;
2. the observer retains its exact four-symbol public API and exact outward
   evidence/errors;
3. low-level ABI/flag, NTFS/ReFS ID and canonical physical-identity rendering,
   enumeration, sharing, stream, handle-state reparse/device, same-handle hash,
   and reverse-close oracles move to the shared backend tests without
   duplication; an adapter-level assertion retains exact outward identity JSON;
4. observer-level alias, stable-absence, deep traversal, parent drift, evidence,
   error, and pre-open reparse/device no-open/no-hash ordering tests remain in
   the adapter suite; mixed tests are split rather than weakened;
5. new RED tests cover non-fixed/unsupported/no-open-by-ID volume gates,
   post-open reparse rejection, successful registration, explicit-close
   deregistration, foreign/repeated/post-context close rejection, failed-open
   nonretention, reverse-order exit, attempt-all close behavior, primary-
   exception preservation with and without a pre-existing cause;
6. a native Windows trace still opens only the drive root by path;
7. exact AST/import tests prove `cli -> steps.common`, no `steps.common -> cli`,
   no private-symbol import, and no dynamic import escape;
8. the focused shared/adapter pair and the full configuration/candidate/
   filesystem/membership authority union pass;
9. compile, import-purity, documentation-authority/index, semantic-drift,
   banned-token, dependency, diff, and three independent current-byte review
   gates pass; and
10. no live ProgramData, pin, token, ACL, configured root, service, data,
    Qdrant, evidence store, job, MiniAgent, or cleanup target is read or changed.

Rollback is one checkpoint revert: the observer's private backend returns
intact and no persisted/runtime schema requires reconciliation.

## Handoff

R-07 remains `IN_PROGRESS`. The next bounded mission is only the extraction-
parity source/test seam above. The pin reader, enrollment, publication,
authenticated composition, protected-member observation, Qdrant observation,
runnable planning, and cleanup execution remain closed.
