<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows Reader-Identity Policy Checkpoint

## Outcome

The selected shared GoodQ Windows reader-identity policy is implemented and
privately checkpointed:

```text
02530486 Extract clean-memory Windows reader identity policy
```

`steps/common/clean_memory_windows_reader_identity.py` now owns the exact
ordinary-reader acceptance policy and the private frozen v1 identity preimage.
It accepts only detached exact mechanics snapshots and returns no raw identity
projection: callers receive either successful validation or one lowercase
SHA-256 digest.

The completed external-pin reader delegates early identity validation and late
digest production to that shared authority while retaining route selection,
reader enrollment, descriptor/access policy, outward errors, evidence, race
fencing, and cleanup ownership.

This checkpoint does not create the protected-manifest reader, read a live
token or descriptor, enroll or publish an authority artifact, compose protected
membership, contact Qdrant, create a cleanup plan, issue approval, or execute
cleanup.

## Closed Public Contract

The shared module exports exactly:

```python
__all__ = (
    "CleanMemoryWindowsReaderIdentityError",
    "validate_clean_memory_windows_reader_identity",
    "clean_memory_windows_reader_identity_sha256",
)
```

Both functions require:

- an exact `WindowsTokenSnapshot`;
- an exact imported base or mandatory-policy profile string; and
- an exact non-boolean unsigned-64 change-notify LUID.

The fixed policy error subclasses `ValueError` and contains only the path-free
message `Clean-memory Windows reader identity is not authorized`. Caller-shape
failures remain closed `TypeError` or `ValueError` failures.

The base profile requires `mandatory_policy is None`. The mandatory-policy
profile accepts only exact integer `1` or `3`. Validation preserves the prior
ordinary-reader domain: it does not require ChangeNotify to be present or
enabled and does not add policy over mechanics-owned or previously ignored
fields.

## Frozen v1 And Adapter Parity

The v1 schema, selected fields, ordering, numeric grammar, canonical JSON
options, and SHA-256 remain byte-exact. Mandatory policy, profile, and the
standalone LUID argument stay outside the preimage; accepted privilege records,
including their LUID values, remain inside it. The projection, schema constant,
canonical bytes, and result shape remain private.

The external adapter now:

1. acquires the same base-profile snapshot and change-notify LUID;
2. validates that snapshot before storage traversal;
3. preserves every existing route, descriptor, access, content, race, and
   cleanup operation;
4. completes `_final_authority_recheck()`; and
5. produces the digest from the same snapshot, profile, and LUID.

Shared policy rejection maps to existing external `untrusted_reader`.
Caller-shape and unexpected shared failures map to sanitized
`observation_failed`. The external four-symbol API, thirteen errors, evidence
bytes/digests, base 17-call token profile, 39/5/19 trace, and cleanup order are
unchanged.

## TDD And Oracle Hardening

RED first proved the shared module and API were absent, the external adapter
still owned private policy/projection, and delegation/timing were missing. The
implementation then passed direct and adapter GREEN before independent review.

Those reviews found and closed five test-oracle gaps without changing product
behavior:

- a complex v1 vector now locks ordered records, lowercase hexadecimal,
  signed expiration, and decimal counts;
- profile, mandatory-policy, and LUID fences are exercised through both public
  entrypoints;
- external mandatory-policy-neutral digest parity remains additive;
- the external ownership guard rejects assignment aliases as well as function
  aliases; and
- both adapter hooks prove object identity with the retained baseline snapshot.

## Fresh Verification

All commands used the explicit `goodq_core` interpreter and synthetic or fake
test surfaces only.

| Gate | Result |
| --- | ---: |
| Direct reader-identity policy | 65 passed |
| External-pin collection census | 499 collected |
| External-pin integration baseline | 499 passed |
| Shared Windows security mechanics | 254 passed |
| Historical held-handle baseline | 167 passed |
| Filesystem-observer parity | 46 passed |
| Canonical validator plus membership | 205 passed |
| Expanded clean-memory authority union | 1,422 passed |
| Exact four-file Python compilation | passed |
| Import, dependency, API, and AST containment | passed in focused suites |
| Documentation semantic drift | 349 active files; zero active violations |
| Banned-token and dependency drift | passed |
| Implementation file census | exactly four files |
| Committed diff check | passed |
| Independent specification/quality review | APPROVED |
| Independent adversarial lifecycle/byte review | READY |

The reviewed committed SHA-256 hashes are:

```text
cli/clean_memory_external_pin.py
4A867080888564EFF276B9672D098D93A8CEF99339EBA2AA036D7B388045D4F1

steps/common/clean_memory_windows_reader_identity.py
C06822426346D5EA3B8BF64AC1C19C870D398ABAC0EC69453BFBF0E072645CE1

tests/unit/test_clean_memory_external_pin.py
9FEE801E2163E083FD81C58980CA31CE327B927C344E2B243AD756E10455815F

tests/unit/test_clean_memory_windows_reader_identity.py
F637F9B9AD2A31D86581918E9E6E7C133A11F25B5A58756B725ECC4937532338
```

No live token, ACL, descriptor, configured or protected root, manifest, pin,
service, GoodQ data, Qdrant store, evidence store, job, MiniAgent, or cleanup
target was read or changed.

## No-Repeat Boundary

Do not recreate the reader-identity policy or frozen v1 projection inside a
consumer, move GoodQ policy into projection-neutral mechanics, export the raw
preimage, or reopen the completed external adapter without contradictory
focused evidence.

The shared policy is not proof of token provenance, enrolled-SID equality,
descriptor or label policy, access results, manifest content, external-pin
agreement, or race safety. Each physical reader retains those responsibilities.

## Next Bounded Mission

Perform one read-only no-repeat decision audit of the protected-manifest
reader's public contract and its exact input and outward-error fence. Reconcile
the completed configuration projection, external-pin evidence, protected-
manifest validator, protected-membership projection, held-handle transport,
security mechanics, manifest security-policy decision, and shared reader-
identity policy.

Do not create reader source or tests until that audit selects the exact module,
exports, evidence boundary, direct-input validation, finite errors, precedence,
and smallest rollback seam. Enrollment, publication, rotation, recovery,
authenticated composition, Qdrant observation, runnable planning, approval,
and cleanup execution remain closed.
