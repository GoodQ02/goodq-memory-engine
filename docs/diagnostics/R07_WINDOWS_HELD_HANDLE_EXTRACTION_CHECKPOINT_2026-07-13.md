<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows Held-Handle Extraction Checkpoint

## Outcome

The projection-neutral Windows held-handle backend is implemented and privately
checkpointed:

```text
0f567557 refactor: extract Windows held-handle backend
```

The checkpoint moves the already-proven no-follow Win32 handle mechanics from
the filesystem observer into `steps/common/windows_held_handle.py`. The observer
now depends only on that module's exact public API while retaining its prior
configuration projection, role traversal, evidence schema, POSIX behavior, and
finite outward error contract.

This is extraction parity only. It adds no Known Folder lookup, effective-token
authority, owner or DACL inspection, external-pin read, enrollment, publication,
rotation, protected-member observation, planning, approval, or cleanup behavior.

## Exact Boundary

The shared module exports exactly:

- `WindowsHeldHandleError`;
- `WindowsDirectoryEntry`;
- `WindowsObjectSnapshot`; and
- `WindowsHeldHandleBackend`.

The backend's non-dunder public method surface is exactly:

- `open_root(root)`;
- `volume_filesystem(handle)`;
- `enumerate_directory(handle, filesystem)`;
- `open_by_id(volume_handle, entry, *, directory)`;
- `snapshot(handle, *, filesystem, expected, object_kind,
  require_stream_contract)`;
- `hash_file(handle)`; and
- `close(handle)`.

Win32 constants, ctypes structures, DLL exports, raw handles, and helper state
remain private. The module is standard-library-only and import-pure; Win32
capabilities are loaded only when the backend is constructed. Failed capability
binding is translated into the finite path-free error contract with native
details retained only as chained causes.

The backend issues opaque owner-bound handle tokens, rejects foreign, repeated,
and post-context use, deregisters before raw close, closes retained handles in
reverse order, attempts every close, and preserves primary exception, cause,
context, and traceback semantics. The shared frozen snapshot is the sole owner
of canonical Windows physical-identity projection and JSON rendering.

## Parity Evidence

Witnessed RED/GREEN cycles covered:

- the missing shared module and exact four-symbol API;
- frozen entry/snapshot/error contracts and exact finite messages;
- opaque token ownership, terminal close, reverse context close, and post-exit
  rejection;
- fixed NTFS/ReFS volume and open-by-ID gates;
- exact Win32 ABI layouts, restart/continuation enumeration, NTFS 64-bit IDs,
  and ReFS 128-bit IDs;
- early device/reparse rejection, stable same-handle snapshots, stream
  inventory, bounded FILETIME conversion, and same-handle SHA-256;
- constructor load and missing-export failure translation;
- adapter-only dependency authority, context-managed backend ownership, exact
  outward error translation, and opaque-handle test doubles; and
- primary-error preservation for explicit and context-exit close failures,
  including backend-primary native cause plus translated cleanup context.

Independent current-byte review found and closed exact-message drift, leaked
public ABI state, incomplete capability binding, missing close-lifecycle oracles,
weak import/dynamic-import gates, raw-integer adapter doubles, duplicate sharing
ownership, and incomplete nested error translation. The final backend,
adapter-parity, and test-oracle reviews returned clean.

The native Windows witnesses prove that only the drive root is opened by path
and that an incompatible writer maps to `sharing_conflict` through the shared
backend. The latter witness exists only in the shared suite; the adapter suite
retains only observer-level parity.

## Fresh Verification

The exact committed implementation bytes passed with the explicit `goodq_core`
interpreter:

| Gate | Result |
|---|---:|
| Shared backend plus observer adapter | 92 passed |
| Native root-only path and incompatible-writer witnesses | 2 passed |
| Approved clean-memory authority union | 376 passed |
| Python compilation | passed |
| Staged implementation census | exactly 4 files |
| Staged diff check | passed |
| Independent backend/lifecycle review | CLEAN |
| Independent adapter/parity review | CLEAN |
| Independent test-oracle review | CLEAN |

The committed byte hashes are:

```text
cli/clean_memory_filesystem.py
82E8C35E6D095D4F57A4C2686844D70A9F99B337C3C3379F69E3153A44BF3126

steps/common/windows_held_handle.py
0912B510BAA96A70B82CE27FF7E41426B0D31B2E5B98AB477A775D2DE8185105

tests/unit/test_clean_memory_filesystem.py
D838EF1868B72DE7AFA1F3410E89175415409F1181C09E22BE8004E66D16BAF2

tests/unit/test_windows_held_handle.py
95E3E936FB0BBF07F17BF2CBF83DFE098870BEB1F4C4124592174A13467ADE15
```

No live ProgramData location, pin, token, ACL, configured root, service, GoodQ
data, Qdrant store, evidence store, job, MiniAgent, or cleanup authority was
read or changed. Test filesystem access remained inside pytest temporary roots.

## No-Repeat Boundary

Do not recreate, copy, or privately import the held-handle implementation. Do
not reopen the completed observer public contract or canonical Windows identity
renderer without contradictory focused evidence. Future Windows authority
readers must consume this public shared backend and add only their separately
approved security-specific capabilities.

## Next Bounded Mission

Implement only the audited read-only Windows external-pin reader in
`cli/clean_memory_external_pin.py` with focused tests in
`tests/unit/test_clean_memory_external_pin.py`. Preserve the no-argument public
contract and the exact evidence, token, security, payload, recheck, and finite
error semantics selected by the boundary audit. Do not inspect a live pin,
enroll or publish trust material, change ACLs, compose authenticated membership,
or add planning or cleanup authority during that seam.
