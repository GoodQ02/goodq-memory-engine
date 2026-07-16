<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Filesystem Observer Boundary Audit

## Decision

Keep the completed configuration projection at checkpoint `a12ceb18` and the
immutable candidate-plan authority at checkpoint `c870a1cb` closed. No existing
repository helper can safely acquire the exact filesystem evidence those
authorities require.

The next implementation seam is exactly one import-pure observer and its focused
test oracle:

- `cli/clean_memory_filesystem.py`;
- `tests/unit/test_clean_memory_filesystem.py`.

The observer accepts only an exact `ResolvedPlanConfiguration` instance,
revalidates its canonical projection digest before filesystem access, and
returns one frozen `FilesystemObservation`. It does not load configuration,
accept a path override, infer authority from the current directory or
environment, contact a service, write evidence, build or persist a plan, create
a job or token, call MiniAgent, or perform cleanup.

The Windows implementation must not use absolute descendant pathname opens.
It must bind a local volume root, walk names through held-directory enumeration,
and open each selected child by its enumerated file identifier. This documented
Win32 route preserves the literal no-follow invariant without introducing an
undocumented NT-native dependency. If the required volume, filesystem, identity,
or open-by-ID capability is unavailable, observation fails closed; there is no
pathname fallback.

## Governing Invariant

The observer is passive target evidence collection, not cleanup or configuration
authority. It may inspect only the exact epoch root and target paths already
bound by the typed configuration projection. It must never traverse a symbolic
link, junction, mount-point reparse boundary, or other redirected entry; never
convert an access, sharing, scan, identity, or race failure into absence; and
never return partial evidence.

An accepted observation proves a deterministic, complete, path-free pre-state
for one ordinary epoch directory, six singleton files, and every regular file
below its exact FAISS root. Destructive execution remains a later authority and
must revalidate the same identities under its own quiescence and lease contract.

## No-Repeat Result

The following work is complete and is not reopened by this seam:

- strict configuration projection and its three-symbol public API;
- exact clean-memory topology and protected-role census;
- immutable candidate-plan authority and first-writer evidence store;
- cleanup-only action-job, approval, and MiniAgent request foundations;
- the passive plan-orchestration audit and its no-Qdrant/no-executor boundary.

The observer reuses the existing downstream `FilesystemTargetEvidence` record.
It does not modify `cli/clean_memory.py`, `steps/common/clean_memory.py`, or their
completed tests.

## Current Source Findings

### Reusable contracts and patterns

- `steps/common/clean_memory.py` already defines `FilesystemTargetEvidence`,
  `ResolvedCleanupScope`, the six required singleton roles, canonical target
  ordering, absent-target semantics, and duplicate physical-identity rejection.
- Its `lstat` reparse predicate and ancestor-walk tests are useful oracle
  patterns, but not safe target-opening primitives.
- Existing Windows junction fixtures and outside-canary tests provide the right
  style for proving that redirected content was never opened or read.
- Existing SHA-256 loops demonstrate bounded chunking, but only the loop body is
  reusable after the observer owns an already verified handle.

### Helpers rejected for direct reuse

| Surface | Reason it cannot implement this observer |
| --- | --- |
| `steps/common/atomic_io.py` | Its `CreateFileW` reader uses `FILE_ATTRIBUTE_NORMAL`, omits `FILE_FLAG_OPEN_REPARSE_POINT`, and opens an absolute pathname. It follows redirected components. |
| `steps/common/clean_memory.py` publication helpers | They are evidence-store-specific and perform separate path checks and reads; their pathname windows are not target-observation authority. |
| `steps/common/model_cache_inspector.py` | It resolves paths, later uses following file/glob calls, imports unrelated configuration/YAML authority, scans a subset, and fails soft. |
| `api/routes/runtime.py` storage scanner | It is deliberately partial and fail-soft, skips entries and errors, and records neither physical identity nor content digest. |
| Existing ingestion, retrieval, watchdog, and test hash helpers | They open by pathname and do not bind no-follow identity, before/after metadata, parent membership, or race evidence. |
| `pathlib` and high-level Windows `os` traversal | Python 3.10 has no Windows `O_NOFOLLOW`, `openat`/`dir_fd`, or directory-descriptor `scandir` equivalent. Full-path post-checking detects some redirection only after traversal. |

No repository implementation of `OpenFileById`,
`GetFileInformationByHandleEx`, `GetVolumeInformationByHandleW`,
`FILE_FLAG_OPEN_REPARSE_POINT`, or an equivalent exact Windows component walk
was found.

The established dependency direction is `cli` to `steps.common`; no
`steps.common` module imports `cli`. Because the observer must runtime-check the
exact `cli.clean_memory.ResolvedPlanConfiguration` class while emitting the
common `FilesystemTargetEvidence` type, placing it under `steps/common` would
create the first reverse-layer edge. The selected CLI-layer adapter preserves
the existing direction and must not be re-exported from `cli.clean_memory`.

## Selected Public Contract

`cli/clean_memory_filesystem.py` exposes exactly:

```text
FILESYSTEM_OBSERVATION_SCHEMA
FilesystemObservationError
FilesystemObservation
observe_filesystem
```

Its `__all__` tuple contains those four names in that order and no others.

`FILESYSTEM_OBSERVATION_SCHEMA` is exactly
`goodq.clean-memory-filesystem-observation.v1`. The module imports only
`ResolvedPlanConfiguration` from `cli.clean_memory` and
`FilesystemTargetEvidence` from `steps.common.clean_memory`; that acyclic import
shape and import purity are explicit test oracles.

`observe_filesystem(configuration)` accepts only an instance whose exact type is
`cli.clean_memory.ResolvedPlanConfiguration`. It rejects subclasses, mappings,
paths, backends, root overrides, noncanonical or tampered projection bytes,
digest mismatch, and host/path-flavor mismatch before reading the filesystem.
Platform adapters remain private implementation details.

`FilesystemObservation` is frozen and contains only:

```text
schema
configuration_scope_sha256
epoch_id
epoch_root_identity_json
filesystem_targets
```

`filesystem_targets` is an immutable tuple of the existing frozen
`FilesystemTargetEvidence` type. The result contains no timestamp, absolute
path, status narrative, partial flag, raw exception, or persisted-report
location.

`FilesystemObservationError` is a `RuntimeError` with one read-only `.code`
attribute. Its code and exact `str(error)` are limited to this table:

| Code | Message |
| --- | --- |
| `invalid_configuration` | `Clean-memory filesystem configuration is invalid` |
| `unsupported_platform` | `Clean-memory filesystem observation is unsupported` |
| `unsupported_filesystem` | `Clean-memory filesystem does not support the configured storage` |
| `required_root_missing` | `Clean-memory epoch root is missing` |
| `redirected_boundary` | `Clean-memory filesystem boundary is redirected` |
| `unexpected_entry_type` | `Clean-memory filesystem entry type is unsupported` |
| `duplicate_identity` | `Clean-memory filesystem identity is ambiguous` |
| `sharing_conflict` | `Clean-memory filesystem target is not quiescent` |
| `observation_raced` | `Clean-memory filesystem changed during observation` |
| `observation_failed` | `Clean-memory filesystem observation failed` |

Raw paths, operating-system error text, and exception details remain chained
internally and never appear in the error code, message, or observation.
Classification is exact: type/projection/digest/flavor failures are
`invalid_configuration`; an unsupported host or missing required host API is
`unsupported_platform`; a non-fixed drive, non-NTFS/ReFS filesystem, or missing
open-by-ID capability is `unsupported_filesystem`; stable epoch-root absence is
`required_root_missing`; a symlink, junction, mount, or reparse entry is
`redirected_boundary`; nonordinary entries, noncanonical names, and named
alternate streams are `unexpected_entry_type`; hardlinks, case aliases, zero or
duplicate IDs, and physical-identity collisions are `duplicate_identity`;
Windows `ERROR_SHARING_VIOLATION` is `sharing_conflict`; changed before/after
membership, identity, metadata, stream, or content state is
`observation_raced`; all other access, enumeration, metadata, or read failures
are `observation_failed`.

## Exact Evidence Semantics

The epoch root is required to exist as one ordinary directory. A missing,
redirected, irregular, inaccessible, or identity-unsupported epoch root is a
failure, not an empty observation.

The observer emits exactly six singleton records first, in this order:

1. `memory_database` -> `memory.db`;
2. `memory_database_wal` -> `memory.db-wal`;
3. `memory_database_shm` -> `memory.db-shm`;
4. `knowledge_graph_database` -> `knowledge_graph.db`;
5. `knowledge_graph_database_wal` -> `knowledge_graph.db-wal`;
6. `knowledge_graph_database_shm` -> `knowledge_graph.db-shm`.

Every emitted record has `target_type="regular_file"`. Every relative path must
already satisfy the complete downstream `_validate_relative_path` contract:
non-empty NFC text, `/` separators only, no absolute or empty/dot/dot-dot
component, no backslash, colon, NUL/control character, leading/trailing
whitespace, dot/space component suffix, Windows reserved base name, or
noncanonical POSIX spelling. An observed filesystem name that cannot be emitted
under that exact contract fails the whole observation.

Only a leaf that is absent from two unchanged enumerations of its held parent is
absent evidence. Its record is exactly `exists=False` with `size_bytes`,
`mtime_ns`, `file_identity_json`, and `sha256` all `None`. Permission, sharing,
identity, enumeration, or open errors never become absence.

The FAISS root is optional. A stably absent FAISS leaf yields no `faiss_file`
records. If present, it must be an ordinary directory. Every regular file below
it is observed regardless of name, extension, hidden status, or configuration
declaration. Empty ordinary directories are allowed; links, reparses, devices,
sockets, FIFOs, and other irregular entries fail the entire observation.

FAISS records use role `faiss_file` and epoch-relative paths of the form
`faiss/<member>`. They follow the six singleton records in canonical relative-
path order. Windows case-equivalent names and duplicate physical identities are
rejected. A regular file with more than one hard link is rejected because a
volume-global identity could otherwise bind cleanup evidence to an unobserved
name outside the target tree.

For every present file, size, modification time, physical identity, and SHA-256
come from one verified open handle. Identity, size, modification time, change
time, link count, alternate-stream inventory where supported, and parent
name-to-ID membership are checked before and after hashing. Any difference fails
with no partial result.

Canonical persisted identity JSON is compact, sorted, path-free, and versioned:

- NTFS uses exactly
  `{"file_id":"<16 lowercase hex>","file_id_kind":"ntfs_file_index_64","object_kind":"directory|regular_file","schema":"goodq.windows-file-identity.v1","volume_serial":"<16 lowercase hex>"}`.
  `file_id` is the unsigned value composed from
  `BY_HANDLE_FILE_INFORMATION.nFileIndexHigh/Low`, and it must equal the
  enumerated unsigned 64-bit ID.
- ReFS uses exactly
  `{"file_id":"<32 lowercase hex>","file_id_kind":"refs_file_id_128","object_kind":"directory|regular_file","schema":"goodq.windows-file-identity.v1","volume_serial":"<16 lowercase hex>"}`.
  `file_id` is the 16 `FILE_ID_128.Identifier` bytes in increasing array-index
  order, hex encoded, and must equal the enumerated extended ID byte-for-byte.
- Both Windows forms use the unsigned 64-bit
  `FILE_ID_INFO.VolumeSerialNumber`, formatted as 16 lowercase hexadecimal
  digits, and require the same value on every retained handle.
- POSIX uses exactly
  `{"device":"<unsigned decimal>","inode":"<unsigned decimal>","object_kind":"directory|regular_file","schema":"goodq.posix-file-identity.v1"}`
  from one `fstat` result.

The Windows NTFS file ID is never derived by truncating a ReFS identifier.
All identity strings use UTF-8-compatible JSON with sorted keys and compact
separators. `object_kind` is exactly `directory` or `regular_file`.

Windows reads `FILE_BASIC_INFO.LastWriteTime.QuadPart` as a signed 64-bit tick
count, requires `filetime_ticks >= 116444736000000000`, and computes `mtime_ns`
as `(filetime_ticks - 116444736000000000) * 100`. POSIX uses `st_mtime_ns`.
Below-epoch, negative, overflowed, or non-integer results fail closed because
downstream evidence requires a nonnegative integer.

## Windows No-Follow Backend

The Windows backend is lazy-loaded through `ctypes` and follows this exact
capability walk:

1. Parse the already-canonical drive path without resolving it. Derive only its
   drive root spelling with a trailing backslash.
2. Call `GetDriveTypeW` on that explicit root and require exactly `DRIVE_FIXED`.
   Unknown, missing, removable, remote, CD-ROM, and RAM-disk roots are
   unsupported; the current directory is never consulted.
3. Open only the drive root with `CreateFileW`: desired access
   `FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES`, share mode `FILE_SHARE_READ`,
   creation `OPEN_EXISTING`, and flags
   `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS`. Query and reject
   any reparse root.
4. Query `GetVolumeInformationByHandleW`; require `NTFS` or `ReFS` plus
   `FILE_SUPPORTS_OPEN_BY_FILE_ID`. Query `FileIdInfo` and retain its unsigned
   64-bit volume serial and exact root identity.
5. Enumerate each held directory and match the exact projected component name.
   Every logical NTFS enumeration pass starts with
   `FileIdBothDirectoryRestartInfo`, continues with `FileIdBothDirectoryInfo`,
   and ends only at `ERROR_NO_MORE_FILES`. ReFS uses
   `FileIdExtdDirectoryRestartInfo` then `FileIdExtdDirectoryInfo` under the same
   rule. Parse every returned buffer; never open a descendant by pathname.
6. On NTFS, open the exact enumerated 64-bit ID using
   `FILE_ID_DESCRIPTOR.FileIdType`. Compare it with the opened handle's combined
   `BY_HANDLE_FILE_INFORMATION.nFileIndexHigh/Low` value.
7. On ReFS, open the exact enumerated 128-bit ID using
   `FILE_ID_DESCRIPTOR.ExtendedFileIdType`. Compare it byte-for-byte with the
   opened handle's `FILE_ID_INFO.FileId.Identifier`.
8. Directory `OpenFileById` calls use desired access
   `FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES`, share mode `FILE_SHARE_READ`,
   and flags `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS`.
   Regular-file calls use `FILE_READ_DATA | FILE_READ_ATTRIBUTES`, share mode
   `FILE_SHARE_READ`, and flags
   `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN`. Security
   attributes are null. Omitting `FILE_SHARE_WRITE` and `FILE_SHARE_DELETE`
   makes an incompatible writer, mapping, delete, or rename a fail-closed
   `sharing_conflict` rather than unleased evidence.
9. Before content read, query `FileAttributeTagInfo`, `FileIdInfo`,
   `FileBasicInfo`, `FileStandardInfo`, and NTFS/ReFS `FileStreamInfo`. Reject
   reparse attributes/tags, wrong type, zero ID, volume mismatch, multiple links
   on a regular file, or enumerated/opened identity mismatch. A regular file
   must expose exactly one unnamed `::$DATA` stream whose size matches the
   standard end-of-file size. A directory must return `ERROR_HANDLE_EOF` or an
   empty `$DATA` stream inventory; any directory stream record, including
   `::$DATA` or a named `:$DATA` stream, is `unexpected_entry_type`. Deleting an
   object must never delete bytes absent from the single represented file hash.
10. Hash only the unnamed stream from that same verified regular-file handle.
    Re-query all handle metadata and stream inventory, then re-enumerate the held
    parent from its restart class and require unchanged name/type/ID membership.
11. Before returning, perform a fresh full restart enumeration of every held
    directory and require identical canonical name/type/ID membership.

`OpenFileById` is volume-global rather than parent-relative. Held-parent
enumeration before any read and after each read binds the volume ID back to the
exact logical name. ID reuse remains a theoretical platform race; restrictive
sharing, held handles, volume binding, parent revalidation, and full metadata
comparison bound that risk for passive evidence. The implementation must state
this limitation and must never silently degrade to full-path `CreateFileW`.

Unknown or non-fixed drives, unsupported filesystems, missing capability flags,
unsupported directory information classes, zero IDs, and any ID-open failure
map to the finite error contract above. They are never a reason to follow a
pathname.

## POSIX No-Follow Backend

The POSIX backend opens only `/` first, with
`O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK`, and then walks
every projected absolute-path component from held parent descriptors with
`os.open(..., dir_fd=parent_fd)`. Directories use the same flags; regular-file
candidates use `O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK`. It enumerates
held directory descriptors, opens children relative to those descriptors,
immediately `fstat`s every returned descriptor, and reads content only after
proving it is one ordinary regular file. FIFO, socket, device, symlink, and
directory-to-file swaps are never read or hashed; `O_NONBLOCK` prevents an
irregular replacement from hanging the observer. Files require `st_nlink == 1`.
The backend hashes from the same descriptor and repeats `fstat` plus parent
membership checks before returning.

If `dir_fd`, descriptor `scandir`, `O_NOFOLLOW`, or required descriptor metadata
is unavailable, the platform is unsupported. It does not fall back to
`Path.resolve`, `Path.open`, or pre/post pathname `stat` calls.

## Race and Failure Oracle

The focused suite must prove all of the following:

- import purity and the exact four-symbol public API;
- literal observation schema, finite error codes/messages, exact identity JSON,
  `target_type`, and Windows/POSIX `mtime_ns` conversion;
- rejection of non-projection input, tampered projection bytes, digest mismatch,
  and path-flavor/host mismatch before filesystem access;
- exact hashes, sizes, times, identities, order, immutability, and repeated
  field-equal output with identical canonical identity strings on an unchanged
  temporary tree;
- all six absent-singleton records contain no stale state;
- stable absent FAISS yields zero FAISS records;
- hidden, nested, unknown-extension, and undeclared regular FAISS files are all
  included deterministically;
- non-NFC, control-bearing, colon/backslash, dot/space-suffixed, reserved,
  dot/dot-dot, and otherwise noncanonical FAISS member names fail before output;
- access and sharing failures are errors, never absence;
- missing or irregular required epoch roots fail closed;
- root, ancestor, directory, target, dangling link, junction, and reparse cases
  fail before any outside-canary content is opened or read;
- hardlinks, Windows case aliases, directories in singleton positions, and
  irregular FAISS members fail closed;
- mid-read mutation, same-size/same-mtime replacement, absent-to-present change,
  rename, add/remove, directory replacement, ID/name drift, and ancestor swap
  return no evidence;
- Windows NTFS-64/ReFS-128 selection, missing open-by-ID capability, unknown or
  remote filesystem, zero ID, volume mismatch, and ID-open failure have no
  pathname fallback;
- Windows accepts only `DRIVE_FIXED`, uses exact root/open access/share/flag
  values, restarts every logical enumeration, consumes multiple buffers through
  `ERROR_NO_MORE_FILES`, requires exactly one unnamed regular-file `$DATA`
  stream, and rejects every directory `$DATA` stream record;
- no absolute descendant open occurs after the volume/root handle is bound;
- POSIX opens only `/` by pathname, walks thereafter by held descriptors, and a
  FIFO/device/irregular swap cannot block or reach a content read;
- the observer import graph remains acyclic in the established
  `cli -> steps.common` direction and does not load unrelated runtime authority;
- output composes with `ResolvedCleanupScope` using injected Qdrant and
  protected-boundary stubs without changing either completed authority.

The negative-capability harness must prove no configuration or environment
read, current-directory inference, `Path.resolve`, network, process, sleep,
mkdir, write, unlink, rename, replace, chmod, Qdrant access, evidence-store
access, candidate-plan construction/persistence, job/token work, MiniAgent
import, candidate-evidence read, or filesystem access beneath configured
protected roots. Reading their already-projected path strings for digest and
shape revalidation is not protected-root observation.

## Corrected Later Sequence

The earlier passive-orchestration audit listed configuration projection,
filesystem observation, Qdrant observation, and runnable plan orchestration.
Current projection evidence exposes one missing authority: eight protected roles
remain deliberately unresolved. Filesystem-target and Qdrant evidence therefore
cannot yet compose a production `ResolvedCleanupScope`.

The corrected order is:

1. completed configuration projection;
2. exact target filesystem observer;
3. a separate read-only audit and checkpoint for protected-boundary authority,
   reusing only the proven platform identity backend and never guessing roots;
4. fail-closed Qdrant observer;
5. runnable `plan` orchestration only when every protected role is exact.

If external authority for any protected role is still unavailable, runnable
planning remains explicitly fail closed. The target observer does not absorb
this missing authority or read protected roots.

## Primary Documentation Evidence

The configured Context7 Python 3.10 documentation confirmed that device and
inode identify an object, `follow_symlinks=False` is supported where advertised,
Windows has no `O_NOFOLLOW`, and directory-descriptor operations are Unix-only.
The following Microsoft documentation fixes the Windows contract:

- `CreateFileW` and `FILE_FLAG_OPEN_REPARSE_POINT`:
  <https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilew>
- `GetFileInformationByHandleEx` directory and identity classes:
  <https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex>
- restart-versus-continuation directory information classes:
  <https://learn.microsoft.com/windows/win32/api/minwinbase/ne-minwinbase-file_info_by_handle_class>
- `FILE_STREAM_INFO` alternate-stream enumeration:
  <https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_stream_info>
- NTFS directory and file stream semantics:
  <https://learn.microsoft.com/openspecs/windows_protocols/ms-fscc/c54dec26-1551-4d3a-a0ea-4fa40f848eb3>
  and
  <https://learn.microsoft.com/openspecs/windows_protocols/ms-fscc/f8762be6-3ab9-411e-a7d6-5cc68f70c78d>.
- signed `FILE_BASIC_INFO` timestamps:
  <https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_basic_info>
- `OpenFileById` and its reparse/directory flags:
  <https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-openfilebyid>
- `FILE_ID_DESCRIPTOR` and NTFS/ReFS ID forms:
  <https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_id_descriptor>
- `GetVolumeInformationByHandleW` and `FILE_SUPPORTS_OPEN_BY_FILE_ID`:
  <https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew>
- `GetDriveTypeW` fixed-versus-remote root classification:
  <https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-getdrivetypew>
- exact Windows handle identities in `FILE_ID_INFO` and
  `BY_HANDLE_FILE_INFORMATION`:
  <https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_id_info>
  and
  <https://learn.microsoft.com/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information>.

## Evidence Boundary

This audit read repository source, tests, active governance documents, current
Python 3.10 documentation through Context7, and official Microsoft Win32
documentation. Three independent read-only discovery lanes reconciled Windows
identity, complete enumeration, API shape, and the RED matrix; a fourth bounded
placement review corrected the source module to preserve dependency direction.
No configured data, database, FAISS content, service, Qdrant state, model,
ingestion, identity, WSL, mixed main checkout, public checkout, operator report,
or protected root was read or changed.

Final-byte independent review and repository documentation gates are recorded
in the checkpoint that selects this exact implementation seam.
