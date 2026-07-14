<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows Bounded-Read Capacity Extension Checkpoint

## Outcome

Private checkpoint `617cd32a` completes the exact projection-neutral transport
prerequisite selected by the protected-manifest reader capability-gap audit.

`WindowsHeldHandleBackend.read_file_bounded()` now accepts an exact integer from
1 through `4_194_305`. Its method name, signature, return contract, EOF
semantics, ownership checks, same-handle rewind, native-error translation,
lifecycle, cleanup, module exports, and backend public method set are unchanged.

The external-pin protocol is unchanged. Its reader still makes exactly one
bounded request at 66 bytes to prove EOF for the exact 65-byte pin payload. This
checkpoint supersedes only the earlier shared method's 66-byte *accepted-
argument ceiling*; it does not alter the external pin, manifest size contract,
or any reader authority.

## Exact Diff

Only two files changed:

- `steps/common/windows_held_handle.py` changes one production boundary literal
  from `66` to `4_194_305`;
- `tests/unit/test_windows_held_handle.py` adds maximum-size fake/native EOF and
  exact-cap oracles and changes the over-maximum invalid case to `4_194_306`.

No second read API, manifest constant, parser, token/descriptor policy,
filesystem adapter, external-pin adapter, protected-manifest reader, service,
dependency, or other runtime behavior was added.

## Preserved Contract

The method still:

- rejects booleans, integer subclasses, non-integers, zero, negatives, and
  values above its exact ceiling before native seek/read;
- validates a live opaque token owned by the active backend;
- rewinds the same native handle;
- requests only positive reads bounded by remaining capacity;
- rejects impossible native counts;
- treats only a successful zero-byte read as an EOF witness;
- returns `(prefix, False)` immediately upon reaching the cap, without an extra
  read; and
- preserves path-free shared error translation and reverse lifecycle cleanup.

The new ceiling is transport capacity only. It does not authorize a manifest,
select a file, define canonical meaning, or interpret security evidence.

## TDD Evidence

The two focused maximum-cap tests were added before production changed.

RED against the prior `<= 66` boundary:

```text
2 failed, 139 deselected
```

Both failures occurred at pre-native-I/O argument validation because exact
`4_194_305` was not yet accepted.

After the one-line production change, the identical focused selection passed:

```text
2 passed, 139 deselected
```

The expanded bounded-read selection passed:

```text
24 passed, 117 deselected
```

The oracles prove:

- exact `4_194_305` is accepted;
- exact `4_194_306` is rejected before native I/O;
- a 4,194,304-byte payload with cap 4,194,305 returns complete bytes and
  `eof_observed=True` only after the explicit zero-byte read;
- a 4,194,305-byte payload with the same cap returns the exact capped bytes and
  `eof_observed=False` without an extra read; and
- native Windows temporary-file coverage exercises both boundary cases.

## Fresh Regression Evidence

The final bytes passed these sequential `goodq_core` regressions:

```text
tests/unit/test_windows_held_handle.py          141 passed
tests/unit/test_clean_memory_external_pin.py   477 passed
tests/unit/test_clean_memory_filesystem.py      46 passed
                                                ----------
                                                664 passed
```

Python compilation passed for the shared backend, external-pin reader, and
filesystem observer. Both staged and unstaged diff checks passed.

An independent task reviewer compared the exact `e03f94fe..617cd32a` bytes with
the frozen task brief and returned spec PASS, no critical/important/minor issue,
and task quality Approved. Controller-side fresh regression runs reproduced all
664 passing tests and compilation success. A second bounded oracle review
independently returned clean for the exact boundaries, EOF/no-extra-probe trace,
native Windows cases, and preserved 66-byte pin assertions.

## Remaining Reader Blockers

This checkpoint closes only byte capacity. The protected-manifest reader remains
unauthorized until both independent prerequisite branches complete:

1. one pure canonical manifest validator is selected, extracted, and proven
   parity-preserving for structural membership; and
2. the manifest-specific owner/write policy is selected, followed by only the
   shared token, descriptor-parsing, and effective-access mechanics that policy
   proves necessary beyond the completed detached descriptor read.

ProgramData locator/recheck, protected-member observation, pin/member lexical
and physical exclusions, final composition, Qdrant observation, runnable
planning, approval, and cleanup remain later closed seams.

## Next Bounded Mission

Run a read-only no-repeat boundary audit of canonical protected-manifest
validation. Select one pure projection-neutral validator ownership/API and an
extraction/parity seam that lets both structural membership and the future
physical reader consume the same authority. Do not modify membership or create
reader code during that audit.

The manifest security-policy decision remains a separate mandatory
prerequisite. Completing parser extraction later must not be reported as reader
readiness.

## Evidence Boundary

Implementation and verification used repository source, tests, fake native
adapters, and pytest-managed temporary files only. No live ProgramData, pin,
manifest, token, ACL, configured or protected root, service, GoodQ data, Qdrant,
evidence store, job, MiniAgent, or cleanup target was read or changed.
