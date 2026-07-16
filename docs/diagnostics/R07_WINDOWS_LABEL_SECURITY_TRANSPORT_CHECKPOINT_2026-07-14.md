<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows Label-Security Transport Checkpoint

## Outcome

Private checkpoint `6b40d8e8` closes the label-aware held-handle transport
prerequisite selected by the protected-manifest security-policy decision.

`WindowsHeldHandleBackend` now accepts one new exact opt-in profile,
`security_read_label`. It uses the existing held descendant handle and public
`read_security_descriptor()` method to request owner, group, DACL, and
mandatory-label information with exact `GetSecurityInfo` mask `0x17`.

The existing default `observation` profile and opt-in `security_read` profile
remain exact. In particular, `security_read` still requests only owner, group,
and DACL with mask `0x7`.

## Exact Diff

Only two files changed:

- `steps/common/windows_held_handle.py` adds the exact profile, label flag, and
  profile-specific request-mask selection; and
- `tests/unit/test_windows_held_handle.py` freezes exact profile acceptance,
  native binding/open parity, `0x7` versus `0x17`, common validation and cleanup
  behavior, and the Windows-native temporary-file witness.

No token inspection, descriptor parser, DACL policy, generic mapping,
`AccessCheck`, manifest reader, evidence schema, enrollment, publication,
candidate-plan persistence, approval, or cleanup behavior was added.

## Preserved Transport Contract

Both security profiles:

- load the same pointer-width-exact existing Win32 security surface;
- leave the volume-root open at exact native access `0x00000081`;
- add `READ_CONTROL` only to held descendant directory/file opens, producing
  exact desired access `0x00020081`;
- reject volume-root, foreign, closed, and post-context tokens before security
  transport;
- validate native success, a non-null valid revision-1 self-relative security
  descriptor, and the exact inclusive 131,072-byte bound;
- detach the descriptor before `LocalFree`;
- preserve native-error, validation-error, and cleanup-error precedence; and
- keep the public class, method signatures, exception type, exports, and import
  boundary unchanged.

Only the security-information mask differs:

| Profile | Exact mask |
|---|---:|
| `security_read` | `0x00000007` |
| `security_read_label` | `0x00000017` |

## TDD Evidence

RED added the new-profile acceptance, exact-mask, descendant-rights, and native
transport oracles before production changed. Against the prior backend:

```text
3 failed, 2 passed, 139 deselected
```

All failures were the exact absent-profile rejection. The existing
`security_read` controls passed.

After the minimal production change, the identical selection passed:

```text
5 passed, 139 deselected
```

The Windows-only pytest-owned temporary-file case executed the real held-handle
`GetSecurityInfo(..., 0x17)` path successfully. It read no configured or
production ACL and performed no ACL mutation.

Independent review then identified one test-oracle gap: label mode did not yet
run the existing negative, structural-validation, allocation-cleanup, and
lifecycle matrix. Production behavior was unchanged while those exact tests
were parameterized across both security profiles. The strengthened targeted
selection passed:

```text
28 passed, 139 deselected
```

## Fresh Verification

The final staged bytes passed these sequential `goodq_core` gates:

| Gate | Result |
|---|---:|
| Windows held-handle backend | 167 passed |
| Windows external-pin reader | 477 passed |
| Combined transport/reader authority | 644 passed |
| Exact two-file Python compilation | passed |
| Staged diff check | passed |
| Independent current-byte review | READY |

The final reviewed staged diff hash was
`b4e2636dddd903440b5641558b9dcbe0152b5581`. Reviewed file hashes were:

```text
93E690A4A7DFC31D77B954717F4216D517BFC2091E3FA7F5896470315E01A837  windows_held_handle.py
83B2600EA78ECD0C703144829AA57732B12466BC2E0AFA2CD67D3AA597D6524E  test_windows_held_handle.py
```

## Exact Limitation

This checkpoint proves transport, not policy deployment. The `0x17` descriptor
is a filtered owner/group/DACL/mandatory-label view, not a complete Windows
access-policy replay. The native temporary-file witness does not prove the
selected exact `0xb014` control or ACE envelope. CandidatePlanStore positive ACL
compatibility also remains unproven. Those require a later TCB-owned test-only
enrollment/integration witness.

## Next Bounded Mission

Run only a read-only no-repeat ownership/parity audit of the projection-neutral
security mechanics required by the selected manifest policy. Inventory the
completed private external-pin token/security implementation and shared
boundaries; decide whether exact token snapshots, filtered-descriptor parsing,
fixed generic mapping, and bounded mutation-denial checking should be extracted
or adapted without changing the completed pin reader.

Do not implement mechanics, inspect a live token or ACL, create the manifest
reader, or reopen enrollment/publication during that audit.

## Evidence Boundary

Implementation and verification used repository source, fake native adapters,
and pytest-owned temporary files only. No live ProgramData, production pin,
manifest, token, configured or production ACL, configured/protected root,
service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup target
was read or changed.
