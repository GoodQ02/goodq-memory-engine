<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows Security Mechanics Extraction Checkpoint

## Outcome

The selected projection-neutral Windows security-mechanics extraction is
implemented and privately checkpointed:

```text
ae4d35bc feat: establish Windows security mechanics ABI
0827193a feat: extract Windows security mechanics
```

`steps/common/windows_security_mechanics.py` is now the sole owner of bounded
token observation, retained token/duplicate ownership, filtered descriptor
parsing, one stable descriptor allocation, exact file generic mapping, and the
closed one-mask mutation-denial `AccessCheck` envelope. The completed external-
pin reader delegates those mechanics while retaining every GoodQ-specific
policy and outward contract.

This checkpoint does not create the protected-manifest reader, move the frozen
reader-identity v1 schema/digest into shared authority, enroll or publish a pin,
read or modify a production ACL, authorize cleanup, or touch configured data.

## Ownership Boundary

The shared module owns only projection-neutral mechanics:

- exact Win64 ABI verification and caller-supplied native bindings;
- base and mandatory-policy token profiles, with class 27 absent from base;
- immutable token, SID, ACL, ACE, descriptor, and denial observations;
- nonconstructible/noncopyable capability owners for sessions, descriptors,
  and access scopes;
- one retained baseline token, short-lived comparison tokens, and one private
  duplicate per open descriptor scope;
- DACL-only and mandatory-label descriptor profiles over one retained ctypes
  allocation used for both parsing and `AccessCheck`;
- exact file generic mapping and a closed single-mask mutation-check set; and
- path-free mechanics errors with deterministic cleanup and control-flow graph
  preservation.

The external-pin adapter still owns:

- its frozen public API, thirteen errors, evidence bytes, and digests;
- Known Folder resolution and native DLL load/failure order;
- the fixed five-object route, names, roles, and rights;
- reader enrollment, intrinsic token acceptance, SID/DACL policy, expected
  denial outcomes, and first-failure precedence;
- the base 17-call token profile only; and
- the frozen reader-identity v1 projection/digest and security-policy/evidence
  projections.

The held-handle backend, protected-manifest validator, and protected-membership
projection were not modified.

## TDD And Adversarial Corrections

The implementation began with RED oracles for the missing shared API and
unadapted external owner. Independent current-byte review then exposed and
closed lifecycle defects that ordinary success-path tests would not catch:

- all failed thread/process token outputs are cleared before last-error
  retrieval, so an interrupt during error retrieval cannot close a native
  failure sentinel;
- control-flow rethrows preserve the original object, traceback tail, cause,
  context, alias topology, and exact suppress-context flag;
- shared/held cleanup-link translation cannot replace a control-flow primary
  when translation itself fails;
- public and cleanup-only rethrows do not acquire an unrelated active handler
  as private exception context; and
- access-scope cleanup, session cleanup, and outer backend cleanup preserve the
  selected ordering and close ownership exactly once.

The final regression matrix covers `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit`, false suppression, direct cause/context aliasing, translation
fallback, all four token-open failure paths, shared helper cleanup-only
rethrows, external cleanup-only rethrows, and direct access-scope close.

## Frozen Parity Evidence

The final external integration trace still proves:

- 39 token snapshots;
- five private duplicate-token scopes;
- 19 bounded mutation checks;
- no class-27 query in the external base profile;
- DACL-only parsing with explicit rejection of both null and non-null SACL
  presence;
- immediate stop on the first non-denial or observation failure;
- access-scope close before the post-access token fence; and
- byte-exact public evidence and digest parity.

The mandatory-policy metamorphic oracle proves otherwise-identical values `1`
and `3` compare unequal in shared snapshots while producing identical frozen
external reader-identity v1 bytes and SHA-256. Structurally valid values `0`
and `2` remain observations, not accepted future manifest policy.

## Fresh Verification

All commands used the explicit `goodq_core` interpreter and fake native
adapters. The final implementation bytes passed:

| Gate | Result |
|---|---:|
| Shared Windows security mechanics | 254 passed |
| Adapted external-pin reader | 499 passed |
| Historical held-handle baseline | 167 passed |
| Filesystem-observer parity | 46 passed |
| Expanded clean-memory authority union | 1,357 passed |
| Exact four-file Python compilation | passed |
| Source containment/public surface | passed in focused suites |
| Documentation semantic drift | passed; 347 active files scanned |
| Banned-token and dependency drift | passed |
| Implementation file census | exactly 4 files |
| Staged diff check | passed |
| Independent policy/parity review | READY |
| Independent lifecycle/cleanup review | READY after corrections |

The pre-extraction historical baselines were 167 held-handle tests and 477
external-pin tests. The final counts are 167 and 499 respectively, so neither
baseline dropped. Low-level mechanics coverage moved to the new 254-test shared
suite; adapter policy and integration coverage remained in the external suite.

The reviewed committed SHA-256 hashes are:

```text
cli/clean_memory_external_pin.py
A9BC491BA913445FCEC1BE0F5EB75294AA4CF86E1FFB23CBA24E7AB4853DE8D0

steps/common/windows_security_mechanics.py
3B5ED47107BB459455E63D98516ECDD23E80423D8C9B963D0734669452AB1A70

tests/unit/test_clean_memory_external_pin.py
5A1DF971FB5DEEA736747B2DF928AAFA600CA7C8852B83416E85F66E9BF9F060

tests/unit/test_windows_security_mechanics.py
554049E680431082CFAF8CFB3E2B71F7DE49AB308CFA6595D6BA8D9B6F8FB123
```

No live token, configured or production ACL/root, manifest, pin, service,
GoodQ data, Qdrant store, evidence store, job, MiniAgent, or cleanup target was
read or changed.

## No-Repeat Boundary

Do not recreate token layouts, descriptor parsers, duplication, generic
mapping, `AccessCheck`, or their cleanup graphs inside a consumer. Do not move
GoodQ roles, trusted SIDs, DACL sequences, accepted token values, expected
access outcomes, consumer errors, or evidence schemas into the shared mechanics
module. Do not rerun the completed extraction without contradictory focused
evidence.

## Next Bounded Mission

Run one read-only no-repeat reassessment of the separate frozen reader-identity
v1 policy seam. Determine its exact ownership and reuse boundary before any
protected-manifest reader is authorized. Reconcile the completed external-pin
projection/digest, protected-manifest policy decision, shared mechanics output,
and validator/reader inputs without implementing a reader or touching a live
identity, token, ACL, manifest, pin, or configured root.
