<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Windows Security-Descriptor Checkpoint

## Outcome

The projection-neutral same-handle security-descriptor capability is
implemented and privately checkpointed:

```text
882dc70 feat: add Windows security descriptor reads
```

`WindowsHeldHandleBackend` now has an opt-in `security_read` profile. The
default `observation` profile retains its prior rights and native dependency
surface. The security profile adds `READ_CONTROL` only to descendants opened
through `open_by_id()` and returns an exact detached self-relative security
descriptor from the same opaque held handle.

This checkpoint supplies one filesystem primitive required by the future
external-pin reader. It does not parse owner, group, or ACL policy; open or
duplicate a process token; call `AccessCheck`; resolve ProgramData; read a live
pin; or add enrollment, publication, planning, approval, or cleanup authority.

## Closed Contract

The exact public changes are:

```python
WindowsHeldHandleBackend(*, access_profile: str = "observation")

def read_security_descriptor(self, handle: object) -> bytes:
    ...
```

- The only accepted profiles are exact strings `observation` and
  `security_read`; invalid values fail before native capability loading.
- Observation mode neither loads Advapi32 nor requires or binds `LocalFree`.
- The volume-root handle remains at exact access `0x81` in both profiles.
- Only security-profile `open_by_id()` descendants add `READ_CONTROL`, for
  exact access `0x20081`; share mode, security attributes, and flags are
  unchanged.
- Only live, owner-bound descendant tokens issued by that security-profile
  backend may request a descriptor. Root, default-profile, foreign, closed,
  and post-context tokens fail before a security call.
- `GetSecurityInfo` receives the exact held handle, `SE_FILE_OBJECT`, and
  owner/group/DACL information flags. Its returned status code is authoritative
  and is not replaced with stale thread last-error state.
- Error-path output is undefined and never inspected or freed. A successful
  non-null output is validated for descriptor form, revision, self-relative
  control, and inclusive length 20 through 131072 bytes.
- The exact bytes are copied before `LocalFree`; native storage is freed once,
  and cleanup failure prevents successful return.
- Primary failures retain their original cause and traceback. A cleanup failure
  is attached without replacing the primary failure.
- The module remains standard-library-only, import-pure, and an exact
  four-symbol export. Raw handles, descriptor pointers, and private token state
  are not exposed through the supported public API.

## TDD And Oracle Hardening

The first RED proved the exact constructor and descriptor method were absent.
Behavioral RED then covered profile validation, native ABI binding, rights,
token provenance, same-handle copying, validation order, native ownership,
cleanup precedence, and lifecycle failures.

Independent test review subsequently found and closed these oracle gaps before
checkpoint:

- both DLL loads now prove `use_last_error=True`;
- every descriptor validator proves it receives the exact pointer returned by
  `GetSecurityInfo`;
- both primary-plus-cleanup exception branches preserve error 6 evidence;
- the inclusive 131072-byte maximum has a success oracle;
- the native witness validates descriptor form without imposing future reader
  owner/group/DACL policy;
- full open-call receipts prove only descendant access rights change;
- returned `GetSecurityInfo` status is distinguished from stale last error;
- invalid-descriptor failure remains causeless; and
- observation mode proves it can initialize without the `LocalFree` export.

All three final reviewers inspected the same exact implementation and test
bytes and returned clean.

## Fresh Verification

The committed implementation bytes passed with the explicit `goodq_core`
interpreter:

| Gate | Result |
|---|---:|
| Security-profile focused slice | 30 passed |
| Shared Windows backend | 101 passed |
| Existing filesystem observer parity | 46 passed |
| Native temporary-file descriptor witness | passed |
| Approved clean-memory authority union | 431 passed |
| Python compilation | passed |
| Exact import/export and dependency-parity checks | passed in focused suite |
| Documentation authority and semantic drift | passed |
| Banned-token and dependency drift | passed |
| Staged implementation census | exactly 2 files |
| Staged/worktree blob equality and diff check | passed |
| Independent backend/lifecycle review | CLEAN |
| Independent adapter/parity review | CLEAN |
| Independent test-oracle review | CLEAN after corrections |

The reviewed committed working-tree hashes are:

```text
steps/common/windows_held_handle.py
A9BF65A616C6A5D178285B269059D2AF011AFEE7F476A8B059BA2E8B8DA166AF

tests/unit/test_windows_held_handle.py
AD39076F2B0018389560B59FFDC2EDE0BA63D38CB93C087E8C3AA6A7708EDEE4
```

No live ProgramData location, pin, token, ACL, configured root, service, GoodQ
data, Qdrant store, evidence store, job, MiniAgent, or cleanup authority was
read or changed. The native witness performed bounded drive-root and ancestor
enumeration to reach its pytest temporary directory; descriptor retrieval
targeted only the test-created file, and the witness changed no ACL.

## No-Repeat Boundary

Do not add a second descriptor backend, expose a raw handle or native pointer,
reopen descendants by pathname, move token or `AccessCheck` policy into the
shared filesystem primitive, or reopen the completed bounded-read and observer
contracts without contradictory focused evidence.

## Next Bounded Mission

Implement only the audited read-only Windows external-pin reader in
`cli/clean_memory_external_pin.py` with focused tests in
`tests/unit/test_clean_memory_external_pin.py`. It must consume the public
held-handle backend, own effective-token and security-policy decisions, accept
no public arguments, return only detached path-free evidence, and preserve the
closed failure taxonomy and exact read/recheck order.

Enrollment, publication, rotation, authenticated membership composition,
protected-member observation, Qdrant observation, runnable planning, cleanup
execution, and live trust-root verification remain closed.
