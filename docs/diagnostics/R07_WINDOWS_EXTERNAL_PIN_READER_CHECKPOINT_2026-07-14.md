<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows External-Pin Reader Checkpoint

## Outcome

The audited no-argument Windows external-pin reader and its held-handle
lifecycle support are implemented and privately checkpointed:

```text
a82cd743 test: close external pin cleanup gaps
017f0f64 feat: implement held-handle external pin reader
```

`read_external_pin()` now resolves the fixed Windows authority location,
authenticates the effective reader and exact security policy, observes every
component through owned no-follow handles, reads the exact bounded pin payload,
rechecks all authority state, and returns detached path-free evidence.

This checkpoint implements only the read-only trust-root observer. It does not
enroll, publish, rotate, or recover a pin; compose authenticated protected
membership; observe Qdrant; create a runnable cleanup plan; issue approval;
execute cleanup; or verify a live production trust root.

## Closed Contract

- The reader has no public arguments and preserves the exact four-symbol module
  export.
- Import is capability-pure: native DLL binding and backend construction occur
  only inside the public call after the Windows platform gate.
- The known authority path is resolved from the fixed Known Folder boundary;
  descendants are selected by exact parent enumeration and opened by physical
  ID through the public held-handle backend.
- One baseline token is retained. Thread/process token comparison handles and
  per-object duplicate tokens are short-lived and owned before each native
  handle-producing call.
- Reader enrollment, owner/group/DACL parsing, ordered ACE policy, generic
  mapping, and `AccessCheck` results are validated before pin content is read.
- The pin payload is exactly one lowercase SHA-256 line, read once through the
  bounded same-handle backend. Every descriptor, object, membership, stream,
  and token dependency is rechecked before evidence construction.
- Returned evidence is a detached immutable ten-key projection. It contains no
  path, raw handle, pointer, SID, descriptor, token buffer, Win32 code, or native
  error detail.
- Backend owners are inserted into the lifecycle ledger before `CreateFileW`
  or `OpenFileById`. Context exit drains that ledger in exact reverse order
  without allocating a snapshot and continues after every `BaseException`.
- Startup, operation, backend-cleanup, and native-cleanup failures are converted
  to the closed public taxonomy. Cleanup graphs are cause-first, linear,
  allocation-independent, cycle-aware, and capped at 256 input nodes; an
  over-depth or cyclic graph receives one explicit processing-failure sentinel.
- Exactly 256 acyclic cleanup nodes are accepted without that sentinel.

## TDD And Oracle Hardening

The reader first failed the frozen public contract and lifecycle tests. The
implementation then remained unstaged while independent reviews found and
closed these additional oracle gaps:

- owner construction and ledger insertion must both precede native acquisition;
- the reserved owner must be visible and live during each native open;
- startup sanitizer allocation failure must use a preallocated public fallback;
- cyclic and over-depth cleanup graphs must terminate without raw leakage;
- public cleanup output must be linear and acyclic;
- exact-cap and over-cap cleanup behavior must differ correctly;
- reverse cleanup must positively match `handle = self._handles[-1]` inside one
  in-place drain loop, rejecting constructors, copies, slices, multiplication,
  comprehensions, literals, and delegated or `for`-loop snapshots; and
- static import containment must reject direct and indirect dynamic loading,
  including `__builtins__` dictionary/attribute indirection.

Three final reviewers inspected the same exact source and test hashes and
returned clean.

## Fresh Verification

The final committed byte lock passed with the explicit `goodq_core` interpreter:

| Gate | Result |
|---|---:|
| Reader plus held-handle backend | 616 passed |
| Approved six-file clean-memory authority union | 946 passed |
| Documentation authority unit suite | 35 passed |
| Python compilation | passed |
| Exact import/public-export gate | passed |
| Documentation authority and semantic drift | passed |
| Banned-token and dependency drift | passed |
| Staged source census | exactly 2 files |
| Staged diff check | passed |
| Independent backend/lifecycle review | CLEAN |
| Independent adapter/parity review | CLEAN |
| Independent parser/test-oracle review | CLEAN after corrections |

The reviewed committed hashes are:

```text
cli/clean_memory_external_pin.py
6726CECB556C4C32DA362C330079F86E8A4460534B8966374AE6919FCF9410D9

steps/common/windows_held_handle.py
1A2587F8EF288A282BAAC8CD71C29260E45175FF31813F45FD240DFE89FD982E

tests/unit/test_clean_memory_external_pin.py
D1A0A4FA7DECE6C6D479539AAFEF1211937BE9A265AE09737DC6E93E5883501A

tests/unit/test_windows_held_handle.py
CCB6B24F54452A64817698B1CDD2EAC4E00A6E9160FAEF6619D36EEAE5E375D9
```

No live ProgramData location, production pin, token, ACL, configured root,
service, GoodQ data, Qdrant store, evidence store, job, MiniAgent, or cleanup
authority was read or changed. Tests used fakes and bounded pytest-owned
temporary filesystem witnesses only.

## No-Repeat Boundary

Do not add a second external-pin reader, reopen descendants by pathname, expose
raw native state, move reader security policy into the projection-neutral
backend, weaken the exact-cap cleanup rule, or repeat the completed reader setup
without contradictory focused evidence.

## Next Bounded Mission

Perform one read-only no-repeat audit of authenticated protected-membership
composition. It must identify the single authority that joins the completed
configuration projection, filesystem observation, protected-membership
projection, and external-pin evidence before Qdrant observation or runnable
planning.

Do not implement that join until its exact inputs, digest bindings, precedence,
failure taxonomy, import boundary, and focused test seam are selected. Pin
enrollment/publication/rotation/recovery, live trust-root verification, Qdrant
observation, planning, approval, and cleanup execution remain closed.
